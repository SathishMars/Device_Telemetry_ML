# Monitoring Guide — Complete Metrics Reference
## Device Telemetry MLOps

---

## When to Use What

| Environment | Monitoring Tool | Why |
|-------------|----------------|-----|
| **Local development** | Prometheus + Grafana | Free, Docker-based, instant setup |
| **Azure production** | Azure Monitor + App Insights | Native integration, alerts to email/SMS/Teams |

Use Prometheus/Grafana locally. Switch to Azure Monitor when deployed to Azure.

---

## ALL 64 Metrics — Complete Reference

### A. API / Application Metrics (28 custom + 7 process = 35)

#### Request Metrics (5)

| # | Metric | Type | Labels | Local (Prometheus) | Azure (App Insights) |
|---|--------|------|--------|-------------------|---------------------|
| 1 | `predictions_total` | Counter | `problem_statement`, `risk_tier` | PromQL | `customMetrics` |
| 2 | `prediction_latency_seconds` | Histogram | `problem_statement` | PromQL (buckets: 10ms–5s) | `requests/duration` |
| 3 | `http_requests_total` | Counter | `method`, `endpoint`, `status` | PromQL | `requests/count` |
| 4 | `errors_total` | Counter | `error_type` | PromQL | `requests/failed` |
| 5 | `requests_in_progress` | Gauge | `problem_statement` | PromQL | `performanceCounters/requestsInQueue` |

#### Model Performance Metrics (6)

| # | Metric | Type | PS | Local (Prometheus) | Azure (App Insights) |
|---|--------|------|-----|-------------------|---------------------|
| 6 | `failure_probability_last` | Gauge | PS-1 | PromQL | `customMetrics` |
| 7 | `failure_probability_distribution` | Histogram | PS-1 | PromQL (buckets: 0.1–1.0) | `customMetrics` |
| 8 | `anomaly_rate_current` | Gauge | PS-4 | PromQL | `customMetrics` |
| 9 | `anomaly_score_distribution` | Histogram | PS-4 | PromQL (buckets: -0.5–0.5) | `customMetrics` |
| 10 | `sla_risk_score_distribution` | Histogram | PS-5 | PromQL (buckets: 10–100) | `customMetrics` |
| 11 | `rul_estimate_days_distribution` | Histogram | PS-5 | PromQL (buckets: 7–90 days) | `customMetrics` |

#### Risk & Business Metrics (4)

| # | Metric | Type | Local (Prometheus) | Azure (App Insights) |
|---|--------|------|-------------------|---------------------|
| 12 | `risk_tier_total` | Counter (`tier` label) | PromQL | `customMetrics` |
| 13 | `devices_at_risk` | Gauge | PromQL | `customMetrics` |
| 14 | `mean_health_score` | Gauge | PromQL | `customMetrics` |
| 15 | `sla_breach_probability_avg` | Gauge | PromQL | `customMetrics` |

#### System & Model Metrics (3)

| # | Metric | Type | Local (Prometheus) | Azure (App Insights) |
|---|--------|------|-------------------|---------------------|
| 16 | `model_loaded` | Gauge (`problem_statement` label) | PromQL | `customMetrics` |
| 17 | `model_load_time_seconds` | Gauge | PromQL | `customMetrics` |
| 18 | `feature_count` | Gauge | PromQL | `customMetrics` |

#### Data & Drift Metrics (3)

| # | Metric | Type | Local (Prometheus) | Azure (App Insights) |
|---|--------|------|-------------------|---------------------|
| 19 | `drift_share_current` | Gauge (0.0–1.0) | PromQL | `customMetrics` |
| 20 | `data_quality_pass_rate` | Gauge (0–100%) | PromQL | `customMetrics` |
| 21 | `retraining_triggered_total` | Counter | PromQL | `customEvents` |

#### Process Metrics (7, auto-generated)

| # | Metric | Type | Local (Prometheus) | Azure (App Insights) |
|---|--------|------|-------------------|---------------------|
| 22 | `process_virtual_memory_bytes` | Gauge | PromQL | `performanceCounters/processPrivateBytes` |
| 23 | `process_resident_memory_bytes` | Gauge | PromQL | `performanceCounters/processPrivateBytes` |
| 24 | `process_cpu_seconds_total` | Counter | PromQL | `performanceCounters/processCpuPercentage` |
| 25 | `process_open_fds` | Gauge | PromQL | N/A |
| 26 | `process_start_time_seconds` | Gauge | PromQL | N/A |
| 27 | `python_gc_objects_collected_total` | Counter | PromQL | N/A |
| 28 | `python_info` | Gauge | PromQL | N/A |

---

### B. Azure Monitor Additional Metrics (Azure only, auto-collected)

