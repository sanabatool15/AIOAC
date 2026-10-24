"""OpenRouter chat completions client (OpenAI-compatible).

Checked against the OpenRouter docs on 2026-10-24:
- POST https://openrouter.ai/api/v1/chat/completions, Bearer auth.
- tool_calls[].function.arguments is a JSON-encoded STRING and must be parsed by us. Several calls can arrive in one reply.
- Send `tools` on every request, including the follow-up that carries tool results.
- Errors: body {"error": {"code", "message", "metadata"}}. 402 = no credits, 408 timeout, 429 rate limit,
  502 model down or bad reply, 503 no provider. 429/503 may carry Retry-After (seconds).
  Errors during generation can come back with HTTP 200 and an `error` field in the body.
- usage: prompt_tokens, completion_tokens, total_tokens, and `cost` (nullable).
"""
import json
import time
import uuid

import httpx

from ...config import settings
from .base import LLMError, LLMResponse, ToolCall, Usage

URL = "https://openrouter.ai/api/v1/chat/completions"
RETRY_STATUS = {408, 429, 500, 502, 503, 504, 524, 529}
MAX_RETRY_WAIT = 10.0

_PLAIN = {
    400: "The AI service rejected the request.",
    401: "The AI service key was not accepted. Check OPENROUTER_API_KEY.",
    402: "The AI service account is out of credits.",
    403: "The AI service refused this request.",
    408: "The AI service took too long to answer.",
    429: "The AI service is busy right now (rate limit).",
    502: "The AI model is not answering properly right now.",
    503: "No AI model is available right now.",
}


def _error_message(status: int, body) -> str:
    detail = ""
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        detail = str(body["error"].get("message") or "")
    base = _PLAIN.get(status, f"The AI service had a problem (code {status}).")
    return f"{base} {detail[:200]}".strip()


def _text(content) -> str | None:
    """Content can be None, a string, or a list of parts."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type", "text") == "text"]
        return "".join(parts) or None
    return str(content)


def _parse_call(raw: dict) -> ToolCall:
    fn = raw.get("function")
    if not isinstance(fn, dict) or not isinstance(fn.get("name"), str) or not fn["name"]:
        return ToolCall(f"call_{uuid.uuid4().hex[:12]}", "", {}, error="the tool call had no name")
    cid = raw["id"] if isinstance(raw.get("id"), str) and raw["id"] else f"call_{uuid.uuid4().hex[:12]}"
    args = fn.get("arguments")
    if args is None or args == "":
        return ToolCall(cid, fn["name"], {})
    if isinstance(args, dict):  # some providers send an object instead of a string
        return ToolCall(cid, fn["name"], args)
    try:
        parsed = json.loads(args)
    except (TypeError, ValueError):
        return ToolCall(cid, fn["name"], {}, error="the arguments were not valid JSON")
    if not isinstance(parsed, dict):
        return ToolCall(cid, fn["name"], {}, error="the arguments must be a JSON object")
    return ToolCall(cid, fn["name"], parsed)


def _usage(raw) -> Usage | None:
    if not isinstance(raw, dict):
        return None
    cost = raw.get("cost")
    return Usage(int(raw.get("prompt_tokens") or 0), int(raw.get("completion_tokens") or 0),
                 float(cost) if isinstance(cost, (int, float)) else None)


def parse_completion(data) -> LLMResponse:
    if not isinstance(data, dict):
        raise LLMError("The AI service sent a reply I could not read.", retryable=True)
    if isinstance(data.get("error"), dict):  # error during generation, HTTP 200
        code = data["error"].get("code")
        status = code if isinstance(code, int) else 502
        raise LLMError(_error_message(status, data), retryable=status in RETRY_STATUS)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise LLMError("The AI service sent an empty reply.", retryable=True)
    ch = choices[0]
    if isinstance(ch.get("error"), dict):
        raise LLMError(_error_message(502, ch), retryable=True)
    msg = ch.get("message") or {}
    calls = [_parse_call(c) for c in (msg.get("tool_calls") or []) if isinstance(c, dict)]
    return LLMResponse(text=_text(msg.get("content")), tool_calls=calls, usage=_usage(data.get("usage")),
                       finish_reason=ch.get("finish_reason"))


def _retry_after(r: httpx.Response) -> float | None:
    try:
        return float(r.headers.get("Retry-After", ""))
    except ValueError:
        return None


class OpenRouterClient:
    def __init__(self, model: str | None = None, api_key: str | None = None, http: httpx.Client | None = None,
                 timeout: float = 60.0, sleep=time.sleep):
        self.model = model
        self.api_key = api_key
        self.http = http
        self.timeout = timeout
        self.sleep = sleep

    def _post(self, body: dict) -> httpx.Response:
        key = self.api_key if self.api_key is not None else settings.openrouter_api_key
        if not key:
            raise LLMError("No AI service key is set (OPENROUTER_API_KEY).")
        headers = {"Authorization": f"Bearer {key}"}
        if self.http is not None:
            return self.http.post(URL, json=body, headers=headers, timeout=self.timeout)
        return httpx.post(URL, json=body, headers=headers, timeout=self.timeout)

    def _once(self, body: dict) -> LLMResponse:
        try:
            r = self._post(body)
        except (httpx.TimeoutException, httpx.TransportError):
            raise LLMError("I could not reach the AI service (timeout or network problem).", retryable=True)
        try:
            data = r.json()
        except ValueError:
            data = None
        if r.status_code >= 400:
            raise LLMError(_error_message(r.status_code, data), retryable=r.status_code in RETRY_STATUS,
                           retry_after=_retry_after(r))
        return parse_completion(data)

    def chat(self, messages, tools):
        body = {"model": self.model or settings.openrouter_model, "messages": messages}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        try:
            return self._once(body)
        except LLMError as first:
            if not first.retryable:
                raise
            self.sleep(min(first.retry_after or 1.0, MAX_RETRY_WAIT))
            return self._once(body)  # one retry only; a second failure goes to the caller
