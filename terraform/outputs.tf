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
