variable "project_id" {
  type        = string
  description = "GCP project that hosts the production environment. One project per environment; production never shares a project with staging."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid GCP project id (6-30 chars, lowercase letters, digits, hyphens, starting with a letter)."
  }
}

variable "region" {
  type        = string
  description = "Region for all regional resources in this environment."
  default     = "europe-west1"

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]$", var.region))
    error_message = "region must be a valid GCP region identifier such as europe-west1 or us-central1."
  }
}

variable "github_repository" {
  type        = string
  description = "GitHub repository (owner/name) whose workflows are allowed to deploy this environment via workload identity federation."
  default     = "Acr86/paved-road"

  validation {
    condition     = can(regex("^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "github_repository must be in owner/name form, e.g. acme/platform."
  }
}

variable "app_image_tag" {
  type        = string
  description = "Tag of the bootstrap application image. Consumed on first apply only; afterwards CI deploys by digest and Terraform ignores image drift."
  default     = "bootstrap"

  validation {
    condition     = length(var.app_image_tag) > 0 && var.app_image_tag != "latest"
    error_message = "app_image_tag must be a non-empty, explicit tag; latest is not reproducible."
  }
}
