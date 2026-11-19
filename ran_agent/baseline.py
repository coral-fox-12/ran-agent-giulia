"""Deterministic baseline agent — hypothesis -> experiment -> answer.

This is the reference agent for the mock backend. Unlike ``agent.Agent``
(ReAct loop driven by the LLM), the baseline needs NO model: it forms
hypotheses from the inspected network + baseline simulation with fixed,
documented rules, runs the cheapest discriminating experiment for each,
and answers in the task's typed schema. It exists so that:

- the harness, the mock simulator, the budgets and the answer schemas can
  be exercised end-to-end before 27/11 with zero model cost;
- there is always a fallback answer when the LLM loop hits its budget
  (the baseline NEVER raises BudgetExceeded — it degrades gracefully to
  fewer experiments, or to an inspection-only answer at 0 simulations);
- the real (Qwen) agent has a dumb-but-honest score to beat on the mock.

Rules are heuristics over mock KPIs, tuned to the mock's directional
model (see MockGiuliaClient docstring). They are NOT radio physics and
must be re-derived from real Giulia KPIs once the 27/11 task docs land.
Thresholds live at the top of this file so they are easy to retune.

Loop (per task):
  1. inspect_network (free, no simulation budget).
  2. baseline simulation (1 sim) — the "healthy" reference KPIs.
  3. rank hypotheses from the baseline KPIs (per task type).
  4. while budget remains: run the cheapest untested experiment that can
     discriminate between the surviving hypotheses; update their status.
  5. build the typed answer from the best-supported hypothesis + the last
     simulation; validate with tasks.validate_answer; return the same
     result dict shape as Agent.run() (llm_backend "baseline", 0 tokens).

Budget rules: the baseline simulation is skipped entirely when
max_simulations == 0; experiments stop the moment the budget is spent;
no step ever calls run_simulation past the cap.
"""
from . import tasks
from .config import task_budget

# --- Tunable thresholds (mock heuristics; retune against real Giulia) ---
RSRP_WEAK_DBM = -100.0      # below this a cell counts as weak / uncovered
RSRP_BAD_DBM = -105.0       # below this propagation is the prime suspect
SINR_BAD_DB = 0.0           # below this a link is effectively unusable
LOAD_HIGH_PCT = 90.0        # above this a cell counts as overloaded
LOAD_LOW_PCT = 30.0         # below this a cell is a shutdown candidate
POWER_STEP_DB = 3.0         # one experiment step for power changes
BASE_POWER_DBM = 43.0       # mock baseline transmit power per cell
BASE_TILT_DEG = 6.0
MAX_COVERAGE_LOSS_PTS = 3.0    # energy saving must not lose more coverage
# (mock model: switching a cell off costs 1 + 5*load/100 pts, so 3.0 pts
#  admits shutting down cells up to ~40% load and rejects heavier ones)
MAX_THROUGHPUT_LOSS_PCT = 10.0  # ... nor more throughput (relative)
DEFAULT_CONDITIONS = {"min_sinr_db": SINR_BAD_DB,
                      "min_rsrp_dbm": RSRP_WEAK_DBM,
                      "max_load_pct": 95.0}
ROOT_CAUSES = {"hardware", "interference", "misconfiguration",
               "propagation", "overload"}

# Synthetic mock geometry: cells get fixed grid coordinates (lat/lon around
# 40.00, -3.70) so polygon / site-placement answers can be built on the mock.
# NOT real geography — real coordinates come from the 27/11 task files.
MOCK_ORIGIN = (40.0, -3.7)


