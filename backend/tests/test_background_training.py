"""Background training: start returns at once, progress, stop, crash recovery, settle idempotency, runners, database."""
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import build_engine, get_session
from app.deps import get_ctx_factory
from app.jobs.inline import InlineJobRunner
from app.models import LedgerEntry, TrainingRun
from app.providers.training.base import TrainingResult
from app.providers.training.local import LocalBackend
from app.repositories.ledger import LedgerRepository
from app.routes import projects as project_routes
from app.services import gate, payments, training
from app.services.agent.tools import ToolContext

from .test_payments_and_demo import ready_to_pay


class StoppableBackend:
    """Paid-looking backend. Calls `during(on_progress, should_stop)` mid-run, then ends as stopped or done."""
    name, instance_type = "scripted", "ml.m5.xlarge"

    def __init__(self, cost=30, during=None):
        self.cost, self.during, self.progress_seen = cost, during, []

    def run(self, path, target, cap, on_progress=None, should_stop=None):
        on_progress("training the model", 0.5)
        self.progress_seen.append("training the model")
        if self.during:
            self.during()
        if should_stop():
            return TrainingResult(0.0, 0.0, 1.0, self.cost, False, None, stopped=True)
        return TrainingResult(0.8, 0.7, 1.0, self.cost, False, b"model")


@pytest.fixture
def paid(session, storage, chosen, provider):
    q, pay = ready_to_pay(session, storage, chosen, provider)
    payments.confirm_capture(session, provider, pay)
    return q


def ledger_count(session, project):
    return session.scalar(select(func.count()).select_from(LedgerEntry).where(LedgerEntry.project_id == project.id))


def test_start_returns_a_running_run_and_does_not_train(session, chosen, paid):
    run = training.start_training(session, chosen, StoppableBackend())
    assert run.status == "running" and chosen.status == "training"
    assert run.result is None and run.cost_cents == 0  # nothing has executed yet


def test_start_still_needs_a_verified_payment(session, storage, chosen, provider):
    from app.providers.payments.mock import MockPaymentProvider
    prov = MockPaymentProvider(auto_confirm=False)
    _, pay = ready_to_pay(session, storage, chosen, prov)
    payments.confirm_capture(session, prov, pay)
    with pytest.raises(gate.GateDenied):
        training.start_training(session, chosen, StoppableBackend())
    assert session.scalar(select(func.count()).select_from(TrainingRun)) == 0


