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