def mock_cell_xy(cell_id, cells):
    """Deterministic (lat, lon) for a mock cell id, from its order in `cells`."""
    idx = list(cells).index(cell_id) if cell_id in cells else 0
    return (MOCK_ORIGIN[0] + 0.01 * (idx // 3),
            MOCK_ORIGIN[1] + 0.01 * (idx % 3))


def bounding_polygon(points, margin=0.005):
    """GeoJSON Polygon: bounding box of (lat, lon) points, expanded by margin."""
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    lo_lat, hi_lat = min(lats) - margin, max(lats) + margin
    lo_lon, hi_lon = min(lons) - margin, max(lons) + margin
    return {"type": "Polygon", "coordinates": [[
        [lo_lon, lo_lat], [hi_lon, lo_lat], [hi_lon, hi_lat],
        [lo_lon, hi_lat], [lo_lon, lo_lat]]]}


def _worst_cell(kpis, metric, lowest=True):
    """(cell_id, value) of the worst cell by `metric` (lowest or highest)."""
    cells = kpis.get("cells", {})
    if not cells:
        return None, None
    key = (lambda kv: kv[1][metric]) if lowest else (lambda kv: -kv[1][metric])
    cell, vals = min(cells.items(), key=key)
    return cell, vals[metric]


class BaselineAgent:
    """Budget-capped hypothesis -> experiment -> answer loop (no LLM)."""

    def __init__(self, simulator, cfg, task):
        self.sim = simulator
        self.cfg = cfg
        self.task = task
        self.task_type = task["type"]
        if self.task_type not in tasks.TASK_TYPES:
            raise ValueError(f"unknown task type: {self.task_type!r}")
        self.max_sims = task_budget(cfg, self.task_type)
        self.sims_used = 0
        self.trace = []
        self.cells = []
        self.baseline_kpis = None
        self.last_kpis = None
        self.last_sim_id = None
        self.hypotheses = []   # {id, text, status, evidence[]}
        self.working_config = {"cells": {}}  # cumulative config for experiments
        self.sim_backend = getattr(simulator, "backend", "giulia")

    # -- plumbing ---------------------------------------------------------
    def _log(self, kind, payload):
        self.trace.append({"step": len(self.trace) + 1, "kind": kind,
                           "payload": payload})

    def _add_hypothesis(self, hid, text):
        hyp = {"id": hid, "text": text, "status": "open", "evidence": []}
        self.hypotheses.append(hyp)
        self._log("hypothesis", {"id": hid, "text": text})
        return hyp

    def _support(self, hyp, note):
        hyp["status"] = "supported"
        hyp["evidence"].append(note)
        self._log("observation", {"hypothesis": hyp["id"], "status": "supported",
                                  "note": note})

    def _refute(self, hyp, note):
        hyp["status"] = "refuted"
        hyp["evidence"].append(note)
        self._log("observation", {"hypothesis": hyp["id"], "status": "refuted",
                                  "note": note})

    def _run_sim(self, config, hypothesis_id, note):
        """Run one simulation if budget remains, else None (never raises)."""
        if self.sims_used >= self.max_sims:
            self._log("budget", {"note": "simulation budget spent; "
                                 f"skipping experiment for {hypothesis_id}"})
            return None
        self.sims_used += 1
        self._log("tool_call", {"name": "run_simulation",
                                "args": {"config": config,
                                         "hypothesis": hypothesis_id}})
        result = self.sim.run_simulation(config)
        self._log("tool_result", {"name": "run_simulation", "result": result})
        self.last_kpis = result["kpis"]
        self.last_sim_id = result["sim_id"]
        self._log("experiment", {"hypothesis": hypothesis_id, "note": note,
                                 "sim_id": result["sim_id"]})
        return result

    def _inspect(self):
        self._log("tool_call", {"name": "inspect_network",
                                "args": {"scenario_id": self.task["id"]}})
        info = self.sim.inspect_network(
            {"id": self.task["id"], **self.task.get("scenario", {})})
        self._log("tool_result", {"name": "inspect_network", "result": info})
        cells = info.get("cells") or self.task.get("scenario", {}).get("cells") or []
        if isinstance(cells, dict):
            cells = list(cells.keys())
        self.cells = list(cells)
        return info

    # -- main loop --------------------------------------------------------
    def run(self):
        self._inspect()
        base = self._run_sim({}, "baseline", "baseline measurement")
        if base is not None:
            self.baseline_kpis = base["kpis"]
        self._hypothesize()
        for hyp_id, config, note in self._experiments():
            result = self._run_sim(config, hyp_id, note)
            if result is None:  # budget spent — stop experimenting, keep answer
                break
            self._interpret(hyp_id, result)
        answer = self._answer()
        tasks.validate_answer(self.task_type, answer)
        self._log("answer", answer)
        return {
            "task_id": self.task["id"],
            "task_type": self.task_type,
            "answer": answer,
            "sims_used": self.sims_used,
            "llm_tokens": 0,
            "llm_backend": "baseline",
            "sim_backend": self.sim_backend,
            "trace": self.trace,
        }

    # -- hypotheses -------------------------------------------------------
    def _hypothesize(self):
        fn = getattr(self, f"_hypothesize_{self.task_type}")
        fn()

    def _hypothesize_fault_diagnosis(self):
        if not self.baseline_kpis:
            suspect = self._suspect_from_scenario() or (self.cells[0] if self.cells else "?")
            self._add_hypothesis(
                "h1", f"{suspect} is faulty (inspection-only: no simulations "
                      "available, cause undecided — defaulting to misconfiguration)")
            return
        cell, sinr = _worst_cell(self.baseline_kpis, "sinr_db")
        rsrp = self.baseline_kpis["cells"][cell]["rsrp_dbm"]
        load = self.baseline_kpis["cells"][cell]["load_pct"]
        if sinr < SINR_BAD_DB and rsrp >= RSRP_WEAK_DBM:
            cause = "interference"  # strong but noisy: neighbours interfere
        elif rsrp < RSRP_BAD_DBM:
            cause = "propagation"   # far / shadowed: signal never arrives
        elif load > LOAD_HIGH_PCT:
            cause = "overload"
        elif sinr < SINR_BAD_DB:
            cause = "misconfiguration"  # weak AND noisy, no single signature
        else:
            cause = "hardware"  # worst cell, no RF signature: suspect the box
        self._add_hypothesis(
            "h1", f"{cell} is faulty, root cause {cause}: worst SINR "
                  f"{sinr} dB, RSRP {rsrp} dBm, load {load}% in baseline sim")
        others = sorted(self.baseline_kpis["cells"],
                        key=lambda c: self.baseline_kpis["cells"][c]["sinr_db"])
        if len(others) > 1:
            self._add_hypothesis(
                "h2", f"alternative: {others[1]} is faulty instead "
                      "(second-worst SINR); kept only if the repeat run disagrees")

    def _hypothesize_outage_impact(self):
        target = (self.task.get("scenario", {}).get("outage_cell")
                  or self.task.get("scenario", {}).get("faulty_cell")
                  or self._suspect_from_scenario())
        if target is None and self.baseline_kpis:
            target, _ = _worst_cell(self.baseline_kpis, "sinr_db")
        target = target or (self.cells[0] if self.cells else "?")
        self._add_hypothesis(
            "h1", f"outage of {target}: neighbours absorb its traffic; "
                  "coverage and throughput fall measurably vs the healthy baseline")

    def _hypothesize_coverage(self):
        if not self.baseline_kpis:
            self._add_hypothesis("h1", "coverage unknown without a baseline sim")
            return
        weak = self._weak_cells(self.baseline_kpis)
        if weak:
            self._add_hypothesis(
                "h1", f"weak cells {weak} (RSRP < {RSRP_WEAK_DBM} dBm); "
                      f"cheapest fix first: +{POWER_STEP_DB} dB on the weakest, "
                      f"{weak[0]}")
        else:
            self._add_hypothesis(
                "h1", "no cell below the RSRP threshold; coverage target "
                      "already met — verify with the baseline sim only")

    def _hypothesize_radio_config(self):
        conds = self._conditions()
        if not self.baseline_kpis:
            self._add_hypothesis("h1", "conditions untestable without a baseline sim")
            return
        violations = self._violations(self.baseline_kpis, conds)
        if not violations:
            self._add_hypothesis("h1", "baseline config already meets all "
                                       "conditions — no change needed")
        else:
            worst = violations[0]
            self._add_hypothesis(
                "h1", f"{len(violations)} condition violation(s) in baseline; "
                      f"worst is {worst['cell']} ({worst['metric']} "
                      f"{worst['value']} vs limit {worst['limit']}); fix one "
                      "knob at a time, starting with its power")

    def _hypothesize_site_placement(self):
        if not self.baseline_kpis:
            self._add_hypothesis("h1", "gap unknown without a baseline sim")
            return
        weak = self._weak_cells(self.baseline_kpis)
        gap = weak[0] if weak else _worst_cell(self.baseline_kpis, "rsrp_dbm")[0]
        self._add_hypothesis(
            "h1", f"coverage gap around {gap} (weakest RSRP); candidate site "
                  "at the midpoint between the two weakest cells closes the "
                  "most gap per unit of new interference")

    def _hypothesize_energy(self):
        if not self.baseline_kpis:
            self._add_hypothesis("h1", "no saving identifiable without a baseline sim")
            return
        cell = self._shutdown_candidate()
        if cell is None:
            self._add_hypothesis("h1", "no lightly loaded cell; no safe shutdown")
            return
        load = self.baseline_kpis["cells"][cell]["load_pct"]
        self._add_hypothesis(
            "h1", f"switch off {cell} (load {load}%): coverage layer should "
                  "absorb its traffic; verify coverage/throughput hold in sim")

    # -- experiments ------------------------------------------------------
    def _experiments(self):
        """Yield (hypothesis_id, config, note) cheapest-first. The loop stops
        when the budget is spent; later experiments are simply never run."""
        fn = getattr(self, f"_experiments_{self.task_type}")
        yield from fn()

    def _experiments_fault_diagnosis(self):
        # Repeat the baseline config: on the deterministic mock this replays
        # identical KPIs, confirming the fault is stable, not a transient.
        if self.baseline_kpis is not None:
            yield ("h1", {}, "repeat baseline: same worst cell => stable fault")

    def _experiments_outage_impact(self):
        hyp = self.hypotheses[0] if self.hypotheses else None
        if hyp is None:
            return
        target = hyp["text"].split("outage of ")[1].split(":")[0]
        yield ("h1", {"cells": {target: {"on": False}}},
               f"simulate outage: switch {target} off, compare vs baseline")

    def _experiments_coverage(self):
        if not self.baseline_kpis:
            return
        weak = self._weak_cells(self.baseline_kpis)
        if not weak:
            return
        cell = weak[0]
        self.working_config["cells"][cell] = {"power_dbm": BASE_POWER_DBM + POWER_STEP_DB}
        yield ("h1", self._snapshot_config(),
               f"raise {cell} power +{POWER_STEP_DB} dB, measure coverage")

    def _experiments_radio_config(self):
        if not self.baseline_kpis:
            return
        conds = self._conditions()
        # Adaptive loop: each step boosts the currently most-violated cell.
        # Implemented as a generator that re-reads last KPIs each iteration.
        while True:
            violations = self._violations(self.last_kpis, conds)
            if not violations:
                return
            worst = violations[0]
            cell = worst["cell"]
            cur = self.working_config["cells"].get(cell, {})
            new_power = cur.get("power_dbm", BASE_POWER_DBM) + POWER_STEP_DB
            self.working_config["cells"][cell] = {"power_dbm": new_power}
            yield ("h1", self._snapshot_config(),
                   f"raise {cell} power to {new_power} dBm "
                   f"(fixes {worst['metric']} {worst['value']} vs {worst['limit']})")
            # Re-check after the sim runs (the run loop calls _interpret,
            # which updates last_kpis); stop if the next check would be the
            # same cell with no improvement — guarded by the budget anyway.
            if self.sims_used >= self.max_sims:
                return

    def _experiments_site_placement(self):
        if not self.baseline_kpis:
            return
        yield ("h1", {"new_cells": ["cell_new"]},
               "place candidate site cell_new at the gap midpoint, measure coverage")

    def _experiments_energy(self):
        if not self.baseline_kpis:
            return
        cell = self._shutdown_candidate()
        if cell is None:
            return
        yield ("h1", {"cells": {cell: {"on": False}}},
               f"switch off lightly loaded {cell}, check coverage/throughput hold")
        # The run loop interprets the shutdown sim before pulling the next
        # experiment, so only offer the fallback if the shutdown was refuted.
        hyp = self.hypotheses[0] if self.hypotheses else None
        if hyp is None or hyp["status"] != "refuted":
            return
        low = sorted(self.baseline_kpis["cells"],
                     key=lambda c: self.baseline_kpis["cells"][c]["load_pct"])[:2]
        cfg = {"cells": {c: {"power_dbm": BASE_POWER_DBM - POWER_STEP_DB}
                         for c in low}}
        yield ("h1", cfg,
               f"fallback: cut power -{POWER_STEP_DB} dB on {low} instead of switching off")

    def _snapshot_config(self):
        return {"cells": {c: dict(v) for c, v in self.working_config["cells"].items()}}

    # -- interpretation ---------------------------------------------------
    def _interpret(self, hyp_id, result):
        fn = getattr(self, f"_interpret_{self.task_type}", None)
        if fn is not None:
            fn(hyp_id, result)

    def _hyp(self, hyp_id):
        for h in self.hypotheses:
            if h["id"] == hyp_id:
                return h
        return self.hypotheses[0] if self.hypotheses else None

    def _interpret_fault_diagnosis(self, hyp_id, result):
        hyp = self._hyp(hyp_id)
        if hyp is None or self.baseline_kpis is None:
            return
        cell, _ = _worst_cell(result["kpis"], "sinr_db")
        base_cell, _ = _worst_cell(self.baseline_kpis, "sinr_db")
        if cell == base_cell:
            self._support(hyp, f"repeat sim {result['sim_id']}: same worst cell "
                               f"{cell} — fault is stable, not transient")
        else:
            self._refute(hyp, f"repeat sim {result['sim_id']}: worst cell moved "
                              f"{base_cell} -> {cell}; fault may be transient")

    def _interpret_outage_impact(self, hyp_id, result):
        hyp = self._hyp(hyp_id)
        if hyp is None or self.baseline_kpis is None:
            return
        base = self.baseline_kpis["network"]
        new = result["kpis"]["network"]
        self._support(hyp, f"outage sim {result['sim_id']}: coverage "
                           f"{base['coverage_pct']} -> {new['coverage_pct']}%, "
                           f"mean throughput {base['mean_throughput_mbps']} -> "
                           f"{new['mean_throughput_mbps']} Mbps")

    def _interpret_coverage(self, hyp_id, result):
        hyp = self._hyp(hyp_id)
        if hyp is None or self.baseline_kpis is None:
            return
        base = self.baseline_kpis["network"]["coverage_pct"]
        new = result["kpis"]["network"]["coverage_pct"]
        if new > base:
            self._support(hyp, f"power fix sim {result['sim_id']}: coverage "
                               f"{base}% -> {new}%")
        else:
            self._refute(hyp, f"power fix sim {result['sim_id']}: coverage "
                              f"unchanged/worse ({base}% -> {new}%)")

    def _interpret_radio_config(self, hyp_id, result):
        hyp = self._hyp(hyp_id)
        if hyp is None:
            return
        conds = self._conditions()
        violations = self._violations(result["kpis"], conds)
        if not violations:
            self._support(hyp, f"sim {result['sim_id']}: all conditions met")
        else:
            self._log("observation", {"hypothesis": hyp_id, "status": "open",
                                      "note": f"sim {result['sim_id']}: "
                                      f"{len(violations)} violation(s) remain"})

    def _interpret_site_placement(self, hyp_id, result):
        hyp = self._hyp(hyp_id)
        if hyp is None or self.baseline_kpis is None:
            return
        base = self.baseline_kpis["network"]["coverage_pct"]
        new = result["kpis"]["network"]["coverage_pct"]
        if new > base:
            self._support(hyp, f"placement sim {result['sim_id']}: coverage "
                               f"{base}% -> {new}%")
        else:
            self._refute(hyp, f"placement sim {result['sim_id']}: coverage "
                              f"unchanged/worse ({base}% -> {new}%)")

    def _interpret_energy(self, hyp_id, result):
        hyp = self._hyp(hyp_id)
        if hyp is None or self.baseline_kpis is None:
            return
        base = self.baseline_kpis["network"]
        new = result["kpis"]["network"]
        cov_loss = base["coverage_pct"] - new["coverage_pct"]
        tput_loss = (base["mean_throughput_mbps"] - new["mean_throughput_mbps"]) \
            / base["mean_throughput_mbps"] * 100 if base["mean_throughput_mbps"] else 0
        saved = (base["total_energy_w"] - new["total_energy_w"]) \
            / base["total_energy_w"] * 100 if base["total_energy_w"] else 0
        if (cov_loss <= MAX_COVERAGE_LOSS_PTS
                and tput_loss <= MAX_THROUGHPUT_LOSS_PCT and saved > 0):
            self._support(hyp, f"sim {result['sim_id']}: saved {saved:.1f}% energy "
                               f"for {cov_loss:.1f} pts coverage, {tput_loss:.1f}% throughput")
        else:
            self._refute(hyp, f"sim {result['sim_id']}: saving {saved:.1f}% costs "
                              f"{cov_loss:.1f} pts coverage / {tput_loss:.1f}% "
                              "throughput — exceeds the service guardrails")

    # -- answers ----------------------------------------------------------
    def _answer(self):
        fn = getattr(self, f"_answer_{self.task_type}")
        return fn()

    def _evidence_text(self):
        parts = []
        for h in self.hypotheses:
            ev = "; ".join(h["evidence"]) if h["evidence"] else "no experiment run"
            parts.append(f"{h['id']} [{h['status']}]: {h['text']} — {ev}")
        if self.baseline_kpis is None:
            parts.append("no simulations ran (budget 0); answer is inspection-only")
        return " | ".join(parts)

    def _answer_fault_diagnosis(self):
        hyp = self.hypotheses[0] if self.hypotheses else None
        if self.baseline_kpis is None:
            suspect = self._suspect_from_scenario() or (self.cells[0] if self.cells else "?")
            return {"faulty_cell": suspect, "root_cause": "misconfiguration",
                    "evidence": self._evidence_text()}
        cell, _ = _worst_cell(self.baseline_kpis, "sinr_db")
        cause = "misconfiguration"
        if hyp is not None and "root cause " in hyp["text"]:
            cause = hyp["text"].split("root cause ")[1].split(":")[0].strip()
            if cause not in ROOT_CAUSES:
                cause = "misconfiguration"
        return {"faulty_cell": cell, "root_cause": cause,
                "evidence": self._evidence_text()}

    def _answer_outage_impact(self):
        if self.baseline_kpis is None or self.last_kpis is None:
            return {"affected_cells": list(self.cells), "coverage_loss_pct": 0.0,
                    "throughput_loss_pct": 0.0,
                    "summary": "no outage simulation ran; impact unmeasured — "
                               + self._evidence_text()}
        base, new = self.baseline_kpis["network"], self.last_kpis["network"]
        cov_loss = (base["coverage_pct"] - new["coverage_pct"]) \
            / base["coverage_pct"] * 100 if base["coverage_pct"] else 0.0
        tput_loss = (base["mean_throughput_mbps"] - new["mean_throughput_mbps"]) \
            / base["mean_throughput_mbps"] * 100 if base["mean_throughput_mbps"] else 0.0
        affected = []
        target = self.hypotheses[0]["text"].split("outage of ")[1].split(":")[0] \
            if self.hypotheses else None
        if target:
            affected.append(target)
        for c, kv in self.baseline_kpis["cells"].items():
            new_t = self.last_kpis["cells"].get(c, {}).get("throughput_mbps")
            if new_t is not None and kv["throughput_mbps"] > 0 \
                    and (kv["throughput_mbps"] - new_t) / kv["throughput_mbps"] > 0.05 \
                    and c not in affected:
                affected.append(c)
        return {"affected_cells": affected or list(self.cells),
                "coverage_loss_pct": round(max(0.0, cov_loss), 1),
                "throughput_loss_pct": round(max(0.0, tput_loss), 1),
                "summary": f"outage vs healthy baseline: coverage "
                           f"{base['coverage_pct']}% -> {new['coverage_pct']}%, mean "
                           f"throughput {base['mean_throughput_mbps']} -> "
                           f"{new['mean_throughput_mbps']} Mbps "
                           f"(sims: baseline + outage). " + self._evidence_text()}

    def _answer_coverage(self):
        kpis = self.last_kpis or self.baseline_kpis
        if kpis is None:
            pts = [mock_cell_xy(c, self.cells) for c in self.cells] or [(40.0, -3.7)]
            return {"coverage_polygon": bounding_polygon(pts),
                    "coverage_pct": 0.0, "weak_cells": list(self.cells)}
        weak = self._weak_cells(kpis)
        pts = [mock_cell_xy(c, self.cells) for c in kpis["cells"]]
        return {"coverage_polygon": bounding_polygon(pts),
                "coverage_pct": kpis["network"]["coverage_pct"],
                "weak_cells": weak}

    def _answer_radio_config(self):
        kpis = self.last_kpis or self.baseline_kpis
        conds = self._conditions()
        if kpis is None:
            return {"config": {}, "meets_conditions": False, "kpis": {}}
        violations = self._violations(kpis, conds)
        return {"config": self._snapshot_config(),
                "meets_conditions": not violations,
                "kpis": kpis}

    def _answer_site_placement(self):
        kpis = self.last_kpis or self.baseline_kpis
        if self.baseline_kpis is None or kpis is None:
            pts = [mock_cell_xy(c, self.cells) for c in self.cells] or [(40.0, -3.7)]
            return {"sites": [], "coverage_polygon": bounding_polygon(pts),
                    "rationale": "no simulations ran — " + self._evidence_text()}
        weak = sorted(self.baseline_kpis["cells"],
                      key=lambda c: self.baseline_kpis["cells"][c]["rsrp_dbm"])[:2]
        pts = [mock_cell_xy(c, self.cells) for c in weak]
        mid = ((pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2) \
            if len(pts) > 1 else pts[0]
        gain = kpis["network"]["coverage_pct"] \
            - self.baseline_kpis["network"]["coverage_pct"]
        all_pts = [mock_cell_xy(c, self.cells) for c in kpis["cells"]] + [mid]
        return {"sites": [{"lat": round(mid[0], 4), "lon": round(mid[1], 4)}],
                "coverage_polygon": bounding_polygon(all_pts),
                "rationale": f"new site at midpoint of weakest cells {weak}; "
                             f"coverage {self.baseline_kpis['network']['coverage_pct']}% "
                             f"-> {kpis['network']['coverage_pct']}% "
                             f"({gain:+.1f} pts). " + self._evidence_text()}

    def _answer_energy(self):
        if self.baseline_kpis is None or self.last_kpis is None:
            return {"config": {}, "energy_saved_pct": 0.0, "kpis": {},
                    }
        base, new = self.baseline_kpis["network"], self.last_kpis["network"]
        saved = (base["total_energy_w"] - new["total_energy_w"]) \
            / base["total_energy_w"] * 100 if base["total_energy_w"] else 0.0
        cov_loss = base["coverage_pct"] - new["coverage_pct"]
        tput_loss = (base["mean_throughput_mbps"] - new["mean_throughput_mbps"]) \
            / base["mean_throughput_mbps"] * 100 if base["mean_throughput_mbps"] else 0.0
        # Only claim the saving if the last experiment kept service within
        # guardrails; otherwise fall back to the no-change answer (honest 0%).
        # The experiment history tells us which config the last sim used.
        last_cfg = self._last_experiment_config()
        if saved > 0 and cov_loss <= MAX_COVERAGE_LOSS_PTS \
                and tput_loss <= MAX_THROUGHPUT_LOSS_PCT:
            return {"config": last_cfg, "energy_saved_pct": round(saved, 1),
                    "kpis": new}
        return {"config": {}, "energy_saved_pct": 0.0,
                "kpis": self.baseline_kpis["network"]}

    # -- helpers ----------------------------------------------------------
    def _last_experiment_config(self):
        for entry in reversed(self.trace):
            if entry["kind"] == "tool_call" \
                    and entry["payload"].get("name") == "run_simulation":
                args = entry["payload"].get("args", {})
                if args.get("config"):
                    return args["config"]
        return {}

    def _weak_cells(self, kpis):
        return sorted(
            (c for c, kv in kpis["cells"].items()
             if kv["rsrp_dbm"] < RSRP_WEAK_DBM),
            key=lambda c: kpis["cells"][c]["rsrp_dbm"])

    def _shutdown_candidate(self):
        cells = self.baseline_kpis["cells"]
        low = [c for c, kv in cells.items() if kv["load_pct"] < LOAD_LOW_PCT]
        pool = low or list(cells)
        return min(pool, key=lambda c: cells[c]["load_pct"])

    def _conditions(self):
        conds = dict(DEFAULT_CONDITIONS)
        for src in (self.task.get("constraints") or {},
                    self.task.get("conditions") or {}):
            for k in ("min_sinr_db", "min_rsrp_dbm", "max_load_pct"):
                if k in src:
                    conds[k] = src[k]
        return conds

    def _violations(self, kpis, conds):
        out = []
        for cell, kv in kpis.get("cells", {}).items():
            if kv["rsrp_dbm"] < conds["min_rsrp_dbm"]:
                out.append({"cell": cell, "metric": "rsrp_dbm",
                            "value": kv["rsrp_dbm"],
                            "limit": conds["min_rsrp_dbm"],
                            "shortfall": conds["min_rsrp_dbm"] - kv["rsrp_dbm"]})
            if kv["sinr_db"] < conds["min_sinr_db"]:
                out.append({"cell": cell, "metric": "sinr_db",
                            "value": kv["sinr_db"],
                            "limit": conds["min_sinr_db"],
                            "shortfall": conds["min_sinr_db"] - kv["sinr_db"]})
            if kv["load_pct"] > conds["max_load_pct"]:
                out.append({"cell": cell, "metric": "load_pct",
                            "value": kv["load_pct"],
                            "limit": conds["max_load_pct"],
                            "shortfall": kv["load_pct"] - conds["max_load_pct"]})
        out.sort(key=lambda v: -v["shortfall"])
        return out

    def _suspect_from_scenario(self):
        """A cell id named in the scenario text (symptom / outage_cell)."""
        scenario = self.task.get("scenario", {})
        text = " ".join(str(scenario.get(k, "")) for k in
                        ("symptom", "description", "outage_cell", "faulty_cell"))
        for c in self.cells:
            if c in text:
                return c
        return None


def run_baseline(cfg, simulator, task):
    """One-call helper: run the baseline agent on a task dict."""
    return BaselineAgent(simulator, cfg, task).run()
