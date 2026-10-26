"""The "Forecast, then verify" flow (specs/payments.md). One id is used for the chat, the job and the agreement:
the project id. Three steps: free pilot -> forecast -> fixed-price quote."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_session
from ..deps import get_ctx_factory
from ..models import Forecast, Project
from ..services import forecast as fc_service
from ..services import gate, lifecycle, quotes
from ..services.cost import QuoteTooExpensive
from ..repositories.traces import TraceRepository

router = APIRouter(tags=["flow"])


def _project(s: Session, pid: str) -> Project:
    p = s.get(Project, pid)
    if p is None:
        raise HTTPException(404, "not found")
    return p


class PilotIn(BaseModel):
    target: float = Field(gt=0, lt=1, description="what the verified result should reach, e.g. 0.8 for 80 out of 100")


def forecast_view(f: Forecast) -> dict:
    return {"forecast_id": f.id, "metric": f.metric, "target": f.target, "is_estimate": True,
            "predicted_metric": f.predicted_metric, "band_low": f.band_low, "band_high": f.band_high,
            "confidence": f.confidence, "eligible": f.eligible, "reason": f.reason, "pilot": f.pilot,
            "min_confidence": settings.forecast_min_confidence}


@router.post("/chats/{cid}/pilot")
def pilot(cid: str, body: PilotIn, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    """Free. Small test on about 5-10% of the data, then the forecast. After a MISSED run this is the Improve round."""
    p = _project(s, cid)
    gate.authorize(s, p, gate.Action.PILOT)
    if p.status == "done":
        try:
            lifecycle.reopen_for_improvement(s, p)
        except lifecycle.BadTransition:
            raise HTTPException(409, "the finished run reached its target, so there is nothing to improve")
    if p.status not in {"baseline_done", "quoted"}:
        raise HTTPException(409, "run the free baseline first")
    try:
        f = fc_service.run_pilot(s, make(p).storage, p, body.target)
    except fc_service.ForecastError as e:
        raise HTTPException(400, str(e))
    TraceRepository(s).add(p.id, "forecast", {"forecast_id": f.id, "confidence": f.confidence, "eligible": f.eligible})
    return forecast_view(f)


@router.get("/jobs/{jid}/forecast")
def forecast(jid: str, s: Session = Depends(get_session)):
    _project(s, jid)
    f = fc_service.latest_forecast(s, jid)
    if f is None:
        raise HTTPException(404, "no pilot has been run yet")
    return forecast_view(f)


@router.post("/agreements/{aid}/quote")
def quote(aid: str, s: Session = Depends(get_session)):
    """One fixed price for the full run: estimated compute + a small success fee, and a hard cap. Not for ineligible forecasts."""
    p = _project(s, aid)
    gate.authorize(s, p, gate.Action.CREATE_QUOTE)
    try:
        q = quotes.create_quote(s, p)
    except (quotes.QuoteError, QuoteTooExpensive, lifecycle.BadTransition) as e:
        raise HTTPException(409, str(e))
    return quote_view(q)


def quote_view(q) -> dict:
    return {"quote_id": q.id, "is_estimate": True, "estimate_cents": q.estimate_cents, "low_cents": q.low_cents,
            "high_cents": q.high_cents, "cap_cents": q.cap_cents, "compute_estimate_cents": q.breakdown.get("compute_estimate_cents"),
            "compute_cap_cents": q.compute_cap_cents, "success_fee_cents": q.fee_cents,
            "forecast_confidence": q.breakdown.get("forecast_confidence"), "target": q.breakdown.get("target"),
            "terms": "You pay compute either way. The success fee only if the target is verified."}
