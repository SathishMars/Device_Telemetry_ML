# Terraform Guide for Device Telemetry MLOps
## A Beginner-Friendly Walkthrough

---

## What is Terraform?

Terraform is an **Infrastructure as Code (IaC)** tool. Instead of clicking through Azure Portal to create resources, you **write code** that describes what you want, and Terraform creates it for you.

**Why use it?**
- **Repeatable:** Run the same code to create identical environments (dev, staging, prod)
- **Version controlled:** Infrastructure changes tracked in Git like application code
- **Destroyable:** One command to tear down everything (no forgotten resources costing money)
- **Reviewable:** Team can review infrastructure changes before applying

**Key concepts:**

| Concept | What it means | Example |
|---------|---------------|---------|
| **Provider** | Cloud platform to deploy to | `azurerm` (Azure) |
| **Resource** | A thing you want to create | Storage account, database, container |
| **Variable** | A configurable input | Region, environment name, SKU |
| **Output** | A value Terraform tells you after creating | API URL, storage key |
| **State** | Terraform's record of what it created | `terraform.tfstate` file |
| **Plan** | Preview of what Terraform WILL do | Shows creates/updates/deletes |
| **Apply** | Actually execute the plan | Creates real Azure resources |

**How it works:**
```
You write .tf files → terraform plan (preview) → terraform apply (create) → Resources exist in Azure
                                                                          → terraform destroy (delete all)
```

---

## Prerequisites

### 1. Install Terraform

Download from https://developer.hashicorp.com/terraform/install

```powershell
# Verify installation
terraform --version
```

Or install via Chocolatey (Windows):
```powershell
choco install terraform
```

### 2. Install Azure CLI & Login

```powershell
# Login to Azure
az login

# Verify subscription
az account show --query "{name:name, id:id}" -o table
```

---

## Project Structure

We'll create Terraform files in a new `terraform/` directory:

```
device_telemetry_mlops/
└── terraform/
    ├── main.tf              # Main infrastructure (what to create)
    ├── variables.tf         # Input variables (configurable values)
    ├── outputs.tf           # Output values (URLs, keys)
    ├── providers.tf         # Azure provider config
    ├── storage.tf           # Data Lake Storage
    ├── databricks.tf        # Databricks workspace
    ├── container_apps.tf    # API serving
    ├── monitoring.tf        # App Insights + Log Analytics
    ├── container_registry.tf # Docker image registry
    ├── keyvault.tf          # Secrets management
    ├── terraform.tfvars     # Your variable values (DO NOT commit)
    └── .gitignore           # Ignore state files & secrets
```

---

## File-by-File Walkthrough

### providers.tf — "Which cloud and what version?"

This tells Terraform: "I want to use Azure"

```hcl
# terraform/providers.tf

# Specify required providers and versions
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"     # Use Azure provider version 3.80+
    }
  }

  # Optional: Store state in Azure (recommended for teams)
  # backend "azurerm" {
  #   resource_group_name  = "rg-terraform-state"
  #   storage_account_name = "stterraformstate"
  #   container_name       = "tfstate"
  #   key                  = "device-telemetry.tfstate"
  # }
}

# Configure the Azure provider
provider "azurerm" {
  features {}
  # Terraform uses your `az login` credentials automatically
}
```

**What this does:** Tells Terraform to download the Azure plugin so it knows how to create Azure resources.

---

### variables.tf — "What can I customize?"

Variables make your code reusable. Change values without changing code.

```hcl
# terraform/variables.tf

variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "device-telemetry"
}

variable "environment" {
  description = "Environment: dev, staging, or prod"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region to deploy to"
  type        = string
  default     = "uksouth"    # London region
}

variable "api_image_tag" {
  description = "Docker image tag for the API"
  type        = string
  default     = "v1"
}

variable "api_min_replicas" {
  description = "Minimum API container replicas"
  type        = number
  default     = 1
}

variable "api_max_replicas" {
  description = "Maximum API container replicas"
  type        = number
  default     = 5
}

variable "databricks_sku" {
  description = "Databricks pricing tier: standard or premium"
  type        = string
  default     = "standard"
}

variable "alert_email" {
  description = "Email for budget and health alerts"
  type        = string
  default     = ""
}
```

