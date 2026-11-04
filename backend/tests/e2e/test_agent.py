from app.ports import LLMResponse
from doubles.llm import FakeLLM
from app.services.agent.loop import run_agent
from tests.helpers.builders import ctx, call






def test_plain_reply(session, storage, provider, project):
    r = run_agent(ctx(session, storage, provider, project), FakeLLM([LLMResponse(text="Do you have past customers?")]), "hi")
    assert r.status == "reply" and "customers" in r.text


def test_selecting_a_dataset_stops_for_user_approval(session, storage, provider, project):
    llm = FakeLLM([call("search_datasets", query="churn"), call("fetch_dataset", dataset_id="sample-churn")])
    r = run_agent(ctx(session, storage, provider, project), llm, "predict churn")
    assert r.status == "reply" or r.status == "awaiting_approval"
    from app.db.tables import DatasetCandidate
    cand = session.query(DatasetCandidate).one()
    llm2 = FakeLLM([call("select_dataset", candidate_id=cand.id, target="left")])
    r2 = run_agent(ctx(session, storage, provider, project), llm2, "that one")
    assert r2.status == "awaiting_approval" and r2.card["tool"] == "select_dataset"
    assert project.status == "described"  # nothing changed without approval
    r3 = run_agent(ctx(session, storage, provider, project, {"select_dataset"}),
                   FakeLLM([call("select_dataset", candidate_id=cand.id, target="left"), LLMResponse(text="Done")]), None)
    assert r3.status == "reply" and project.status == "data_chosen"


def test_tools_not_offered_at_this_step_are_refused(session, storage, provider, project):
    llm = FakeLLM([call("start_training"), LLMResponse(text="I can't start yet.")])
    r = run_agent(ctx(session, storage, provider, project), llm, "train it now")
    assert r.status == "reply"
    from app.repositories.traces import TraceRepository
    res = [s.content["result"] for s in TraceRepository(session).steps(project.id, ("tool_result",))]
    assert "not available" in res[0]["error"] and project.status == "described"


def test_gate_still_blocks_training_even_when_status_says_paid(session, storage, provider, project):
    project.status = "paid"  # wrongly marked paid, no quote and no verified payment exist
    session.commit()
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("start_training"), LLMResponse(text="no")]), "go")
    from app.repositories.traces import TraceRepository
    res = [s.content["result"] for s in TraceRepository(session).steps(project.id, ("tool_result",))]
    assert "not allowed" in res[0]["error"] and project.status == "paid"


def test_step_limit(session, storage, provider, project):
    llm = FakeLLM([call("search_datasets", query="x")] * 50)
    r = run_agent(ctx(session, storage, provider, project), llm, "loop")
    assert r.status == "limit"


def test_unknown_tool_is_reported_not_crashed(session, storage, provider, project):
    r = run_agent(ctx(session, storage, provider, project), FakeLLM([call("rm_rf"), LLMResponse(text="ok")]), "x")
    assert r.status == "reply"


def test_approved_tool_runs_server_side_when_the_model_answers_text_only(session, storage, provider, project):
    """The user approved the card; the model just chats. The stored card's call is carried out by the server (the gate still checks)."""
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("search_datasets", query="churn"), call("fetch_dataset", dataset_id="sample-churn")]), "predict churn")
    from app.db.tables import DatasetCandidate
    cand = session.query(DatasetCandidate).one()
    r2 = run_agent(ctx(session, storage, provider, project), FakeLLM([call("select_dataset", candidate_id=cand.id, target="left")]), "that one")
    assert r2.status == "awaiting_approval" and project.status == "described"
    llm = FakeLLM([LLMResponse(text="Sure, happy to help!"), LLMResponse(text="Your data is chosen.")])
    r3 = run_agent(ctx(session, storage, provider, project, {"select_dataset"}), llm, None)
    assert project.status == "data_chosen" and r3.status == "reply" and "chosen" in r3.text


def test_approval_never_runs_a_tool_the_user_did_not_approve(session, storage, provider, project):
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("search_datasets", query="churn"), call("fetch_dataset", dataset_id="sample-churn")]), "x")
    from app.db.tables import DatasetCandidate
    cand = session.query(DatasetCandidate).one()
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("select_dataset", candidate_id=cand.id, target="left")]), "that one")
    r = run_agent(ctx(session, storage, provider, project, {"request_payment"}), FakeLLM([LLMResponse(text="ok")]), None)
    assert project.status == "described" and r.status == "reply"
