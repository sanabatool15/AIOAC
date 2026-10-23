import json

import httpx

from ...config import settings
from .base import LLMResponse, ToolCall

URL = "https://openrouter.ai/api/v1/chat/completions"  # OpenAI-compatible; not exercised by tests (no network)


class OpenRouterClient:
    def chat(self, messages, tools):
        body = {"model": settings.openrouter_model, "messages": messages}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        r = httpx.post(URL, json=body, timeout=60,
                       headers={"Authorization": f"Bearer {settings.openrouter_api_key}"})
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        calls = [ToolCall(c["id"], c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"))
                 for c in msg.get("tool_calls") or []]
        return LLMResponse(text=msg.get("content"), tool_calls=calls)
