# aws/serverless-runtime

Runs a containerized HTTP service on AWS App Runner: the service itself, a VPC connector with a dedicated egress-only security group, an auto scaling configuration, a runtime instance role, and an ECR pull (access) role. It is the AWS mirror of the `gcp/serverless-runtime` module and keeps the same ownership contract: Terraform bootstraps the service, its identity and its network posture once, while the CI pipeline owns the running image and deploys releases by pinned digest.

## Usage

```hcl
module "api_runtime" {
  source = "../../modules/aws/serverless-runtime"

  name       = "platform-api"
  image      = "123456789012.dkr.ecr.us-east-1.amazonaws.com/platform-api:bootstrap"
  port       = 8080
  vpc_id     = module.network.vpc_id
  subnet_ids = module.network.private_subnet_ids

  env = {
    LOG_LEVEL = "info"
  }

  secret_env = {
    DATABASE_URL = aws_secretsmanager_secret.database_url.arn
  }

  min_instances = 1
  max_instances = 4

  tags = {
    environment = "staging"
    service     = "platform-api"
  }
}
```

## Opinions

- **CI owns the image, Terraform owns everything else.** The `image` variable is only the bootstrap image. `ignore_changes` on the image identifier plus `auto_deployments_enabled = false` means releases are explicit pipeline actions (`start-deployment` with a pinned digest) — a tag push to ECR never rolls the service, and a Terraform plan never rolls it back. This is the exact ownership split used by the GCP twin.
- **Private by default.** `public` defaults to `false`; exposing a service to the internet is a deliberate, reviewable line in the consumer's diff. All egress flows through the VPC connector.
- **The connector security group is egress-only, by construction.** It is created inside the module with zero ingress rules — connector ENIs only ever originate traffic, so there is nothing to allow inbound.
- **Two roles, two jobs.** The access role (assumed by `build.apprunner.amazonaws.com`) can pull from ECR and nothing else; the instance role (assumed by `tasks.apprunner.amazonaws.com`) is what application code runs as and starts with no permissions. A compromised runtime cannot touch the registry.
- **Secrets are references, not values.** `secret_env` accepts only Secrets Manager / SSM parameter ARNs, and the module grants the instance role read on exactly those ARNs — nothing wider. Plaintext secrets never transit Terraform state through `env`, and an `env`/`secret_env` name collision is rejected at plan time.
- **Invalid sizing fails at plan, not at deploy.** `cpu`/`memory` are validated against App Runner's actual supported combination matrix, and `max_instances >= min_instances` is enforced across variables.
- **Genuine deltas from the GCP twin, stated rather than papered over.** App Runner cannot scale to zero (`min_instances >= 1` is enforced, so the idle floor is a real cost), and it has no analog of a scale-to-zero Cloud Run job. Database migrations therefore need a different vehicle on AWS: run them as one-off ECS `RunTask` invocations on Fargate, reusing the same image and the instance role pattern — not as a second App Runner service.
