# Azure Deployment Guide
## Device Telemetry MLOps — London Metro Reader Monitoring

This guide covers deploying the full Device Telemetry MLOps pipeline on Azure, mapping each local component to its Azure equivalent.

---

## Architecture: Local → Azure Mapping

| Local Component | Azure Service | Purpose |
|----------------|---------------|---------|
| CSV files | Azure Data Lake Storage Gen2 | Raw data storage |
| Bronze/Silver/Gold layers | Azure Databricks (Delta Lake) | Medallion architecture |
| Feature Store | Databricks Feature Store | Centralized features |
| MLflow (SQLite) | Azure Databricks MLflow / Azure ML | Experiment tracking |
| Model Registry (local) | Databricks Unity Catalog / Azure ML Registry | Model versioning |
| FastAPI (local) | Azure Container Apps / AKS | Model serving |
| Prometheus + Grafana | Azure Monitor + App Insights | Monitoring |
| Docker Compose | Azure Container Apps / AKS | Container orchestration |
| React Dashboard | Azure Static Web Apps | Frontend hosting |
| Evidently AI | Azure Databricks Jobs | Drift detection |
| Great Expectations | Azure Databricks Jobs | Data quality |
| Incremental Pipeline | Azure Data Factory / Databricks Workflows | Orchestration |
| Blue-Green / Canary | Azure Container Apps Revisions | Deployment strategies |

---

## Prerequisites

- Azure Subscription with Contributor access
- Azure CLI installed (`az --version`)
- Docker Desktop (for building images)
- Azure DevOps or GitHub Actions (for CI/CD)

```powershell
# Login to Azure
az login

# Set subscription
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Install extensions
az extension add --name containerapp
az extension add --name databricks
```

---

## Step 1: Resource Group & Networking

```powershell
# Variables
$RG = "rg-device-telemetry-ml"
$LOCATION = "uksouth"    # London region for low latency

# Create Resource Group
az group create --name $RG --location $LOCATION
```

---

## Step 2: Azure Data Lake Storage Gen2 (Data Layer)

Replaces local `data/raw/`, `data/bronze/`, `data/silver/`, `data/gold/`.

```powershell
$STORAGE_ACCOUNT = "stdevicetelemetry"

# Create Storage Account with Data Lake Gen2
az storage account create `
  --name $STORAGE_ACCOUNT `
  --resource-group $RG `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2 `
  --hns true    # Hierarchical namespace = Data Lake Gen2

# Create containers (medallion layers)
az storage container create --account-name $STORAGE_ACCOUNT --name raw
az storage container create --account-name $STORAGE_ACCOUNT --name bronze
az storage container create --account-name $STORAGE_ACCOUNT --name silver
az storage container create --account-name $STORAGE_ACCOUNT --name gold
az storage container create --account-name $STORAGE_ACCOUNT --name feature-store
az storage container create --account-name $STORAGE_ACCOUNT --name artifacts
az storage container create --account-name $STORAGE_ACCOUNT --name drift-reports
```

### Upload Initial Data

```powershell
# Upload sample data to raw container
az storage blob upload-batch `
  --account-name $STORAGE_ACCOUNT `
  --destination raw `
  --source data/raw/
```

---

## Step 3: Azure Databricks (ML Training & MLOps)

Replaces local notebooks, MLflow, Feature Store, and incremental pipeline.

### Create Databricks Workspace

```powershell
az databricks workspace create `
  --name "dbw-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --sku standard
```

### Configure Databricks

1. **Open** the Databricks workspace from Azure Portal
2. **Create a cluster:** `Standard_DS3_v2` (4 cores, 14 GB) — single node for dev
3. **Install libraries** on the cluster:
   ```
   xgboost, catboost, shap, lifelines, mlxtend, dowhy, evidently, great-expectations
   ```

### Mount Data Lake

In a Databricks notebook:

```python
# Mount Azure Data Lake Storage
configs = {
    "fs.azure.account.key.stdevicetelemetry.dfs.core.windows.net":
        dbutils.secrets.get(scope="storage", key="account-key")
}

dbutils.fs.mount(
    source="abfss://raw@stdevicetelemetry.dfs.core.windows.net/",
    mount_point="/mnt/raw",
    extra_configs=configs
)

# Repeat for bronze, silver, gold, feature-store, artifacts
for container in ["bronze", "silver", "gold", "feature-store", "artifacts"]:
    dbutils.fs.mount(
        source=f"abfss://{container}@stdevicetelemetry.dfs.core.windows.net/",
        mount_point=f"/mnt/{container}",
        extra_configs=configs
    )
```

