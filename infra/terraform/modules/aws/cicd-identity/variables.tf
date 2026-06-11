variable "name_prefix" {
  type        = string
  description = "Prefix for named resources; the deploy role is created as \"<name_prefix>-deploy\"."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,56}$", var.name_prefix))
    error_message = "name_prefix must start with a lowercase letter, contain only lowercase letters, digits, and hyphens, and be 2-57 characters (IAM role names cap at 64 including the \"-deploy\" suffix)."
  }
}

variable "github_repository" {
  type        = string
  description = "GitHub repository whose workflows may assume the deploy role, in \"owner/name\" form."

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be in \"owner/name\" form, e.g. \"acme/platform\"."
  }
}

variable "allowed_refs" {
  type        = list(string)
  description = "Git refs in github_repository allowed to assume the deploy role. Each entry is rendered as one subject condition value (\"repo:<owner/name>:ref:<ref>\"). Wildcards are allowed within a ref, e.g. \"refs/tags/v*\"."
  default     = ["refs/heads/main"]

  validation {
    condition = length(var.allowed_refs) > 0 && alltrue([
      for ref in var.allowed_refs : can(regex("^refs/(heads|tags)/.+", ref))
    ])
    error_message = "allowed_refs must be non-empty and every entry must start with \"refs/heads/\" or \"refs/tags/\"; pull_request and environment subjects are deliberately not supported by this module."
  }
}
