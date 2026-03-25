# Device Telemetry MLOps — Architecture
## London Metro Contactless Reader Monitoring System

---

## Architecture Diagram (11-Layer Enterprise Pattern)

```
+========================================================================================+
|                    DEVICE TELEMETRY MLOPS — FULL ARCHITECTURE                            |
|                    London Metro Reader Monitoring (MARS Pattern)                          |
+========================================================================================+

 LAYER 1: DATA INGESTION
 +-----------+     +-----------+     +-----------+     +-----------+
 | IoT Hub / |     | Azure     |     | Event     |     | Azure     |
 | Event Hub |---->| Data      |---->| Grid      |---->| Function  |
 | (readers) |     | Factory   |     | (triggers)|     | (webhook) |
 +-----------+     +-----------+     +-----------+     +-----------+
  200 devices      7 pipelines       Pipeline events   MLflow relay
  ~500 rec/day     15-min CDC        Blob triggers      HMAC valid.
                   Watermark                            DevOps trigger
                       |
                       v
 LAYER 2: MEDALLION DATA LAKE (ADLS Gen2)
 +-------------+     +-------------+     +-------------+     +-----------+
 |   RAW       |     |   BRONZE    |     |   SILVER    |     |   GOLD    |
 |  (CSV/JSON) |---->|  (Delta)    |---->|  (Delta)    |---->|  (Delta)  |
 |             |     | Immutable   |     | Cleaned     |     | 80+ feat  |
 |  IoT stream |     | Partitioned |     | Deduped     |     | Rolling   |
 |  Error logs |     | + metadata  |     | Validated   |     | Delta     |
 |  Maint logs |     |             |     | Type-cast   |     | Cumulative|
 +-------------+     +-------------+     +-------------+     +-----------+
                                                                   |
  Lifecycle: Hot ---(90d)---> Cool ---(365d)---> Archive            |
                                                                   v
 LAYER 3: PROCESSING ENGINE (DATABRICKS)                    +-------------+
 +--------------------+--------------------+-----------+    | FEATURE     |
 | Cluster: ETL       | Cluster: Feat Eng  | Ad-hoc    |    | STORE       |
 | DS4_v2 (8c/28GB)   | DS4_v2 (8c/28GB)   | DS3_v2    |    | (Unity      |
 | Auto 2-8 workers   | Auto 2-6 workers   | 1-4 wrkrs |    |  Catalog)   |
 | Spot instances      | Quality gate >=97% | 30min     |    | Versioned   |
 | ~4h/day active      | Z-ordering, Delta  | timeout   |    | PS-specific |
 +--------------------+--------------------+-----------+    +-------------+
  Triggered by ADF     Silver -> Gold        Interactive          |
  Bronze writes        Feature engineering   Exploration          |
                                                                  v
 LAYER 4: ML TRAINING (AZURE ML + DATABRICKS)
 +=========================================================================+
 |                                                                         |
 |  +------------------+  +------------------+  +-------------------+      |
 |  | PS-1: FAILURE    |  | PS-2: ERROR      |  | PS-3: ROOT CAUSE  |      |
 |  | PREDICTION       |  | PATTERNS         |  | ANALYSIS          |      |
 |  |                  |  |                  |  |                   |      |
 |  | Random Forest    |  | Apriori Rules    |  | SHAP (Tree)       |      |
 |  | XGBoost (champ)  |  | Markov Chain     |  | DoWhy Causal      |      |
 |  | CatBoost         |  | Severity Escal.  |  | ATE Estimation    |      |
 |  |                  |  |                  |  |                   |      |
 |  | Target:          |  | Target:          |  | Target:           |      |
 |  | failure_next_3d  |  | Error co-occur   |  | Why failures      |      |
 |  | AUC > 0.90       |  | Transition probs |  | happen             |      |
 |  +------------------+  +------------------+  +-------------------+      |
 |                                                                         |
 |  +------------------+  +-------------------+                            |
 |  | PS-4: ANOMALY    |  | PS-5: SLA RISK    |                            |
 |  | DETECTION        |  | PREDICTION        |    Training Cluster:       |
 |  |                  |  |                   |    DS13_v2 (8c/56GB)       |
 |  | Isolation Forest |  | Weibull (shape/   |    Auto 0-8 nodes         |
 |  | SPC Charts (3s)  |  |   scale)          |    Daily 02:00 UTC        |
 |  |                  |  | Cox PH (hazard)   |    Low-priority           |
 |  | Target:          |  | RUL (remaining    |                            |
 |  | Abnormal devices |  |   useful life)    |    Accuracy Gates:        |
 |  | 8% contamination |  | SLA breach prob   |    PS-1: AUC > 0.90      |
 |  +------------------+  +-------------------+    PS-4: F1 > 0.85       |
 |                                                  PS-5: C-idx > 0.80    |
 +=========================================================================+
                              |
                              v
 LAYER 4b: MLFLOW MODEL REGISTRY
 +-------------------------------------------------------------------------+
 |  Experiment Tracking        Model Registry (Unity Catalog)              |
 |  +--------------------+     +------+------+------+------+------+       |
 |  | PS1_Failure   (3+) |     | PS-1 | PS-2 | PS-3 | PS-4 | PS-5 |       |
 |  | PS2_Error     (1+) |     |v1 v2 |v1    |v1    |v1 v2 |v1    |       |
 |  | PS3_RootCause (1+) |     |Prod  |Prod  |Prod  |Prod  |Prod  |       |
 |  | PS4_Anomaly   (1+) |     +------+------+------+------+------+       |
 |  | PS5_SLA       (1+) |                                                |
 |  | Drift_Detect  (1)  |     Champion -> Production                     |
 |  | Daily_Pipeline(N)  |     Challenger -> Staging                      |
 |  +--------------------+     Webhook -> CI/CD on promotion              |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 5: MODEL PACKAGING
 +-------------------------------------------------------------------------+
 |  Azure Container Registry (Premium)                                     |
 |  +------------+  +------------+  +------------+  +----------+           |
 |  | mars-base  |  | mars-ps1   |  | mars-ps4   |  | mars-api |           |
 |  | ubuntu22.04|  | xgboost    |  | iforest    |  | fastapi  |           |
 |  | python3.11 |  | catboost   |  | spc        |  | uvicorn  |           |
 |  | mlflow2.12 |  | shap       |  |            |  | prom-cli |           |
 |  +------------+  +------------+  +------------+  +----------+           |
 |                                                                         |
 |  Geo-replication | Content Trust | Trivy scan on push | 30 versions    |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 6: CI/CD (AZURE DEVOPS)
 +-------------------------------------------------------------------------+
 |                                                                         |
 |  +--------+    +---------+    +------------+    +--------------+        |
 |  | BUILD  |--->| TEST    |--->| DEPLOY     |--->| TRAFFIC      |        |
 |  |        |    |         |    | BLUE       |    | SWAP         |        |
 |  | Lint   |    | Unit    |    | Health chk |    | 0%->10% (5m) |        |
 |  | Docker |    | Integr. |    | Smoke test |    | 10%->50%(5m) |        |
 |  | Trivy  |    | Accuracy|    | Manual gate|    | 50%->100%    |        |
 |  | Push   |    | gates   |    |            |    | Auto-rollback|        |
 |  +--------+    +---------+    +------------+    +--------------+        |
 |                                                                         |
 |  4 repos: mars-mlops | mars-api | mars-ui | mars-infra (Terraform)     |
 |  ~80 pipeline runs/month | 2 parallel agents                           |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 7: REAL-TIME INFERENCE
 +-------------------------------------------------------------------------+
 |                                                                         |
 |   API Management (OAuth 2.0 + PKCE, Rate: 1K/min, Circuit breaker)     |
 |   +------------------------------------------------------------------+  |
 |   |                                                                  |  |
 |   |  +----------+  +----------+  +----------+  +----------+  +----+ |  |
 |   |  | EP: PS-1 |  | EP: PS-2 |  | EP: PS-3 |  | EP: PS-4 |  |PS-5| |  |
 |   |  | Failure  |  | Errors   |  | Root     |  | Anomaly  |  |SLA | |  |
 |   |  | DS4_v2   |  | DS4_v2   |  | Cause    |  | DS4_v2   |  |Risk| |  |
 |   |  | Auto 2-6 |  | Auto 2-6 |  | DS4_v2   |  | Auto 2-6 |  |    | |  |
 |   |  +----------+  +----------+  +----------+  +----------+  +----+ |  |
 |   |                                                                  |  |
 |   +------------------------------------------------------------------+  |
 |        |                                                                |
 |        v                                                                |
 |   +------------------+                                                  |
 |   | Redis Cache (P1) |  TTL 5min | 85% hit rate | 6GB | HA replicas   |
 |   +------------------+                                                  |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 8: APPLICATION TIER
 +-------------------------------------------------------------------------+
 |                                                                         |
 |  +----------------------------+  +----------------------------+         |
 |  | App Service: API           |  | App Service: UI            |         |
 |  | P2v3 (2c/8GB) Linux       |  | P2v3 (2c/8GB) Linux       |         |
 |  | Blue-Green slots           |  | Blue-Green slots           |         |
 |  | FastAPI Python 3.11       |  | React 18.2 + TypeScript    |         |
 |  | 5 microservices            |  | SHAP visualization         |         |
 |  | Auto 2-10 replicas        |  | 6 dashboard tabs           |         |
 |  |                            |  | Auto 2-4 replicas          |         |
 |  | Endpoints:                 |  |                            |         |
 |  | /predict/failure           |  | Tabs:                      |         |
 |  | /predict/anomaly           |  | Overview | PS-1 | PS-2     |         |
 |  | /predict/sla-risk          |  | PS-3 | PS-4 | PS-5         |         |
 |  | /predict/batch/all         |  |                            |         |
 |  | /health | /metrics         |  |                            |         |
 |  +----------------------------+  +----------------------------+         |
 |                                                                         |
 |  +----------------------------+                                         |
 |  | Azure SQL Database         |  Gen Purpose | 8 vCores | 32GB | 1TB   |
 |  | Predictions, sessions,     |  Geo-rep | TDE | 35d backup            |
 |  | audit, config tables       |                                         |
 |  +----------------------------+                                         |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 9: SECURITY & NETWORKING
 +-------------------------------------------------------------------------+
 |                                                                         |
 |  VNet: 10.224.0.0/21 (2,048 IPs) — 8 Subnets                          |
 |  +--------+--------+--------+--------+--------+--------+------+------+ |
 |  |appsvc  | apim   | priv-  | data-  | ml-    | dbx-   | dbx- |net-  | |
 |  |int     |        | endpts | svc    | compute| host   | cont |edge  | |
 |  |/24     | /24    | /24    | /24    | /23    | /26    | /26  | /24  | |
 |  +--------+--------+--------+--------+--------+--------+------+------+ |
 |                                                                         |
 |  +--------+  +--------+  +--------+  +--------+  +--------+            |
 |  |Firewall|  |Bastion |  |VPN Gw  |  |NAT Gw  |  |Key     |            |
 |  |DNAT/NAT|  |No pub  |  |Active- |  |Outbound|  |Vault   |            |
 |  |Threat  |  |RDP/SSH |  |Standby |  |SNAT    |  |Premium |            |
 |  |Intel   |  |File    |  |BGP     |  |64K conn|  |HSM     |            |
 |  +--------+  |xfer    |  +--------+  +--------+  |Purge   |            |
 |               +--------+                          |protect |            |
 |                                                   +--------+            |
 |  12 Private Endpoints | 8 Private DNS Zones | NSGs (deny-all default)  |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 10: MONITORING & OPERATIONS
 +-------------------------------------------------------------------------+
 |                                                                         |
 |  +------------------+  +------------------+  +-------------------+      |
 |  | App Insights     |  | Log Analytics    |  | Managed Grafana   |      |
 |  | Adaptive sampl.  |  | KQL queries      |  | 25+ dashboards    |      |
 |  | 90d retention    |  | 90d | 10GB/day   |  | Azure AD SSO      |      |
 |  | Custom metrics:  |  | All services log |  |                   |      |
 |  | - accuracy       |  | NSG flow logs    |  | Dashboards:       |      |
 |  | - latency        |  | FW logs          |  | - ML health       |      |
 |  | - cache_hit      |  | Diagnostics on   |  | - Pipeline SLAs   |      |
 |  | - drift_score    |  |   every resource  |  | - Infrastructure  |      |
 |  +------------------+  +------------------+  | - Cost tracking   |      |
 |                                               +-------------------+      |
 |  Azure Monitor Alerts: 50+ rules, 4 severity tiers                     |
 |  +------+----------+-----------+--------------------------------------+ |
 |  | P1   | 5 min    | PagerDuty | API down, model fail, >20 critical  | |
 |  | P2   | 15 min   | Email     | Error >1%, drift >30%, latency >1s  | |
 |  | P3   | 1 hour   | Slack     | Quality <90%, training fail         | |
 |  | P4   | Next day | Email     | Budget >80%, idle cluster           | |
 |  +------+----------+-----------+--------------------------------------+ |
 +-------------------------------------------------------------------------+
                              |
                              v
 LAYER 11: DISASTER RECOVERY
 +-------------------------------------------------------------------------+
 |  Recovery Services Vault (Standard | GRS)                               |
 |  SQL: daily backup, 35d retention | ADLS: weekly, 12 weeks             |
 +-------------------------------------------------------------------------+

+========================================================================================+
```

