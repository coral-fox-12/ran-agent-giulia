# Reproduce a run (code-review checklist)

Fill this in for every scored run. The top-10 code review (48 h) requires the
submitted code to reproduce the leaderboard score.

## Environment pins
- Repo commit: _(fill in `git rev-parse HEAD`)_
- Giulia commit: _(fill in `git -C giulia rev-parse HEAD`)_
- Model: `Qwen/Qwen3.6-35B-A3B` revision _(fill in HF revision hash)_
- Inference server: _(llama.cpp / vLLM / SGLang + version)_
- Python env: `requirements.txt` + `venv` (this repo)

## Commands
```bash
bash setup_giulia.sh
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
# start the model server serving Qwen3.6-35B-A3B, then:
cp config.yaml config.local.yaml   # set llm.base_url + simulator.backend
./venv/bin/python examples/mock_run.py   # sanity check (mock backends)
# real run: <fill in the exact run command + task file>
```

## Seeds
- `llm.seed: 42`, `eval.seed: 42` (config.yaml). All RNG seeded; reruns must
  reproduce the score.

## Selected submissions (pick 2 before the deadline)
- Submission 1: _(Zindi submission id)_
- Submission 2: _(Zindi submission id)_
