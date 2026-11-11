"""Fixes G1 to G6 from the first real-model run: the user picks the target, plain wording, honest price breakdown,
readable approval card, clean activity feed. All on the scripted model."""
from datetime import datetime, timezone

import pytest

from app.ports import LLMResponse
from app.repositories.traces import TraceRepository
from app.services import activity
from app.services.agent import context, guards, target
from app.services.agent.loop import run_agent
from app.services.agent.runlog import scrub
from app.services.agent.tools import TOOLS, select_dataset_card
from doubles.llm import FakeLLM
from tests.helpers.builders import call, ctx, eligible_forecast, make_quote
from tests.helpers.fakes import FakeSource


def _results(session, project, name):
    return [s.content["result"] for s in TraceRepository(session).steps(project.id, ("tool_result",)) if s.content["name"] == name]


@pytest.fixture
def baselined(session, chosen):
    chosen.status = "baseline_done"
    chosen.baseline_result = {"accuracy": 0.812, "simple_guess_accuracy": 0.73}
    session.commit()
    return chosen


# ---------------------------------------------------------------- G1: the user names the target
@pytest.mark.parametrize("text,value", [("I need 80 out of 100", 0.8), ("about 80%", 0.8), ("8 out of 10 please", 0.8),
                                        ("aim for 0.8", 0.8), ("85 percent", 0.85), ("at least .9", 0.9)])
def test_numbers_in_the_users_words_are_recognised(text, value):
    assert target.user_named([text], value)


@pytest.mark.parametrize("text", ["Yes, I approve: select dataset. Please carry it out.", "predict 1500 customers", "ok go"])
def test_synthetic_or_number_free_text_names_no_target(text):
    assert not target.user_named([text], 0.8)


def test_pilot_asks_instead_of_choosing_the_target(session, storage, provider, baselined):
    llm = FakeLLM([call("run_pilot", target=0.8), LLMResponse(text="How many out of 100 do you need right? The free test got about 81.")])
    r = run_agent(ctx(session, storage, provider, baselined), llm, "ok, go ahead")
    (res,) = _results(session, baselined, "run_pilot")
    assert res["need_target"] is True and res["baseline_percent"] == 81 and "hint" in res
    assert baselined.status == "baseline_done" and r.status == "reply"
    from app.repositories import forecasts as forecasts_repo
    assert forecasts_repo.all_for_project(session, baselined.id) == []


def test_approval_text_does_not_count_as_a_target(session, storage, provider, baselined):
    llm = FakeLLM([call("run_pilot", target=0.8), LLMResponse(text="Which accuracy do you need?")])
    run_agent(ctx(session, storage, provider, baselined, {"select_dataset"}), llm, None)  # the loop writes "Yes, I approve: ..."
    assert _results(session, baselined, "run_pilot")[0]["need_target"] is True


def test_pilot_runs_when_the_user_stated_the_target(session, storage, provider, baselined):
    llm = FakeLLM([call("run_pilot", target=0.8), LLMResponse(text="Here is the forecast.")])
    run_agent(ctx(session, storage, provider, baselined), llm, "I need 80 out of 100 right")
    (res,) = _results(session, baselined, "run_pilot")
    assert "need_target" not in res and res["target"] == 0.8 and res["target_out_of_100"] == 80 and "band_out_of_100" in res


def test_a_target_other_than_the_one_the_user_said_is_refused(session, storage, provider, baselined):
    run_agent(ctx(session, storage, provider, baselined), FakeLLM([call("run_pilot", target=0.95), LLMResponse(text="ok")]), "I need 80%")
    assert _results(session, baselined, "run_pilot")[0]["need_target"] is True


def test_create_quote_still_needs_an_eligible_forecast(session, storage, provider, baselined):
    run_agent(ctx(session, storage, provider, baselined), FakeLLM([call("create_quote"), LLMResponse(text="ok")]), "I need 80%")
    assert "error" in _results(session, baselined, "create_quote")[0]


# ---------------------------------------------------------------- G2: wording rules
def test_prompt_has_the_wording_rules_and_fits_the_budget(session, project):
    text = context.build_system(session, project)
    for needle in ("no bold", "uci:144", "out of 100", "never cents", "Never choose the target accuracy", "top 2", "platform fee", "free small test", "the most you can be charged"):
        assert needle in text
    assert len(text) < 4800  # 4000 -> 4200 (data-choice and data-fix rules) -> 4800 (Phase 2 persona and new skills)
    assert "pilot" not in text.lower() and "hard cap" not in text.lower()


