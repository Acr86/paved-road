output "endpoint" {
  description = "Connection endpoint in address:port form."
  value       = aws_db_instance.this.endpoint
}

output "address" {
  description = "DNS address of the instance."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Port the instance listens on."
  value       = aws_db_instance.this.port
}

output "instance_arn" {
  description = "ARN of the DB instance (for IAM auth policies and monitoring scoping)."
  value       = aws_db_instance.this.arn
}

output "master_user_secret_arn" {
  description = "ARN of the RDS-managed Secrets Manager secret holding the master user credentials."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "security_group_id" {
  description = "ID of the database security group (reference it to grant additional ingress sources out of band)."
  value       = aws_security_group.this.id
}

output "database_name" {
  description = "Name of the initial database (parity with the GCP twin: consumers read it from here, not from a duplicated literal)."
  value       = aws_db_instance.this.db_name
}
