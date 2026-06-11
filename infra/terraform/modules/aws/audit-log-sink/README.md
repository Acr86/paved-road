# aws/audit-log-sink

Tamper-evident audit log pipeline: applications write audit events to a CloudWatch log
group (the hot, searchable tier), a subscription filter drains every event through a
Kinesis Data Firehose stream, and Firehose lands compressed batches in an S3 bucket
locked down as a WORM archive — Object Lock with a multi-year default retention,
versioning, full public access block, TLS-only bucket policy, and a lifecycle policy
that tiers to Glacier but never expires. This is the AWS mirror of the GCP
`audit-log-sink` module; see Opinions for where the two clouds genuinely differ.

## Usage

```hcl
module "audit_log_sink" {
  source = "../../modules/aws/audit-log-sink"

  name_prefix        = "platform-prod"
  log_group_name     = "/platform/audit"
  log_retention_days = 365

  retention_years    = 7
  worm_mode          = "GOVERNANCE"
  glacier_after_days = 90

  kms_key_arn = aws_kms_key.audit.arn
}
```

## Opinions

- **WORM by default.** The bucket is created with Object Lock enabled (which cannot be
  retrofitted) and every object inherits a 7-year default retention. On GCP the same
  role is played by a BigQuery append-only dataset plus IAM that grants nobody delete —
  an equivalent *posture*, but the genuine delta is enforcement depth: S3 Object Lock is
  enforced by the storage layer itself, while BigQuery append-only is an IAM convention
  a project owner can revert. The AWS mirror is strictly stronger at the storage layer.
- **GOVERNANCE, not COMPLIANCE, as the default mode.** COMPLIANCE retention cannot be
  shortened by anyone — including root — until it expires, which turns every test apply
  into a 7-year liability. GOVERNANCE keeps the same default-deny behavior but leaves a
  break-glass path gated on `s3:BypassGovernanceRetention`. Regulated workloads flip
  `worm_mode = "COMPLIANCE"` consciously, not accidentally.
- **Deny non-TLS, period.** The bucket policy denies all S3 actions when
  `aws:SecureTransport` is false, for every principal, regardless of IAM allows.
- **Lifecycle tiers, never expires.** Compliance storage is measured in years, hot
  storage pricing in months: objects (current and noncurrent versions) move to Glacier
  after 90 days, but there is no expiration action — deletion is governed exclusively
  by Object Lock retention, not by a lifecycle rule someone tuned for cost.
- **CloudWatch is the search tier, not the archive.** The log group retention is capped
  (and `0` / never-expire is deliberately rejected) because long-term custody belongs to
  the WORM bucket, not to a log group with mutable retention settings.
- **Encryption is not optional, KMS is.** With `kms_key_arn` set, the bucket, the
  Firehose stream, and the log group use the customer-managed key (with `kms:ViaService`
  scoping on the Firehose grant); without it, the bucket still enforces SSE-S3 AES256 —
  there is no unencrypted configuration of this module.
- **Small Firehose buffers.** 60 seconds / 5 MB, near the service floor: audit events
  are evidence and should spend as little time as possible existing only inside the
  delivery stream.
- **One role per hop, scoped trust.** `logs -> firehose` and `firehose -> s3` each get a
  dedicated IAM role whose policy names exact resources, and whose trust policy carries
  a confused-deputy guard (`aws:SourceArn` on the log group, `sts:ExternalId` pinned to
  the account for Firehose).
- **Unfiltered subscription.** The subscription filter pattern is empty on purpose: an
  audit sink that filters at ingest is not an audit sink.
