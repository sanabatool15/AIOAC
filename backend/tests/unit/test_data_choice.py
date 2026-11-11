import pytest

from app.services.agent import data_choice, tools
from tests.helpers.builders import ctx


@pytest.mark.parametrize("text", [
    "I have no data. Please find a dataset.",
    "I don't have any data",
    "can you find me a dataset for this?",
    "Please search for open datasets",
    "mere pas data nahi hai",
    "میرے پاس ڈیٹا نہیں ہے",
])
def test_phrases_that_ask_for_a_search(text):
    assert data_choice.wants_search([text])


@pytest.mark.parametrize("text", [
    "I want to predict which customers will leave.",
    "I will upload my own file",
    "Here is a link to my data",
    "Which data columns matter?",
])
def test_phrases_that_do_not(text):
    assert not data_choice.wants_search([text])


def test_the_picker_sentence_is_recognised():
    assert data_choice.wants_search([data_choice.PICKER_MESSAGE])


@pytest.mark.parametrize("name,args", [("discover_datasets", {"goal_summary": "x", "queries": ["a b"]}), ("search_datasets", {"query": "churn"})])
def test_search_tools_wait_until_the_user_chooses(session, storage, provider, project, name, args):
    project.goal = "predict which customers will leave"
    session.commit()
    r = tools.TOOLS[name].fn(ctx(session, storage, provider, project), args)
    assert r.get("waiting_for_choice") and "three choices" in r["advice"] and "candidates" not in r and "results" not in r


def test_search_runs_after_the_user_says_they_have_no_data(session, storage, provider, project):
    project.goal = "predict which customers will leave. I have no data."
    session.commit()
    r = tools.TOOLS["search_datasets"].fn(ctx(session, storage, provider, project), {"query": "customer churn"})
    assert "waiting_for_choice" not in r and r["results"]


def test_a_model_worded_button_cannot_start_a_search(session, storage, provider, project):
    """The model can offer a button that says "I have no data"; a click on it is not the user's own choice."""
    from app.services.agent.loop import run_agent
    from app.ports import LLMResponse
    from doubles.llm import FakeLLM
    from tests.helpers.builders import call
    project.goal = "predict which customers will leave"
    session.commit()
    llm = FakeLLM([call("search_datasets", query="churn"), LLMResponse(text="Please pick one of the three choices.")])
    run_agent(ctx(session, storage, provider, project), llm, "I have no data. Please find a dataset.", choice=True)
    from app.repositories.traces import TraceRepository
    res = [s.content["result"] for s in TraceRepository(session).steps(project.id, ("tool_result",)) if s.content["name"] == "search_datasets"]
    assert res[0].get("waiting_for_choice")
