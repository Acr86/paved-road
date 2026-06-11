# aws/registry

Opinionated ECR repository for platform container images. It is the AWS mirror of the `gcp/registry` module: same tagging convention, same retention stance, same security posture, expressed in ECR primitives instead of Artifact Registry ones. Every repository scans images on push, encrypts at rest (AES-256 by default, customer-managed KMS when a key is supplied), and carries a lifecycle policy so storage cost stays bounded without anyone ever "cleaning up the registry" by hand.

## Usage

```hcl
module "orders_api_images" {
  source = "../../modules/aws/registry"

  name = "platform/orders-api"

  # Retention tuned for a busy service: deeper rollback window on trunk builds.
  keep_tagged_count       = 30
  untagged_retention_days = 7
  tag_prefixes            = ["main", "pr-"]

  # Encrypt with the platform CMK instead of the ECR default key.
  kms_key_arn = module.platform_kms.key_arn
}

output "orders_api_image_repo" {
  value = module.orders_api_images.repository_url
}
```

## Opinions

- **Scan on push is not optional.** `image_scanning_configuration.scan_on_push` is hardcoded to `true` with no variable to turn it off. A registry that accepts unscanned images is a supply-chain blind spot, and "we'll enable scanning later" never happens.
- **The lifecycle policy is the same FinOps stance as the GCP twin.** Mirrors `gcp/registry` rule for rule: untagged images are garbage after `untagged_retention_days` (default 7) days, and only the last `keep_tagged_count` (default 20) images per tag prefix survive. A registry without retention rules grows monotonically and someone eventually pays for terabytes of images nothing can pull anymore.
- **One lifecycle rule per tag prefix, not one rule with a prefix list.** ECR evaluates multiple entries in a single `tagPrefixList` as AND, so `["main", "pr-"]` in one rule would match nothing. Generating a rule per prefix restores the intended OR semantics and makes retention independent per prefix: a burst of PR builds can never evict trunk images you may need to roll back to.
- **MUTABLE tags by default, because deploys promote by digest.** The moving `main` tag is a human convenience pointer; the immutable identity of what runs in production is the image digest, which the deploy pipeline pins. Teams whose pipelines deploy by tag should set `image_tag_mutability = "IMMUTABLE"` instead — the module supports both, but the default encodes the digest-promotion workflow.
- **`force_delete` defaults to false.** `terraform destroy` on a repository that still holds images should fail loudly, not quietly erase deployment history. Opting into force deletion is a deliberate per-call decision, never the baseline.
- **Encryption is always on; the only choice is whose key.** `kms_key_arn` set means customer-managed KMS; unset means ECR's AES-256 default. There is no plaintext option to misconfigure.
