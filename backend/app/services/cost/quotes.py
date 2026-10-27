from datetime import datetime, timedelta, timezone

from ...config import settings
from ...db import Session
from ...db.tables import Project, Quote
from ...repositories import analysis as analysis_repo
from ...repositories import datasets as datasets_repo
from ...repositories import quotes as quotes_repo
from .. import lifecycle
from .cost import estimate_quote


class QuoteError(Exception):
    pass


def create_quote(session: Session, project: Project) -> Quote:
    run = analysis_repo.latest_baseline_run(session, project.id)
    if run is None:
        raise QuoteError("run the free baseline first: the quote needs its timings")
    version = datasets_repo.get_version(session, run.dataset_version_id)
    est = estimate_quote([tuple(s) for s in run.samples], version.rows, settings.max_job_cap_cents)
    q = quotes_repo.add(session, project_id=project.id, instance_type=est.instance_type, estimate_cents=est.estimate_cents,
              low_cents=est.low_cents, high_cents=est.high_cents, cap_cents=est.cap_cents, breakdown=est.breakdown,
              prices_version=est.prices_version,
              expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.quote_ttl_minutes))
    if project.status in {"baseline_done", "quoted", "awaiting_payment"}:
        lifecycle.transition(session, project, "quoted")
    return q


def approve_quote(session: Session, project: Project, quote: Quote) -> Quote:
    exp = quote.expires_at if quote.expires_at.tzinfo else quote.expires_at.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise QuoteError("this quote has expired; ask for a new one")
    quotes_repo.mark_approved(session, quote, datetime.now(timezone.utc))
    lifecycle.transition(session, project, "awaiting_payment")
    return quote
