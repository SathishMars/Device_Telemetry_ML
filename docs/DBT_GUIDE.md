# dbt (Data Build Tool) Guide
## Device Telemetry MLOps

---

## What is dbt?

dbt is a **SQL-first transformation tool** that sits between your raw data and your ML-ready features. It replaces the Python-based Bronze → Silver → Gold notebooks with **version-controlled, tested, documented SQL models**.

```
WITHOUT dbt (current):
  Python notebooks do everything: ingest + clean + transform + feature engineer
  01_bronze_layer.py → 02_silver_layer.py → 03_gold_layer.py

WITH dbt:
  Python handles: ingestion (ADF/Airflow) + ML training (notebooks 05-09)
  dbt handles:    Bronze → Silver → Gold transformations (SQL models)

  SEPARATION OF CONCERNS:
  ┌──────────┐     ┌──────────────────────┐     ┌──────────────┐
  │ Ingestion │────>│ dbt (transformations)│────>│ ML Training  │
  │ ADF/Python│     │ Bronze→Silver→Gold   │     │ PS-1 to PS-5 │
  │           │     │ SQL + tests + docs   │     │ Python       │
  └──────────┘     └──────────────────────┘     └──────────────┘
```

**Why use dbt?**

| Without dbt | With dbt |
|-------------|----------|
| Transformations buried in Python scripts | SQL models, version-controlled in Git |
| No data tests | Built-in tests (unique, not_null, accepted_values, relationships) |
| No data lineage | Auto-generated lineage DAG |
| No documentation | Auto-generated docs site |
| Manual quality checks (Great Expectations) | dbt tests replace most GE checks |
| Hard to debug transformations | Each model is a single SQL file, easy to debug |
| No incremental processing | `incremental` materialization built-in |

---

## Where dbt Fits in the Architecture

```
LAYER 1: DATA INGESTION
  ADF / Airflow / Python
  IoT Hub → Raw CSV/JSON → ADLS raw/
       │
       │ (dbt does NOT handle ingestion)
       │
       v
LAYER 2: DATA TRANSFORMATION ← ← ← dbt LIVES HERE
  ┌──────────────────────────────────────────────────────────────┐
  │                                                              │
  │  dbt Project: device_telemetry                               │
  │                                                              │
  │  models/                                                     │
  │  ├── staging/          (Bronze → Silver)                     │
  │  │   ├── stg_telemetry.sql                                   │
  │  │   ├── stg_error_logs.sql                                  │
  │  │   ├── stg_devices.sql                                     │
  │  │   └── stg_maintenance.sql                                 │
  │  │                                                           │
  │  ├── intermediate/     (Silver → joins + business logic)     │
  │  │   ├── int_device_daily_metrics.sql                        │
  │  │   ├── int_error_sequences.sql                             │
  │  │   └── int_maintenance_history.sql                         │
  │  │                                                           │
  │  └── marts/            (Gold → ML-ready features)            │
  │      ├── fct_device_features.sql      ← Feature Store        │
  │      ├── fct_failure_labels.sql       ← PS-1 target          │
  │      ├── fct_error_patterns.sql       ← PS-2 input           │
  │      ├── fct_anomaly_features.sql     ← PS-4 input           │
  │      └── fct_sla_risk_features.sql    ← PS-5 input           │
  │                                                              │
  │  tests/                                                      │
  │  ├── schema.yml           (column tests)                     │
  │  └── custom/              (business rule tests)              │
  │                                                              │
  │  macros/                  (reusable SQL functions)            │
  │  └── rolling_average.sql                                     │
  │                                                              │
  └──────────────────────────────────────────────────────────────┘
       │
       │ (dbt outputs → Feature Store / Gold tables)
       │
       v
LAYER 3-4: ML TRAINING
  Python notebooks (05-09) read from dbt marts
  PS-1 to PS-5 models trained on dbt-produced features
```

---

## dbt Project Structure

