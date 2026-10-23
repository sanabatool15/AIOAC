from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AgentStep


class TraceRepository:
    def __init__(self, session: Session):
        self.s = session

    def add(self, project_id: str, kind: str, content: dict, run_id: str | None = None) -> None:
        seq = self.s.scalar(select(func.coalesce(func.max(AgentStep.seq), 0)).where(AgentStep.project_id == project_id)) + 1
        self.s.add(AgentStep(project_id=project_id, run_id=run_id, seq=seq, kind=kind, content=content))
        self.s.commit()

    def steps(self, project_id: str, kinds: tuple[str, ...] | None = None) -> list[AgentStep]:
        q = select(AgentStep).where(AgentStep.project_id == project_id).order_by(AgentStep.seq)
        if kinds:
            q = q.where(AgentStep.kind.in_(kinds))
        return list(self.s.scalars(q))
