# Azure Deployment Guide
## Device Telemetry MLOps — London Metro Reader Monitoring
## Enterprise Architecture (MARS-Pattern)

This guide deploys the full Device Telemetry MLOps pipeline on Azure following the MARS Predictive Maintenance architecture pattern — an 11-layer enterprise production deployment.

---

## Architecture: Local → Azure Mapping

| Local Component | Azure Service | Layer |
|----------------|---------------|-------|
| CSV files | Azure Data Factory + ADLS Gen2 | Layer 1-2 |
| Bronze/Silver/Gold layers | Databricks (Delta Lake) + 3 cluster types | Layer 3 |
| Feature Store | Databricks Feature Store (Unity Catalog) | Layer 3 |
| MLflow (SQLite) | Azure ML Workspace + Databricks MLflow | Layer 4 |
| Model Registry | MLflow Model Registry (Azure ML integrated) | Layer 4 |
| Docker images | Azure Container Registry (Premium) | Layer 5 |
| CI/CD (GitHub Actions) | Azure DevOps (4-stage pipeline) | Layer 6 |
| FastAPI (local) | AKS + Managed Online Endpoints | Layer 7 |
| React Dashboard | App Service (Blue-Green) | Layer 8 |
| Prometheus + Grafana | Azure Managed Grafana + App Insights | Layer 10 |
| Evidently AI | Databricks Jobs + Azure Monitor alerts | Layer 10 |

---

## Prerequisites

```powershell
# Login to Azure
az login
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Install extensions
az extension add --name containerapp
az extension add --name databricks
az extension add --name aks-preview
az extension add --name application-insights
```

---

## Services Sizing — Configuration Baseline

### Layer 1: Data Ingestion

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Azure Data Factory** | Standard v2, Managed VNet | Managed VNet Integration | 1 | 7 pipelines, 15-min CDC, tumbling window triggers, schema validation |
| **ADF Managed VNet IR** | Azure-managed (no VMs) | Managed Private Endpoints | 1 | Connects to data sources via Managed PEs. Self-hosted IR not required |
| **Event Grid** | Standard | System topics | 1 | Pipeline completion events, blob-created triggers for ADLS |
| **Azure Function** | Consumption Plan | HTTP trigger | 1 | MLflow webhook relay. HMAC validation. Triggers DevOps pipeline |

```powershell
$RG = "rg-device-telemetry-prod"
$LOCATION = "uksouth"

# Create Resource Group
az group create --name $RG --location $LOCATION

# Create Data Factory
az datafactory create `
  --name "adf-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION

# ADF Pipeline: 15-min CDC with tumbling window
# Configure in ADF Studio:
# - Source: IoT Hub / Event Hub → raw/
# - Sink: ADLS Gen2 bronze/
# - Trigger: Tumbling window (15 min)
# - CDC: Change tracking enabled
# - Schema validation: Column mapping + type check
```

### Layer 2: Medallion Data Lake

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **ADLS Gen2 (Primary)** | StorageV2, Standard, Hot, GRS, HNS | 2.5 TB capacity | 1 | Containers: bronze/, silver/, gold/, models/, backups/. Lifecycle: Hot→Cool 90d→Archive 365d |
| **Blob Storage (Artifacts)** | StorageV2, Standard, LRS | 10 TB capacity | 1 | tfstate/ (versioned), artifacts/, staging/. Soft-delete 14d |

```powershell
# Primary Data Lake
az storage account create `
  --name "stdevicetelemetryprod" `
  --resource-group $RG `
  --location $LOCATION `
  --sku Standard_GRS `
  --kind StorageV2 `
  --hns true `
  --enable-hierarchical-namespace true

# Create medallion containers
foreach ($container in @("raw", "bronze", "silver", "gold", "feature-store", "models", "backups")) {
    az storage container create --account-name "stdevicetelemetryprod" --name $container
}

# Lifecycle policy: Hot → Cool (90d) → Archive (365d)
az storage account management-policy create `
  --account-name "stdevicetelemetryprod" `
  --resource-group $RG `
  --policy '{
    "rules": [{
      "name": "lifecycle-rule",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "baseBlob": {
            "tierToCool": {"daysAfterModificationGreaterThan": 90},
            "tierToArchive": {"daysAfterModificationGreaterThan": 365}
          }
        },
        "filters": {"blobTypes": ["blockBlob"]}
      }
    }]
  }'

