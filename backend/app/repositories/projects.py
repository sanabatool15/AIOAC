from ..db import Session
from ..db.tables import Project


def get(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)


def create(session: Session, goal: str) -> Project:
    p = Project(goal=goal)
    session.add(p)
    session.commit()
    return p


def set_status(session: Session, project: Project, new: str) -> None:
    project.status = new
    session.commit()
