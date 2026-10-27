import json

from app.services.agent import context, skills
from app.services.agent.tools import TOOLS


def test_every_status_tool_exists_in_the_registry():
    for names in context.TOOLS_BY_STATUS.values():
        assert set(names) <= set(TOOLS)


def test_paid_tools_are_only_offered_when_relevant():
    assert "start_training" not in context.tool_names("described")
    assert "request_payment" not in context.tool_names("data_chosen")
    assert "start_training" in context.tool_names("paid")
    assert context.tool_names("done") == ["load_skill"]


def test_system_prompt_has_state_and_skill_index_but_not_skill_bodies(session, project):
    text = context.build_system(session, project)
    assert "Status: described" in text and "dataset-search" in text
    assert "Fetch at most 2 or 3 candidates" not in text  # bodies load on demand
    assert len(text) < 2500


def test_skills_load_and_unknown_is_none():
    assert "Plain words" in skills.load("plain-language")
    assert skills.load("nope") is None
    assert set(skills.names()) >= {"dataset-search", "data-insights", "cost-quote", "plain-language"}


def test_compact_trims_long_lists_then_text():
    big = {"results": [{"i": n, "pad": "x" * 100} for n in range(100)]}
    out = json.loads(context.compact(big))
    assert len(out["results"]) == 5 and "_trimmed" in out
    assert len(context.compact({"t": "y" * 10_000}, limit=500)) < 600
    assert context.compact({"a": 1}) == '{"a": 1}'


def test_state_block_shows_quote_and_next_step(session, project):
    from tests.test_gate import make_quote
    make_quote(session, project, approved=False)
    s = context.state_block(session, project)
    assert "not approved yet" in s and "Next:" in s


NEW_SKILLS = ["data-leakage", "lopsided-classes", "choosing-the-target-column", "suspiciously-good-baseline",
              "too-little-data", "explaining-results-plainly"]


def test_data_science_skills_are_listed_and_load():
    index = skills.index()
    for name in NEW_SKILLS:
        assert f"- {name}:" in index
        body = skills.load(name)
        assert body and body.startswith("# ")
        assert len(body.splitlines()) < 60  # playbooks stay short


def test_skills_hold_no_money_rules():
    # money rules live in code (gate.py), never in a playbook the model could ignore
    for name in NEW_SKILLS:
        body = skills.load(name).lower()
        for word in ("refund", "paypal", "charge", "start_training", "request_payment"):
            assert word not in body, (name, word)


def test_load_skill_tool_serves_them(session, storage, provider, project):
    from tests.test_agent import ctx
    for name in NEW_SKILLS:
        assert "playbook" in TOOLS["load_skill"].fn(ctx(session, storage, provider, project), {"name": name})


def test_state_block_lists_fetched_candidates_so_the_model_can_propose_select_again(session, storage, project):
    from app.services.data.samples import churn_csv
    from app.services.data import datasets
    c = datasets.add_candidate(session, storage, project, "churn", "bundled", churn_csv(300))
    assert c.id in context.state_block(session, project)