# Artifacts storage (Terraform state, model artifacts)
az storage account create `
  --name "startifactsdevtelemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --sku Standard_LRS `
  --kind StorageV2
```

### Layer 3: Processing Engine (Databricks)

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Databricks Workspace** | Premium | Runtime 13.3 LTS, VNet Injection, Unity Catalog | 1 | No public IP. SCIM provisioning. Cluster policies. 3 clusters |
| **Cluster: ETL** | DS4_v2 (8c/28GB), DS3_v2 (4c/14GB) workers | Auto 2–8 workers, Spot instances | 1 | Triggered by ADF. ~4h/day active. Parquet reads→Bronze writes |
| **Cluster: Feature Eng** | DS4_v2 (8c/28GB), DS3_v2 (4c/14GB) workers | Auto 2–6 workers | 1 | Quality gate ≥97%. Z-ordering. Delta Lake. Silver→Gold |
| **Cluster: Ad-hoc** | DS3_v2 (4c/14GB), DS3_v2 (4c/14GB) workers | Auto 1–4 workers, Auto-terminate 30min | 1 | Interactive exploration for data scientists |

```powershell
# Create Databricks Workspace (Premium with VNet injection)
az databricks workspace create `
  --name "dbw-device-telemetry-prod" `
  --resource-group $RG `
  --location $LOCATION `
  --sku premium `
  --no-public-ip

# Configure in Databricks UI:
# 1. Enable Unity Catalog
# 2. Create 3 cluster policies (ETL, Feature Eng, Ad-hoc)
# 3. Mount ADLS Gen2 using service principal
# 4. Import notebooks from Git repo
```

**Notebook → Databricks mapping:**

| Local Notebook | Databricks Path | Cluster | Schedule |
|---------------|----------------|---------|----------|
| `01_bronze_layer.py` | `/pipelines/01_bronze` | ETL | ADF trigger (every 15 min CDC) |
| `02_silver_layer.py` | `/pipelines/02_silver` | ETL | After bronze completes |
| `03_gold_layer.py` | `/pipelines/03_gold` | Feature Eng | After silver completes |
| `04_feature_store.py` | `/pipelines/04_feature_store` | Feature Eng | After gold completes |
| `05_ps1_failure_prediction.py` | `/training/ps1_failure` | Training (Azure ML) | Daily 02:00 UTC or on drift |
| `06_ps2_error_pattern.py` | `/training/ps2_error` | Training (Azure ML) | Daily 02:00 UTC |
| `07_ps3_root_cause.py` | `/training/ps3_root_cause` | Training (Azure ML) | Daily 02:00 UTC |
| `08_ps4_anomaly_detection.py` | `/training/ps4_anomaly` | Training (Azure ML) | Daily 02:00 UTC |
| `09_ps5_sla_risk.py` | `/training/ps5_sla_risk` | Training (Azure ML) | Daily 02:00 UTC |
| `10_drift_detection.py` | `/monitoring/drift_detection` | Feature Eng | After predictions |

### Layer 4: ML Training

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Azure ML Workspace** | Enterprise | 80 models tracking, MLflow Native | 1 | 5 PS experiments. Registry: None→Staging→Production |
| **Training Cluster** | DS13_v2 (8c/56GB), Low-priority | Auto 0–8 nodes | 1 | Daily 02:00 UTC. 3-hr window. 4–8 parallel jobs. Idle timeout: 1200s |
| **Compute Instances (Dev)** | DS3_v2 (4c/14GB) ×2, DS4_v2 (8c/28GB) ×1 | 3 instances, Auto-shutdown 60min | 3 | Jupyter/VS Code. Managed Identity. 3rd instance for PS1/PS5 heavy workloads |
| **MLflow Model Registry** | Integrated in Azure ML | Version-controlled | 1 | Accuracy gates: >90% (PS1), >85% (PS2–5). Drift via Evidently. Webhook→CI/CD |

```powershell
# Create Azure ML Workspace
az ml workspace create `
  --name "aml-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION

