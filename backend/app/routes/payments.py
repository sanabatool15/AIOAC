from fastapi import APIRouter

router = APIRouter(prefix="/payments", tags=["payments"])

# TODO: POST /payments/orders, POST /payments/capture (human review required)
