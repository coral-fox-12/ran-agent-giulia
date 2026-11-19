"""ran-agent-giulia: budget-aware ReAct agent for the AI Agents for RAN Challenge.

Base model is FIXED by the challenge rules: Qwen3.6-35B-A3B.
Simulator backends: "mock" (deterministic, offline dev) or "giulia" (real subprocess).
"""
from .baseline import BaselineAgent, run_baseline  # noqa: F401

__version__ = "0.2.0-baseline"
