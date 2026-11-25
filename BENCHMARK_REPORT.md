# Benchmark & Observability Report — Day 14

> Các bảng load/eval và CSV scaling dưới đây lấy từ lần chạy mock local trong checkout này. Hai lần Locust chưa chứng minh scale 1-vs-3 hợp lệ; các phần cloud, ảnh và fault injection còn chờ bằng chứng thật, không tự ước lượng.

**Họ tên:** [TỰ ĐIỀN]  
**Ngày chạy local:** 2026-11-25 (theo đồng hồ phiên chạy)  
**Môi trường:** Linux, Python 3.11.17 (uv), mock LLM local; [TỰ ĐIỀN CPU/RAM/Docker từ máy thực tế]

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Theo ngưỡng mặc định `load_test.py`; thử nghiệm 100 concurrent vượt ngưỡng. |
| Error rate `/ask` | ≤ 2% | Theo ngưỡng mặc định `load_test.py`; thử nghiệm 50 concurrent vượt ngưỡng. |
| Accuracy trên golden dataset | ≥ 100% ở bản v2 đã sửa | Quality gate cuối chạy `--min-accuracy 1.0` và 23/23 câu đạt; bản v2 ban đầu dùng ngưỡng mặc định ≥ 80%. |

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Nguồn số liệu: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json` (bản sao kết quả chạy local từ `develop/reports/`).

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.61 | 186.8 | 216.2 | 1696.3 | 1.00% | PASS |
| 10 | 38.91 | 189.9 | 218.4 | 1693.5 | 2.00% | PASS |
| 50 | 120.33 | 192.8 | 237.7 | 387.5 | 2.67% | FAIL (error) |
| 100 | 57.65 | 399.6 | 3389.5 | 3790.5 | 0.67% | FAIL (p95) |

**Nhận xét từ lần chạy local:** RPS tăng từ 4.61 lên 120.33 ở concurrency 50 nhưng giảm còn 57.65 ở 100; không tuyến tính do contention/queueing trên máy local. 50 concurrent vượt SLO lỗi (2.67%); 100 concurrent vượt SLO p95 (3389.5 ms). Mỗi hàng lấy từ file JSON tương ứng (300 request), mock có jitter/lỗi ngẫu nhiên nên số liệu các lần chạy khác có thể thay đổi.

### 2.2 Tail latency

Nguồn số liệu: `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 187.4 | 215.7 | 219.6 |
| 0.03 (mặc định) | 241.5 | 220.0 | 1701.8 |
| 0.1 | 309.5 | 1683.3 | 1704.2 |

