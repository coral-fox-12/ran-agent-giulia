"""Configuration loading. `config.yaml` + optional `config.local.yaml` override.

The base model name is pinned by the challenge rules and is validated on load:
anything other than Qwen3.6-35B-A3B (or its official FP8 release) is refused,
so a dev proxy can never leak into a scored run by accident.
"""
import copy
import os

import yaml

DEFAULTS = {
    "llm": {
        "model": "Qwen/Qwen3.6-35B-A3B",
        "base_url": "",
        "api_key": "",
        "temperature": 0.2,
        "max_tokens": 4096,
        "seed": 42,
        "timeout_s": 300,
    },
    "simulator": {
        "backend": "mock",
        "giulia_dir": "./giulia",
        "python": "./venv/bin/python",
        "timeout_s": 1800,
    },
    "agent": {"max_steps": 24, "max_simulations": 10, "max_tokens_per_task": 60000},
    "tasks": {},
    "eval": {"seed": 42, "out_dir": "runs/"},
    "submit": {"format": "TBD-2026-11-27", "out_file": "runs/submission.csv"},
}

# Exact model IDs allowed by the challenge (base model fixed in the rules).
ALLOWED_MODELS = {
    "Qwen/Qwen3.6-35B-A3B",
    "Qwen/Qwen3.6-35B-A3B-FP8",
}


def _deep_merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path="config.yaml"):
    cfg = copy.deepcopy(DEFAULTS)
    if os.path.exists(path):
        with open(path) as f:
            cfg = _deep_merge(cfg, yaml.safe_load(f) or {})
    local = "config.local.yaml"
    if os.path.exists(local):
        with open(local) as f:
            cfg = _deep_merge(cfg, yaml.safe_load(f) or {})
    model = cfg["llm"]["model"]
    if model not in ALLOWED_MODELS:
        raise ValueError(
            f"Refusing model {model!r}: the challenge fixes the base model to "
            f"Qwen3.6-35B-A3B. Allowed: {sorted(ALLOWED_MODELS)}"
        )
    return cfg


def task_budget(cfg, task_type):
    """Per-task simulation budget: task override > agent default."""
    per_task = (cfg.get("tasks") or {}).get(task_type) or {}
    return int(per_task.get("max_simulations", cfg["agent"]["max_simulations"]))