**What this does:** Defines all the knobs you can turn. You set actual values in `terraform.tfvars`.

---

### terraform.tfvars — "My actual values"

```hcl
# terraform/terraform.tfvars
# ⚠️  DO NOT commit this file to Git (contains your specific values)

project_name     = "device-telemetry"
environment      = "dev"
location         = "uksouth"
api_image_tag    = "v1"
api_min_replicas = 1
api_max_replicas = 3
databricks_sku   = "standard"
alert_email      = "your.email@example.com"
```

---

### main.tf — "The foundation"

Creates the Resource Group (the folder that holds all Azure resources).

```hcl
# terraform/main.tf

# -----------------------------------------------------------
# Local values (computed from variables, used everywhere)
# -----------------------------------------------------------
locals {
  # Naming convention: {project}-{resource}-{environment}
  resource_prefix = "${var.project_name}-${var.environment}"

  # Common tags applied to ALL resources
  common_tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
    team        = "ml-engineering"
  }
}

# -----------------------------------------------------------
# Resource Group — the container for all resources
# -----------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.resource_prefix}"
  location = var.location
  tags     = local.common_tags
}
```

**What this does:**
- `locals` = computed values reused across files
- `resource "azurerm_resource_group" "main"` = creates an Azure Resource Group
- `tags` = labels for cost tracking and organization

---

### storage.tf — "Where data lives"

Creates Data Lake Storage with all medallion layer containers.

```hcl
# terraform/storage.tf

# -----------------------------------------------------------
# Azure Data Lake Storage Gen2
# Replaces: data/raw/, data/bronze/, data/silver/, data/gold/
# -----------------------------------------------------------
resource "azurerm_storage_account" "datalake" {
  name                     = "st${replace(var.project_name, "-", "")}${var.environment}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"        # Locally redundant (cheapest)
  account_kind             = "StorageV2"
  is_hns_enabled           = true         # ← This enables Data Lake Gen2

  tags = local.common_tags
}

# -----------------------------------------------------------
# Containers (one per medallion layer)
# -----------------------------------------------------------
resource "azurerm_storage_container" "raw" {
  name                  = "raw"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "bronze" {
  name                  = "bronze"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "silver" {
  name                  = "silver"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "gold" {
  name                  = "gold"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "feature_store" {
  name                  = "feature-store"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "artifacts" {
  name                  = "artifacts"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "drift_reports" {
  name                  = "drift-reports"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}
```

**What this does:** Creates 1 storage account with 7 containers — one for each data layer. `is_hns_enabled = true` makes it a Data Lake (not just blob storage).

---

### databricks.tf — "Where ML training happens"

```hcl
# terraform/databricks.tf

# -----------------------------------------------------------
# Azure Databricks Workspace
# Replaces: local notebooks, MLflow, Feature Store
# -----------------------------------------------------------
resource "azurerm_databricks_workspace" "main" {
  name                = "dbw-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.databricks_sku    # "standard" or "premium"

  tags = local.common_tags
}
```

**What this does:** Creates a Databricks workspace where you upload and run all 10 notebooks. MLflow tracking is built-in.

---

### container_registry.tf — "Where Docker images are stored"

```hcl
# terraform/container_registry.tf

# -----------------------------------------------------------
# Azure Container Registry
# Stores the FastAPI Docker image
# -----------------------------------------------------------
resource "azurerm_container_registry" "main" {
  name                = "acr${replace(var.project_name, "-", "")}${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true     # Allows username/password auth

  tags = local.common_tags
}
```

---

### container_apps.tf — "Where the API runs"

```hcl
# terraform/container_apps.tf

# -----------------------------------------------------------
# Log Analytics Workspace (required by Container Apps)
# -----------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.common_tags
}

# -----------------------------------------------------------
# Container Apps Environment
# -----------------------------------------------------------
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${local.resource_prefix}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = local.common_tags
}

# -----------------------------------------------------------
# Container App — Telemetry API
# Replaces: python api/main.py
# -----------------------------------------------------------
resource "azurerm_container_app" "api" {
  name                         = "telemetry-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Multiple"    # Enables Blue-Green/Canary

  template {
    container {
      name   = "telemetry-api"
      image  = "${azurerm_container_registry.main.login_server}/telemetry-api:${var.api_image_tag}"
      cpu    = 1.0
      memory = "2Gi"

      # Environment variables
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
    }

    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas

    # Auto-scale based on HTTP requests
    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = 50
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  tags = local.common_tags
}
```

