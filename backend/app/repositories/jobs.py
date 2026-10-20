import uuid

from sqlalchemy.orm import Session

from ..models import Job, JobStatus


class JobRepository:
    def __init__(self, session: Session):
        self.s = session

    def create(self, description: str) -> Job:
        job = Job(id=uuid.uuid4().hex, description=description)
        self.s.add(job)
        self.s.commit()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.s.get(Job, job_id)

    def set_status(self, job: Job, status: JobStatus) -> None:
        job.status = status
        self.s.commit()