**Nhận xét từ lần chạy local:** Khi slow rate tăng 0 → 0.03, p99 tăng 219.6 → 1701.8 ms trong khi p95 chỉ 215.7 → 220.0 ms; ở rate 0.1 p95 tăng lên 1683.3 ms. Average 309.5 ms tại rate 0.1 che khuất độ trễ đuôi p95 1683.3 ms, nên không dùng average làm SLO duy nhất. Mỗi phép đo gồm 300 request, concurrency 20.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Nguồn số liệu: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.1 | 109.0 | 112.5 |
| Tổng cost (USD) | 0.000405 | 0.000760 | 0.000780 |
| Cost / câu đúng (USD) | 0.00040455 | 0.00003619 | 0.00003393 |
| Quality gate | FAIL | PASS (≥ 80%) | PASS (≥ 100%, không regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm tài liệu JWT có expiry và chữ ký vào `KNOWLEDGE_BASE`, kích hoạt bằng `jwt`. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm tài liệu Kubernetes HPA về các chỉ số scale, kích hoạt bằng `kubernetes hpa`. |

**Trade-off chất lượng / chi phí / latency (mock):** v1 dùng 57.1 token/câu, cost $0.000405 cho 23 câu nhưng chỉ đúng 1; v2 đã sửa dùng 112.5 token/câu, cost $0.000780 nhưng đúng 23. Chi phí/câu đúng giảm từ $0.00040455 xuống $0.00003393. p95 eval v1 185.4 ms, v2 trước sửa 219.1 ms và v2 sau sửa 213.2 ms. Đây là giá trị đo từ mock, không phải hóa đơn provider.

---

## 4. Observability stack (production)

**Trạng thái lần chạy local 2026-11-25:** stack đầy đủ chưa chạy được vì host port `3000` thuộc container khác (`p-068-grafana-1`). Chỉ bật thử agent/Nginx/Jaeger/Prometheus để thu CSV Locust, không có Grafana của lab; không có ảnh/traces/alert xác thực cho bảng dưới. Image agent ban đầu lỗi import `uvicorn`; sửa `PYTHONUSERBASE` trong Dockerfile rồi xác nhận import thành công trước khi chạy Locust. Không coi việc sửa này là bằng chứng hoàn tất CP8.

### 4.1 Screenshot (thêm ảnh thật vào `screenshots/`)

- [ ] `screenshots/grafana-dashboard.png` — dashboard Grafana khi đang có tải, thấy Golden Signals
- [ ] `screenshots/jaeger-slow-trace.png` — trace chậm, nhận diện span tốn thời gian
- [ ] `screenshots/jaeger-error-trace.png` — trace lỗi có `exception`
- [ ] `screenshots/prometheus-alert-firing.png` — trang Alerts Prometheus, ít nhất hai alert firing cùng lúc theo checkpoint K5

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | Chưa chạy | Chưa đo | Chưa đo |
| B | `MOCK_SLOW_RATE=0.3` | Chưa chạy | Chưa đo | Chưa đo |
| C | `LLM_MODEL=mock-llm-large` | Chưa chạy | Chưa đo | Chưa đo |
| D | `docker pause` 1 instance | Chưa chạy | Chưa đo | Chưa đo |
| E | `AGENT_VERSION=v1` | Chưa chạy | Chưa đo | Chưa đo |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?** [TỰ ĐIỀN]

### 4.3 Debug bằng trace

- `trace_id`: [TỰ ĐIỀN từ trace thật]
- Tổng thời gian: [TỰ ĐIỀN] ms
- Span chiếm nhiều thời gian nhất: [TỰ ĐIỀN]
- Dòng log JSON tương ứng có cùng `trace_id`:

```json
[DÁN LOG THẬT]
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Nguồn số liệu thô: `benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv`; xem giới hạn xác minh số replica bên dưới.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.27 | 190 | 220 | 1700 | 64/7178 `/ask` (0.89%) |
| 3 | 60.11 | 190 | 220 | 1700 | 68/7160 `/ask` (0.95%) |

**Giải thích kết quả:** Trên hai lần chạy 2 phút, p95 `/ask` đều 220 ms và RPS 60.27 → 60.11, **không thấy cải thiện trong số liệu này**. Locust trả exit code 1 vì 503 (64 và 68 request `/ask` tương ứng). Hai CSV chỉ ghi request/latency/failures, **không ghi số replica trong suốt phép đo**; vì vậy không thể dùng chúng để chứng minh phép so sánh đúng 1-vs-3 instance hay quy kết nút thắt. Cần chạy lại trên stack sạch và lưu bằng chứng số container trong cả hai giai đoạn.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. [TỰ ĐIỀN]
  2. [TỰ ĐIỀN]
  3. [TỰ ĐIỀN]
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa? [TỰ ĐIỀN]

## Evidence checklist

- [x] Load JSON: 4 concurrency (`load_v2_c1`, `c10`, `c50`, `c100`) và 3 slow-rate files — chạy local 2026-11-25.
- [x] Eval JSON: `eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json` — chạy local 2026-11-25.
- [x] Locust CSV thô: `benchmark-results/scale_1_stats.csv`, `scale_3_stats.csv` (cần chạy lại để so sánh scale hợp lệ; xem cảnh báo ở mục 5).
- [ ] 4 ảnh Part 7: Grafana, Jaeger slow trace, Jaeger error trace, Prometheus firing alerts.
- [ ] 3 ảnh deployment: dashboard, running service, test results trong `screenshots/`.
- [x] Số liệu ở bảng load/eval khớp JSON và bảng scaling khớp hai CSV; phép so sánh scaling vẫn thiếu bằng chứng số replica ổn định.

## Lệnh/evidence handoff K5 (chạy và lưu output thật)

Từ root repo, tạo report nếu chưa có và không ghi đè file đã điền:

```bash
cp -n 06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md BENCHMARK_REPORT.md
```

Trong `06-lab-complete/benchmark-observability/develop/`, chạy agent v2 ở `http://localhost:8002`, rồi:

```bash
for c in 1 10 50 100; do
  python load_test.py --url http://localhost:8002 --requests 300 --concurrency "$c" --out "reports/load_v2_c${c}.json"
done
```

Chạy tiếp các phép đo slow-rate (mỗi lần restart v2 với biến môi trường tương ứng):

```bash
python load_test.py --url http://localhost:8002 --requests 300 --concurrency 20 --out reports/load_v2_slow_0.json
python load_test.py --url http://localhost:8002 --requests 300 --concurrency 20 --out reports/load_v2_slow_0.03.json
python load_test.py --url http://localhost:8002 --requests 300 --concurrency 20 --out reports/load_v2_slow_0.1.json
```

Chạy eval v1/v2 theo Exercise 7.3, lưu `reports/eval_v1.json` và `reports/eval_v2.json`; sau khi sửa `develop/utils/mock_llm.py` và restart v2, lưu eval cuối:

```bash
python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json
```

Từ thư mục `06-lab-complete/benchmark-observability/production/`, dùng cùng project name `k5-day14-observability`; Locust phải chạy headless để ghi CSV:

```bash
docker compose -p k5-day14-observability up -d --build --scale agent=1
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
docker compose -p k5-day14-observability up -d --scale agent=3
docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

Trước khi dọn stack, chụp ảnh và lưu log thật. Sau khi tạo evidence, copy file ra đúng các thư mục root:

```bash
mkdir -p reports benchmark-results screenshots
cp -r 06-lab-complete/benchmark-observability/develop/reports/. reports/
cp -r 06-lab-complete/benchmark-observability/production/benchmark-results/. benchmark-results/
```

Khi đã lưu evidence: `docker compose -p k5-day14-observability down -v`. Lệnh load/eval phía trên đã chạy cho bản local; stack Docker/Locust và ảnh Part 7 chỉ đánh dấu hoàn thành sau khi có file thật.
