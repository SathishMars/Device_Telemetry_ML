# CI/CD & Retraining Guide
## Device Telemetry MLOps

---

## CI/CD Pipeline Overview

```
Developer pushes code to main
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    GitHub Actions CI/CD                         │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────┐   ┌──────────────┐   ┌────────────┐             │
│  │  LINT   │──▶│ TEST PIPELINE│──▶│TEST MODELS │             │
│  │ black   │   │ bronze/silver│   │ PS-1 to 5  │             │
│  │ flake8  │   │ gold/quality │   │ validate   │             │
│  └─────────┘   └──────────────┘   └─────┬──────┘             │
│                                          │                     │
│                  ┌───────────────────────┬┘                    │
│                  ▼                       ▼                     │
│          ┌────────────┐         ┌──────────────┐              │
│          │ TEST API   │         │TEST DASHBOARD│              │
│          │ pytest     │         │ npm build    │              │
│          └─────┬──────┘         └──────┬───────┘              │
│                │                       │                      │
│                └──────────┬────────────┘                      │
│                           ▼                                   │
│                  ┌─────────────────┐                          │
│                  │ BUILD & PUSH    │  ← Only on main branch   │
│                  │ Docker → ACR    │                          │
│                  └────────┬────────┘                          │
│                           │                                   │
│              ┌────────────┼────────────┐                      │
│              ▼                         ▼                      │
│     ┌─────────────────┐     ┌──────────────────┐             │
│     │ DEPLOY API      │     │ DEPLOY DASHBOARD │             │
│     │ Container Apps  │     │ Static Web Apps  │             │
│     └─────────────────┘     └──────────────────┘             │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

---

## What Triggers the CI/CD Pipeline

| Trigger | What Happens | Jobs Run |
|---------|-------------|----------|
| **Push to `main`** | Full CI/CD: lint → test → build → deploy | All 8 jobs |
| **Pull Request to `main`** | CI only: lint → test (no deploy) | Jobs 1-5 only |
| **Push to docs/ or *.md** | Nothing (path ignored) | Skipped |

---

## GitHub Secrets Required

Set these in GitHub → Repository → Settings → Secrets → Actions:

| Secret | Where to get it | Used by |
|--------|----------------|---------|
| `AZURE_CREDENTIALS` | `az ad sp create-for-rbac --name "github-actions" --role contributor --scopes /subscriptions/{id}` | Azure login |
| `AZURE_STATIC_WEB_APPS_TOKEN` | Azure Portal → Static Web Apps → Manage deployment token | Dashboard deploy |

### Create Azure Service Principal

```powershell
az ad sp create-for-rbac \
  --name "github-device-telemetry" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/rg-device-telemetry-dev \
  --sdk-auth
```

Copy the JSON output → paste as `AZURE_CREDENTIALS` secret in GitHub.

---

## When is Retraining Required?

### Scenario 1: Data Drift Detected (Automated)

```
Daily at 6 AM UTC
    │
    ▼
Check Drift (Evidently AI)
    │
    ├── Drift share < 30% → No retraining → Log & skip
    │
    └── Drift share ≥ 30% → RETRAIN
            │
            ▼
        Retrain all 5 PS models
            │
            ▼
        Validate (AUC > 0.80, F1 > 0.30)
            │
            ▼
        Deploy with Canary (10% traffic)
            │
            ▼
        Monitor → Promote to 100% if healthy
```

**What causes data drift:**
- Seasonal changes (summer heat → different temperature readings)
- New device firmware rolled out (changes telemetry patterns)
- New stations/routes added (different traffic patterns)
- Hardware aging (gradual degradation patterns shift)

### Scenario 2: Performance Degradation

| Metric | Threshold | Action |
|--------|-----------|--------|
| AUC-ROC drops below 0.85 | Monitor weekly | Retrain with recent data |
| F1 Score drops below 0.40 | Alert immediately | Investigate + retrain |
| False positive rate > 20% | Alert | Check feature quality, retrain |
| Prediction latency P99 > 1s | Alert | Optimize model, not retrain |

**How to detect:**
- Evidently AI monitors prediction distribution
- Compare predictions vs actual outcomes (when maintenance data arrives)
- Grafana alerts on metric thresholds

### Scenario 3: New Data Available

| Situation | Action |
|-----------|--------|
| New device type added (new manufacturer) | Retrain — model hasn't seen this type |
| New error codes introduced | Retrain PS-2 (error patterns) |
| SLA targets changed | Retrain PS-5 (different thresholds) |
| 3+ months of new production data | Retrain all — fresher patterns |

### Scenario 4: Model Bug or Feature Change

| Situation | Action |
|-----------|--------|
| Bug found in feature engineering | Fix code → retrain → redeploy |
| New feature added to Gold layer | Retrain to include new feature |
| Feature removed or renamed | Retrain — old model expects old features |
| Library version upgrade (xgboost, catboost) | Validate old model still works, retrain if not |

### Scenario 5: Scheduled Retraining

Even without drift, retrain periodically as a best practice:

| Frequency | Reason |
|-----------|--------|
| **Weekly** | PS-4 Anomaly Detection (SPC baselines need updating) |
| **Monthly** | PS-1, PS-2, PS-3 (model freshness) |
| **Quarterly** | PS-5 Survival Analysis (Weibull parameters shift with aging fleet) |

### Scenario 6: Manual Trigger

Trigger retraining manually from GitHub Actions UI:

1. Go to **Actions** tab → **Model Retraining Pipeline**
2. Click **Run workflow**
3. Select reason: `manual`, `drift_detected`, `performance_degradation`, `new_data_available`, `model_bug_fix`
4. Optionally check **Force retrain** to skip drift check

---

## Retraining Pipeline Flow

```
┌──────────────────┐
│  TRIGGER          │ ← Schedule (daily 6AM) / Manual / Drift alert
└────────┬─────────┘
         ▼
