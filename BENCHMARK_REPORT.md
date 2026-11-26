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

- [x] [Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)](screenshots/CP8-observability/CP8-11-grafana-golden-signals-baseline.png)
- [x] [Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)](screenshots/CP8-observability/CP8-16b-jaeger-llm-span-detail.png)
- [x] [Một trace lỗi trong Jaeger (có event `exception`)](screenshots/CP8-observability/CP8-18-jaeger-error-trace-exception.png)
- [x] [Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**](screenshots/CP8-observability/CP8-22-experiment-a-prometheus-alert-firing.png)

Production Observability Stack bao gồm Nginx, Agent instances, Prometheus, Grafana, Jaeger và Locust.

Trong quá trình triển khai ban đầu, Agent gặp lỗi `ModuleNotFoundError: No module named 'uvicorn'` do đường dẫn Python user-site packages không khớp với thư mục cài đặt dependencies trong Docker image. Sau khi sửa cấu hình Dockerfile, các Agent instances khởi động thành công và API Health Check trả về HTTP 200.

Load Balancing được xác nhận thông qua header `X-Served-By`, với requests được phân phối đến hai Agent instances.

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → ghi nhận firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | AgentHighErrorRate | 4m 47s | Error rate: 20.63% theo Prometheus |
| B | `MOCK_SLOW_RATE=0.3` | AgentHighLatencyP95 | 3m 09s | Latency p95: 1.911 s theo Prometheus |
| C | `LLM_MODEL=mock-llm-large` | LLMCostBurnRateHigh | 2m 41s | Cost burn rate: $17.15/giờ |
| D | `docker pause` 1 instance | AgentInstanceDown | 2m 10s | Instances up giảm từ 2 xuống 1 |
| E | `AGENT_VERSION=v1` | Không có alert riêng về chất lượng | N/A | Agent version và Retrieval hit ratio |

Thời gian trong bảng được tính từ timestamp bắt đầu thí nghiệm đến timestamp lưu evidence khi alert ở trạng thái FIRING. Đây không phải thời điểm chuyển trạng thái chính xác của Prometheus.

Các chi phí LLM đều là chi phí mô phỏng, không phải chi phí thực tế.

**Evidence:**

| Experiment | Grafana | Prometheus |
|---|---|---|
| A | [High Error Rate](screenshots/CP8-observability/CP8-21-experiment-a-grafana-high-error-rate.png) | [Alert FIRING](screenshots/CP8-observability/CP8-22-experiment-a-prometheus-alert-firing.png) |
| B | [High Latency](screenshots/CP8-observability/CP8-24-experiment-b-grafana-high-latency.png) | [Alert FIRING](screenshots/CP8-observability/CP8-25-experiment-b-prometheus-alert-firing.png) |
| C | [High Cost](screenshots/CP8-observability/CP8-26-experiment-c-grafana-high-cost.png) | [Alert FIRING](screenshots/CP8-observability/CP8-27-experiment-c-prometheus-alert-firing.png) |
| D | [Instance Down](screenshots/CP8-observability/CP8-28-experiment-d-grafana-instance-down.png) | [Alert FIRING](screenshots/CP8-observability/CP8-29-experiment-d-prometheus-alert-firing.png) |
| E | [Quality Regression](screenshots/CP8-observability/CP8-30-experiment-e-grafana-quality-regression.png) | Không có rule riêng |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Trong Experiment E, Agent v1 vẫn phục vụ requests với hai instances đang hoạt động. Các cảnh báo liên quan đến error rate, latency và instance availability không được kích hoạt tại thời điểm quan sát.

Cost Alert từ thí nghiệm trước vẫn còn FIRING, nhưng không phải cảnh báo về chất lượng câu trả lời.

Kết quả Evaluation trong CP7 cho thấy Agent v1 chỉ đạt accuracy 4.3%, trong khi Agent v2 đạt 91.3% trước khi cải thiện Knowledge Base và 100% sau khi cải thiện.

Điều này chứng minh rằng hệ thống hoạt động ổn định về mặt hạ tầng không đồng nghĩa với việc AI trả lời chính xác.