---

## Domain Context

**London Metro Contactless Reader System** — 200+ Cubic/Thales/Scheidt-Bachmann reader devices across 20 stations processing contactless card taps for entry/exit gates. Devices generate daily telemetry (signal, temperature, response times, errors) that needs proactive monitoring to prevent gate closures and passenger delays.

**Data Volume:** ~500 records/day (200 devices), growing to 6,000/month with error logs and maintenance records.

---

## 5 Problem Statements — Detailed

### PS-1: Failure Prediction (RF, XGBoost, CatBoost)

**Goal:** Predict if a device will fail in the next 3 days.

**Why:** Proactive replacement prevents gate closures and passenger delays. A single gate failure during rush hour affects ~2,000 passengers.

**Approach:**
- Binary classification: `failure_next_3d` (0 = no failure, 1 = will fail)
- 3 models compared: Random Forest (ensemble bagging), XGBoost (gradient boosting), CatBoost (ordered boosting with native categorical support)
- Class imbalance handled via `scale_pos_weight` / balanced class weights (~5% failure rate)
- Champion model selected by AUC-ROC (must exceed 0.90)
- Features: 30+ including rolling averages, deltas, cumulative errors, health score

**Output per device:**
```
device_id: LMR_0042
failure_probability: 0.73
risk_tier: HIGH
recommended_action: "Schedule corrective maintenance within 48h"
```

