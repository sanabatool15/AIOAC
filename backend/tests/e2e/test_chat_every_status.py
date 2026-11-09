"""Phase 4 (specs/agent-data-scientist.md): the chat works at every project status with only that status's tools,
explain_result reads a finished run, and the claim guard still blocks promises to run anything."""
import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.deps import get_ctx_factory, get_llm_client
from app.integrations.training_local.backend import LocalBackend
from app.main import app
from app.ports import LLMResponse
from app.services import gate
from app.services.agent import context
from app.services.agent.tools import ToolContext
from doubles.llm import FakeLLM
from tests.e2e.test_higher_target import api as run_api, one_round  # noqa: F401  (fixture reused)
from tests.helpers.builders import call

ALL_STATUSES = ["described", "data_chosen", "readiness_done", "baseline_done", "quoted", "awaiting_payment", "paid",
                "training", "done", "failed", "stopped", "voided"]


class Spy(FakeLLM):
    def __init__(self, script):
        super().__init__(script)
        self.tool_sets: list[list[str]] = []

    def chat(self, messages, tools):
        self.tool_sets.append([t["name"] for t in tools])
        return super().chat(messages, tools)


@pytest.fixture
def chat_api(session, storage, provider):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set(approved)))
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("status", ALL_STATUSES)
def test_chat_answers_at_every_status_with_only_that_statuss_tools(chat_api, session, chosen, status):
    chosen.status = status
    session.commit()
    spy = Spy([LLMResponse(text="Here is where things stand.")])
    app.dependency_overrides[get_llm_client] = lambda: spy
    r = chat_api.post(f"/projects/{chosen.id}/chat", json={"message": "where are we?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "reply" and body["text"] == "Here is where things stand." and body["card"] is None
    assert spy.tool_sets == [context.tool_names(status)]
    # no paid tool is ever offered where the gate would not allow it, and explain_result only after a run ended
    assert ("explain_result" in spy.tool_sets[0]) == (status in ("done", "stopped", "failed"))
    assert ("start_training" in spy.tool_sets[0]) == (status == "paid")


def test_explain_result_is_level_zero_and_not_offered_before_a_run():
    from app.services.agent.tools import TOOLS
    t = TOOLS["explain_result"]
    assert gate.LEVEL[t.action] == 0
    for st in ("described", "data_chosen", "readiness_done", "baseline_done", "quoted", "awaiting_payment", "paid", "training", "voided"):
        assert "explain_result" not in context.tool_names(st)


def test_explain_result_after_a_hit_and_a_miss_through_the_chat(run_api, chat_api, session, storage, provider, chosen, verdict):
    pid = chosen.id
    assert run_api.post(f"/projects/{pid}/readiness").status_code == 200
    assert run_api.post(f"/projects/{pid}/baseline").status_code == 200
    verdict["value"] = 0.9
    one_round(run_api, session, storage, provider, chosen, 0.6)
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM([call("explain_result"), LLMResponse(text="You reached your target.")])
    r = chat_api.post(f"/projects/{pid}/chat", json={"message": "what does this mean?"}).json()
    (b,) = r["blocks"]
    assert b["type"] == "result" and b["outcome"] == "done" and b["target_met"] is True
    assert b["verified_out_of_100"] == 90 and b["target_out_of_100"] == 60 and b["model_type"]
    assert "total_charged" not in str(b) and "$" not in str(b)   # money stays on the receipt, not in the block

    from app.services import explain
    facts = explain.result_facts(session, chosen)
    assert facts["outcome"] == "done" and facts["target_met"] is True and facts["rows_in_data"] > 0
    assert facts["money"]["total_charged"].startswith("$") and facts["money"]["released"].startswith("$")
    assert facts["simple_guess_out_of_100"] is not None and "verified_vs_free_test" in facts

    # a second, higher target that is missed on the locked rows
    verdict["value"] = 0.5
    one_round(run_api, session, storage, provider, chosen, 0.65)
    miss = explain.result_facts(session, chosen)
    assert miss["target_met"] is False and miss["verified_out_of_100"] == 50 and miss["target_out_of_100"] == 65
    assert any("lower target" in tip for tip in miss["what_could_help"])
    # the activity feed knows the tool, the log keeps the tool result stub
    from app.services.agent import memory
    assert memory.stub_for("explain_result", miss).startswith("explain_result: ok, outcome=done")


def test_a_promise_to_retrain_is_still_blocked_where_explain_result_exists(chat_api, session, chosen):
    for status in ("done", "stopped", "failed"):
        chosen.status = status
        session.commit()
        app.dependency_overrides[get_llm_client] = lambda: FakeLLM([call("explain_result"), LLMResponse(text="I will retrain it with new settings now.")])
        r = chat_api.post(f"/projects/{chosen.id}/chat", json={"message": "can you fix it?"}).json()
        assert "I need to correct myself" in r["text"], status
        assert "retrain" not in r["text"] or "correct myself" in r["text"]
