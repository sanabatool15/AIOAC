from sqlalchemy import select, update

from ..db import Session
from ..db.tables import Project


def get(session: Session, project_id: str) -> Project | None:
    return session.get(Project, project_id)


def reload(session: Session, project: Project) -> Project:
    """Re-read the project from the database (another request may have changed it)."""
    session.refresh(project)
    return project


def get_owned(session: Session, project_id: str, user_id: str, org_id: str) -> Project | None:
    """The project only if it belongs to this user and org; None otherwise (the caller answers 404)."""
    return session.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id, Project.org_id == org_id))


def create(session: Session, goal: str, user_id: str | None = None, org_id: str | None = None) -> Project:
    p = Project(goal=goal, user_id=user_id, org_id=org_id, task_type="classification")
    session.add(p)
    session.commit()
    return p


def set_status(session: Session, project: Project, new: str) -> None:
    project.status = new
    session.commit()


def set_chosen_version(session: Session, project: Project, version_id: str) -> None:
    """Point the project at another dataset version (a guided fix makes a child version)."""
    project.chosen_dataset_version_id = version_id
    session.commit()


def claim_status(session: Session, project: Project, expected: str, new: str) -> bool:
    """Compare-and-swap: move the status only if it is still `expected` in the database. True for exactly one caller."""
    res = session.execute(update(Project).where(Project.id == project.id, Project.status == expected).values(status=new))
    session.commit()
    session.refresh(project)
    return res.rowcount == 1


def list_all(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())))


def list_owned(session: Session, user_id: str, org_id: str) -> list[Project]:
    return list(session.scalars(select(Project).where(Project.user_id == user_id, Project.org_id == org_id)
                                .order_by(Project.created_at.desc(), Project.id.desc())))