# Create training compute cluster
az ml compute create `
  --name "training-cluster" `
  --resource-group $RG `
  --workspace-name "aml-device-telemetry" `
  --type AmlCompute `
  --size Standard_DS13_v2 `
  --min-instances 0 `
  --max-instances 8 `
  --idle-time-before-scale-down 1200 `
  --tier low_priority

# Create dev compute instances
foreach ($name in @("dev-ds3-01", "dev-ds3-02", "dev-ds4-01")) {
    $size = if ($name -like "*ds4*") { "Standard_DS4_v2" } else { "Standard_DS3_v2" }
    az ml compute create `
      --name $name `
      --resource-group $RG `
      --workspace-name "aml-device-telemetry" `
      --type ComputeInstance `
      --size $size
}
```

**Model Registry gates:**

| PS | Model | Minimum Accuracy | Auto-promote to Production |
|----|-------|-----------------|---------------------------|
| PS-1 | Failure Predictor | AUC > 0.90 | Yes (if > previous champion) |
| PS-2 | Error Pattern Rules | Lift > 1.5 | Manual review |
| PS-3 | SHAP Explainer | N/A (explainability) | Auto |
| PS-4 | Anomaly Detector | F1 > 0.85 | Yes |
| PS-5 | SLA Risk (Cox PH) | C-index > 0.80 | Yes |

### Layer 5: Model Packaging

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Container Registry** | Premium | 8 repos, Geo-replication, Content Trust | 1 | Repos: mars-base, mars-ps{1-5}, mars-api, mars-ui. Trivy scan on push |
| **Docker Images** | — | 8 images total (1.4–2.1GB each) | 8 | Shared base: openmci4.1.0-ubuntu22.04. MLflow 2.12 + azureml-inference-server |
| **ML Environment Defs** | — | 5 registered, Version-pinned | 5 | Inference config: /health, /score:5001. Linked to ACR images |

```powershell
# Create Premium ACR with geo-replication
az acr create `
  --name "acrdevicetelemetry" `
  --resource-group $RG `
  --sku Premium `
  --admin-enabled true

# Enable content trust (image signing)
az acr config content-trust update `
  --name "acrdevicetelemetry" `
  --status enabled

# Build and push images
docker build -f api/Dockerfile -t acrdevicetelemetry.azurecr.io/mars-api:v1 .
docker push acrdevicetelemetry.azurecr.io/mars-api:v1
```

### Layer 6: MLOps CI/CD

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Azure DevOps** | Standard | 4 repos, CI/CD, 4-stage pipeline | 1 | Repos: mars-mlops, mars-api, mars-ui, mars-infra (Terraform). Build→Test→Deploy Blue→Traffic Swap |
| **CI/CD Agents** | Microsoft-hosted or Self-hosted | 2 parallel jobs | 2 | Docker build agent. ~80 pipeline runs/month |
| **Azure Kubernetes Service** | Standard DS4_v2 | 2-6 nodes (based on load) | 1 | — |
| **Blue-Green Deployment** | Managed Online EP | Canary rollout | — | 0%→10% (5m)→50% (5m)→100%. Auto-rollback on error>1% or latency>2× |

**4-Stage CI/CD Pipeline:**

```
Stage 1: BUILD
├── Lint code (flake8, black)
├── Run unit tests
├── Build Docker images
└── Push to ACR (with Trivy scan)

Stage 2: TEST
├── Deploy to staging endpoint
├── Run integration tests
├── Validate model accuracy gates
└── Run drift detection

Stage 3: DEPLOY BLUE
├── Deploy new version to Blue slot
├── Health check (/health)
├── Smoke test (sample predictions)
└── Hold for approval (manual gate)