**What this does:**
- Creates a Container Apps environment with logging
- Deploys the FastAPI container with auto-scaling (1-5 replicas)
- `revision_mode = "Multiple"` enables Blue-Green / Canary deployments
- External ingress makes it accessible from the internet

---

### monitoring.tf — "How we watch everything"

```hcl
# terraform/monitoring.tf

# -----------------------------------------------------------
# Application Insights
# Replaces: Prometheus + Grafana
# -----------------------------------------------------------
resource "azurerm_application_insights" "main" {
  name                = "ai-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = local.common_tags
}

# -----------------------------------------------------------
# Budget Alert — don't overspend!
# -----------------------------------------------------------
resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "budget-${local.resource_prefix}"
  resource_group_id = azurerm_resource_group.main.id

  amount     = 300      # Monthly budget in USD
  time_grain = "Monthly"

  time_period {
    start_date = "2025-01-01T00:00:00Z"
    end_date   = "2027-12-31T00:00:00Z"
  }

  notification {
    enabled   = true
    threshold = 80     # Alert at 80% of budget
    operator  = "GreaterThan"

    contact_emails = var.alert_email != "" ? [var.alert_email] : []
  }

  notification {
    enabled   = true
    threshold = 100    # Alert at 100% of budget
    operator  = "GreaterThan"

    contact_emails = var.alert_email != "" ? [var.alert_email] : []
  }
}
```

---

### keyvault.tf — "Where secrets are stored"

```hcl
# terraform/keyvault.tf

# -----------------------------------------------------------
# Get current Azure user (for Key Vault access)
# -----------------------------------------------------------
data "azurerm_client_config" "current" {}

# -----------------------------------------------------------
# Azure Key Vault
# -----------------------------------------------------------
resource "azurerm_key_vault" "main" {
  name                = "kv-${replace(local.resource_prefix, "-", "")}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  # Give yourself full access
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = ["Get", "List", "Set", "Delete"]
  }

  tags = local.common_tags
}

# -----------------------------------------------------------
# Store secrets
# -----------------------------------------------------------
resource "azurerm_key_vault_secret" "storage_key" {
  name         = "storage-account-key"
  value        = azurerm_storage_account.datalake.primary_access_key
  key_vault_id = azurerm_key_vault.main.id
}

resource "azurerm_key_vault_secret" "app_insights_key" {
  name         = "app-insights-key"
  value        = azurerm_application_insights.main.instrumentation_key
  key_vault_id = azurerm_key_vault.main.id
}
```

**What this does:** Automatically stores the storage key and App Insights key in Key Vault — no manual secret copying needed.

---

### outputs.tf — "What Terraform tells you after creating"

```hcl
# terraform/outputs.tf

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "storage_account_name" {
  description = "Data Lake storage account name"
  value       = azurerm_storage_account.datalake.name
}

output "databricks_workspace_url" {
  description = "Databricks workspace URL"
  value       = azurerm_databricks_workspace.main.workspace_url
}

output "container_registry_url" {
  description = "ACR login server for docker push"
  value       = azurerm_container_registry.main.login_server
}

output "api_url" {
  description = "Telemetry API public URL"
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "app_insights_key" {
  description = "Application Insights instrumentation key"
  value       = azurerm_application_insights.main.instrumentation_key
  sensitive   = true
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = azurerm_key_vault.main.name
}
```

---

### .gitignore — "Don't commit secrets or state"

```
# terraform/.gitignore

# State files (contain secrets!)
*.tfstate
*.tfstate.backup
.terraform/

# Variable files with secrets
terraform.tfvars
*.auto.tfvars

# Lock file (can be committed, but optional)
# .terraform.lock.hcl

# Crash logs
crash.log
crash.*.log
```

---

## How to Run Terraform (Step by Step)

