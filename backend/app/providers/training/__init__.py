from ...config import settings
from .local import LocalBaselineBackend


def get_training_backend():
    if settings.training_backend == "sagemaker":
        from .sagemaker import SageMakerBackend

        return SageMakerBackend()
    return LocalBaselineBackend()
