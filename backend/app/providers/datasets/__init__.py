from functools import lru_cache

from ...config import settings
from .base import DatasetSource, SourceError  # noqa: F401
from .huggingface import HuggingFaceSource
from .openml import OpenMLSource
from .registry import SourceRegistry
from .uci import UCISource


def build_registry(hf: DatasetSource | None = None, uci: DatasetSource | None = None, oml: DatasetSource | None = None) -> SourceRegistry:
    return (SourceRegistry()
            .register("hf", hf or HuggingFaceSource(settings.hf_token), "Hugging Face", lambda i: f"https://huggingface.co/datasets/{i}")
            .register("uci", uci or UCISource(), "UCI Machine Learning Repository", lambda i: f"https://archive.ics.uci.edu/dataset/{i}")
            .register("oml", oml or OpenMLSource(), "OpenML", lambda i: f"https://www.openml.org/d/{i}"))


@lru_cache
def get_dataset_source() -> SourceRegistry:
    return build_registry()
