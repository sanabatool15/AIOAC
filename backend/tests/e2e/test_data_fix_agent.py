"""The agent's two data-fix tools: propose is free and read-only; apply needs the user's approval card."""
from app.ports import LLMResponse
from app.repositories import datasets as datasets_repo
from app.routes.projects import _approved_actions
from app.services.agent import context
from app.services.agent.loop import run_agent
from doubles.llm import FakeLLM
from tests.e2e.test_data_fix_flow import messy  # noqa: F401  (fixture)
from tests.helpers.builders import call, ctx


def test_the_tools_are_offered_only_where_a_fix_makes_sense():
    for status in ("baseline_done", "quoted"):
        assert {"propose_data_fix", "apply_data_fix"} <= set(context.tool_names(status))
    for status in ("described", "data_chosen", "readiness_done", "awaiting_payment", "paid", "training", "done"):
        assert not {"propose_data_fix", "apply_data_fix"} & set(context.tool_names(status))


def test_propose_is_free_and_changes_nothing(session, storage, provider, messy):  # noqa: F811
    before = (messy.chosen_dataset_version_id, datasets_repo.count_versions(session, messy.id))
    r = run_agent(ctx(session, storage, provider, messy),
                  FakeLLM([call("propose_data_fix"), LLMResponse(text="We could remove repeated rows; we will test whether it changes the estimate.")]), "can we improve it?")
    assert r.status == "reply"
    assert before == (messy.chosen_dataset_version_id, datasets_repo.count_versions(session, messy.id))


def test_apply_stops_at_a_card_that_shows_the_change_and_changes_nothing(session, storage, provider, messy):  # noqa: F811
    r = run_agent(ctx(session, storage, provider, messy), FakeLLM([call("apply_data_fix")]), "fix it")
    assert r.status == "awaiting_approval" and r.card["tool"] == "apply_data_fix" and r.card["level"] == 1
    d = r.card["detail"]
    assert d["rows_removed"] > 0 and d["columns_dropped"] == ["notes_col"]
    assert d["rows_after"] == d["rows_before"] - d["rows_removed"] and d["columns_after"] == d["columns_before"] - 1
    assert "original stays saved" in r.card["what"]
    assert r.card["args"]["version_id"] == d["version_id"]
    assert datasets_repo.count_versions(session, messy.id) == 1 and messy.status == "baseline_done"


def test_approved_apply_makes_the_new_version(session, storage, provider, messy):  # noqa: F811
    root_id = messy.chosen_dataset_version_id
    run_agent(ctx(session, storage, provider, messy), FakeLLM([call("apply_data_fix")]), "fix it")
    r = run_agent(ctx(session, storage, provider, messy, {"clean"}),
                  FakeLLM([call("apply_data_fix"), LLMResponse(text="Done. Let's run the free test again.")]), None)
    assert r.status == "reply" and messy.chosen_dataset_version_id != root_id
    child = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
    assert child.parent_id == root_id and messy.status == "baseline_done"


def test_an_approval_of_another_action_does_not_apply_the_fix(session, storage, provider, messy):  # noqa: F811
    root_id = messy.chosen_dataset_version_id
    r = run_agent(ctx(session, storage, provider, messy, {"select_dataset"}), FakeLLM([call("apply_data_fix")]), "fix it")
    assert r.status == "awaiting_approval" and messy.chosen_dataset_version_id == root_id


def test_the_chat_route_turns_the_card_tool_into_the_gate_action():
    assert _approved_actions(["apply_data_fix"]) == {"clean"}
    assert _approved_actions(["select_dataset", "something-else"]) == {"select_dataset", "something-else"}
