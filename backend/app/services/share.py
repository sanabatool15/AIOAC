"""Public read-only result links. HUMAN REVIEW: this is the only code that builds data for people who are not signed in.

The public view is built from an explicit allow-list of fields. It never carries money, payment ids, emails, user or
organization ids, storage keys or traces.
"""
import secrets
from datetime import datetime, timezone

from ..db import Session
from ..db.tables import Project
from ..repositories import datasets as datasets_repo
from ..repositories import projects as projects_repo
from ..repositories import shares as shares_repo
from ..repositories import training_runs as runs_repo

TOKEN_BYTES = 32  # secrets.token_urlsafe(32) is 43 characters from 32 random bytes
NOTE = "These numbers are estimates from held-back test rows, not a promise about future results."


def _view(share) -> dict:
    return {"enabled": True, "token": share.token, "url_path": f"/s/{share.token}", "created_at": share.created_at}


def create(session: Session, project: Project) -> dict:
    """Idempotent: returns the active share if there is one."""
    share = shares_repo.active_for_project(session, project.id) or shares_repo.add(session, project.id, secrets.token_urlsafe(TOKEN_BYTES))
    return _view(share)


def status(session: Session, project: Project) -> dict:
    share = shares_repo.active_for_project(session, project.id)
    return _view(share) if share else {"enabled": False, "token": None, "created_at": None}


def revoke(session: Session, project: Project) -> None:
    shares_repo.revoke_all(session, project.id, datetime.now(timezone.utc))


def public_result(session: Session, token: str) -> dict | None:
    """None for an unknown or revoked token (the route answers one 404 body for both)."""
    share = shares_repo.active_by_token(session, token)
    if share is None:
        return None
    project = projects_repo.get(session, share.project_id)
    if project is None:
        return None
    version = datasets_repo.get_version(session, project.chosen_dataset_version_id) if project.chosen_dataset_version_id else None
    cand = datasets_repo.chosen_candidate(session, project.id)
    base = project.baseline_result or {}
    run = runs_repo.latest_finished(session, project.id)
    verification = None
    if run is not None and run.status == "done" and run.result and run.result.get("verification"):
        v = run.result["verification"]
        verification = {"value": v.get("value"), "target": v.get("target"), "passed": v.get("passed")}
    return {"goal": project.goal, "status": project.status,
            "dataset": version and {"name": cand.name if cand else None, "rows": version.rows, "target": version.target_column},
            "baseline": {"accuracy": base.get("accuracy"), "simple_guess_accuracy": base.get("simple_guess_accuracy")} if base else None,
            "verification": verification,
            "finished_at": run.finished_at if verification and run else None,
            "is_estimate_note": NOTE}
