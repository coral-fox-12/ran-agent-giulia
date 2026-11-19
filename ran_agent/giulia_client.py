"""Giulia simulator client.

Two backends share one interface so the agent code never cares which is live:
- MockGiuliaClient: deterministic synthetic KPIs (seeded) — offline dev + tests.
- SubprocessGiuliaClient: runs real Giulia (`python main.py <config>`) in the
  upstream checkout and reads the Parquet KPI outputs back with pyarrow.

Real Giulia needs GPU + Sionna 2 + the 2.7 GB shadowing .mat files
(see docs/RESEARCH.md §7). The mock exists precisely because those are not
available before the 27/11 data drop.
"""
import json
import os
import random
import subprocess


class SimulationError(Exception):
    pass


class MockGiuliaClient:
    """Seeded synthetic network: KPIs are a deterministic function of the
    config dict, so mock runs are reproducible. NOT a radio model — a harness
    stand-in only.

    Config-response model (directional only, documented simplifications):
    config may carry per-cell overrides, e.g.
    ``{"cells": {"cell_B": {"power_dbm": 46, "tilt_deg": 4, "on": False}}}``
    and/or ``{"new_cells": ["cell_D"]}``. Baselines: 43 dBm, 6 deg tilt, on.
    - power +1 dB -> own RSRP +1 dB, own throughput +5%, own SINR +0.5 dB,
      own energy +8 W, neighbours' SINR -0.2 dB (it becomes interference),
      network coverage +0.5 pts. (Real networks: raising power also raises
      interference to neighbours and eventually saturates — the mock only
      models the first-order direction so experiments can discriminate.)
    - tilt +1 deg (more downtilt) -> own RSRP -0.3 dB (far-field loss).
    - on=False -> RSRP -140, SINR -10, throughput 0, load 0, energy 5 W;
      network coverage loses 1 + 5 * (cell load / 100) pts (a lightly loaded
      cell contributes little unique coverage — neighbours absorb it).
    - each new cell -> +3 pts coverage.
    Base draws are seeded per cell (``f"{seed}:{cell}"``) and once for the
    network, so the same cell draws the same baseline KPIs in every config
    and experiments measure only the config effect (regression-locked in
    tests/test_baseline.py)."""

    backend = "mock"

    BASE_POWER_DBM = 43.0
    BASE_TILT_DEG = 6.0
    DEFAULT_CELLS = ["cell_A", "cell_B", "cell_C"]
    OFF_CELL_KPIS = {"rsrp_dbm": -140.0, "sinr_db": -10.0,
                     "throughput_mbps": 0.0, "load_pct": 0.0, "energy_w": 5.0}

    def __init__(self, seed=42):
        self.seed = seed
        self.simulations_run = 0

    def _cell_names(self, config):
        names = list(self.DEFAULT_CELLS)
        cells = config.get("cells", {})
        if isinstance(cells, dict):
            for c in cells:
                if c not in names:
                    names.append(c)
        elif isinstance(cells, list):
            for c in cells:
                if c not in names:
                    names.append(c)
        for c in config.get("new_cells", []):
            if c not in names:
                names.append(c)
        return names

    def _kpis(self, config):
        # Base draws are seeded PER CELL (and once for the network), NOT on the
        # config dict: the same cell always draws the same baseline KPIs, so
        # two simulations differ ONLY by the config overrides applied. This is
        # what makes experiments comparable (baseline vs treatment) — seeding
        # on the config JSON would make every config draw a different network
        # and no experiment could measure anything.
        names = self._cell_names(config)
        overrides = config.get("cells", {})
        if not isinstance(overrides, dict):
            overrides = {}
        new_cells = set(config.get("new_cells", []))
        cells = {}
        for c in names:
            rng = random.Random(f"{self.seed}:{c}")
            cells[c] = {
                "rsrp_dbm": round(rng.uniform(-110, -70), 1),
                "sinr_db": round(rng.uniform(-3, 25), 1),
                "throughput_mbps": round(rng.uniform(5, 180), 1),
                "load_pct": round(rng.uniform(5, 95), 1),
                "energy_w": round(rng.uniform(40, 400), 1),
            }
        # Baseline coverage level: one seeded draw. (Mean throughput and
        # total energy are derived from the cells below, never drawn.)
        base_cov = round(random.Random(f"{self.seed}:network").uniform(82, 99.5), 1)
        # Apply per-cell overrides.
        power_delta = {}
        off_cells = []
        for c, ov in overrides.items():
            if c not in cells:
                continue
            if ov.get("on") is False:
                load = cells[c]["load_pct"]
                cells[c] = dict(self.OFF_CELL_KPIS)
                off_cells.append((c, load))
                continue
            d_p = float(ov.get("power_dbm", self.BASE_POWER_DBM)) - self.BASE_POWER_DBM
            tilt = float(ov.get("tilt_deg", self.BASE_TILT_DEG))
            power_delta[c] = d_p
            k = cells[c]
            k["rsrp_dbm"] = round(k["rsrp_dbm"] + d_p - 0.3 * (tilt - self.BASE_TILT_DEG), 1)
            k["throughput_mbps"] = round(
                k["throughput_mbps"] * max(0.1, 1 + 0.05 * d_p), 1)
            k["energy_w"] = round(max(5.0, k["energy_w"] + 8.0 * d_p), 1)
        # SINR cross-effects: own power up helps own SINR, hurts neighbours'.
        off_names = {c for c, _ in off_cells}
        for c, d_p in power_delta.items():
            if d_p == 0:
                continue
            cells[c]["sinr_db"] = round(cells[c]["sinr_db"] + 0.5 * d_p, 1)
            for other in cells:
                if other != c and other not in off_names:
                    cells[other]["sinr_db"] = round(
                        cells[other]["sinr_db"] - 0.2 * d_p, 1)
        # Network KPIs are ALWAYS derived from the cells (mean throughput and
        # total energy are the cells' mean/sum; coverage is the base draw plus
        # the config adjustments below). Deriving them keeps baseline and
        # treatment simulations comparable — a random network draw would make
        # every experiment measure noise instead of the config change.
        coverage = base_cov
        coverage += 0.5 * sum(power_delta.values())
        for _, load in off_cells:
            coverage -= 1.0 + 5.0 * (load / 100.0)
        coverage += 3.0 * len(new_cells)
        network = {
            "coverage_pct": round(min(99.9, max(0.0, coverage)), 1),
            "mean_throughput_mbps": round(
                sum(k["throughput_mbps"] for k in cells.values()) / len(cells), 1),
            "total_energy_w": round(
                sum(k["energy_w"] for k in cells.values()), 1),
        }
        return {"cells": cells, "network": network}

    def inspect_network(self, scenario):
        return {"scenario": scenario.get("id", "mock-scenario"),
                "cells": scenario.get("cells", ["cell_A", "cell_B", "cell_C"]),
                "note": "mock backend — no radio propagation is modelled"}

    def run_simulation(self, config):
        self.simulations_run += 1
        return {"sim_id": self.simulations_run, "kpis": self._kpis(config)}

    def get_kpis(self, sim_id=None):
        return self._kpis({})


