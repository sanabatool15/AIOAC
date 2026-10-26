"""Training as a background job: start, run, progress, stop, crash recovery.

HUMAN REVIEW REQUIRED: this code decides when a paid run starts and how it is settled.

Flow (specs/training.md section 7):
  start_training  runs the gate, moves the project to `training`, creates the run (`running`). The caller then
                  hands the run id to a JobRunner (app/jobs). Nothing paid runs inside the HTTP request.
  execute_run     the job body. Runs the backend, then settles through payments.settle (usage + refund).
  request_stop    sets a flag; the backend sees it through should_stop().
  recover_stale_runs  at API start: runs left `running` with no live worker are failed and fully refunded.

Every ending goes through _claim(): one UPDATE that only succeeds while the run is still `running`. So a run is
finished exactly once, even if a duplicate job delivery or recovery races with the live worker. payments.settle is
also idempotent per run id (ledger keys `usage:<run>` and `refund:<run>`).
"""
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import DatasetVersion, Model, Project, TrainingRun
from ..providers.payments.base import PaymentProvider, ProviderError
from ..providers.storage.base import Storage
from ..providers.training.base import TrainingBackend
from ..repositories.budget import BudgetRepository
from ..repositories.traces import TraceRepository
from . import gate, lifecycle, payments
from .prices import INSTANCES, PLATFORM_FEE_CENTS, STORAGE_CENTS


