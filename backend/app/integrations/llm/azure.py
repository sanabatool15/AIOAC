"""Azure AI Foundry / Azure OpenAI chat completions client (OpenAI-compatible v1 API).

Checked against Microsoft Learn ("Azure OpenAI in Microsoft Foundry Models v1 API", updated 2026-06):
- POST <base>/chat/completions where <base> is https://RESOURCE.openai.azure.com/openai/v1/ or
  https://RESOURCE.services.ai.azure.com/openai/v1/. No api-version parameter.
- `model` is the DEPLOYMENT name. Key auth uses the `api-key` header.
- Models from other providers (Grok, DeepSeek, GLM, ...) use the same chat completions shape when the deployment supports it.
- The reply shape is the OpenAI one, so parsing is shared with the OpenRouter client. Azure sends no `usage.cost`,
  so only the token limits apply (the model cost ceiling is not enforced).
"""
from urllib.parse import urlparse

import httpx

from ...config import settings
from ...ports import LLMError
from .openrouter import OpenRouterClient

ALLOWED_HOST_SUFFIXES = (".openai.azure.com", ".services.ai.azure.com")


def chat_url(base_url: str) -> str:
    """Build the chat completions URL. Refuses any host that is not an Azure AI host, so the key cannot go elsewhere."""
    parsed = urlparse(base_url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host.endswith(ALLOWED_HOST_SUFFIXES):
        raise LLMError("AZURE_OPENAI_BASE_URL must be an https address like "
                       "https://YOUR-RESOURCE.openai.azure.com/openai/v1/")
    return base_url.strip().rstrip("/") + "/chat/completions"


class AzureFoundryClient(OpenRouterClient):
    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None,
                 http: httpx.Client | None = None, timeout: float = 60.0, sleep=None):
        kw = {"sleep": sleep} if sleep is not None else {}
        super().__init__(model=model or settings.azure_openai_model, api_key=api_key, http=http, timeout=timeout, **kw)
        self.base_url = base_url

    def _post(self, body: dict) -> httpx.Response:
        key = self.api_key if self.api_key is not None else settings.azure_openai_api_key
        if not key:
            raise LLMError("No AI service key is set (AZURE_OPENAI_API_KEY).")
        if not self.model:
            raise LLMError("No model deployment name is set (AZURE_OPENAI_MODEL).")
        url = chat_url(self.base_url if self.base_url is not None else settings.azure_openai_base_url)
        headers = {"api-key": key}
        if self.http is not None:
            return self.http.post(url, json=body, headers=headers, timeout=self.timeout)
        return httpx.post(url, json=body, headers=headers, timeout=self.timeout)
