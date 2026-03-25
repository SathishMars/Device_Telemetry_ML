# Device Telemetry MLOps - How to Run Guide
## London Metro Contactless Reader Monitoring System

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│              DEVICE TELEMETRY MLOPS PIPELINE                             │
│              London Metro Reader Monitoring                              │
└──────────────────────────────────────────────────────────────────────────┘

DATA SOURCES (CSV → simulates IoT streams)
├── devices.csv        (200 reader devices)
├── telemetry.csv      (6,000 daily readings, 30 days)
├── error_logs.csv     (~1,500 error events)
└── maintenance.csv    (~400 SLA records)

MEDALLION ARCHITECTURE
├── Bronze Layer → Raw Parquet (immutable, partitioned by date)
├── Silver Layer → Cleaned, typed, deduplicated
└── Gold Layer   → 80+ engineered features (rolling, delta, composite)

FEATURE STORE → Versioned, PS-specific feature tables

5 PROBLEM STATEMENTS (ML)
├── PS-1: Failure Prediction      → RF, XGBoost, CatBoost
├── PS-2: Error Pattern Recognition → Association Rules (Apriori), Markov Chain
├── PS-3: Root Cause Analysis     → SHAP, Causal Inference (DoWhy)
├── PS-4: Anomaly Detection       → Isolation Forest, SPC Control Charts
└── PS-5: SLA Risk Prediction     → Weibull, Cox PH, Remaining Useful Life

MLOPS
├── MLflow    → Experiment tracking, model registry (Champion/Challenger)
├── Evidently → Data drift detection, quality reports (HTML)
├── Great Expectations → Data validation at each layer
└── Incremental Pipeline → Day-wise near real-time processing

SERVING & MONITORING
├── FastAPI      → /predict/failure, /predict/anomaly, /predict/sla-risk
├── React UI     → Dashboard displaying all 5 PS outputs
├── Prometheus   → Metrics scraping (predictions, latency, errors)
├── Grafana      → Dashboards and alerts
└── Docker       → Containerized deployment (Blue-Green / Canary ready)
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm (for React dashboard)
- Docker & Docker Compose (for monitoring stack)
- ~2 GB disk space

---

## Environment Setup (Virtual Environment)

### Create and Activate venv

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops

# Create virtual environment
python -m venv venv

# Activate venv (PowerShell)
venv\Scripts\Activate.ps1

# Activate venv (CMD)
venv\Scripts\activate

# Activate venv (Git Bash / Linux / macOS)
source venv/Scripts/activate    # Windows Git Bash
source venv/bin/activate        # Linux / macOS
```

You should see `(venv)` in your terminal prompt when activated.

### Install Dependencies

```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Install all Python dependencies
pip install -r requirements.txt
```

### Install React Dashboard Dependencies

```powershell
cd dashboard
npm install
cd ..
```

### Deactivate venv (when done)

```powershell
deactivate
```

> **Note:** Always activate the venv before running any pipeline commands.
> All commands below assume the venv is active — look for `(venv)` in your prompt.

---

## Full Pipeline Execution (Recommended)

The full pipeline runs all 13 steps automatically:

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
python run_pipeline.py
```

**Pipeline Steps:**

| Step | Description | Script |
|------|-------------|--------|
| 1 | Generate sample data (200 devices, 30 days) | `data/generate_sample_data.py` |
| 2 | Bronze Layer (raw CSV → Parquet) | `notebooks/01_bronze_layer.py` |
| 3 | Silver Layer (clean, deduplicate, type cast) | `notebooks/02_silver_layer.py` |
| 4 | Gold Layer (80+ engineered features) | `notebooks/03_gold_layer.py` |
| 5 | Feature Store (versioned, PS-specific) | `notebooks/04_feature_store.py` |
| 6 | PS-1: Failure Prediction (RF, XGBoost, CatBoost) | `notebooks/05_ps1_failure_prediction.py` |
| 7 | PS-2: Error Patterns (Apriori, Markov) | `notebooks/06_ps2_error_pattern.py` |
| 8 | PS-3: Root Cause (SHAP, Causal Inference) | `notebooks/07_ps3_root_cause.py` |
| 9 | PS-4: Anomaly Detection (Isolation Forest, SPC) | `notebooks/08_ps4_anomaly_detection.py` |
| 10 | PS-5: SLA Risk (Weibull, Cox PH, RUL) | `notebooks/09_ps5_sla_risk.py` |
| 11 | Register Models in MLflow Registry | `scripts/register_models.py` |
| 12 | Drift Detection (Evidently AI) | `notebooks/10_drift_detection.py` |
| 13 | Data Quality (Great Expectations) | `scripts/run_data_quality.py` |

