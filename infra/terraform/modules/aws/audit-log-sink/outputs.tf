output "bucket_arn" {
  description = "ARN of the WORM audit archive bucket."
  value       = aws_s3_bucket.audit.arn
}

output "bucket_id" {
  description = "Name (id) of the WORM audit archive bucket."
  value       = aws_s3_bucket.audit.id
}

output "log_group_name" {
  description = "Name of the CloudWatch log group applications write audit events to."
  value       = aws_cloudwatch_log_group.audit.name
}

output "firehose_arn" {
  description = "ARN of the Firehose delivery stream that drains the log group into the archive bucket."
  value       = aws_kinesis_firehose_delivery_stream.audit.arn
}

output "kms_key_arn" {
  description = "ARN of the CMK encrypting the audit trail (provided or module-created). Other log groups in the environment reuse it (its policy already grants the CloudWatch Logs principal)."
  value       = local.kms_key_arn
}
