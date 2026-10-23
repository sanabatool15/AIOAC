from .base import LLMClient, LLMResponse, ToolCall  # noqa: F401
from .openrouter import OpenRouterClient


def get_llm() -> LLMClient:
    return OpenRouterClient()
