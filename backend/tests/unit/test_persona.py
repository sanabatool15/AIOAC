"""Phase 2 of specs/agent-data-scientist.md: persona prompt, richer state block, greeting backstop, new skills."""
from app.ports import LLMResponse
from app.repositories import analysis as analysis_repo
from app.services.agent import context, skills
from app.services.agent.loop import run_agent
from app.services.agent.tools import TOOLS
from doubles.llm import FakeLLM
from tests.helpers.builders import call, ctx, eligible_forecast
from tests.unit.test_agent_fixes import _results

NEW_SKILLS = ["ask-like-an-analyst", "why-accuracy-is-low-and-what-helps", "reading-a-forecast", "improve-after-miss"]
BUDGET = 5200  # long state block (dataset, known, decisions, forecast); the plain prompt is capped at 4800 in test_context.py. Raised from 4200 in Phase 2: persona, reply shape, 4 new skill descriptions


def test_persona_and_reply_shape_are_in_the_prompt(session, project):
    text = context.build_system(session, project)
    for needle in ("friendly senior data scientist", "everyday comparisons", "I think", "Reply shape", "call NO tool", "never invent, adjust or extrapolate"):
        assert needle in text
    assert "never 0.8" in text and "never cents" in text


def test_prompt_fits_the_budget_with_a_long_state_block(session, chosen):
    chosen.status = "baseline_done"
    chosen.baseline_result = {"accuracy": 0.81, "simple_guess_accuracy": 0.73}
    session.commit()
    eligible_forecast(session, chosen)
    assert len(context.build_system(session, chosen)) < BUDGET


def test_new_skills_load_are_short_and_hold_no_money_rules():
    index = skills.index()
    for name in NEW_SKILLS + ["explaining-results-plainly", "data-insights"]:
        assert f"- {name}:" in index
        body = skills.load(name)
        assert body and body.startswith("# ") and len(body.splitlines()) < 60
        for word in ("refund", "paypal", "charge", "start_training", "request_payment"):
            assert word not in body.lower(), (name, word)
    for name in NEW_SKILLS:
        assert "Use " in skills._load()[name][0]
    assert "three or four sentences" not in skills.load("explaining-results-plainly")


def test_situation_skills_are_registered_in_the_evals():
    from evals.run import SITUATION_SKILLS
    assert set(NEW_SKILLS) <= SITUATION_SKILLS


def test_state_block_tells_what_is_known_and_decided(session, storage, chosen):
    from app.services.data import analysis
    analysis.readiness(session, storage, chosen)
    s = context.state_block(session, chosen)
    assert "Known about the data:" in s and "rows" in s
    assert "Decisions so far:" not in s  # nothing decided yet
    f = eligible_forecast(session, chosen)
    f.pilot = {"kept": "a forest of decision trees"}
    session.commit()
    s = context.state_block(session, chosen)
    assert "Decisions so far:" in s and "a forest of decision trees" in s and "80 out of 100" in s


def test_state_block_wraps_ignored_column_names_as_untrusted(session, chosen):
    v = context.datasets_repo.get_version(session, chosen.chosen_dataset_version_id)
    analysis_repo.add_insight_report(session, chosen, dataset_version_id=v.id, measurements={"rows": 50, "minority_share": 0.03, "id_columns": ["customerID"]}, findings=[], grade="B")
    s = context.state_block(session, chosen)
    assert "<untrusted_dataset_text>customerID</untrusted_dataset_text>" in s and "lopsided" in s and "3 in 100" in s


def test_next_step_explains_before_the_next_test_but_keeps_the_target_rule():
    for st in ("data_chosen", "readiness_done"):
        assert "plain" in context.NEXT_STEP[st]
    assert "recommendation" in context.NEXT_STEP["readiness_done"]
    assert "target" in context.NEXT_STEP["baseline_done"].lower()
    for st in ("done", "failed", "stopped", "voided"):
        assert "no tools" in context.NEXT_STEP[st]


# ---------------------------------------------------------------- greeting backstop
def test_hi_gets_a_question_and_no_search_even_if_the_model_tries(session, storage, provider, project):
    project.goal = "hi"
    session.commit()
    llm = FakeLLM([call("discover_datasets", goal_summary="x", queries=["a b", "c d"]),
                   LLMResponse(text="Hi! I can predict a yes/no or a group from your own records. What would you like to predict?")])
    r = run_agent(ctx(session, storage, provider, project), llm, "hi")
    res = _results(session, project, "discover_datasets")
    assert res and res[0].get("need_clarity") and "candidates" not in res[0]
    assert "?" in r.text


def test_hi_search_datasets_is_also_held_back(session, storage, provider, project):
    project.goal = "hello there"
    session.commit()
    r = TOOLS["search_datasets"].fn(ctx(session, storage, provider, project), {"query": "customer churn"})
    assert r.get("need_clarity") and "results" not in r


def test_hi_with_a_scripted_greeting_makes_no_tool_call(session, storage, provider, project):
    project.goal = "hi"
    session.commit()
    llm = FakeLLM([LLMResponse(text="Hi! What would you like to predict?")])
    r = run_agent(ctx(session, storage, provider, project), llm, "hi")
    assert "?" in r.text and not _results(session, project, "discover_datasets")
