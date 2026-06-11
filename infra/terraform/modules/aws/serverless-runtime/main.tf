data "aws_partition" "current" {}

locals {
  secretsmanager_arns = distinct(sort([
    for arn in values(var.secret_env) : arn
    if length(regexall("^arn:aws[a-z-]*:secretsmanager:", arn)) > 0
  ]))

  ssm_parameter_arns = distinct(sort([
    for arn in values(var.secret_env) : arn
    if length(regexall("^arn:aws[a-z-]*:ssm:", arn)) > 0
  ]))
}

# --- Identity: two roles, two jobs ---------------------------------------
# The access role is assumed by App Runner's build/deploy plane to pull from
# ECR; the instance role is what the application code runs as. Keeping them
# separate means a compromised runtime cannot touch the registry.

data "aws_iam_policy_document" "instance_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.name}-instance"
  description        = "Runtime identity for the ${var.name} App Runner service."
  assume_role_policy = data.aws_iam_policy_document.instance_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "access_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "access" {
  name               = "${var.name}-ecr-access"
  description        = "ECR pull identity for the ${var.name} App Runner service."
  assume_role_policy = data.aws_iam_policy_document.access_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "ecr_access" {
  role       = aws_iam_role.access.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# Referencing a secret in secret_env grants the instance role read on exactly
# that ARN — nothing wider. The role carries no other permissions by default;
# application-specific grants belong to the consumer.
data "aws_iam_policy_document" "runtime_secrets" {
  count = length(var.secret_env) > 0 ? 1 : 0

  dynamic "statement" {
    for_each = length(local.secretsmanager_arns) > 0 ? [1] : []

    content {
      sid       = "ReadReferencedSecrets"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = local.secretsmanager_arns
    }
  }

  dynamic "statement" {
    for_each = length(local.ssm_parameter_arns) > 0 ? [1] : []

    content {
      sid       = "ReadReferencedParameters"
      actions   = ["ssm:GetParameters"]
      resources = local.ssm_parameter_arns
    }
  }
}

resource "aws_iam_role_policy" "runtime_secrets" {
  count = length(var.secret_env) > 0 ? 1 : 0

  name   = "runtime-secrets"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.runtime_secrets[0].json
}

# --- Network: egress through the VPC, private ingress by default ----------

resource "aws_security_group" "connector" {
  name_prefix = "${var.name}-vpc-"
  description = "Egress-only security group for the ${var.name} App Runner VPC connector"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-vpc-connector" })

  lifecycle {
    create_before_destroy = true
  }
}

# Connector ENIs only ever originate traffic, so this group deliberately has
# no ingress rules at all.
resource "aws_vpc_security_group_egress_rule" "connector_all" {
  security_group_id = aws_security_group.connector.id
  description       = "Allow all outbound traffic from the service workload"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_apprunner_vpc_connector" "this" {
  vpc_connector_name = "${var.name}-vpc"
  subnets            = var.subnet_ids
  security_groups    = [aws_security_group.connector.id]
  tags               = var.tags
}

# --- Scaling ---------------------------------------------------------------

resource "aws_apprunner_auto_scaling_configuration_version" "this" {
  auto_scaling_configuration_name = "${var.name}-asc"
  min_size                        = var.min_instances
  max_size                        = var.max_instances
  tags                            = var.tags
}

# --- Service ---------------------------------------------------------------

resource "aws_apprunner_service" "this" {
  service_name = var.name

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.access.arn
    }

    # Deploys are explicit pipeline actions: CI calls start-deployment with a
    # pinned digest. Pushing a tag to ECR must never roll the service on its
    # own.
    auto_deployments_enabled = false

    image_repository {
      image_identifier      = var.image
      image_repository_type = "ECR"

      image_configuration {
        port                          = var.port
        runtime_environment_variables = var.env
        runtime_environment_secrets   = var.secret_env
      }
    }
  }

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.instance.arn
  }

  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.this.arn
    }

    ingress_configuration {
      is_publicly_accessible = var.public
    }
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.this.arn

  tags = var.tags

  # Service creation races IAM propagation of the ECR pull policy; without
  # this ordering the first apply intermittently fails to pull the image.
  depends_on = [aws_iam_role_policy_attachment.ecr_access]

  # CI owns the image: Terraform only sets the bootstrap image at creation,
  # and every subsequent release is deployed by the pipeline with a pinned
  # digest. Without ignore_changes, every plan would try to roll the service
  # back to the bootstrap image. Same ownership split as the GCP
  # serverless-runtime twin.
  lifecycle {
    ignore_changes = [source_configuration[0].image_repository[0].image_identifier]
  }
}
