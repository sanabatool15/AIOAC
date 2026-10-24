# AIOAC long-lived AWS pieces (specs/training.md section 3). NEVER applied by an agent: a human reviews
# `terraform plan` and runs apply with their own limited credentials (not the root account).
# Training jobs themselves are started by the app at runtime, not defined here.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

locals {
  bucket_name = var.bucket_name != "" ? var.bucket_name : "aioac-${data.aws_caller_identity.current.account_id}-${var.region}"
}

# ---- Bucket: private, encrypted, with expiry so forgotten files cannot pile up ----
resource "aws_s3_bucket" "data" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  # Per-job inputs, packaged scripts and outputs live under jobs/ and expire.
  rule {
    id     = "expire-jobs"
    status = "Enabled"
    filter {
      prefix = "jobs/"
    }
    expiration {
      days = var.jobs_expiry_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  # Any other prefix (for example the chosen dataset) is kept longer, still not forever.
  rule {
    id     = "expire-everything-else"
    status = "Enabled"
    filter {
      prefix = ""
    }
    expiration {
      days = var.other_expiry_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

# ---- Role that SageMaker assumes while a training job runs ----
data "aws_iam_policy_document" "training_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
    # Confused-deputy protection: only jobs in this account.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "training" {
  name               = "aioac-sagemaker-training"
  assume_role_policy = data.aws_iam_policy_document.training_trust.json
}

data "aws_iam_policy_document" "training_access" {
  statement {
    sid       = "ReadWriteJobFiles"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/jobs/*"]
  }
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/sagemaker/TrainingJobs*"]
  }
  # AWS-owned scikit-learn image lives in an AWS account's ECR; pulling needs these.
  statement {
    sid       = "PullAwsImage"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid       = "PullAwsImageLayers"
    actions   = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
    resources = ["arn:aws:ecr:${var.region}:${var.sagemaker_image_registry_account}:repository/sagemaker-scikit-learn"]
  }
}

resource "aws_iam_role_policy" "training" {
  name   = "aioac-training-access"
  role   = aws_iam_role.training.id
  policy = data.aws_iam_policy_document.training_access.json
}

# ---- Least-privilege policy for the app user (attach to a limited IAM user you create yourself) ----
data "aws_iam_policy_document" "app" {
  statement {
    sid       = "JobFiles"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/jobs/*"]
  }
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    sid       = "TrainingJobs"
    actions   = ["sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob", "sagemaker:StopTrainingJob"]
    resources = ["arn:aws:sagemaker:${var.region}:${data.aws_caller_identity.current.account_id}:training-job/aioac-*"]
  }
  statement {
    sid       = "PassOnlyTrainingRole"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.training.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "app" {
  name   = "aioac-app"
  policy = data.aws_iam_policy_document.app.json
}

# ---- Budget alert: warns well before the credit is gone ----
resource "aws_budgets_budget" "monthly" {
  name         = "aioac-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 75
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}