Stage 4: TRAFFIC SWAP
├── Canary: 0% → 10% (monitor 5 min)
├── Canary: 10% → 50% (monitor 5 min)
├── Full: 50% → 100%
└── Auto-rollback if error > 1% or latency > 2×
```

### Layer 7: Real-Time Inference

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Managed Online Endpoints** | DS4_v2 (8c/28GB) | Auto 2–6 per EP, 1 per PS | 5 | Each serves predictions. Blue-Green per endpoint |
| **Azure Cache for Redis** | Premium P1 | HA with replicas, 6GB, SSL:6380 | 1 | TTL 5min. RDB/15min snapshots. 85% cache hit. Caches prediction results |
| **API Management** | Premium, 1 unit | OAuth 2.0 + PKCE, Internal VNet mode | 1 | Rate: 1K/min. Circuit breaker. Routes: /predict, /explain, /health, /models. Private endpoints + VNet |

```powershell
# Create Azure ML Managed Online Endpoints (1 per PS)
foreach ($ps in @("ps1-failure", "ps2-errors", "ps3-rootcause", "ps4-anomaly", "ps5-slarisk")) {
    az ml online-endpoint create `
      --name "ep-$ps" `
      --resource-group $RG `
      --workspace-name "aml-device-telemetry" `
      --auth-mode key
}

# Create Redis Cache
az redis create `
  --name "redis-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --sku Premium `
  --vm-size P1 `
  --enable-non-ssl-port false

# Create API Management
az apim create `
  --name "apim-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --publisher-name "Metro ML Team" `
  --publisher-email "ml-team@metro.gov.uk" `
  --sku-name Premium `
  --virtual-network Internal
```

### Layer 8: Application Tier

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **App Service — API** | P2v3 (2c/8GB) Linux | Blue-Green slots, VNet integrated, Auto 2–10 | 1 plan | FastAPI Python 3.11. 5 microservices. SSL/TLS |
| **App Service — UI** | P2v3 (2c/8GB) Linux | Blue-Green slots, VNet integrated, Auto 2–4 | 1 plan | React 18.2 + TypeScript. SHAP visualisation. Dashboard |
| **Azure SQL Database** | Gen Purpose | Geo-rep, TDE, 8 vCores, 32GB, 1TB, 35d backup | 1 | Predictions, sessions, audit, config tables |

```powershell
# Create App Service Plan
az appservice plan create `
  --name "asp-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --sku P2V3 `
  --is-linux

# Deploy API
az webapp create `
  --name "app-telemetry-api" `
  --resource-group $RG `
  --plan "asp-device-telemetry" `
  --runtime "PYTHON:3.11"

# Deploy React UI
az webapp create `
  --name "app-telemetry-ui" `
  --resource-group $RG `
  --plan "asp-device-telemetry" `
  --runtime "NODE:18-lts"

# Create SQL Database
az sql server create `
  --name "sql-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --admin-user sqladmin `
  --admin-password "<STRONG_PASSWORD>"

az sql db create `
  --name "db-telemetry" `
  --server "sql-device-telemetry" `
  --resource-group $RG `
  --edition GeneralPurpose `
  --capacity 8 `
  --max-size 1TB
```

### Layer 9: Security & Networking

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **VNet** | 10.224.0.0/21 (2,048 IPs) | 8 subnets | 1 | snet-appsvc-int, snet-apim, snet-priv-endpoints, snet-data-services, snet-ml-compute, snet-dbx-host, snet-dbx-container, snet-network-edge |
| **VNet Peering** | Bidirectional | — | 1 | ADF Managed PEs traverse peering for data access |
| **Azure Firewall** | Standard | DNAT/NAT/FQDN | 1 | Threat intelligence. All logs→Log Analytics |
| **Azure Bastion** | Standard | Native client | 1 | No public RDP/SSH. File transfer enabled |
| **VPN Gateway** | VpnGw1 | Active-Standby, Route-based | 1 | Connectivity to on-prem. BGP capable |
| **NAT Gateway** | Standard | Deterministic outbound IP | 1 | Outbound SNAT for compute subnets. 64K connections |
| **Key Vault** | Premium, HSM | Purge protection, Soft-delete 90d | 1 | Secrets, certs, connection strings. Managed Identity. RBAC |
| **Private Endpoints** | Standard | 12 PEs total | 12 | ADLS(blob+dfs), Blob, Databricks(2), AML(2), ACR, Redis, SQL, KV, ADF |
| **Private DNS Zones** | Azure Private DNS | 8 zones | 8 | blob, dfs, sql, redis, kv, acr, aml, dbx |
| **NSGs** | Standard | Deny-all default | 8 | 1 per subnet. Allow rules per service pair. Flow logs enabled |

```powershell
# Create VNet with 8 subnets
az network vnet create `
  --name "vnet-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --address-prefix 10.224.0.0/21

foreach ($subnet in @(
    "snet-appsvc-int,10.224.0.0/24",
    "snet-apim,10.224.1.0/24",
    "snet-priv-endpoints,10.224.2.0/24",
    "snet-data-services,10.224.3.0/24",
    "snet-ml-compute,10.224.4.0/23",
    "snet-dbx-host,10.224.6.0/26",
    "snet-dbx-container,10.224.6.64/26",
    "snet-network-edge,10.224.7.0/24"
)) {
    $parts = $subnet -split ","
    az network vnet subnet create `
      --vnet-name "vnet-device-telemetry" `
      --resource-group $RG `
      --name $parts[0] `
      --address-prefix $parts[1]
}

# Create Key Vault (Premium with HSM)
az keyvault create `
  --name "kv-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --sku premium `
  --enable-purge-protection true `
  --enable-soft-delete true
```

