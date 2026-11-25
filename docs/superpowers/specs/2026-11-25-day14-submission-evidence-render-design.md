# Day 14: verified local evidence and Render handoff

## Intent

Complete as much of the K5 submission as can be honestly produced in this checkout, then give the student reproducible Render deployment instructions. A submission is ready only when every required artifact has evidence from an actual run and the full Part 6 grader passes.

## Approach

- Chosen: run the documented local experiments and fill reports from generated artifacts; guide the student through Render and identify account-dependent steps separately.
- Rejected: documentation-only handoff (leaves required JSON/CSV absent).
- Rejected: invented benchmark values, screenshots, public URL, or grader output (would misrepresent the submission).

## Scope and constraints

- Preserve existing unfinished work and the protected Part 6 grader and golden dataset. Do not commit or push, deploy to a cloud account, or expose API keys without explicit permission.
- Run CP7 v1/v2 load and evaluation experiments with documented parameters; if the exercise requires repairing the v2 knowledge base, make the smallest justified fix and retain before/after evidence. Place real JSON in root `reports/` and fill corresponding report cells from those files.
- Attempt the CP8 local Docker observability stack and headless Locust runs. Only record real CSVs, traces, alerts, timings, and screenshots; label blocked steps explicitly if images or dependencies cannot be obtained. Avoid disrupting other Docker projects.
- Re-run Part 6 tests and the unmodified full grader. Docker Hub's earlier 429 may still prevent an image build; do not describe a skipped test or earlier grader run as a pass on the current tree.
- Fill repository-derived and measured portions of `MISSION_ANSWERS.md`, `BENCHMARK_REPORT.md`, and `DEPLOYMENT.md`; preserve personal-reflection prompts for the student rather than authoring their experiences or inventing a public URL.
- Provide step-by-step Render setup for this repo's `06-lab-complete/` Docker service plus Redis and environment variables, and commands to verify the four HTTP responses without leaking the key. Update deployment documentation with the actual public URL and screenshots only after student-provided deployment evidence.
- Final audit checks artifact names, consistency of reported figures with JSON/CSV, secrets, protected files, and remaining conditions for submission.

## Success criterion

All locally obtainable evidence exists with reproducible commands and no fabricated claims. The final handoff explicitly lists any unavailable cloud, Docker, screenshot, personal-answer, or grader requirements; it must not claim the submission is ready while any required criterion is unmet.
