from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..jobs import get_job_runner
from ..deps import get_ctx_factory
from ..models import Project
from ..providers.llm import get_llm
from ..providers.storage import get_storage
from ..repositories.traces import TraceRepository
from ..services import datasets, gate, lifecycle, payments, quotes, training
from ..services.agent.loop import run_agent

router = APIRouter(prefix="/projects", tags=["projects"])


def _project(s: Session, pid: str) -> Project:
    p = s.get(Project, pid)
    if p is None:
        raise HTTPException(404, "project not found")
    return p


class ProjectIn(BaseModel):
    goal: str


class ChatIn(BaseModel):
    message: str | None = None
    approve: list[str] = []  # L1 actions the user approved on the card


class UploadIn(BaseModel):
    name: str
    csv_text: str


@router.post("")
def create(body: ProjectIn, s: Session = Depends(get_session)):
    p = Project(goal=body.goal)
    s.add(p)
    s.commit()
    return {"id": p.id, "status": p.status}


@router.get("/{pid}")
def read(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    q = gate.latest_quote(s, pid)
    return {"id": p.id, "goal": p.goal, "status": p.status, "readiness_grade": p.readiness_grade,
            "trust_level": p.trust_level, "baseline": p.baseline_result,
            "quote": q and {"id": q.id, "estimate_cents": q.estimate_cents, "low_cents": q.low_cents,
                            "high_cents": q.high_cents, "cap_cents": q.cap_cents, "approved": q.approved_at is not None}}


@router.post("/{pid}/chat")
def chat(pid: str, body: ChatIn, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    p = _project(s, pid)
    r = run_agent(make(p, body.approve), get_llm(), body.message)
    return {"status": r.status, "text": r.text, "card": r.card}


@router.post("/{pid}/data")
def upload(pid: str, body: UploadIn, s: Session = Depends(get_session)):
    p = _project(s, pid)
    try:
        c = datasets.add_candidate(s, get_storage(), p, body.name, "upload", body.csv_text.encode())
    except datasets.DatasetError as e:
        raise HTTPException(400, str(e))
    return {"candidate_id": c.id, "rows": c.rows}


@router.post("/{pid}/quote/approve")
def approve_quote(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    q = gate.latest_quote(s, pid)
    if q is None:
        raise HTTPException(400, "no quote yet")
    try:
        quotes.approve_quote(s, p, q)
    except (quotes.QuoteError, lifecycle.BadTransition) as e:
        raise HTTPException(400, str(e))
    return {"approved": True, "cap_cents": q.cap_cents}


def get_runner():
    return get_job_runner()


@router.post("/{pid}/train")
def train(pid: str, s: Session = Depends(get_session), make=Depends(get_ctx_factory), runner=Depends(get_runner)):
    """Starts training in the background and returns at once. Poll GET /projects/{id}/training."""
    p = _project(s, pid)
    ctx = make(p)
    try:
        run = training.start_training(s, p, ctx.backend)
    except gate.GateDenied as e:
        raise HTTPException(403, str(e))
    try:
        runner.enqueue(run.id)
    except Exception:
        training.fail_run(s, ctx.provider, run, "could not queue the job")  # nothing ran: full refund
        raise HTTPException(503, "could not start the training job; your payment is being refunded")
    return {"run_id": run.id, "status": run.status}


@router.get("/{pid}/training")
def training_progress(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    run = training.active_run(s, pid)
    if run is None:
        raise HTTPException(404, "no training has started for this project")
    return training.progress(s, run)


@router.post("/{pid}/training/stop")
def training_stop(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    try:
        run = training.request_stop(s, p)
    except training.NoActiveRun as e:
        raise HTTPException(409, str(e))
    return {"run_id": run.id, "stop_requested": True}


@router.get("/{pid}/trace")
def trace(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    return [{"seq": t.seq, "kind": t.kind, "content": t.content} for t in TraceRepository(s).steps(pid)]
