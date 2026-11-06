from fastapi import APIRouter

from ..integrations.factory import llm_configured
from ..services import auth

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "llm": {"configured": llm_configured()}, "auth": {"configured": auth.configured()}}
