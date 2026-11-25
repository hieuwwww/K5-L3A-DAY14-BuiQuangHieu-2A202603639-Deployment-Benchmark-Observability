# Deployment Information

> Hoàn thiện sau khi tự deploy Part 6. Không ghi giá trị secret/API key vào file này.

## Public URL

https://k5-l3a-day14-buiquanghieu-2a202603639.onrender.com/

## Platform

Render

## Hướng dẫn deploy Render (bạn thao tác trên tài khoản của mình)

1. Sau khi bài local đã kiểm tra, rà soát secret và `git status`, rồi **bạn** commit/push thay đổi lên fork GitHub đúng tên repo K5. Đặt repo Public để Lab Coach truy cập được. Không push `.env` hoặc API key.
2. Vào Render Dashboard → **New → Key Value** (Redis-compatible/Valkey), chọn region trùng Web Service (ví dụ Singapore) và compute plan phù hợp. Xem giá/giới hạn trên Dashboard trước khi tạo. Ưu tiên maxmemory policy `noeviction` để không âm thầm làm mất state rate limit/budget; Free Key Value không lưu bền khi restart, nên **không** xem cấu hình Free là bảo đảm ngân sách production. Trong trang Key Value → **Connect**, lấy **Internal URL** (không đưa URL này lên Git).
3. Render Dashboard → **New → Web Service**, kết nối cùng repo và branch đã push. Chọn **Language: Docker**, **Root Directory: `06-lab-complete`**, Dockerfile path `Dockerfile`, Docker context `.` (đều tương đối theo Root Directory); chọn cùng region với Key Value. Dùng CMD của Dockerfile, không nhập start command Python khác. Health check path `/health`. Chọn plan sau khi xem giới hạn/cước; Free web có thể ngủ khi nhàn rỗi và lần gọi đầu sẽ chậm.
4. Trong Web Service → **Environment**, tạo `AGENT_API_KEY` với key ngẫu nhiên đủ mạnh (giữ riêng), `REDIS_URL` bằng Internal URL vừa lấy, `ENVIRONMENT=production`. Có thể đặt `RATE_LIMIT_PER_MINUTE=10`, `DAILY_BUDGET_USD=1.0`, `MAX_OUTPUT_TOKENS=1024`; `PORT` được Render cấp, Dockerfile đã đọc `$PORT`. Lưu và deploy; **không** ghi giá trị key hoặc REDIS_URL vào tài liệu/ảnh. Tài khoản dùng Free Key Value có nguy cơ mất state khi restart; nếu cần hạn mức bền vững, dùng plan có persistence và kiểm tra chính sách Redis/Valkey.
5. Theo dõi build/deploy logs tới trạng thái Live. Nếu Docker Hub trả 429 khi tải `python:3.11-slim`, retry sau hoặc cấu hình registry credential theo hướng dẫn Render, **không** tuyên bố đã build thành công khi build fail. Nếu `/ready` 503: xác nhận hai resource cùng workspace/region, Internal URL đúng và Key Value ở trạng thái Available; `/health` vẫn có thể trả 200 khi Redis chưa sẵn sàng.
6. Sao chép URL HTTPS của Web Service vào mục Public URL, chạy bốn phép kiểm bên dưới. Chỉ ghi kết quả HTTP sau khi chạy thật và chụp 3 ảnh yêu cầu (che secret). Sau đó kiểm tra URL từ cửa sổ ẩn danh. Không dùng Render Blueprint mẫu `03-cloud-deployment/render/render.yaml` vì nó triển khai app demo ở Part 3, không phải Part 6.

Tham khảo tài liệu Render: [Docker deployment](https://render.com/docs/docker), [monorepo Root Directory](https://render.com/docs/monorepo-support), [Render Key Value](https://render.com/docs/key-value), [Free limitations](https://render.com/docs/free).

## Test Commands

Thay `BASE` bằng URL của bạn. Gán key qua biến môi trường cục bộ, không dán key vào file hoặc ảnh chụp.

```bash
BASE="https://your-agent.example"

# Health check — expected 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"

# Readiness check — expected 200 when Redis is connected
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# No key — expected 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'

# Valid key — expected 200
read -rsp 'API key: ' AGENT_API_KEY; export AGENT_API_KEY; echo
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
unset AGENT_API_KEY
```

## Environment Variables Set

Tên biến cần xác nhận trên Dashboard (không ghi giá trị): `REDIS_URL`, `AGENT_API_KEY`, `ENVIRONMENT`, và nếu có `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MAX_OUTPUT_TOKENS`; `PORT` do Render cấp.

## Screenshots

- [x] `screenshots/dashboard.png` — deployment dashboard
- [x] `screenshots/running.png` — service running
- [x] `screenshots/test.png` — HTTP status tests (no API key value visible)

## Deployment verification

- Deployment shown in Render screenshot: Nov 25, 2026, 9:32:27 PM GMT+7 (commit `dcbe191`).
- HTTP results recorded in `screenshots/test.png`: `/health` 200, `/ready` 200, unauthenticated `/ask` 401, authenticated `/ask` 200.
- Source: screenshot supplied by the user. These results do not independently verify the dashboard's environment-variable values.
