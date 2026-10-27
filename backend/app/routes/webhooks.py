from fastapi import APIRouter, Depends, HTTPException, Request
from ..db import Session, get_session
from ..integrations.factory import get_payment_provider
from ..services import payments

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/paypal")
async def paypal(request: Request, s: Session = Depends(get_session)):
    body = await request.body()
    try:
        result = payments.handle_webhook(s, get_payment_provider(), dict(request.headers), body)
    except payments.InvalidWebhook:
        raise HTTPException(400, "invalid signature")
    except payments.PaymentError:
        raise HTTPException(409, "amount mismatch")  # recorded once; not retried into a 500 loop
    return {"result": result}
