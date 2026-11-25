# Day 14 Lab — Mission Answers

> **Student:** tự điền họ tên/MSSV nếu biểu mẫu lớp yêu cầu; không ghi email hoặc số điện thoại.  
> Các mục `[TỰ ĐIỀN]` cần câu trả lời, quan sát hoặc output do bạn tự tạo/chạy. Không nộp nguyên trạng các dấu nhắc này.

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. `01-localhost-vs-production/develop/app.py:17-18` để key và URL database trong code: khi push sẽ lộ thông tin đăng nhập (chuỗi minh họa trong lab là giả).
2. `develop/app.py:21-22` hardcode debug/max tokens: khó thay đổi theo môi trường, dễ bật debug ngoài ý muốn.
3. `develop/app.py:33-38` dùng `print`, còn in cả key: log khó lọc, dễ lộ secret.
4. `develop/app.py:42` thiếu health check: nền tảng không có endpoint để phát hiện process hỏng.
5. `develop/app.py:51-53` bind `localhost`, port 8000 cứng, `reload=True`: không phù hợp container/cloud và debug reloader có thể chạy trong production.

### Exercise 1.2: Develop API run

- Lệnh bạn đã chạy: [TỰ ĐIỀN]
- Kết quả gọi API của bạn: [TỰ ĐIỀN]

### Exercise 1.3: Develop vs production

| Feature | Develop | Production | Why important? |
|---|---|---|---|
| Config/secrets | Hardcode key và DB URL minh họa | Lấy config từ environment; không commit secret | Một image có thể chạy nhiều môi trường mà không lộ key |
| Health/readiness | Thiếu endpoint chuyên dụng | `/health` báo process còn sống; `/ready` báo khả năng nhận traffic | Platform phân biệt cần restart với cần tạm ngừng route |
| Logging | `print` cả key | Log JSON có field để truy vấn | Dễ tìm sự cố và tránh in bí mật |
| Shutdown | `reload=True`, không có xử lý shutdown | ASGI lifespan và server chờ request đang chạy | Giảm mất request khi deploy/restart |
| State/scaling | Gắn vào process/localhost | Shared state qua Redis, container sau load balancer | Các replica dùng chung rate limit và budget |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `02-docker/develop/Dockerfile` dùng `python:3.11`; `02-docker/production/Dockerfile` dùng `python:3.11-slim` ở cả builder và runtime.
2. Working directory: `/app` ở cả hai Dockerfile.
3. Port/process: develop `EXPOSE 8000`, `python app.py`; production `EXPOSE 8000`, chạy `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2`.
4. Production dùng multi-stage để tránh đưa công cụ build vào image cuối và chạy non-root; develop là single-stage phục vụ học tập.

### Exercise 2.2–2.3: Container and image measurements

- Kết quả chạy container/curl của bạn: [TỰ ĐIỀN]
- Develop image size (`docker images`): [TỰ ĐIỀN MB]
- Production image size (`docker images`): [TỰ ĐIỀN MB]
- Chênh lệch (%), kèm cách tính: [TỰ ĐIỀN]

### Exercise 2.4: Compose stack

- Sơ đồ service bạn quan sát: [TỰ ĐIỀN]
- Kết quả test qua Nginx của bạn: [TỰ ĐIỀN]

## Part 3: Cloud Deployment

### Exercise 3.1 hoặc 3.2: Deploy Part 6

- Platform: [TỰ ĐIỀN Railway hoặc Render]
- Public URL: [TỰ ĐIỀN SAU KHI DEPLOY]
- Ảnh dashboard/service/test: `screenshots/` (tự chụp và thêm)
- Kết quả 4 lệnh CP6 (`/health`, `/ready`, `/ask` không key, `/ask` có key): [TỰ ĐIỀN output HTTP code]
- So sánh cấu hình (chưa phải trải nghiệm deploy): `06-lab-complete/railway.toml` cấu hình builder/healthcheck/port cho Railway; mẫu `03-cloud-deployment/render/render.yaml` mô tả Web Service, env vars và Key Value (Redis-compatible) bằng Blueprint. Bài K5 dùng dịch vụ Part 6 trong `06-lab-complete/`, không dùng mẫu app của Part 3 làm bản deploy. [BỔ SUNG quan sát của bạn sau khi deploy Render]

### Exercise 3.3: Cloud Run pipeline

Trong `03-cloud-deployment/production-cloud-run/cloudbuild.yaml`, bước `test` chạy trước bước build image; nếu test lỗi sẽ không deploy. Bước `build` tag image theo commit SHA và `latest`, rồi `push` lên registry. Bước `deploy` gọi `gcloud run deploy` dùng image theo commit SHA, đặt vùng, giới hạn scale và secret từ Secret Manager. `service.yaml` khai báo container port, resource limits, concurrency và probe liveness/startup để Cloud Run quản lý vòng đời. Đây là phân tích file mẫu, không khẳng định đã deploy Cloud Run.

## Part 4: API Security

### Exercise 4.1–4.3: Test results

- 401 (thiếu/sai key): [DÁN output `curl -i` bạn tự chạy; che token]
- 200 (token hợp lệ): [DÁN output `curl -i`; che token]
- 429 (rate limit): [DÁN output `curl -i`; che token]

### Exercise 4.4: Cost guard