def test_hints_and_state_use_plain_words(session, storage, provider, baselined):
    from app.services.agent import target
    assert "pilot" not in target.QUESTION_HINT.lower()
    make_quote(session, baselined, approved=False)
    state = context.state_block(session, baselined)
    assert "pilot" not in state.lower() and "cap " not in state.lower()


def test_state_block_uses_out_of_100_and_dollars(session, baselined):
    q = make_quote(session, baselined, approved=False)
    text = context.state_block(session, baselined)
    assert "about 81 out of 100" in text and "0.81" not in text
    assert f"${q.cap_cents / 100:,.2f}" in text and f"{q.cap_cents}c" not in text


def test_baseline_tool_gives_out_of_100(session, storage, provider, chosen):
    chosen.status = "readiness_done"
    session.commit()
    run_agent(ctx(session, storage, provider, chosen), FakeLLM([call("run_baseline"), LLMResponse(text="ok")]), "test it")
    (res,) = _results(session, chosen, "run_baseline")
    assert res["right_out_of_100"] == round(res["accuracy"] * 100)


# ---------------------------------------------------------------- G3: price breakdown
def test_quote_result_and_block_carry_a_plain_breakdown(session, storage, provider, baselined):
    from app.services.agent.blocks import blocks_from_result
    eligible_forecast(session, baselined)
    # the baseline run row with timings is needed by the estimator
    from app.services.data import analysis
    baselined.status = "readiness_done"
    session.commit()
    analysis.baseline(session, storage, baselined)
    from app.services.data import pilot
    pilot.run_pilot(session, storage, baselined, 0.6)
    res = TOOLS["create_quote"].fn(ctx(session, storage, provider, baselined), {})
    bd = res["breakdown"]
    assert set(bd) == {"compute_estimate_cents", "compute_cap_cents", "storage_cents", "platform_fee_cents",
                       "success_fee_estimate_cents", "success_fee_max_cents"}
    assert bd["platform_fee_cents"] and bd["success_fee_max_cents"] == res["success_fee_cents"]
    assert res["in_dollars"]["most_you_can_be_charged"].startswith("$") and res["in_dollars"]["platform_fee"].startswith("$")
    (block,) = blocks_from_result("create_quote", res, baselined)
    assert block["breakdown"] == bd and block["estimate_cents"] == res["estimate_cents"]


# ---------------------------------------------------------------- G4: approval card names
def _title_in_trace(session, project, ident="hf:good/churn", title="Credit card default"):
    TraceRepository(session).add(project.id, "tool_result", {"name": "discover_datasets", "result": {
        "candidates": [{"id": ident, "name": f"<untrusted_dataset_text>{title}</untrusted_dataset_text>", "source": "x"}]}})


def test_fetch_keeps_the_discovery_title_as_the_candidate_name(session, storage, provider, project):
    _title_in_trace(session, project)
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("fetch_dataset", dataset_id="hf:good/churn"), LLMResponse(text="ok")]), "go")
    (res,) = _results(session, project, "fetch_dataset")
    assert res["title"] == "Credit card default"
    from app.repositories import datasets as datasets_repo
    cand = datasets_repo.get_candidate(session, res["candidate_id"])
    assert cand.name == "Credit card default" and "good/churn" in cand.source_url  # the internal id stays in the link


def test_card_has_title_source_rows_and_target_meaning(session, storage, provider, project):
    from app.services.data import datasets
    from app.services.data.samples import churn_csv
    c = datasets.add_candidate(session, storage, project, "Credit card default", "UCI", churn_csv(1500))
    card = select_dataset_card(ctx(session, storage, provider, project),
                               {"candidate_id": c.id, "target": "left", "target_meaning": "whether the next payment was missed"})
    assert card["what"] == 'Use "Credit card default" (UCI, 1,500 rows) and predict "left": whether the next payment was missed'
    assert card["detail"]["target_meaning"] == "whether the next payment was missed" and card["detail"]["name"] == "Credit card default"


def test_target_meaning_is_optional_and_validated():
    params = TOOLS["select_dataset"].parameters
    assert "target_meaning" in params["properties"] and "target_meaning" not in params["required"]
    assert guards.check_args(params, {"candidate_id": "a", "target": "b"}) is None
    assert "target_meaning" in guards.check_args(params, {"candidate_id": "a", "target": "b", "target_meaning": 5})


