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
