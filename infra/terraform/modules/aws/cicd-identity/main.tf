# AWS validates the GitHub OIDC issuer against its own library of trusted
# root CAs (since 2023), so the thumbprint below is never consulted during
# token exchange. The IAM API still requires the field, so we pin GitHub's
# long-published value instead of fetching the cert chain at plan time --
# a live TLS probe would add a supply-chain dependency and plan-time drift
# for a value AWS ignores anyway.
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Name = "${var.name_prefix}-github-oidc"
  }
}

data "aws_iam_policy_document" "github_trust" {
  statement {
    sid     = "GitHubActionsAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # One rendered value per allowed ref. A broad wildcard such as
    # "repo:owner/name:*" would also match pull_request and environment
    # subjects -- forked-PR workflows could then mint deploy credentials.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        for ref in var.allowed_refs : "repo:${var.github_repository}:ref:${ref}"
      ]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.name_prefix}-deploy"
  description          = "Assumed by GitHub Actions workflows in ${var.github_repository} via OIDC. Carries no permissions of its own; callers attach resource-scoped grants to the role ARN."
  assume_role_policy   = data.aws_iam_policy_document.github_trust.json
  max_session_duration = 3600

  tags = {
    Name = "${var.name_prefix}-deploy"
  }
}