def test_approved_select_without_target_meaning_still_runs(session, storage, provider, project):
    from app.services.data import datasets
    from app.services.data.samples import churn_csv
    c = datasets.add_candidate(session, storage, project, "Churn", "bundled", churn_csv(1500))
    run_agent(ctx(session, storage, provider, project), FakeLLM([call("select_dataset", candidate_id=c.id, target="left")]), "that one")
    r = run_agent(ctx(session, storage, provider, project, {"select_dataset"}), FakeLLM([LLMResponse(text="Sure!"), LLMResponse(text="Done")]), None)
    assert project.status == "data_chosen" and r.status == "reply"


# ---------------------------------------------------------------- G5: activity feed
def test_secret_scrubber_keeps_dataset_ids_but_still_hides_keys():
    ident = "hf:someone/risk-assessment-credit-default-prediction-v2"
    assert scrub(f"Looked at {ident}") == f"Looked at {ident}"
    assert scrub("hf:org/task-sk-abcdefghijklmnopqrstuvwx") == "hf:org/task-sk-abcdefghijklmnopqrstuvwx"
    assert "sk-abcdefghijklmnopqrstu" not in scrub("key is sk-abcdefghijklmnopqrstuvwxyz123456")
    assert "[redacted key]" in scrub("OPENAI sk-proj-abcdefghijklmnopqrstuvwxyz")


def test_feed_has_titles_not_ids_and_drops_approval_text(session, storage, provider, project):
    t = TraceRepository(session)
    t.add(project.id, "user", {"text": "Yes, I approve: select dataset. Please carry it out."})
    t.add(project.id, "user", {"text": "predict who defaults"})
    t.add(project.id, "tool_call", {"name": "look_at_dataset", "args": {"dataset_id": "uci:144"}})
    t.add(project.id, "tool_result", {"name": "look_at_dataset", "result": {"title": "Credit card default", "rows": 30000}})
    t.add(project.id, "tool_call", {"name": "fetch_dataset", "args": {"dataset_id": "hf:someone/risk-assessment-credit-default-prediction-v2"}})
    t.add(project.id, "tool_result", {"name": "fetch_dataset", "result": {"title": "Credit card default", "rows": 30000, "candidate_id": "x"}})
    t.add(project.id, "tool_call", {"name": "look_at_dataset", "args": {"dataset_id": "uci:999"}})
    t.add(project.id, "tool_result", {"name": "look_at_dataset", "result": {"rows": 10}})
    texts = " | ".join(f["text"] for f in activity.activity(session, project))
    assert "Yes, I approve" not in texts and "predict who defaults" in texts
    assert "uci:" not in texts and "hf:" not in texts and "[redacted" not in texts
    assert 'Looked at "Credit card default"' in texts and 'Downloaded "Credit card default"' in texts
    assert "Looked at a dataset" in texts


# ---------------------------------------------------------------- a button the model offered is not the user's own words
def test_a_clicked_model_option_does_not_name_the_target(session, storage, provider, baselined):
    """ask_choice buttons are worded by the model. A click on "80 out of 100" must not satisfy the G1 target guard."""
    llm = FakeLLM([call("run_pilot", target=0.8), LLMResponse(text="How many out of 100 do you need right?")])
    run_agent(ctx(session, storage, provider, baselined), llm, "80 out of 100", choice=True)
    assert _results(session, baselined, "run_pilot")[0]["need_target"] is True


def test_a_typed_target_still_counts_after_a_choice_click(session, storage, provider, baselined):
    run_agent(ctx(session, storage, provider, baselined), FakeLLM([LLMResponse(text="ok")]), "70 out of 100", choice=True)
    llm = FakeLLM([call("run_pilot", target=0.8), LLMResponse(text="Here is the forecast.")])
    run_agent(ctx(session, storage, provider, baselined), llm, "I need 80 out of 100 right")
    assert "need_target" not in _results(session, baselined, "run_pilot")[0]


def test_a_clicked_option_is_shown_in_the_chat_like_any_user_message(session, storage, provider, baselined):
    from app.repositories import conversations
    run_agent(ctx(session, storage, provider, baselined), FakeLLM([LLMResponse(text="ok")]), "Column A", choice=True)
    msgs = conversations.project_messages(session, baselined.id)
    assert any(m.role == "user" and m.content == "Column A" and m.kind == "choice" for m in msgs)
