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


class TargetNotHigher(BadTransition):
    """A new round after a HIT needs a strictly higher target. The message is plain words for the user."""


def _out_of_100(rate: float) -> int:
    return round(rate * 100)


def reopen_for_improvement(session: Session, project: Project, new_target: float | None = None) -> None:
    """New round after a finished run: go back to the point where a new free pilot and a new quote can be made.
    - Target MISSED: always allowed (the Improve round).
    - Target REACHED: allowed only with a strictly higher `new_target` ("Try a higher target").
    Nothing is deleted: the dataset version, earlier model, payment record and history stay. The earlier hold is already
    settled; a new quote needs a new hold, and a new training makes a new model version."""
    run = runs_repo.latest_for_project(session, project.id)
    verdict = (run.result or {}).get("verification", {}) if run is not None else {}
    if project.status != "done" or run is None or verdict.get("passed") is None:
        raise BadTransition(f"{project.status} -> baseline_done")
    if verdict["passed"] is True:
        reached = verdict.get("target")
        if new_target is None or reached is None or _out_of_100(new_target) <= _out_of_100(reached):
            raise TargetNotHigher(
                f"the finished run already reached {_out_of_100(reached or 0)} out of 100; "
                f"the new target must be higher than that" + (f" (you asked for {_out_of_100(new_target)})" if new_target is not None else ""))
    projects_repo.set_status(session, project, "baseline_done")


def reopen_for_new_data(session: Session, project: Project) -> None:
    """A guided data fix made a new dataset version. Go back to `data_chosen` so the readiness check and the free test
    run again on the new data (both free). Only before a price is paid for: from baseline_done or quoted."""
    if project.status not in {"baseline_done", "quoted"}:
        raise BadTransition(f"{project.status} -> data_chosen")
    projects_repo.set_status(session, project, "data_chosen")
