# Apache Airflow Guide — Pipeline Orchestration
## Device Telemetry MLOps

---

## Why Airflow?

| Scheduler | Best for | Limitation |
|-----------|---------|------------|
| **Windows Task Scheduler** | Simple local cron | No DAG visualization, no retries, no dependency management |
| **Databricks Workflows** | Databricks-native jobs | Locked to Databricks ecosystem |
| **Azure Data Factory** | Azure-native ETL | Expensive, limited ML pipeline support |
| **Apache Airflow** | Complex ML pipelines with dependencies | Needs setup (Docker or managed service) |

**Airflow advantages:**
- DAG (Directed Acyclic Graph) — visual pipeline with dependencies
- Built-in retries, alerting, backfill
- Web UI to monitor, trigger, and debug runs
- Integrates with Databricks, Azure ML, Spark, Docker
- Open-source (free) or managed (Azure Managed Airflow, MWAA, Astronomer)

---

## Architecture: Airflow in the Stack

```
                    +------------------+
                    |   Airflow Web UI |  http://localhost:8080
                    |   (monitor DAGs) |
                    +--------+---------+
                             |
                    +--------+---------+
                    | Airflow Scheduler|  Triggers DAGs on schedule
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
        +-----+----+  +-----+----+  +------+-----+
        | Worker 1 |  | Worker 2 |  | Worker 3   |
        | (Celery)  |  | (Celery)  |  | (Celery)   |
        +-----------+  +-----------+  +------------+
              |              |              |
    +---------+---------+----+----+---------+--------+
    |                   |         |                  |
    v                   v         v                  v
 Bronze/Silver/      ML Training  Drift           API
 Gold Pipeline       (5 PS)       Detection       Restart
```

---

## Installation

### Option 1: Docker Compose (Recommended)

```powershell
# Create airflow directory
mkdir D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\airflow
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\airflow

# Download official docker-compose
curl -LfO "https://airflow.apache.org/docs/apache-airflow/2.8.1/docker-compose.yaml"

# Create required directories
mkdir dags logs plugins config

# Initialize Airflow (first time only)
docker compose up airflow-init

# Start Airflow
docker compose up -d
```

**Open:** http://localhost:8080 (login: `airflow` / `airflow`)

### Option 2: pip install (lightweight, local)

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1

pip install apache-airflow==2.8.1

# Initialize database
airflow db init

# Create admin user
airflow users create --username admin --password admin --firstname Admin --lastname User --role Admin --email admin@example.com

# Start (2 terminals needed)
# Terminal 1: Scheduler
airflow scheduler

# Terminal 2: Web UI
airflow webserver --port 8080
```

### Option 3: Azure Managed Airflow

```powershell
# No local setup needed — fully managed
az managed-airflow create `
  --name "airflow-device-telemetry" `
  --resource-group $RG `
  --location uksouth `
  --sku Standard
