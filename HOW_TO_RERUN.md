# How to Re-Run — Daily Quick Start Guide
## Device Telemetry MLOps

This guide is for when you've **already run the full pipeline once** and are coming back the next day. No need to regenerate data or retrain models — just start the services.

---

## Pre-Check: Kill Zombie Processes

Old processes from yesterday may still be holding ports. **Always run this first:**

```powershell
# Check and kill any process on port 8000 (API)
netstat -ano | findstr :8000 | findstr LISTENING
# Note the PID numbers, then kill each one:
taskkill /F /PID <PID1>
taskkill /F /PID <PID2>

# Check and kill any process on port 5000 (MLflow)
netstat -ano | findstr :5000 | findstr LISTENING
taskkill /F /PID <PID>

# Check and kill any process on port 5173 (React Dashboard)
netstat -ano | findstr :5173 | findstr LISTENING
taskkill /F /PID <PID>
```

> **Example:** If `netstat` shows PID `6616` and `34188`, run:
> ```powershell
> taskkill /F /PID 6616
> taskkill /F /PID 34188
> ```

---

## Option A: Start Everything (5 Terminals)

### Terminal 1 — API Server

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Wait for: `Application startup complete.`

**Verify:** http://localhost:8000/health
**Swagger UI:** http://localhost:8000/docs

### Terminal 2 — React Dashboard

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\dashboard
npm run dev
```

Wait for: `Local: http://localhost:5173/`

**Open:** http://localhost:5173

### Terminal 3 — MLflow UI

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db --port 5000
```

**Open:** http://localhost:5000

### Terminal 4 — Prometheus + Grafana (Docker)

> **Prerequisite:** Docker Desktop must be running. Start it from the Windows Start menu first.

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\monitoring
docker compose up -d
```

**Open:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (login: `admin` / `admin`)

### Terminal 5 — Working Terminal (for running scripts)

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
```

Use this terminal for drift checks, quality checks, retraining, etc.

---

## Option B: Start Only What You Need

| What you want to do | Terminals needed |
|---------------------|-----------------|
| View React dashboard | Terminal 1 (API) + Terminal 2 (Dashboard) |
| View MLflow experiments | Terminal 3 (MLflow) only |
| View Grafana dashboards | Terminal 1 (API) + Terminal 4 (Docker) |
| Test API predictions | Terminal 1 (API) only |
| Run drift/quality checks | Terminal 5 (Working) only |
| View existing HTML reports | No terminal needed (see below) |

### View Existing Reports (no server needed)

```powershell
# Evidently AI drift reports
start D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\data\drift_reports\data_drift_no_drift.html
start D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\data\drift_reports\data_drift_simulated_drift.html
start D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\data\drift_reports\data_quality_no_drift.html

# Data quality summary
type D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\data\quality_reports\quality_summary.json

# Drift retraining decision
type D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\data\drift_reports\drift_decision.json
```

---

## All URLs at a Glance

| Service | URL | Port | What you see |
|---------|-----|------|-------------|
| API (Swagger) | http://localhost:8000/docs | 8000 | Interactive API testing |
| API (Health) | http://localhost:8000/health | 8000 | API status, loaded models |
| API (Metrics) | http://localhost:8000/metrics | 8000 | Raw Prometheus metrics (28 metrics) |
| React Dashboard | http://localhost:5173 | 5173 | All 5 PS outputs, charts, tables |
| MLflow | http://localhost:5000 | 5000 | Experiments, model registry, artifacts |
| Prometheus | http://localhost:9090 | 9090 | Query metrics, check scrape targets |
| Grafana | http://localhost:3000 | 3000 | Dashboards, alerts (admin/admin) |

---

## Common Daily Tasks

### Run Drift Detection (new data check)

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1
python notebooks/10_drift_detection.py
```

Then view the report:
```powershell
start data\drift_reports\data_drift_no_drift.html
type data\drift_reports\drift_decision.json
```

### Run Data Quality Check

```powershell
python scripts/run_data_quality.py
type data\quality_reports\quality_summary.json
```

### Process New Day of Data (Incremental)

```powershell
python scripts/run_incremental_daily.py
```

### Test API Predictions

