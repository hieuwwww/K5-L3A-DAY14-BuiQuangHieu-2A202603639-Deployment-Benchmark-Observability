# Day 14 Lab Completion — Design

## Intent

Help the student complete the K5 Day 14 Deployment, Benchmark & Observability lab using the repository's own instructions and checklist. The final submission should be technically verifiable and honest: no invented measurements, cloud URLs, screenshots, or claims that require access to the student's accounts or machine.

## Goals

- Complete the Part 6 starter implementation in `06-lab-complete/` according to its README contract and make the grading script pass as many/all checks as the available environment permits.
- Preserve instructor-provided files that must not be edited, especially `check_production_ready.py` and `develop/eval/golden_dataset.jsonl`.
- Prepare submission documents and evidence locations according to K5 `CHECKPOINTS.md`, `SUBMISSION.md`, and `DAY14_DELIVERY_CHECKLIST.md`.
- Run local verification and record actual command outcomes; clearly identify checks requiring Docker, a Redis/cloud account, live deployment, screenshots, or student-provided measurements.
- Include an AI log entry reflecting this assistance, for the student to review and accurately supplement.

## Non-goals and anti-goals

- Do not fabricate personal exercise answers, benchmark results, Docker image sizes, alert timings, deployment URLs, screenshots, or test output.
- Do not modify the grader or the protected golden evaluation dataset.
- Do not commit secrets, `.env` files, cloud tokens, or real API keys.
- Do not deploy to a cloud account or publish the repository on the student's behalf.
- Do not claim a full `PASS 12/12` unless the unmodified grading script actually reports it in this environment.

## Constraints

- K5-specific guidance in the root `README.md` and `CHECKPOINTS.md` overrides generic checklist paths. Part 6 code remains inside `06-lab-complete/`.
- The grader contract requires FastAPI routes, API key auth, Redis-backed rate limiting and cost accounting, health/readiness semantics, structured JSON app logs, graceful shutdown, a multi-stage non-root Docker image, Compose Redis, and Railway or Render configuration.
- Benchmark commands and deployment behavior follow the corrected ports/endpoints and project-name notes in the root README.
- Measured or account-specific evidence must come from the student's own execution.

## Approaches considered

1. **Complete all verifiable local work and prepare clearly marked submission templates (chosen).** Implement Part 6, run the grader/tests where possible, and prepare answer/deployment/report documents with explicit evidence TODOs. This provides broad progress without misrepresenting student-specific evidence.
2. **Complete Part 6 only.** Smaller scope, but leaves required submission structure and guidance fragmented across the lab docs.
3. **Fill every submission field with plausible examples.** Rejected because it would fabricate individual work and measurements and conflict with `RULES.md`.

## Design

### Part 6 implementation

Implement the existing starter modules rather than relocating or replacing the project structure. Read configuration from environment variables; use lazy Redis connectivity so the app starts if Redis is temporarily unavailable; return liveness independently of Redis and readiness based on Redis health; protect `/ask` with constant-time API-key comparison; enforce a Redis sliding-window limit and a Redis-backed daily budget; emit one JSON object per application log line; and rely on ASGI/Uvicorn graceful process shutdown rather than installing a signal handler that prevents termination. Complete Docker, Compose, `.dockerignore`, `.env.example`, and one or both supported cloud configuration files consistently with the grader contract.

### Submission artifacts

- Add `MISSION_ANSWERS.md` with the required Part 1–5 sections and Part 6 grader-output location. Leave personal observations and run-derived outputs visibly marked for the student rather than inventing them. Include an AI log describing the assistance and local verification actually performed.
- Cover required Part 3 platform comparison and Cloud Run pipeline description as student-completed prompts; do not present AI-authored prose as the student's own answer.
- Add `DEPLOYMENT.md` with the required test command template and clearly unfilled public URL/platform/screenshot fields until the student deploys.
- Create `BENCHMARK_REPORT.md` from the provided template without inventing results, and provide expected evidence directories only where useful. Do not create fake JSON/CSV or screenshot evidence.
- Preserve the submission's required root-level `reports/`, `benchmark-results/`, and `screenshots/` layout; do not imply empty directories constitute evidence. Generated JSON/CSV must be copied from the specified Part 7 paths after the student runs them.
- Keep all generated artifacts and code aligned to the K5 repository layout.

