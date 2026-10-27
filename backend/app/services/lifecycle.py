"""Project state machine (specs/spec1.md section 5)."""
from ..db import Session
from ..db.tables import Project
from ..repositories import payments as payments_repo
from ..repositories import projects as projects_repo
from ..repositories import quotes as quotes_repo
from ..repositories import training_runs as runs_repo

ORDER = ["described", "data_chosen", "readiness_done", "baseline_done", "quoted",
         "awaiting_payment", "paid", "training", "done"]
SIDE_EXITS = {"failed", "stopped", "voided"}  # voided: our failure or a cancel; the hold was released


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
        quote = quotes_repo.latest_for_project(session, project.id)
        if quote is None or payments_repo.held_for_quote(session, project.id, quote.id) is None:
            raise BadTransition("paid requires a server-confirmed hold for the current quote")  # db.md integrity rule 1
    projects_repo.set_status(session, project, new)


def reopen_for_improvement(session: Session, project: Project) -> None:
    """Improve round: after a run that finished but MISSED its target, go back to the point where a new free
    pilot and a new quote can be made. The earlier hold is already released; a new quote needs a new hold."""
    run = runs_repo.latest_for_project(session, project.id)
    missed = run is not None and (run.result or {}).get("verification", {}).get("passed") is False
    if project.status != "done" or not missed:
        raise BadTransition(f"{project.status} -> baseline_done")
    projects_repo.set_status(session, project, "baseline_done")
