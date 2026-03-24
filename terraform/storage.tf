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
