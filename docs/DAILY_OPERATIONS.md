# Daily Operations & Retraining Guide
## How Incremental Data Flows, Predictions Run, and Models Retrain

---

## The Big Picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    DAILY DATA LIFECYCLE                                    │
│                                                                          │
│  6:00 AM ── New Data Arrives (~500 records)                              │
│     │                                                                    │
│     ├── Ingest → Bronze (raw parquet, append)                            │
│     ├── Clean  → Silver (deduplicate, validate)                          │
│     ├── Features → Gold (rolling, delta, cumulative)                     │
│     │                                                                    │
│  6:05 AM ── Live Predictions                                             │
│     │                                                                    │
│     ├── PS-1: Failure probability per device                             │
│     ├── PS-4: Anomaly detection (is this device behaving oddly?)         │
│     └── PS-5: SLA risk score & RUL update                                │
│     │                                                                    │
│  6:10 AM ── Monitoring                                                   │
│     │                                                                    │
│     ├── Drift check (has data distribution changed?)                     │
│     └── Data quality check (are values in expected ranges?)              │
│     │                                                                    │
│  Every 15 Days ── Retrain Models                                         │
│     │                                                                    │
│     ├── All accumulated data becomes new training set                    │
│     ├── PS-1, PS-4, PS-5 models retrained                               │
│     ├── New champion selected if better                                  │
│     ├── Registered in MLflow Model Registry                              │
│     └── API restarted to load new models                                 │
│                                                                          │
│  On Drift (>30%) ── Emergency Retrain                                    │
│     └── Same as above, but triggered immediately                         │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## How Data Accumulates

```
Day 1:   [500 records]  ──→ Training set: 500
Day 2:   [500 records]  ──→ Training set: 1,000
Day 3:   [500 records]  ──→ Training set: 1,500
...
Day 15:  [500 records]  ──→ Training set: 7,500  ←── RETRAIN (15-day cycle)
Day 16:  [500 records]  ──→ Training set: 8,000
...
Day 30:  [500 records]  ──→ Training set: 15,000 ←── RETRAIN (15-day cycle)
```

**Key point:** New daily data is always added to Gold/Feature Store. Models are trained on the **full accumulated dataset** (not just the new 500 records).

---

## Running the Daily Pipeline

### Manual (run yourself)

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1

# Run for today
python scripts/daily_scheduled_pipeline.py

# Run for a specific date
python scripts/daily_scheduled_pipeline.py --date 2025-02-01

# Force retrain (regardless of schedule)
python scripts/daily_scheduled_pipeline.py --force-retrain
```

### Automated: Windows Task Scheduler (6 AM daily)

#### Step 1: Create a batch file

Save as `D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\run_daily.bat`:

```bat
@echo off
cd /d D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
call venv\Scripts\activate
python scripts/daily_scheduled_pipeline.py >> logs\daily_pipeline.log 2>&1
```

Create the logs folder:
```powershell
mkdir D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\logs
```

#### Step 2: Create the scheduled task

```powershell
# Create a scheduled task to run at 6 AM daily
schtasks /create /tn "DeviceTelemetry_DailyPipeline" /tr "D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\run_daily.bat" /sc daily /st 06:00 /rl HIGHEST

# Verify it was created
schtasks /query /tn "DeviceTelemetry_DailyPipeline"

# Run it manually to test
schtasks /run /tn "DeviceTelemetry_DailyPipeline"

