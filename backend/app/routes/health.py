from fastapi import APIRouter

from ..integrations.factory import llm_configured

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True, "llm": {"configured": llm_configured()}}
