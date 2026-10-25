from functools import lru_cache

from ...config import settings
from .base import DatasetSource, SourceError  # noqa: F401
from .huggingface import HuggingFaceSource
from .registry import SourceRegistry


def build_registry(hf: DatasetSource | None = None) -> SourceRegistry:
    return SourceRegistry().register("hf", hf or HuggingFaceSource(settings.hf_token), "Hugging Face",
                                     lambda i: f"https://huggingface.co/datasets/{i}")


@lru_cache
def get_dataset_source() -> SourceRegistry:
    return build_registry()