```

---

## DAG Definition — Daily Pipeline

Create this file at `airflow/dags/device_telemetry_daily.py`:

```python
"""
Device Telemetry MLOps — Daily Pipeline DAG
Runs at 6:00 AM UTC every day
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule
import json
import os

BASE_DIR = "D:/Sathish/ML_Device_Telemetry/device_telemetry_mlops"
VENV_PYTHON = f"{BASE_DIR}/venv/Scripts/python.exe"

# ─── DAG Configuration ────────────────────────────────────
default_args = {
    "owner": "ml-team",
    "depends_on_past": False,
    "email": ["ml-team@metro.gov.uk"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

dag = DAG(
    dag_id="device_telemetry_daily_pipeline",
    default_args=default_args,
    description="Daily pipeline: ingest → features → predict → drift → retrain",
    schedule_interval="0 6 * * *",   # 6:00 AM UTC daily
    start_date=datetime(2025, 1, 1),
    catchup=False,                    # Don't backfill missed runs
    max_active_runs=1,                # Only 1 run at a time
    tags=["device-telemetry", "ml", "production"],
)


# ─── Task Functions ───────────────────────────────────────

def run_notebook(script_name, **context):
    """Execute a Python notebook/script."""
    import subprocess
    script_path = os.path.join(BASE_DIR, script_name)
    result = subprocess.run(
        [VENV_PYTHON, script_path],
        capture_output=True, text=True, cwd=BASE_DIR, timeout=1800
    )
    if result.returncode != 0:
        raise Exception(f"Script failed: {result.stderr[-500:]}")
    print(result.stdout[-1000:])
    return result.returncode


def check_drift_decision(**context):
    """Branch: retrain if drift > 30% or 15 days since last training."""
    drift_path = os.path.join(BASE_DIR, "data", "drift_reports", "drift_decision.json")
    training_log = os.path.join(BASE_DIR, "data", "training_log.json")

    # Check drift
    should_retrain = False
    if os.path.exists(drift_path):
        with open(drift_path) as f:
            drift = json.load(f)
        if drift.get("should_retrain", False):
            should_retrain = True
            print(f"Drift detected: {drift.get('drift_share', 0)*100:.1f}%")

    # Check 15-day schedule
    if not should_retrain and os.path.exists(training_log):
        with open(training_log) as f:
            log = json.load(f)
        last_retrain = log.get("last_retrain_date")
        if last_retrain:
            from datetime import datetime
            days_since = (datetime.now() - datetime.strptime(last_retrain, "%Y-%m-%d")).days
            if days_since >= 15:
                should_retrain = True
                print(f"Scheduled retrain: {days_since} days since last")

    if should_retrain:
        return "retrain_ps1"   # Go to retrain branch
    else:
        return "skip_retrain"  # Go to skip branch


def restart_api(**context):
    """Restart the API to load new models."""
    import subprocess
    # Kill existing API process
    subprocess.run(
        ["powershell", "-Command",
         "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | "
         "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
        capture_output=True
    )
    # Start new API
    subprocess.Popen(
        [VENV_PYTHON, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=BASE_DIR
    )
    print("API restarted with new models")


# ─── DAG Tasks ────────────────────────────────────────────

# STAGE 1: DATA PIPELINE
t_bronze = PythonOperator(
    task_id="bronze_ingestion",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/01_bronze_layer.py"},
    dag=dag,
)

t_silver = PythonOperator(
    task_id="silver_cleaning",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/02_silver_layer.py"},
    dag=dag,
)

t_gold = PythonOperator(
    task_id="gold_feature_engineering",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/03_gold_layer.py"},
    dag=dag,
)

t_feature_store = PythonOperator(
    task_id="feature_store_update",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/04_feature_store.py"},
    dag=dag,
)

t_quality = PythonOperator(
    task_id="data_quality_check",
    python_callable=run_notebook,
    op_kwargs={"script_name": "scripts/run_data_quality.py"},
    dag=dag,
)

# STAGE 2: PREDICTIONS (all 5 PS run in parallel on existing models)
t_predict = BashOperator(
    task_id="daily_predictions",
    bash_command=f'{VENV_PYTHON} {BASE_DIR}/scripts/daily_scheduled_pipeline.py '
                 f'--date {{{{ ds }}}}',
    cwd=BASE_DIR,
    dag=dag,
)

# STAGE 3: DRIFT DETECTION
t_drift = PythonOperator(
    task_id="drift_detection",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/10_drift_detection.py"},
    dag=dag,
)

# STAGE 4: RETRAIN DECISION (branch)
t_branch = BranchPythonOperator(
    task_id="check_retrain_needed",
    python_callable=check_drift_decision,
    dag=dag,
)

# STAGE 5a: RETRAIN (if needed) — all 5 PS in parallel
t_retrain_ps1 = PythonOperator(
    task_id="retrain_ps1",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/05_ps1_failure_prediction.py"},
    dag=dag,
)

t_retrain_ps2 = PythonOperator(
    task_id="retrain_ps2",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/06_ps2_error_pattern.py"},
    dag=dag,
)

t_retrain_ps3 = PythonOperator(
    task_id="retrain_ps3",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/07_ps3_root_cause.py"},
    dag=dag,
)

t_retrain_ps4 = PythonOperator(
    task_id="retrain_ps4",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/08_ps4_anomaly_detection.py"},
    dag=dag,
)

t_retrain_ps5 = PythonOperator(
    task_id="retrain_ps5",
    python_callable=run_notebook,
    op_kwargs={"script_name": "notebooks/09_ps5_sla_risk.py"},
    dag=dag,
)

t_register = PythonOperator(
    task_id="register_models",
    python_callable=run_notebook,
    op_kwargs={"script_name": "scripts/register_models.py"},
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag,
)

t_restart_api = PythonOperator(
    task_id="restart_api",
    python_callable=restart_api,
    trigger_rule=TriggerRule.ALL_SUCCESS,
    dag=dag,
)

# STAGE 5b: SKIP RETRAIN
t_skip = EmptyOperator(
    task_id="skip_retrain",
    dag=dag,
)

# STAGE 6: DONE
t_done = EmptyOperator(
    task_id="pipeline_complete",
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    dag=dag,
)


# ─── Task Dependencies (DAG structure) ───────────────────
#
#  bronze → silver → gold → feature_store → quality
#                                              |
#                                              v
#                                          predict
#                                              |
#                                              v
#                                           drift
#                                              |
#                                              v
#                                     check_retrain_needed
#                                        /            \
#                                       v              v
#                              retrain_ps1         skip_retrain
#                              retrain_ps2              |
#                              retrain_ps3              |
#                              retrain_ps4              |
#                              retrain_ps5              |
#                                  |                    |
#                                  v                    |
#                           register_models             |
#                                  |                    |
#                                  v                    |
#                            restart_api                |
#                                  |                    |
#                                  v                    v
#                              pipeline_complete

t_bronze >> t_silver >> t_gold >> t_feature_store >> t_quality
t_quality >> t_predict >> t_drift >> t_branch

# Retrain branch (parallel PS training)
t_branch >> t_retrain_ps1
t_branch >> t_retrain_ps2
t_branch >> t_retrain_ps3
t_branch >> t_retrain_ps4
t_branch >> t_retrain_ps5

[t_retrain_ps1, t_retrain_ps2, t_retrain_ps3,
 t_retrain_ps4, t_retrain_ps5] >> t_register >> t_restart_api >> t_done

# Skip branch
t_branch >> t_skip >> t_done
```

---

## DAG Visualization

What you see in the Airflow Web UI:

```
+--------+    +--------+    +------+    +--------+    +---------+
| bronze |--->| silver |--->| gold |--->| feat   |--->| quality |
+--------+    +--------+    +------+    | store  |    +---------+
                                        +--------+        |
                                                           v
                                                      +---------+
                                                      | predict |
                                                      +---------+
                                                           |
                                                           v
                                                      +---------+
                                                      |  drift  |
                                                      +---------+
                                                           |
                                                           v
                                                    +-----------+
                                                    | check     |
                                                    | retrain?  |
                                                    +-----------+
                                                    /           \
                                                   v             v
                            +----------+  +----------+     +---------+
                            |retrain   |  |retrain   |     |  skip   |
                            |ps1       |  |ps2       |     | retrain |
                            +-----+----+  +-----+----+     +---------+
                            |retrain   |  |retrain   |          |
                            |ps3       |  |ps4       |          |
                            +-----+----+  +-----+----+          |
                                  |retrain   |                   |
                                  |ps5       |                   |
                                  +-----+----+                   |
                                        |                        |
                                        v                        |
                                 +----------+                    |
                                 | register |                    |
                                 | models   |                    |
                                 +----------+                    |
                                        |                        |
                                        v                        |
                                 +----------+                    |
                                 | restart  |                    |
                                 | api      |                    |
                                 +----------+                    |
                                        |                        |
                                        v                        v
                                    +----------------------------+
                                    |     pipeline_complete      |
                                    +----------------------------+
```

**Color coding in Airflow UI:**
- Green = success
- Red = failed
- Yellow = running
- Light blue = queued
- White = not yet started

---

## Multiple DAGs

### DAG 1: Daily Pipeline (above) — `0 6 * * *` (6 AM daily)

### DAG 2: Hourly Health Check

```python
dag_health = DAG(
    dag_id="device_telemetry_health_check",
    schedule_interval="0 * * * *",   # Every hour
    ...
)

# Tasks: check API health, check Prometheus targets, check model loaded
```

### DAG 3: Weekly Full Retrain

```python
dag_weekly = DAG(
    dag_id="device_telemetry_weekly_retrain",
    schedule_interval="0 2 * * 0",   # 2 AM every Sunday
    ...
)

# Tasks: full retrain of all 5 PS regardless of drift
```

### DAG 4: Monthly Report

```python
dag_monthly = DAG(
    dag_id="device_telemetry_monthly_report",
    schedule_interval="0 8 1 * *",   # 8 AM on 1st of each month
    ...
)

# Tasks: generate fleet report, email to stakeholders
```

---

## Airflow vs Other Schedulers

| Feature | Windows Task Scheduler | Databricks Workflows | Azure Data Factory | **Apache Airflow** |
|---------|----------------------|---------------------|-------------------|-------------------|
| DAG visualization | No | Yes (basic) | Yes (drag-drop) | **Yes (best)** |
| Branching logic | No | Limited | If Activity | **BranchOperator** |
| Parallel tasks | No | Yes | Yes | **Yes** |
| Retry with backoff | No | Yes | Yes | **Yes (configurable)** |
| Backfill missed runs | No | No | No | **Yes** |
| Web UI | No | Databricks UI | ADF Studio | **Full web UI** |
| Alerting | No | Email | Email/webhook | **Email/Slack/PagerDuty** |
| Cost | Free | Databricks DBUs | Per activity run | **Free (self-hosted)** |
| Python-native | No (.bat) | Notebooks | JSON/ARM | **Yes (pure Python)** |
| Task dependencies | No | Yes | Yes | **Yes (rich operators)** |
| XCom (pass data) | No | dbutils | Pipeline params | **Yes** |
| Sensors (wait for) | No | No | Trigger | **Yes (file, HTTP, SQL)** |
| Local dev | Yes | No (cloud only) | No (cloud only) | **Yes (Docker)** |

---

## Airflow with Azure (Production)

### Option A: Self-hosted on AKS

```powershell
# Deploy Airflow on AKS using Helm
helm repo add apache-airflow https://airflow.apache.org
helm install airflow apache-airflow/airflow `
  --namespace airflow `
  --set executor=CeleryExecutor `
  --set workers.replicas=3
```

### Option B: Azure Managed Airflow (Preview)

```powershell
az managed-airflow create `
  --name "airflow-device-telemetry" `
  --resource-group $RG `
  --location uksouth
```

### Option C: Astronomer (Managed Airflow SaaS)

Fully managed Airflow with enterprise support. Deploy DAGs via Git push.

---

## Airflow Connections to Configure

Set up in Airflow UI → Admin → Connections:

| Connection ID | Type | Used for |
|---------------|------|----------|
| `azure_blob_default` | Azure Blob Storage | Read/write ADLS Gen2 |
| `databricks_default` | Databricks | Trigger Databricks notebooks |
| `azure_ml_default` | HTTP | Trigger Azure ML pipelines |
| `slack_webhook` | HTTP | Send alerts to Slack |
| `smtp_default` | SMTP | Email alerts on failure |

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start Airflow (Docker) | `cd airflow && docker compose up -d` |
| Start Airflow (local) | `airflow scheduler` + `airflow webserver --port 8080` |
| Open Web UI | http://localhost:8080 (admin/admin) |
| Trigger DAG manually | `airflow dags trigger device_telemetry_daily_pipeline` |
| Backfill missed dates | `airflow dags backfill device_telemetry_daily_pipeline -s 2025-01-01 -e 2025-01-15` |
| List DAGs | `airflow dags list` |
| Check task status | `airflow tasks states-for-dag-run device_telemetry_daily_pipeline <run_id>` |
| Pause DAG | `airflow dags pause device_telemetry_daily_pipeline` |
| Unpause DAG | `airflow dags unpause device_telemetry_daily_pipeline` |
