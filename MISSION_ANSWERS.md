# Day 14 Lab — Mission Answers

> **Student:** Bùi Quang Hiếu / 2A202603639
> Các ghi chú "chưa thực hiện/chưa xác minh" là những phần còn thiếu bằng chứng thực tế; không coi các phần đó là đã hoàn thành.

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

1. `01-localhost-vs-production/develop/app.py:17-18` để key và URL database trong code: khi push sẽ lộ thông tin đăng nhập (chuỗi minh họa trong lab là giả).
2. `develop/app.py:21-22` hardcode debug/max tokens: khó thay đổi theo môi trường, dễ bật debug ngoài ý muốn.
3. `develop/app.py:33-38` dùng `print`, còn in cả key: log khó lọc, dễ lộ secret.
4. `develop/app.py:42` thiếu health check: nền tảng không có endpoint để phát hiện process hỏng.
5. `develop/app.py:51-53` bind `localhost`, port 8000 cứng, `reload=True`: không phù hợp container/cloud và debug reloader có thể chạy trong production.

### Exercise 1.2: Develop API run

- Lệnh bạn đã chạy: curl -i -X POST http://localhost:8002/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
- Kết quả gọi API của bạn: HTTP/1.1 422 Unprocessable Content
date: Wed, 25 Nov 2026 15:36:42 GMT
server: uvicorn
content-length: 94
content-type: application/json

{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}(.venv)

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

- Kết quả chạy container/curl của bạn: đã gửi lệnh `curl -i -X POST http://localhost:8002/ask` với JSON body `{"question":"What is Docker?"}`; nhận HTTP 422 vì endpoint develop này nhận `question` dưới dạng query parameter, không nhận JSON body. Vì vậy lần gọi này chưa xác nhận được request thành công qua container.
  ```text
  HTTP/1.1 422 Unprocessable Entity
  {"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
  ```
- Develop image size (`docker images`): 426MB
- Production image size (`docker images`): 57.4MB
- Chênh lệch (%), kèm cách tính: 86.53% (develop size - production size) / develop size × 100%

### Exercise 2.4: Compose stack

- Sơ đồ cấu hình trong `02-docker/production/docker-compose.yml` (chưa xác nhận bằng lần chạy của tôi): Client → Nginx (:80) → Agent (:8000); Agent kết nối Redis (:6379) và Qdrant (:6333) trên Docker network nội bộ.
- Kết quả test qua Nginx: chưa thực hiện/chưa có output để ghi nhận.

## Part 3: Cloud Deployment

### Exercise 3.1 hoặc 3.2: Deploy Part 6

- Platform: Render
- Public URL: https://k5-l3a-day14-buiquanghieu-2a202603639.onrender.com/
- Ảnh dashboard/service/test: `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`.
- Kết quả 4 lệnh CP6 (`/health`, `/ready`, `/ask` không key, `/ask` có key):
curl -sS -o /dev/null -w '/health: %{http_code}\n' "$BASE/health"
/health: 200

curl -sS -o /dev/null -w '/ready: %{http_code}\n' "$BASE/ready"
/ready: 200

curl -sS -o /dev/null -w '/ask không có key: %{http_code}\n'   -X POST "$BASE/ask"   -H 'Content-Type: application/json'   -d '{"question":"Hello"}'
/ask không có key: 401

read -rsp 'API key: ' AGENT_API_KEY; export AGENT_API_KEY; echo
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
unset AGENT_API_KEY
API key: [đã nhập ẩn; không ghi giá trị]
200

- Quan sát Render: dashboard hiển thị Web Service kiểu Docker, nhánh `main`, commit `dcbe191` và trạng thái Live. Test public URL trong ảnh Terminal cho `/health` 200, `/ready` 200, `/ask` không key 401 và `/ask` có key 200. Ảnh không chứng minh giá trị hoặc cấu hình cụ thể của biến môi trường.

### Exercise 3.3: Cloud Run pipeline

Trong `03-cloud-deployment/production-cloud-run/cloudbuild.yaml`, bước `test` chạy trước bước build image; nếu test lỗi sẽ không deploy. Bước `build` tag image theo commit SHA và `latest`, rồi `push` lên registry. Bước `deploy` gọi `gcloud run deploy` dùng image theo commit SHA, đặt vùng, giới hạn scale và secret từ Secret Manager. `service.yaml` khai báo container port, resource limits, concurrency và probe liveness/startup để Cloud Run quản lý vòng đời. Đây là phân tích file mẫu, không khẳng định đã deploy Cloud Run.

## Part 4: API Security

### Exercise 4.1–4.3: Test results

- 401 (thiếu key): public Render `/ask` trả HTTP 401 trong lần kiểm tra được chụp tại `screenshots/test.png`.
- 200 (key hợp lệ): public Render `/ask` trả HTTP 200 trong cùng lần kiểm tra; không lưu hoặc hiển thị key.
- 429 (rate limit): chưa thực hiện/chưa có output xác thực để ghi nhận.

### Exercise 4.4: Cost guard