┌──────────────────┐     ┌─────────────────┐
│ 1. CHECK DRIFT   │────▶│ No drift → SKIP │
│ Evidently AI     │     └─────────────────┘
│ KS test/feature  │
└────────┬─────────┘
         │ drift > 30%
         ▼
┌──────────────────┐
│ 2. RETRAIN       │
│ Full pipeline:   │
│ Data → Features  │
│ → PS-1 to PS-5   │
│ → Register MLflow│
└────────┬─────────┘
         ▼
┌──────────────────┐     ┌─────────────────────┐
│ 3. VALIDATE      │────▶│ AUC < 0.80 → ABORT │
│ AUC > 0.80       │     │ Alert team          │
│ F1 > 0.30        │     └─────────────────────┘
│ API tests pass   │
└────────┬─────────┘
         │ validation passed
         ▼
┌──────────────────┐
│ 4. CANARY DEPLOY │
│ 10% traffic      │
│ to new model     │
└────────┬─────────┘
         │ monitor 24h
         ▼
┌──────────────────┐     ┌─────────────────────┐
│ 5. PROMOTE       │────▶│ Errors high → ROLL  │
│ 100% traffic     │     │ BACK to old model   │
│ to new model     │     └─────────────────────┘
└──────────────────┘
```

---

## Retraining Decision Matrix

| Signal | Drift Share | Performance | Action |
|--------|------------|-------------|--------|
| No drift, good performance | < 30% | AUC > 0.90 | Do nothing |
| Minor drift, good performance | 10-30% | AUC > 0.85 | Monitor, retrain next month |
| Significant drift, good performance | > 30% | AUC > 0.85 | Retrain (proactive) |
| No drift, degraded performance | < 30% | AUC < 0.85 | Investigate features, retrain |
| Significant drift, degraded performance | > 30% | AUC < 0.85 | Urgent retrain + root cause |
| Critical drift | > 50% | Any | Emergency retrain + alert team |

---

## CI/CD Workflow Files

| File | Purpose | Trigger |
|------|---------|---------|
| `.github/workflows/ci-cd.yml` | Main CI/CD: lint → test → build → deploy | Push/PR to main |
| `.github/workflows/retrain.yml` | Retraining: drift check → retrain → validate → canary deploy | Daily schedule / manual |

---

## Setting Up GitHub Actions (Step by Step)

### 1. Create Azure Service Principal

```powershell
az ad sp create-for-rbac \
  --name "github-device-telemetry" \
  --role contributor \
  --scopes /subscriptions/<YOUR_SUBSCRIPTION_ID>/resourceGroups/rg-device-telemetry-dev \
  --sdk-auth
```

### 2. Add Secrets to GitHub

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add:
- `AZURE_CREDENTIALS` → paste the JSON from step 1
- `AZURE_STATIC_WEB_APPS_TOKEN` → from Azure Portal

### 3. Push Code

```powershell
git push origin main
```

The CI/CD pipeline triggers automatically.

### 4. Monitor

- Go to **Actions** tab to see pipeline runs
- Green checkmark = all jobs passed
- Red X = check the failed job logs

---

## Quick Reference

| Action | How |
|--------|-----|
| Trigger CI/CD | Push to `main` branch |
| Trigger retraining (manual) | Actions → Model Retraining Pipeline → Run workflow |
| Check drift status | Read `data/drift_reports/drift_decision.json` |
| Rollback deployment | `az containerapp ingress traffic set --revision-weight "latest=100"` |
| View pipeline logs | GitHub → Actions → Click run → Click job |
| Skip CI for a commit | Add `[skip ci]` to commit message |
