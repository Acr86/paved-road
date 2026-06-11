# aws/cicd-identity

Keyless CI/CD identity for GitHub Actions on AWS. Creates the GitHub Actions OIDC
identity provider (`token.actions.githubusercontent.com`) and a single `deploy`
IAM role whose trust policy admits only workflow runs from one repository on an
explicit allowlist of refs. The role is created with **no permissions attached**:
it exists purely as a federated identity, and every grant is made resource-side
by the modules that own the resources. This is the AWS mirror of the GCP
`cicd-identity` module (Workload Identity Federation pool + provider + deploy
service account).

## Usage

```hcl
module "cicd_identity" {
  source = "../../modules/aws/cicd-identity"

  name_prefix       = "platform-prod"
  github_repository = "acme/platform"
  allowed_refs      = ["refs/heads/main", "refs/tags/v*"]
}

# Grants happen resource-side, never here: resource modules take the
# role ARN and attach their own scoped policy.
module "registry" {
  source = "../../modules/aws/container-registry"

  name_prefix     = "platform-prod"
  push_principals = [module.cicd_identity.deploy_role_arn]
}
```

In the workflow, exchange the runner's OIDC token for role credentials:

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::123456789012:role/platform-prod-deploy
      aws-region: eu-west-1
```

## AWS / GCP equivalence note

On GCP, Workload Identity Federation bindings (attribute conditions, allowed
audiences) live on the **pool/provider**, which is shared infrastructure; the
service account merely trusts the pool. On AWS the equivalent constraints live
in the **trust policy of each individual role**. That asymmetry is why this
module's contract takes `allowed_refs` as a variable and renders the subject
conditions itself, instead of exposing pool/provider primitives for callers to
compose: on AWS there is no shared object to hang those conditions on, so the
ref allowlist *is* the role. Callers of both modules see the same shape
(`repository in, deploy identity ARN out`) even though the enforcement point
differs per cloud.

## Opinions

- **Zero permissions on the deploy role.** The module outputs `deploy_role_arn`
  and nothing else grants anything. Resource modules (ECR repo, S3 bucket,
  ECS service) attach their own scoped policies referencing that ARN. A CI role
  with `AdministratorAccess` is the single most common OIDC misconfiguration;
  this contract makes it structurally impossible inside the module.
- **Refs are rendered one condition value per entry, never collapsed into a
  repo-wide wildcard.** `repo:owner/name:*` also matches `pull_request` and
  `environment` subjects, which would let a forked PR mint deploy credentials.
  The variable validation additionally rejects anything not under `refs/heads/`
  or `refs/tags/`.
- **The thumbprint is pinned, not fetched.** AWS validates the GitHub issuer
  against its own trusted CA library and ignores the thumbprint at exchange
  time, but the IAM API still requires the field. Pinning GitHub's published
  value avoids a plan-time TLS probe (supply-chain surface, drift) for a value
  that has no security effect.
- **Session duration is capped at one hour.** Deploy jobs that need longer than
  the IAM minimum are a smell; long-lived CI credentials defeat the point of
  going keyless.
- **One provider per account.** AWS allows exactly one OIDC provider per issuer
  URL per account; this module assumes ownership of it. If the account already
  has one, `terraform import` it into this module rather than instantiating the
  module twice in the same account.
