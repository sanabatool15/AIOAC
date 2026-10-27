"""The free pilot and its forecast. One id is used for the chat and the job: the project id."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..db import Session, get_session
from ..db.tables import Forecast, Project
from ..deps import get_ctx_factory
from ..repositories import forecasts as forecasts_repo
from ..repositories import projects as projects_repo
from ..repositories.traces import TraceRepository
from ..services import gate, lifecycle
from ..services.data import pilot

router = APIRouter(tags=["forecast"])


def _project(s: Session, pid: str) -> Project:
    p = projects_repo.get(s, pid)
    if p is None:
        raise HTTPException(404, "not found")
    return p


class PilotIn(BaseModel):
    target: float = Field(gt=0, lt=1, description="what the verified result should reach, e.g. 0.8 for 80 out of 100")


def forecast_view(f: Forecast) -> dict:
    return {"forecast_id": f.id, "metric": f.metric, "target": f.target, "is_estimate": True,
            "predicted_metric": f.predicted_metric, "band_low": f.band_low, "band_high": f.band_high,
            "confidence": f.confidence, "eligible": f.eligible, "reason": f.reason, "pilot": f.pilot,
            "min_confidence": settings.forecast_min_confidence,
            "suggested_target": (f.pilot or {}).get("suggested_target"), "issues": (f.pilot or {}).get("issues", [])}


@router.post("/chats/{cid}/pilot")
def run_pilot(cid: str, body: PilotIn, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
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
        f = pilot.run_pilot(s, make(p).storage, p, body.target)
    except pilot.ForecastError as e:
        raise HTTPException(400, str(e))
    TraceRepository(s).add(p.id, "forecast", {"forecast_id": f.id, "confidence": f.confidence, "eligible": f.eligible})
    return forecast_view(f)


@router.get("/jobs/{jid}/forecast")
def read_forecast(jid: str, s: Session = Depends(get_session)):
    _project(s, jid)
    f = forecasts_repo.latest_for_project(s, jid)
    if f is None:
        raise HTTPException(404, "no pilot has been run yet")
    return forecast_view(f)
