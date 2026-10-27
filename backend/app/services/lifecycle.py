"""Project state machine (specs/spec1.md section 5)."""
from ..db import Session
from ..db.tables import Project
from ..repositories import payments as payments_repo
from ..repositories import projects as projects_repo

ORDER = ["described", "data_chosen", "readiness_done", "baseline_done", "quoted",
         "awaiting_payment", "paid", "training", "done"]
SIDE_EXITS = {"failed", "stopped", "refunded"}


class BadTransition(Exception):
    pass


def transition(session: Session, project: Project, new: str) -> None:
    cur = project.status
    if new == "refunded":
        ok = cur in {"failed", "stopped", "done"}
    elif new in SIDE_EXITS:
        ok = cur in ORDER and cur != "done"
    elif new in ORDER and cur in ORDER:
        ok = ORDER.index(new) == ORDER.index(cur) + 1 or (new == "quoted" and cur in {"quoted", "awaiting_payment"})
    else:
        ok = False
    if not ok:
        raise BadTransition(f"{cur} -> {new}")
    if new == "paid":
        verified = payments_repo.verified_for_project(session, project.id)
        if verified is None:
            raise BadTransition("paid requires a verified payment")  # db.md integrity rule 1
    projects_repo.set_status(session, project, new)
