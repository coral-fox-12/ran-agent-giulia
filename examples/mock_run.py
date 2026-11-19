"""Mock end-to-end run: one fault-diagnosis task through the agent loop
with the mock LLM + mock simulator. No GPU, no model, no Giulia needed.

Usage: ./venv/bin/python examples/mock_run.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ran_agent import config as cfgmod
from ran_agent.agent import Agent
from ran_agent.llm import MockLLM
from ran_agent.giulia_client import MockGiuliaClient

TASK = {
    "id": "mock-fault-001",
    "type": "fault_diagnosis",
    "scenario": {"cells": ["cell_A", "cell_B", "cell_C"],
                 "symptom": "cell_B SINR collapsed at 14:00, neighbours normal"},
    "objective": "Identify the faulty cell and root cause.",
    "constraints": {"max_simulations": 8},
}

if __name__ == "__main__":
    cfg = cfgmod.load_config("config.yaml")
    agent = Agent(MockLLM(), MockGiuliaClient(seed=42), cfg, TASK)
    result = agent.run()
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, indent=2))
    print(f"\nTRACE steps: {len(result['trace'])} | sims used: {result['sims_used']} "
          f"| llm backend: {result['llm_backend']} | sim backend: {result['sim_backend']}")
    print("OK — mock run complete. Real model + real Giulia swap in via config.yaml.")