```
device_telemetry_mlops/
└── dbt_project/
    ├── dbt_project.yml          # Project config
    ├── profiles.yml             # Connection config (local or Azure)
    ├── models/
    │   ├── staging/
    │   │   ├── _staging.yml     # Source definitions + tests
    │   │   ├── stg_telemetry.sql
    │   │   ├── stg_error_logs.sql
    │   │   ├── stg_devices.sql
    │   │   └── stg_maintenance.sql
    │   ├── intermediate/
    │   │   ├── _intermediate.yml
    │   │   ├── int_device_daily_metrics.sql
    │   │   ├── int_error_sequences.sql
    │   │   └── int_maintenance_history.sql
    │   └── marts/
    │       ├── _marts.yml       # Tests + docs for final tables
    │       ├── fct_device_features.sql
    │       ├── fct_failure_labels.sql
    │       ├── fct_error_patterns.sql
    │       ├── fct_anomaly_features.sql
    │       └── fct_sla_risk_features.sql
    ├── tests/
    │   └── assert_failure_rate_reasonable.sql
    ├── macros/
    │   ├── rolling_average.sql
    │   └── health_score.sql
    ├── seeds/
    │   └── error_code_mapping.csv
    └── snapshots/
        └── scd_devices.sql      # Slowly changing dimension
```

---

## Installation

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops
venv\Scripts\Activate.ps1

# For local development (DuckDB — no database server needed)
pip install dbt-duckdb

# For Azure Databricks
pip install dbt-databricks

# For Azure Synapse / SQL
pip install dbt-sqlserver

# Initialize project
dbt init device_telemetry
```

---

## Configuration Files

### dbt_project.yml

```yaml
# dbt_project/dbt_project.yml

name: "device_telemetry"
version: "1.0.0"
config-version: 2

profile: "device_telemetry"

model-paths: ["models"]
test-paths: ["tests"]
macro-paths: ["macros"]
seed-paths: ["seeds"]
snapshot-paths: ["snapshots"]

clean-targets:
  - "target"
  - "dbt_packages"

models:
  device_telemetry:
    staging:
      +materialized: view          # Staging = views (lightweight)
      +schema: staging
    intermediate:
      +materialized: table         # Intermediate = tables
      +schema: intermediate
    marts:
      +materialized: incremental   # Marts = incremental (append new data)
      +schema: marts
```

### profiles.yml

```yaml
# dbt_project/profiles.yml

device_telemetry:
  target: dev
  outputs:

    # Local development (DuckDB — zero setup)
    dev:
      type: duckdb
      path: "../data/telemetry_dw.duckdb"
      threads: 4

    # Azure Databricks (production)
    prod:
      type: databricks
      host: "adb-1234567890.azuredatabricks.net"
      http_path: "/sql/1.0/warehouses/abc123"
      token: "{{ env_var('DBT_DATABRICKS_TOKEN') }}"
      schema: gold
      threads: 8

    # Azure Synapse (alternative)
    synapse:
      type: sqlserver
      server: "synapse-device-telemetry.sql.azuresynapse.net"
      database: "telemetry_dw"
      schema: gold
      authentication: CLI
```

---

## Model Definitions (SQL Files)

### Staging Models (Bronze → Silver)

#### stg_telemetry.sql
```sql
-- models/staging/stg_telemetry.sql
-- Cleans raw telemetry data: dedup, type cast, range validation

{{
    config(
        materialized='view',
        tags=['daily']
    )
}}

with source as (
    select * from {{ source('raw', 'telemetry') }}
),

cleaned as (
    select
        device_id,
        cast(date as date) as reading_date,

        -- Range validation (clip to valid ranges)
        least(greatest(signal_strength_dbm, 0), 100) as signal_strength_dbm,
        least(greatest(temperature_c, -10), 80) as temperature_c,
        greatest(response_time_ms, 10) as response_time_ms,
        greatest(network_latency_ms, 1) as network_latency_ms,
        least(greatest(power_voltage, 2.0), 6.0) as power_voltage,
        least(greatest(memory_usage_pct, 0), 100) as memory_usage_pct,
        least(greatest(cpu_usage_pct, 0), 100) as cpu_usage_pct,
        greatest(error_count, 0) as error_count,
        greatest(reboot_count, 0) as reboot_count,
        least(greatest(uptime_hours, 0), 24) as uptime_hours,
        greatest(daily_taps, 0) as daily_taps,
        least(greatest(tap_success_rate, 0), 1.0) as tap_success_rate,

        -- Metadata
        current_timestamp as _loaded_at

    from source

    -- Deduplicate: keep latest per device per day
    qualify row_number() over (
        partition by device_id, date
        order by date desc
    ) = 1
)

select * from cleaned
```

#### stg_error_logs.sql
```sql
-- models/staging/stg_error_logs.sql

{{
    config(materialized='view', tags=['daily'])
}}

with source as (
    select * from {{ source('raw', 'error_logs') }}
),

