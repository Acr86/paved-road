variable "name" {
  type        = string
  description = "Service name. Used as the App Runner service name and as the prefix for the VPC connector, security group, auto scaling configuration and IAM roles."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,26}[a-z0-9]$", var.name))
    error_message = "name must be 4-28 characters, lowercase alphanumeric and hyphens, start with a letter and not end with a hyphen (suffixed resource names must stay inside App Runner's 32/40 character limits)."
  }
}

variable "image" {
  type        = string
  description = "Initial container image identifier in a private ECR repository (tag or digest form). Only consumed at bootstrap: after creation, CI owns the image and Terraform ignores drift on it."

  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/.+(:[A-Za-z0-9._-]+|@sha256:[a-f0-9]{64})$", var.image))
    error_message = "image must reference a private ECR repository (<account>.dkr.ecr.<region>.amazonaws.com/<repo>) with an explicit :tag or @sha256 digest; the service is wired for ECR authentication only."
  }
}

variable "port" {
  type        = number
  description = "Container port the application listens on."
  default     = 8080

  validation {
    condition     = var.port >= 1 && var.port <= 65535
    error_message = "port must be between 1 and 65535."
  }
}

variable "env" {
  type        = map(string)
  description = "Plain runtime environment variables (name to value). Never put secret material here; use secret_env so values stay out of Terraform state and plan output."
  default     = {}

  validation {
    condition     = alltrue([for k in keys(var.env) : can(regex("^[A-Za-z_][A-Za-z0-9_]*$", k))])
    error_message = "env keys must be valid environment variable names ([A-Za-z_][A-Za-z0-9_]*)."
  }
}

variable "secret_env" {
  type        = map(string)
  description = "Secret runtime environment variables: name to Secrets Manager secret ARN or SSM parameter ARN. The instance role is automatically granted read on exactly these ARNs."
  default     = {}

  validation {
    condition     = alltrue([for k in keys(var.secret_env) : can(regex("^[A-Za-z_][A-Za-z0-9_]*$", k))])
    error_message = "secret_env keys must be valid environment variable names ([A-Za-z_][A-Za-z0-9_]*)."
  }

  validation {
    condition = alltrue([
      for arn in values(var.secret_env) :
      can(regex("^arn:aws[a-z-]*:(secretsmanager|ssm):", arn))
    ])
    error_message = "secret_env values must be Secrets Manager secret ARNs or SSM parameter ARNs; raw secret values are not accepted."
  }

  validation {
    condition     = length(setintersection(toset(keys(var.env)), toset(keys(var.secret_env)))) == 0
    error_message = "env and secret_env must not declare the same variable name; the collision would be resolved silently by the platform."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC in which the egress-only security group for the VPC connector is created."

  validation {
    condition     = startswith(var.vpc_id, "vpc-")
    error_message = "vpc_id must be a VPC id (vpc-...)."
  }
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet ids the VPC connector places its ENIs in. Use at least two subnets in distinct availability zones."

  validation {
    condition     = length(var.subnet_ids) > 0 && alltrue([for s in var.subnet_ids : startswith(s, "subnet-")])
    error_message = "subnet_ids must contain at least one subnet id (subnet-...)."
  }
}

variable "public" {
  type        = bool
  description = "Whether the service accepts traffic from the public internet. Defaults to false: private ingress, reachable only through a VPC ingress connection or an internal entry point."
  default     = false
}

variable "min_instances" {
  type        = number
  description = "Minimum number of provisioned instances. App Runner cannot scale to zero, so this is also the idle footprint you pay for."
  default     = 1

  validation {
    condition     = var.min_instances >= 1 && var.min_instances <= 25
    error_message = "min_instances must be between 1 and 25; App Runner has no scale-to-zero."
  }
}

variable "max_instances" {
  type        = number
  description = "Maximum number of instances the service may scale out to."
  default     = 3

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 25
    error_message = "max_instances must be between 1 and 25 (the default App Runner service quota)."
  }

  validation {
    condition     = var.max_instances >= var.min_instances
    error_message = "max_instances must be greater than or equal to min_instances."
  }
}

variable "cpu" {
  type        = string
  description = "vCPU units per instance (1024 = 1 vCPU). Must form a combination App Runner supports together with memory."
  default     = "1024"

  validation {
    condition     = contains(["256", "512", "1024", "2048", "4096"], var.cpu)
    error_message = "cpu must be one of 256, 512, 1024, 2048, 4096."
  }
}

variable "memory" {
  type        = string
  description = "Memory in MB per instance. Validated against the cpu value at plan time, because App Runner only accepts specific cpu/memory pairs."
  default     = "2048"

  validation {
    condition = contains(lookup({
      "256"  = ["512", "1024"]
      "512"  = ["1024"]
      "1024" = ["2048", "3072", "4096"]
      "2048" = ["4096", "6144"]
      "4096" = ["8192", "10240", "12288"]
    }, var.cpu, []), var.memory)
    error_message = "memory is not a valid pairing for the selected cpu. Supported: 256->[512,1024], 512->[1024], 1024->[2048,3072,4096], 2048->[4096,6144], 4096->[8192,10240,12288]."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to every resource the module creates."
  default     = {}
}
