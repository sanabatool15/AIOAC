"""The guided data fix through the real routes: propose, apply (the click), re-run the free steps, new price, paid run."""
import io

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_session
from app.deps import get_ctx_factory
from app.integrations.training_local.backend import LocalBackend
from app.repositories import datasets as datasets_repo
from app.repositories import payments as payments_repo
from app.routes import fixes as fix_routes
from app.routes import forecast as forecast_routes
from app.routes import quotes as quote_routes
from app.services import payments, training
from app.services.agent.tools import ToolContext
from app.services.cost import quotes
from app.services.data import analysis, datasets, verification
from tests.e2e.test_payments_and_demo import ScriptedBackend
from tests.helpers.auth import sign_in
from tests.unit.test_fixes import messy_csv


def client(session, storage, provider):
    app = sign_in(FastAPI())
    for r in (forecast_routes.router, quote_routes.router, fix_routes.router):
        app.include_router(r)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", LocalBackend(), None, set(approved)))
    return TestClient(app)


@pytest.fixture
def messy(session, storage, project):
    c = datasets.add_candidate(session, storage, project, "messy", "bundled", messy_csv())
    datasets.select_candidate(session, storage, project, c.id, "left")
    analysis.readiness(session, storage, project)
    analysis.baseline(session, storage, project)
    return project


def test_propose_then_apply_then_pilot_then_a_new_price(session, storage, messy, provider):
    c = client(session, storage, provider)
    root_id = messy.chosen_dataset_version_id
    r = c.post(f"/chats/{messy.id}/fix/propose")
    prop = r.json()
    assert r.status_code == 200 and prop["available"] and prop["columns_dropped"] == ["notes_col"] and prop["rows_removed"] > 0
    assert prop["rows_before"] - prop["rows_removed"] == prop["rows_after"] and messy.chosen_dataset_version_id == root_id  # nothing changed yet

    assert c.post(f"/chats/{messy.id}/pilot", json={"target": 0.6}).json()["eligible"]
    first_quote = c.post(f"/agreements/{messy.id}/quote").json()["quote_id"]
    assert messy.status == "quoted"

    done = c.post(f"/chats/{messy.id}/fix/apply", json={"version_id": prop["version_id"]})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "baseline_done" and body["rows_after"] == prop["rows_after"] and body["fixes_left"] == 2
    assert messy.chosen_dataset_version_id == body["version_id"] != root_id
    # the old price is no longer valid, and no new price can be made from the old forecast
    from app.repositories import quotes as quotes_repo
    refused = c.post(f"/agreements/{messy.id}/quote")
    assert refused.status_code == 409 and "data changed" in refused.json()["detail"]
    assert quotes_repo.latest_for_project(session, messy.id).id == first_quote
    # the free pilot is run again on the new data; then a new price pinned to the new version
    assert c.get(f"/jobs/{messy.id}/forecast").json()["before_fix"] is None   # nothing to compare with yet
    f = c.post(f"/chats/{messy.id}/pilot", json={"target": 0.6}).json()
    assert f["eligible"]
    assert f["before_fix"] and set(f["before_fix"]) >= {"predicted_metric", "confidence", "band_low", "band_high"}  # the forecast on the old data
    q = c.post(f"/agreements/{messy.id}/quote")
    assert q.status_code == 200 and q.json()["quote_id"] != first_quote
    assert quotes_repo.latest_for_project(session, messy.id).dataset_version_id == body["version_id"]


def test_the_activity_feed_says_a_fix_was_applied_in_plain_words(session, storage, messy, provider):
    from app.services import activity
    client(session, storage, provider).post(f"/chats/{messy.id}/fix/apply", json={})
    lines = [a["text"] for a in activity.activity(session, messy) if a["kind"] == "datafix"]
    assert len(lines) == 1 and lines[0].startswith("Changed your data after you approved it") and "original is kept" in lines[0]
    assert "datasets/" not in lines[0]   # never a storage key


def test_apply_is_refused_when_the_data_moved_on(session, storage, messy, provider):
    c = client(session, storage, provider)
    r = c.post(f"/chats/{messy.id}/fix/apply", json={"version_id": "an-older-version"})
    assert r.status_code == 409 and "changed" in r.json()["detail"]


def test_apply_with_nothing_to_fix_is_a_plain_409(session, storage, project, provider):
    clean = pd.read_csv(io.BytesIO(messy_csv(dups=0, empty_share=0.0))).drop_duplicates()
    cand = datasets.add_candidate(session, storage, project, "clean", "bundled", clean.to_csv(index=False).encode())
    datasets.select_candidate(session, storage, project, cand.id, "left")
    analysis.readiness(session, storage, project)
    analysis.baseline(session, storage, project)
    c = client(session, storage, provider)
    assert c.post(f"/chats/{project.id}/fix/propose").json()["available"] is False
    r = c.post(f"/chats/{project.id}/fix/apply", json={})
    assert r.status_code == 409 and "nothing" in r.json()["detail"].lower()


def test_the_limit_is_three_applied_fixes(session, storage, messy, provider, monkeypatch):
    from app.config import settings
    c = client(session, storage, provider)
    assert settings.max_fixes_per_project == 3
    for _ in range(3):  # each round makes the data messy again by hand so another fix is possible
        assert c.post(f"/chats/{messy.id}/fix/apply", json={}).status_code == 200
        v = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
        df = pd.read_csv(io.BytesIO(storage.get(v.storage_key)))
        df["junk"] = None
        df = pd.concat([df, df.head(20)], ignore_index=True)
        storage.put(v.storage_key, df.to_csv(index=False).encode())
        v.rows, v.columns = len(df), df.shape[1]
        session.commit()
    r = c.post(f"/chats/{messy.id}/fix/apply", json={})
    assert r.status_code == 409 and "most we try" in r.json()["detail"]
    assert c.post(f"/chats/{messy.id}/fix/propose").json()["fixes_left"] == 0


def test_paid_run_after_a_fix_trains_on_the_child_and_verifies_on_the_roots_locked_rows(session, storage, messy, provider, verdict):
    c = client(session, storage, provider)
    root = datasets_repo.get_version(session, messy.chosen_dataset_version_id)
    verification.split_for(session, storage, root)
    _, root_locked_key = verification.split_keys(root.id)
    root_locked = pd.read_csv(storage.path(root_locked_key))
    child_id = c.post(f"/chats/{messy.id}/fix/apply", json={}).json()["version_id"]
    assert c.post(f"/chats/{messy.id}/pilot", json={"target": 0.6}).json()["eligible"]
    q = quotes.create_quote(session, messy)
    quotes.approve_quote(session, messy, q)
    pay, _ = payments.create_order(session, provider, "mock", messy)
    assert payments.confirm_hold(session, provider, pay)
    backend = ScriptedBackend(cost=10)
    run = training.run_training(session, messy, backend, storage, provider)
    assert run.status == "done" and run.dataset_version_id == child_id
    work_path = backend.paths[0]
    assert child_id in work_path   # trained on the child's work rows
    work = pd.read_csv(work_path)
    cols = list(work.columns)
    assert not set(verification.row_keys(work, cols)) & set(verification.row_keys(root_locked, cols))   # no locked row in the work set
    assert payments_repo.for_quote(session, q.id).state in {"released", "fee_captured", "fee_skipped"}
