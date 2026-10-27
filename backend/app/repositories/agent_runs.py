"""One row per agent turn (`agent_runs`)."""
from sqlalchemy import func, select, update

from ..db import Session
from ..db.tables import AgentRun, AgentStep


def create(session: Session, project_id: str, conversation_id: str) -> AgentRun:
    run = AgentRun(project_id=project_id, conversation_id=conversation_id)
    session.add(run)
    session.commit()
    return run


def project_usage(session: Session, project_id: str, exclude_run: str) -> tuple[int, int]:
    """(tokens, model cost in millionths of a dollar) used by the project's other runs."""
    q = select(func.coalesce(func.sum(AgentRun.tokens_used), 0), func.coalesce(func.sum(AgentRun.llm_cost_micros), 0)).where(
        AgentRun.project_id == project_id, AgentRun.id != exclude_run)
    tokens, micros = session.execute(q).one()
    return int(tokens), int(micros)


def stamp_unowned_steps(session: Session, project_id: str, run_id: str) -> None:
    """Gate decisions are written without a run id; give them this run's id and commit."""
    session.execute(update(AgentStep).where(AgentStep.project_id == project_id, AgentStep.run_id.is_(None)).values(run_id=run_id))
    session.commit()
