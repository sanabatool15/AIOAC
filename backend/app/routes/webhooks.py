from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# TODO: POST /webhooks/paypal. Verify signature first, then
# WebhookRepository.record_once(event_id) before doing anything (idempotent).
