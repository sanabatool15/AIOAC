"""Routes for the screens that come back on real data: history, activity, model use, account totals, receipts, sharing."""
import json

import pytest
from fastapi.testclient import TestClient

from app.db import get_session
from app.db.tables import Project
from app.deps import current_user
from app.integrations.training_local.backend import LocalBackend
from app.main import app
from app.repositories.traces import TraceRepository
from app.routes import screens
from app.services import training
from tests.conftest import make_user
from tests.helpers.builders import held


@pytest.fixture
def api(session, storage, monkeypatch):
    app.dependency_overrides[get_session] = lambda: session
    monkeypatch.setattr(screens, "get_storage", lambda: storage)
    for lim in (screens.predict_limiter, screens.batch_limiter, screens.public_limiter):
        lim.reset()
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def trained(session, storage, chosen, provider):
    """A finished project with a real stored model (local backend, real verification on the locked rows)."""
    held(session, storage, chosen, provider)
    run = training.run_training(session, chosen, LocalBackend(), storage, provider)
    assert run.status == "done"
    return chosen


# ------------------------------------------------------------------ 1. history

def test_history_is_empty_but_well_formed_for_a_new_project(api, project):
    h = api.get(f"/projects/{project.id}/history").json()
    assert h == {"versions": [], "runs": [], "quotes": [], "payment": None, "payments": []}


def test_history_lists_versions_runs_quotes_payment_and_never_storage_keys(api, trained):
    h = api.get(f"/projects/{trained.id}/history").json()
    v = h["versions"][0]
    assert set(v) == {"id", "parent_id", "rows", "columns", "target_column", "source", "license", "notes", "created_at"}
    assert v["target_column"] == "left" and v["rows"] > 0
    r = h["runs"][0]
    assert set(r) == {"id", "status", "backend", "cost_cents", "started_at", "finished_at", "result", "round", "version_no",
                      "dataset_version_id"} and r["status"] == "done"
    assert r["round"] == 1 and r["version_no"] == 1
    assert set(r["result"]["verification"]) == {"value", "target", "passed"} and "accuracy" in r["result"]
    assert set(h["quotes"][0]) == {"id", "estimate_cents", "low_cents", "high_cents", "cap_cents", "approved", "created_at"}
    assert h["quotes"][0]["approved"] is True
    assert h["payment"]["state"] in ("released", "fee_captured", "fee_skipped") and "hold_cents" in h["payment"]
    text = json.dumps(h)
    assert "storage" not in text and "models/" not in text and "splits/" not in text


# ------------------------------------------------------------------ 2. the model

def test_model_is_unavailable_before_training(api, chosen):
    assert api.get(f"/projects/{chosen.id}/model").json() == {"available": False}
    assert api.post(f"/projects/{chosen.id}/predict", json={"record": {"tenure": 3}}).status_code == 404
    assert api.post(f"/projects/{chosen.id}/predict-batch", json={"csv_text": "a\n1\n"}).status_code == 404
    assert api.get(f"/projects/{chosen.id}/model/download").status_code == 404


def test_model_describes_columns_classes_and_versions(api, trained):
    m = api.get(f"/projects/{trained.id}/model").json()
    assert m["available"] and m["usable"] and m["target"] == "left"
    assert m["accuracy"] is not None and m["simple_guess_accuracy"] is not None and "estimate" in m["is_estimate_note"]
    assert m["sklearn_version"] and m["size_bytes"] > 100 and m["trained_at"]
    kinds = {c["name"]: c for c in m["columns"]}
    assert kinds and {c["kind"] for c in kinds.values()} <= {"number", "text"}
    assert "customer_id" not in kinds and "left" not in kinds  # the row label and the answer are not inputs
    assert m["classes"]
    for c in kinds.values():
        assert set(c) == {"name", "kind", "example", "choices"}
    text_cols = [c for c in kinds.values() if c["kind"] == "text"]
    assert text_cols and all(c["choices"] for c in text_cols)


