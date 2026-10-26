from ...config import settings
from .base import LLMClient, LLMError, LLMResponse, ToolCall, Usage  # noqa: F401
from .openrouter import OpenRouterClient


def get_llm(model: str | None = None) -> LLMClient:
    if settings.llm_provider == "azure":
        from .azure import AzureFoundryClient
        return AzureFoundryClient(model=model)
    return OpenRouterClient(model=model)
