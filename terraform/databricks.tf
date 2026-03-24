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
