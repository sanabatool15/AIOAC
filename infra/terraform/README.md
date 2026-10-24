# infra/terraform

Never applied by an agent. Review with `terraform plan`, apply with your own limited credentials (not root).

- Create `terraform.tfvars` (ignored by version control) with `alert_email = "you@example.com"`.
- Outputs map to `SAGEMAKER_BUCKET` and `SAGEMAKER_ROLE_ARN` in `.env`.
- Attach the `aioac-app` policy to a limited IAM user for the app.
- Not validated: terraform was not installed where this was written. Run `terraform fmt` and `terraform validate` first.