| # | Metric | Source | What it captures |
|---|--------|--------|-----------------|
| 29 | `requests/count` | App Insights | Total HTTP requests |
| 30 | `requests/duration` | App Insights | Request latency P50/P95/P99 |
| 31 | `requests/failed` | App Insights | Failed requests (4xx/5xx) |
| 32 | `exceptions/count` | App Insights | Unhandled exceptions |
| 33 | `dependencies/duration` | App Insights | External call latency (DB, storage) |
| 34 | `dependencies/failed` | App Insights | Failed external calls |
| 35 | `availabilityResults/availabilityPercentage` | Availability test | Uptime % (ping test every 5 min) |
| 36 | `performanceCounters/processCpuPercentage` | Container | CPU usage % |
| 37 | `performanceCounters/processPrivateBytes` | Container | Memory usage |
| 38 | `performanceCounters/requestsPerSecond` | Container | Throughput |
| 39 | `browserTimings/totalDuration` | React Dashboard | Frontend page load time |
| 40 | `pageViews/count` | React Dashboard | Which dashboard tabs are viewed |

---

### C. Azure Infrastructure Metrics (Azure only)

| # | Metric | Source | What it captures |
|---|--------|--------|-----------------|
| 41 | Container App CPU utilization | Azure Monitor | Container CPU % |
| 42 | Container App Memory utilization | Azure Monitor | Container RAM MB |
| 43 | Container App Replica count | Azure Monitor | Auto-scaling replicas |
| 44 | Container App Request count | Azure Monitor | Ingress requests |
| 45 | Container App Response latency | Azure Monitor | Ingress latency |
| 46 | Storage Account transactions | Azure Monitor | Data Lake read/writes |
| 47 | Storage Account ingress/egress | Azure Monitor | Data transfer GB |
| 48 | Databricks cluster utilization | Azure Monitor | Cluster CPU/memory |
| 49 | Key Vault operations | Azure Monitor | Secret access count |
| 50 | Budget consumption | Cost Management | $ spent vs budget |

---

### D. ML-Specific Metrics (MLflow / Azure ML / Databricks)

| # | Metric | PS | Source | What it captures |
|---|--------|-----|--------|-----------------|
| 51 | AUC / F1 / Precision / Recall | PS-1 | MLflow | Model quality per retrain |
| 52 | Feature importance (top 10) | PS-1 | MLflow | Which features drive predictions |
| 53 | Association rules count | PS-2 | MLflow | Error pattern complexity |
| 54 | Markov transition probabilities | PS-2 | MLflow | Error sequence behavior |
| 55 | SHAP values (global) | PS-3 | MLflow | Causal feature importance |
| 56 | Anomaly rate % | PS-4 | MLflow | Fleet anomaly prevalence |
| 57 | SPC violations count | PS-4 | MLflow | Control chart breaches |
| 58 | Weibull lambda/rho | PS-5 | MLflow | Fleet reliability parameters |
| 59 | Cox concordance index | PS-5 | MLflow | Survival model accuracy |
| 60 | Mean RUL days | PS-5 | MLflow | Fleet-wide remaining life |
| 61 | Training data size | Pipeline | MLflow | Records used in training |
| 62 | Training duration | Pipeline | MLflow | How long retraining took |
| 63 | Champion model version | Pipeline | MLflow | Which model is in Production |
| 64 | Drift share % | Pipeline | MLflow | Feature distribution shift |

---

## Grafana Dashboards (Local Development)

### Dashboard 1: Operations Overview

| Panel | PromQL Query | Visualization | Why |
|-------|-------------|---------------|-----|
| Predictions/min | `rate(predictions_total[1m]) * 60` | Time series | Traffic volume |
| Error Rate % | `rate(errors_total[5m]) / rate(http_requests_total[5m]) * 100` | Time series + threshold | Service health |
| P50/P95/P99 Latency | `histogram_quantile(0.99, rate(prediction_latency_seconds_bucket[5m])) * 1000` | Multi-line | Performance |
| Requests In Progress | `requests_in_progress` | Gauge | Load |
| Uptime | `time() - process_start_time_seconds` | Stat | Reliability |
| Memory Usage | `process_resident_memory_bytes / 1024 / 1024` | Gauge (MB) | Resources |

### Dashboard 2: Model Performance

| Panel | PromQL Query | Visualization | Why |
|-------|-------------|---------------|-----|
| Failure Prob Distribution | `histogram_quantile(0.5, failure_probability_distribution_bucket)` | Heatmap | Model confidence |
| Anomaly Score Distribution | `anomaly_score_distribution_bucket` | Histogram | Threshold clustering |
| SLA Risk Distribution | `sla_risk_score_distribution_bucket` | Histogram | Risk spread |
| Risk Tier Breakdown | `risk_tier_total` | Pie chart | CRITICAL vs LOW ratio |
| Mean Health Score | `mean_health_score` | Gauge (0-100) | Fleet health trend |
| Failure Prob Trend | `failure_probability_last` | Time series | Latest predictions |