cleaned as (
    select
        device_id,
        cast(timestamp as timestamp) as error_timestamp,
        cast(timestamp as date) as error_date,
        error_code,
        severity,
        upper(trim(error_code)) as error_code_clean,
        case severity
            when 'LOW' then 1
            when 'MEDIUM' then 2
            when 'HIGH' then 3
            when 'CRITICAL' then 4
            else 0
        end as severity_rank,
        current_timestamp as _loaded_at

    from source
    where device_id is not null
      and error_code is not null
)

select * from cleaned
```

#### _staging.yml (source definitions + tests)
```yaml
# models/staging/_staging.yml

version: 2

sources:
  - name: raw
    description: "Raw telemetry data from IoT devices"
    tables:
      - name: telemetry
        description: "Daily device readings"
        columns:
          - name: device_id
            tests:
              - not_null
          - name: date
            tests:
              - not_null
          - name: tap_success_rate
            tests:
              - not_null
              - dbt_utils.accepted_range:
                  min_value: 0
                  max_value: 1

      - name: error_logs
        description: "Device error events"
        columns:
          - name: device_id
            tests:
              - not_null
          - name: error_code
            tests:
              - not_null
              - accepted_values:
                  values: ['NFC_TIMEOUT', 'NETWORK_LOSS', 'CARD_READ_ERROR',
                           'SENSOR_MALFUNCTION', 'FIRMWARE_CRASH', 'POWER_FLUCTUATION',
                           'MEMORY_OVERFLOW', 'DISPLAY_ERROR', 'COMMUNICATION_FAILURE',
                           'GATE_MECHANISM_STUCK', 'AUTH_FAILURE', 'OVERHEATING']

      - name: devices
        description: "Device master data"
      - name: maintenance
        description: "Maintenance and SLA records"

models:
  - name: stg_telemetry
    description: "Cleaned telemetry with range validation and dedup"
    columns:
      - name: device_id
        tests:
          - not_null
      - name: reading_date
        tests:
          - not_null
      - name: signal_strength_dbm
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100

  - name: stg_error_logs
    description: "Cleaned error logs with severity ranking"
```

### Intermediate Models (Silver → Joins + Aggregations)

#### int_device_daily_metrics.sql
```sql
-- models/intermediate/int_device_daily_metrics.sql
-- Aggregates telemetry + error counts per device per day

{{
    config(materialized='table', tags=['daily'])
}}

with telemetry as (
    select * from {{ ref('stg_telemetry') }}
),

errors as (
    select
        device_id,
        error_date,
        count(*) as daily_error_events,
        count(distinct error_code) as unique_error_codes,
        max(severity_rank) as max_severity,
        sum(case when severity in ('HIGH', 'CRITICAL') then 1 else 0 end) as critical_errors
    from {{ ref('stg_error_logs') }}
    group by device_id, error_date
),

joined as (
    select
        t.*,
        coalesce(e.daily_error_events, 0) as daily_error_events,
        coalesce(e.unique_error_codes, 0) as unique_error_codes,
        coalesce(e.max_severity, 0) as max_severity,
        coalesce(e.critical_errors, 0) as critical_errors
    from telemetry t
    left join errors e
        on t.device_id = e.device_id
        and t.reading_date = e.error_date
)

select * from joined
```

### Mart Models (Gold → ML-Ready Features)

#### fct_device_features.sql
```sql
-- models/marts/fct_device_features.sql
-- ML-ready feature table with rolling averages, deltas, cumulative metrics

{{
    config(
        materialized='incremental',
        unique_key=['device_id', 'reading_date'],
        incremental_strategy='merge',
        tags=['daily', 'feature_store']
    )
}}

with daily as (
    select * from {{ ref('int_device_daily_metrics') }}
    {% if is_incremental() %}
    -- Only process new data (incremental!)
    where reading_date > (select max(reading_date) from {{ this }})
    {% endif %}
),

