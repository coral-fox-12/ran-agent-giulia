# Smoke test — what was verified on 2026-11-19 (VM, no GPU) and where it stops

Giulia checkout: `git clone --depth 1 https://github.com/giulia-open-lab/OpenGiuliaSLS.git`
(30 MB, commit at clone time — pin the exact commit in `REPRODUCE.md` before any scored run).

## Verified
1. `InputConfig.load('config.example.yml')` → OK (config schema parses).
2. Entry-point resolution → fails only on missing `pyarrow` → fixed by installing
   pyarrow + numpy/pandas/scipy into an isolated venv (numpy 2.5.5 / pandas 3.1.1 /
   pyarrow 26.0.1).
3. Next failure: `ModuleNotFoundError: No module named 'torch'` from
   `giulia/presets/g_standard_preset.py` — **this is the documented boundary**.

## NOT attempted (and why)
- Installing torch + Sionna 2.0.1 (multi-GB incl. CUDA 13 runtime): this VM has no
  GPU and ~1 GB free RAM; the run would then stop at the shadowing maps anyway.
- Real shadowing `.mat` files: the clone has 134-byte Git LFS pointers only;
  real files are 2.7 GB, downloadable only from the UPV network/VPN
  (`scripts/download_shadowing_files.py`). All three presets call
  `validate_shadowing_files()`, and `scipy.io.loadmat` on a pointer file fails.
  Even the lightest example (`config.example.yml`, ITU-R M.2135 UMa, preset
  `GiuliaStd`) needs them.

## Where a real run happens
Kaggle GPU notebook (T4×2) or any GPU host: install per `scripts/installer_dependencies.sh`
(Sionna 2.0.1 pins), obtain the `.mat` files (expected from the 27/11 challenge data
drop — otherwise ask on the Zindi discussion board), then `python main.py config.example.yml`.

## This repo's own tests (no GPU / model / maps needed)
```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m unittest discover -s tests -v
./venv/bin/python examples/mock_run.py
```
