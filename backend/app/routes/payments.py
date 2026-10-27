from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..config import settings
from ..db import Session, get_session
from ..integrations.factory import get_payment_provider
from ..ports import ProviderError
from ..repositories import payments as payments_repo
from ..repositories import projects as projects_repo
from ..services import gate, payments

router = APIRouter(prefix="/payments", tags=["payments"])


class OrderIn(BaseModel):
    project_id: str


@router.post("/orders")
def create_order(body: OrderIn, s: Session = Depends(get_session)):
    project = projects_repo.get(s, body.project_id)
    if project is None:
        raise HTTPException(404)
    try:
        pay, url = payments.create_order(s, get_payment_provider(), settings.payment_provider, project)
    except gate.GateDenied as e:
        raise HTTPException(403, str(e))
    except ProviderError:
        raise HTTPException(502, "The payment service could not be reached. Nothing was charged. Please try again.")
    return {"payment_id": pay.id, "hold_cents": pay.amount_cents, "compute_max_cents": pay.compute_amount_cents,
            "success_fee_max_cents": pay.fee_amount_cents, "approve_url": url, "state": pay.state}


@router.post("/{payment_id}/authorize")
def authorize(payment_id: str, s: Session = Depends(get_session)):
    """The browser says the buyer approved the hold. Only the server's own check with PayPal makes it count."""
    pay = payments_repo.get(s, payment_id)
    if pay is None:
        raise HTTPException(404)
    try:
        ok = payments.confirm_hold(s, get_payment_provider(), pay)
    except payments.PaymentError as e:
        raise HTTPException(409, str(e))
    except ProviderError:
        raise HTTPException(502, "The payment service could not be reached. Nothing was charged. Please try again.")
    return {"held": ok, "state": pay.state}


@router.get("/{payment_id}")
def read(payment_id: str, s: Session = Depends(get_session)):
    """Receipt data: what was held, the compute captured, the fee captured, and what was released."""
    pay = payments_repo.get(s, payment_id)
    if pay is None:
        raise HTTPException(404)
    return {"payment_id": pay.id, "state": pay.state, "hold_cents": pay.amount_cents,
            "compute_captured_cents": pay.compute_captured_cents, "fee_captured_cents": pay.fee_captured_cents,
            "released_cents": pay.released_cents,
            "total_charged_cents": pay.compute_captured_cents + pay.fee_captured_cents}
