import math
from datetime import datetime, timedelta, timezone

from ...config import settings
from ...db import Session
from ...db.tables import Project, Quote
from ...repositories import analysis as analysis_repo
from ...repositories import datasets as datasets_repo
from ...repositories import forecasts as forecasts_repo
from ...repositories import quotes as quotes_repo
from .. import lifecycle
from .cost import estimate_quote


class QuoteError(Exception):
    pass


def create_quote(session: Session, project: Project) -> Quote:
    """One fixed price for the full run: estimated compute + a small success fee, with a hard cap.
    Refused unless the latest free pilot produced an eligible forecast (specs/payments.md)."""
    forecast = forecasts_repo.latest_for_project(session, project.id)
    if forecast is None:
        raise QuoteError("run the free pilot first: the quote needs its forecast")
    if not forecast.eligible:
        raise QuoteError(forecast.reason or "this run is not eligible to be sold")
    run = analysis_repo.latest_baseline_run(session, project.id)
    if run is None:
        raise QuoteError("run the free baseline first: the quote needs its timings")
    version = datasets_repo.get_version(session, run.dataset_version_id)
    est = estimate_quote([tuple(s) for s in run.samples], version.rows, settings.max_job_cap_cents)

    def fee_of(compute_cents: int) -> int:  # the success fee is a share of the compute
        return math.ceil(settings.success_fee_percent * compute_cents)

    max_fee, fee_estimate = fee_of(est.cap_cents), fee_of(est.estimate_cents)  # max_fee is what the hold carries
    q = quotes_repo.add(
        session, project_id=project.id, instance_type=est.instance_type, estimate_cents=est.estimate_cents + fee_estimate,
        low_cents=est.low_cents + fee_of(est.low_cents), high_cents=est.high_cents + fee_of(est.high_cents),
        cap_cents=est.cap_cents + max_fee, compute_cap_cents=est.cap_cents, fee_cents=max_fee, forecast_id=forecast.id,
        breakdown={**est.breakdown, "compute_estimate_cents": est.estimate_cents,
                   "compute_low_cents": est.low_cents, "compute_high_cents": est.high_cents,
                   "success_fee_estimate_cents": fee_estimate, "success_fee_max_cents": max_fee,
                   "forecast_confidence": forecast.confidence, "target": forecast.target},
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
