"""Slice S14 (agent): the agent can choose the kind of prediction, never chooses the goal, and speaks each type's own words."""
import re

import pytest

from app.services.agent import tools
from app.services.data import analysis, datasets
from tests.e2e.test_unsupervised import blobs
from tests.helpers.builders import ctx
from tests.helpers.ml_slices import house_csv

NO_100 = re.compile(r"out of 100 (right|predictions)", re.I)


def test_set_task_type_changes_the_project_and_says_when_there_is_no_fee(session, storage, provider, project):
    out = tools.set_task_type(ctx(session, storage, provider, project), {"task_type": "grouping"})
    assert out["task_type"] == "grouping" and out["needs_answer_column"] is False and "no success fee" in out["money_note"]
    assert project.task_type == "grouping"
    assert "error" in tools.set_task_type(ctx(session, storage, provider, project), {"task_type": "images"})
    assert tools.TOOLS["set_task_type"].action.value == "analyze"   # free: level 0


def test_the_kind_cannot_change_after_data_is_chosen(session, storage, provider, chosen):
    assert "error" in tools.set_task_type(ctx(session, storage, provider, chosen), {"task_type": "regression"})


def test_select_dataset_needs_no_target_for_groups(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    tools.set_task_type(c, {"task_type": "grouping"})
    cand = datasets.add_candidate(session, storage, project, "customers", "bundled", blobs())
    card = tools.select_dataset_card(c, {"candidate_id": cand.id})
    assert "look for groups" in card["what"]
    assert tools.select_dataset(c, {"candidate_id": cand.id})["target"] is None
    assert "target" not in tools.TOOLS["select_dataset"].parameters["required"]


@pytest.fixture
def numbers(session, storage, project):
    project.task_type = "regression"
    c = datasets.add_candidate(session, storage, project, "houses", "bundled", house_csv(1500))
    datasets.select_candidate(session, storage, project, c.id, "price")
    analysis.readiness(session, storage, project)
    analysis.baseline_detailed(session, storage, project)
    return project


def test_a_number_goal_must_be_in_the_users_own_words(session, storage, provider, numbers):
    out = tools.run_pilot(ctx(session, storage, provider, numbers), {"typical_error": 10000})
    assert out["need_target"] is True and out["task_type"] == "regression" and "amount" in out["hint"]
    numbers.goal = "what will it sell for, I can accept being off by $10,000"
    session.commit()
    out = tools.run_pilot(ctx(session, storage, provider, numbers), {"typical_error": 10000})
    assert "need_target" not in out and out["plain"]["typical_error_text"] and "$" in out["plain"]["target_text"]
    assert not NO_100.search(str(out))   # a number answer is never "out of 100 right"


def test_groups_need_no_goal_and_speak_in_steadiness(session, storage, provider, project):
    c = ctx(session, storage, provider, project)
    tools.set_task_type(c, {"task_type": "grouping"})
    cand = datasets.add_candidate(session, storage, project, "customers", "bundled", blobs())
    tools.select_dataset(c, {"candidate_id": cand.id})
    analysis.readiness(session, storage, project)
    base = tools.run_baseline_tool(c, {})
    assert base["task_type"] == "grouping" and "steady" in base["result_text"] and not NO_100.search(str(base))
    out = tools.run_pilot(c, {})
    assert out["eligible"] and out["task_type"] == "grouping" and "steady" in out["plain"]["steadiness_text"]
