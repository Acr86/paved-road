output "repository_url" {
  description = "Full URL of the repository (account.dkr.ecr.region.amazonaws.com/name), the value docker push and pull targets use."
  value       = aws_ecr_repository.this.repository_url
}

output "repository_arn" {
  description = "ARN of the repository, for IAM policies granting push/pull to CI and runtime roles."
  value       = aws_ecr_repository.this.arn
}

output "registry_id" {
  description = "AWS account ID of the registry hosting the repository."
  value       = aws_ecr_repository.this.registry_id
}
