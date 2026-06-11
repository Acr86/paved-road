output "deploy_role_arn" {
  description = "ARN of the deploy role. Pass it to resource modules for resource-scoped grants; the role itself ships with zero permissions."
  value       = aws_iam_role.deploy.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider. Account-global: AWS allows exactly one provider per issuer URL per account."
  value       = aws_iam_openid_connect_provider.github.arn
}