# Delete the task (if needed)
schtasks /delete /tn "DeviceTelemetry_DailyPipeline" /f
```

### Automated: Azure (Production)

#### Using Databricks Workflows

```json
{
  "name": "Daily_Telemetry_Pipeline",
  "schedule": {
    "quartz_cron_expression": "0 0 6 * * ?",
    "timezone_id": "Europe/London"
  },
  "tasks": [
    {"task_key": "ingest", "notebook_task": {"notebook_path": "/pipelines/daily_ingest"}},
    {"task_key": "predict", "depends_on": [{"task_key": "ingest"}], "notebook_task": {"notebook_path": "/pipelines/daily_predict"}},
    {"task_key": "drift_check", "depends_on": [{"task_key": "predict"}], "notebook_task": {"notebook_path": "/pipelines/drift_check"}},
    {"task_key": "retrain", "depends_on": [{"task_key": "drift_check"}], "condition_task": {"op": "GREATER_THAN", "left": "{{tasks.drift_check.values.drift_share}}", "right": "0.30"}, "notebook_task": {"notebook_path": "/pipelines/retrain"}}
  ]
}
```

#### Using Azure Data Factory

```
Trigger: Schedule (Daily at 6:00 AM UTC)
  │
  ├── Copy Activity: IoT Hub / Event Hub → Data Lake raw/
  │
  ├── Databricks Notebook: daily_ingest (Bronze → Silver → Gold)
  │
  ├── Databricks Notebook: daily_predict (PS-1, PS-4, PS-5)
  │
  ├── Databricks Notebook: drift_check
  │
  └── If Activity: drift_share > 0.30
      ├── True:  Databricks Notebook: retrain_models
      └── False: (skip)
```

---

## What the Daily Pipeline Does (Step by Step)

### Step 1: Ingest New Data → Bronze (6:00 AM)

```
New 500 records arrive (CSV / API / IoT Hub)
    │
    ▼
Bronze Layer: Append to parquet, date-partitioned
    data/bronze/telemetry/data_20250201.parquet  (new file)
```

- Raw data is **appended**, never overwritten
- Each day gets its own parquet partition
- Metadata added: `_ingested_at`, `_source_file`

### Step 2: Clean → Silver (6:01 AM)

```
Bronze data
    │
    ▼
Silver Layer: Deduplicate + validate + merge with existing
    data/silver/telemetry.parquet  (updated, growing file)
```

- Duplicates removed
- Null values filled (median)
- Range validation (temperature 0-80°C, signal 0-100 dBm)
- **Appended** to existing silver data

### Step 3: Feature Engineering → Gold (6:02 AM)

```
Silver data (last 30 days)
    │
    ▼
Gold Layer: Compute rolling, delta, cumulative features
    data/gold/device_features.parquet  (recalculated)
    data/feature_store/device_telemetry_features.parquet
```

- Uses last 30 days of silver data
- 7-day rolling averages and std
- Day-over-day deltas
- Cumulative error/reboot counts
- Health score computation

### Step 4: Live Predictions (6:05 AM)

```
Today's Gold features
    │
    ├── PS-1 Model ──→ failure_probability, risk_tier per device
    ├── PS-4 Model ──→ anomaly_label, anomaly_score per device
    └── PS-5 Data  ──→ rul_days, sla_risk_score per device
    │
    ▼
Saved to: data/predictions/predictions_20250201.parquet
          data/predictions/latest_predictions.csv
```

**Output columns per device:**

| Column | Source | Example |
|--------|--------|---------|
| `device_id` | — | LMR_0042 |
| `failure_probability` | PS-1 | 0.73 |
| `failure_risk_tier` | PS-1 | HIGH |
| `anomaly_label` | PS-4 | -1 (anomaly) |
| `anomaly_score` | PS-4 | -0.23 |
| `rul_median_days` | PS-5 | 12 |
| `sla_risk_score` | PS-5 | 68.5 |

### Step 5: Drift Check (6:08 AM)

```
Reference (training data) vs Current (recent data)
    │
    ├── KS test per numeric feature
    ├── Drift share = drifted_features / total_features
    │
    ▼
drift_decision.json: { "should_retrain": true/false, "drift_share": 0.XX }
```

### Step 6: Retrain Check (6:10 AM)

```
Should we retrain?
    │
    ├── Is drift > 30%?            → YES → RETRAIN NOW
    ├── Has it been 15+ days?      → YES → RETRAIN NOW
    ├── Is --force-retrain flag?   → YES → RETRAIN NOW
    └── Otherwise                  → NO  → Skip, predict with existing models
