class SageMakerBackend:
    """Paid CPU job on AWS SageMaker.

    TODO: start the job, poll accumulated cost on a timer, stop at cap_cents, return TrainingResult.
    Needs AWS credentials and the Terraform-created bucket and roles (specs/training.md).
    """

    name = "sagemaker"
    instance_type = "ml.m5.xlarge"

    def run(self, dataset_path, target, cap_cents):
        raise NotImplementedError
