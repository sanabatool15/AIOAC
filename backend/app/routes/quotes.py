"""The fixed-price quote for the full run. The "agreement" is just the quote of the project."""
from fastapi import APIRouter, Depends, HTTPException

from ..db import Session, get_session
from ..db.tables import Quote
from ..repositories import projects as projects_repo
from ..services import gate, lifecycle
from ..services.cost import quotes
from ..services.cost.cost import QuoteTooExpensive

router = APIRouter(tags=["quotes"])


def quote_view(q: Quote) -> dict:
    return {"quote_id": q.id, "is_estimate": True, "estimate_cents": q.estimate_cents, "low_cents": q.low_cents,
            "high_cents": q.high_cents, "cap_cents": q.cap_cents,
            "compute_estimate_cents": q.breakdown.get("compute_estimate_cents"), "compute_cap_cents": q.compute_cap_cents,
            "success_fee_estimate_cents": q.breakdown.get("success_fee_estimate_cents"), "success_fee_max_cents": q.fee_cents,
            "forecast_confidence": q.breakdown.get("forecast_confidence"), "target": q.breakdown.get("target"),
            "terms": "You pay compute either way. The success fee only if the target is verified."}


@router.post("/agreements/{aid}/quote")
def create_quote(aid: str, s: Session = Depends(get_session)):
    """One fixed price for the full run: estimated compute + a small success fee, and a hard cap. Not for ineligible forecasts."""
    p = projects_repo.get(s, aid)
    if p is None:
        raise HTTPException(404, "not found")
    gate.authorize(s, p, gate.Action.CREATE_QUOTE)
    try:
        q = quotes.create_quote(s, p)
    except (quotes.QuoteError, QuoteTooExpensive, lifecycle.BadTransition) as e:
        raise HTTPException(409, str(e))
    return quote_view(q)
