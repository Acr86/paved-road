data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  bucket_name = "${var.name_prefix}-audit-archive"
  create_kms  = var.kms_key_arn == null
  # Audit data is always CMK-encrypted: callers either bring a key or this
  # module creates a rotated one. There is no AES256 fallback for evidence.
  kms_key_arn = local.create_kms ? aws_kms_key.audit[0].arn : var.kms_key_arn
}

# --- Encryption key ------------------------------------------------------------

data "aws_iam_policy_document" "kms_key" {
  # checkov:skip=CKV_AWS_109:KMS key policy — Resource "*" means "this key" in a key policy; the account-root statement is the canonical guard against an unmanageable key.
  # checkov:skip=CKV_AWS_111:Same key-policy semantics as above; the service principals are constrained by EncryptionContext/SourceAccount conditions.
  # checkov:skip=CKV_AWS_356:Key policies cannot reference the key ARN they are creating; "*" is self-referential here, not account-wide.
  statement {
    sid       = "AccountRootAdministration"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid    = "CloudWatchLogsEncryption"
    effect = "Allow"
    actions = [
      "kms:Encrypt*",
      "kms:Decrypt*",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
    ]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["logs.${data.aws_region.current.region}.amazonaws.com"]
    }

    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:*"]
    }
  }

  statement {
    sid    = "FirehoseStreamEncryption"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_kms_key" "audit" {
  count = local.create_kms ? 1 : 0

  description             = "${var.name_prefix} audit log encryption (CloudWatch + S3 archive)"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.kms_key.json
}

resource "aws_kms_alias" "audit" {
  count = local.create_kms ? 1 : 0

  name          = "alias/${var.name_prefix}-audit"
  target_key_id = aws_kms_key.audit[0].key_id
}

# --- WORM archive bucket -----------------------------------------------------

resource "aws_s3_bucket" "audit" {
  # checkov:skip=CKV_AWS_144:Cross-region replication is a deliberate scope boundary for this reference (ADR-0013 records the production answer: replicate the archive to a second region with its own Object Lock).
  # checkov:skip=CKV_AWS_18:Object-level access auditing for this bucket belongs to CloudTrail data events (ADR-0013); S3 server access logs would require a second log bucket whose own logging recurses.
  bucket = local.bucket_name

  # Object Lock can only be enabled at bucket creation; it cannot be retrofitted.
  object_lock_enabled = true
}

# EventBridge gets every object-level event: downstream consumers (alerting on
# unexpected deletes, ingest bookkeeping) subscribe there instead of each
# carving private bucket notifications.
resource "aws_s3_bucket_notification" "audit" {
  bucket      = aws_s3_bucket.audit.id
  eventbridge = true
}

# Object Lock requires versioning. AWS enables it implicitly when the bucket is
# created with object_lock_enabled, but the explicit resource keeps the state
# honest and gives the lock/lifecycle resources a dependency anchor.
resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id

  rule {
    default_retention {
      mode  = var.worm_mode
      years = var.retention_years
    }
  }

  depends_on = [aws_s3_bucket_versioning.audit]
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket = aws_s3_bucket.audit.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = local.kms_key_arn
    }

    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id

  # Tiers only, never expires: deletion is governed by Object Lock retention,
  # not by lifecycle rules.
  rule {
    id     = "tier-to-glacier"
    status = "Enabled"

    filter {}

    transition {
      days          = var.glacier_after_days
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = var.glacier_after_days
      storage_class   = "GLACIER"
    }
  }

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.audit]
}

data "aws_iam_policy_document" "bucket_policy" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.audit.arn,
      "${aws_s3_bucket.audit.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "audit" {
  bucket = aws_s3_bucket.audit.id
  policy = data.aws_iam_policy_document.bucket_policy.json

  depends_on = [aws_s3_bucket_public_access_block.audit]
}

# --- Hot tier: CloudWatch log group ------------------------------------------

resource "aws_cloudwatch_log_group" "audit" {
  name              = var.log_group_name
  retention_in_days = var.log_retention_days

  # The key policy grants logs.<region>.amazonaws.com usage explicitly.
  kms_key_id = local.kms_key_arn
}

# --- Delivery: Firehose to the archive bucket --------------------------------

data "aws_iam_policy_document" "firehose_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }

    # Firehose's documented confused-deputy guard: ExternalId is the account id.
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "firehose_to_s3" {
  name               = "${var.name_prefix}-firehose-to-s3"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume.json
}

data "aws_iam_policy_document" "firehose_to_s3" {
  statement {
    sid    = "WriteAuditArchive"
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:PutObject",
    ]
    resources = [
      aws_s3_bucket.audit.arn,
      "${aws_s3_bucket.audit.arn}/*",
    ]
  }

  statement {
    sid    = "EncryptArchiveWithCmk"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
    ]
    resources = [local.kms_key_arn]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["s3.${data.aws_region.current.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "firehose_to_s3" {
  name   = "write-audit-archive"
  role   = aws_iam_role.firehose_to_s3.id
  policy = data.aws_iam_policy_document.firehose_to_s3.json
}

resource "aws_kinesis_firehose_delivery_stream" "audit" {
  name        = "${var.name_prefix}-audit-ingest"
  destination = "extended_s3"

  server_side_encryption {
    enabled  = true
    key_type = "CUSTOMER_MANAGED_CMK"
    key_arn  = local.kms_key_arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_to_s3.arn
    bucket_arn = aws_s3_bucket.audit.arn

    # Near the service floor on purpose: audit events are evidence and should
    # spend as little time as possible existing only inside the stream.
    buffering_size     = 5
    buffering_interval = 60

    compression_format  = "GZIP"
    prefix              = "cloudwatch/!{timestamp:yyyy/MM/dd}/"
    error_output_prefix = "firehose-errors/!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd}/"
  }

  depends_on = [aws_iam_role_policy.firehose_to_s3]
}

# --- Wiring: log group subscription into Firehose -----------------------------

data "aws_iam_policy_document" "logs_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["logs.${data.aws_region.current.region}.amazonaws.com"]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values = [
        aws_cloudwatch_log_group.audit.arn,
        "${aws_cloudwatch_log_group.audit.arn}:*",
      ]
    }
  }
}

resource "aws_iam_role" "logs_to_firehose" {
  name               = "${var.name_prefix}-logs-to-firehose"
  assume_role_policy = data.aws_iam_policy_document.logs_assume.json
}

data "aws_iam_policy_document" "logs_to_firehose" {
  statement {
    sid    = "PutToFirehose"
    effect = "Allow"
    actions = [
      "firehose:PutRecord",
      "firehose:PutRecordBatch",
    ]
    resources = [aws_kinesis_firehose_delivery_stream.audit.arn]
  }
}

resource "aws_iam_role_policy" "logs_to_firehose" {
  name   = "put-to-firehose"
  role   = aws_iam_role.logs_to_firehose.id
  policy = data.aws_iam_policy_document.logs_to_firehose.json
}

resource "aws_cloudwatch_log_subscription_filter" "audit" {
  name            = "${var.name_prefix}-audit-to-archive"
  log_group_name  = aws_cloudwatch_log_group.audit.name
  destination_arn = aws_kinesis_firehose_delivery_stream.audit.arn
  role_arn        = aws_iam_role.logs_to_firehose.arn

  # Empty pattern matches everything: an audit sink that filters at ingest is
  # not an audit sink.
  filter_pattern = ""

  depends_on = [aws_iam_role_policy.logs_to_firehose]
}
