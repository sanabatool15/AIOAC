"""One guided data fix (services/data/fixes.py). Propose is free and changes nothing; apply is the user's click."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db import Session, get_session
from ..db.tables import Project
from ..deps import get_ctx_factory, owned_project
from ..repositories.traces import TraceRepository
from ..services import gate
from ..services.data import fixes

router = APIRouter(tags=["fixes"])


class ApplyIn(BaseModel):
    version_id: str | None = None   # the data version the user saw in the proposal; nothing is applied if it moved on


@router.post("/chats/{pid}/fix/propose")
def propose(pid: str, *, p: Project = Depends(owned_project), s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    """Free. What a data fix would change (rows removed, columns dropped, before and after). Changes nothing."""
    try:
        return fixes.propose_fix(s, make(p).storage, p).as_dict()
    except fixes.FixError as e:
        raise HTTPException(409, str(e))


@router.post("/chats/{pid}/fix/apply")
def apply(pid: str, *, p: Project = Depends(owned_project), body: ApplyIn, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    """The click is the approval (gate level 1). Makes a new version of the data and re-runs the free steps on it."""
    gate.authorize(s, p, gate.Action.CLEAN, user_approved=True)
    try:
        child, proposal = fixes.apply_fix(s, make(p).storage, p, expected_version_id=body.version_id)
    except fixes.FixError as e:
        raise HTTPException(409, str(e))
    TraceRepository(s).add(p.id, "data_fix", {"version_id": child.id, "rows_removed": proposal.rows_removed,
                                              "columns_dropped": proposal.columns_dropped})
    return {"version_id": child.id, "status": p.status, "rows_before": proposal.rows_before, "rows_after": proposal.rows_after,
            "columns_before": proposal.columns_before, "columns_after": proposal.columns_after,
            "rows_removed": proposal.rows_removed, "columns_dropped": proposal.columns_dropped,
            "fixes_left": max(0, proposal.fixes_left - 1),
            "next": "run the free small test again on the new data to see whether the estimate changed"}