**Pipeline options:**
```powershell
python run_pipeline.py              # Full pipeline (all 13 steps)
python run_pipeline.py --ps 1       # Run only PS-1
python run_pipeline.py --skip-data  # Skip data generation (steps 1-5)
python run_pipeline.py --skip-ml    # Skip ML training (steps 6-10)
```

---

## Step-by-Step Execution

### Step 1: Generate Sample Data
```powershell
python data/generate_sample_data.py
```
**Output:** 4 CSV files in `data/raw/`
- `devices.csv` — 200 metro reader devices
- `telemetry.csv` — 6,000 records (200 devices x 30 days)
- `error_logs.csv` — ~1,500 error events
- `maintenance.csv` — ~400 maintenance/SLA records

### Step 2-5: Data Pipeline (Bronze → Silver → Gold → Feature Store)
```powershell
python notebooks/01_bronze_layer.py      # Raw CSV → Parquet (date-partitioned)
python notebooks/02_silver_layer.py      # Cleaning, dedup, range validation
python notebooks/03_gold_layer.py        # 80+ features (rolling, delta, composite)
python notebooks/04_feature_store.py     # Versioned feature tables + schema
```

### Step 6: PS-1 — Failure Prediction
```powershell
python notebooks/05_ps1_failure_prediction.py
```
- **Models:** Random Forest, XGBoost, CatBoost
- **Target:** `failure_next_3d` (will device fail in next 3 days?)
- **Output:** Champion model (.pkl), ROC curves, confusion matrices
- **MLflow Experiment:** `PS1_Failure_Prediction` (3 runs)

### Step 7: PS-2 — Error Pattern Recognition
```powershell
python notebooks/06_ps2_error_pattern.py
```
- **Apriori:** Finds co-occurring error patterns (e.g., NFC_TIMEOUT + NETWORK_LOSS)
- **Markov Chain:** Models error sequence transitions and stationary distribution
- **Output:** Association rules, transition matrix, severity escalations

### Step 8: PS-3 — Root Cause Analysis
```powershell
python notebooks/07_ps3_root_cause.py
```
- **SHAP (TreeExplainer):** Global & local feature importance for failures
- **Causal Inference (DoWhy):** Estimates causal effect of features on failure
- **Output:** SHAP summary/bar/dependence plots, causal analysis results

### Step 9: PS-4 — Anomaly Detection
```powershell
python notebooks/08_ps4_anomaly_detection.py
```
- **Isolation Forest:** Unsupervised anomaly detection (8% contamination)
- **SPC Control Charts:** 3-sigma control limits per telemetry feature
- **Output:** Anomaly labels, control charts, device anomaly summary

### Step 10: PS-5 — SLA Risk Prediction
```powershell
python notebooks/09_ps5_sla_risk.py
```
- **Weibull Distribution:** Time-to-failure modeling (shape/scale)
- **Cox Proportional Hazards:** Survival analysis with device covariates
- **RUL Estimation:** Remaining Useful Life per device
- **Output:** Survival curves, hazard ratios, RUL estimates, SLA risk scores

### Step 11: Register Models
```powershell
python scripts/register_models.py
```
Registers champion models in MLflow Model Registry:
- **`device_failure_predictor`** (PS-1 XGBoost) → Stage: Production
- **`device_anomaly_detector`** (PS-4 Isolation Forest) → Stage: Production

### Step 12: Drift Detection
```powershell
python notebooks/10_drift_detection.py
```
**Output:** `data/drift_reports/*.html` (interactive Evidently AI reports)

### Step 13: Data Quality
```powershell
python scripts/run_data_quality.py
```
**Output:** `data/quality_reports/quality_report.csv`

