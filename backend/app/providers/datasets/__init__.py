from functools import lru_cache

from ...config import settings
from .base import DatasetSource, SourceError  # noqa: F401
from .huggingface import HuggingFaceSource


@lru_cache
def get_dataset_source() -> DatasetSource:
    return HuggingFaceSource(settings.hf_token)