### Layer 10: Monitoring & Operations

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Application Insights** | Workspace-based | Adaptive sampling, 90d retention | 1 | Distributed tracing. Custom metrics: accuracy, latency, cache_hit, drift_score |
| **Log Analytics** | Pay-as-you-go | KQL queries, 90d, 10GB/day cap | 1 | All services log here. NSG flow + FW logs. Diagnostic settings on every resource |
| **Azure Monitor Alerts** | — | 50+ rules, 4 severity tiers | 50 | P1: PagerDuty (5min). P2: Email (15min). P3/P4: Slack (1hr). Smart detection |
| **Managed Grafana** | Standard | 25+ dashboards, Azure AD SSO | 1 | ML health, pipeline SLAs, infrastructure, cost tracking dashboards |

```powershell
# Create Log Analytics Workspace
az monitor log-analytics workspace create `
  --name "law-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --retention-time 90 `
  --daily-quota-gb 10

# Create Application Insights
az monitor app-insights component create `
  --app "ai-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION `
  --workspace "law-device-telemetry" `
  --kind web

# Create Managed Grafana
az grafana create `
  --name "grafana-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION
```

**Alert Rules (50+ rules across 4 severity tiers):**

| Severity | Response Time | Channel | Example Rules |
|----------|-------------|---------|---------------|
| **P1 (Critical)** | 5 min | PagerDuty + SMS | API down, model not loaded, >20 critical devices |
| **P2 (High)** | 15 min | Email + Teams | High error rate (>1%), drift detected (>30%), latency P99 >1s |
| **P3 (Medium)** | 1 hour | Slack | Data quality <90%, training failed, cache hit <70% |
| **P4 (Low)** | Next business day | Email | Budget >80%, cluster idle, unused compute instances |

### Layer 11: Disaster Recovery

| Service | SKU / Tier | Specification | Qty | Configuration |
|---------|-----------|---------------|-----|---------------|
| **Recovery Services Vault** | Standard, GRS | Daily + weekly backups | 1 | SQL: daily, 35d retention. ADLS: weekly, 12 weeks |

```powershell
# Create Recovery Services Vault
az backup vault create `
  --name "rsv-device-telemetry" `
  --resource-group $RG `
  --location $LOCATION

# Enable SQL backup
az backup protection enable-for-azurewl `
  --resource-group $RG `
  --vault-name "rsv-device-telemetry" `
  --policy-name "DailyBackupPolicy" `
  --workload-type SQLDATABASE
```

---

## Daily Pipeline Flow on Azure