---

## Incremental Daily Processing

Simulates near real-time processing, one day at a time:

```powershell
python scripts/run_incremental_daily.py
```

Processes each of the 30 days incrementally:
- Bronze ingestion for that day
- Silver cleaning
- Quality check
- Daily statistics and anomaly flagging

---

## MLflow UI

View all experiments, metrics, model artifacts, and registered models:

```powershell
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000
```
**Open:** http://localhost:5000

### Experiments

| Experiment | Runs | Description |
|------------|------|-------------|
| PS1_Failure_Prediction | 3+ | RF, XGBoost, CatBoost + Champion registered |
| PS2_Error_Pattern_Recognition | 1+ | Apriori rules, Markov transitions |
| PS3_Root_Cause_Analysis | 1+ | SHAP values, causal effects |
| PS4_Anomaly_Detection | 1+ | Isolation Forest, SPC results |
| PS5_SLA_Risk_Prediction | 1+ | Weibull, Cox PH, RUL estimates |
| Drift_Detection | 1 | Evidently AI drift results |

### Navigating MLflow UI

1. **Experiments tab** (left sidebar) → Click an experiment → See all runs
2. **Click a run name** → See **Parameters**, **Metrics**, and **Artifacts** (plots, CSVs, models)
3. **Models tab** (top nav) → See registered models with version history and stage (Staging/Production)
4. Inside a run's **Artifacts** → Click any `.png` to view plots directly in the browser

### Champion vs Challenger Model Strategy

| Aspect | Champion | Challenger |
|--------|----------|------------|
| Definition | Current best model in Production | New candidate model being evaluated |
| MLflow Stage | `Production` | `Staging` |
| Traffic | 100% (or majority via Blue-Green) | 0% (or small % via Canary) |
| Example | XGBoost (AUC=0.964) | CatBoost / RF |
| Promotion | Current best | Promoted if outperforms on next retrain |

> **Note:** This is a local MLflow setup using SQLite. It is **not** Unity Catalog
> (which is a Databricks-managed feature). The local MLflow Model Registry provides
> equivalent functionality: model versioning, stage transitions (None → Staging → Production),
> and artifact storage. To use Unity Catalog, deploy on Databricks with
> `mlflow.set_registry_uri("databricks-uc")`.

---

## API Server

### Starting the API

**Important:** Kill any existing process on port 8000 before starting:

```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000 | findstr LISTENING

# Kill old process (replace <PID> with the number from above)
taskkill /F /PID <PID>

# Start the API
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Open:** http://localhost:8000/docs (Swagger UI — test endpoints in browser)

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |
| `/model/info` | GET | Model metadata |
| `/predict/failure` | POST | PS-1: Failure prediction |
| `/predict/anomaly` | POST | PS-4: Anomaly detection |
| `/predict/sla-risk` | POST | PS-5: SLA risk score |
| `/predict/failure/batch` | POST | Batch predictions |
| `/dashboard/summary` | GET | All PS summary (for React UI) |
| `/dashboard/ps1` to `/dashboard/ps5` | GET | Per-PS details (for React UI) |

### Sample API Calls (PowerShell)

```powershell
# PS-1: Failure Prediction
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/failure" -ContentType "application/json" -Body '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'

# PS-4: Anomaly Detection
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/anomaly" -ContentType "application/json" -Body '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'

# PS-5: SLA Risk
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/sla-risk" -ContentType "application/json" -Body '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'

# Health Check
Invoke-RestMethod -Uri "http://localhost:8000/health"

# Swagger UI (interactive API testing)
start http://localhost:8000/docs
```

### Sample API Calls (Git Bash / Linux / macOS)

```bash
curl -X POST http://localhost:8000/predict/failure \
  -H "Content-Type: application/json" \
  -d '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'
```

> **Tip:** Use the Swagger UI at http://localhost:8000/docs to test all endpoints interactively in your browser.

### Load Testing

```powershell
python scripts/generate_traffic.py --rps 5 --duration 120
```

---

## React Dashboard

A React-based UI dashboard that displays outputs from all 5 problem statements with interactive charts and tables.

### Setup (one-time)

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\dashboard
npm install
```