class SubprocessGiuliaClient:
    """Runs the real simulator. `run_simulation` writes a Giulia config YAML
    (derived from the agent's proposed config), executes `main.py`, then loads
    the Parquet KPI dataset for the run label."""

    backend = "giulia"

    def __init__(self, giulia_dir="./giulia", python="./venv/bin/python",
                 timeout_s=1800):
        self.giulia_dir = giulia_dir
        self.python = python
        self.timeout_s = timeout_s
        self.simulations_run = 0
        if not os.path.isdir(giulia_dir):
            raise SimulationError(
                f"Giulia checkout not found at {giulia_dir!r} — run setup_giulia.sh"
            )

    def inspect_network(self, scenario):
        # The real scenario files arrive 27/11; until then this is a stub that
        # reports the scenario descriptor back. Replace with the task API then.
        return {"scenario": scenario.get("id"), "detail": "see task files (27/11)"}

    def run_simulation(self, config):
        self.simulations_run += 1
        cfg_path = os.path.join(
            self.giulia_dir, f"agent_run_{self.simulations_run}.yml")
        import yaml
        with open(cfg_path, "w") as f:
            yaml.safe_dump(config, f)
        try:
            proc = subprocess.run(
                [self.python, "main.py", cfg_path],
                cwd=self.giulia_dir, capture_output=True, text=True,
                timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            raise SimulationError(f"Giulia run timed out after {self.timeout_s}s")
        if proc.returncode != 0:
            raise SimulationError(
                f"Giulia exited {proc.returncode}: {proc.stderr[-2000:]}")
        return {"sim_id": self.simulations_run, "stdout_tail": proc.stdout[-2000:]}

    def get_kpis(self, sim_id=None):
        # KPI datasets land under outputs/ per the run config; load the latest.
        # Exact label layout depends on the 27/11 task configs — TBD.
        raise NotImplementedError(
            "get_kpis for real Giulia: wire to the task config's output labels "
            "once the 27/11 data drop defines them (see docs/RESEARCH.md §7).")


def build_simulator(cfg):
    sim = cfg["simulator"]
    if sim.get("backend") == "giulia":
        return SubprocessGiuliaClient(
            giulia_dir=sim.get("giulia_dir", "./giulia"),
            python=sim.get("python", "./venv/bin/python"),
            timeout_s=sim.get("timeout_s", 1800))
    return MockGiuliaClient(seed=cfg["eval"].get("seed", 42))
