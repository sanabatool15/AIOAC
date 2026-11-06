"""Everything that happened in one project, for the History screen. Read-only. Never exposes storage keys."""
from ..db import Session
from ..db.tables import Project
from ..repositories import datasets as datasets_repo
from ..repositories import payments as payments_repo
from ..repositories import quotes as quotes_repo
from ..repositories import training_runs as runs_repo


def result_summary(result: dict | None) -> dict | None:
    if not result:
        return None
    out = {k: result[k] for k in ("accuracy", "simple_guess_accuracy") if k in result}
    v = result.get("verification")
    if v:
        out["verification"] = {"value": v.get("value"), "target": v.get("target"), "passed": v.get("passed")}
    if result.get("stopped_by_user"):
        out["stopped_by_user"] = True
    return out or None


def payment_summary(pay) -> dict:
    return {"payment_id": pay.id, "state": pay.state, "hold_cents": pay.amount_cents,
            "compute_captured_cents": pay.compute_captured_cents, "fee_captured_cents": pay.fee_captured_cents,
            "released_cents": pay.released_cents, "total_charged_cents": pay.compute_captured_cents + pay.fee_captured_cents}


def project_history(session: Session, project: Project) -> dict:
    versions = [{"id": v.id, "parent_id": v.parent_id, "rows": v.rows, "columns": v.columns, "target_column": v.target_column,
                 "source": v.source, "license": v.license, "notes": v.notes, "created_at": v.created_at}
                for v in datasets_repo.versions_for_project(session, project.id)]
    runs = [{"id": r.id, "status": r.status, "backend": r.backend, "cost_cents": r.cost_cents,
             "started_at": r.started_at, "finished_at": r.finished_at, "result": result_summary(r.result)}
            for r in runs_repo.all_for_project(session, project.id)]
    quotes = [{"id": q.id, "estimate_cents": q.estimate_cents, "low_cents": q.low_cents, "high_cents": q.high_cents,
               "cap_cents": q.cap_cents, "approved": q.approved_at is not None, "created_at": q.created_at}
              for q in quotes_repo.all_for_project(session, project.id)]
    pay = payments_repo.latest_for_project(session, project.id)
    return {"versions": versions, "runs": runs, "quotes": quotes, "payment": payment_summary(pay) if pay else None}