def _a_record(api, pid):
    cols = api.get(f"/projects/{pid}/model").json()["columns"]
    return {c["name"]: c["example"] for c in cols if c["example"] is not None}


def test_predict_one_record_allows_missing_columns(api, trained):
    rec = _a_record(api, trained.id)
    full = api.post(f"/projects/{trained.id}/predict", json={"record": rec})
    assert full.status_code == 200
    body = full.json()
    assert body["prediction"] is not None and body["note"] == "an estimate, not a promise"
    assert abs(sum(body["probabilities"].values()) - 1) < 1e-3
    one = api.post(f"/projects/{trained.id}/predict", json={"record": {next(iter(rec)): rec[next(iter(rec))]}})
    assert one.status_code == 200 and one.json()["prediction"] is not None


def test_predict_rejects_junk_in_plain_words(api, trained):
    pid = trained.id
    cols = api.get(f"/projects/{pid}/model").json()["columns"]
    number = next(c["name"] for c in cols if c["kind"] == "number")
    r = api.post(f"/projects/{pid}/predict", json={"record": {number: "lots"}})
    assert r.status_code == 400 and number in r.json()["detail"] and "number" in r.json()["detail"]
    r = api.post(f"/projects/{pid}/predict", json={"record": {"not_a_column": 1}})
    assert r.status_code == 400 and "does not use" in r.json()["detail"]
    assert api.post(f"/projects/{pid}/predict", json={"record": {}}).status_code == 400
    assert api.post(f"/projects/{pid}/predict", json={"record": {number: ""}}).status_code == 400


def test_predict_batch_returns_preview_and_full_csv(api, trained):
    csv_text = "tenure,monthly_charges\n" + "\n".join(f"{i % 70},{50 + i % 40}" for i in range(30))
    cols = {c["name"] for c in api.get(f"/projects/{trained.id}/model").json()["columns"]}
    if not {"tenure", "monthly_charges"} <= cols:  # use whatever numeric columns the sample has
        num = [c["name"] for c in api.get(f"/projects/{trained.id}/model").json()["columns"] if c["kind"] == "number"][:2]
        csv_text = ",".join(num) + "\n" + "\n".join(f"{i % 70},{50 + i % 40}" for i in range(30))
    r = api.post(f"/projects/{trained.id}/predict-batch", json={"csv_text": csv_text})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["rows"] == 30 and len(b["preview"]) == 20 and "prediction" in b["columns"]
    assert b["csv_text"].splitlines()[0].split(",")[-2:] and len(b["csv_text"].strip().splitlines()) == 31
    assert all("prediction" in row for row in b["preview"])


