"""A misbehaving model must never get money spent or steps skipped. Scripted client only, no network."""
import time

from sqlalchemy import select

from app.config import settings
from app.models import AgentRun, AgentStep, Payment
from app.providers.llm.base import LLMError, LLMResponse, ToolCall, Usage
from app.providers.llm.fake import FakeLLM
from app.repositories.traces import TraceRepository
from app.services.agent import tools as agent_tools
from app.services.agent.loop import run_agent
from tests.test_agent import call, ctx
from tests.test_gate import make_quote


def results(session, project):
    return [s.content["result"] for s in TraceRepository(session).steps(project.id, ("tool_result",))]


def gates(session, project):
    return [s.content for s in TraceRepository(session).steps(project.id, ("gate",))]


def go(session, storage, provider, project, script, approved=(), msg="hi"):
    return run_agent(ctx(session, storage, provider, project, approved), FakeLLM(script), msg)


def test_unknown_tool_lists_what_is_available(session, storage, provider, project):
    r = go(session, storage, provider, project, [call("delete_everything"), LLMResponse(text="ok")])
    err = results(session, project)[0]
    assert r.status == "reply" and "unknown tool" in err["error"] and "search_datasets" in err["available"]


def test_missing_and_wrongly_typed_arguments(session, storage, provider, project):
    script = [LLMResponse(tool_calls=[ToolCall("1", "search_datasets", {}), ToolCall("2", "search_datasets", {"query": 42}),
                                      ToolCall("3", "fetch_dataset", {"dataset_id": "  "})]), LLMResponse(text="sorry")]
    go(session, storage, provider, project, script)
    errs = [r["error"] for r in results(session, project)]
    assert "missing: query" in errs[0] and "non-empty text" in errs[1] and "non-empty text" in errs[2]


def test_unreadable_arguments_from_the_client_are_reported_to_the_model(session, storage, provider, project):
    bad = LLMResponse(tool_calls=[ToolCall("1", "search_datasets", {}, error="the arguments were not valid JSON")])
    llm = FakeLLM([bad, LLMResponse(text="ok")])
    run_agent(ctx(session, storage, provider, project), llm, "x")
    assert "could not read the arguments" in results(session, project)[0]["error"]
    # the model sees that error on its next turn
    assert "could not read the arguments" in llm.calls[1][-1]["content"]


def test_several_tool_calls_in_one_reply_all_run(session, storage, provider, project):
    two = LLMResponse(tool_calls=[ToolCall("1", "load_skill", {"name": "plain-language"}), ToolCall("2", "search_datasets", {"query": "churn"})])
    go(session, storage, provider, project, [two, LLMResponse(text="done")])
    assert len(results(session, project)) == 2


def test_repeating_the_same_call_stops_the_turn(session, storage, provider, project):
    r = go(session, storage, provider, project, [call("search_datasets", query="same")] * 10)
    assert r.status == "limit" and r.reason == "repeat" and "going in circles" in r.text


def test_step_limit_message_is_plain(session, storage, provider, project):
    script = [call("search_datasets", query=f"q{i}") for i in range(50)]
    r = go(session, storage, provider, project, script)
    assert r.status == "limit" and r.reason == "steps" and "step limit" in r.text


def test_paid_tools_are_not_offered_or_run_before_approval(session, storage, provider, project):
    # project is at "described": the model asks for every paid tool anyway
    script = [LLMResponse(tool_calls=[ToolCall("1", "request_payment", {}), ToolCall("2", "start_training", {}),
                                      ToolCall("3", "create_quote", {})]), LLMResponse(text="ok")]
    go(session, storage, provider, project, script)
    assert all("not available" in r["error"] for r in results(session, project))
    assert project.status == "described" and session.scalars(select(Payment)).first() is None


def test_request_payment_without_approved_quote_is_denied_by_the_gate(session, storage, provider, project):
    project.status = "awaiting_payment"
    make_quote(session, project, approved=False)
    go(session, storage, provider, project, [call("request_payment"), LLMResponse(text="ok")])
    assert "not allowed" in results(session, project)[0]["error"]
    assert session.scalars(select(Payment)).first() is None
    assert any(g["action"] == "request_payment" and g["allowed"] is False for g in gates(session, project))


def test_start_training_with_unverified_payment_is_denied(session, storage, provider, project):
    q = make_quote(session, project)
    project.status = "paid"
    session.add(Payment(project_id=project.id, quote_id=q.id, provider="mock", provider_order_id="o", amount_cents=700, verified=False))
    session.commit()
    go(session, storage, provider, project, [call("start_training"), LLMResponse(text="ok")])
    assert "not allowed" in results(session, project)[0]["error"] and project.status == "paid"


def test_model_cannot_skip_steps(session, storage, provider, project):
    script = [call("run_baseline"), call("run_readiness"), call("select_dataset", candidate_id="x", target="y"), LLMResponse(text="ok")]
    go(session, storage, provider, project, script)
    errs = [r["error"] for r in results(session, project)]
    assert "not available" in errs[0] and "not available" in errs[1]
    assert project.status == "described"


def test_approval_flag_for_another_action_does_not_unlock_selection(session, storage, provider, project):
    r = go(session, storage, provider, project, [call("select_dataset", candidate_id="x", target="y")], approved={"start_training"})
    assert r.status == "awaiting_approval"


