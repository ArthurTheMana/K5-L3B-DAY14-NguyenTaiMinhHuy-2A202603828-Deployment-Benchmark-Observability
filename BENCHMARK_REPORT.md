# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Tài Minh Huy
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows, WSL2 Ubuntu, Python 3.12.16, Docker 29.9.3, Docker Compose v5.7.0

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Đảm bảo thời gian phản hồi và phát hiện tail latency. |
| Error rate `/ask` | ≤ 2% | Đảm bảo ít nhất 98% requests thành công. |
| Accuracy trên golden dataset | ≥ 80%; mục tiêu cuối 100% | Kiểm soát chất lượng và ngăn regression. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.49 | 188.0 | 217.2 | 1687.2 | 0.33% | PASS |
| 10 | 36.14 | 185.8 | 218.8 | 1697.6 | 1.00% | PASS |
| 50 | 111.72 | 199.8 | 262.5 | 1696.6 | 1.00% | PASS |
| 100 | 80.81 | 282.4 | 2053.0 | 2832.8 | 2.00% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

RPS không tăng tuyến tính theo concurrency. Throughput đạt cao nhất tại concurrency 50 với 111.72 RPS. Khi concurrency tăng lên 100, throughput giảm còn 80.81 RPS và p95 tăng lên 2053 ms. Đây là dấu hiệu hệ thống bắt đầu bão hòa, nhưng chưa đủ dữ liệu để xác định chính xác bottleneck. Mỗi lần kiểm thử sử dụng 300 requests.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.4 | 215.8 | 223.4 |
| 0.03 (mặc định) | 208.5 | 215.6 | 1668.3 |
| 0.1 | 358.0 | 1689.1 | 1707.1 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

p99 nhạy với request chậm ngay khi slow rate tăng từ 0% lên 3%, tăng từ 223.4 ms lên 1668.3 ms. Tại slow rate 10%, p95 tăng lên 1689.1 ms, trong khi average chỉ đạt 358 ms. Vì vậy, không nên chỉ sử dụng average latency để đánh giá SLO. Error rate biến động do lỗi upstream ngẫu nhiên của Mock LLM.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 55.0 | 109.0 | 115.1 |
| Tổng cost (USD) | 0.000391 | 0.000760 | 0.000803 |
| Cost / câu đúng (USD) | 0.00039090 | 0.00003619 | 0.00003492 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Bổ sung kiến thức JWT và API Key. |
| scaling-03 | cpu, memory, custom metrics | Bổ sung kiến thức Kubernetes HPA. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v2 sử dụng nhiều tokens và có tổng chi phí cao hơn v1, nhưng chi phí trên mỗi câu trả lời đúng thấp hơn đáng kể. Sau khi bổ sung hai Knowledge Base entries, accuracy đạt 100% (23/23), zero regression và zero execution errors. p95 latency lần lượt là 184.8 ms, 216.1 ms và 219.9 ms. Chi phí được mô phỏng bằng Mock LLM. Accuracy 100% chỉ được xác nhận trên Golden Dataset hiện tại.

---


### 3.1 Quality Gate và Regression Testing

| Test | Result | Exit Code |
|---|---|---|
| Agent v1 baseline | FAIL | 1 |
| Agent v2 vs v1 | PASS | 0 |
| Negative Quality Gate | Expected FAIL | 1 |
| Strict Quality Gate (100%) | PASS | 0 |

Agent v2 đạt 23/23 câu đúng và zero regression.
Negative Quality Gate phát hiện 20 regression.
Strict Quality Gate xác nhận accuracy 100%.


### 3.2 GitHub Actions Quality Gate

CI step đề xuất sau khi khởi động candidate agent:

    - name: AI Agent Quality Gate
      working-directory: 06-lab-complete/benchmark-observability/develop
      run: python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_ci.json

Exit code 0 cho phép CI pipeline tiếp tục.
Exit code 1 làm CI job thất bại.
Required status check giúp ngăn merge khi Quality Gate FAIL.

CI step này chưa được chạy thực tế trên GitHub Actions.

### 3.3 Evidence

- [JSON reports](06-lab-complete/benchmark-observability/develop/reports/)
- [Terminal evidence](evidence/CP7/)
- [Screenshots](screenshots/CP7-benchmark-local/)

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