Trong Part 6, rate limiter Redis đếm request theo cửa sổ 60 giây và từ chối 429 khi vượt `RATE_LIMIT_PER_MINUTE`; nó chống lưu lượng quá nhanh nhưng không đo USD. Cost guard dùng Redis Lua để reserve trước chi phí input + output cap theo ngày UTC, rồi settle chi phí mock thực tế hoặc release khi lỗi; hết `DAILY_BUDGET_USD` trả 402. Rate limit chặn số lần gọi, cost guard chặn ngân sách; cả hai dùng shared Redis để nhất quán giữa replicas. Giá trị là estimate từ mock token, không phải hóa đơn LLM thật.

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation notes and results

- Liveness `/health` cho biết process sống, vẫn 200 khi Redis lỗi; readiness `/ready` kiểm tra Redis và trả 503 nếu chưa đủ điều kiện nhận request. Khi readiness fail, không route traffic tới replica đó; liveness fail mới cần restart.
- State trong RAM riêng mỗi replica sẽ làm bộ đếm rate limit/budget không đồng nhất khi Nginx chuyển request qua replica khác; shared Redis giúp mọi replica đọc cùng trạng thái.
- Kết quả `test_stateless.py` trên 3 agent (dùng stack/cổng theo README K5): [TỰ ĐIỀN]
- Kết quả graceful shutdown bạn quan sát: [TỰ ĐIỀN]
- Lệnh dọn stack đã chạy: [TỰ ĐIỀN]

## Part 6: Final Project

- Lệnh: `cd 06-lab-complete && python check_production_ready.py`
- Output thực tế từ lần AI chạy trong checkout này (2026-11-25; không phải xác nhận bạn đã tự chạy trên máy khác):

```text
Production Readiness Check — Day 14 Lab
1. Dockerfile (multi-stage, < 500 MB): ✅ Docker build 1s; image 270 MB; GET /health 200
2. docker-compose.yml (agent + redis): ✅
3. .dockerignore: ✅
4. Health check: ✅ /health 200
5. Readiness: ✅ /ready 200; Redis offline → /ready 503, /health 200
6. API key auth: ✅ thiếu/sai key 401, đúng key 200
7. Rate limit: ✅ vượt giới hạn 429 sau 5 request, state còn sau restart
8. Cost guard: ✅ hết budget 402 ở request 1 với budget ≈ 0
9. Environment config: ✅
10. Structured logging: ✅ 10 dòng app log là JSON hợp lệ
11. Graceful shutdown: ✅ SIGTERM lúc in-flight trả 200; docker stop exit 0, 0.3s
12. Public URL ready (config): ✅ (không có nghĩa đã deploy URL public)
```

- Checklist Deliverable từ lần chạy grader trên:

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  PASS 12/12 — PRODUCTION READY!
```

Lệnh grader không sửa và golden dataset không sửa. **Trước nộp:** tự chạy lại `python check_production_ready.py` trên bản đã push; nếu kết quả khác, cập nhật mục này bằng output của chính lần đó.

## Part 7: Benchmark & Observability

- Agent v1/v2 local: AI đã chạy `AGENT_VERSION=v1 PORT=8001 python app.py` và `AGENT_VERSION=v2 PORT=8002 python app.py` bằng Python 3.11.17 trong môi trường tạm; chạy `load_test.py` cho 4 concurrency và 3 slow rate (300 request/lần), và `eval/run_eval.py` cho v1/v2. Xem file JSON thật tại `reports/` và số liệu trong `BENCHMARK_REPORT.md`.
- Quality gate: v1 1/23 (FAIL ngưỡng mặc định 80%), v2 trước sửa KB 21/23 (PASS 80%), v2 sau sửa KB 23/23 (PASS `--min-accuracy 1.0`, không regression so với v2 trước sửa). File: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.
- Job CI/exit code: chạy `python eval/run_eval.py --url "$BASE" --baseline reports/eval_v2.json --min-accuracy 1.0 --out reports/eval_ci.json` sau khi service test đã sẵn sàng; giữ nguyên exit code của script để GitHub Actions chặn merge khi accuracy thấp hơn 100% hoặc có regression. AI đã thử v1 so với baseline v2: exit code **1**, 20 câu regression (kết quả chỉ lưu trong `/tmp/opencode/`, không dùng làm report nộp).
- Bằng chứng Part 7: xem `BENCHMARK_REPORT.md`, `reports/`, `benchmark-results/`, `screenshots/`.

## AI log

- **Hỏi AI:** đọc hướng dẫn/checklist trong repo và hỗ trợ hoàn thiện bài lab.
- **AI hỗ trợ:** rà soát README, RULES, CHECKPOINTS, SUBMISSION và checklist; hỗ trợ code Part 6/bộ khung tài liệu; chạy benchmark local và eval bằng mock, sửa hai mục KB dựa trên lỗi eval. AI chạy lại unmodified grader trên code hiện tại ngày 2026-11-25: `PASS 12/12`, 41/41 checks; chạy 19 unit tests PASS. AI chạy thử partial stack observability và hai phép đo Locust nhưng so sánh scaling chưa hợp lệ (xem `BENCHMARK_REPORT.md`). Trước đó build từng lỗi Docker Hub 429, đã thành công ở lần kiểm tra mới nhất; không coi lần cũ là bằng chứng.
- **Tôi đã tự chỉnh gì:** [TỰ ĐIỀN trung thực sau khi tự xem/sửa bài]
- **Tôi tự kiểm tra gì:** [TỰ ĐIỀN lệnh đã chạy và kết quả thật của bạn; không ghi thay cho kiểm tra bạn chưa thực hiện]