### Dashboard 3: SLA & Reliability

| Panel | PromQL Query | Visualization | Why |
|-------|-------------|---------------|-----|
| Devices At Risk | `devices_at_risk` | Stat (red) | Immediate attention |
| SLA Breach Probability | `sla_breach_probability_avg` | Gauge (0-1) | SLA violation likelihood |
| RUL Distribution | `rul_estimate_days_distribution_bucket` | Bar chart | Devices with <14 days left |
| CRITICAL Predictions/hr | `rate(risk_tier_total{tier="CRITICAL"}[1h]) * 3600` | Time series | Alert trend |
| Predictions by PS | `sum by(problem_statement)(predictions_total)` | Bar chart | PS usage |

### Dashboard 4: Data Quality & Drift

| Panel | PromQL Query | Visualization | Why |
|-------|-------------|---------------|-----|
| Drift Share | `drift_share_current * 100` | Gauge (red >30%) | Retrain needed? |
| Data Quality Pass Rate | `data_quality_pass_rate` | Gauge (0-100%) | Quality gates |
| Retraining Count | `retraining_triggered_total` | Stat | Retrain frequency |
| Models Loaded | `model_loaded` | Table | Active models |

### Grafana Alert Rules

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High Error Rate | `rate(errors_total[5m]) > 0.1` | Critical | Page on-call |
| High Latency | `histogram_quantile(0.99, ...) > 1.0` | Warning | Scale up |
| Drift Detected | `drift_share_current > 0.30` | Warning | Trigger retrain |
| Quality Degraded | `data_quality_pass_rate < 90` | Warning | Check pipeline |
| Critical Devices | `devices_at_risk > 20` | Critical | Alert maintenance |
| Model Not Loaded | `model_loaded == 0` | Critical | Restart API |
| High Memory | `process_resident_memory_bytes > 2e9` | Warning | Investigate leak |

### Setting Up Grafana

```powershell
# Start Prometheus + Grafana
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\monitoring
docker compose up -d
```

1. Open http://localhost:3000 → Login: `admin` / `admin`
2. **Connections** → **Data Sources** → **Add Prometheus** → URL: `http://prometheus:9090` → **Save & Test**
3. **+** → **New Dashboard** → **Add Visualization** → Enter PromQL → Choose chart type

---

## Azure App Insights (Azure Production)

### Setup

```powershell
pip install opencensus-ext-azure opencensus-ext-fastapi
```

Add to `api/main.py`:

```python
import os
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.trace.samplers import ProbabilitySampler
import logging

APPINSIGHTS_CONNECTION = os.getenv(
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "InstrumentationKey=your-key-here"
)

# Auto-collect request traces
from opencensus.ext.fastapi.fastapi_middleware import FastAPIMiddleware
app.add_middleware(
    FastAPIMiddleware,
    exporter=AzureExporter(connection_string=APPINSIGHTS_CONNECTION),
    sampler=ProbabilitySampler(rate=1.0)
)

# Send logs to App Insights
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(connection_string=APPINSIGHTS_CONNECTION))

# Custom metrics (equivalent to Prometheus counters/gauges)
from opencensus.ext.azure import metrics_exporter
from opencensus.stats import aggregation, measure, stats, view

failure_prob_measure = measure.MeasureFloat("failure_probability", "Failure prob", "prob")
failure_prob_view = view.View(
    "failure_probability_distribution", "Distribution of failure probabilities",
    [], failure_prob_measure,
    aggregation.DistributionAggregation([0.1, 0.2, 0.3, 0.5, 0.7, 0.9])
)
stats.stats.view_manager.register_view(failure_prob_view)

# Record a metric
mmap = stats.stats.stats_recorder.new_measurement_map()
mmap.measure_float_put(failure_prob_measure, prob)
mmap.record()
```

### KQL Queries (Azure Portal → App Insights → Logs)

#### Request Metrics

```kusto
// Predictions per minute
requests
| where name contains "predict"
| summarize count() by bin(timestamp, 1m)
| render timechart

// P50, P95, P99 latency
requests
| where name contains "predict"
| summarize p50=percentile(duration,50), p95=percentile(duration,95), p99=percentile(duration,99)
  by bin(timestamp, 5m)
| render timechart

// Error rate by endpoint
requests
| where timestamp > ago(1h)
| summarize total=count(), failed=countif(success == false) by name
| extend error_rate = round(todouble(failed) / total * 100, 2)
| order by error_rate desc

// Slowest endpoints
requests
| where timestamp > ago(1h)
| summarize avg_duration=avg(duration), p99=percentile(duration, 99) by name
| order by p99 desc
```

#### Model Performance

