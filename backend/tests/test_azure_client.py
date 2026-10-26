import httpx
import pytest

from app.providers.llm import get_llm
from app.providers.llm.azure import AzureFoundryClient, chat_url
from app.providers.llm.base import LLMError
from app.providers.llm.openrouter import OpenRouterClient

BASE = "https://res.openai.azure.com/openai/v1/"
TOOLS = [{"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}]


def client(handler, **kw):
    return AzureFoundryClient(model="my-deployment", api_key="az-fake", base_url=BASE,
                              http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None, **kw)


def test_request_shape_and_header():
    seen = {}

    def handler(req):
        seen["url"], seen["key"], seen["auth"] = str(req.url), req.headers.get("api-key"), req.headers.get("authorization")
        seen["body"] = req.read()
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 3, "completion_tokens": 2}})

    r = client(handler).chat([{"role": "user", "content": "x"}], TOOLS)
    assert seen["url"] == "https://res.openai.azure.com/openai/v1/chat/completions"
    assert seen["key"] == "az-fake" and seen["auth"] is None
    assert b'"model":"my-deployment"' in seen["body"].replace(b" ", b"")
    assert r.text == "hi" and r.usage.total_tokens == 5 and r.usage.cost_usd is None


def test_tool_call_parsed():
    def handler(req):
        call = {"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{\"a\": 1}"}}
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [call]}, "finish_reason": "tool_calls"}]})

    r = client(handler).chat([], TOOLS)
    assert r.tool_calls[0].name == "t" and r.tool_calls[0].args == {"a": 1}


def test_auth_error_is_plain_and_not_retried():
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(LLMError):
        client(handler).chat([], TOOLS)
    assert len(n) == 1


def test_rate_limit_retried_once():
    n = []

    def handler(req):
        n.append(1)
        if len(n) == 1:
            return httpx.Response(429, json={"error": {"message": "slow"}})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})

    assert client(handler).chat([], TOOLS).text == "ok" and len(n) == 2


@pytest.mark.parametrize("bad", ["http://res.openai.azure.com/openai/v1/", "https://evil.example.com/openai/v1/",
                                 "https://res.openai.azure.com.evil.com/openai/v1/", ""])
def test_refuses_non_azure_hosts(bad):
    with pytest.raises(LLMError):
        chat_url(bad)


def test_foundry_host_allowed():
    assert chat_url("https://res.services.ai.azure.com/openai/v1").endswith("/openai/v1/chat/completions")


def test_missing_key_or_model(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "azure_openai_api_key", "")
    with pytest.raises(LLMError):
        AzureFoundryClient(model="m", base_url=BASE).chat([], TOOLS)
    with pytest.raises(LLMError):
        AzureFoundryClient(model="", api_key="k", base_url=BASE).chat([], TOOLS)


def test_get_llm_switches_on_setting(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_provider", "azure")
    assert isinstance(get_llm(), AzureFoundryClient)
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    c = get_llm()
    assert isinstance(c, OpenRouterClient) and not isinstance(c, AzureFoundryClient)