with_rolling as (
    select
        *,

        -- 7-day rolling averages
        {{ rolling_average('signal_strength_dbm', 7) }},
        {{ rolling_average('temperature_c', 7) }},
        {{ rolling_average('error_count', 7) }},
        {{ rolling_average('response_time_ms', 7) }},

        -- 7-day rolling std
        stddev(signal_strength_dbm) over (
            partition by device_id
            order by reading_date
            rows between 6 preceding and current row
        ) as signal_strength_dbm_7d_std,

        stddev(error_count) over (
            partition by device_id
            order by reading_date
            rows between 6 preceding and current row
        ) as error_count_7d_std,

        -- Day-over-day delta
        signal_strength_dbm - lag(signal_strength_dbm) over (
            partition by device_id order by reading_date
        ) as signal_strength_dbm_delta,

        temperature_c - lag(temperature_c) over (
            partition by device_id order by reading_date
        ) as temperature_c_delta,

        error_count - lag(error_count) over (
            partition by device_id order by reading_date
        ) as error_count_delta,

        -- Cumulative
        sum(error_count) over (
            partition by device_id order by reading_date
        ) as cumulative_errors,

        sum(reboot_count) over (
            partition by device_id order by reading_date
        ) as cumulative_reboots,

        -- Health score
        {{ health_score(
            'tap_success_rate', 'signal_strength_dbm', 'memory_usage_pct',
            'cpu_usage_pct', 'uptime_hours', 'error_count'
        ) }} as health_score

    from daily
)

select * from with_rolling
```

#### fct_failure_labels.sql (PS-1 target)
```sql
-- models/marts/fct_failure_labels.sql
-- Creates the failure_next_3d label for PS-1

{{
    config(materialized='table', tags=['daily', 'ps1'])
}}

with features as (
    select * from {{ ref('fct_device_features') }}
),

with_labels as (
    select
        f.*,

        -- Look ahead 3 days: did this device have a failure?
        case when exists (
            select 1 from features f2
            where f2.device_id = f.device_id
              and f2.reading_date between f.reading_date + interval '1 day'
                                      and f.reading_date + interval '3 days'
              and f2.error_count >= 5
        ) then 1 else 0 end as failure_next_3d

    from features f
)

select * from with_labels
```

---

## Macros (Reusable SQL Functions)

### rolling_average.sql
```sql
-- macros/rolling_average.sql

{% macro rolling_average(column_name, window_days) %}
    avg({{ column_name }}) over (
        partition by device_id
        order by reading_date
        rows between {{ window_days - 1 }} preceding and current row
    ) as {{ column_name }}_{{ window_days }}d_mean
{% endmacro %}
```

### health_score.sql
```sql
-- macros/health_score.sql

{% macro health_score(tap_rate, signal, memory, cpu, uptime, errors) %}
    (
        {{ tap_rate }} * 30 +
        (least(greatest({{ signal }}, 0), 100) / 100.0) * 20 +
        (1.0 - {{ memory }} / 100.0) * 15 +
        (1.0 - {{ cpu }} / 100.0) * 15 +
        (least(greatest({{ uptime }}, 0), 24) / 24.0) * 10 +
        (1.0 - least(greatest({{ errors }}, 0), 10) / 10.0) * 10
    )
{% endmacro %}
```

---

## Tests

### Schema tests (_marts.yml)
```yaml
# models/marts/_marts.yml

version: 2

models:
  - name: fct_device_features
    description: "ML-ready feature table. 80+ features per device per day."
    columns:
      - name: device_id
        tests:
          - not_null
          - unique:
              config:
                where: "reading_date = current_date"
      - name: reading_date
        tests:
          - not_null
      - name: health_score
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100
      - name: signal_strength_dbm_7d_mean
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 100

  - name: fct_failure_labels
    description: "PS-1 training data with failure_next_3d label"
    columns:
      - name: failure_next_3d
        tests:
          - not_null
          - accepted_values:
              values: [0, 1]
    tests:
      - dbt_utils.expression_is_true:
          expression: "avg(failure_next_3d) between 0.02 and 0.15"
          config:
            severity: warn
```

### Custom test
```sql
-- tests/assert_failure_rate_reasonable.sql
-- Failure rate should be between 2% and 15%

select
    avg(failure_next_3d) as failure_rate
from {{ ref('fct_failure_labels') }}
having avg(failure_next_3d) < 0.02 or avg(failure_next_3d) > 0.15
```

---

## Running dbt

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\dbt_project

# Check connection
dbt debug

# Install packages (dbt_utils, etc.)
dbt deps

# Seed reference data (error code mapping)
dbt seed

# Run all models (Bronze → Silver → Gold)
dbt run

# Run only staging models
dbt run --select staging.*

# Run only marts (Gold)
dbt run --select marts.*

# Run incrementally (only new data)
dbt run --select fct_device_features

# Run tests
dbt test

# Run tests for a specific model
dbt test --select fct_device_features

# Generate documentation
dbt docs generate

# Serve documentation site
dbt docs serve --port 8081
# Open: http://localhost:8081
```