### Upload Notebooks

Upload each notebook from `notebooks/` to Databricks:

| Local File | Databricks Path | Azure Changes |
|------------|----------------|---------------|
| `01_bronze_layer.py` | `/Repos/notebooks/01_bronze_layer` | Read from `/mnt/raw`, write to `/mnt/bronze` |
| `02_silver_layer.py` | `/Repos/notebooks/02_silver_layer` | Read from `/mnt/bronze`, write to `/mnt/silver` |
| `03_gold_layer.py` | `/Repos/notebooks/03_gold_layer` | Read from `/mnt/silver`, write to `/mnt/gold` |
| `04_feature_store.py` | `/Repos/notebooks/04_feature_store` | Use Databricks Feature Store API |
| `05_ps1_failure_prediction.py` | `/Repos/notebooks/05_ps1` | MLflow auto-logs to Databricks MLflow |
| `06_ps2_error_pattern.py` | `/Repos/notebooks/06_ps2` | Same |
| `07_ps3_root_cause.py` | `/Repos/notebooks/07_ps3` | Same |
| `08_ps4_anomaly_detection.py` | `/Repos/notebooks/08_ps4` | Same |
| `09_ps5_sla_risk.py` | `/Repos/notebooks/09_ps5` | Same |
| `10_drift_detection.py` | `/Repos/notebooks/10_drift` | Save reports to `/mnt/drift-reports` |

### Key Code Changes for Databricks

```python
# Replace local file paths with DBFS mounts
# LOCAL:  pd.read_parquet("data/silver/telemetry.parquet")
# AZURE:  spark.read.parquet("/mnt/silver/telemetry.parquet").toPandas()

# MLflow tracking is automatic in Databricks — remove:
#   mlflow.set_tracking_uri("sqlite:///...")
# Databricks MLflow tracks experiments automatically

# Feature Store — use Databricks Feature Store:
from databricks.feature_store import FeatureStoreClient
fs = FeatureStoreClient()
fs.create_table(
    name="device_telemetry.features",
    primary_keys=["device_id", "date"],
    df=spark_df,
    description="Device telemetry features"
)
```

### Unity Catalog (Model Registry)

```python
import mlflow
mlflow.set_registry_uri("databricks-uc")

# Register model
mlflow.register_model(
    model_uri=f"runs:/{run_id}/model",
    name="device_telemetry.models.failure_predictor"
)
```

### Databricks Workflows (Pipeline Orchestration)

Create a multi-task job that replaces `run_pipeline.py`:

```json
{
  "name": "Device_Telemetry_Pipeline",
  "tasks": [
    {"task_key": "bronze", "notebook_task": {"notebook_path": "/Repos/notebooks/01_bronze_layer"}},
    {"task_key": "silver", "depends_on": [{"task_key": "bronze"}], "notebook_task": {"notebook_path": "/Repos/notebooks/02_silver_layer"}},
    {"task_key": "gold", "depends_on": [{"task_key": "silver"}], "notebook_task": {"notebook_path": "/Repos/notebooks/03_gold_layer"}},
    {"task_key": "feature_store", "depends_on": [{"task_key": "gold"}], "notebook_task": {"notebook_path": "/Repos/notebooks/04_feature_store"}},
    {"task_key": "ps1", "depends_on": [{"task_key": "feature_store"}], "notebook_task": {"notebook_path": "/Repos/notebooks/05_ps1"}},
    {"task_key": "ps2", "depends_on": [{"task_key": "feature_store"}], "notebook_task": {"notebook_path": "/Repos/notebooks/06_ps2"}},
    {"task_key": "ps3", "depends_on": [{"task_key": "ps1"}], "notebook_task": {"notebook_path": "/Repos/notebooks/07_ps3"}},
    {"task_key": "ps4", "depends_on": [{"task_key": "feature_store"}], "notebook_task": {"notebook_path": "/Repos/notebooks/08_ps4"}},
    {"task_key": "ps5", "depends_on": [{"task_key": "feature_store"}], "notebook_task": {"notebook_path": "/Repos/notebooks/09_ps5"}},
    {"task_key": "drift", "depends_on": [{"task_key": "ps1"}], "notebook_task": {"notebook_path": "/Repos/notebooks/10_drift"}}
  ],
  "schedule": {
    "quartz_cron_expression": "0 0 6 * * ?",
    "timezone_id": "Europe/London"
  }
}
```

---

## Step 4: Azure Container Registry (Docker Images)