### PS-2: Error Pattern Recognition (Apriori, Markov Chain)

**Goal:** Discover which errors co-occur and which errors cascade into other errors.

**Why:** Understanding error cascades enables targeted firmware fixes and preventive actions. If NFC_TIMEOUT always leads to FIRMWARE_CRASH, fix the timeout root cause first.

**Approach:**
- **Apriori (Association Rules):** Each device-day is a "transaction" of error codes. Frequent itemsets reveal co-occurring errors. Rules with support > 5%, confidence > 50%, lift > 1.5 are significant.
  - Example: `{NFC_TIMEOUT, NETWORK_LOSS}` → `{FIRMWARE_CRASH}` (confidence: 72%, lift: 3.2)
- **Markov Chain (Transition Matrix):** Build transition probability matrix from error sequences per device. Stationary distribution reveals long-run error likelihoods. Identifies cascade paths:
  - `SENSOR_MALFUNCTION` → `FIRMWARE_CRASH` (p = 0.35)
  - `LOW_BATTERY` → `REBOOT` → `NFC_TIMEOUT` (escalation chain)

**Output:**
```
Top rule: {NFC_TIMEOUT} + {NETWORK_LOSS} → {DEVICE_REBOOT} (conf: 0.68)
Escalation paths: 3,011 severity escalations detected
Most dangerous: SENSOR_MALFUNCTION (leads to CRITICAL in 35% of cases)
```

