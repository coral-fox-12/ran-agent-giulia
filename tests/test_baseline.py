"""Tests for the deterministic baseline agent + config-responsive mock.

No GPU, no model, no Giulia, no network.
Run: python -m unittest discover -s tests -v
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ran_agent import config as cfgmod
from ran_agent import eval as ev
from ran_agent.baseline import BaselineAgent, bounding_polygon, mock_cell_xy
from ran_agent.giulia_client import MockGiuliaClient

CELLS = ["cell_A", "cell_B", "cell_C"]

# Regression lock for the seed-42 mock baseline (per-cell seeded draws).
# If these change, the mock's determinism contract broke — investigate,
# do not just update the numbers.
BASELINE_A = {"rsrp_dbm": -109.5, "sinr_db": -2.5, "throughput_mbps": 125.4,
              "load_pct": 47.3, "energy_w": 302.0}
BASELINE_B = {"rsrp_dbm": -70.1, "sinr_db": 22.4, "throughput_mbps": 171.2,
              "load_pct": 54.0, "energy_w": 353.5}
BASELINE_C = {"rsrp_dbm": -84.4, "sinr_db": 9.9, "throughput_mbps": 26.2,
              "load_pct": 38.0, "energy_w": 191.0}
BASELINE_NET = {"coverage_pct": 85.6, "mean_throughput_mbps": 107.6,
                "total_energy_w": 846.5}


def make_task(task_type, **extra):
    task = {"id": f"test-{task_type}", "type": task_type,
            "scenario": {"cells": list(CELLS)},
            "objective": "test"}
    task.update(extra)
    return task


def run_baseline(task, cfg=None, seed=42):
    cfg = cfg or cfgmod.load_config("config.yaml")
    return BaselineAgent(MockGiuliaClient(seed=seed), cfg, task).run()


class TestMockConfigResponse(unittest.TestCase):
    def test_empty_config_regression(self):
        kpis = MockGiuliaClient(seed=42).run_simulation({})["kpis"]
        self.assertEqual(kpis["cells"]["cell_A"], BASELINE_A)
        self.assertEqual(kpis["cells"]["cell_B"], BASELINE_B)
        self.assertEqual(kpis["cells"]["cell_C"], BASELINE_C)
        self.assertEqual(kpis["network"], BASELINE_NET)

    def test_same_config_same_kpis(self):
        m = MockGiuliaClient(seed=42)
        cfg = {"cells": {"cell_A": {"power_dbm": 46}}}
        self.assertEqual(m.run_simulation(cfg)["kpis"],
                         m.run_simulation(cfg)["kpis"])
        self.assertEqual(m.run_simulation({})["kpis"], m.get_kpis())

    def test_power_up_raises_rsrp_sinr_and_energy(self):
        m = MockGiuliaClient(seed=42)
        base = m.run_simulation({})["kpis"]["cells"]["cell_A"]
        boosted = m.run_simulation(
            {"cells": {"cell_A": {"power_dbm": 46}}})["kpis"]["cells"]["cell_A"]
        self.assertEqual(boosted["rsrp_dbm"], base["rsrp_dbm"] + 3.0)
        self.assertGreater(boosted["sinr_db"], base["sinr_db"])
        self.assertGreater(boosted["throughput_mbps"], base["throughput_mbps"])
        self.assertGreater(boosted["energy_w"], base["energy_w"])

    def test_power_up_hurts_neighbours_sinr(self):
        m = MockGiuliaClient(seed=42)
        base = m.run_simulation({})["kpis"]["cells"]["cell_B"]
        boosted = m.run_simulation(
            {"cells": {"cell_A": {"power_dbm": 46}}})["kpis"]["cells"]["cell_B"]
        self.assertLess(boosted["sinr_db"], base["sinr_db"])

    def test_switch_off_cell(self):
        m = MockGiuliaClient(seed=42)
        off = m.run_simulation({"cells": {"cell_C": {"on": False}}})["kpis"]
        self.assertEqual(off["cells"]["cell_C"]["throughput_mbps"], 0.0)
        self.assertEqual(off["cells"]["cell_C"]["rsrp_dbm"], -140.0)
        self.assertEqual(off["cells"]["cell_C"]["energy_w"], 5.0)
        # Other cells untouched; network reflects the loss only.
        self.assertEqual(off["cells"]["cell_A"], BASELINE_A)
        self.assertLess(off["network"]["coverage_pct"],
                        BASELINE_NET["coverage_pct"])
        self.assertLess(off["network"]["total_energy_w"],
                        BASELINE_NET["total_energy_w"])

    def test_new_cell_adds_coverage(self):
        m = MockGiuliaClient(seed=42)
        new = m.run_simulation({"new_cells": ["cell_D"]})["kpis"]
        self.assertIn("cell_D", new["cells"])
        self.assertEqual(new["network"]["coverage_pct"],
                         BASELINE_NET["coverage_pct"] + 3.0)
        # Existing cells keep their baseline draws when a cell is added.
        self.assertEqual(new["cells"]["cell_A"], BASELINE_A)


class TestBaselineAllTypes(unittest.TestCase):
    def test_every_task_type_answers_within_budget(self):
        cfg = cfgmod.load_config("config.yaml")
        for task_type in ("fault_diagnosis", "outage_impact", "coverage",
                          "radio_config", "site_placement", "energy"):
            task = make_task(task_type)
            if task_type == "outage_impact":
                task["scenario"]["outage_cell"] = "cell_B"
            if task_type == "radio_config":
                task["constraints"] = {"min_rsrp_dbm": -100, "min_sinr_db": 0}
            result = run_baseline(task, cfg)
            self.assertEqual(result["task_id"], task["id"])
            self.assertEqual(result["llm_backend"], "baseline")
            self.assertEqual(result["llm_tokens"], 0)
            self.assertEqual(result["sim_backend"], "mock")
            budget = cfgmod.task_budget(cfg, task_type)
            self.assertLessEqual(result["sims_used"], budget,
                                 f"{task_type} exceeded budget")
            self.assertGreater(result["sims_used"], 0, f"{task_type} ran no sims")
            ok, issues = ev.check_answer_quality(task_type, result["answer"])
            self.assertTrue(ok, f"{task_type} quality issues: {issues}")
            kinds = [t["kind"] for t in result["trace"]]
            self.assertIn("hypothesis", kinds)
            self.assertIn("experiment", kinds)
            self.assertIn("answer", kinds)

    def test_deterministic_same_seed_same_answer(self):
        cfg = cfgmod.load_config("config.yaml")
        task = make_task("fault_diagnosis")
        r1 = run_baseline(task, cfg)
        r2 = run_baseline(task, cfg)
        self.assertEqual(r1["answer"], r2["answer"])
        self.assertEqual(r1["trace"], r2["trace"])

    def test_fault_diagnosis_picks_worst_sinr_cell(self):
        result = run_baseline(make_task("fault_diagnosis"))
        # cell_A: worst SINR (-2.5) and RSRP -109.5 < -105 -> propagation.
        self.assertEqual(result["answer"]["faulty_cell"], "cell_A")
        self.assertEqual(result["answer"]["root_cause"], "propagation")
        self.assertIn("sim 2", result["answer"]["evidence"])

    def test_energy_saves_without_breaking_service(self):
        result = run_baseline(make_task("energy"))
        self.assertGreater(result["answer"]["energy_saved_pct"], 0)
        self.assertIn("cell_C", str(result["answer"]["config"]))
        # Coverage cost of the saving stays inside the guardrail.
        self.assertGreaterEqual(
            result["answer"]["kpis"]["coverage_pct"],
            BASELINE_NET["coverage_pct"] - 3.0)

    def test_radio_config_meets_conditions(self):
        task = make_task("radio_config",
                         constraints={"min_rsrp_dbm": -100, "min_sinr_db": 0})
        result = run_baseline(task)
        self.assertTrue(result["answer"]["meets_conditions"])
        ok, issues = ev.check_answer_quality(
            "radio_config", result["answer"], result["answer"]["kpis"])
        self.assertTrue(ok, issues)

    def test_outage_losses_are_measured_not_guessed(self):
        task = make_task("outage_impact")
        task["scenario"]["outage_cell"] = "cell_B"
        result = run_baseline(task)
        self.assertEqual(result["answer"]["affected_cells"], ["cell_B"])
        self.assertGreater(result["answer"]["coverage_loss_pct"], 0)
        self.assertGreater(result["answer"]["throughput_loss_pct"], 0)

    def test_site_placement_site_is_gap_midpoint(self):
        result = run_baseline(make_task("site_placement"))
        sites = result["answer"]["sites"]
        self.assertEqual(len(sites), 1)
        a = mock_cell_xy("cell_A", CELLS)
        c = mock_cell_xy("cell_C", CELLS)
        self.assertAlmostEqual(sites[0]["lat"], (a[0] + c[0]) / 2)
        self.assertAlmostEqual(sites[0]["lon"], (a[1] + c[1]) / 2)


class TestBaselineBudgets(unittest.TestCase):
    def _cfg_with_budget(self, task_type, budget):
        cfg = copy.deepcopy(cfgmod.load_config("config.yaml"))
        cfg["agent"]["max_simulations"] = budget
        cfg["tasks"] = {task_type: {"max_simulations": budget}}
        return cfg

    def test_budget_one_still_answers(self):
        cfg = self._cfg_with_budget("fault_diagnosis", 1)
        result = run_baseline(make_task("fault_diagnosis"), cfg)
        self.assertEqual(result["sims_used"], 1)
        ok, _ = ev.check_answer_quality("fault_diagnosis", result["answer"])
        self.assertTrue(ok)

    def test_budget_zero_answers_inspection_only(self):
        cfg = self._cfg_with_budget("fault_diagnosis", 0)
        result = run_baseline(make_task("fault_diagnosis"), cfg)
        self.assertEqual(result["sims_used"], 0)
        self.assertIn("inspection-only",
                      result["answer"]["evidence"])
        ok, _ = ev.check_answer_quality("fault_diagnosis", result["answer"])
        self.assertTrue(ok)

    def test_unknown_task_type_rejected(self):
        with self.assertRaises(ValueError):
            run_baseline(make_task("not_a_task"))


class TestQualityCheck(unittest.TestCase):
    def test_tampered_answers_fail(self):
        ok, issues = ev.check_answer_quality(
            "energy", {"config": {}, "energy_saved_pct": 50.0, "kpis": {}})
        self.assertFalse(ok)
        self.assertTrue(issues)
        ok, _ = ev.check_answer_quality(
            "radio_config",
            {"config": {}, "meets_conditions": True, "kpis": {}})
        self.assertFalse(ok)  # claims met but reports no KPIs
        ok, _ = ev.check_answer_quality(
            "fault_diagnosis",
            {"faulty_cell": "cell_A", "root_cause": "aliens", "evidence": "x"})
        self.assertFalse(ok)

    def test_bounding_polygon_is_closed_geojson(self):
        poly = bounding_polygon([(40.0, -3.7), (40.01, -3.69)])
        self.assertEqual(poly["type"], "Polygon")
        ring = poly["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])  # closed ring
        self.assertEqual(len(ring), 5)


if __name__ == "__main__":
    unittest.main()
