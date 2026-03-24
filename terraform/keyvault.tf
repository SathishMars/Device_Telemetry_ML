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