def test_predict_batch_limits_and_bad_files(api, trained):
    pid = trained.id
    num = next(c["name"] for c in api.get(f"/projects/{pid}/model").json()["columns"] if c["kind"] == "number")
    many = f"{num}\n" + "\n".join("1" for _ in range(screens.model_use.MAX_BATCH_ROWS + 1))
    r = api.post(f"/projects/{pid}/predict-batch", json={"csv_text": many})
    assert r.status_code == 400 and "Too many rows" in r.json()["detail"]
    big = f"{num}\n" + "1\n" * (screens.model_use.MAX_BATCH_BYTES // 2 + 10)
    assert api.post(f"/projects/{pid}/predict-batch", json={"csv_text": big}).status_code == 400
    assert api.post(f"/projects/{pid}/predict-batch", json={"csv_text": "   "}).status_code == 400
    r = api.post(f"/projects/{pid}/predict-batch", json={"csv_text": "zzz,yyy\n1,2\n"})
    assert r.status_code == 400 and "match" in r.json()["detail"]
    r = api.post(f"/projects/{pid}/predict-batch", json={"csv_text": f"{num}\nabc\n"})
    assert r.status_code == 400 and "must be a number" in r.json()["detail"]


def test_predict_is_rate_limited(api, trained, monkeypatch):
    monkeypatch.setattr(screens, "batch_limiter", screens.RateLimiter(2, 60))
    num = next(c["name"] for c in api.get(f"/projects/{trained.id}/model").json()["columns"] if c["kind"] == "number")
    codes = [api.post(f"/projects/{trained.id}/predict-batch", json={"csv_text": f"{num}\n1\n"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_download_is_an_attachment_with_the_version_it_needs(api, trained):
    r = api.get(f"/projects/{trained.id}/model/download")
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["x-requires-scikit-learn"] and len(r.content) > 100
    import io, joblib
    assert hasattr(joblib.load(io.BytesIO(r.content)), "predict")


def test_a_model_that_cannot_be_loaded_gives_a_plain_message(api, session, storage, trained):
    from app.repositories import training_runs as runs_repo
    row = runs_repo.current_model(session, trained.id)
    storage.put(row.storage_key, b"not a model")
    m = api.get(f"/projects/{trained.id}/model").json()
    assert m["available"] and m["usable"] is False and "scikit-learn" in m["unusable_reason"] and m["columns"] == []
    r = api.post(f"/projects/{trained.id}/predict", json={"record": {"a": 1}})
    assert r.status_code == 409 and "scikit-learn" in r.json()["detail"] and "Traceback" not in r.text
    assert api.get(f"/projects/{trained.id}/model/download").status_code == 200  # the file can still be taken away


# ------------------------------------------------------------------ 3 and 4. account

def test_usage_and_receipts_count_only_my_projects(api, session, trained, user):
    u = api.get("/account/usage").json()
    assert set(u) == {"projects", "training_runs", "compute_charged_cents", "success_fees_cents", "released_cents",
                      "llm_tokens", "llm_cost_micros", "recent_activity"}
    assert u["projects"] == 1 and u["training_runs"] == 1
    assert u["compute_charged_cents"] + u["success_fees_cents"] + u["released_cents"] > 0
    assert 1 <= len(u["recent_activity"]) <= 20 and set(u["recent_activity"][0]) == {"when", "kind", "text"}
    rc = api.get("/account/payments").json()
    assert len(rc) == 1 and rc[0]["project_id"] == trained.id and rc[0]["goal"] == trained.goal
    assert set(rc[0]) == {"payment_id", "state", "hold_cents", "compute_captured_cents", "fee_captured_cents", "released_cents",
                          "total_charged_cents", "project_id", "goal", "created_at"}
    assert rc[0]["total_charged_cents"] == rc[0]["compute_captured_cents"] + rc[0]["fee_captured_cents"]

    other = make_user(session, "other@example.test")
    app.dependency_overrides[current_user] = lambda: other
    try:
        assert api.get("/account/payments").json() == []
        o = api.get("/account/usage").json()
        assert o["projects"] == 0 and o["training_runs"] == 0 and o["compute_charged_cents"] == 0 and o["recent_activity"] == []
    finally:
        app.dependency_overrides[current_user] = lambda: user


# ------------------------------------------------------------------ 5. sharing

PUBLIC_KEYS = {"goal", "status", "dataset", "baseline", "verification", "finished_at", "is_estimate_note", "version_no"}  # version_no added with model versions (deliberate)


def test_share_create_is_idempotent_and_public_view_is_exactly_the_safe_keys(api, session, trained):
    pid = trained.id
    assert api.get(f"/projects/{pid}/share").json() == {"enabled": False, "token": None, "created_at": None}
    a = api.post(f"/projects/{pid}/share").json()
    b = api.post(f"/projects/{pid}/share").json()
    assert a["token"] == b["token"] and len(a["token"]) >= 43 and a["url_path"] == f"/s/{a['token']}"
    st = api.get(f"/projects/{pid}/share").json()
    assert set(st) == {"enabled", "token", "created_at"} and st["enabled"] and st["token"] == a["token"] and st["created_at"]

    pub = api.get(f"/public/results/{a['token']}")
    assert pub.status_code == 200
    body = pub.json()
    assert set(body) == PUBLIC_KEYS
    assert set(body["dataset"]) == {"name", "rows", "target"} and set(body["baseline"]) == {"accuracy", "simple_guess_accuracy"}
    assert set(body["verification"]) == {"value", "target", "passed"} and body["finished_at"] and body["status"] == "done"
    text = pub.text
    from app.repositories import payments as payments_repo
    pay = payments_repo.latest_for_project(session, pid)
    for secret in (pid, pay.id, trained.user_id, trained.org_id, "example.test", "storage", "models/", "hold", "cents"):
        assert secret not in text, secret


def test_public_view_of_a_project_without_results_is_still_only_safe_keys(api, project):
    token = api.post(f"/projects/{project.id}/share").json()["token"]
    body = api.get(f"/public/results/{token}").json()
    assert set(body) == PUBLIC_KEYS and body["dataset"] is None and body["baseline"] is None and body["verification"] is None


def test_revoked_and_unknown_tokens_get_the_same_404(api, project):
    token = api.post(f"/projects/{project.id}/share").json()["token"]
    assert api.get(f"/public/results/{token}").status_code == 200
    assert api.delete(f"/projects/{project.id}/share").json() == {"enabled": False}
    assert api.delete(f"/projects/{project.id}/share").status_code == 200  # idempotent
    gone = api.get(f"/public/results/{token}")
    unknown = api.get("/public/results/" + "x" * 43)
    short = api.get("/public/results/abc")
    assert gone.status_code == unknown.status_code == short.status_code == 404
    assert gone.json() == unknown.json() == short.json() == {"detail": "result not found"}
    assert api.get(f"/projects/{project.id}/share").json()["enabled"] is False
    fresh = api.post(f"/projects/{project.id}/share").json()
    assert fresh["token"] != token and api.get(f"/public/results/{token}").status_code == 404


def test_public_route_is_rate_limited_per_ip(api, project, monkeypatch):
    monkeypatch.setattr(screens, "public_limiter", screens.RateLimiter(3, 60))
    codes = [api.get("/public/results/" + "y" * 43).status_code for _ in range(4)]
    assert codes == [404, 404, 404, 429]


def test_sharing_cannot_be_managed_by_another_user(api, session, project, user):
    token = api.post(f"/projects/{project.id}/share").json()["token"]
    other = make_user(session, "mallory@example.test")
    app.dependency_overrides[current_user] = lambda: other
    try:
        for method in ("get", "post", "delete"):
            assert getattr(api, method)(f"/projects/{project.id}/share").status_code == 404
        assert api.get(f"/public/results/{token}").status_code == 200  # still shared; Mallory changed nothing
    finally:
        app.dependency_overrides[current_user] = lambda: user


@pytest.mark.real_auth
def test_public_result_needs_no_login(session, project):
    from app.repositories import shares as shares_repo
    app.dependency_overrides[get_session] = lambda: session
    try:
        shares_repo.add(session, project.id, "t" * 43)
        r = TestClient(app).get("/public/results/" + "t" * 43)  # no cookie at all
        assert r.status_code == 200 and set(r.json()) == PUBLIC_KEYS
    finally:
        app.dependency_overrides.pop(get_session, None)


# ------------------------------------------------------------------ 6. activity

def test_activity_is_plain_language_built_from_the_trace(api, session, project):
    t = TraceRepository(session)
    t.add(project.id, "user", {"text": "predict loans with key sk-abcdefghijklmnopqrstuvwxyz123456"})
    t.add(project.id, "tool_call", {"name": "discover_datasets", "args": {"queries": ["loan default", "credit risk"]}})
    t.add(project.id, "tool_result", {"name": "discover_datasets", "result": {"candidates": [{"secret_row": "x" * 50}]}})
    t.add(project.id, "tool_call", {"name": "look_at_dataset", "args": {"dataset_id": "hf:foo"}})
    t.add(project.id, "tool_result", {"name": "look_at_dataset", "result": {"name": "Credit card default", "rows": 30000}})
    t.add(project.id, "gate", {"action": "select_dataset", "allowed": False, "reason": "needs user approval"})
    t.add(project.id, "gate", {"action": "select_dataset", "allowed": True})
    t.add(project.id, "tool_result", {"name": "run_readiness", "result": {"grade": "A", "findings": []}})
    t.add(project.id, "tool_result", {"name": "run_baseline", "result": {"accuracy": 0.874}})
    t.add(project.id, "tool_result", {"name": "create_quote", "result": {"quote_id": "q1"}})
    t.add(project.id, "tool_result", {"name": "fetch_dataset", "result": {"error": "Traceback: boom at /srv/app.py"}})
    t.add(project.id, "gate", {"action": "start_training", "allowed": False, "reason": "no server-confirmed hold for the current quote"})
    t.add(project.id, "tool_call", {"name": "load_skill", "args": {}})
    t.add(project.id, "tool_result", {"name": "load_skill", "result": {"playbook": "long text"}})
    feed = api.get(f"/projects/{project.id}/activity").json()
    texts = [f["text"] for f in feed]
    assert all(set(f) == {"when", "kind", "text"} for f in feed)
    assert "Searched open datasets for loan default, credit risk" in texts
    assert 'Looked at "Credit card default" (30,000 rows)' in texts
    assert "Waited for your approval" in texts and "Allowed to choose the dataset" in texts
    assert "Checked data readiness: grade A" in texts
    assert "Ran the free test: about 87 out of 100 right" in texts
    assert "Created a price estimate" in texts
    assert any(x.startswith("Held back a step (start training)") for x in texts)
    joined = " ".join(texts)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in joined and "Traceback" not in joined and "secret_row" not in joined
    assert "{" not in joined and "playbook" not in joined and not any("skill" in x.lower() for x in texts)
    assert texts.index("Searched open datasets for loan default, credit risk") < texts.index("Created a price estimate")


def test_activity_includes_steps_done_with_buttons_from_stored_rows(api, session, trained):
    """No agent trace at all here: every line comes from insight_reports, baseline_runs, forecasts, quotes, payments, runs."""
    feed = api.get(f"/projects/{trained.id}/activity").json()
    texts = [f["text"] for f in feed]
    assert all(set(f) == {"when", "kind", "text"} for f in feed)
    wanted = ["Checked data readiness: grade", "Ran the free test: about", "Forecast ready: about", "Price estimate ready",
              "You approved the price estimate", "Payment hold requested", "PayPal hold confirmed by the server",
              "Training started", "Training finished", "Released"]
    for w in wanted:
        assert any(t.startswith(w) for t in texts), (w, texts)
    # in the order the steps happen
    first = [next(i for i, t in enumerate(texts) if t.startswith(w)) for w in wanted[:9]]
    assert first == sorted(first), texts
    joined = " ".join(texts)
    for bad in ("{", "[", "storage", "models/", "splits/", "Traceback", "sk-", "ledger", "provider_", "PAYID"):
        assert bad not in joined, bad
    assert "estimate" in " ".join(t for t in texts if t.startswith("Price estimate ready")).lower()


def test_activity_does_not_repeat_a_step_that_is_in_both_the_trace_and_the_stored_rows(api, session, trained):
    t = TraceRepository(session)
    t.add(trained.id, "tool_result", {"name": "run_readiness", "result": {"grade": "A", "findings": []}})
    t.add(trained.id, "tool_result", {"name": "run_baseline", "result": {"accuracy": 0.8}})
    t.add(trained.id, "tool_result", {"name": "create_quote", "result": {"quote_id": "q"}})
    t.add(trained.id, "tool_result", {"name": "start_training", "result": {"run_id": "r"}})
    t.add(trained.id, "tool_result", {"name": "run_pilot", "result": {}})
    texts = [f["text"] for f in api.get(f"/projects/{trained.id}/activity").json()]
    for start in ("Checked data readiness", "Ran the free test", "Price estimate ready", "Training started", "Forecast ready"):
        assert sum(x.startswith(start) for x in texts) == 1, (start, texts)
    assert "Created a price estimate" not in texts and "Started training" not in texts


def test_activity_for_a_cancelled_hold_says_it_was_released_in_full(api, session, chosen, provider, storage):
    from app.services import payments
    q, pay = held(session, storage, chosen, provider)
    payments.cancel(session, provider, chosen)
    texts = [f["text"] for f in api.get(f"/projects/{chosen.id}/activity").json()]
    assert any(t.startswith("The hold was released in full") for t in texts), texts
    assert not any(t.startswith("Charged") for t in texts)


def test_activity_shows_exact_charges_and_a_skipped_fee(api, session, trained):
    from app.repositories import payments as payments_repo
    pay = payments_repo.latest_for_project(session, trained.id)
    payments_repo.save(session, pay, compute_captured_cents=52, fee_captured_cents=0, released_cents=4, state="fee_skipped")
    texts = [f["text"] for f in api.get(f"/projects/{trained.id}/activity").json()]
    assert "Charged $0.52 for the compute used" in texts
    assert "No success fee: the target was not verified" in texts
    assert "Released $0.04 of the hold; it was never charged" in texts

# ------------------------------------------------------------------ 6. model versions

from app.repositories import projects as projects_repo  # noqa: E402
from app.repositories import training_runs as runs_repo  # noqa: E402
from app.services import lifecycle, payments  # noqa: E402
from app.services.cost import quotes  # noqa: E402
from tests.helpers.builders import eligible_forecast, make_quote  # noqa: E402


def _new_paid_run(session, storage, project, provider):
    """New forecast, quote and hold on the same data, then a paid run (the project must be at baseline_done)."""
    # quotes.create_quote refuses a new quote after a settled hold (see the report), so the next quote is built directly
    fc = eligible_forecast(session, project)
    q = make_quote(session, project)
    q.forecast_id, q.breakdown = fc.id, {"target": 0.8}
    session.commit()
    lifecycle.transition(session, project, "quoted")
    quotes.approve_quote(session, project, q)
    pay, _ = payments.create_order(session, provider, "mock", project)
    assert payments.confirm_hold(session, provider, pay)
    return training.run_training(session, project, LocalBackend(), storage, provider)


def _stored(storage, session, pid):
    return {m.id: storage.get(m.storage_key) for m in runs_repo.models_for_project(session, pid)}


@pytest.fixture
def two_versions(session, storage, chosen, provider, verdict):
    """Round 1 missed its target (score 0.55), round 2 reached it (0.9). Both saved a real, loadable model."""
    verdict["value"] = 0.55
    held(session, storage, chosen, provider)
    assert training.run_training(session, chosen, LocalBackend(), storage, provider).status == "done"
    lifecycle.reopen_for_improvement(session, chosen)  # the Improve round
    verdict["value"] = 0.9
    assert _new_paid_run(session, storage, chosen, provider).status == "done"
    return chosen


def test_two_runs_make_two_versions_and_the_better_one_is_in_use(api, two_versions):
    v = api.get(f"/projects/{two_versions.id}/model/versions").json()
    assert [x["version_no"] for x in v] == [2, 1]  # newest first
    assert [x["is_current"] for x in v] == [True, False]
    assert set(v[0]) == {"model_id", "version_no", "created_at", "is_current", "accuracy", "simple_guess_accuracy", "verified_value",
                         "target", "passed", "dataset_version_id", "dataset_rows", "usable"}
    assert v[0]["passed"] is True and v[1]["passed"] is False and v[0]["verified_value"] == 0.9 and v[1]["verified_value"] == 0.55
    assert v[0]["dataset_version_id"] == v[1]["dataset_version_id"] and all(x["usable"] for x in v)
    assert "models/" not in json.dumps(v)
    m = api.get(f"/projects/{two_versions.id}/model").json()
    assert m["model_id"] == v[0]["model_id"] and m["version_no"] == 2 and m["is_current"] is True


def test_switching_the_version_changes_what_try_it_and_download_use(api, session, storage, two_versions):
    pid = two_versions.id
    v1, v2 = [x["model_id"] for x in reversed(api.get(f"/projects/{pid}/model/versions").json())]
    r = api.post(f"/projects/{pid}/model/{v1}/use")
    assert r.status_code == 200 and r.json() == {"model_id": v1, "version_no": 1, "is_current": True}
    assert api.get(f"/projects/{pid}/model").json()["model_id"] == v1
    assert [x["is_current"] for x in api.get(f"/projects/{pid}/model/versions").json()] == [False, True]
    stored = _stored(storage, session, pid)
    by_id = api.get(f"/projects/{pid}/model/download", params={"model_id": v2})
    default = api.get(f"/projects/{pid}/model/download")
    assert by_id.status_code == 200 and default.status_code == 200
    assert by_id.content == stored[v2] and default.content == stored[v1]
    rec = {c["name"]: c["example"] for c in api.get(f"/projects/{pid}/model").json()["columns"] if c["example"] is not None}
    assert api.post(f"/projects/{pid}/predict", params={"model_id": v2}, json={"record": rec}).status_code == 200
    assert api.get(f"/projects/{pid}/model", params={"model_id": v2}).json()["version_no"] == 2


def test_unknown_model_id_is_404_everywhere(api, trained):
    pid = trained.id
    assert api.post(f"/projects/{pid}/model/nope/use").status_code == 404
    assert api.get(f"/projects/{pid}/model/download", params={"model_id": "nope"}).status_code == 404
    assert api.get(f"/projects/{pid}/model", params={"model_id": "nope"}).status_code == 404
    assert api.post(f"/projects/{pid}/predict", params={"model_id": "nope"}, json={"record": {"a": 1}}).status_code == 404
    assert api.post(f"/projects/{pid}/predict-batch", params={"model_id": "nope"}, json={"csv_text": "a\n1\n"}).status_code == 404


def test_a_model_of_another_project_is_not_reachable_by_id(api, session, storage, trained, user):
    other = projects_repo.create(session, "other goal", user.id, user.org_id)
    storage.put("models/x.joblib", b"x")
    foreign = runs_repo.add_model(session, other.id, "run-x", "models/x.joblib", {})
    pid = trained.id
    assert api.post(f"/projects/{pid}/model/{foreign.id}/use").status_code == 404
    assert api.get(f"/projects/{pid}/model/download", params={"model_id": foreign.id}).status_code == 404


def test_other_user_gets_404_on_versions_and_use(api, session, two_versions, user):
    pid = two_versions.id
    mine = api.get(f"/projects/{pid}/model/versions").json()[0]["model_id"]
    other = make_user(session, "intruder@example.test")
    app.dependency_overrides[current_user] = lambda: other
    try:
        assert api.get(f"/projects/{pid}/model/versions").status_code == 404
        assert api.post(f"/projects/{pid}/model/{mine}/use").status_code == 404
        assert api.get(f"/projects/{pid}/model/download", params={"model_id": mine}).status_code == 404
    finally:
        app.dependency_overrides[current_user] = lambda: user
    assert api.get(f"/projects/{pid}/model/versions").status_code == 200


def test_a_worse_new_model_does_not_replace_the_better_one(api, session, storage, two_versions, provider, verdict):
    pid = two_versions.id
    verdict["value"] = 0.3  # round 3 does worse than the version in use
    projects_repo.set_status(session, two_versions, "baseline_done")  # a hit cannot be reopened by the Improve rule; move by hand
    assert _new_paid_run(session, storage, two_versions, provider).status == "done"
    v = api.get(f"/projects/{pid}/model/versions").json()
    assert [(x["version_no"], x["is_current"]) for x in v] == [(3, False), (2, True), (1, False)]


def test_history_lists_every_payment_and_labels_rounds(api, two_versions):
    h = api.get(f"/projects/{two_versions.id}/history").json()
    assert len(h["payments"]) == 2 and h["payment"]["payment_id"] == h["payments"][-1]["payment_id"]
    assert {"payment_id", "state", "hold_cents", "total_charged_cents", "quote_id", "created_at"} <= set(h["payments"][0])
    assert [(r["round"], r["version_no"]) for r in h["runs"]] == [(2, 2), (1, 1)]  # newest first
    assert all(r["dataset_version_id"] for r in h["runs"])


def test_share_shows_only_the_version_in_use_without_other_versions_or_cost(api, two_versions):
    pid = two_versions.id
    token = api.post(f"/projects/{pid}/share").json()["token"]
    pub = api.get(f"/public/results/{token}").json()
    assert set(pub) == PUBLIC_KEYS and pub["version_no"] == 2 and pub["verification"]["value"] == 0.9
    v1 = [x["model_id"] for x in api.get(f"/projects/{pid}/model/versions").json() if x["version_no"] == 1][0]
    api.post(f"/projects/{pid}/model/{v1}/use")
    pub = api.get(f"/public/results/{token}").json()
    assert pub["version_no"] == 1 and pub["verification"]["value"] == 0.55 and pub["verification"]["passed"] is False
    text = json.dumps(pub)
    assert "cents" not in text and "model_id" not in text and "payment" not in text


def test_model_of_an_all_numeric_dataset_is_described_and_usable(api, session, storage, project, provider):
    """Spambase-like data has no text columns: scikit-learn never fits the text group, and /model must still answer 200."""
    import numpy as np
    from app.services.data import datasets
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 1500)
    lines = ["f1,f2,f3,spam"] + [f"{a:.3f},{b:.3f},{c:.3f},{t}" for a, b, c, t in
                                  zip(rng.normal(size=1500) + y, rng.normal(size=1500), rng.normal(size=1500) - y, y)]
    c = datasets.add_candidate(session, storage, project, "numbers", "bundled", "\n".join(lines).encode())
    datasets.select_candidate(session, storage, project, c.id, "spam")
    held(session, storage, project, provider)
    assert training.run_training(session, project, LocalBackend(), storage, provider).status == "done"
    r = api.get(f"/projects/{project.id}/model")
    assert r.status_code == 200
    m = r.json()
    assert m["usable"] is True and {c["kind"] for c in m["columns"]} == {"number"}
    assert all(c["choices"] is None for c in m["columns"])
    assert api.post(f"/projects/{project.id}/predict", json={"record": {"f1": 1.0}}).status_code == 200

def test_activity_shows_a_finished_step_while_the_turn_is_still_running(api, session, project):
    """The chat polls /activity during a turn. The turn lock must not block it, and a step already saved must appear."""
    from app.services.agent import loop
    t = TraceRepository(session)
    t.add(project.id, "user", {"text": "predict loan default"})
    t.add(project.id, "tool_call", {"name": "discover_datasets", "args": {"queries": ["loan default"]}})
    t.add(project.id, "tool_result", {"name": "discover_datasets", "result": {"candidates": [{"id": "uci:1", "name": "Credit card default"}]}})
    t.add(project.id, "tool_call", {"name": "look_at_dataset", "args": {"dataset_id": "uci:1"}})  # still running, no result yet
    loop._acquire(project.id)  # the turn is running
    try:
        feed = api.get(f"/projects/{project.id}/activity")
    finally:
        loop._release(project.id)
    assert feed.status_code == 200
    texts = [f["text"] for f in feed.json()]
    assert 'Found 1 possible dataset: "Credit card default"' in texts
    assert "Looking at a dataset…" in texts
    assert "uci:" not in " ".join(texts)
