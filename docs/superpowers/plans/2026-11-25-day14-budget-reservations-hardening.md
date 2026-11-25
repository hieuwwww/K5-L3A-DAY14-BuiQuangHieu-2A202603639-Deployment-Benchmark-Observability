# Day 14 Budget Reservations & Request Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent concurrent `/ask` requests from exceeding the configured daily budget and make Redis failures, rate-limit keys, and request logs deliberate and safe.

**Architecture:** Use atomic Redis Lua scripts to reserve a bounded per-request maximum before calling the model, then idempotently settle actual estimated cost or release on model failure. Catch Redis operation failures as HTTP 503, hash API keys before using them in Redis keys, and emit request log fields at the JSON object's top level.

**Tech Stack:** Existing Python/FastAPI, redis-py, Redis Lua, `unittest`, Docker.

**Spec:** `docs/superpowers/specs/2026-11-25-day14-lab-completion-design.md`, section “Review follow-up design — budget reservations and request hardening”.

## Global Constraints

- Do not modify `06-lab-complete/check_production_ready.py` or `06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl`.
- Preserve HTTP 401, 429, and 402 behavior; Redis unavailability returns HTTP 503; never fail open.
- Do not add dependencies or deploy resources.
- Bound each reservation by an explicit `MAX_OUTPUT_TOKENS` setting and enforce that ceiling at the model boundary.
- Continue using the existing per-token prices and UTC daily budget key.

## Review Focus

- Concurrent reservations near the budget limit must never permit combined reservations over budget; test simultaneous reserve attempts against real Redis (the preferred proof) and keep fake-Redis contract coverage for fast unit tests.
- Duplicate settlement/release attempts must not double-apply accounting; test idempotency by repeating the same reservation operation.
- Oversized model output and model exceptions must respect the configured cap and release held budget; cover both behaviors.
- Redis `get`/`eval`/Lua failures in rate limiting and budget reservation/settlement/release must yield HTTP 503, not 500 or fail-open; test each operation boundary, including release failure after a model error.
- API key bytes must not appear in Redis key names, and logs must parse as one JSON object with top-level request fields; assert the exact stored key and JSON fields.

---

### Task 1: Define the bounded request budget contract

**Files:**
- Modify: `06-lab-complete/app/config.py`
- Modify: `06-lab-complete/.env.example`
- Test: `06-lab-complete/tests/test_config_redis.py`

**Interfaces:**
- Produces `settings.max_output_tokens: int`, loaded from `MAX_OUTPUT_TOKENS`, default `1024`.

- [ ] **Step 1: Write the failing settings test** asserting `MAX_OUTPUT_TOKENS=64` loads as 64 and the default is 1024 when unset.
- [ ] **Step 2: Run the focused test and verify it fails** because `Settings` has no `max_output_tokens` setting.
- [ ] **Step 3: Add the setting and document it** in `.env.example` with a non-secret local default.
- [ ] **Step 4: Run the focused test and verify it passes.**

### Task 2: Add atomic reservation and idempotent settlement/release

**Files:**
- Modify: `06-lab-complete/app/cost_guard.py`
- Test: `06-lab-complete/tests/test_config_redis.py`

**Interfaces:**
- Consumes: `settings.daily_budget_usd`, `settings.max_output_tokens`, and existing `r` Redis client.
- Produces:
  - `reserve_budget(input_tokens: int) -> str`: atomically reserves input estimate plus maximum output cost and returns a unique reservation ID; raises 402 when over cap and 503 on Redis operation failure.
  - `settle_budget(reservation_id: str, input_tokens: int, output_tokens: int) -> float`: replaces a held maximum reservation with actual estimated cost; idempotent; raises 503 on Redis failure.
  - `release_budget(reservation_id: str) -> None`: releases an outstanding reservation idempotently; raises 503 on Redis failure.
- Retire `check_budget()` and `record_cost()` after migration; preserve the UTC daily aggregate semantics.

- [ ] **Step 1: Write failing tests** for: reserve under cap; reserve over cap returns 402; concurrent reservations cannot exceed cap; settlement releases unused capacity; duplicate settlement does not double count; duplicate release is harmless; attempted output above `max_output_tokens` is rejected and reservation is releasable.
- [ ] **Step 2: Run those tests and verify expected failures** against the current non-reservation API.
- [ ] **Step 3: Implement reservation ledger and Lua operations.** Store aggregate committed + reserved amount under the UTC-day key and per-reservation hash metadata under reservation-specific keys, including the original UTC-day aggregate key, reserved amount, and state. Settlement/release must use that stored day key, so a request crossing UTC midnight updates the day on which it reserved. Use Redis Lua for atomic reserve/settle/release; keep reservation metadata TTL no shorter than the day-key TTL. Make each terminal operation transition once from reserved to settled/released and keep terminal state long enough to make retries idempotent.
- [ ] **Step 4: Run the focused cost tests against the fake Redis contract and local Redis integration where available.** Verify repeated terminal calls preserve the total and concurrent attempts leave the total at or below the budget.

