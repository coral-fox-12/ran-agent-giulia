"""Smoke tests for the harness — stdlib + requirements only.
No GPU, no model, no Giulia, no network. Run: python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ran_agent import config as cfgmod
from ran_agent import eval as ev
from ran_agent import tasks
from ran_agent.agent import Agent
from ran_agent.llm import MockLLM
from ran_agent.giulia_client import MockGiuliaClient
from ran_agent.submit import build_submission, SubmissionNotReady
from ran_agent.tools import TOOLS, TOOL_NAMES


class TestConfig(unittest.TestCase):
    def test_defaults_load_and_pin_model(self):
        cfg = cfgmod.load_config("config.yaml")
        self.assertEqual(cfg["llm"]["model"], "Qwen/Qwen3.6-35B-A3B")

    def test_wrong_model_refused(self):
        import copy
        cfg = copy.deepcopy(cfgmod.DEFAULTS)
        cfg["llm"]["model"] = "Qwen/Qwen2.5-7B-Instruct"
        with open("/tmp/_badcfg.yaml", "w") as f:
            import yaml
            yaml.safe_dump(cfg, f)
        with self.assertRaises(ValueError):
            cfgmod.load_config("/tmp/_badcfg.yaml")

    def test_task_budget_override(self):
        cfg = cfgmod.load_config("config.yaml")
        self.assertEqual(cfgmod.task_budget(cfg, "fault_diagnosis"), 8)


class TestEval(unittest.TestCase):
    def test_wer_identical_is_zero(self):
        self.assertEqual(ev.word_error_rate("a b c", "a b c"), 0.0)

    def test_wer_one_substitution(self):
        self.assertAlmostEqual(ev.word_error_rate("a b c", "a x c"), 1 / 3)

    def test_multi_col_acc(self):
        acc, per = ev.multi_col_acc({"a": 1, "b": "x"}, {"a": 1, "b": "y"})
        self.assertEqual(acc, 0.5)
        self.assertEqual(per, {"a": 1.0, "b": 0.0})

    def test_polygon_iou_identical(self):
        sq = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.assertAlmostEqual(ev.polygon_iou(sq, sq), 1.0)

    def test_polygon_iou_half_overlap(self):
        a = [(0, 0), (2, 0), (2, 2), (0, 2)]
        b = [(1, 0), (3, 0), (3, 2), (1, 2)]
        self.assertAlmostEqual(ev.polygon_iou(a, b), 2 / 6, places=6)


class TestAgentMock(unittest.TestCase):
    def test_mock_end_to_end(self):
        cfg = cfgmod.load_config("config.yaml")
        task = {"id": "mock-001", "type": "fault_diagnosis",
                "scenario": {"cells": ["cell_A", "cell_B"]},
                "objective": "find the faulty cell"}
        agent = Agent(MockLLM(), MockGiuliaClient(seed=42), cfg, task)
        result = agent.run()
        self.assertEqual(result["task_id"], "mock-001")
        self.assertEqual(result["sim_backend"], "mock")
        self.assertEqual(result["llm_backend"], "mock")
        self.assertLessEqual(result["sims_used"], 8)
        self.assertTrue(len(result["trace"]) >= 2)

    def test_answer_validation(self):
        with self.assertRaises(ValueError):
            tasks.validate_answer("fault_diagnosis", {"faulty_cell": "cell_A"})
        self.assertTrue(tasks.validate_answer(
            "fault_diagnosis",
            {"faulty_cell": "cell_A", "root_cause": "interference",
             "evidence": "sim 1 shows SINR collapse on cell_A"}))


class TestSubmit(unittest.TestCase):
    def test_blocked_until_schema(self):
        with self.assertRaises(SubmissionNotReady):
            build_submission([], "runs/submission.csv")


class TestTools(unittest.TestCase):
    def test_schemas_wellformed(self):
        self.assertIn("run_simulation", TOOL_NAMES)
        self.assertIn("propose_answer", TOOL_NAMES)
        for t in TOOLS:
            self.assertEqual(t["type"], "function")
            self.assertIn("parameters", t["function"])


if __name__ == "__main__":
    unittest.main()