### Running the Dashboard

You need **two terminals** running simultaneously:

**Terminal 1 — Start the API:**
```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```
Wait for: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 — Start the React dashboard:**
```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\dashboard
npm run dev
```
Wait for: `Local: http://localhost:5173/`

**Open:** http://localhost:5173

### Dashboard Tabs

| Tab | Content |
|-----|---------|
| **Overview** | KPI cards for all 5 PS, risk distribution pie chart, SPC violations bar chart |
| **PS-1: Failure Prediction** | Champion model metrics (AUC, F1, Precision, Recall), Champion vs Challenger table |
| **PS-2: Error Patterns** | Association rules table (Apriori), Markov transition probabilities, severity escalation paths, stationary distribution |
| **PS-3: Root Cause** | SHAP feature importance bar chart, causal inference results table, local explanation for sample device |
| **PS-4: Anomaly Detection** | Anomaly vs normal feature difference chart, SPC control limits table, top anomalous devices |
| **PS-5: SLA Risk** | RUL distribution histogram, risk tier pie chart, per-device RUL estimates, Cox PH hazard ratios, SLA risk scores |

### Troubleshooting Dashboard

| Issue | Solution |
|-------|----------|
| "Connection Error" | API is not running. Start it in Terminal 1 first |
| Port 8000 already in use | Run `netstat -ano \| findstr :8000` then `taskkill /F /PID <PID>` |
| Dashboard loads but no data | Restart the API (`Ctrl+C` then re-run `python -m uvicorn api.main:app ...`) |

---

## Viewing Drift & Quality Reports (HTML)

After running drift detection, interactive HTML reports are generated:

```powershell
# Data Drift — Production data
start data/drift_reports/data_drift_no_drift.html

# Data Drift — Simulated (demonstrates retraining trigger)
start data/drift_reports/data_drift_simulated_drift.html

# Data Quality — Summary statistics
start data/drift_reports/data_quality_no_drift.html

# Drift Decision (JSON)
type data\drift_reports\drift_decision.json

# Quality Validation Summary
type data\quality_reports\quality_summary.json
```

> On macOS use `open` instead of `start`. On Linux use `xdg-open`.

| Report | Contents |
|--------|----------|
| `data_drift_no_drift.html` | Per-feature KS test p-values, drift share %, distribution plots |
| `data_drift_simulated_drift.html` | Same with artificial drift — shows how retraining is triggered |
| `data_quality_no_drift.html` | Missing values, duplicates, feature statistics |
| `drift_decision.json` | Machine-readable retraining decision (threshold: 30%) |

---

## Docker Deployment

### Build & Run API Container

```powershell
docker build -f api/Dockerfile -t telemetry-api:v1 .
docker run -d --name telemetry-api -p 8000:8000 telemetry-api:v1
```

### Full Monitoring Stack (Prometheus + Grafana + API)

```powershell
cd monitoring
docker compose up -d
```

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8000 | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin |

### Blue-Green Deployment

Zero-downtime model updates:

```powershell
cd monitoring
docker compose -f docker-compose.blue-green.yml up -d
```

```
Blue  (current stable)  ← 100% traffic ─┐
                                          ├── Nginx (port 80)
Green (new version)     ←   0% traffic ──┘
```

**Switch traffic:** Edit `nginx.conf` weights → `docker exec nginx-router nginx -s reload`

### Canary Deployment

Gradual rollout (same infrastructure as Blue-Green):

```
Stage 1:  Blue 95%  | Green  5%   (monitor 24h)
Stage 2:  Blue 80%  | Green 20%   (monitor 24h)
Stage 3:  Blue 50%  | Green 50%   (monitor 24h)
Stage 4:  Blue  0%  | Green 100%  (full promotion)
```

### When to Use What

| Scenario | Strategy |
|----------|----------|
| Development / testing | **Full Monitoring Stack** — just need observability |
| Routine model update | **Blue-Green** — instant switch, rollback in <30s |
| Major model change | **Canary** — gradual rollout, monitor at each stage |

---

## Prometheus Metrics

