output "service_arn" {
  description = "ARN of the App Runner service."
  value       = aws_apprunner_service.this.arn
}

output "service_url" {
  description = "HTTPS URL of the service. App Runner exposes a bare hostname; the scheme is prefixed here for parity with the GCP twin's URI output."
  value       = "https://${aws_apprunner_service.this.service_url}"
}

output "instance_role_arn" {
  description = "ARN of the runtime instance role. Attach application-specific permissions (queues, buckets, tables) to this role from the consuming stack."
  value       = aws_iam_role.instance.arn
}

output "connector_security_group_id" {
  description = "Security group of the VPC connector — the identity of this workload's egress. Scope database/cache ingress to this SG instead of CIDR ranges."
  value       = aws_security_group.connector.id
}