### Task 3: Enforce reservation lifecycle at the API/model boundary

**Files:**
- Modify: `06-lab-complete/app/main.py`
- Modify: `06-lab-complete/utils/mock_llm.py` only if a token-cap parameter is required by the implementation
- Test: `06-lab-complete/tests/test_api.py`

**Interfaces:**
- Consumes Task 1 `settings.max_output_tokens` and Task 2 reservation functions.
- `/ask` estimates input tokens as `max(1, len(question) // 4)`, reserves before `llm_ask`, rejects estimated output above cap, then settles with output estimate `max(1, len(answer) // 4)`.

- [ ] **Step 1: Write failing API tests** asserting reservation occurs before model invocation; model is not invoked if reserve returns 402; successful model execution settles; model exception releases and preserves the original HTTP failure; model output above cap is not returned and releases its reservation.
- [ ] **Step 2: Run the focused tests and verify expected failures** because `/ask` still calls `check_budget` and `record_cost`.
- [ ] **Step 3: Replace the preflight/read-after-write flow** with reserve → model → output-cap validation → settle, releasing on model or validation failure. Never call the model before a successful reservation.
- [ ] **Step 4: Run API tests and assert status codes/accounting calls for every lifecycle path.** A model exception is preserved only when reservation release succeeds; a Redis failure during release returns HTTP 503 and emits a log with the reservation ID, without exposing the API key.

### Task 4: Convert Redis operation failures to HTTP 503 and hash rate keys

**Files:**
- Modify: `06-lab-complete/app/rate_limiter.py`
- Modify: `06-lab-complete/app/cost_guard.py`
- Modify: `06-lab-complete/app/redis_client.py` only if health handling needs a shared exception helper
- Test: `06-lab-complete/tests/test_config_redis.py`

**Interfaces:**
- Rate limiter keeps `check_rate_limit(key: str) -> None`; Redis command failures raise `HTTPException(503)`; rejected requests remain 429.
- Rate-limit Redis key uses `sha256(key.encode()).hexdigest()` and must not contain the original key.
- Budget operations from Task 2 return 503 for Redis errors while preserving 402 for budget exhaustion.

- [ ] **Step 1: Write failing tests** with Redis `eval`/`get` raising connection errors, asserting HTTP 503; assert the exact rate key contains a SHA-256 digest and not the raw API key.
- [ ] **Step 2: Run focused tests and verify expected failures** (raised raw exception or unhashed key).
- [ ] **Step 3: Catch Redis command exceptions at guard boundaries** and translate them to HTTP 503 without masking existing HTTP exceptions or converting 429/402.
- [ ] **Step 4: Run focused failure/key tests and existing auth/rate/cost tests.**

### Task 5: Emit top-level structured request log fields

**Files:**
- Modify: `06-lab-complete/app/main.py`
- Test: `06-lab-complete/tests/test_api.py`

**Interfaces:**
- `_JsonFormatter` accepts the request event and emits one JSON object containing top-level `ts`, `lvl`, `event`, `path`, `status`, and `ms` fields.

- [ ] **Step 1: Update the log test** to assert `event == "request"`, `path == "/ask"`, integer `status`, numeric `ms`, and that `event` is not a serialized JSON string.
- [ ] **Step 2: Run it and verify failure** because the current middleware nests JSON as the message string.
- [ ] **Step 3: Pass structured fields through `LogRecord` extras** and have `_JsonFormatter` include the explicit request fields without double encoding.
- [ ] **Step 4: Run the focused logging test and parse every captured app log line as JSON.**

### Task 6: Full verification and protected-file audit

**Files:**
- No intended source changes.

- [ ] **Step 1: Run the full suite** from `06-lab-complete/`: `.venv/bin/python -m unittest discover -s tests -v`.
- [ ] **Step 2: Run the unmodified full grader**: `.venv/bin/python check_production_ready.py`; require `PASS 12/12` and 41/41 checks, otherwise report exact unmet criteria.
- [ ] **Step 3: Verify diff integrity** with `git diff --check` and confirm the grader and golden dataset have no diff.
- [ ] **Step 4: Record review findings and remaining limits**: estimates reflect the lab's mock token accounting, not provider-billed usage; any external provider integration would require provider-enforced max output and actual usage data.