```powershell
$ACR_NAME = "acrdevicetelemetry"

# Create ACR
az acr create `
  --name $ACR_NAME `
  --resource-group $RG `
  --sku Basic `
  --admin-enabled true

# Login to ACR
az acr login --name $ACR_NAME

# Build and push API image
docker build -f api/Dockerfile -t "$ACR_NAME.azurecr.io/telemetry-api:v1" .
docker push "$ACR_NAME.azurecr.io/telemetry-api:v1"
```

---

## Step 5: Azure Container Apps (API Serving)

Replaces local FastAPI + Docker.

```powershell
# Create Container Apps Environment
az containerapp env create `
  --name "cae-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION

# Get ACR credentials
$ACR_PASSWORD = $(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

# Deploy API
az containerapp create `
  --name "telemetry-api" `
  --resource-group $RG `
  --environment "cae-device-telemetry" `
  --image "$ACR_NAME.azurecr.io/telemetry-api:v1" `
  --target-port 8000 `
  --ingress external `
  --min-replicas 1 `
  --max-replicas 5 `
  --cpu 1.0 `
  --memory 2.0Gi `
  --registry-server "$ACR_NAME.azurecr.io" `
  --registry-username $ACR_NAME `
  --registry-password $ACR_PASSWORD

# Get the API URL
az containerapp show --name "telemetry-api" --resource-group $RG --query "properties.configuration.ingress.fqdn" -o tsv
```

### Blue-Green Deployment with Container Apps Revisions

```powershell
# Deploy new version (Green) with 0% traffic
az containerapp update `
  --name "telemetry-api" `
  --resource-group $RG `
  --image "$ACR_NAME.azurecr.io/telemetry-api:v2" `
  --revision-suffix "green"

# Split traffic: 90% Blue, 10% Green (Canary)
az containerapp ingress traffic set `
  --name "telemetry-api" `
  --resource-group $RG `
  --revision-weight "telemetry-api--blue=90" "telemetry-api--green=10"

# Full promotion to Green (100%)
az containerapp ingress traffic set `
  --name "telemetry-api" `
  --resource-group $RG `
  --revision-weight "telemetry-api--green=100"

# Rollback to Blue
az containerapp ingress traffic set `
  --name "telemetry-api" `
  --resource-group $RG `
  --revision-weight "telemetry-api--blue=100"
```

---

## Step 6: Azure Monitor + Application Insights (Monitoring)

Replaces Prometheus + Grafana.

```powershell
# Create Application Insights
az monitor app-insights component create `
  --app "ai-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --kind web

# Get instrumentation key
$INSTRUMENTATION_KEY = $(az monitor app-insights component show `
  --app "ai-device-telemetry" `
  --resource-group $RG `
  --query "instrumentationKey" -o tsv)
```

### Add to FastAPI

```python
# pip install opencensus-ext-azure
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.ext.fastapi.fastapi_middleware import FastAPIMiddleware

app.add_middleware(
    FastAPIMiddleware,
    exporter=AzureExporter(connection_string=f"InstrumentationKey={INSTRUMENTATION_KEY}"),
    sampler=ProbabilitySampler(1.0)
)
```

### Azure Monitor Metrics (equivalent to Prometheus)

| Prometheus Metric | Azure Monitor Equivalent |
|-------------------|--------------------------|
| `predictions_total` | Custom Metric: `predictions_count` |
| `prediction_latency_seconds` | `requests/duration` |
| `errors_total` | `requests/failed` |
| `http_requests_total` | `requests/count` |

### Azure Dashboards (equivalent to Grafana)

Create dashboards in Azure Portal → Monitor → Dashboards:

```kusto
// Predictions per minute (KQL query for Log Analytics)
customMetrics
| where name == "predictions_count"
| summarize count() by bin(timestamp, 1m)
| render timechart

// P99 latency
requests
| summarize percentile(duration, 99) by bin(timestamp, 5m)
| render timechart

// Error rate
requests
| summarize failed = countif(success == false), total = count() by bin(timestamp, 5m)
| extend error_rate = todouble(failed) / total * 100
| render timechart
```

---

## Step 7: Azure Static Web Apps (React Dashboard)

```powershell
# Build the React app
cd dashboard
npm run build

# Create Static Web App
az staticwebapp create `
  --name "swa-device-telemetry" `
  --resource-group $RG `
  --source "https://github.com/SathishMars/Device_Telemetry_ML" `
  --location $LOCATION `
  --branch main `
  --app-location "/dashboard" `
  --output-location "dist" `
  --login-with-github
