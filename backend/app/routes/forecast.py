"""The free pilot and its forecast. One id is used for the chat and the job: the project id."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..config import settings
from ..db import Session, get_session
from ..db.tables import Forecast, Project
from ..deps import get_ctx_factory, owned_project
from ..repositories import forecasts as forecasts_repo
from ..repositories.traces import TraceRepository
from ..services import gate, lifecycle
from ..services.data import families, pilot, tasks
from ..services.data.pilot import plain_view

router = APIRouter(tags=["forecast"])


class PilotIn(BaseModel):
    target: float | None = Field(default=None, gt=0, lt=1, description="what the verified result should reach, e.g. 0.8 for 80 out of 100")
    typical_error: float | None = Field(default=None, gt=0, description="a number answer only: 'typically off by no more than this', in the answer's own units; the server converts it")

    @model_validator(mode="after")
    def _one_goal(self):
        if self.target is not None and self.typical_error is not None:
            raise ValueError("send either target or typical_error, not both")
        return self   # sending neither is allowed only for grouping and unusual records (checked in the route)


def previous_on_other_data(s: Session, f: Forecast) -> Forecast | None:
    """The newest earlier forecast that looked at DIFFERENT data (before a guided fix), for a before and after view."""
    items = forecasts_repo.all_for_project(s, f.project_id)   # oldest first
    earlier = items[:[x.id for x in items].index(f.id)] if f.id in [x.id for x in items] else []
    for old in reversed(earlier):
        if old.dataset_version_id and old.dataset_version_id != f.dataset_version_id:
            return old
    return None


def forecast_view(f: Forecast, before: Forecast | None = None) -> dict:
    return {"forecast_id": f.id, "metric": f.metric, "target": f.target, "is_estimate": True,
            "predicted_metric": f.predicted_metric, "band_low": f.band_low, "band_high": f.band_high,
            "confidence": f.confidence, "eligible": f.eligible, "reason": f.reason, "pilot": f.pilot,
            "min_confidence": settings.forecast_min_confidence,
            "suggested_target": (f.pilot or {}).get("suggested_target"), "issues": (f.pilot or {}).get("issues", []),
            "model_type": families.type_info(f.family) if f.family else None,
            "task_type": (f.pilot or {}).get("task_type", "classification"), "plain": plain_view(f),
            "before_fix": before and {"predicted_metric": before.predicted_metric, "band_low": before.band_low, "band_high": before.band_high,
                                      "confidence": before.confidence, "target": before.target, "eligible": before.eligible}}


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
    """Free. Small test on about 5-10% of the data, then the forecast. After a finished run it starts a new round: Improve (target missed) or Try a higher target (reached, new target must be higher)."""
    gate.authorize(s, p, gate.Action.PILOT)
    kind = tasks.task_of(p)
    if body.target is None and body.typical_error is None:
        if kind.needs_target:
            raise HTTPException(422, "send a target or a typical_error")
        body.target = pilot.DEFAULT_STEADINESS   # grouping and unusual: the bar is ours, not the user's
    if p.status == "done":
        try:
            lifecycle.reopen_for_improvement(s, p, body.target if body.target is not None else 0.5)
        except lifecycle.TargetNotHigher as e:
            raise HTTPException(400, str(e))
        except lifecycle.BadTransition:
            raise HTTPException(409, "there is no finished run to start a new round from")
    if p.status not in {"baseline_done", "quoted"}:
        raise HTTPException(409, _PILOT_BLOCKED.get(p.status, "run the free baseline first"))
    try:
        storage = make(p).storage
        target = body.target if body.target is not None else pilot.target_for_error(s, storage, p, body.typical_error)
        f = pilot.run_pilot(s, storage, p, target)
    except pilot.ForecastError as e:
        raise HTTPException(400, str(e))
    TraceRepository(s).add(p.id, "forecast", {"forecast_id": f.id, "confidence": f.confidence, "eligible": f.eligible})
    return forecast_view(f, previous_on_other_data(s, f))


@router.get("/jobs/{pid}/forecast")
def read_forecast(pid: str, *, p: Project = Depends(owned_project), s: Session = Depends(get_session)):
    f = forecasts_repo.latest_for_project(s, pid)
    if f is None:
        raise HTTPException(404, "no pilot has been run yet")
    return forecast_view(f, previous_on_other_data(s, f))
