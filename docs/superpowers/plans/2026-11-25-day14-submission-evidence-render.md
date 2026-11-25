# Day 14 Submission Evidence and Render Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible local submission evidence, fill only evidence-backed answers and measurements, and provide an accurate Render deployment handoff.

**Architecture:** Run existing Part 7 experiment scripts and retain their original JSON/CSV outputs at the root submission paths. Summarize measured values in existing Markdown documents; keep cloud/account-dependent facts pending until the student deploys and confirms them.

**Tech Stack:** Python/FastAPI, Docker Compose, Locust, Redis, Markdown, Render Docker Web Service.

**Spec:** `docs/superpowers/specs/2026-11-25-day14-submission-evidence-render-design.md`

## Global Constraints

- Do not edit `06-lab-complete/check_production_ready.py` or `06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl`.
- Do not fabricate metrics, logs, screenshots, alert timings, public URL, or first-person student experience.
- Keep other Docker projects and existing uncommitted work intact; don't commit/push or connect to the student's cloud account.
- `SUBMISSION.md` requires root-level `reports/`, `benchmark-results/`, and `screenshots/` with real files, not empty placeholders.
- Preserve raw output even when load SLO fails (the script may exit 1 with a valid report).

## Review Focus

- Expired/unreachable Docker Hub image: label Part 6 and CP8 Docker verification blocked; never substitute a stale image. Task 3/4 verify.
- Randomized mock latency/errors: source each reported figure from its own matching JSON, not example output. Task 1/2 verify.
- Evaluation KB fix: preserve v2-before and v2-after reports, prohibit regression and check all golden IDs. Task 2 verify.
- Port collisions and pre-existing containers: use isolated processes/project name and clean up only what this run creates. Task 1/3 verify.
- Secret or personal data leakage in Render commands, logs, screenshots, and markdown: use env-variable prompts and redact. Task 4 verify.

---

### Task 1: Local load and tail-latency evidence

**Files:** Create: `reports/load_v2_c{1,10,50,100}.json`, `reports/load_v2_slow_{0,0.03,0.1}.json`; modify: `BENCHMARK_REPORT.md` section 2.

**Interfaces:** The existing `develop/load_test.py --url ... --requests 300 --concurrency N --out PATH` emits a JSON report. The existing `develop/app.py` runs v2 on `PORT=8002`; `MOCK_SLOW_RATE` configures tail simulation at process start.

- [ ] Check Python environment and run a disposable v2 process with `AGENT_VERSION=v2 PORT=8002`, verifying `GET /health` or `/metrics`; if port 8002 is busy, identify and avoid interfering with its owner.
- [ ] Run seven documented 300-request experiments: c=1,10,50,100 and slow rates 0,0.03,0.1 at concurrency=20; capture exit status and preserve reports even for SLO violations.
- [ ] Verify every JSON parses, has the matching request/concurrency settings, and summarize only matching recorded metrics in report tables 2.1/2.2; mark SLO based on measured thresholds and document run date/environment.
- [ ] Shut down only v2 processes started by this task.

### Task 2: Eval baseline and documented KB repair

**Files:** Create: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`; optionally modify: `06-lab-complete/benchmark-observability/develop/utils/mock_llm.py` KNOWLEDGE_BASE entries; modify `BENCHMARK_REPORT.md` section 3 and relevant `MISSION_ANSWERS.md` evaluation/quality-gate section.

**Interfaces:** Existing `develop/eval/run_eval.py --url URL --baseline PATH --min-accuracy 1.0 --out PATH` writes JSON; golden dataset remains untouched. If a KB fix is necessary, targeted missing keywords are taken from real `eval_v2.json` and the matching dataset row.

- [ ] Start isolated v1/v2 processes; run documented v1 baseline and v2 eval with `--baseline reports/eval_v1.json`, recording output and IDs of failed cases.
- [ ] If v2 has documented retrieval misses, first preserve failing report, then add only necessary KNOWLEDGE_BASE entries; restart v2 and rerun with `--baseline reports/eval_v2.json --min-accuracy 1.0 --out reports/eval_v2_fixed.json`.
- [ ] Verify final gate passes without regression and all three JSONs parse; if not, report exact failure instead of claiming 100%. Test the intentionally bad v1-vs-v2 gate and record exit code.
- [ ] Fill report section 3 and quality-gate explanation exclusively with run output; stop owned processes.

### Task 3: Local observability and scaling evidence

**Files:** Create when available: `benchmark-results/scale_{1,3}_stats.csv`, four real Part 7 screenshots under `screenshots/`; modify: `BENCHMARK_REPORT.md` sections 4/5 and supporting notes.

**Interfaces:** `06-lab-complete/benchmark-observability/production/docker-compose.yml` runs under `-p k5-day14-observability`; documented headless Locust `--csv /mnt/results/scale_1` and `scale_3` writes CSV to `production/benchmark-results/`.

- [ ] Inspect stack configuration and resource/port availability before launch; record any Docker Hub failure instead of changing required Dockerfiles or using stale images.
- [ ] If stack starts, run 100 users for 2m for one then three agents, copy original CSVs to root, and fill scaling report using CSV values.
- [ ] While stack is active, capture genuine Grafana, Jaeger slow/error trace, and simultaneous Prometheus alert evidence if obtainable; record real trace IDs and matching JSON logs; do not create fake screenshots.
- [ ] Shut down only owned stack with matching Compose project after evidence capture; document unverified experiments individually.

### Task 4: Final submission documents, Render guide, and audit

**Files:** Modify: `MISSION_ANSWERS.md`, `DEPLOYMENT.md`, `BENCHMARK_REPORT.md`; create/modify: Render guide in `DEPLOYMENT.md` and optionally `06-lab-complete/render.yaml` only if needed and validated.

**Interfaces:** `06-lab-complete/Dockerfile` runs `uvicorn app.main:app`; Render Web Service root directory `06-lab-complete`, Docker runtime, environment variables `AGENT_API_KEY`, `REDIS_URL`, optional rate/budget/output configuration; Redis must be reachable before `/ready` is 200.

- [ ] Fill objective exercises from repository code/observed output, leaving personal observations/claims marked for student confirmation; update AI log honestly.
- [ ] Write actionable Render dashboard steps: connect Public GitHub repo, Docker root directory, provision Redis, set secrets through Render dashboard, verify four CP6 status codes with an API key prompted locally; explicitly mention Render plan/pricing need confirmation and require real URL/screenshots.
- [ ] Run current Part 6 unittest suite and unmodified full grader; record output/status without treating a Docker skip or 429 as passing 12/12.
- [ ] Check all root artifact names, values against JSON/CSV, `git diff --check`, protected-file diff, tracked secrets, and unfinished placeholders; report exact remaining student actions and submission readiness.