### PS-3: Root Cause Analysis (SHAP, Causal Inference)

**Goal:** Identify which factors most contribute to device failures and quantify their causal effect.

**Why:** Guides engineering decisions — should we improve firmware, replace hardware, or adjust maintenance schedules? Correlation is not causation.

**Approach:**
- **SHAP (TreeExplainer):** Computes Shapley values for each feature's contribution to the PS-1 champion model's predictions.
  - Global importance: mean |SHAP| across all devices → ranks features
  - Local explanation: per-device breakdown → "This device is predicted to fail because signal dropped 15dBm in 3 days"
  - Dependence plots: how feature values map to SHAP contributions
- **Causal Inference (DoWhy):** Estimates Average Treatment Effect (ATE) of binarized features on failure probability. Uses backdoor criterion + propensity score matching.
  - Example: "Low signal (< 60 dBm) causally increases failure probability by 12 percentage points"

**Output per device:**
```
device_id: LMR_0042
primary_cause: "Low signal strength" (SHAP = +0.23)
secondary: "High cumulative errors" (SHAP = +0.18)
causal_ATE: signal < 60dBm increases failure by 12%
```

### PS-4: Anomaly Detection (Isolation Forest, SPC)

**Goal:** Detect abnormal device behavior in real-time, before failures occur.

