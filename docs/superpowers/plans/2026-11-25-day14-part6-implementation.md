# Day 14 Part 6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete `06-lab-complete/` to satisfy the documented production-agent contract and prove results with the unmodified grader.

**Architecture:** Keep the current FastAPI module layout. Centralize environment configuration, use a lazy Redis client for shared rate/budget state, implement request authentication and checks as dependencies/helpers, and rely on Uvicorn/ASGI shutdown behavior. Complete the existing Docker and cloud deployment files without changing the grader.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Redis, Docker/Compose, pytest (focused tests if needed).

**Spec:** `docs/superpowers/specs/2026-11-25-day14-lab-completion-design.md`

## Global Constraints

- Work inside `06-lab-complete/`; do not move the Part 6 app elsewhere.
- `check_production_ready.py` and `benchmark-observability/develop/eval/golden_dataset.jsonl` are protected; do not modify them.
- `/health` returns 200 independent of Redis; `/ready` returns 200 only when Redis is reachable.
- `/ask` accepts JSON `{"question":"..."}` and requires `X-API-Key`; missing/incorrect key returns 401.
- Rate limit is Redis-backed and per API key; budget is Redis-backed and returns 402 when exceeded.
- App log lines are valid JSON; Docker uses a multi-stage slim image, non-root user, healthcheck, and honors `PORT`.
- Never add `.env`, real secrets, or fabricated evidence. Only full grader output `PASS 12/12` counts as complete.

## Review Focus

- Empty/missing Redis URL or unavailable Redis: process still starts, `/health` stays 200, `/ready` reports unavailable, protected operations fail safely.
- Missing and wrong API keys: both return 401 (not 422/403), with no key leaked in logs.
- Concurrent requests across workers: Redis operations must not exceed the per-minute limit or overspend budget due to non-atomic read/modify/write.
- Budget boundary and daily reset: reject once the configured budget is reached/exceeded and do not count a rejected request.
- SIGTERM during an active request: finish the request and exit cleanly within Docker's stop timeout.

---

### Task 1: Environment configuration and Redis lifecycle

**Files:**
- Modify: `06-lab-complete/app/config.py`
- Modify: `06-lab-complete/app/redis_client.py`
- Test: add focused tests under `06-lab-complete/tests/` if the grader does not cover the failure modes directly.

**Interfaces:**
- `settings` exposes `port`, `environment`, `agent_api_key`, `redis_url`, `rate_limit_per_minute`, and `daily_budget_usd`.
- `redis_client.r` is a lazily usable Redis client; `redis_healthy() -> bool` catches connectivity errors and returns false.

- [ ] **Step 1: Add tests** for env parsing/defaults and Redis unavailable/startup/health behavior.
- [ ] **Step 2: Run the focused tests** and confirm they fail against the starter implementation.
- [ ] **Step 3: Implement settings and lazy Redis client** with no network ping during import.
- [ ] **Step 4: Run focused tests** and `python check_production_ready.py --static-only` from `06-lab-complete/`.

### Task 2: Authentication, rate limit, and cost guard

**Files:**
- Modify: `06-lab-complete/app/auth.py`
- Modify: `06-lab-complete/app/rate_limiter.py`
- Modify: `06-lab-complete/app/cost_guard.py`
- Test: focused tests under `06-lab-complete/tests/`.

**Interfaces:**
- `verify_api_key() -> str` is a FastAPI dependency reading `X-API-Key` and returns the validated key or raises 401.
- `check_rate_limit(key: str) -> None` raises 429 with `Retry-After` when limited.
- `check_budget() -> None` raises 402 when the configured budget is exhausted.
- `record_cost(input_tokens: int, output_tokens: int) -> float` records daily cost and returns request cost.

- [ ] **Step 1: Add failing tests** for missing/wrong/correct keys, rate threshold/retry header, budget threshold, and cost recording/reset.
- [ ] **Step 2: Run the focused tests** and confirm failures.
- [ ] **Step 3: Implement Redis-backed checks**; use atomic Redis operations or a Lua script where required to keep limits correct across workers.
- [ ] **Step 4: Run focused tests** and the static grader.

### Task 3: FastAPI routes, logging, and shutdown behavior

**Files:**
- Modify: `06-lab-complete/app/main.py`
- Test: focused API tests under `06-lab-complete/tests/`.

**Interfaces:**
- `app` remains the FastAPI application imported as `app.main:app`.
- `GET /health`, `GET /ready`, and authenticated `POST /ask` follow the exact status contract.

- [ ] **Step 1: Add failing API tests** for liveness/readiness, authentication, successful ask, rate/budget responses, and JSON application log records.
- [ ] **Step 2: Run API tests** against the starter and confirm failure.
- [ ] **Step 3: Wire dependencies and checks into routes**, log app events as JSON objects, and avoid custom signal handlers that interfere with Uvicorn.
- [ ] **Step 4: Run focused API tests** and `python check_production_ready.py --skip-docker` from `06-lab-complete/`.

### Task 4: Production container and deployment configuration

**Files:**
- Modify: `06-lab-complete/Dockerfile`
- Modify: `06-lab-complete/docker-compose.yml`
- Create/update: `06-lab-complete/.dockerignore`
- Create/update: `06-lab-complete/.env.example`
- Modify as needed: `06-lab-complete/railway.toml`
- Modify as needed: `06-lab-complete/render.yaml`

- [ ] **Step 1: Validate the config contract**: all required env keys documented, `.dockerignore` excludes `.env`, caches, and virtualenvs, and at least one supported deployment config is complete.
- [ ] **Step 2: Implement multi-stage slim Docker build**, non-root runtime, `HEALTHCHECK`, PID-1 Uvicorn command honoring `PORT`, and Compose Redis wiring.
- [ ] **Step 3: Run Docker checks**: build image, inspect image size, start without Redis to verify process startup, start Compose with Redis, exercise health/readiness/API, and verify `docker stop` exits within 10 seconds.

### Task 5: Full grading and change audit

**Files:**
- No intended source changes unless verification exposes a defect.

- [ ] **Step 1: Run the unmodified full grader** from `06-lab-complete/` with Docker available: `python check_production_ready.py`.
- [ ] **Step 2: Record exact output and status**; report `PASS 12/12` only if all 12 checks pass with no warnings.
- [ ] **Step 3: Audit protected files and secrets** using git diff/status and secret-pattern checks; confirm grader and golden dataset are unchanged.
- [ ] **Step 4: Report any unavailable checks** with the exact reason and student-run command needed to complete them.