```

**Update API URL in dashboard:** Change `API_URL` in `dashboard/src/App.jsx` to point to the Container Apps URL:

```javascript
const API_URL = 'https://telemetry-api.<region>.azurecontainerapps.io'
```

---

## Step 8: Azure Data Factory (Incremental Pipeline)

Replaces `scripts/run_incremental_daily.py` for production scheduling.

```powershell
# Create Data Factory
az datafactory create `
  --name "adf-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION
```

### ADF Pipeline Design

```
Trigger (Daily 6 AM UTC)
  │
  ├── Copy Activity: IoT Hub → Data Lake (raw/)
  │
  ├── Databricks Notebook: 01_bronze_layer
  │
  ├── Databricks Notebook: 02_silver_layer
  │
  ├── Databricks Notebook: 03_gold_layer
  │
  ├── Databricks Notebook: 04_feature_store
  │
  ├── Parallel:
  │   ├── Databricks: 05_ps1 → 07_ps3
  │   ├── Databricks: 06_ps2
  │   ├── Databricks: 08_ps4
  │   └── Databricks: 09_ps5
  │
  ├── Databricks Notebook: 10_drift_detection
  │
  └── If drift > 30%:
      └── Trigger: Retrain + Redeploy API
```

---

## Step 9: Azure Key Vault (Secrets Management)

```powershell
# Create Key Vault
az keyvault create `
  --name "kv-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION

# Store secrets
az keyvault secret set --vault-name "kv-device-telemetry" --name "storage-account-key" --value "<KEY>"
az keyvault secret set --vault-name "kv-device-telemetry" --name "acr-password" --value "<PASSWORD>"
az keyvault secret set --vault-name "kv-device-telemetry" --name "app-insights-key" --value "$INSTRUMENTATION_KEY"
```

---

## Cost Estimation (Monthly)

| Service | SKU | Estimated Cost |
|---------|-----|---------------|
| Data Lake Storage Gen2 | Standard LRS, ~10 GB | ~$2 |
| Databricks | Standard, DS3_v2 (8h/day) | ~$150 |
| Container Apps | 1 vCPU, 2 GB, 1 replica | ~$30 |
| Container Registry | Basic | ~$5 |
| Application Insights | 5 GB/month | ~$12 |
| Static Web Apps | Free tier | $0 |
| Key Vault | Standard | ~$1 |
| Data Factory | 10 runs/day | ~$5 |
| **Total** | | **~$205/month** |

> For dev/test: Use Databricks spot instances and scale Container Apps to 0 when idle to reduce to ~$80/month.

---

## CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Device Telemetry ML

on:
  push:
    branches: [main]

env:
  ACR_NAME: acrdevicetelemetry
  RG: rg-device-telemetry-ml
  API_APP: telemetry-api

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Build and push Docker image
        run: |
          az acr login --name $ACR_NAME
          docker build -f api/Dockerfile -t $ACR_NAME.azurecr.io/telemetry-api:${{ github.sha }} .
          docker push $ACR_NAME.azurecr.io/telemetry-api:${{ github.sha }}

      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name $API_APP \
            --resource-group $RG \
            --image $ACR_NAME.azurecr.io/telemetry-api:${{ github.sha }}

  deploy-dashboard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build React Dashboard
        run: |
          cd dashboard
          npm ci
          npm run build

      - name: Deploy to Static Web Apps
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_TOKEN }}
          app_location: "/dashboard"
          output_location: "dist"
```

---

## Security Checklist

- [ ] Enable Managed Identity for Container Apps → Data Lake access
- [ ] Store all secrets in Key Vault (no hardcoded keys)
- [ ] Enable VNET integration for Databricks and Container Apps
- [ ] Configure CORS on Container Apps (allow only Static Web App domain)
- [ ] Enable Azure AD authentication on API endpoints
- [ ] Enable diagnostic logging on all services
- [ ] Set up Azure Budget alerts ($300/month threshold)
- [ ] Enable Databricks audit logging
- [ ] Use Private Endpoints for Storage and Key Vault

---

## Quick Reference

| Action | Command |
|--------|---------|
| Deploy all infra | Run Steps 1-9 above sequentially |
| Push new API version | `docker build` → `docker push` → `az containerapp update` |
| Blue-Green switch | `az containerapp ingress traffic set --revision-weight ...` |
| View logs | `az containerapp logs show --name telemetry-api -g $RG` |
| Scale API | `az containerapp update --min-replicas 2 --max-replicas 10` |
| Run pipeline manually | Trigger Databricks Workflow from Databricks UI |
| View monitoring | Azure Portal → Application Insights → Live Metrics |
| Check costs | Azure Portal → Cost Management + Billing |
