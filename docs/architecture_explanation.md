# Device Telemetry MLOps - Architecture & Problem Statement Details

## Domain Context

**London Metro Contactless Reader System** — 200+ Cubic/Thales/Scheidt-Bachmann reader devices across 20 stations processing contactless card taps for entry/exit gates. Devices generate daily telemetry (signal, temperature, response times, errors) that needs proactive monitoring.

---

## Problem Statements Explained

### PS-1: Failure Prediction (RF, XGBoost, CatBoost)
**Goal:** Predict if a device will fail in the next 3 days.
**Why:** Proactive replacement prevents gate closures and passenger delays.
**Approach:**
- Binary classification: failure_next_3d (0/1)
- 3 models compared: Random Forest (ensemble bagging), XGBoost (gradient boosting), CatBoost (ordered boosting)
- Class imbalance handled via scale_pos_weight / balanced class weights
- Champion model selected by AUC-ROC

### PS-2: Error Pattern Recognition (Apriori, Markov)
**Goal:** Discover which errors co-occur and which errors lead to other errors.
**Why:** Understanding error cascades enables targeted firmware fixes and preventive actions.
**Approach:**
- **Apriori:** Each device-day is a "transaction" of error codes. Frequent itemsets and association rules reveal co-occurring errors (e.g., NFC_TIMEOUT + NETWORK_LOSS appear together with high lift).
- **Markov Chain:** Build transition matrix from error sequences. Stationary distribution reveals long-run error likelihoods. Identifies cascade paths (e.g., SENSOR_MALFUNCTION → FIRMWARE_CRASH).

### PS-3: Root Cause Analysis (SHAP, Causal Inference)
**Goal:** Identify which factors most contribute to device failures.
**Why:** Guides engineering decisions (firmware updates, hardware specs, maintenance schedules).
**Approach:**
- **SHAP (TreeExplainer):** Computes Shapley values for each feature's contribution to predictions. Global importance (mean |SHAP|) + local explanations per device.
- **Causal Inference (DoWhy):** Estimates Average Treatment Effect (ATE) of binarized features on failure. Uses backdoor criterion + propensity score matching.

### PS-4: Anomaly Detection (Isolation Forest, SPC)
**Goal:** Detect abnormal device behavior in real-time.
**Why:** Anomalies caught early prevent cascading failures and SLA breaches.
**Approach:**
- **Isolation Forest:** Unsupervised anomaly detection. Devices isolated quickly (fewer splits) are anomalous. Contamination set to 8%.
- **SPC Control Charts:** UCL/LCL (3σ) computed from 7-day baseline. Western Electric rules applied. Violations flagged for immediate attention.

### PS-5: SLA Risk Prediction (Weibull, Cox PH, RUL)
**Goal:** Estimate when a device will fail and whether SLA will be breached.
**Why:** SLA compliance (4h/8h/24h resolution targets) directly impacts contractual penalties.
**Approach:**
- **Weibull Distribution:** Parametric survival model. Shape parameter (ρ) indicates failure pattern: ρ>1 = wear-out, ρ<1 = infant mortality.
- **Cox Proportional Hazards:** Semi-parametric model with device covariates. Hazard ratios quantify how each factor affects failure risk.
- **RUL Estimation:** Conditional survival probability used to estimate remaining days until 50% failure probability.

---

## MLOps Components

### MLflow
- **Tracking:** All 5 PS experiments logged with parameters, metrics, artifacts
- **Registry:** Champion model versioned and tagged
- **Backend:** SQLite (local), easily portable to remote tracking server

### Evidently AI
- **Data Drift:** KS test (numeric) and chi-square (categorical) per feature
- **Threshold:** >30% features drifted triggers retraining
- **Reports:** Interactive HTML dashboards

### Great Expectations
- **Bronze:** Schema validation, null checks, uniqueness
- **Silver:** Range validation, type correctness
- **Gold:** Distribution checks, feature completeness, no infinities

### Prometheus + Grafana
- **Metrics:** Prediction counts, latency histograms, error rates
- **Dashboards:** Real-time monitoring of model performance
- **Alerts:** Configurable thresholds for SLA-critical metrics

---

## Incremental Processing Pattern

```
Day 1: Ingest → Clean → Quality Check → Stats → Anomaly Flag
Day 2: Ingest → Clean → Quality Check → Stats → Anomaly Flag
...
Day N: Ingest → Clean → Quality Check → Stats → Anomaly Flag
       └→ Periodic: Drift Check → Retrain Decision
```

Each day's data is processed independently, enabling near real-time monitoring without reprocessing historical data.

---

## Champion vs Challenger Model Strategy

```
Champion (Production)  ←── 100% traffic ──┐
                                            ├── Nginx / API Router
Challenger (Staging)   ←──   0% traffic ──┘

Compare metrics over time → If Challenger wins → Promote to Champion
```

| Aspect | Champion | Challenger |
|--------|----------|------------|
| Definition | Current best model serving predictions | New candidate being evaluated |
| MLflow Stage | `Production` | `Staging` |
| Traffic share | 100% (or 95% in Canary) | 0% (or 5% in Canary) |
| Example | XGBoost (AUC=0.964) | CatBoost / Random Forest |
| Promotion | Already promoted | Promoted if outperforms on next retrain |

In this project, PS-1 trains 3 models (RF, XGBoost, CatBoost), selects the best by AUC-ROC as **Champion**, and registers it as `Production` in MLflow. The others remain as **Challengers** that could be promoted during future retraining cycles.

---

## Deployment Strategies

### Full Monitoring Stack
- **Use for:** Development, testing, observability
- **Components:** 1 API + Prometheus + Grafana
- **Limitation:** Downtime during model updates (API restart needed)

### Blue-Green Deployment
- **Use for:** Routine model updates with zero downtime
- **How:** Run 2 containers (Blue=current, Green=new), flip traffic via Nginx
- **Rollback:** Instant (<30 seconds), just flip weights back

### Canary Deployment
- **Use for:** Risky model changes, gradual rollout
- **How:** Same as Blue-Green but with gradual traffic shift (5% → 20% → 50% → 100%)
- **Safety:** Monitor error rates and latency at each stage before increasing

---

## React Dashboard

The React dashboard provides a visual interface for all 5 problem statement outputs:

- **Overview tab:** KPI cards, risk distribution pie chart, SPC violations
- **PS-1 tab:** Champion metrics, model comparison, Champion vs Challenger
- **PS-2 tab:** Association rules, Markov transitions, severity escalations
- **PS-3 tab:** SHAP importance bar chart, causal inference, local explanations
- **PS-4 tab:** Anomaly vs normal differences, SPC limits, anomalous devices
- **PS-5 tab:** RUL histogram, risk tiers, Cox hazard ratios, SLA scores

The dashboard fetches data from the FastAPI backend via `/dashboard/*` endpoints, which read from the artifact files generated during training.
