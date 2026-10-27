from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_session
from ..db.tables import Payment, Project
from ..integrations.factory import get_payment_provider
from ..ports import ProviderError
from ..services import gate, payments

router = APIRouter(prefix="/payments", tags=["payments"])


class OrderIn(BaseModel):
    project_id: str


@router.post("/orders")
def create_order(body: OrderIn, s: Session = Depends(get_session)):
    project = s.get(Project, body.project_id)
    if project is None:
        raise HTTPException(404)
    try:
        pay, url = payments.create_order(s, get_payment_provider(), settings.payment_provider, project)
    except gate.GateDenied as e:
        raise HTTPException(403, str(e))
    except ProviderError:
        raise HTTPException(502, "The payment service could not be reached. Nothing was charged. Please try again.")
    return {"payment_id": pay.id, "amount_cents": pay.amount_cents, "approve_url": url}


@router.post("/{payment_id}/capture")
def capture(payment_id: str, s: Session = Depends(get_session)):
    """The browser asks us to finish the payment. Only the server's own check marks it paid."""
    pay = s.get(Payment, payment_id)
    if pay is None:
        raise HTTPException(404)
    try:
        ok = payments.confirm_capture(s, get_payment_provider(), pay)
    except payments.PaymentError as e:
        raise HTTPException(409, str(e))
    except ProviderError:
        raise HTTPException(502, "The payment service could not be reached. Please try again.")
    return {"verified": ok}