### Verification

Run static checks and the unmodified Part 6 grader, then targeted tests or commands supported by the environment. Record exact outcomes. If Docker/Redis/cloud credentials are unavailable, distinguish skipped/unverified checks from passes and list the exact commands the student needs to run. Review changes for accidentally included secrets and protected-file modifications.

Report grader results precisely: only the full, unmodified grader reporting `PASS 12/12` counts as Part 6 complete; warnings, partial runs, and checks not possible in this environment must remain clearly labeled as incomplete/unverified.

## Builder decisions

- Use the existing Python/FastAPI/Redis/Docker patterns and dependency versions in the repository.
- Prefer a minimal implementation that matches the grader's documented contract over introducing unrelated features or dependencies.
- The student supplies personal lab observations, live deployment details, benchmark numbers, alert timings, and screenshots after running the documented exercises.

## Review follow-up design — budget reservations and request hardening

### Intent

Address the independent review's confirmed race in daily budget enforcement and harden adjacent Redis/error/logging details without changing the Part 6 grader or the lab's external API contract.

### Approaches considered

1. **Atomic reservation plus settlement (selected by user).** Reserve the maximum cost allowed for one request in Redis atomically before invoking the model; settle by replacing the reservation with measured cost afterward. This prevents concurrent requests from spending against the same remaining budget, at the cost of temporarily holding budget and rejecting requests that cannot reserve the cap.
2. **Serialize requests around the model call.** Simpler reservation semantics, but holds a distributed lock across the slow model call and materially reduces throughput; rejected.
3. **Keep preflight read and document overspend.** No change in request behavior but does not close the reported budget race; rejected.

### Design

- Add an atomic Redis Lua reservation operation keyed by UTC day. A request must reserve its estimated input cost plus the configured maximum output-token cost before the model call. Fail with HTTP 402 if the reservation would exceed the daily budget. Do not invoke the model if the reservation cannot be made.
- Configure an explicit `MAX_OUTPUT_TOKENS` ceiling and pass/enforce that ceiling at the model boundary. For this repository's mock LLM, validate the resulting answer estimate does not exceed the ceiling. The reservation is derived from the input estimate and that output ceiling, using the existing per-token prices.
- After a successful model response, atomically settle the reservation to the actual estimated token cost, releasing unused reserved capacity. If model execution fails, release the reservation; the original failure response is preserved unless Redis settlement itself fails, in which case return HTTP 503 and log the reservation identifier for reconciliation.
- Use a unique reservation identifier and an idempotent Lua settlement/release operation so retries cannot apply settlement twice. Keep reservation accounting and expiry in the UTC-day budget key; no new external service or library.
- Configured Redis connection/command failures in readiness, rate limiting, reservation, settlement, or release must be caught and surfaced as HTTP 503 (readiness already behaves this way). Liveness remains independent of Redis. No silent fail-open behavior.
- Derive rate-limit Redis keys from a one-way SHA-256 digest of the API key; never store the raw credential in Redis key names.
- Emit request logs as JSON objects with top-level `event`, `path`, `status`, and `ms` fields rather than JSON-encoding a nested event string.

### Constraints and non-goals

- Preserve the grader and `benchmark-observability/develop/eval/golden_dataset.jsonl` unchanged.
- Preserve HTTP 401/429/402 contracts and add deliberate HTTP 503 behavior only for unavailable Redis.
- Keep the implementation in existing Part 6 modules; do not add dependencies or deploy cloud resources.
- Do not claim external LLM spend safety beyond the enforced configured input/output token ceiling; estimates/pricing are still the lab's mock accounting model.

### Verification

- Add failing tests first for concurrent reservation caps, settlement/release/idempotency, output cap, Redis operation failures, digest-only rate keys, and top-level JSON log fields.
- Run the complete unittest suite and the unmodified full production grader; protected files must remain unchanged.
