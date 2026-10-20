from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..repositories.jobs import JobRepository
from ..services import jobs as job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobIn(BaseModel):
    description: str


@router.post("")
def create(body: JobIn, s: Session = Depends(get_session)):
    job = job_service.create_job(s, body.description)
    return {"id": job.id, "status": job.status}


@router.get("/{job_id}")
def read(job_id: str, s: Session = Depends(get_session)):
    job = JobRepository(s).get(job_id)
    if not job:
        raise HTTPException(404)
    return {"id": job.id, "status": job.status, "readiness_score": job.readiness_score}
