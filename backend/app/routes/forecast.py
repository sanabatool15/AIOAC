"""The free pilot and its forecast. One id is used for the chat and the job: the project id."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..db import Session, get_session
from ..db.tables import Forecast, Project
from ..deps import get_ctx_factory, owned_project
from ..repositories import forecasts as forecasts_repo
from ..repositories.traces import TraceRepository
from ..services import gate, lifecycle
from ..services.data import families, pilot

router = APIRouter(tags=["forecast"])


class PilotIn(BaseModel):
    target: float = Field(gt=0, lt=1, description="what the verified result should reach, e.g. 0.8 for 80 out of 100")


def forecast_view(f: Forecast) -> dict:
    return {"forecast_id": f.id, "metric": f.metric, "target": f.target, "is_estimate": True,
            "predicted_metric": f.predicted_metric, "band_low": f.band_low, "band_high": f.band_high,
            "confidence": f.confidence, "eligible": f.eligible, "reason": f.reason, "pilot": f.pilot,
            "min_confidence": settings.forecast_min_confidence,
            "suggested_target": (f.pilot or {}).get("suggested_target"), "issues": (f.pilot or {}).get("issues", []),
            "model_type": families.type_info(f.family) if f.family else None}


_PILOT_BLOCKED = {
    "awaiting_payment": "a payment is already in progress for this project, so the free test cannot be run again now",
    "paid": "the payment is already confirmed for this project, so the free test cannot be run again now",
    "training": "training is already running for this project, so the free test cannot be run again now",
    "failed": "this project has ended, so the free test cannot be run again",
    "stopped": "this project has ended, so the free test cannot be run again",
    "voided": "this project has ended, so the free test cannot be run again",
}


@router.post("/chats/{pid}/pilot")
def run_pilot(pid: str, *, p: Project = Depends(owned_project), body: PilotIn, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    """Free. Small test on about 5-10% of the data, then the forecast. After a MISSED run this is the Improve round."""
    gate.authorize(s, p, gate.Action.PILOT)
    if p.status == "done":
        try:
            lifecycle.reopen_for_improvement(s, p)
        except lifecycle.BadTransition:
            raise HTTPException(409, "the finished run reached its target, so there is nothing to improve")
    if p.status not in {"baseline_done", "quoted"}:
        raise HTTPException(409, _PILOT_BLOCKED.get(p.status, "run the free baseline first"))
    try:
        f = pilot.run_pilot(s, make(p).storage, p, body.target)
    except pilot.ForecastError as e:
        raise HTTPException(400, str(e))
    TraceRepository(s).add(p.id, "forecast", {"forecast_id": f.id, "confidence": f.confidence, "eligible": f.eligible})
    return forecast_view(f)


@router.get("/jobs/{pid}/forecast")
def read_forecast(pid: str, *, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    f = forecasts_repo.latest_for_project(s, pid)
    if f is None:
        raise HTTPException(404, "no pilot has been run yet")
    return forecast_view(f)