Trong Part 6, rate limiter Redis đếm request theo cửa sổ 60 giây và từ chối 429 khi vượt `RATE_LIMIT_PER_MINUTE`; nó chống lưu lượng quá nhanh nhưng không đo USD. Cost guard dùng Redis Lua để reserve trước chi phí input + output cap theo ngày UTC, rồi settle chi phí mock thực tế hoặc release khi lỗi; hết `DAILY_BUDGET_USD` trả 402. Rate limit chặn số lần gọi, cost guard chặn ngân sách; cả hai dùng shared Redis để nhất quán giữa replicas. Giá trị là estimate từ mock token, không phải hóa đơn LLM thật.

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation notes and results

- Liveness `/health` cho biết process sống, vẫn 200 khi Redis lỗi; readiness `/ready` kiểm tra Redis và trả 503 nếu chưa đủ điều kiện nhận request. Khi readiness fail, không route traffic tới replica đó; liveness fail mới cần restart.
- State trong RAM riêng mỗi replica sẽ làm bộ đếm rate limit/budget không đồng nhất khi Nginx chuyển request qua replica khác; shared Redis giúp mọi replica đọc cùng trạng thái.
- Kết quả `test_stateless.py` trên 3 agent (dùng stack/cổng theo README K5): ============================================================
Stateless Scaling Demo
============================================================

Session ID: 75d490b5-29bd-46aa-8229-68507db3314e

Request 1: [instance-bd6f44]
  Q: What is Docker?
  A: Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!...

Request 2: [instance-6ce423]
  Q: Why do we need containers?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 3: [instance-00a810]
  Q: What is Kubernetes?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 4: [instance-bd6f44]
  Q: How does load balancing work?
  A: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận....

Request 5: [instance-6ce423]
  Q: What is Redis used for?
  A: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé....

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-bd6f44', 'instance-00a810', 'instance-6ce423'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Kubernetes?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: How does load balancing work?...
  [assistant]: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã đư...
  [user]: What is Redis used for?...
  [assistant]: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đ...

✅ Session history preserved across all instances via Redis!
- Kết quả graceful shutdown bạn quan sát: curl -s -X POST "http://localhost:8000/ask?question=hello" &
curl -s -X POST "http://localhost:8002/ask?question=hello" &
sleep 0.5 && kill -SIGTERM 902735
wait
[1] 908373
[2] 908374
{"timestamp":"2026-11-25T16:17:37.240+00:00","status":404,"error":"Not Found","path":"/ask"}[1]-  Done                   curl -s -X POST "http://localhost:8000/ask?question=hello"
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}[2]+  Done      curl -s -X POST "http://localhost:8002/ask?question=hello"
- Lệnh dọn stack đã chạy: cd 05-scaling-reliability/production && docker compose down

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

- Trạng thái của tôi: **chưa tự thực hiện Part 7**. Các file JSON/CSV và `BENCHMARK_REPORT.md` trong repository là artefact benchmark/eval local do AI tạo trong quá trình hỗ trợ; tôi chưa tự chạy hoặc xác minh lại chúng.
- Chưa hoàn thành bằng chứng quan sát: `grafana-dashboard.png`, `jaeger-slow-trace.png`, `jaeger-error-trace.png`, `prometheus-alert-firing.png` chưa có trong `screenshots/`.
- Do chưa tự hoàn thành phần này, không khẳng định đã tự chạy CI job, kiểm tra dashboard/trace/alert, hoặc xác nhận scaling benchmark.

## AI log

- **Hỏi AI:** đọc hướng dẫn/checklist trong repo và hỗ trợ hoàn thiện bài lab.
- **AI hỗ trợ:** rà soát README, RULES, CHECKPOINTS, SUBMISSION và checklist; hỗ trợ code Part 6/bộ khung tài liệu; chạy benchmark local và eval bằng mock, sửa hai mục KB dựa trên lỗi eval. AI chạy lại unmodified grader trên code hiện tại ngày 2026-11-25: `PASS 12/12`, 41/41 checks; chạy 19 unit tests PASS. AI chạy thử partial stack observability và hai phép đo Locust nhưng so sánh scaling chưa hợp lệ (xem `BENCHMARK_REPORT.md`). Trước đó build từng lỗi Docker Hub 429, đã thành công ở lần kiểm tra mới nhất; không coi lần cũ là bằng chứng.
- **Tôi đã tự chỉnh gì:** Tôi đã bổ sung kết quả quan sát được cho `test_stateless.py`, graceful shutdown và lệnh dọn stack ở Part 5. AI hỗ trợ giải thích hướng dẫn và cách trình bày.
- **Tôi tự kiểm tra gì:** Tôi đã chạy `test_stateless.py` với 3 agent; output hiển thị 3 instance và lịch sử hội thoại gồm 10 messages. Thử graceful shutdown của tôi chưa chứng minh được hai request hoàn tất: request ở port 8000 trả 404, request ở port 8002 trả response. Tôi đã kiểm tra public Render URL; ảnh `screenshots/test.png` ghi nhận `/health` 200, `/ready` 200, `/ask` không key 401 và `/ask` có key 200. Tôi chưa tự làm Part 7 và chưa có kết quả test 429 hoặc test Compose/Nginx Part 2.4.
