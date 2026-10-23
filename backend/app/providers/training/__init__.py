from functools import lru_cache

from ...config import settings
from .local import LocalBackend


@lru_cache
def get_training_backend():
    if settings.training_backend == "sagemaker":
        from .sagemaker import SageMakerBackend

        return SageMakerBackend()
    return LocalBackend()
