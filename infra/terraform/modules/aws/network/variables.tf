variable "name_prefix" {
  type        = string
  description = "Prefix applied to every resource name and Name tag (e.g. \"platform-staging\")."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,28}[a-z0-9]$", var.name_prefix))
    error_message = "name_prefix must be 3-30 chars, lowercase alphanumeric and hyphens, starting with a letter and not ending with a hyphen."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "IPv4 CIDR block for the VPC. Subnets are carved with 4 extra prefix bits, so a /16 yields /20 subnets."

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block (e.g. 10.0.0.0/16)."
  }

  validation {
    condition = (
      can(cidrhost(var.vpc_cidr, 0)) &&
      tonumber(split("/", var.vpc_cidr)[1]) >= 16 &&
      tonumber(split("/", var.vpc_cidr)[1]) <= 24
    )
    error_message = "vpc_cidr prefix length must be between /16 and /24 so the cidrsubnet math leaves usable subnet sizes."
  }
}

variable "az_count" {
  type        = number
  description = "Number of availability zones to spread subnets across. One private and one public subnet are created per AZ."
  default     = 2

  validation {
    condition     = var.az_count >= 1 && var.az_count <= 3 && floor(var.az_count) == var.az_count
    error_message = "az_count must be a whole number between 1 and 3."
  }
}

variable "flow_log_kms_key_arn" {
  type        = string
  description = "Optional KMS key ARN encrypting the flow log group. The key policy must allow the CloudWatch Logs service principal (the audit-log-sink module's key qualifies)."
  default     = null
}

variable "flow_log_retention_days" {
  type        = number
  description = "Retention in days for the VPC flow log CloudWatch log group. Must be a value CloudWatch Logs accepts. Network telemetry is security evidence: a year is the floor, not the ceiling."
  default     = 365

  validation {
    condition = contains(
      [1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653],
      var.flow_log_retention_days
    )
    error_message = "flow_log_retention_days must be one of the retention values supported by CloudWatch Logs (1, 3, 5, 7, 14, 30, 60, 90, ...)."
  }
}
