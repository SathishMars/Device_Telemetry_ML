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
