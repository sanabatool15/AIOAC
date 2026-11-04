from sqlalchemy import select

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


def list_all(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())))
