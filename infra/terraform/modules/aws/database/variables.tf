variable "name" {
  type        = string
  description = "Instance identifier. Also used to derive the subnet group, security group, parameter group, and final snapshot names."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.name)) && length(var.name) <= 60 && !strcontains(var.name, "--")
    error_message = "name must be 2-60 chars, lowercase alphanumeric and single hyphens, start with a letter, end alphanumeric (RDS identifier rules)."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC in which the database security group is created. Must contain the private subnets."

  validation {
    condition     = startswith(var.vpc_id, "vpc-")
    error_message = "vpc_id must be a VPC ID (vpc-...)."
  }
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the DB subnet group. At least two, in distinct AZs (RDS requirement, and a Multi-AZ prerequisite)."

  validation {
    condition     = length(var.private_subnet_ids) >= 2 && alltrue([for s in var.private_subnet_ids : startswith(s, "subnet-")])
    error_message = "private_subnet_ids needs at least two subnet IDs (subnet-...)."
  }
}

variable "allowed_security_group_ids" {
  type        = list(string)
  description = "Security groups granted ingress to PostgreSQL (5432). The preferred way to authorize workloads."
  default     = []

  validation {
    condition     = alltrue([for sg in var.allowed_security_group_ids : startswith(sg, "sg-")])
    error_message = "allowed_security_group_ids entries must be security group IDs (sg-...)."
  }

  validation {
    condition     = length(var.allowed_security_group_ids) + length(var.allowed_cidr_blocks) > 0
    error_message = "Provide at least one ingress source via allowed_security_group_ids or allowed_cidr_blocks; a database nothing can reach is a misconfiguration."
  }
}

variable "allowed_cidr_blocks" {
  type        = list(string)
  description = "IPv4 CIDR blocks granted ingress to PostgreSQL (5432). For sources without a security group (e.g. peered networks)."
  default     = []

  validation {
    condition     = alltrue([for c in var.allowed_cidr_blocks : can(cidrnetmask(c))])
    error_message = "allowed_cidr_blocks entries must be valid IPv4 CIDR blocks."
  }

  validation {
    condition     = !contains(var.allowed_cidr_blocks, "0.0.0.0/0")
    error_message = "0.0.0.0/0 is not an acceptable ingress source for a database. List the actual client networks."
  }
}

variable "engine_version" {
  type        = string
  description = "PostgreSQL engine version. This module targets major version 17; minor versions track automatically via auto_minor_version_upgrade."
  default     = "17.4"

  validation {
    condition     = can(regex("^17(\\.|$)", var.engine_version))
    error_message = "engine_version must be PostgreSQL 17.x. A major version change is a new module contract, not a variable flip."
  }
}

variable "instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.micro"

  validation {
    condition     = startswith(var.instance_class, "db.")
    error_message = "instance_class must be an RDS class (db.*)."
  }
}

variable "allocated_storage" {
  type        = number
  description = "Initial storage in GiB (gp3)."
  default     = 20

  validation {
    condition     = var.allocated_storage >= 20
    error_message = "allocated_storage must be at least 20 GiB (gp3 minimum)."
  }
}

variable "max_allocated_storage" {
  type        = number
  description = "Storage autoscaling ceiling in GiB. Must exceed allocated_storage; autoscaling cannot be disabled through this module."
  default     = 100

  validation {
    condition     = var.max_allocated_storage > var.allocated_storage
    error_message = "max_allocated_storage must be greater than allocated_storage; a full disk should never be the incident."
  }
}

variable "database_name" {
  type        = string
  description = "Name of the initial database created on the instance."

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]*$", var.database_name)) && length(var.database_name) <= 63
    error_message = "database_name must be lowercase snake_case, start with a letter, max 63 chars (avoids quoted-identifier pain in PostgreSQL)."
  }
}

variable "master_username" {
  type        = string
  description = "Master username. The password is generated and stored by RDS in Secrets Manager; it never appears in Terraform state."
  default     = "app_admin"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]*$", var.master_username)) && !contains(["rdsadmin", "rds_superuser", "admin", "postgres"], var.master_username)
    error_message = "master_username must be lowercase snake_case and not an RDS-reserved name (rdsadmin, rds_superuser, admin, postgres)."
  }
}

variable "ha" {
  type        = bool
  description = "Multi-AZ deployment. Defaults to true; opting out is an explicit dev/sandbox decision."
  default     = true
}

variable "backup_retention_period" {
  type        = number
  description = "Automated backup retention in days. Minimum 1: disabling backups is not an option this module offers."
  default     = 7

  validation {
    condition     = var.backup_retention_period >= 1 && var.backup_retention_period <= 35
    error_message = "backup_retention_period must be between 1 and 35 days."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "Protect the instance from deletion. Disable only as a deliberate, reviewed step before decommissioning."
  default     = true
}

variable "kms_key_id" {
  type        = string
  description = "Optional customer-managed KMS key ARN. When set it covers storage, Performance Insights, and the managed master-user secret. When null, AWS-managed keys are used; encryption itself is never optional."
  default     = null
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource in the module."
  default     = {}
}
