from sqlalchemy.orm import Session

from ..repositories.jobs import JobRepository


def create_job(session: Session, description: str):
    return JobRepository(session).create(description)
