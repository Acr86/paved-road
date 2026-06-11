resource "aws_ecr_repository" "this" {
  # checkov:skip=CKV_AWS_51:Tag mutability is the promotion mechanism (ADR-0005): main is a moving pointer the release pipeline re-targets at an already-scanned digest. Provenance is cosign signatures over digests, not tag immutability.
  name                 = var.name
  image_tag_mutability = var.image_tag_mutability
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = var.kms_key_arn != null ? "KMS" : "AES256"
    kms_key         = var.kms_key_arn
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  # ECR treats multiple entries in a single tagPrefixList as AND (an image must
  # carry ALL listed prefixes to match), which would make ["main", "pr-"] match
  # nothing. One rule per prefix gives the intended OR semantics and keeps the
  # retention count independent per prefix, so PR builds can never evict
  # trunk builds.
  policy = jsonencode({
    rules = concat(
      [
        {
          rulePriority = 1
          description  = "Expire untagged images after ${var.untagged_retention_days} days"
          selection = {
            tagStatus   = "untagged"
            countType   = "sinceImagePushed"
            countUnit   = "days"
            countNumber = var.untagged_retention_days
          }
          action = {
            type = "expire"
          }
        }
      ],
      [
        for idx, prefix in var.tag_prefixes : {
          rulePriority = idx + 2
          description  = "Keep only the last ${var.keep_tagged_count} images tagged ${prefix}*"
          selection = {
            tagStatus     = "tagged"
            tagPrefixList = [prefix]
            countType     = "imageCountMoreThan"
            countNumber   = var.keep_tagged_count
          }
          action = {
            type = "expire"
          }
        }
      ]
    )
  })
}
