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
    stand-in only."""

    backend = "mock"

    def __init__(self, seed=42):
        self.seed = seed
        self.simulations_run = 0

    def _kpis(self, config):
        rng = random.Random(f"{self.seed}:{json.dumps(config, sort_keys=True)}")
        cells = config.get("cells", ["cell_A", "cell_B", "cell_C"])
        return {
            "cells": {
                c: {
                    "rsrp_dbm": round(rng.uniform(-110, -70), 1),
                    "sinr_db": round(rng.uniform(-3, 25), 1),
                    "throughput_mbps": round(rng.uniform(5, 180), 1),
                    "load_pct": round(rng.uniform(5, 95), 1),
                    "energy_w": round(rng.uniform(40, 400), 1),
                }
                for c in cells
            },
            "network": {
                "coverage_pct": round(rng.uniform(82, 99.5), 1),
                "mean_throughput_mbps": round(rng.uniform(30, 120), 1),
                "total_energy_w": round(rng.uniform(300, 1500), 1),
            },
        }

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