```powershell
# PS-1: Failure Prediction
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/failure" -ContentType "application/json" -Body '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'

# PS-4: Anomaly Detection
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/anomaly" -ContentType "application/json" -Body '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'

# PS-5: SLA Risk
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/predict/sla-risk" -ContentType "application/json" -Body '{"device_id":"LMR_0001","signal_strength_dbm":45.0,"temperature_c":52.0,"response_time_ms":350.0,"network_latency_ms":55.0,"power_voltage":3.8,"memory_usage_pct":85.0,"cpu_usage_pct":78.0,"error_count":8,"reboot_count":2,"uptime_hours":18.5,"daily_taps":400,"tap_success_rate":0.78,"health_score":35.0,"age_days":1200,"cumulative_errors":150,"cumulative_reboots":25,"total_maintenance_count":12,"corrective_count":8,"emergency_count":3}'

# Health Check
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

### Generate Load for Grafana Dashboards

```powershell
python scripts/generate_traffic.py --rps 5 --duration 120
```

---

## When to Retrain Models

| Scenario | What to run | Time |
|----------|------------|------|
| **Drift detected (>30%)** | `python run_pipeline.py --skip-data` | ~5 min |
| **Retrain only PS-1** | `python notebooks/05_ps1_failure_prediction.py` then `python scripts/register_models.py` | ~2 min |
| **Retrain only PS-4** | `python notebooks/08_ps4_anomaly_detection.py` then `python scripts/register_models.py` | ~1 min |
| **Retrain only PS-5** | `python notebooks/09_ps5_sla_risk.py` then `python scripts/register_models.py` | ~1 min |
| **New data + retrain all** | `python run_pipeline.py` | ~8 min |
| **Data pipeline only** | `python run_pipeline.py --skip-ml` | ~2 min |

After retraining, **restart the API** to load new models:
```powershell
# Ctrl+C in Terminal 1, then:
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## What's Already on Disk (no need to recreate)

| Data | Location | Size |
|------|----------|------|
| Raw CSVs | `data/raw/*.csv` | ~2 MB |
| Bronze Parquet | `data/bronze/` | ~3 MB |
| Silver Parquet | `data/silver/` | ~2 MB |
| Gold Features | `data/gold/` | ~4 MB |
| Feature Store | `data/feature_store/` | ~4 MB |
| PS-1 Models | `data/artifacts/ps1/` | ~5 MB |
| PS-2 Rules | `data/artifacts/ps2/` | ~1 MB |
| PS-3 SHAP | `data/artifacts/ps3/` | ~2 MB |
| PS-4 Anomaly Model | `data/artifacts/ps4/` | ~3 MB |
| PS-5 Survival/RUL | `data/artifacts/ps5/` | ~2 MB |
| MLflow Database | `mlruns/mlflow.db` | ~5 MB |
| MLflow Artifacts | `mlruns/1-6/` | ~15 MB |
| Drift Reports | `data/drift_reports/*.html` | ~3 MB |
| Quality Reports | `data/quality_reports/` | ~1 MB |
| React node_modules | `dashboard/node_modules/` | ~200 MB |
| Python venv | `venv/` | ~1.5 GB |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `WinError 10013` or `address already in use` | Port is occupied. Run `netstat -ano \| findstr :PORT \| findstr LISTENING` then `taskkill /F /PID <PID>` |
| `Connection Error` in React dashboard | API not running. Start Terminal 1 first, wait for `startup complete` |
| `unable to open database file` (MLflow) | Wrong directory. Make sure you `cd device_telemetry_mlops` first |
| `No module named uvicorn` | Wrong venv. Run `venv\Scripts\Activate.ps1` from inside `device_telemetry_mlops/` |
| Dashboard shows stale data | Restart API (`Ctrl+C` → re-run uvicorn) |
| Docker errors | Make sure Docker Desktop is running (check system tray) |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in the activated venv |
| Grafana no data | Check Prometheus target is UP at http://localhost:9090/targets |
| PowerShell enters debug mode | Type `q` then `Set-PSDebug -Off` |

---

## Shutdown (End of Day)

```powershell
# Terminal 1: Ctrl+C (stops API)
# Terminal 2: Ctrl+C (stops React dashboard)
# Terminal 3: Ctrl+C (stops MLflow)

# Terminal 4: Stop Docker containers
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\monitoring
docker compose down

# Deactivate venv
deactivate
```

All data, models, and reports remain on disk for tomorrow.
