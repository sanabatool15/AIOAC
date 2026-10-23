"""Runs a paid training job after the gate allows it, enforces the cap, then settles and refunds."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import DatasetVersion, Model, Project, TrainingRun
from ..providers.payments.base import PaymentProvider
from ..providers.storage.base import Storage
from ..providers.training.base import TrainingBackend
from ..repositories.budget import BudgetRepository
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
        payments.settle(session, provider, project, run)
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
    payments.settle(session, provider, project, run)
    lifecycle.transition(session, project, "done")
    return run
