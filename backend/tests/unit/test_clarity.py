import pytest

from app.services.agent import clarity, tools
from tests.helpers.builders import ctx


@pytest.mark.parametrize("text", [
    "Help me predict stuff for my business.",
    "I have no data. Use AI to make my business better.",
    "make it better",
])
def test_vague_goals_are_not_clear(text):
    assert not clarity.is_clear([text])


@pytest.mark.parametrize("text", [
    "I run a subscription business and I want to predict which customers will cancel next month.",
    "Predict whether a loan applicant will fail to pay the loan back.",
    "Predict which of my 40 staff members will quit next year.",
    "Predict the exact sale price of a house from its size and location.",
    "میرے کون سے گاہک اگلے مہینے چھوڑ دیں گے",
    "mere kaun se customers agle mahine chhod denge",
])
def test_goals_that_name_an_outcome_are_clear(text):
    assert clarity.is_clear([text])


def test_an_answer_to_the_question_makes_the_goal_clear():
    assert clarity.is_clear(["Help me predict stuff for my business.", "Which customers will stop buying"])


def test_search_tools_ask_instead_of_searching_on_a_vague_goal(session, storage, provider, project):
    project.goal = "Help me predict stuff for my business."
    session.commit()
    c = ctx(session, storage, provider, project)
    for name, args in (("discover_datasets", {"goal_summary": "x", "queries": ["a b"]}), ("search_datasets", {"query": "x"})):
        r = tools.TOOLS[name].fn(c, args)
        assert r.get("need_clarity") and "ONE short question" in r["advice"] and "candidates" not in r


def test_search_tools_run_when_the_goal_is_clear(session, storage, provider, project):
    r = tools.TOOLS["search_datasets"].fn(ctx(session, storage, provider, project), {"query": "customer churn"})
    assert "need_clarity" not in r and r["results"]
