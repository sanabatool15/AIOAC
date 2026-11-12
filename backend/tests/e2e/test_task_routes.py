"""The HTTP side of the new task types: choose the kind, select without an answer column, run the free test and pilot."""
import pytest

from app.services.data import datasets
from tests.e2e.test_higher_target import api  # noqa: F401  (the fixture: real routes, mock payments, local training)
from tests.e2e.test_unsupervised import blobs
from tests.helpers.ml_slices import house_csv, sales_csv


def new_project(api, goal="predict something"):
    return api.post("/projects", json={"goal": goal}).json()["id"]


def upload(api, pid, csv: bytes):
    return api.post(f"/projects/{pid}/data", json={"name": "d", "csv_text": csv.decode()}).json()["candidate_id"]


def test_the_kind_is_chosen_before_data_and_only_then(api):
    pid = new_project(api)
    assert api.post(f"/projects/{pid}/task-type", json={"task_type": "regression"}).json() == {
        "task_type": "regression", "plain_name": "a number", "needs_target": True, "pays_success_fee": True}
    assert api.get(f"/projects/{pid}").json()["task_type"] == "regression"
    assert api.post(f"/projects/{pid}/task-type", json={"task_type": "nonsense"}).status_code == 400
    r = api.post(f"/projects/{pid}/task-type", json={"task_type": "grouping"}).json()
    assert r["needs_target"] is False and r["pays_success_fee"] is False
    cid = upload(api, pid, blobs())
    assert api.post(f"/projects/{pid}/data/{cid}/select", json={}).json()["status"] == "data_chosen"
    assert api.post(f"/projects/{pid}/task-type", json={"task_type": "regression"}).status_code == 409


def test_a_number_still_needs_its_answer_column(api):
    pid = new_project(api)
    api.post(f"/projects/{pid}/task-type", json={"task_type": "regression"})
    cid = upload(api, pid, house_csv(400))
    r = api.post(f"/projects/{pid}/data/{cid}/select", json={})
    assert r.status_code == 400 and "which column" in r.json()["detail"]


def test_grouping_runs_the_free_steps_without_a_target_and_the_pilot_has_a_default_bar(api):
    pid = new_project(api)
    api.post(f"/projects/{pid}/task-type", json={"task_type": "grouping"})
    cid = upload(api, pid, blobs())
    api.post(f"/projects/{pid}/data/{cid}/select", json={})
    assert api.post(f"/projects/{pid}/readiness").json()["grade"]
    b = api.post(f"/projects/{pid}/baseline").json()
    assert b["accuracy"] > 0.5 and b["status"] == "baseline_done"
    f = api.post(f"/chats/{pid}/pilot", json={}).json()
    assert f["eligible"] and f["task_type"] == "grouping" and f["target"] == 0.6 and "steady" in f["plain"]["steadiness_text"]
    q = api.post(f"/agreements/{pid}/quote").json()
    assert q["success_fee_max_cents"] == 0 and q["cap_cents"] == q["compute_cap_cents"]


def test_a_number_pilot_without_a_goal_is_refused_and_forecast_takes_a_typical_error(api):
    pid = new_project(api)
    api.post(f"/projects/{pid}/task-type", json={"task_type": "forecast"})
    cid = upload(api, pid, sales_csv("trend", 96))
    api.post(f"/projects/{pid}/data/{cid}/select", json={"target": "units"})
    api.post(f"/projects/{pid}/readiness")
    api.post(f"/projects/{pid}/baseline")
    assert api.post(f"/chats/{pid}/pilot", json={}).status_code == 422
    f = api.post(f"/chats/{pid}/pilot", json={"typical_error": 10}).json()
    assert f["task_type"] == "forecast" and f["plain"] and "typically off by" in f["plain"]["typical_error_text"]
    assert api.post(f"/chats/{pid}/pilot", json={"typical_error": 99999}).status_code == 400
