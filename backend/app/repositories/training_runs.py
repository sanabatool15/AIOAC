from datetime import datetime, timezone

from sqlalchemy import select, update

from ..db import Session
from ..db.tables import Model, TrainingRun


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get(session: Session, run_id: str) -> TrainingRun | None:
    return session.get(TrainingRun, run_id)


def create(session: Session, project_id: str, backend: str, instance_type: str | None,
           progress_stage: str, now: datetime) -> TrainingRun:
    run = TrainingRun(project_id=project_id, backend=backend, instance_type=instance_type,
                      progress_stage=progress_stage, started_at=now, updated_at=now)
    session.add(run)
    session.commit()
    return run


def latest_for_project(session: Session, project_id: str) -> TrainingRun | None:
    return session.scalar(select(TrainingRun).where(TrainingRun.project_id == project_id)
                          .order_by(TrainingRun.started_at.desc()))


def latest_finished(session: Session, project_id: str) -> TrainingRun | None:
    return session.scalar(select(TrainingRun).where(TrainingRun.project_id == project_id,
                                                    TrainingRun.status.in_(("done", "failed", "stopped")))
                          .order_by(TrainingRun.created_at.desc()))


def running(session: Session) -> list[TrainingRun]:
    return list(session.scalars(select(TrainingRun).where(TrainingRun.status == "running")))


def claim_start(session: Session, run: TrainingRun) -> bool:
    """Take the right to start the backend, exactly once per run. True only for the first caller.
    A worker that dies after claiming leaves a silent `running` run; crash recovery fails and refunds it,
    and the job is never started a second time."""
    res = session.execute(update(TrainingRun).where(TrainingRun.id == run.id, TrainingRun.status == "running",
                                                    TrainingRun.claimed_at.is_(None))
                          .values(claimed_at=_now(), updated_at=_now()))
    session.commit()
    session.refresh(run)
    return res.rowcount == 1


def finish_if_running(session: Session, run: TrainingRun, **values) -> bool:
    """Finish the run exactly once. True only for the caller that moved it out of `running`."""
    res = session.execute(update(TrainingRun).where(TrainingRun.id == run.id, TrainingRun.status == "running")
                          .values(finished_at=_now(), updated_at=_now(), **values))
    session.commit()
    session.refresh(run)
    return res.rowcount == 1


def set_progress(session: Session, run: TrainingRun, stage: str, fraction: float) -> None:
    run.progress_stage = stage
    run.progress_fraction = max(0.0, min(1.0, fraction))
    run.updated_at = _now()
    session.commit()


def heartbeat_and_stop_requested(session: Session, run: TrainingRun) -> bool:
    session.refresh(run, ["stop_requested"])
    run.updated_at = _now()  # heartbeat
    session.commit()
    return bool(run.stop_requested)


def mark_stop_requested(session: Session, run: TrainingRun) -> None:
    run.stop_requested = True
    run.progress_stage = "stopping"
    session.commit()


def add_model(session: Session, project_id: str, run_id: str, storage_key: str, quality: dict) -> None:
    session.add(Model(project_id=project_id, training_run_id=run_id, storage_key=storage_key, quality=quality))
    session.commit()