---

## dbt + Airflow Integration

Add dbt tasks to the Airflow DAG:

```python
from airflow.operators.bash import BashOperator

DBT_DIR = "D:/Sathish/ML_Device_Telemetry/device_telemetry_mlops/dbt_project"

# Replace Python bronze/silver/gold tasks with dbt
t_dbt_staging = BashOperator(
    task_id="dbt_staging",
    bash_command=f"cd {DBT_DIR} && dbt run --select staging.*",
    dag=dag,
)

t_dbt_intermediate = BashOperator(
    task_id="dbt_intermediate",
    bash_command=f"cd {DBT_DIR} && dbt run --select intermediate.*",
    dag=dag,
)

t_dbt_marts = BashOperator(
    task_id="dbt_marts",
    bash_command=f"cd {DBT_DIR} && dbt run --select marts.*",
    dag=dag,
)

t_dbt_test = BashOperator(
    task_id="dbt_test",
    bash_command=f"cd {DBT_DIR} && dbt test",
    dag=dag,
)

# DAG flow: ingest → dbt staging → dbt intermediate → dbt marts → dbt test → ML training
t_ingest >> t_dbt_staging >> t_dbt_intermediate >> t_dbt_marts >> t_dbt_test >> t_predict
```

Updated pipeline with dbt:
```
06:00 — ADF/Airflow ingests raw data → ADLS raw/
06:02 — dbt run --select staging.*       (Bronze → Silver)
06:04 — dbt run --select intermediate.*  (Silver → Joins)
06:06 — dbt run --select marts.*         (Gold features, INCREMENTAL)
06:07 — dbt test                          (quality gates)
06:08 — Python: PS-1 to PS-5 predictions (read from dbt marts)
06:10 — Drift check, retrain decision
```

---

## dbt vs Python Notebooks — What Replaces What

| Current (Python) | With dbt | Why dbt is better |
|-----------------|----------|-------------------|
| `01_bronze_layer.py` | `stg_telemetry.sql` + `stg_error_logs.sql` | SQL is clearer for transformations, auto-dedup with `qualify` |
| `02_silver_layer.py` | `stg_*.sql` models | Range validation in SQL, declarative not imperative |
| `03_gold_layer.py` | `int_*.sql` + `fct_*.sql` | Rolling averages as window functions, incremental processing |
| `04_feature_store.py` | `fct_device_features.sql` | Incremental materialization, automatic partitioning |
| `run_data_quality.py` (Great Expectations) | `_marts.yml` tests | Inline with models, no separate tool |
| N/A | `dbt docs serve` | Auto-generated lineage DAG + column docs |

**What dbt does NOT replace:**
- ML training notebooks (05-09) → Stay as Python
- Drift detection (Evidently AI) → Stay as Python
- API serving (FastAPI) → Stay as Python
- Daily pipeline orchestration → Stay as Airflow

---

## dbt on Azure Databricks

```yaml
# profiles.yml for Databricks

device_telemetry:
  target: prod
  outputs:
    prod:
      type: databricks
      host: "adb-1234567890.azuredatabricks.net"
      http_path: "/sql/1.0/warehouses/abc123"
      token: "{{ env_var('DBT_DATABRICKS_TOKEN') }}"
      catalog: unity_catalog        # Unity Catalog
      schema: gold
      threads: 8
```

```powershell
# Run dbt against Databricks
export DBT_DATABRICKS_TOKEN="dapi_xxxxx"
dbt run --target prod
dbt test --target prod
```

---

## Quick Reference

| Action | Command |
|--------|---------|
| Install dbt (DuckDB) | `pip install dbt-duckdb` |
| Install dbt (Databricks) | `pip install dbt-databricks` |
| Initialize project | `dbt init device_telemetry` |
| Check connection | `dbt debug` |
| Run all models | `dbt run` |
| Run staging only | `dbt run --select staging.*` |
| Run incrementally | `dbt run --select fct_device_features` |
| Run tests | `dbt test` |
| Generate docs | `dbt docs generate && dbt docs serve --port 8081` |
| View lineage | http://localhost:8081 (after `dbt docs serve`) |
| Seed reference data | `dbt seed` |
| Clean build artifacts | `dbt clean` |
| Install packages | `dbt deps` |
