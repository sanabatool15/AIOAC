from sqlalchemy import select, update

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


def claim_status(session: Session, project: Project, expected: str, new: str) -> bool:
    """Compare-and-swap: move the status only if it is still `expected` in the database. True for exactly one caller."""
    res = session.execute(update(Project).where(Project.id == project.id, Project.status == expected).values(status=new))
    session.commit()
    session.refresh(project)
    return res.rowcount == 1


def list_all(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())))