class NoActiveRun(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes


def start_training(session: Session, project: Project, backend: TrainingBackend) -> TrainingRun:
    """Gate check, status -> training, create the run. Returns at once; the work happens in execute_run."""
    gate.authorize(session, project, gate.Action.START_TRAINING)  # raises GateDenied unless payment is server-verified
    lifecycle.transition(session, project, "training")
    run = TrainingRun(project_id=project.id, backend=backend.name, instance_type=backend.instance_type,
                      progress_stage="waiting to start", started_at=_now(), updated_at=_now())
    session.add(run)
    session.commit()
    return run


def active_run(session: Session, project_id: str) -> TrainingRun | None:
    return session.scalar(select(TrainingRun).where(TrainingRun.project_id == project_id)
                          .order_by(TrainingRun.started_at.desc()))


def _claim_start(session: Session, run: TrainingRun) -> bool:
    """Take the right to start the backend, exactly once per run. True only for the first caller.
    A worker that dies after claiming leaves a silent `running` run; crash recovery fails and refunds it,
    and the job is never started a second time."""
    res = session.execute(update(TrainingRun).where(TrainingRun.id == run.id, TrainingRun.status == "running",
                                                    TrainingRun.claimed_at.is_(None))
                          .values(claimed_at=_now(), updated_at=_now()))
    session.commit()
    session.refresh(run)
    return res.rowcount == 1


def _claim(session: Session, run: TrainingRun, **values) -> bool:
    """Finish the run exactly once. True only for the caller that moved it out of `running`."""
    res = session.execute(update(TrainingRun).where(TrainingRun.id == run.id, TrainingRun.status == "running")
                          .values(finished_at=_now(), updated_at=_now(), **values))
    session.commit()
    session.refresh(run)
    return res.rowcount == 1


def _settle(session: Session, provider: PaymentProvider, project: Project, run: TrainingRun) -> bool:
    """Usage + refund. If PayPal fails the ledger keeps the owed amount, a `refund_failed` trace step records it,
    and the refund can be retried (retry_refund). Returns whether settlement completed."""
    try:
        payments.settle(session, provider, project, run)
        return True
    except ProviderError as exc:
        session.rollback()
        TraceRepository(session).add(project.id, "refund_failed", {"run_id": run.id, "error": type(exc).__name__})
        return False


def fail_run(session: Session, provider: PaymentProvider, run: TrainingRun, error: str) -> bool:
    """The user gets everything back: cost 0, refund the whole capture. False if the run had already ended."""
    if not _claim(session, run, status="failed", cost_cents=0, result={"error": error}):
        return False
    project = session.get(Project, run.project_id)
    if project.status == "training":
        lifecycle.transition(session, project, "failed")
    if _settle(session, provider, project, run) and project.status == "failed":
        lifecycle.transition(session, project, "refunded")  # only once the money is really back
    return True


def execute_run(session: Session, run_id: str, backend: TrainingBackend, storage: Storage,
                provider: PaymentProvider) -> TrainingRun | None:
    """The job body. Safe to call twice for the same run: the second call does nothing."""
    run = session.get(TrainingRun, run_id)
    if run is None or run.status != "running":
        return run
    if not _claim_start(session, run):
        return run   # another delivery of the same task already owns this run; never start the backend twice
    project = session.get(Project, run.project_id)
    quote = gate.latest_quote(session, project.id)
    version = session.get(DatasetVersion, project.chosen_dataset_version_id)

    def on_progress(stage: str, fraction: float) -> None:
        run.progress_stage = stage
        run.progress_fraction = max(0.0, min(1.0, fraction))
        run.updated_at = _now()
        session.commit()

    def should_stop() -> bool:
        session.refresh(run, ["stop_requested"])
        run.updated_at = _now()  # heartbeat
        session.commit()
        return bool(run.stop_requested)

    try:
        res = backend.run(storage.path(version.storage_key), version.target_column, quote.cap_cents,
                          on_progress=on_progress, should_stop=should_stop, job_key=run.id)
    except Exception as exc:
        session.rollback()
        fail_run(session, provider, run, type(exc).__name__)
        return run

    cost = max(0, min(res.cost_cents, quote.cap_cents))  # never above the cap
    if res.stopped:
        if _claim(session, run, status="stopped", cost_cents=cost, progress_stage="stopped",
                  result={"stopped_by_user": True}):
            BudgetRepository(session).add_spend(cost)
            lifecycle.transition(session, project, "stopped")
            _settle(session, provider, project, run)
        return run

    result = {"accuracy": res.accuracy, "simple_guess_accuracy": res.simple_guess_accuracy,
              "runtime_seconds": res.runtime_seconds}
    if not _claim(session, run, status="done", cost_cents=cost, progress_stage="finished", progress_fraction=1.0,
                  stopped_at_cap=res.stopped_at_cap or res.cost_cents >= quote.cap_cents, result=result):
        return run
    if res.model_bytes:
        key = f"models/{project.id}/{run.id}.joblib"
        storage.put(key, res.model_bytes)
        session.add(Model(project_id=project.id, training_run_id=run.id, storage_key=key, quality=result))
        session.commit()
    BudgetRepository(session).add_spend(cost)
    _settle(session, provider, project, run)
    lifecycle.transition(session, project, "done")
    return run


def request_stop(session: Session, project: Project) -> TrainingRun:
    run = active_run(session, project.id)
    if run is None or run.status != "running":
        raise NoActiveRun("there is no training running for this project")
    run.stop_requested = True
    run.progress_stage = "stopping"
    session.commit()
    return run


def _quoted_seconds(cents: float, instance_type: str | None) -> float | None:
    spec = INSTANCES.get(instance_type or "")
    if spec is None:
        return None
    compute = cents - STORAGE_CENTS - PLATFORM_FEE_CENTS
    return max(0.0, compute / spec.hourly_cents * 3600)


def progress(session: Session, run: TrainingRun) -> dict:
    """Plain-language progress. Spend and ETA are estimates based on elapsed time against the quote."""
    quote = gate.latest_quote(session, run.project_id)
    end = _aware(run.finished_at) if run.finished_at else _now()
    elapsed = max(0.0, (end - _aware(run.started_at)).total_seconds())
    spec = INSTANCES.get(run.instance_type or "")
    if run.status == "running":
        spend = min(quote.cap_cents, math.ceil(elapsed / 3600 * spec.hourly_cents)) if spec else 0
    else:
        spend = run.cost_cents
    eta = None
    if run.status == "running" and quote is not None:
        lo = _quoted_seconds(quote.low_cents, run.instance_type)
        hi = _quoted_seconds(quote.high_cents, run.instance_type)
        if lo is not None and hi is not None:
            eta = {"low_seconds": max(0, round(lo - elapsed)), "high_seconds": max(0, round(hi - elapsed)), "is_estimate": True}
    return {"run_id": run.id, "status": run.status, "stage": run.progress_stage,
            "fraction": run.progress_fraction, "elapsed_seconds": round(elapsed),
            "spend_so_far_cents": spend, "spend_is_estimate": run.status == "running",
            "cap_cents": quote.cap_cents if quote else None, "eta": eta,
            "stop_requested": run.stop_requested, "result": run.result}


def recover_stale_runs(session: Session, provider: PaymentProvider, is_active, stale_after_seconds: int) -> list[str]:
    """Run at API start. A `running` run is dead when no worker holds it and it has had no heartbeat for
    `stale_after_seconds`. Dead runs are failed and refunded in full through the normal settle path."""
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    recovered = []
    for run in list(session.scalars(select(TrainingRun).where(TrainingRun.status == "running"))):
        if is_active(run.id) or _aware(run.updated_at) > cutoff:
            continue
        if fail_run(session, provider, run, "interrupted"):
            recovered.append(run.id)
    return recovered


def run_training(session: Session, project: Project, backend: TrainingBackend, storage: Storage,
                 provider: PaymentProvider) -> TrainingRun:
    """Blocking version: start and run in the caller's thread. Kept for callers that wait for the result
    (the agent's start_training tool and the demo check). The HTTP route uses start_training + a JobRunner."""
    run = start_training(session, project, backend)
    return execute_run(session, run.id, backend, storage, provider)


def retry_refund(session: Session, provider: PaymentProvider, project: Project) -> int:
    """Re-run settlement for the latest finished run. Safe to repeat: usage and refund are keyed per run."""
    run = session.scalar(select(TrainingRun).where(TrainingRun.project_id == project.id,
                                                    TrainingRun.status.in_(("done", "failed", "stopped")))
                         .order_by(TrainingRun.created_at.desc()))
    if run is None:
        raise payments.PaymentError("no finished training run to settle")
    refunded = payments.settle(session, provider, project, run)
    if project.status == "failed":
        lifecycle.transition(session, project, "refunded")
    return refunded