```kusto
// Failure probability distribution
customMetrics
| where name == "failure_probability"
| summarize avg(value), percentile(value, 95) by bin(timestamp, 5m)
| render timechart

// Risk tier breakdown
customMetrics
| where name == "risk_tier_count"
| extend tier = tostring(customDimensions["tier"])
| summarize count() by tier
| render piechart

// SLA risk score trend
customMetrics
| where name == "sla_risk_score"
| summarize avg(value), max(value) by bin(timestamp, 1h)
| render timechart

// Anomaly detection rate
customMetrics
| where name == "anomaly_detected"
| summarize anomalies=countif(value == 1), total=count() by bin(timestamp, 1h)
| extend rate = round(todouble(anomalies) / total * 100, 2)
| render timechart
```

#### Drift & Quality

```kusto
// Data drift trend
customMetrics
| where name == "drift_share"
| project timestamp, drift_pct = value * 100
| render timechart

// Data quality trend
customMetrics
| where name == "data_quality_pass_rate"
| render timechart

// Retraining events
customEvents
| where name == "model_retrained"
| project timestamp, reason = tostring(customDimensions["reason"])
```

#### System Health

```kusto
// API availability
availabilityResults
| summarize availability = avg(success) * 100 by bin(timestamp, 1h)
| render timechart

// Exceptions
exceptions
| where timestamp > ago(24h)
| summarize count() by type, bin(timestamp, 1h)
| render timechart

// Dependencies (external calls)
dependencies
| where timestamp > ago(1h)
| summarize avg(duration), count() by name
| order by count_ desc
```

### Azure Alert Rules

Set up in Azure Portal → App Insights → Alerts → New Alert Rule:

| Alert | KQL Condition | Severity | Action |
|-------|--------------|----------|--------|
| High Error Rate | `requests \| where success == false \| count > 10` (per 5 min) | Sev 1 | Email + Teams |
| High Latency | `requests \| percentile(duration, 99) > 1000` | Sev 2 | Email |
| Model Drift | `customMetrics \| where name == "drift_share" and value > 0.30` | Sev 2 | Trigger retrain |
| Critical Devices | `customMetrics \| where name == "devices_at_risk" and value > 20` | Sev 1 | Page on-call |
| API Down | `availabilityResults \| avg(success) < 0.95` | Sev 0 | SMS + Email |

---

## Azure ML vs Databricks — Where Monitoring Lives

| Monitoring aspect | Azure Databricks | Azure ML |
|-------------------|-----------------|----------|
| **MLflow experiments** | Built-in (auto-tracked) | Supported (manual setup) |
| **Model Registry** | Unity Catalog | Azure ML Registry |
| **Training metrics** | MLflow (metrics 51-64) | Azure ML metrics |
| **Data pipeline health** | Databricks Workflows dashboard | Azure Data Factory Monitor |
| **Cluster utilization** | Ganglia metrics (built-in) | N/A |
| **Cost monitoring** | Azure Cost Management | Azure Cost Management |
| **Recommendation** | **Use for data + training** | Use for serving + endpoints |

### Databricks-Specific Monitoring

In Databricks, these additional metrics are available via the Workflows dashboard:

| Metric | Where to find | What it shows |
|--------|--------------|---------------|
| Job run duration | Workflows → Job runs | How long daily pipeline takes |
| Job success/failure | Workflows → Job runs | Pipeline reliability |
| Cluster utilization | Compute → Cluster details | CPU/memory during training |
| Notebook cell duration | Notebook run output | Bottleneck identification |
| MLflow experiment metrics | MLflow UI (built-in) | All 64 ML metrics above |
| Unity Catalog model versions | Catalog → Models | Champion/Challenger history |
| Feature Store freshness | Feature Store UI | When features last updated |

---

## Prometheus vs Azure App Insights — Side by Side

| Aspect | Prometheus + Grafana | Azure App Insights |
|--------|---------------------|-------------------|
| **Best for** | Local dev, Docker | Azure production |
| **Cost** | Free (self-hosted) | ~$2.30/GB ingested |
| **Setup** | `docker compose up -d` (5 min) | Azure resource + SDK (15 min) |
| **Dashboards** | Grafana (highly customizable) | Azure Portal (integrated) |
| **Alerting** | Grafana alerts (webhook, email) | Azure Monitor (SMS, email, Teams, webhook) |
| **Retention** | Configurable (default 30d) | 90 days (up to 730d) |
| **Distributed tracing** | Needs Jaeger/Zipkin | Built-in |
| **Log correlation** | Manual | Automatic (request → logs → exceptions) |
| **Custom metrics** | `prometheus_client` Python lib | `opencensus` Python lib |
| **Query language** | PromQL | KQL (Kusto) |
| **Infra metrics** | Not included | Auto-collected (CPU, memory, requests) |
| **Total metrics** | 28 custom + 7 process = 35 | 35 custom + 12 auto + 10 infra = 57 |