**Why:** Anomalies caught early prevent cascading failures and SLA breaches. A device showing unusual patterns today may fail in 3-7 days.

**Approach:**
- **Isolation Forest:** Unsupervised anomaly detection. Devices isolated quickly (fewer random splits) are anomalous. Contamination set to 8% (expected anomaly rate). Features: signal, temp, response time, latency, power, memory, CPU, errors, tap success, uptime, health.
- **SPC Control Charts:** UCL/LCL (mean +/- 3 sigma) computed from 7-day rolling baseline per feature. Western Electric rules applied:
  - Rule 1: Point outside 3-sigma → violation
  - Rule 2: 2 of 3 consecutive points outside 2-sigma → warning

**Output per device:**
```
device_id: LMR_0042
is_anomaly: true
anomaly_score: -0.32 (more negative = more anomalous)
spc_violations: temperature_c (above UCL: 55.2 > 52.8)
```

### PS-5: SLA Risk Prediction (Weibull, Cox PH, RUL)

**Goal:** Estimate when a device will fail and the probability of SLA breach.

**Why:** SLA compliance targets (4h response for CRITICAL, 8h for HIGH, 24h for MEDIUM) directly impact contractual penalties. Missing an SLA costs ~$5,000 per incident.

**Approach:**
- **Weibull Distribution:** Parametric survival model. Two parameters:
  - Lambda (scale): characteristic life in days
  - Rho (shape): failure pattern — rho > 1 = wear-out (failures increase with age), rho < 1 = infant mortality
  - Reliability at day T: R(T) = exp(-(T/lambda)^rho)
- **Cox Proportional Hazards:** Semi-parametric model with device covariates (age, manufacturer, error history, health score). Hazard ratios quantify how each factor affects failure risk:
  - HR = 2.3 for old devices (age > 1000 days) means 2.3x higher failure risk
- **RUL Estimation:** Conditional survival probability used to estimate remaining days until 50% failure probability. Devices with RUL < 14 days → CRITICAL tier.

**Output per device:**
```
device_id: LMR_0042
rul_median_days: 12
sla_risk_score: 78.5 (out of 100)
risk_tier: CRITICAL
recommended_action: "EMERGENCY: Schedule immediate replacement"
```

---

## MLOps Components

### Medallion Architecture (Bronze → Silver → Gold)

