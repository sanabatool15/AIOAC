"""Builds the real integration for each interface in app/ports.py, chosen by settings.

Tests and evals never edit this file's logic: they inject doubles (backend/doubles/) by patching these functions
or passing the double in directly. The app itself never imports doubles.
"""
from functools import lru_cache

from ..config import settings
from ..ports import DatasetSource, JobRunner, LLMClient, PaymentProvider, Storage, TrainingBackend
from .datasets.huggingface import HuggingFaceSource
from .datasets.openml import OpenMLSource
from .datasets.registry import SourceRegistry
from .datasets.uci import UCISource
from .jobs.inline import InlineJobRunner
from .llm.openrouter import OpenRouterClient
from .storage.local import LocalStorage
from .training_local.backend import LocalBackend


@lru_cache
def get_payment_provider() -> PaymentProvider:
    from .paypal.provider import PayPalProvider

    return PayPalProvider()


@lru_cache
def get_training_backend() -> TrainingBackend:
    if settings.training_backend == "sagemaker":
        from .aws.sagemaker import SageMakerBackend

        return SageMakerBackend()
    return LocalBackend()


def get_llm(model: str | None = None) -> LLMClient:
    if settings.llm_provider == "azure":
        from .llm.azure import AzureFoundryClient
        return AzureFoundryClient(model=model)
    return OpenRouterClient(model=model)


@lru_cache
def get_storage() -> Storage:
    return LocalStorage(settings.storage_dir)


def build_registry(hf: DatasetSource | None = None, uci: DatasetSource | None = None, oml: DatasetSource | None = None) -> SourceRegistry:
    return (SourceRegistry()
            .register("hf", hf or HuggingFaceSource(settings.hf_token), "Hugging Face", lambda i: f"https://huggingface.co/datasets/{i}")
            .register("uci", uci or UCISource(), "UCI Machine Learning Repository", lambda i: f"https://archive.ics.uci.edu/dataset/{i}")
            .register("oml", oml or OpenMLSource(), "OpenML", lambda i: f"https://www.openml.org/d/{i}"))


@lru_cache
def get_dataset_source() -> SourceRegistry:
    return build_registry()


@lru_cache
def get_job_runner() -> JobRunner:
    if settings.job_runner == "inngest":
        from .jobs.inngest_runner import InngestJobRunner  # imported here so the inline default needs no extra package

        return InngestJobRunner()
    from .jobs.worker import run_job

    return InlineJobRunner(run_job, threaded=True)
