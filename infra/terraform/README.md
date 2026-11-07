# infra/terraform

Never applied by an agent. Review with `terraform plan`, apply with your own limited credentials (not root).

- Create `terraform.tfvars` (ignored by version control) with `alert_email = "you@example.com"`.
- Outputs map to `SAGEMAKER_BUCKET` and `SAGEMAKER_ROLE_ARN` in `.env`.
- Attach the `aioac-app` policy to a limited IAM user for the app.
- Not validated: terraform was not installed where this was written. Run `terraform fmt` and `terraform validate` first.

## App storage in S3 (STORAGE_BACKEND=s3)
- The app writes under `app/` (variable `app_prefix`, same as `STORAGE_S3_PREFIX`): `app/candidates/...` (temporary), `app/datasets/...` and `app/models/...` (kept).
- Lifecycle: `jobs/` expires after `jobs_expiry_days`; `app/candidates/` after `candidates_expiry_days` (1 day, S3's minimum). The old catch-all expiry rule (`other_expiry_days`, empty prefix) was removed because it would also have deleted chosen datasets and models.
- The `aioac-app` policy gained get/put/delete on `app/*` and list limited to the `app/` prefix. Nothing else.
- Not validated: terraform is not installed in the session that wrote this change. Run `terraform fmt`, `terraform validate` and `terraform plan` before applying.