def test_api_train_returns_at_once_then_progress_and_stop(session, storage, chosen, provider, paid):
    queued = []

    class Recording:  # a runner that only records; the test plays the worker
        stale_after_seconds = 0
        enqueue = staticmethod(queued.append)
        is_active = staticmethod(lambda rid: False)

    backend = StoppableBackend()
    app = FastAPI()
    app.include_router(project_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[project_routes.get_runner] = lambda: Recording()
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", backend, None, set()))
    c = TestClient(app)

    r = c.post(f"/projects/{chosen.id}/train")
    assert r.status_code == 200 and r.json()["status"] == "running" and queued == [r.json()["run_id"]]
    assert chosen.status == "training"

    p = c.get(f"/projects/{chosen.id}/training").json()
    assert p["status"] == "running" and p["stage"] == "waiting to start" and p["elapsed_seconds"] >= 0
    assert p["cap_cents"] == paid.cap_cents and p["eta"]["is_estimate"] and p["spend_is_estimate"]
    assert p["eta"]["low_seconds"] <= p["eta"]["high_seconds"]

    assert c.post(f"/projects/{chosen.id}/training/stop").json()["stop_requested"] is True
    training.execute_run(session, queued[0], backend, storage, provider)  # the worker now runs and sees the flag
    done = c.get(f"/projects/{chosen.id}/training").json()
    assert done["status"] == "stopped" and chosen.status == "stopped"
    assert c.post(f"/projects/{chosen.id}/training/stop").status_code == 409  # nothing left to stop


def test_api_train_refused_without_payment(session, storage, chosen, provider):
    app = FastAPI()
    app.include_router(project_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    assert TestClient(app).post(f"/projects/{chosen.id}/train").status_code == 403


def test_enqueue_failure_refunds_everything(session, storage, chosen, provider, paid):
    class Broken:
        def enqueue(self, rid):
            raise RuntimeError("inngest unreachable")

    app = FastAPI()
    app.include_router(project_routes.router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[project_routes.get_runner] = lambda: Broken()
    app.dependency_overrides[get_ctx_factory] = lambda: (
        lambda p, approved=frozenset(): ToolContext(session, p, storage, provider, "mock", StoppableBackend(), None, set()))
    assert TestClient(app).post(f"/projects/{chosen.id}/train").status_code == 503
    assert chosen.status == "refunded" and provider.refunds[-1][1] == paid.cap_cents
    assert LedgerRepository(session).balance(chosen.id) == 0


def test_progress_is_reported_and_finishes(session, storage, chosen, provider, paid):
    seen = []
    run = training.start_training(session, chosen, backend := StoppableBackend(during=lambda: seen.append(training.progress(session, run))))
    training.execute_run(session, run.id, backend, storage, provider)
    assert seen[0]["stage"] == "training the model" and seen[0]["fraction"] == 0.5 and seen[0]["status"] == "running"
    assert seen[0]["spend_so_far_cents"] <= paid.cap_cents
    final = training.progress(session, run)
    assert final["status"] == "done" and final["fraction"] == 1.0 and final["eta"] is None and not final["spend_is_estimate"]


def test_stop_mid_run_refunds_unused_and_balance_never_negative(session, storage, chosen, provider, paid):
    run = training.start_training(session, chosen, backend := StoppableBackend(cost=30, during=lambda: training.request_stop(session, chosen)))
    training.execute_run(session, run.id, backend, storage, provider)
    assert run.status == "stopped" and chosen.status == "stopped" and run.cost_cents == 30
    assert provider.refunds == [(provider.refunds[0][0], paid.cap_cents - 30)]
    assert LedgerRepository(session).balance(chosen.id) == 0  # capture - usage - refund
    kinds = [e.kind for e in session.scalars(select(LedgerEntry).where(LedgerEntry.project_id == chosen.id).order_by(LedgerEntry.id))]
    assert kinds == ["capture", "usage", "refund"]


def test_stopped_cost_is_capped(session, storage, chosen, provider, paid):
    run = training.start_training(session, chosen, backend := StoppableBackend(cost=99_999, during=lambda: training.request_stop(session, chosen)))
    training.execute_run(session, run.id, backend, storage, provider)
    assert run.cost_cents == paid.cap_cents and provider.refunds == []
    assert LedgerRepository(session).balance(chosen.id) == 0


def test_stopping_a_finished_run_is_refused(session, storage, chosen, provider, paid):
    training.run_training(session, chosen, StoppableBackend(), storage, provider)
    with pytest.raises(training.NoActiveRun):
        training.request_stop(session, chosen)


def test_settling_a_stopped_run_twice_changes_nothing(session, storage, chosen, provider, paid):
    run = training.start_training(session, chosen, backend := StoppableBackend(cost=30, during=lambda: training.request_stop(session, chosen)))
    training.execute_run(session, run.id, backend, storage, provider)
    n_entries, n_refunds, spent = ledger_count(session, chosen), len(provider.refunds), None
    from app.repositories.budget import BudgetRepository
    spent = BudgetRepository(session).spent()
    payments.settle(session, provider, chosen, run)           # settle again
    training.execute_run(session, run.id, backend, storage, provider)  # duplicate job delivery
    assert training.fail_run(session, provider, run, "late") is False  # cannot overwrite a finished run
    assert run.status == "stopped" and run.cost_cents == 30
    assert ledger_count(session, chosen) == n_entries and len(provider.refunds) == n_refunds == 1
    assert BudgetRepository(session).spent() == spent


def test_crash_recovery_fails_and_fully_refunds(session, chosen, provider, paid):
    run = training.start_training(session, chosen, StoppableBackend())
    run.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.commit()
    assert training.recover_stale_runs(session, provider, lambda rid: False, 300) == [run.id]
    assert run.status == "failed" and chosen.status == "refunded"
    assert provider.refunds[-1][1] == paid.cap_cents and LedgerRepository(session).balance(chosen.id) == 0
    assert training.recover_stale_runs(session, provider, lambda rid: False, 300) == []  # repeat is harmless
    assert len(provider.refunds) == 1


def test_recovery_leaves_live_and_fresh_runs_alone(session, chosen, provider, paid):
    run = training.start_training(session, chosen, StoppableBackend())
    assert training.recover_stale_runs(session, provider, lambda rid: False, 300) == []  # fresh heartbeat
    run.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    session.commit()
    assert training.recover_stale_runs(session, provider, lambda rid: True, 300) == []  # worker still alive
    assert run.status == "running" and provider.refunds == []


def test_backend_error_still_refunds_in_full(session, storage, chosen, provider, paid):
    class Boom(StoppableBackend):
        def run(self, *a, **k):
            raise RuntimeError("boom")

    run = training.run_training(session, chosen, Boom(), storage, provider)
    assert run.status == "failed" and chosen.status == "refunded" and provider.refunds[-1][1] == paid.cap_cents


def test_local_backend_reports_stages_and_honours_stop(tmp_path, storage, session, chosen):
    from app.models import DatasetVersion
    v = session.get(DatasetVersion, chosen.chosen_dataset_version_id)
    stages = []
    res = LocalBackend().run(storage.path(v.storage_key), v.target_column, 100, on_progress=lambda s, f: stages.append((s, f)))
    assert [s for s, _ in stages] == ["preparing the data", "training the model", "saving the model"]
    assert [f for _, f in stages] == sorted(f for _, f in stages) and not res.stopped and res.model_bytes
    stopped = LocalBackend().run(storage.path(v.storage_key), v.target_column, 100, should_stop=lambda: True)
    assert stopped.stopped and stopped.cost_cents == 0 and stopped.model_bytes is None
    LocalBackend().run(storage.path(v.storage_key), v.target_column, 100)  # callbacks are optional


def test_inline_runner_threaded_runs_in_background():
    started, release = threading.Event(), threading.Event()

    def work(rid):
        started.set()
        release.wait(5)

    r = InlineJobRunner(work, threaded=True)
    r.enqueue("run1")
    assert started.wait(5) and r.is_active("run1")  # enqueue returned while the job is still running
    release.set()
    for _ in range(100):
        if not r.is_active("run1"):
            break
        threading.Event().wait(0.02)
    assert not r.is_active("run1")


def test_inline_runner_sync_runs_before_returning():
    calls = []
    r = InlineJobRunner(calls.append)
    r.enqueue("a")
    assert calls == ["a"] and not r.is_active("a")


def test_inngest_runner_sends_one_event_per_run():
    pytest.importorskip("inngest")
    from app.jobs.inngest_runner import EVENT_NAME, InngestJobRunner

    class FakeClient:
        sent = []
        def send_sync(self, ev):
            self.sent.append(ev)

    c = FakeClient()
    InngestJobRunner(c).enqueue("r1")
    ev = c.sent[0]
    assert ev.name == EVENT_NAME and ev.data == {"run_id": "r1"} and ev.id == "train-r1"
    assert InngestJobRunner(c).is_active("r1") is False


def test_inngest_function_is_served_by_fastapi():
    inngest = pytest.importorskip("inngest")
    from app.jobs.inngest_runner import InngestJobRunner

    client = inngest.Inngest(app_id="aioac-test", is_production=False)  # dev mode: no keys, no network at import
    app = FastAPI()
    InngestJobRunner(client).serve(app, execute=lambda rid: None)
    assert any(getattr(r, "path", "") == "/api/inngest" for r in app.routes)


def test_database_url_handling():
    pytest.importorskip("psycopg")
    sqlite = build_engine("sqlite:///./x.db")
    assert sqlite.url.get_backend_name() == "sqlite"
    direct = build_engine("postgresql://u:p@db.example.supabase.co:5432/postgres")
    assert direct.url.drivername == "postgresql+psycopg" and direct.pool.__class__.__name__ != "NullPool"
    pooled = build_engine("postgres://u.proj:p@aws-0-eu.pooler.supabase.com:6543/postgres?sslmode=require")
    assert pooled.url.drivername == "postgresql+psycopg" and pooled.pool.__class__.__name__ == "NullPool"
    assert build_engine("postgresql://u:p@h:6543/postgres", pooled=False).pool.__class__.__name__ != "NullPool"


def test_no_sqlite_only_column_types():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    from app.db import Base
    for table in Base.metadata.sorted_tables:  # compiles every table for Postgres without connecting
        CreateTable(table).compile(dialect=postgresql.dialect())
