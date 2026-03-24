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
