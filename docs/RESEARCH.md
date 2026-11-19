# AI Agents for RAN Challenge — RESEARCH

**Competition:** AI Agents for RAN Challenge (Zindi, ITU + Huawei, GSMA Open Telco AI)
**Slug:** `ai-agents-for-ran-challenge` · **Zindi page:** https://zindi.africa/competitions/ai-agents-for-ran-challenge
**Account:** coral-fox-12 (existing — NO second account) · **Status: ✅ JOINED 23:25 +07 19/11/2026**
**Verified live via Zindi API:** `is_participant = True`, `participations_count = 193` (we are #193).
**Repo:** https://github.com/coral-fox-12/ran-agent-giulia (scaffold, this research's companion)
**Sources:** Zindi API dump `ran-competition-dump.json` (fetched 19/11, 82 KB, rules updated 2026-11-10),
ITU AI for Good article, GSMA press release 10/11/2026, competehub.dev summary, OpenGiuliaSLS repo + arXiv papers.
Anything marked **UNVERIFIED** below is not on the Zindi page and must be confirmed from the 27/11 data drop
or the 18/11 webinar recording (no recording/slides found in public search as of 19/11).

## 1. Timeline (all dates verified from the Zindi API dump)

| Milestone | UTC | +07 (Vietnam) |
|---|---|---|
| Announced (GSMA, Doha) | 2026-11-10 | 10/11 |
| Intro webinar (GSMA/ITU/IEEE) | 2026-11-18 | 18/11 (already held; no public recording found) |
| **Challenge starts / data drops** | **2026-11-27 12:00Z** | **27/11 19:00 +07** |
| Submissions close | 2027-02-05 21:30Z | 06/02 04:30 +07 |
| Challenge ends | 2027-02-05 22:00Z | 06/02 05:00 +07 |
| Private leaderboard reveal | 2027-02-06 22:00Z | 07/02 05:00 +07 |
| Leaderboard sealing | 2027-02-26 22:00Z | 27/02 05:00 +07 |
| MWC Barcelona 2027 (travel grant) | Mar 2027 | — |

`entries_close_at` is `null` in the API — entries stay open until the challenge ends.
No team members may be added in the final 5 days.

## 2. Prizes — €30,000 total (€20,000 cash + up to €10,500 travel)

| Place | Cash | MWC Barcelona travel grant |
|---|---|---|
| 1st | €10,000 | up to €3,500 |
| 2nd | €5,000 | up to €3,500 |
| 3rd | €2,500 | up to €3,500 |
| 4th | €1,500 | — |
| 5th | €1,000 | — |

Plus 5,000 Zindi points shared across participants. Payment by bank transfer (PayPal only if ≤ $100);
international transfer fees are deducted unless the prize is under $500 (then Zindi covers them).
Winners must show proof of ID, proof of residence and a bank letter confirming banking details.
**Russia payment exclusion:** Zindi cannot currently pay winners located in Russia (Russia-Ukraine conflict).
**Vietnam is NOT excluded** — rules say "Open to all"; the only payment exclusion named is Russia.
Prizes are paid after code review and leaderboard sealing. Top-3 winners must assign worldwide
copyright in the winning solution code to Zindi.

## 3. What the challenge is

Build an AI agent that solves radio-network engineering tasks inside **Giulia**, an interactive
system-level network simulator (open source, Universitat Politècnica de València). The agent receives
a structured scenario + engineering objective, uses **dedicated tools** to inspect the network and
run simulations, and submits a **structured answer**. A change to one site/cell affects coverage,
interference, user association, throughput and energy elsewhere — so the agent must form hypotheses,
choose useful experiments, and weigh network-wide effects. Each task limits the number of simulations,
so experiment choice is part of the score.

Judging criteria (per GSMA/ITU press releases — **not** stated on the Zindi page itself):
**accuracy, efficiency, reasoning capability, security.** Treat as press-reported, not rules-verified.

### Task types (6, verified from Description page)

| # | Task type | Likely answer form (inferred — see §5) |
|---|---|---|
| 1 | Fault diagnosis / troubleshooting | Analytical: identify the faulty element + root cause (text / multi-column) |
| 2 | Outage impact analysis | Analytical: quantify impact of an outage (numbers + text) |
| 3 | Coverage | Analytical and/or config: coverage KPIs, possibly a coverage polygon (geo IoU metric) |
| 4 | Radio configuration optimisation | Config: a configuration meeting specific performance conditions |
| 5 | Network site placement | Config/geometric: where to place site(s) — polygon IoU metric suggests geometry answers |
| 6 | Energy management | Config: settings meeting energy + performance trade-offs |

Some tasks need an analytical answer; others need a configuration that meets specific performance
conditions. Tasks are "structured radio network tasks describing the scenario, engineering objective,
permitted changes, constraints and required answer format" (Data Description page, verbatim).
**The actual task files, tool API and answer schema are NOT public yet — they arrive with the 27/11 data drop.**

## 4. Rules summary (verified against the API dump)

- **Open to all.** Solo OK; teams up to 4. No second accounts; no code/info sharing across accounts
  outside a team (DQ). Team submission budget = challenge max minus members' prior submissions.
- **Open-source languages and tools only.** Pretrained models OK if openly available to everyone.
  **No AutoML.** No paid services / free trials needing a credit card.
- **Base LM is FIXED: Qwen3.6-35B-A3B** (see §6). All participants must use it as the agent's base model.
- **Submission limits: 10/day, 300 total.** A submission that fails processing does NOT count and gets no score.
- **Pick 2:** before the end you choose 2 submissions to be judged on the private leaderboard;
  if you don't choose, your 2 best public-leaderboard submissions are used. Best private score of the 2 is final.
- **Public/private split — ⚠️ CONTRADICTION IN THE RULES:** the short Rules summary says public ≈ 30% /
  private ≈ 70%; the Full Challenge Rules say public ≈ 20% / private ≈ 80%. Either way the private
  board is the large majority and the final ranking. Flagged; assume 20/80 (full rules) for planning.
- **Tiebreak:** earlier submission wins on identical scores.
- **Data licence:** CC-BY SA 4.0. Only the challenge datasets may be used.
- **Code review (top 10):** at close you get an email requesting your code; **48 hours** to submit it.
  Code must reproduce your score (else rank adjusted to the reproduced score); code that doesn't run
  = dropped from top 10. Always set the seed. No custom packages in a submission notebook.
  Zindi may also request code from anyone at any time during the challenge, with a **24-hour** deadline.
- **Penalties:** 1st offence = no prizes 6 months + 2,000 points removed; 2nd offence = account banned.
- **Payment after code review + sealing.**

## 5. Scoring / evaluation — what is known and what is NOT

**Known (from API dump):**
- `error_metric: multi` with three metrics: **`word_error_rate`**, **`multi_col_acc`**, **`iou_polygon_geo`**.
  Reading: answers are structured/multi-column (multi_col_acc = accuracy across answer columns),
  some answers are free text (word_error_rate), and some are polygons/geometry (IoU over polygons —
  almost certainly site-placement / coverage-area answers, likely GeoJSON/WKT).
- Public leaderboard ranks by accuracy score while the challenge is open; private board is final.
- The Evaluation page on Zindi says only: **"The challenge has three stages."** — no further text.

**UNVERIFIED / unknown (must come from the 27/11 drop or webinar):**
- What the "three stages" are (no public source explains them as of 19/11).
- The exact submission format (file type, columns, answer schema, polygon encoding).
  Inferred most likely: a CSV with one row per task + structured answer columns (mirrors the
  `multi_col_acc` metric and standard Zindi practice) — but this is an inference, NOT a fact.
- Whether the agent runs live against a hosted task environment (with a tools API) during scoring,
  or whether we submit static answers produced offline by our agent. The Description ("use dedicated
  tools to inspect and simulate") suggests a tools API exists; its spec is not public yet.
- Whether the organisers provide an inference endpoint for Qwen3.6-35B-A3B, or participants self-host.
- Per-task simulation budgets (each task "limits the number of simulations" — numbers unknown).
- How "efficiency" is scored (tokens? simulations used? wall time? — press mentions efficiency as a
  judging criterion, but no formula is public).

## 6. Base LM — Qwen3.6-35B-A3B (verified from Hugging Face)

- **HF repo:** `Qwen/Qwen3.6-35B-A3B` (open weights, Apache-2.0). MoE: **35B total / 3B active**,
  256 experts, 8 active per token, 40 layers, hidden 2048, vocab 248,320.
- **Context:** 262,144 tokens native, extensible to 1,010,000. Multimodal (vision encoder).
- **Variants:** `Qwen/Qwen3.6-35B-A3B-FP8` (FP8, ~35 GB, "nearly identical" performance per model card);
  community GGUF quants (e.g. FastFlowLM `Qwen3.6-35B-A3B-gguf`, Q4_K_M ≈ 21 GB + mmproj).
- **How to run it FREE ($0) — realistic options:**
  | Route | Fits? | Notes |
  |---|---|---|
  | Kaggle GPU T4×2 (32 GB VRAM, ~30 h/week, refreshes Sat 07:00 +07) | **GGUF Q4_K_M (~21 GB) via llama.cpp — YES**; FP8 35 GB via vLLM — NO (weights alone exceed VRAM) | Our primary route. llama.cpp with partial GPU offload + CPU MoE offload; expect ~10–45 tok/s. vLLM/SGLang need the full model in VRAM. |
  | Colab free T4 16 GB | GGUF Q4_K_M only with heavy CPU offload; slow | Backup only. |
  | Local VM (this machine: no GPU, ~1 GB RAM free) | NO | Cannot run a 35B model here, even quantised. Harness dev uses a mock/small proxy LM. |
  | OpenRouter `qwen/qwen3.6-35b-a3b` | **NO — paid** ($0.10/1M in, $0.90/1M out; no `:free` variant) | Would violate the $0 rule AND the "no paid services" rule. Do NOT use. |
  | HF Inference / other hosted free tiers | UNVERIFIED whether any free tier serves this exact model | Check at build time; self-hosting is the compliant default. |
- **Important:** the rules require the *base model* to be Qwen3.6-35B-A3B. Using a smaller/cheaper
  model for harness development is fine, but anything submitted/scored must be produced by the agent
  running on Qwen3.6-35B-A3B. Keep the model swappable in config (`llm.model`) so dev can use a
  proxy and runs can use the real model — but never submit proxy-model outputs.
- **Quantisation note:** if the organisers require exact weights, GGUF Q4_K_M is a quantised
  approximation of the same base model. FP8 (official Qwen release) is the closest to full precision
  that fits anywhere free — it does NOT fit Kaggle T4×2. If a full-precision run is ever required,
  the only free route is CPU-offloaded llama.cpp (very slow) — flag as a risk (§9).

## 7. Giulia simulator (verified from the repo + local smoke test)

- **What:** data-driven system-level simulator (Python, event-driven) for heterogeneous cellular
  (4G/5G/6G) + Wi-Fi networks; 3GPP-based models, per-cell radio customisation, deployment-grade
  detail (BS/UE, propagation, mMIMO, scheduling, beamforming, power). Built at UPV; used in
  Huawei/UPV research (e.g. arXiv 2601.13993, FR3 6G capacity/energy trade-offs).
- **Repo:** https://github.com/giulia-open-lab/OpenGiuliaSLS.git (cloned 19/11, 30 MB, `giulia/` in workdir).
- **Stack:** Python 3.11+, **Sionna 2.0.1 (NVIDIA, PyTorch-based)**, PyTorch 2.9+ (installer pulls
  PyTorch 2.13 + CUDA 13.0 runtime automatically), NumPy, Pandas, SciPy, Shapely, GeoPandas, PyProj,
  Trimesh, Mitsuba, Astropy, itur, scikit-learn. Docker image available (`iteamupv/giulia`).
- **Entry:** `python main.py [config.yml]`; config-driven (YAML). Example: `config.example.yml`
  (ITU-R M.2135 UMa, preset `GiuliaStd`). Programmatic use: `InputConfig.load(...)` → `config.run()`
  → call the entry point on the main thread. Outputs: Parquet datasets per label (+ `.schema.md`),
  legacy NPZ, optional GOF (zipped Parquet). Load with `pyarrow` / `giulia.outputs.utils.load_gof`.
- **Smoke test performed 19/11 (this VM, documented):**
  1. `git clone --depth 1` OK (30 MB).
  2. `InputConfig.load('config.example.yml')` → **OK** (config schema parses).
  3. Entry-point resolution fails on missing `pyarrow` → installed pyarrow + numpy/pandas/scipy
     into an isolated venv (`venv/`, numpy 2.5.5 / pandas 3.1.1 / pyarrow 26.0.1) → OK.
  4. Next failure: **`ModuleNotFoundError: No module named 'torch'`** from
     `giulia/presets/g_standard_preset.py` — the documented boundary. Installing torch+Sionna
     (multi-GB, CUDA runtime) was NOT attempted: this VM has no GPU and ~1 GB free RAM, and the
     run would still stop at the shadowing maps (next bullet).
  5. **Shadowing maps blocker (verified):** all three presets call `validate_shadowing_files()`;
     the 14 `*.mat` files (2.7 GB) are NOT in the repo — the clone contains 134-byte Git LFS
     pointer files only (`oid sha256:… size 155381110`). They load via `scipy.io.loadmat`, so
     pointers would fail at load time. Download script `scripts/download_shadowing_files.py`
     reaches a server **only from the UPV network/VPN**. There is no public mirror found.
     → A full Giulia run is impossible until real `.mat` files are obtained. Most likely source:
     the 27/11 challenge data drop (organisers must supply them, or the task scenarios don't need
     shadowing). **This is the #1 technical risk — see §9.**
  6. `config.yml` (repo default) runs a heavy 4G/5G multilayer scenario needing a large-memory GPU;
     `config.example.yml` is the light first run. GPU is effectively required for real runs
     (`enable_GPU: true` in the example).
- **Where to run it for real:** Kaggle GPU notebook (T4×2) with the installer pins, or a Docker
  run on any GPU host. The scaffold's `giulia_client.py` wraps Giulia as a subprocess + Parquet
  reader so the agent never needs to import torch directly.

## 8. Code-review readiness (top 10 — plan from day one)

- Repo must be public, MIT-licensed, with a README that reproduces the result end-to-end.
- **Seed everything** (model sampling seed, sim seed, agent RNG); reruns must reproduce the score.
- No custom packages in any submission notebook; only publicly available open-source packages.
- Keep a `REPRODUCE.md` in the repo: exact commands, environment pins (Giulia commit, model
  revision, llama.cpp/vLLM version), and the 2 selected submission IDs.
- Never submit proxy-model outputs; keep the model name + revision in every run log.
- The 48-hour code-review clock starts at the email — keep the repo clean and pushable at all times.

## 9. Top risks / unknowns

1. **Shadowing maps (2.7 GB, UPV-only).** Without them Giulia cannot run any preset. If the 27/11
   drop doesn't include them (or an equivalent), we cannot run the official simulator at all and
   must ask on the Zindi discussion board / webinar channel. Mitigation: build the harness against
   a mock simulator now; swap in real Giulia the day the maps land.
2. **Submission format + "three stages" + tools API all unpublished.** We cannot verify the answer
   schema, the scoring stages, or how the agent's tools work until 27/11. Mitigation: scaffold is
   format-agnostic (answers as typed dicts; `submit.py` is a clearly-marked placeholder to be
   rewritten from the real spec on 27/11).
3. **Running a 35B MoE free.** FP8 doesn't fit Kaggle T4×2; GGUF Q4_K_M via llama.cpp is the only
   free route and will be slow (long-context agentic runs = many tokens). Token/time budget per task
   must be designed around this. If the organisers provide a hosted endpoint, this risk disappears —
   check the 27/11 drop first.
4. **Public/private split contradiction** (30/70 vs 20/80) — minor; assume the stricter 20/80.
5. **Simulation budget per task unknown** — agent must be budget-aware by design (hard cap on sims,
   cheapest informative experiment first). The scaffold enforces `max_simulations` per task.
6. **GDC travel grant needs a US visa** (for top 3) — cash is unaffected if the trip is forfeited;
   not a build blocker, note for the parent.

## 10. Pre-27/11 plan — what can be built now vs what must wait

### CAN build/test BEFORE 27/11 (this scaffold)
- [x] Giulia cloned; config parsing + entry-point resolution smoke-tested; failure boundary documented.
- [x] Agent harness skeleton (config, LLM client, simulator client with mock backend, tool schemas,
      per-task runners, ReAct loop, local eval harness, submission placeholder).
- [x] Prompt templates per task type (6 files in `prompts/`).
- [x] Mock end-to-end run: synthetic network + mock simulator + mock LLM → typed answers + local scores.
- [x] Baseline agent logic on the mock backend (hypothesis → experiment → answer loop, budget-capped). — DONE 20/11 (ran_agent/baseline.py + tests/test_baseline.py, 30/30 tests green, examples/baseline_run.py all 6 types quality OK).
- [ ] Download Qwen3.6-35B-A3B GGUF Q4_K_M (~21 GB) to a persistent cache **only if a free host with
      disk + bandwidth is available** — NOT on this VM (quota). Kaggle dataset / Colab Drive are the
      candidates; decide with parent (download is free, just heavy).
- [ ] Verify llama.cpp serves the GGUF on Kaggle T4 (needs a GPU session; queue for the 21/11 GPU window
      if a slot is free — NTL v7 / Zindi v20 / Squares GA already compete for it; parent decides order).
- [x] RAN domain primer for the agent: 3GPP concepts the tasks assume (RSRP/RSRQ/SINR, handover,
      PCI confusion, antenna tilt/azimuth, power, load balancing, energy-saving carrier shutdown).
      Draft from public sources; verify against the 27/11 task docs. — DONE 20/11 (docs/ran-primer.md, marked DRAFT, with a 27/11 verification checklist).

### MUST wait for 27/11
- Real task files, answer schema, submission format, tools API spec, per-task simulation budgets.
- The "three stages" of evaluation.
- Shadowing maps (unless obtained earlier via UPV contact — do NOT cold-email UPV asking for them
  without parent approval; the discussion board is the right channel after 27/11).
- Whether the organisers host Qwen3.6-35B-A3B (if yes, the whole self-hosting plan simplifies).
- First scored submission (nothing submittable before 27/11; limits 10/day, 300 total — spend them
  on real tasks only).

### Next steps (owners)
1. **Agent (this scaffold):** finish mock-backend baseline + unit tests; keep repo green. (Done in this run.)
2. **Parent:** confirm the 27/11 data-drop watch (check Zindi discussion board + competition page on
   27/11 19:00 +07); decide the Qwen GGUF download host; decide GPU-window priority for the llama.cpp
   T4 test on 21/11.
3. **On 27/11 (agent):** fetch task data + spec, rewrite `submit.py` to the real schema, wire the real
   Giulia client (if maps available), run the first real task end-to-end, report.

## Sources
- Zindi API: `GET https://api.zindi.world/v1/competitions/ai-agents-for-ran-challenge`
  (dump saved as `ran-competition-dump.json`; rules `updated_at` 2026-11-10).
- https://aiforgood.itu.int/advancing-ai-for-telecommunications-two-global-challenges-to-make-standards-more-accessible/
- https://www.gsma.com/newsroom/press-release/new-ai-challenges-launch-to-advance-network-automation-and-standards-knowledge/
- https://competehub.dev/en/competitions/zindiai-agents-for-ran-challenge
- https://github.com/giulia-open-lab/OpenGiuliaSLS.git (cloned 2026-11-19, `giulia/`)
- arXiv 2601.13993 (FR3 6G, Giulia description) · arXiv 2607.06072v2 (HAPS, Giulia repo link)
- https://huggingface.co/Qwen/Qwen3.6-35B-A3B · https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8
- https://open-ran.org/blog/github-for-ran-intelligence-inside-gsmas-ai-agents-for-ran-challenge-and-the-push-toward-verifiable-autonomous-networks/
