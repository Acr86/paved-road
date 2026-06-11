# aws/database

Opinionated PostgreSQL 17 on Amazon RDS, mirroring the platform's GCP database module: private-only networking, IAM database authentication, encryption everywhere, and backups that cannot be turned off. The module owns its entire network perimeter (subnet group plus a dedicated security group) so callers declare *who* may connect and never touch port rules directly.

## Usage

```hcl
module "orders_db" {
  source = "../../modules/aws/database"

  name               = "platform-orders"
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids

  allowed_security_group_ids = [module.orders_service.security_group_id]

  database_name  = "orders"
  instance_class = "db.r6g.large"

  allocated_storage     = 100
  max_allocated_storage = 500

  ha                      = true
  backup_retention_period = 14
  kms_key_id              = aws_kms_key.data.arn

  tags = {
    team        = "commerce"
    environment = "production"
  }
}
```

## Opinions

- **No public access path exists.** `publicly_accessible` is hardcoded to `false`, not exposed as a variable. The subnet group only accepts private subnets and ingress is limited to declared security groups or CIDRs. `0.0.0.0/0` is rejected at plan time, and a configuration with zero ingress sources is rejected too — an unreachable database is a misconfiguration, not a security posture.
- **The master password never enters Terraform state.** `manage_master_user_password = true` makes RDS generate the credential and own its Secrets Manager lifecycle (including rotation). The `random_password` alternative writes the secret in plaintext into every copy of the state file forever; consumers read `master_user_secret_arn` instead.
- **IAM database authentication is always on.** Workloads and humans should authenticate with short-lived IAM tokens scoped by policy; the master credential is for bootstrap and break-glass, not daily traffic.
- **Backups are not optional.** `backup_retention_period` defaults to 7 days (point-in-time recovery, mirroring the GCP module's PITR default) and validation rejects 0. Deletion protection defaults on and a final snapshot is always taken — destroying the instance always leaves a recovery point.
- **Encryption is not optional either.** `storage_encrypted` is hardcoded. Passing a customer-managed KMS key applies it consistently to storage, Performance Insights, and the managed master-user secret; omitting it falls back to AWS-managed keys, never to plaintext.
- **TLS is required at the engine.** The bundled parameter group sets `rds.force_ssl = 1`, so a client that skips TLS is refused regardless of its network position.
- **Multi-AZ by default.** Single-AZ (`ha = false`) is the explicit opt-out for sandboxes, not the silent default for production.
- **Stay current within the major version.** `auto_minor_version_upgrade = true` keeps minor patches flowing; `allow_major_version_upgrade = false` plus a `17.x` validation make a major upgrade a deliberate module-contract change, never an accidental variable edit.
- **A full disk should never be the incident.** gp3 storage with autoscaling is mandatory: `max_allocated_storage` must exceed `allocated_storage` and autoscaling cannot be disabled through this module.
- **Default-deny outbound.** The security group defines no egress rules at all — RDS never initiates outbound connections, so none are granted.
- **Observability built in.** Performance Insights is always enabled and the `postgresql` and `upgrade` logs are exported to CloudWatch; slow-query forensics should not require a redeploy.