```
RAW DATA                    BRONZE                    SILVER                    GOLD
+----------+               +-----------+              +-----------+             +-----------+
| CSV/JSON |   Ingest      | Parquet   |   Clean     | Parquet   |  Feature    | Parquet   |
| IoT data |-------------->| Immutable |------------>| Deduped   |  Engineer   | 80+ cols  |
| ~500/day |   +metadata   | Date-part |   +validate | Type-cast |------------>| Rolling   |
+----------+   +watermark  +-----------+   +range chk| No nulls  |             | Delta     |
               +CDC detect                            +-----------+             | Cumulative|
                                                                               | Health    |
                                                                               +-----------+
```

### MLflow (Experiment Tracking + Model Registry)

| Component | Local | Azure |
|-----------|-------|-------|
| Tracking URI | `sqlite:///mlruns/mlflow.db` | Databricks built-in |
| Experiments | 7 (PS1-PS5 + Drift + Daily) | Same |
| Registry | Local MLflow Registry | Unity Catalog |
| Stages | None → Staging → Production → Archived | Same |
| Access | `http://localhost:5000` | Databricks workspace UI |

### Evidently AI (Drift Detection)

- **Statistical tests:** KS test (numeric features), Chi-square (categorical)
- **Threshold:** >30% features drifted → trigger automatic retraining
- **Reports:** Interactive HTML dashboards (data drift + data quality)
- **Schedule:** Daily after predictions, compare last 7 days vs training data

### Great Expectations (Data Quality)

| Layer | Checks | Gate |
|-------|--------|------|
| Bronze | Schema validation, null primary keys, row count > 0 | Must pass to proceed |
| Silver | Range validation (age 0-2000, temp -10 to 80), type correctness, no duplicates | Quality >= 97% |
| Gold | Feature completeness, no infinities/NaN, label distribution (~5% failure rate) | Must pass to proceed |

### Watermark & CDC (Change Data Capture)

```
WATERMARK (watermark.json):
"What was the LAST data I processed?"
  telemetry: last_date=2025-01-15, hash=abc123
  → New data for 2025-01-16? → PROCESS
  → Same data for 2025-01-15, same hash? → SKIP
  → Same date, different hash? → CDC UPDATE

CDC (cdc_log.json):
Compare new data vs existing Silver:
  INSERTS: 480 new records (new device+date combinations)
  UPDATES: 15 changed records (same key, values corrected)
  DELETES: 5 removed records (device decommissioned)
```

---

## Daily Pipeline Flow

```
06:00 UTC ── New Data Arrives (~500 records)
  |
  +-- [Step 1] Watermark Check + Bronze Ingestion (CDC)
  |     Only process data AFTER last watermark
  |     Detect inserts / updates / deletes
  |
  +-- [Step 2] Silver Cleaning (merge changes)
  |     Deduplicate, validate, type-cast
  |     Apply CDC: insert new, update changed, remove deleted
  |
  +-- [Step 3] Gold Feature Engineering
  |     7-day rolling, deltas, cumulative, health score
  |     Recompute on last 30 days of Silver data
  |
  +-- [Step 4] ALL 5 PS Predictions
  |     +-- PS-1: failure_probability per device
  |     +-- PS-2: error co-occurrences + escalations (fleet-level)
  |     +-- PS-3: SHAP explanation for flagged devices
  |     +-- PS-4: anomaly_label + SPC violations per device
  |     +-- PS-5: sla_risk_score + rul_days per device
  |
  +-- [Step 5] Drift Check (Evidently AI)
  |     Compare last 7 days vs training data
  |     If drift > 30% → flag for retraining
  |
  +-- [Step 6] Retrain Check
  |     Every 15 days OR drift > 30% OR manual trigger
  |     Retrain all 5 PS on FULL accumulated data
  |     Register new champions in MLflow
  |     Trigger CI/CD for deployment
  |
  +-- [Step 7] Log to MLflow
        Daily_Pipeline experiment: records ingested,
        predictions made, anomalies, drift share
```

---

## Champion vs Challenger Strategy