```

---

## Retraining: How It Works

### When Retraining Happens

| Trigger | Condition | How Often |
|---------|-----------|-----------|
| **Scheduled** | Every 15 days | ~2x per month |
| **Drift-triggered** | drift_share > 30% | Only when data shifts significantly |
| **Manual** | `--force-retrain` flag | On demand |
| **Performance degradation** | Monitored via Grafana alerts | When predictions degrade |

### What Happens During Retraining

```
1. Load ALL accumulated data from Feature Store
   (not just today's 500, but all 7,500+ records)
       │
2. Retrain PS-1: Failure Prediction
   ├── Train RF, XGBoost, CatBoost
   ├── Compare AUC scores
   └── Select new champion
       │
3. Retrain PS-4: Anomaly Detection
   ├── Fit new Isolation Forest on full data
   └── Recalculate SPC control limits
       │
4. Retrain PS-5: SLA Risk
   ├── Refit Weibull distribution
   ├── Refit Cox PH model
   └── Recalculate RUL per device
       │
5. Register new models in MLflow
   ├── Champion → Production
   └── Old champion → Archived
       │
6. Restart API to load new models
```

### Training Data Window

```
┌──────────────────────────────────────────────────────────┐
│                  TRAINING DATA STRATEGY                    │
│                                                          │
│  Day 1 ─────────────── Day 15 ──────────────── Day 30   │
│  │◄── First training ──►│                                │
│  │    (7,500 records)    │                                │
│  │                       │◄── Retrain #2 ──────►│        │
│  │                       │    (15,000 records)   │        │
│  │                                                       │
│  Option A: FULL WINDOW (use all data)                    │
│  ├── More data = better model                            │
│  └── Risk: old patterns may not reflect current state    │
│                                                          │
│  Option B: SLIDING WINDOW (last 30 days only)            │
│  ├── Model reflects recent behavior                      │
│  └── Risk: less data, may miss rare failure patterns     │
│                                                          │
│  Current setting: FULL WINDOW (all accumulated data)     │
└──────────────────────────────────────────────────────────┘
```

---

## Monitoring the Daily Pipeline

### In MLflow (http://localhost:5000)

Check the **"Daily_Pipeline"** experiment:

- Each day creates a run with metrics:
  - `records_ingested`, `predictions_made`
  - `high_risk_devices`, `anomalies_detected`
  - `drift_share`, `retrained`, `pipeline_duration_seconds`

### In Grafana (http://localhost:3000)

Key PromQL queries for daily monitoring:

```promql
# Predictions made today
increase(predictions_total[24h])

# Drift trend
drift_share_current * 100

# Devices at risk (from API predictions)
devices_at_risk

# Average failure probability
failure_probability_last
```

### View Today's Predictions

```powershell
# Latest predictions (CSV)
type data\predictions\latest_predictions.csv

# Or open in Excel/VS Code
start data\predictions\latest_predictions.csv
```

---

## Training Log

The pipeline maintains a training log at `data/training_log.json`:

```json
{
  "last_retrain_date": "2025-01-15",
  "total_retrains": 3,
  "retrain_history": [
    {"date": "2025-01-01", "reason": "First training", "timestamp": "2025-01-01T06:00:00"},
    {"date": "2025-01-15", "reason": "Scheduled retrain (15 days since last)", "timestamp": "2025-01-15T06:05:00"},
    {"date": "2025-01-22", "reason": "Drift detected (45.2% > 30%)", "timestamp": "2025-01-22T06:08:00"}
  ]
}
```

---

## Configuration

Edit these values in `scripts/daily_scheduled_pipeline.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RETRAIN_INTERVAL_DAYS` | 15 | Days between scheduled retrains |
| `DRIFT_THRESHOLD` | 0.30 | Drift share that triggers retrain (30%) |
| `EXPECTED_DAILY_RECORDS` | 500 | Expected records per day |

---

## Quick Reference

| Action | Command |
|--------|---------|
| Run daily pipeline (today) | `python scripts/daily_scheduled_pipeline.py` |
| Run for specific date | `python scripts/daily_scheduled_pipeline.py --date 2025-02-01` |
| Force retrain | `python scripts/daily_scheduled_pipeline.py --force-retrain` |
| View predictions | `type data\predictions\latest_predictions.csv` |
| Check training log | `type data\training_log.json` |
| Check drift decision | `type data\drift_reports\drift_decision.json` |
| Schedule at 6 AM | `schtasks /create /tn "DeviceTelemetry_DailyPipeline" /tr "run_daily.bat" /sc daily /st 06:00 /rl HIGHEST` |
