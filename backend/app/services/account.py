"""Account-level totals and receipts for the signed-in user. Read-only."""
from ..db import Session
from ..db.tables import User
from ..repositories import account as repo
from .history import payment_summary


def _dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


def _naive(dt):
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def usage(session: Session, user: User) -> dict:
    uid, oid = user.id, user.org_id
    compute, fees, released = repo.payment_totals(session, uid, oid)
    tokens, micros = repo.llm_totals(session, uid, oid)
    items = []
    for p in repo.recent_projects(session, uid, oid, 20):
        items.append({"when": p.created_at, "kind": "project", "text": f'Started "{p.goal[:80]}"'})
    for run, goal in repo.recent_runs(session, uid, oid, 20):
        words = {"running": "Training started", "done": "Training finished", "stopped": "Training stopped",
                 "failed": "Training failed"}.get(run.status, "Training update")
        items.append({"when": run.finished_at or run.started_at, "kind": "training", "text": f'{words} for "{goal[:80]}"'})
    for pay, goal in repo.payments_with_goal(session, uid, oid, 20):
        paid = pay.compute_captured_cents + pay.fee_captured_cents
        text = (f'Charged {_dollars(paid)} for "{goal[:80]}"' if paid
                else f'Held {_dollars(pay.amount_cents)} for "{goal[:80]}" (nothing charged)')
        items.append({"when": pay.created_at, "kind": "payment", "text": text})
    items.sort(key=lambda i: _naive(i["when"]), reverse=True)
    return {"projects": repo.count_projects(session, uid, oid), "training_runs": repo.count_runs(session, uid, oid),
            "compute_charged_cents": compute, "success_fees_cents": fees, "released_cents": released,
            "llm_tokens": tokens, "llm_cost_micros": micros, "recent_activity": items[:20]}


def receipts(session: Session, user: User) -> list[dict]:
    return [{**payment_summary(p), "project_id": p.project_id, "goal": goal, "created_at": p.created_at}
            for p, goal in repo.payments_with_goal(session, user.id, user.org_id)]
