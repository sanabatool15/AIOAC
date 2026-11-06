"""Chat replies carry typed blocks built by code from tool results (not by the model), and history returns them."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.deps import get_llm_client
from app.main import app
from app.ports import LLMResponse
from doubles.llm import FakeLLM
from tests.helpers.builders import call


@pytest.fixture
def api(session, storage, provider):
    from app.deps import get_ctx_factory
    from app.integrations.training_local.backend import LocalBackend
    from app.services.agent.tools import ToolContext
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set(approved)))
    yield TestClient(app)
    app.dependency_overrides.clear()


def chat(api, pid, script, **body):
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM(script)
    return api.post(f"/projects/{pid}/chat", json={"message": "go", **body}).json()


def test_plain_reply_has_empty_blocks(api, project):
    r = chat(api, project.id, [LLMResponse(text="Hi")])
    assert r["blocks"] == [] and r["status"] == "reply" and r["text"] == "Hi" and r["card"] is None


def test_readiness_then_baseline_blocks_and_history(api, session, chosen):
    r = chat(api, chosen.id, [call("run_readiness"), LLMResponse(text="Your data looks fine.")])
    (b,) = r["blocks"]
    assert b["type"] == "readiness" and b["grade"] and b["trust"] is None
    assert all(f["kind"] in ("OK", "NOTE") and f["text"] for f in b["findings"])
    r2 = chat(api, chosen.id, [call("run_baseline"), LLMResponse(text="Free test done.")])
    (b2,) = r2["blocks"]
    assert b2["type"] == "baseline" and 0 <= b2["simple_guess_accuracy"] <= 1 and 0 <= b2["accuracy"] <= 1 and b2["trust"] in ("Low", "Medium", "High")
    msgs = api.get(f"/projects/{chosen.id}/messages").json()
    assistant = [m for m in msgs if m["role"] == "assistant"]
    assert [m["blocks"][0]["type"] for m in assistant] == ["readiness", "baseline"]
    assert all(m["blocks"] == [] for m in msgs if m["role"] == "user")


def test_quote_and_pay_blocks_from_tool_results():
    from app.services.agent.blocks import blocks_from_result
    q = blocks_from_result("create_quote", {"quote_id": "q1", "estimate_cents": 500, "range_cents": [400, 700], "cap_cents": 700,
                                            "success_fee_cents": 30, "label": "estimate"}, None)
    assert q == [{"type": "quote", "quote_id": "q1", "estimate_cents": 500, "low_cents": 400, "high_cents": 700, "cap_cents": 700,
                  "success_fee_cents": 30, "is_estimate": True}]
    p = blocks_from_result("request_payment", {"payment_id": "p1", "hold_cents": 730, "approve_url": "https://sandbox.paypal.com/x"}, None)
    assert p == [{"type": "pay", "payment_id": "p1", "approve_url": "https://sandbox.paypal.com/x", "hold_cents": 730}]
    assert blocks_from_result("create_quote", {"error": "no"}, None) == []
    assert blocks_from_result("search_datasets", {"results": []}, None) == []


def test_pay_block_in_a_chat_turn(api, session, chosen):
    from tests.helpers.builders import eligible_forecast, make_quote
    q = make_quote(session, chosen)
    eligible_forecast(session, chosen)
    chosen.status = "awaiting_payment"
    session.commit()
    r = chat(api, chosen.id, [call("request_payment"), LLMResponse(text="Please approve the hold in PayPal.")])
    (b,) = [b for b in r["blocks"] if b["type"] == "pay"]
    assert b["payment_id"] and b["approve_url"] and b["hold_cents"] == q.cap_cents


def test_select_dataset_card_names_the_dataset(api, session, storage, project):
    """F9: the approval card says which dataset and which column, in plain words."""
    from app.services.data import datasets
    from app.services.data.samples import churn_csv
    c = datasets.add_candidate(session, storage, project, "Credit card default", "UCI", churn_csv(1500), license="cc-by-4.0")
    r = chat(api, project.id, [call("select_dataset", candidate_id=c.id, target="left")])
    assert r["status"] == "awaiting_approval"
    card = r["card"]
    assert card["tool"] == "select_dataset" and card["level"] == 1 and card["args"]["candidate_id"] == c.id
    assert card["what"] == 'Use "Credit card default" (UCI, 1,500 rows) and predict the column "left"'
    d = card["detail"]
    assert d["name"] == "Credit card default" and d["source"] == "UCI" and d["rows"] == 1500
    assert d["license"] == "cc-by-4.0" and d["target"] == "left" and d["columns"] > 1
    stored = [m for m in api.get(f"/projects/{project.id}/messages").json() if m["kind"] == "card"]
    assert stored[-1]["card"]["detail"] == d and stored[-1]["text"] == card["what"]


def test_select_dataset_card_unknown_candidate_is_null_detail(api, project):
    r = chat(api, project.id, [call("select_dataset", candidate_id="nope", target="left")])
    assert r["status"] == "awaiting_approval"
    assert r["card"]["detail"] == {"name": None, "source": None, "rows": None, "columns": None, "license": None, "target": "left"}
    assert r["card"]["what"]
