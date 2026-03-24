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
