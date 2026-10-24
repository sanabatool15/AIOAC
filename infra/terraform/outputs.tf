output "bucket" {
  value       = aws_s3_bucket.data.bucket
  description = "Set as SAGEMAKER_BUCKET."
}

output "training_role_arn" {
  value       = aws_iam_role.training.arn
  description = "Set as SAGEMAKER_ROLE_ARN."
}

output "app_policy_arn" {
  value       = aws_iam_policy.app.arn
  description = "Attach to a limited IAM user for the app."
}
