variable "name_prefix" {
  type        = string
  description = "Prefix for all named resources (bucket, Firehose stream, IAM roles). Lowercase alphanumeric and hyphens."

  validation {
    condition     = can(regex("^[a-z](?:[a-z0-9-]*[a-z0-9])?$", var.name_prefix))
    error_message = "name_prefix must start with a letter, contain only lowercase letters, digits and hyphens, and not end with a hyphen."
  }

  validation {
    condition     = length(var.name_prefix) <= 40
    error_message = "name_prefix must be 40 characters or fewer so derived bucket and IAM role names stay within AWS limits."
  }
}

variable "retention_years" {
  type        = number
  description = "Default Object Lock retention applied to every object written to the archive bucket, in years."
  default     = 7

  validation {
    condition     = var.retention_years >= 1 && var.retention_years <= 100 && floor(var.retention_years) == var.retention_years
    error_message = "retention_years must be a whole number between 1 and 100."
  }
}

variable "worm_mode" {
  type        = string
  description = "S3 Object Lock retention mode. GOVERNANCE can be bypassed with s3:BypassGovernanceRetention; COMPLIANCE cannot be shortened by anyone, including the root user, until retention expires."
  default     = "GOVERNANCE"

  validation {
    condition     = contains(["GOVERNANCE", "COMPLIANCE"], var.worm_mode)
    error_message = "worm_mode must be either GOVERNANCE or COMPLIANCE."
  }
}

variable "glacier_after_days" {
  type        = number
  description = "Days after which archive objects (current and noncurrent versions) transition to the GLACIER storage class."
  default     = 90

  validation {
    condition     = var.glacier_after_days >= 1 && floor(var.glacier_after_days) == var.glacier_after_days
    error_message = "glacier_after_days must be a whole number of at least 1."
  }
}

variable "log_group_name" {
  type        = string
  description = "Name of the CloudWatch log group that receives audit events before they are streamed to the archive (e.g. /platform/audit)."

  validation {
    condition     = can(regex("^[A-Za-z0-9_/.#-]{1,512}$", var.log_group_name))
    error_message = "log_group_name may only contain letters, digits, and the characters _ / . # - (1-512 characters)."
  }
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log group retention in days. This is the hot search tier only; long-term retention lives in the WORM bucket, so 0 (never expire) is deliberately not allowed."
  default     = 365

  validation {
    condition = contains(
      [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653],
      var.log_retention_days
    )
    error_message = "log_retention_days must be one of the values accepted by CloudWatch Logs (1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653)."
  }
}

variable "kms_key_arn" {
  type        = string
  description = "Optional customer-managed KMS key ARN. When set, the bucket, the Firehose stream, and the log group encrypt with it and its policy must allow the CloudWatch Logs and Firehose service principals. When null, the module creates a rotated CMK with that policy — audit data is never merely SSE-S3."
  default     = null

  validation {
    condition     = var.kms_key_arn == null || can(regex("^arn:aws[a-z-]*:kms:[a-z0-9-]+:[0-9]{12}:key/", var.kms_key_arn))
    error_message = "kms_key_arn must be a full KMS key ARN (arn:aws:kms:<region>:<account>:key/<id>) or null."
  }
}
