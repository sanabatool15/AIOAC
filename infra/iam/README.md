# Limiting the training role (not applied yet)

`aioac-sagemaker-role` was created by hand with two broad AWS policies: `AmazonS3FullAccess` (every bucket in the
account) and `AmazonSageMakerFullAccess`. `aioac-sagemaker-role-policy.json` is the same least-privilege policy that
`infra/terraform/main.tf` defines for `aioac-sagemaker-training` (project bucket `jobs/*` only, training-job log
group only, the scikit-learn image in the AWS registry), with the real account, region and bucket filled in.

Apply in this order, so training never loses access in between. Needs an IAM user that may change roles (not the
app user `aioac-dev`, whose permissions are limited to what the app needs).

1. Add the limited policy:
   `aws iam put-role-policy --role-name aioac-sagemaker-role --policy-name aioac-training-access --policy-document file://infra/iam/aioac-sagemaker-role-policy.json`
2. Remove the broad ones (only now is the limit real):
   `aws iam detach-role-policy --role-name aioac-sagemaker-role --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess`
   `aws iam detach-role-policy --role-name aioac-sagemaker-role --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess`
3. Run the capped job (about 1 cent): `RUN_REAL=1 RUN_PAID=1 pytest tests/integration/test_sagemaker_training.py -v -s`.
   If it fails with an access error, read the message, add only the missing action to the JSON, and repeat step 1.
4. Remove the `xfail` marker from `test_training_role_is_limited_to_the_project_bucket` in
   `backend/tests/integration/test_aws_setup.py` (it is `strict`, so it will tell you when the roles are limited).