Để phát hiện loại sự cố này trong production, mình sẽ sử dụng:

- Golden Dataset Evaluation định kỳ.
- Quality Gate trong CI/CD để ngăn triển khai phiên bản bị regression.
- Retrieval hit ratio và answer quality monitoring.
- Synthetic requests với câu hỏi và kết quả mong đợi.
- User feedback và Human-in-the-Loop review cho các trường hợp cần kiểm tra chất lượng.

### 4.3 Debug bằng trace

Trace chậm được lựa chọn từ Jaeger:

- `trace_id`: `e65009b6031618b3e301a36e3e6fb964`
- Tổng thời gian HTTP request: 1716.3 ms.
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1695.5 ms, khoảng 98.79%).
- Retrieval span: 18.3 ms theo Jaeger.
- HTTP status: 200.
- Input tokens: 83.
- Output tokens: 44.
- Simulated cost: $0.000039.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts":"2026-11-26T09:42:55.822549+00:00","level":"INFO","service":"observable-agent","instance":"bee1391bd8b2","event":"llm_call","trace_id":"e65009b6031618b3e301a36e3e6fb964","span_id":"3dfecc212851b35e","request_id":"6d8a69571c72","model":"mock-llm-small","agent_version":"v2","input_tokens":83,"output_tokens":44,"cost_usd":3.9e-05,"llm_ms":1695.5}
```

```json
{"ts":"2026-11-26T09:42:55.822961+00:00","level":"INFO","service":"observable-agent","instance":"bee1391bd8b2","event":"http_request","trace_id":"e65009b6031618b3e301a36e3e6fb964","span_id":"3dfecc212851b35e","request_id":"6d8a69571c72","method":"POST","route":"/ask","status":200,"ms":1716.3}
```

Kết quả cho thấy LLM call chiếm phần lớn thời gian xử lý request. Retrieval chỉ chiếm một phần nhỏ. Vì vậy, tối ưu retrieval sẽ không giải quyết được phần lớn latency của request cụ thể này.

Trace ID giúp liên kết distributed tracing với structured logging để xác định nguyên nhân của sự cố.

**Evidence:**

- [Jaeger slow trace](screenshots/CP8-observability/CP8-16-jaeger-slow-trace-detail.png)
- [LLM span detail](screenshots/CP8-observability/CP8-16b-jaeger-llm-span-detail.png)
- [Trace and log correlation](screenshots/CP8-observability/CP8-19-trace-log-correlation.png)
- [Structured log evidence](evidence/CP8/slow-trace-log-correlation.txt)

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 66.10 | 190 | 270 | 1700 | 61 |
| 3 | 65.64 | 190 | 220 | 1700 | 65 |

Các số liệu trong bảng được lấy từ dòng Aggregated trong Locust CSV reports.

**Điều kiện kiểm thử:**

| Parameter | Configuration |
|---|---|
| Virtual users | 100 |
| Spawn rate | 10 users/s |
| Duration | 120 seconds |
| Agent version | v2 |
| LLM model | mock-llm-small |
| Mock latency | 120 ms |
| Mock slow rate | 3% |
| Mock error rate | 1% |
| Load Balancer | Nginx |

**Kết quả bổ sung:**

| Metric | 1 instance | 3 instances |
|---|---|---|
| Total requests | 7899 | 7843 |
| Average latency | 220.97 ms | 214.48 ms |
| Aggregated error rate | 0.77% | 0.83% |
| `/ask` requests | 7222 | 7116 |
| `/ask` p95 latency | 290 ms | 230 ms |
| `/ask` error rate | 0.84% | 0.91% |
| `/ask` latency SLO | PASS | PASS |
| `/ask` error rate SLO | PASS | PASS |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Khi tăng số lượng Agent instances từ 1 lên 3, aggregated p95 latency giảm từ 270 ms xuống 220 ms, tương đương cải thiện khoảng 18.52%.

Throughput gần như không thay đổi, từ 66.10 xuống 65.64 requests/s. p99 vẫn duy trì ở 1700 ms do các request chậm bất thường được mô phỏng bởi Mock LLM.

Cả hai cấu hình đều đáp ứng SLO của API `/ask`, với p95 latency không vượt quá 500 ms và error rate không vượt quá 2%.

Một Agent instance có thể đã đáp ứng phần lớn workload hiện tại. Số lượng virtual users cố định, Locust wait time và Mock LLM latency có thể giới hạn throughput. Tuy nhiên, cần thêm profiling và saturation tests để xác định chính xác bottleneck của toàn hệ thống.

Scaling không tự động giải quyết tail latency hoặc lỗi upstream. Cần kết hợp horizontal scaling với việc tối ưu LLM latency, retry policy và timeout management.

**Lưu ý về quá trình kiểm thử:**

Lần chạy benchmark ban đầu với một instance gặp vấn đề do Docker Compose tự động khởi động thêm Agent dependency. Mình đã bổ sung tham số `--no-deps` vào lệnh `docker compose run` và thực hiện lại bài kiểm thử với đúng số lượng instances.

Locust có thể trả về exit code 1 khi phát hiện request thất bại. Kết quả SLO được đánh giá độc lập dựa trên latency và error rate thực tế.

**Evidence:**

- [Scaling 1 instance CSV](benchmark-results/scale_1_stats.csv)
- [Scaling 3 instances CSV](benchmark-results/scale_3_stats.csv)
- [Scaling 1 instance log](evidence/CP8/scaling-1-instance.txt)
- [Scaling 3 instances log](evidence/CP8/scaling-3-instances.txt)
- [Scaling 1 instance status](evidence/CP8/scaling-1-instance-status.txt)
- [Scaling 3 instances status](evidence/CP8/scaling-3-instances-status.txt)

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:

  1. **Benchmark cần đánh giá nhiều chỉ số.** Average latency không phản ánh đầy đủ trải nghiệm người dùng. p95, p99, throughput và error rate giúp phát hiện các vấn đề về tail latency, saturation và reliability.

  2. **Observability giúp xác định nguyên nhân sự cố.** Prometheus thu thập metrics, Grafana trực quan hóa dữ liệu, Jaeger theo dõi từng request và structured logs cung cấp thông tin chi tiết. Việc kết hợp ba trụ cột Metrics, Traces và Logs giúp quá trình troubleshooting hiệu quả hơn.

  3. **Chất lượng AI cần được kiểm soát độc lập với hạ tầng.** Một Agent có thể đáp ứng latency và availability SLO nhưng vẫn trả lời sai. Evaluation, Golden Dataset và Quality Gate là những thành phần quan trọng để ngăn quality regression.

- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

Mình sẽ bổ sung các metric và alert sau:

| Metric / Alert | Mục đích |
|---|---|
| Answer accuracy | Theo dõi chất lượng câu trả lời |
| Quality regression rate | Phát hiện phiên bản Agent bị giảm chất lượng |
| Cost per successful request | Đánh giá hiệu quả chi phí thay vì chỉ nhìn tổng chi phí |
| Upstream timeout rate | Phát hiện lỗi hoặc độ trễ từ LLM provider |
| Retry rate | Phát hiện tình trạng retry quá nhiều |
| Load Balancer 5xx rate | Phát hiện lỗi xảy ra ngoài Agent instances |
| CPU and memory utilization | Theo dõi mức sử dụng tài nguyên |
| Queue depth | Phát hiện backlog và saturation |
| Error budget burn rate | Cảnh báo nguy cơ vi phạm SLO |
| Retrieval quality | Phát hiện suy giảm chất lượng truy xuất dữ liệu |

Kết quả thực nghiệm cho thấy Agent v2 cải thiện accuracy từ 4.3% của v1 lên 100% trên Golden Dataset sau khi bổ sung Knowledge Base, không có regression. Các thí nghiệm Fault Injection đã xác nhận khả năng phát hiện lỗi, latency cao, chi phí cao và instance không phản hồi.

Scaling từ một lên ba instances cải thiện p95 latency, nhưng không làm throughput tăng đáng kể với workload hiện tại.

Các kết quả được xác nhận trong môi trường lab sử dụng Mock LLM và không đại diện cho hiệu năng hoặc chất lượng của một hệ thống AI production thực tế.