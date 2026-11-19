# ran-agent-giulia

AI agent for the **AI Agents for RAN Challenge** (Zindi, ITU + Huawei, €30,000) —
solves radio-network engineering tasks inside the open-source **Giulia** simulator
with **Qwen3.6-35B-A3B** as the fixed base model.

**Status: scaffold — pre-27/11.** The challenge starts 27/11 19:00 +07; task data,
answer schema, tools API and the "three stages" of evaluation are not public yet.
Everything here runs against a deterministic **mock simulator + mock LLM** until the
real data drops. See [`docs/RESEARCH.md`](docs/RESEARCH.md) for the full verified
research (rules, timeline, model, simulator smoke-test boundary, risks).

## Concept

A budget-aware ReAct agent:

1. Read the structured task (scenario, objective, permitted changes, constraints).
2. Form a hypothesis, then pick the cheapest informative experiment.
3. Call Giulia tools (`inspect_network`, `run_simulation`, `get_kpis`) — each
   simulation counts against the task's simulation budget.
4. Propose a configuration or an analytical answer in the required typed schema.
5. Validate locally (metrics: word error rate / multi-column accuracy / polygon IoU),
   then write the submission file.

Per-task runners live in `ran_agent/tasks.py`; prompt templates in `prompts/`;
the simulator is wrapped in `ran_agent/giulia_client.py` (real subprocess backend
+ mock backend for offline development).

## Quickstart

```bash
# 1. Clone Giulia (the simulator — upstream repo, not vendored here)
bash setup_giulia.sh          # clones OpenGiuliaSLS into ./giulia (needs ~30 MB)

# 2. Python env (3.11+)
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

# 3. Mock end-to-end run (no GPU, no model, no shadowing maps needed)
./venv/bin/python examples/mock_run.py

# 4. Unit tests
./venv/bin/python -m unittest discover -s tests -v
```

## Real runs (after 27/11)

- **Model:** `Qwen/Qwen3.6-35B-A3B` (or the FP8 release). Free route: GGUF Q4_K_M
  via llama.cpp on Kaggle T4×2 — see `docs/RESEARCH.md` §6. Set `llm.base_url` in
  `config.yaml` to your OpenAI-compatible server (llama.cpp / vLLM / SGLang).
  Never submit outputs produced by a proxy model.
- **Simulator:** real Giulia needs PyTorch 2.9+ / Sionna 2.0.1, a GPU, and the
  2.7 GB shadowing `.mat` files (UPV-only download — see `docs/RESEARCH.md` §7).
  Set `simulator.backend: giulia` and `simulator.giulia_dir` in `config.yaml`.
- **Submission:** `ran_agent/submit.py` is a placeholder until the 27/11 spec lands.

## Layout

```
ran_agent/
  config.py        # config.yaml loading + defaults
  llm.py           # OpenAI-compatible client + MockLLM
  giulia_client.py # simulator wrapper (subprocess + mock backends)
  tools.py         # tool schemas the agent may call
  tasks.py         # per-task runners, answer schemas, budgets
  agent.py         # ReAct loop (hypothesis -> experiment -> answer)
  eval.py          # local scoring: WER / multi-col acc / polygon IoU
  submit.py        # submission builder (FORMAT TBD until 27/11)
prompts/           # one prompt template per task type
examples/mock_run.py
tests/test_smoke.py
docs/RESEARCH.md
```

## Rules compliance

- Base model fixed to Qwen3.6-35B-A3B; open-source tools only; no AutoML; no paid
  services. Seeds are set everywhere for reproducibility (code review: top 10, 48 h).
- Solo entry, account `coral-fox-12` on Zindi (joined 19/11/2026, participant #193).
- MIT licensed.
