from .base import LLMClient, LLMError, LLMResponse, ToolCall, Usage  # noqa: F401
from .openrouter import OpenRouterClient


def get_llm() -> LLMClient:
    return OpenRouterClient()
