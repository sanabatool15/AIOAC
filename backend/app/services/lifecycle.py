"""Project state machine (specs/spec1.md section 5)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Payment, Project, Quote, TrainingRun

ORDER = ["described", "data_chosen", "readiness_done", "baseline_done", "quoted",
         "awaiting_payment", "paid", "training", "done"]
SIDE_EXITS = {"failed", "stopped", "voided"}  # voided: our failure or a cancel; nothing was charged


class BadTransition(Exception):
    pass


def transition(session: Session, project: Project, new: str) -> None:
    cur = project.status
    if new == "voided":
        ok = cur in {"failed", "stopped"}
    elif new in SIDE_EXITS:
        ok = cur in ORDER and cur != "done"
    elif new in ORDER and cur in ORDER:
        ok = ORDER.index(new) == ORDER.index(cur) + 1 or (new == "quoted" and cur in {"quoted", "awaiting_payment"})
    else:
        ok = False
    if not ok:
        raise BadTransition(f"{cur} -> {new}")
    if new == "paid":
        quote = session.scalar(select(Quote).where(Quote.project_id == project.id).order_by(Quote.created_at.desc()))
        held = quote and session.scalar(select(Payment).where(Payment.quote_id == quote.id, Payment.verified.is_(True),
                                                              Payment.state == "held"))
        if held is None:
            raise BadTransition("paid requires a server-confirmed hold for the current quote")  # db.md integrity rule 1
    project.status = new
    session.commit()


def reopen_for_improvement(session: Session, project: Project) -> None:
    """Improve round (screen 29): after a run that finished but MISSED its target, go back to the point where a new
    free pilot and a new quote can be made. The earlier hold is already released; a new quote needs a new hold."""
    run = session.scalar(select(TrainingRun).where(TrainingRun.project_id == project.id).order_by(TrainingRun.started_at.desc()))
    missed = run is not None and (run.result or {}).get("verification", {}).get("passed") is False
    if project.status != "done" or not missed:
        raise BadTransition(f"{project.status} -> baseline_done")
    project.status = "baseline_done"
    session.commit()