Key metrics exposed at `GET /metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `predictions_total` | Counter | Total predictions by PS and risk tier |
| `prediction_latency_seconds` | Histogram | Prediction latency |
| `failure_probability_last` | Gauge | Last failure probability |
| `anomaly_rate_current` | Gauge | Current anomaly rate |
| `http_requests_total` | Counter | HTTP requests by method/endpoint |
| `errors_total` | Counter | API errors by type |
| `model_loaded` | Gauge | Model load status |

### Grafana Dashboard Queries

```promql
rate(predictions_total[1m]) * 60                                        # Predictions/min
histogram_quantile(0.99, prediction_latency_seconds_bucket) * 1000      # P99 latency (ms)
rate(errors_total[5m])                                                   # Error rate
predictions_total{risk_tier="CRITICAL"} / predictions_total              # Critical rate
```

---

## Running Tests

```powershell
pytest tests/test_api.py -v
```

---

## Project Structure

```
device_telemetry_mlops/
├── data/
│   ├── generate_sample_data.py       # Synthetic data generator
│   ├── raw/                           # CSV source files
│   ├── bronze/                        # Raw Parquet (immutable)
│   ├── silver/                        # Cleaned Parquet
│   ├── gold/                          # Feature-engineered dataset
│   ├── feature_store/                 # Versioned features + schema
│   ├── artifacts/                     # Model files, plots, metrics
│   │   ├── ps1/                       # Failure prediction artifacts
│   │   ├── ps2/                       # Error pattern artifacts
│   │   ├── ps3/                       # Root cause artifacts
│   │   ├── ps4/                       # Anomaly detection artifacts
│   │   └── ps5/                       # SLA risk artifacts
│   ├── drift_reports/                 # Evidently AI HTML reports
│   └── quality_reports/               # Great Expectations results
├── notebooks/
│   ├── 01_bronze_layer.py             # Raw ingestion
│   ├── 02_silver_layer.py             # Data cleaning
│   ├── 03_gold_layer.py               # Feature engineering
│   ├── 04_feature_store.py            # Feature store creation
│   ├── 05_ps1_failure_prediction.py   # RF, XGBoost, CatBoost
│   ├── 06_ps2_error_pattern.py        # Apriori, Markov
│   ├── 07_ps3_root_cause.py           # SHAP, Causal Inference
│   ├── 08_ps4_anomaly_detection.py    # Isolation Forest, SPC
│   ├── 09_ps5_sla_risk.py             # Weibull, Cox, RUL
│   └── 10_drift_detection.py          # Evidently AI
├── scripts/
│   ├── run_end_to_end.py              # Master orchestrator
│   ├── run_data_quality.py            # Great Expectations
│   ├── run_incremental_daily.py       # Day-wise incremental pipeline
│   ├── register_models.py             # MLflow model registration
│   └── generate_traffic.py            # Load testing
├── api/
│   ├── main.py                        # FastAPI service + dashboard endpoints
│   └── Dockerfile                     # Container image
├── dashboard/                         # React UI dashboard
│   ├── src/
│   │   ├── App.jsx                    # Main app with tabs
│   │   ├── App.css                    # Dark theme styles
│   │   └── components/
│   │       ├── Summary.jsx            # Overview KPI cards + charts
│   │       ├── PS1Panel.jsx           # Failure Prediction panel
│   │       ├── PS2Panel.jsx           # Error Patterns panel
│   │       ├── PS3Panel.jsx           # Root Cause panel
│   │       ├── PS4Panel.jsx           # Anomaly Detection panel
│   │       └── PS5Panel.jsx           # SLA Risk panel
│   ├── package.json
│   └── vite.config.js
├── monitoring/
│   ├── docker-compose.yml             # Prometheus + Grafana stack
│   ├── docker-compose.blue-green.yml  # Blue-Green deployment
│   ├── prometheus.yml                 # Prometheus config
│   └── nginx.conf                     # Traffic routing
├── tests/
│   └── test_api.py                    # API tests
├── mlruns/                            # MLflow tracking database
├── run_pipeline.py                    # Full pipeline (13 steps)
├── requirements.txt                   # Python dependencies
└── HOW_TO_RUN.md                      # This file
```

---

## Daily Quick Start (Returning Next Day)

If you've already run the full pipeline once, your data, models, and artifacts are all persisted on disk. You only need to **start the services**:

### Open 4 Terminals

**Terminal 1 — API Server:**
```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — React Dashboard:**
```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\dashboard
npm run dev
```