def test_claiming_payment_or_training_that_did_not_happen_is_corrected(session, storage, provider, project):
    for claim in ["Good news, your payment was received and training has started!", "I've started the training now.",
                  "I have refunded the unused amount."]:
        r = go(session, storage, provider, project, [LLMResponse(text=claim)], msg="status?")
        assert r.status == "reply" and r.text.startswith("I need to correct myself"), claim
        assert "Nothing was charged" in r.text
    assert any(s.kind == "claim_blocked" for s in session.scalars(select(AgentStep)))


def test_honest_statements_are_not_touched(session, storage, provider, project):
    for text in ["Your payment has not been received yet.", "I can't start training until you pay.", "The free test is done."]:
        assert go(session, storage, provider, project, [LLMResponse(text=text)]).text == text


def test_true_claims_pass_when_state_supports_them(session, storage, provider, project):
    project.status = "done"
    session.commit()
    assert go(session, storage, provider, project, [LLMResponse(text="Training has finished and the refund was sent.")]).status == "reply"
    assert "correct myself" not in session.scalars(select(AgentStep).where(AgentStep.kind == "assistant")).all()[-1].content["text"]


def test_empty_reply_gets_a_plain_fallback(session, storage, provider, project):
    r = go(session, storage, provider, project, [LLMResponse(text=None)])
    assert r.status == "reply" and r.text


def test_llm_failure_is_a_plain_error_not_a_crash(session, storage, provider, project):
    class Broken:
        def chat(self, m, t):
            raise LLMError("The AI service is busy right now (rate limit).")

    r = run_agent(ctx(session, storage, provider, project), Broken(), "hi")
    assert r.status == "error" and "busy" in r.text


def test_runs_are_recorded_and_steps_carry_the_run_id(session, storage, provider, project):
    llm = FakeLLM([LLMResponse(tool_calls=[ToolCall("1", "search_datasets", {"query": "churn"})], usage=Usage(100, 20, 0.002)),
                   LLMResponse(text="Found one.", usage=Usage(150, 30, 0.003))])
    run_agent(ctx(session, storage, provider, project), llm, "hi")
    run = session.scalars(select(AgentRun)).one()
    assert run.status == "reply" and run.steps_used == 2 and run.tokens_used == 300
    assert run.llm_cost_micros == 5000 and run.ended_at is not None
    steps = TraceRepository(session).steps(project.id)
    assert steps and all(s.run_id == run.id for s in steps)  # includes gate decisions
    assert {"user", "tool_call", "gate", "tool_result", "assistant", "llm"} <= {s.kind for s in steps}


def test_per_turn_token_budget(session, storage, provider, project, monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tokens_per_turn", 1000)
    big = [LLMResponse(tool_calls=[ToolCall(str(i), "search_datasets", {"query": f"q{i}"})], usage=Usage(900, 200)) for i in range(5)]
    r = go(session, storage, provider, project, big)
    assert r.status == "limit" and r.reason == "tokens" and "budget" in r.text


def test_project_token_budget_spans_turns(session, storage, provider, project, monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tokens_per_project", 500)
    go(session, storage, provider, project, [LLMResponse(text="a", usage=Usage(400, 200))])
    r = go(session, storage, provider, project, [LLMResponse(text="b")], msg="again")
    assert r.status == "limit" and r.reason == "project_tokens"


def test_project_llm_cost_ceiling(session, storage, provider, project, monkeypatch):
    monkeypatch.setattr(settings, "agent_llm_cost_ceiling_usd", 0.01)
    go(session, storage, provider, project, [LLMResponse(text="a", usage=Usage(10, 10, 0.02))])
    llm = FakeLLM([LLMResponse(text="never asked")])
    r = run_agent(ctx(session, storage, provider, project), llm, "again")
    assert r.status == "limit" and r.reason == "cost" and "separate from your training price" in r.text
    assert llm.calls == []  # the model was not called at all


def test_cost_ceiling_ignored_when_service_reports_no_cost(session, storage, provider, project, monkeypatch):
    monkeypatch.setattr(settings, "agent_llm_cost_ceiling_usd", 0.0001)
    go(session, storage, provider, project, [LLMResponse(text="a", usage=Usage(10, 10, None))])
    # no cost known -> not enforced (token budgets still are)
    assert go(session, storage, provider, project, [LLMResponse(text="b")], msg="again").status == "reply"


def test_slow_free_tool_times_out_with_plain_message(session, storage, provider, project, monkeypatch):
    monkeypatch.setattr(settings, "agent_tool_timeout_s", 0.05)
    tool = agent_tools.TOOLS["search_datasets"]
    monkeypatch.setitem(agent_tools.TOOLS, "search_datasets",
                        agent_tools.Tool(tool.name, tool.description, tool.parameters, tool.action, lambda c, a: time.sleep(0.5) or {}))
    r = go(session, storage, provider, project, [call("search_datasets", query="x"), LLMResponse(text="unreached")])
    assert r.status == "limit" and r.reason == "timeout" and "took too long" in r.text
    assert any(s.kind == "limit" for s in TraceRepository(session).steps(project.id))