### Step 1: Initialize

Downloads the Azure provider plugin. Run once per project.

```powershell
cd D:\Sathish\ML_Device_Telemetry\device_telemetry_mlops\terraform

terraform init
```

**You'll see:**
```
Initializing the backend...
Initializing provider plugins...
- Installing hashicorp/azurerm v3.80.0...
Terraform has been successfully initialized!
```

### Step 2: Plan (Preview)

Shows what Terraform WILL create — **nothing is created yet**.

```powershell
terraform plan
```

**You'll see:**
```
Plan: 15 to add, 0 to change, 0 to destroy.

  + azurerm_resource_group.main
  + azurerm_storage_account.datalake
  + azurerm_storage_container.raw
  + azurerm_storage_container.bronze
  + azurerm_storage_container.silver
  + azurerm_storage_container.gold
  ...
```

Review this carefully — it shows exactly what will be created.

### Step 3: Apply (Create)

Actually creates all resources in Azure.

```powershell
terraform apply
```

Terraform will show the plan again and ask:
```
Do you want to perform these actions?
  Enter a value: yes
```

Type `yes` and press Enter. Wait 5-10 minutes.

**You'll see outputs:**
```
Apply complete! Resources: 15 added, 0 changed, 0 destroyed.

Outputs:
  api_url                = "https://telemetry-api.uksouth.azurecontainerapps.io"
  databricks_workspace_url = "https://adb-1234567890.azuredatabricks.net"
  storage_account_name   = "stdevicetelemetrydev"
```

### Step 4: Verify

```powershell
# Check what Terraform created
terraform state list

# See details of a specific resource
terraform state show azurerm_container_app.api
```

### Step 5: Destroy (When Done)

Deletes ALL resources to stop charges:

```powershell
terraform destroy
```

Type `yes` to confirm. **This cannot be undone.**

---

## Common Terraform Commands

| Command | What it does | When to use |
|---------|-------------|-------------|
| `terraform init` | Downloads provider plugins | First time, or after changing providers |
| `terraform plan` | Preview changes | Before every apply |
| `terraform apply` | Create/update resources | When you want to deploy |
| `terraform destroy` | Delete all resources | When you're done (stops billing) |
| `terraform state list` | Show all managed resources | To see what exists |
| `terraform output` | Show output values | To get URLs, keys |
| `terraform fmt` | Format .tf files | Before committing code |
| `terraform validate` | Check syntax errors | Before planning |

---

## Typical Workflow

```
                    ┌──────────────┐
                    │  Edit .tf    │
                    │  files       │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ terraform    │  ← Preview (safe, read-only)
                    │ plan         │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Review       │  ← Does the plan look right?
                    │ changes      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ terraform    │  ← Actually create resources
                    │ apply        │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ git commit   │  ← Track changes in Git
                    │ .tf files    │
                    └──────────────┘
```

---

## Updating Resources

To change something (e.g., increase API replicas):

1. Edit `terraform.tfvars`:
   ```hcl
   api_max_replicas = 10    # was 5
   ```

2. Run plan to preview:
   ```powershell
   terraform plan
   ```
   Output: `1 to change`

3. Apply:
   ```powershell
   terraform apply
   ```

Terraform only changes what's different — it won't recreate everything.

---

## Multiple Environments

Create separate tfvars files for each environment:

```
terraform/
├── terraform.tfvars         # dev (default)
├── staging.tfvars           # staging
└── prod.tfvars              # production
```

```powershell
# Deploy to staging
terraform plan -var-file="staging.tfvars"
terraform apply -var-file="staging.tfvars"

# Deploy to production
terraform plan -var-file="prod.tfvars"
terraform apply -var-file="prod.tfvars"
```

---

## Quick Reference

| Action | Command |
|--------|---------|
| First-time setup | `terraform init` |
| Preview changes | `terraform plan` |
| Deploy | `terraform apply` |
| Destroy everything | `terraform destroy` |
| Format code | `terraform fmt` |
| Check syntax | `terraform validate` |
| List resources | `terraform state list` |
| Get API URL | `terraform output api_url` |
| Deploy to staging | `terraform apply -var-file="staging.tfvars"` |
