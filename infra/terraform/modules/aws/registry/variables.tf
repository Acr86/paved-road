variable "name" {
  type        = string
  description = "Name of the ECR repository. Typically one repository per service, e.g. \"platform/orders-api\"."

  validation {
    condition     = can(regex("^[a-z0-9]+(?:[._/-][a-z0-9]+)*$", var.name))
    error_message = "Repository name must be lowercase alphanumeric, optionally separated by '.', '_', '-' or '/' (ECR naming rules)."
  }
}

variable "image_tag_mutability" {
  type        = string
  description = <<-EOT
    Tag mutability for the repository. Defaults to MUTABLE on purpose: the deploy
    pipeline promotes images by digest, not by tag, so a moving tag (e.g. "main")
    is a convenience pointer for humans while the digest remains the immutable
    deployment identity. Set to IMMUTABLE if your pipeline deploys by tag.
  EOT
  default     = "MUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "image_tag_mutability must be either MUTABLE or IMMUTABLE."
  }
}

variable "untagged_retention_days" {
  type        = number
  description = "Days to keep untagged images before the lifecycle policy expires them. Untagged images are layers nothing points to by name; they only cost storage."
  default     = 7

  validation {
    condition     = var.untagged_retention_days >= 1 && floor(var.untagged_retention_days) == var.untagged_retention_days
    error_message = "untagged_retention_days must be a whole number of at least 1."
  }
}

variable "keep_tagged_count" {
  type        = number
  description = "Number of most recent images to keep per tag-prefix rule; older tagged images are expired. Sized to cover realistic rollback depth, not history forever."
  default     = 20

  validation {
    condition     = var.keep_tagged_count >= 1 && floor(var.keep_tagged_count) == var.keep_tagged_count
    error_message = "keep_tagged_count must be a whole number of at least 1."
  }
}

variable "tag_prefixes" {
  type        = list(string)
  description = "Tag prefixes the keep-last-N lifecycle rule applies to. Defaults match the platform tagging convention: \"main\" for trunk builds, \"pr-\" for review builds."
  default     = ["main", "pr-"]

  validation {
    condition     = length(var.tag_prefixes) > 0
    error_message = "tag_prefixes must contain at least one prefix, otherwise tagged images would never be cleaned up."
  }

  validation {
    condition     = alltrue([for p in var.tag_prefixes : length(trimspace(p)) > 0])
    error_message = "tag_prefixes must not contain empty or whitespace-only entries."
  }
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of a customer-managed KMS key to encrypt images. When null, ECR's default AES-256 encryption is used (still encrypted at rest, just not with your key)."
  default     = null
  nullable    = true

  validation {
    condition     = var.kms_key_arn == null || can(regex("^arn:aws[a-zA-Z-]*:kms:[a-z0-9-]+:[0-9]{12}:key/", var.kms_key_arn))
    error_message = "kms_key_arn must be a KMS key ARN (arn:aws:kms:<region>:<account>:key/...)."
  }
}

variable "force_delete" {
  type        = bool
  description = "Allow deleting the repository even when it still contains images. Defaults to false so a terraform destroy cannot silently take deployed image history with it."
  default     = false
}
