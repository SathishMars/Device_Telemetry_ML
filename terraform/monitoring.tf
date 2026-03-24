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