```
06:00 UTC — ADF Trigger (tumbling window, 15-min CDC)
  │
  ├── ADF Pipeline: IoT Hub → ADLS raw/ (CDC with watermark)
  │
  ├── Event Grid → Triggers Databricks ETL Cluster
  │   ├── Notebook: 01_bronze_layer (raw → bronze Delta)
  │   ├── Notebook: 02_silver_layer (clean → silver Delta)
  │   └── Notebook: 03_gold_layer (features → gold Delta)
  │
  ├── Databricks Feature Eng Cluster
  │   └── Notebook: 04_feature_store (update Unity Catalog)
  │
  ├── Azure ML Training Cluster (02:00 UTC)
  │   ├── PS-1: Failure Prediction (XGBoost/CatBoost)
  │   ├── PS-2: Error Patterns (Apriori/Markov)
  │   ├── PS-3: Root Cause (SHAP/DoWhy)
  │   ├── PS-4: Anomaly Detection (Isolation Forest)
  │   └── PS-5: SLA Risk (Weibull/Cox/RUL)
  │
  ├── Model Registry Check
  │   ├── Accuracy gates pass? → Register → Staging
  │   ├── A/B test pass? → Promote → Production
  │   └── Webhook → Azure DevOps → CI/CD Pipeline
  │
  ├── CI/CD: Build → Test → Deploy Blue → Canary → Production
  │   └── Auto-rollback if error > 1% or latency > 2×
  │
  ├── Managed Online Endpoints (5 EPs, 1 per PS)
  │   ├── Redis Cache (85% hit rate, TTL 5 min)
  │   └── API Management (OAuth 2.0, rate limiting 1K/min)
  │
  ├── Drift Detection (Evidently AI Databricks job)
  │   └── If drift > 30% → Trigger retraining
  │
  └── Monitoring
      ├── App Insights (request traces, custom metrics)
      ├── Log Analytics (all service logs)
      ├── Azure Monitor (50+ alert rules)
      └── Managed Grafana (25+ dashboards)
```

---

## Cost Estimation (Monthly)

| Layer | Service | Estimated Cost |
|-------|---------|---------------|
| 1 | Data Factory (ADF) | ~$50 |
| 2 | ADLS Gen2 (2.5 TB) + Blob (10 TB) | ~$80 |
| 3 | Databricks (3 clusters, ~8h/day) | ~$400 |
| 4 | Azure ML (training cluster, 3 instances) | ~$300 |
| 5 | Container Registry (Premium) | ~$50 |
| 6 | Azure DevOps (2 agents) | ~$80 |
| 7 | Managed Online Endpoints (5 EPs) + Redis + APIM | ~$500 |
| 8 | App Service (API + UI) + SQL DB | ~$250 |
| 9 | Networking (Firewall, VPN, Bastion, NAT) | ~$350 |
| 10 | Monitoring (App Insights, Log Analytics, Grafana) | ~$100 |
| 11 | Disaster Recovery (Vault) | ~$20 |
| **Total** | | **~$2,180/month** |

> **Cost reduction for dev/test:** Use spot instances for Databricks/ML clusters, scale endpoints to 0 when idle, use Basic ACR, remove Firewall/VPN/Bastion. Reduces to ~$500/month.

---

## Security Checklist

- [ ] All services in VNet with Private Endpoints (no public access)
- [ ] Managed Identity for all service-to-service auth (no passwords)
- [ ] Key Vault for all secrets (connection strings, API keys)
- [ ] NSGs with deny-all default on every subnet
- [ ] Azure Firewall for egress filtering
- [ ] Bastion for admin access (no public RDP/SSH)
- [ ] Container image scanning (Trivy) on ACR push
- [ ] OAuth 2.0 + PKCE on API Management
- [ ] TDE on SQL Database + encryption at rest on ADLS
- [ ] Diagnostic settings on every resource → Log Analytics
- [ ] Budget alerts at 80% and 100% of monthly budget
- [ ] Geo-replication for ACR and SQL Database

---

## Quick Reference

| Action | Command |
|--------|---------|
| Deploy all infra | `cd terraform && terraform apply` |
| Push new API version | `docker build` → `az acr build` → `az ml online-deployment update` |
| Canary rollout | `az ml online-endpoint update --traffic "blue=90 green=10"` |
| Full promotion | `az ml online-endpoint update --traffic "green=100"` |
| Rollback | `az ml online-endpoint update --traffic "blue=100"` |
| View logs | `az monitor log-analytics query -w <workspace-id> --analytics-query "requests \| top 10"` |
| Check costs | Azure Portal → Cost Management + Billing |
| Run pipeline manually | Trigger ADF pipeline or Databricks Workflow from portal |
| View Grafana | Azure Portal → Managed Grafana → Open dashboard |
