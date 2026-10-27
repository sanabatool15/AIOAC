import json

import httpx
import pytest

from app.ports import LLMError
from app.integrations.llm.openrouter import OpenRouterClient

TOOLS = [{"name": "search_datasets", "description": "d", "parameters": {"type": "object", "properties": {}}}]


def client(handler, **kw):
    sleeps = []
    c = OpenRouterClient(model="test/model", api_key="sk-fake", http=httpx.Client(transport=httpx.MockTransport(handler)),
                         sleep=sleeps.append, **kw)
    c.sleeps = sleeps
    return c


def ok(message, usage=None, finish="stop"):
    body = {"choices": [{"message": message, "finish_reason": finish}]}
    if usage:
        body["usage"] = usage
    return httpx.Response(200, json=body)


def call(id, name, args):
    return {"id": id, "type": "function", "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)}}


def test_request_shape_and_text_reply():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers["authorization"]
        return ok({"role": "assistant", "content": "hello"}, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.0012})

    r = client(h).chat([{"role": "user", "content": "hi"}], TOOLS)
    assert seen["body"]["model"] == "test/model" and seen["auth"] == "Bearer sk-fake"
    assert seen["body"]["tools"] == [{"type": "function", "function": TOOLS[0]}]
    assert r.text == "hello" and r.usage.total_tokens == 15 and r.usage.cost_usd == 0.0012


def test_model_id_comes_from_settings_by_default(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_model", "from/settings")
    seen = {}

    def h(req):
        seen["m"] = json.loads(req.content)["model"]
        return ok({"content": "x"})

    OpenRouterClient(api_key="k", http=httpx.Client(transport=httpx.MockTransport(h))).chat([], [])
    assert seen["m"] == "from/settings"


def test_no_tools_key_when_no_tools():
    seen = {}

    def h(req):
        seen["body"] = json.loads(req.content)
        return ok({"content": "x"})

    client(h).chat([], [])
    assert "tools" not in seen["body"]


def test_null_content_with_tool_calls_and_multiple_calls():
    msg = {"role": "assistant", "content": None, "tool_calls": [call("a", "search_datasets", {"query": "x"}), call("b", "load_skill", {"name": "plain-language"})]}
    r = client(lambda req: ok(msg, finish="tool_calls")).chat([], TOOLS)
    assert r.text is None and [c.name for c in r.tool_calls] == ["search_datasets", "load_skill"]
    assert r.tool_calls[0].args == {"query": "x"} and r.finish_reason == "tool_calls"


def test_content_as_list_of_parts():
    r = client(lambda req: ok({"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]})).chat([], [])
    assert r.text == "ab"


@pytest.mark.parametrize("raw,fragment", [("{not json", "not valid JSON"), ('["a"]', "JSON object")])
def test_malformed_arguments_are_flagged_not_raised(raw, fragment):
    r = client(lambda req: ok({"tool_calls": [call("a", "search_datasets", raw)]})).chat([], TOOLS)
    assert r.tool_calls[0].error and fragment in r.tool_calls[0].error and r.tool_calls[0].args == {}


def test_empty_arguments_and_object_arguments_and_missing_id():
    msg = {"tool_calls": [call("a", "run_readiness", ""), {"function": {"name": "x", "arguments": {"k": "v"}}}]}
    r = client(lambda req: ok(msg)).chat([], [])
    assert r.tool_calls[0].args == {} and r.tool_calls[0].error is None
    assert r.tool_calls[1].args == {"k": "v"} and r.tool_calls[1].id


def test_call_without_name_is_flagged():
    r = client(lambda req: ok({"tool_calls": [{"id": "a", "function": {"arguments": "{}"}}]})).chat([], [])
    assert r.tool_calls[0].error


def test_retry_once_on_rate_limit_then_succeed_honouring_retry_after():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        if n["i"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": {"code": 429, "message": "slow down"}})
        return ok({"content": "fine"})

    c = client(h)
    assert c.chat([], []).text == "fine" and n["i"] == 2 and c.sleeps == [3.0]


def test_retry_wait_is_capped():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(429, headers={"Retry-After": "999"}, json={}) if n["i"] == 1 else ok({"content": "k"})

    c = client(h)
    c.chat([], [])
    assert c.sleeps == [10.0]


def test_only_one_retry_then_plain_error():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(502, json={"error": {"code": 502, "message": "upstream"}})

    with pytest.raises(LLMError) as e:
        client(h).chat([], [])
    assert n["i"] == 2 and "not answering" in str(e.value)


@pytest.mark.parametrize("status,fragment", [(401, "key was not accepted"), (402, "out of credits"), (400, "rejected")])
def test_no_retry_for_client_errors(status, fragment):
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(status, json={"error": {"code": status, "message": "m"}})

    with pytest.raises(LLMError) as e:
        client(h).chat([], [])
    assert n["i"] == 1 and fragment in str(e.value) and not e.value.retryable


def test_timeout_is_retried_once_then_reported():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(LLMError) as e:
        client(h).chat([], [])
    assert n["i"] == 2 and "timeout" in str(e.value)


def test_error_inside_http_200_body():
    n = {"i": 0}

    def h(req):
        n["i"] += 1
        return httpx.Response(200, json={"error": {"code": 502, "message": "provider died"}}) if n["i"] == 1 else ok({"content": "back"})

    assert client(h).chat([], []).text == "back" and n["i"] == 2


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="<html>oops</html>"),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json=["not", "a", "dict"]),
])
def test_garbage_replies_raise_llm_error(response):
    with pytest.raises(LLMError):
        client(lambda req: response).chat([], [])


def test_missing_key_is_a_plain_error(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        OpenRouterClient(http=httpx.Client(transport=httpx.MockTransport(lambda r: ok({})))).chat([], [])


def test_usage_missing_or_cost_null():
    r = client(lambda req: ok({"content": "x"}, {"prompt_tokens": 3, "completion_tokens": 1, "cost": None})).chat([], [])
    assert r.usage.cost_usd is None and r.usage.total_tokens == 4
    assert client(lambda req: ok({"content": "x"})).chat([], []).usage is None
