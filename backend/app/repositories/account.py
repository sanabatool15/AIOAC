"""Read-only totals and lists for one signed-in user (projects joined by user and org)."""
from sqlalchemy import func, select

from ..db import Session
from ..db.tables import AgentRun, Payment, Project, TrainingRun


def _mine(user_id: str, org_id: str):
    return (Project.user_id == user_id) & (Project.org_id == org_id)


def count_projects(session: Session, user_id: str, org_id: str) -> int:
    return session.scalar(select(func.count()).select_from(Project).where(_mine(user_id, org_id))) or 0


def count_runs(session: Session, user_id: str, org_id: str) -> int:
    return session.scalar(select(func.count()).select_from(TrainingRun).join(Project, Project.id == TrainingRun.project_id)
                          .where(_mine(user_id, org_id))) or 0


def payment_totals(session: Session, user_id: str, org_id: str) -> tuple[int, int, int]:
    row = session.execute(select(func.coalesce(func.sum(Payment.compute_captured_cents), 0),
                                 func.coalesce(func.sum(Payment.fee_captured_cents), 0),
                                 func.coalesce(func.sum(Payment.released_cents), 0))
                          .join(Project, Project.id == Payment.project_id).where(_mine(user_id, org_id))).one()
    return int(row[0]), int(row[1]), int(row[2])


def llm_totals(session: Session, user_id: str, org_id: str) -> tuple[int, int]:
    row = session.execute(select(func.coalesce(func.sum(AgentRun.tokens_used), 0), func.coalesce(func.sum(AgentRun.llm_cost_micros), 0))
                          .join(Project, Project.id == AgentRun.project_id).where(_mine(user_id, org_id))).one()
    return int(row[0]), int(row[1])


def recent_projects(session: Session, user_id: str, org_id: str, limit: int) -> list[Project]:
    return list(session.scalars(select(Project).where(_mine(user_id, org_id)).order_by(Project.created_at.desc()).limit(limit)))


def recent_runs(session: Session, user_id: str, org_id: str, limit: int) -> list[tuple[TrainingRun, str]]:
    rows = session.execute(select(TrainingRun, Project.goal).join(Project, Project.id == TrainingRun.project_id)
                           .where(_mine(user_id, org_id)).order_by(TrainingRun.started_at.desc()).limit(limit)).all()
    return [(r, g) for r, g in rows]


def payments_with_goal(session: Session, user_id: str, org_id: str, limit: int | None = None) -> list[tuple[Payment, str]]:
    q = (select(Payment, Project.goal).join(Project, Project.id == Payment.project_id).where(_mine(user_id, org_id))
         .order_by(Payment.created_at.desc(), Payment.id.desc()))
    if limit:
        q = q.limit(limit)
    return [(p, g) for p, g in session.execute(q).all()]
