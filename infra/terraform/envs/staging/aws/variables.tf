variable "region" {
  type        = string
  description = "AWS region for all regional resources in this environment. Each environment lives in its own AWS account, so names do not need an account-level discriminator."
  default     = "eu-west-1"

  validation {
    condition     = can(regex("^[a-z]{2}(-[a-z]+)+-[0-9]$", var.region))
    error_message = "region must be a valid AWS region identifier such as eu-west-1 or us-east-1."
  }
}

variable "github_repository" {
  type        = string
  description = "GitHub repository (owner/name) whose workflows are allowed to assume the deploy role via OIDC."
  default     = "Acr86/paved-road"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
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