**Terminal 3 — MLflow UI:**
```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000
```

**Terminal 4 — Docker Monitoring (optional):**
```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\monitoring
docker compose up -d
```

### When to Re-run Specific Steps

| Scenario | Command | What it does |
|----------|---------|-------------|
| Just viewing results | Start Terminals 1-3 above | Services only, no reprocessing |
| New data arrived | `python scripts/run_incremental_daily.py` | Ingests + processes new day |
| Check for drift | `python notebooks/10_drift_detection.py` | Runs Evidently AI on latest data |
| Re-check data quality | `python scripts/run_data_quality.py` | Great Expectations validation |
| Retrain all models (keep data) | `python run_pipeline.py --skip-data` | Re-runs steps 6-13 only |
| Retrain only PS-1 | `python notebooks/05_ps1_failure_prediction.py` then `python scripts/register_models.py` | Faster, targeted retrain |
| Full rebuild from scratch | `python run_pipeline.py` | All 13 steps |
| Port 8000 stuck from yesterday | `netstat -ano \| findstr :8000` then `taskkill /F /PID <PID>` | Kill orphan process |

### What's Persisted (survives restarts)

| Data | Location | Recreated by |
|------|----------|-------------|
| Raw CSVs | `data/raw/` | `data/generate_sample_data.py` |
| Bronze/Silver/Gold | `data/bronze/`, `silver/`, `gold/` | Notebooks 01-03 |
| Feature Store | `data/feature_store/` | `notebooks/04_feature_store.py` |
| Trained models (.pkl) | `data/artifacts/ps1-5/` | Notebooks 05-09 |
| MLflow experiments | `mlruns/mlflow.db` | Training notebooks |
| Drift reports (HTML) | `data/drift_reports/` | `notebooks/10_drift_detection.py` |
| Quality reports | `data/quality_reports/` | `scripts/run_data_quality.py` |
| Dashboard node_modules | `dashboard/node_modules/` | `npm install` |

---

## Quick Reference

| Action | Command |
|--------|---------|
| **Setup** | |
| Create venv | `python -m venv venv` |
| Activate (PowerShell) | `venv\Scripts\Activate.ps1` |
| Activate (Git Bash) | `source venv/Scripts/activate` |
| Install Python deps | `pip install -r requirements.txt` |
| Install React deps | `cd dashboard && npm install` |
| Deactivate | `deactivate` |
| **Pipeline** | |
| Full pipeline | `python run_pipeline.py` |
| Only PS-1 | `python run_pipeline.py --ps 1` |
| Skip data gen | `python run_pipeline.py --skip-data` |
| Incremental daily | `python scripts/run_incremental_daily.py` |
| Register models | `python scripts/register_models.py` |
| **Serving** | |
| Start API | `python -m uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| Start React dashboard | `cd dashboard && npm run dev` |
| Swagger UI | `start http://localhost:8000/docs` |
| Load test | `python scripts/generate_traffic.py --rps 5 --duration 120` |
| **Monitoring** | |
| MLflow UI | `mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000` |
| Drift check | `python notebooks/10_drift_detection.py` |
| Data quality | `python scripts/run_data_quality.py` |
| View drift report | `start data/drift_reports/data_drift_no_drift.html` |
| View quality report | `start data/drift_reports/data_quality_no_drift.html` |
| **Docker** | |
| Docker stack | `cd monitoring && docker compose up -d` |
| Blue-Green | `cd monitoring && docker compose -f docker-compose.blue-green.yml up -d` |
| **Testing** | |
| Run tests | `pytest tests/test_api.py -v` |
| **Troubleshooting** | |
| Kill port 8000 | `netstat -ano \| findstr :8000` then `taskkill /F /PID <PID>` |
| Clear Python cache | `Get-ChildItem -Recurse -Directory __pycache__ \| Remove-Item -Recurse` |
