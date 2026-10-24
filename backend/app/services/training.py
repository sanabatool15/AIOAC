"""Runs a paid training job after the gate allows it, enforces the cap, then settles and refunds."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import DatasetVersion, Model, Project, TrainingRun
from ..providers.payments.base import PaymentProvider, ProviderError
from ..providers.storage.base import Storage
from ..providers.training.base import TrainingBackend
from ..repositories.budget import BudgetRepository
from ..repositories.traces import TraceRepository
from . import gate, lifecycle, payments


def run_training(session: Session, project: Project, backend: TrainingBackend, storage: Storage,
                 provider: PaymentProvider) -> TrainingRun:
    quote = gate.authorize(session, project, gate.Action.START_TRAINING)
    version = session.get(DatasetVersion, project.chosen_dataset_version_id)
    lifecycle.transition(session, project, "training")
    run = TrainingRun(project_id=project.id, backend=backend.name, instance_type=backend.instance_type)
    session.add(run)
    session.commit()
    try:
        res = backend.run(storage.path(version.storage_key), version.target_column, quote.cap_cents)
    except Exception as exc:  # the user gets everything back if the job fails
        run.status, run.cost_cents, run.result = "failed", 0, {"error": type(exc).__name__}
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        lifecycle.transition(session, project, "failed")
        if _settle_or_flag(session, provider, project, run):
            lifecycle.transition(session, project, "refunded")
        return run

    cost = min(res.cost_cents, quote.cap_cents)  # never above the cap
    run.cost_cents = cost
    run.stopped_at_cap = res.stopped_at_cap or res.cost_cents >= quote.cap_cents
    run.status = "done"
    run.result = {"accuracy": res.accuracy, "simple_guess_accuracy": res.simple_guess_accuracy,
                  "runtime_seconds": res.runtime_seconds}
    run.finished_at = datetime.now(timezone.utc)
    session.commit()
    if res.model_bytes:
        key = f"models/{project.id}/{run.id}.joblib"
        storage.put(key, res.model_bytes)
        session.add(Model(project_id=project.id, training_run_id=run.id, storage_key=key, quality=run.result))
        session.commit()
    BudgetRepository(session).add_spend(cost)
    _settle_or_flag(session, provider, project, run)  # the job finished either way
    lifecycle.transition(session, project, "done")
    return run


def _settle_or_flag(session: Session, provider: PaymentProvider, project: Project, run: TrainingRun) -> bool:
    """Settle and refund. If PayPal fails, record it so the refund can be retried; never lose track of owed money."""
    try:
        payments.settle(session, provider, project, run)
        return True
    except ProviderError as exc:
        session.rollback()
        TraceRepository(session).add(project.id, "refund_failed", {"run_id": run.id, "error": type(exc).__name__})
        return False


def retry_refund(session: Session, provider: PaymentProvider, project: Project) -> int:
    """Re-run settlement for the latest finished run. Safe to repeat: usage and refund are keyed per run."""
    run = session.scalar(select(TrainingRun).where(TrainingRun.project_id == project.id,
                                                    TrainingRun.status.in_(("done", "failed")))
                         .order_by(TrainingRun.created_at.desc()))
    if run is None:
        raise payments.PaymentError("no finished training run to settle")
    refunded = payments.settle(session, provider, project, run)
    if project.status == "failed":
        lifecycle.transition(session, project, "refunded")
    return refunded
