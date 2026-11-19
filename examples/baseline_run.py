"""Baseline agent on the mock backend: all 6 task types, no LLM, no GPU.

Runs the deterministic hypothesis -> experiment -> answer loop from
ran_agent/baseline.py against MockGiuliaClient and prints each typed
answer, simulations used vs budget, and the local quality check
(ran_agent.eval.check_answer_quality — schema + internal consistency,
no ground truth needed on the mock).

Usage: python3 examples/baseline_run.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ran_agent import config as cfgmod
from ran_agent import eval as ev
from ran_agent.baseline import BaselineAgent
from ran_agent.giulia_client import MockGiuliaClient

CELLS = ["cell_A", "cell_B", "cell_C"]

TASKS = [
    {"id": "mock-fault-001", "type": "fault_diagnosis",
     "scenario": {"cells": CELLS,
                  "symptom": "cell_B SINR collapsed at 14:00, neighbours normal"},
     "objective": "Identify the faulty cell and root cause."},
    {"id": "mock-outage-001", "type": "outage_impact",
     "scenario": {"cells": CELLS, "outage_cell": "cell_B"},
     "objective": "Quantify the impact of cell_B going down."},
    {"id": "mock-coverage-001", "type": "coverage",
     "scenario": {"cells": CELLS},
     "objective": "Find and fix the coverage gap."},
    {"id": "mock-radio-001", "type": "radio_config",
     "scenario": {"cells": CELLS},
     "objective": "Find a config meeting RSRP >= -100 dBm and SINR >= 0 dB.",
     "constraints": {"min_rsrp_dbm": -100, "min_sinr_db": 0}},
    {"id": "mock-site-001", "type": "site_placement",
     "scenario": {"cells": CELLS},
     "objective": "Place one new site to close the coverage gap."},
    {"id": "mock-energy-001", "type": "energy",
     "scenario": {"cells": CELLS},
     "objective": "Save energy without breaking coverage or throughput."},
]


def main():
    cfg = cfgmod.load_config("config.yaml")
    all_ok = True
    for task in TASKS:
        agent = BaselineAgent(MockGiuliaClient(seed=42), cfg, task)
        result = agent.run()
        budget = cfgmod.task_budget(cfg, task["type"])
        ok, issues = ev.check_answer_quality(
            task["type"], result["answer"],
            result["answer"].get("kpis") if isinstance(
                result["answer"].get("kpis"), dict) and
            "cells" in result["answer"].get("kpis", {}) else None)
        all_ok = all_ok and ok
        print(f"\n== {task['id']} ({task['type']}) "
              f"sims {result['sims_used']}/{budget} "
              f"quality={'OK' if ok else 'FAIL: ' + '; '.join(issues)}")
        print(json.dumps(result["answer"], indent=2))
        hyps = [(h["id"], h["status"]) for h in agent.hypotheses]
        print(f"hypotheses: {hyps} | trace steps: {len(result['trace'])}")
    print(f"\n{'ALL OK' if all_ok else 'FAILURES PRESENT'} — baseline mock run complete.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
