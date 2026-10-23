from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import BaselineRun, DatasetVersion, Project, Quote
from . import lifecycle
from .cost import estimate_quote


class QuoteError(Exception):
    pass


def create_quote(session: Session, project: Project) -> Quote:
    run = session.scalar(select(BaselineRun).where(BaselineRun.project_id == project.id).order_by(BaselineRun.created_at.desc()))
    if run is None:
        raise QuoteError("run the free baseline first: the quote needs its timings")
    version = session.get(DatasetVersion, run.dataset_version_id)
    est = estimate_quote([tuple(s) for s in run.samples], version.rows, settings.max_job_cap_cents)
    q = Quote(project_id=project.id, instance_type=est.instance_type, estimate_cents=est.estimate_cents,
              low_cents=est.low_cents, high_cents=est.high_cents, cap_cents=est.cap_cents, breakdown=est.breakdown,
              prices_version=est.prices_version,
              expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.quote_ttl_minutes))
    session.add(q)
    session.commit()
    if project.status in {"baseline_done", "quoted", "awaiting_payment"}:
        lifecycle.transition(session, project, "quoted")
    return q


def approve_quote(session: Session, project: Project, quote: Quote) -> Quote:
    exp = quote.expires_at if quote.expires_at.tzinfo else quote.expires_at.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise QuoteError("this quote has expired; ask for a new one")
    quote.approved_at = datetime.now(timezone.utc)
    session.commit()
    lifecycle.transition(session, project, "awaiting_payment")
    return quote
