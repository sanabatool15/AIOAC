variable "region" {
  type        = string
  description = "AWS region for the bucket and training jobs."
  default     = "us-east-1"
}

variable "bucket_name" {
  type        = string
  description = "Bucket name. Empty means aioac-<account id>-<region>."
  default     = ""
}

variable "alert_email" {
  type        = string
  description = "Where budget alerts go. Set in terraform.tfvars (gitignored), not in this file."
}

variable "budget_usd" {
  type        = number
  description = "Budget for alerts. The planned AWS credit is 160."
  default     = 160
}

variable "jobs_expiry_days" {
  type        = number
  description = "Days before per-job files under jobs/ are deleted."
  default     = 7
}

variable "app_prefix" {
  type        = string
  description = "Key prefix the app uses for its own files (STORAGE_S3_PREFIX). Must end with a slash."
  default     = "app/"
}

variable "candidates_expiry_days" {
  type        = number
  description = "Days before temporary dataset candidates under <app_prefix>candidates/ are deleted (S3 works in whole days)."
  default     = 1
}

variable "sagemaker_image_registry_account" {
  type        = string
  description = "AWS account that owns the scikit-learn image registry in this region (683313688378 for us-east-1 per AWS docs)."
  default     = "683313688378"
}