```
                    +---------+
                    |  MLflow  |
                    | Registry |
                    +----+----+
                         |
           +-------------+-------------+
           |                           |
     +-----+------+             +------+------+
     |  CHAMPION   |             | CHALLENGER  |
     |  (v2)       |             | (v3)        |
     |             |             |             |
     | Stage:      |             | Stage:      |
     | Production  |             | Staging     |
     | Traffic:    |             | Traffic:    |
     | 100% (or    |             | 0% (or 5%  |
     |  95% canary)|             |  canary)    |
     +-----+------+             +------+------+
           |                           |
           +-------------+-------------+
                         |
                    +----+----+
                    |  Compare |
                    |  Metrics |
                    +----+----+
                         |
                    If Challenger
                    wins on AUC/F1
                         |
                    Promote to
                    Production
```

| Aspect | Champion | Challenger |
|--------|----------|------------|
| Definition | Current best model serving predictions | New candidate being evaluated |
| MLflow Stage | `Production` | `Staging` |
| Traffic share | 100% (or 95% in Canary) | 0% (or 5% in Canary) |
| Example | XGBoost v2 (AUC=0.964) | CatBoost v3 (AUC=0.958) |
| Promotion | Already promoted | Promoted if outperforms on next retrain |

---

## Deployment Strategies

### Blue-Green (Zero Downtime)

```
BEFORE:
  Nginx ──> Blue (v1, 100%) | Green (idle)

DEPLOY:
  Nginx ──> Blue (v1, 100%) | Green (v2, testing)
  Health check Green: /health → OK
  Smoke test: sample prediction → OK

SWITCH:
  Nginx ──> Blue (v1, 0%)   | Green (v2, 100%)
  Rollback available in <30 seconds
```

### Canary (Gradual Rollout)

```
Stage 1:  Blue (v1) 95%  | Green (v2)  5%   -- monitor 5 min
          Error rate < 1%? Latency OK? --> proceed
Stage 2:  Blue (v1) 50%  | Green (v2) 50%   -- monitor 5 min
          Metrics stable? --> proceed
Stage 3:  Blue (v1)  0%  | Green (v2) 100%  -- full promotion
          Auto-rollback if error > 1% or latency > 2x baseline
```

### When to Use What

| Scenario | Strategy | Decision |
|----------|----------|----------|
| Routine 15-day retrain, similar metrics | **Blue-Green** | Automatic (scripted) |
| Major model change (new algorithm/features) | **Canary** | Manual (ML engineer monitors) |
| Emergency retrain (drift > 30%) | **Blue-Green** | Automatic |
| First deployment | **Simple** (single instance) | Manual |

---

## React Dashboard

6 tabs displaying all 5 PS outputs with interactive charts:

```
+========================================================================+
|  Device Telemetry MLOps Dashboard                                       |
|  [Overview] [PS-1] [PS-2] [PS-3] [PS-4] [PS-5]                        |
+========================================================================+
|                                                                        |
|  OVERVIEW TAB:                                                         |
|  +----------+ +----------+ +----------+ +----------+ +----------+      |
|  | PS-1     | | PS-2     | | PS-3     | | PS-4     | | PS-5     |      |
|  | 3 HIGH   | | 24 rules | | Top:     | | 8% anom  | | 12 CRIT  |      |
|  | RISK     | | 39 trans | | signal   | | 114 SPC  | | Avg RUL  |      |
|  | devices  | | itions   | | strength | | violat.  | | 22 days  |      |
|  +----------+ +----------+ +----------+ +----------+ +----------+      |
|                                                                        |
|  PS-1 TAB: Champion AUC=0.96 | Confusion Matrix | Feature Importance  |
|  PS-2 TAB: Rules Table | Markov Heatmap | Escalation Paths             |
|  PS-3 TAB: SHAP Bar Chart | Causal Results | Device Explanation        |
|  PS-4 TAB: Anomaly Scatter | SPC Charts | Top Anomalous Devices       |
|  PS-5 TAB: RUL Histogram | Risk Pie | Cox Hazard Ratios | SLA Scores  |
+========================================================================+
```

The dashboard fetches data from FastAPI backend endpoints:
- `GET /dashboard/summary` → Overview KPIs
- `GET /dashboard/ps1` through `/dashboard/ps5` → Per-PS details

---

## Monitoring (64 Metrics)

| Category | Count | Examples |
|----------|-------|---------|
| API / Request | 5 | predictions_total, latency, errors, http_requests |
| Model Performance | 6 | failure_prob distribution, anomaly scores, SLA risk, RUL |
| Risk / Business | 4 | risk_tier_total, devices_at_risk, mean_health_score |
| System / Model | 3 | model_loaded, load_time, feature_count |
| Data / Drift | 3 | drift_share, quality_pass_rate, retraining_triggered |
| Process (auto) | 7 | memory, CPU, GC, file descriptors |
| Azure Auto-collected | 12 | requests, exceptions, dependencies, availability |
| Azure Infrastructure | 10 | Container CPU/memory, storage transactions, cluster utilization |
| ML-specific (MLflow) | 14 | AUC, F1, SHAP, Weibull params, Cox C-index, RUL, drift share |
| **Total** | **64** | See MONITORING_GUIDE.md for full list |

---

## Project Structure

```
device_telemetry_mlops/
├── data/
│   ├── generate_sample_data.py        # Synthetic data generator
│   ├── raw/                            # CSV source files
│   ├── bronze/                         # Raw Parquet (immutable, partitioned)
│   ├── silver/                         # Cleaned Parquet
│   ├── gold/                           # Feature-engineered dataset (80+ features)
│   ├── feature_store/                  # Versioned features + schema
│   ├── artifacts/ps1-ps5/              # Model files, plots, metrics per PS
│   ├── predictions/                    # Daily prediction outputs
│   ├── drift_reports/                  # Evidently AI HTML reports
│   ├── quality_reports/                # Great Expectations results
│   ├── watermark.json                  # Watermark tracking
│   ├── cdc_log.json                    # CDC audit trail
│   └── training_log.json              # Retraining history
├── notebooks/
│   ├── 01_bronze_layer.py              # Raw ingestion (Parquet, partitioned)
│   ├── 02_silver_layer.py              # Cleaning, dedup, validation
│   ├── 03_gold_layer.py                # Feature engineering (80+ features)
│   ├── 04_feature_store.py             # Feature store creation
│   ├── 05_ps1_failure_prediction.py    # RF, XGBoost, CatBoost
│   ├── 06_ps2_error_pattern.py         # Apriori, Markov Chain
│   ├── 07_ps3_root_cause.py            # SHAP, DoWhy Causal Inference
│   ├── 08_ps4_anomaly_detection.py     # Isolation Forest, SPC
│   ├── 09_ps5_sla_risk.py              # Weibull, Cox PH, RUL
│   └── 10_drift_detection.py           # Evidently AI
├── scripts/
│   ├── daily_scheduled_pipeline.py     # Daily pipeline (watermark + CDC + all 5 PS)
│   ├── register_models.py              # MLflow model registration
│   ├── run_data_quality.py             # Great Expectations
│   └── generate_traffic.py             # Load testing
├── api/
│   ├── main.py                         # FastAPI (predict + dashboard endpoints)
│   └── Dockerfile                      # Container image
├── dashboard/                          # React UI (Vite + Recharts)
├── monitoring/                         # Docker Compose (Prometheus + Grafana)
├── terraform/                          # Azure IaC (12 .tf files)
├── .github/workflows/ci-cd.yml        # GitHub Actions pipeline
├── docs/
│   ├── Architecture.md                 # This file
│   ├── AZURE_DEPLOYMENT.md             # 11-layer Azure deployment guide
│   ├── TERRAFORM_GUIDE.md              # Terraform beginner walkthrough
│   ├── MONITORING_GUIDE.md             # All 64 metrics reference
│   ├── DAILY_OPERATIONS.md             # Daily pipeline & retraining guide
│   └── SPRINT_PLAN.md                  # 6-sprint development plan
├── run_pipeline.py                     # Full pipeline (13 steps)
├── run_daily.bat                       # Windows Task Scheduler (6 AM)
├── start_api.bat                       # Auto-start API on login
├── HOW_TO_RUN.md                       # Step-by-step execution guide
├── HOW_TO_RERUN.md                     # Daily quick-start guide
└── requirements.txt                    # Python dependencies
```
