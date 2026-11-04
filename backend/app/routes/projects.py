import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..db import Session, get_session
from ..integrations.factory import get_job_runner
from ..deps import get_ctx_factory
from ..db.tables import Project
from ..integrations.factory import get_llm
from ..ports import ProviderError
from ..integrations.factory import get_storage
from ..repositories import analysis as analysis_repo
from ..repositories import conversations as conversations_repo
from ..repositories import datasets as datasets_repo
from ..repositories import forecasts as forecasts_repo
from ..repositories import payments as payments_repo
from ..repositories import projects as projects_repo
from ..repositories import training_runs as runs_repo
from ..repositories.traces import TraceRepository
from ..services.data import analysis, datasets
from .forecast import forecast_view
from .payments import receipt
from ..services import gate, lifecycle, payments, training
from ..services.cost import quotes
from ..services.agent.loop import TurnInProgress, run_agent
from ..services.agent.runlog import DbSink, RunLog

router = APIRouter(prefix="/projects", tags=["projects"])


def _project(s: Session, pid: str) -> Project:
    p = projects_repo.get(s, pid)
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
    p = projects_repo.create(s, body.goal)
    return {"id": p.id, "status": p.status}


@router.get("")
def list_projects(s: Session = Depends(get_session)):
    return [{"id": p.id, "goal": p.goal, "status": p.status, "created_at": p.created_at} for p in projects_repo.list_all(s)]


@router.get("/{pid}")
def read(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    q = gate.latest_quote(s, pid)
    version = datasets_repo.get_version(s, p.chosen_dataset_version_id) if p.chosen_dataset_version_id else None
    report = analysis_repo.latest_insight_report(s, version.id) if version else None
    forecast = forecasts_repo.latest_for_project(s, pid)
    pay = payments_repo.for_quote(s, q.id) if q else None
    run = runs_repo.latest_for_project(s, pid)
    return {"id": p.id, "goal": p.goal, "status": p.status, "readiness_grade": p.readiness_grade,
            "trust_level": p.trust_level, "baseline": p.baseline_result,
            "quote": q and {"id": q.id, "estimate_cents": q.estimate_cents, "low_cents": q.low_cents,
                            "high_cents": q.high_cents, "cap_cents": q.cap_cents, "success_fee_max_cents": q.fee_cents,
                            "approved": q.approved_at is not None},
            "dataset": version and {"rows": version.rows, "columns": version.columns, "target": version.target_column,
                                    "source": version.source, "license": version.license},
            "readiness": report and {"grade": report.grade, "findings": report.findings},
            "forecast": forecast and forecast_view(forecast),
            "payment": pay and {"payment_id": pay.id, "state": pay.state, "approve_url": pay.approve_url, "hold_cents": pay.amount_cents},
            "run": run and {"run_id": run.id, "status": run.status}}


@router.get("/{pid}/messages")
def messages(pid: str, s: Session = Depends(get_session)):
    """Chat history for the screen: what the user said, what the assistant said, and approval cards. Tool results and skills are left out."""
    _project(s, pid)
    out = []
    for m in conversations_repo.project_messages(s, pid):
        if m.kind == "card":
            try:
                card = json.loads(m.content)
            except ValueError:
                continue
            out.append({"id": m.id, "role": "assistant", "text": card.get("what", ""), "kind": "card", "card": card, "created_at": m.created_at})
        elif m.role in ("user", "assistant") and m.kind in ("chat", "note") and m.content:
            out.append({"id": m.id, "role": m.role, "text": m.content, "kind": m.kind, "created_at": m.created_at})
    return out


@router.post("/{pid}/chat")
def chat(pid: str, body: ChatIn, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    p = _project(s, pid)
    try:
        r = run_agent(make(p, body.approve), get_llm(), body.message, log=RunLog([DbSink(s)], log_id=f"app/{pid}"))
    except TurnInProgress as e:
        raise HTTPException(409, str(e))
    return {"status": r.status, "text": r.text, "card": r.card}


@router.post("/{pid}/data")
def upload(pid: str, body: UploadIn, s: Session = Depends(get_session)):
    p = _project(s, pid)
    try:
        c = datasets.add_candidate(s, get_storage(), p, body.name, "upload", body.csv_text.encode())
    except datasets.DatasetError as e:
        raise HTTPException(400, str(e))
    return {"candidate_id": c.id, "rows": c.rows}


class SelectIn(BaseModel):
    target: str | None = None


@router.post("/{pid}/data/{candidate_id}/select")
def select_data(pid: str, candidate_id: str, body: SelectIn | None = None, s: Session = Depends(get_session)):
    """The user's click is the approval. Same service as the agent's select_dataset tool."""
    p = _project(s, pid)
    if p.status != "described":
        raise HTTPException(409, "a dataset was already chosen for this project")
    storage = get_storage()
    target = body.target if body else None
    try:
        if not target:
            cols = datasets.candidate_columns(s, storage, p, candidate_id)
            raise HTTPException(400, "which column should we predict? Columns: " + ", ".join(cols))
        v = datasets.select_candidate(s, storage, p, candidate_id, target)
    except datasets.DatasetError as e:
        raise HTTPException(400, str(e))
    return {"rows": v.rows, "target": v.target_column, "status": p.status}


@router.post("/{pid}/readiness")
def readiness(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    if p.status == "described":
        raise HTTPException(409, "choose a dataset first")
    if p.status != "data_chosen":
        raise HTTPException(409, "the readiness check was already done for this project")
    r = analysis.readiness(s, get_storage(), p)
    return {"grade": r.grade, "findings": r.findings, "status": p.status}


@router.post("/{pid}/baseline")
def baseline(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    if p.status in ("described", "data_chosen"):
        raise HTTPException(409, "choose a dataset first" if p.status == "described" else "run the readiness check first")
    if p.status != "readiness_done":
        raise HTTPException(409, "the free test was already done for this project")
    r = analysis.baseline(s, get_storage(), p)
    return {"accuracy": r.accuracy, "simple_guess_accuracy": r.simple_guess_accuracy, "trust_level": p.trust_level, "status": p.status}


@router.get("/{pid}/payment")
def project_payment(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    q = gate.latest_quote(s, pid)
    pay = payments_repo.for_quote(s, q.id) if q else None
    if pay is None:
        raise HTTPException(404, "no payment has been started for this project")
    return {**receipt(pay), "project_id": pid}


@router.post("/{pid}/quote/approve")
def approve_quote(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    q = gate.latest_quote(s, pid)
    if q is None:
        raise HTTPException(400, "no quote yet")
    if q.approved_at is not None:  # a repeat returns the same result
        exp = q.expires_at if q.expires_at.tzinfo else q.expires_at.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(400, "this quote has expired; ask for a new one")
        return {"approved": True, "cap_cents": q.cap_cents}
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
    except gate.NotReady as e:
        raise HTTPException(409, str(e))
    except gate.GateDenied as e:  # a real refusal, such as the global budget guard
        raise HTTPException(403, str(e))
    try:
        runner.enqueue(run.id)
    except Exception:
        training.fail_run(s, ctx.provider, run, "could not queue the job")  # nothing ran: the hold is voided
        raise HTTPException(503, "could not start the training job; nothing was charged and your hold is being released")
    return {"run_id": run.id, "status": run.status}


@router.get("/{pid}/training")
def training_progress(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    run = training.active_run(s, pid)
    if run is None:
        return {"status": "not_started"}
    return training.progress(s, run)


@router.post("/{pid}/training/stop")
def training_stop(pid: str, s: Session = Depends(get_session)):
    p = _project(s, pid)
    try:
        run = training.request_stop(s, p)
    except training.NoActiveRun as e:
        raise HTTPException(409, str(e))
    return {"run_id": run.id, "stop_requested": True}


@router.post("/{pid}/settle/retry")
def retry_settle(pid: str, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    """Try again to finish the payment steps after PayPal failed part-way. Safe to call repeatedly."""
    p = _project(s, pid)
    try:
        state = training.retry_settle(s, make(p).provider, p)
    except payments.PaymentError as e:
        raise HTTPException(409, str(e))
    except ProviderError:
        raise HTTPException(502, "The payment service could not be reached yet. Nothing extra was charged. Please try again shortly.")
    return {"payment_state": state, "status": p.status}


@router.post("/{pid}/cancel")
def cancel(pid: str, s: Session = Depends(get_session), make=Depends(get_ctx_factory)):
    """Change your mind after the hold and before training starts. The whole hold is released; you pay nothing."""
    p = _project(s, pid)
    try:
        pay = payments.cancel(s, make(p).provider, p)
    except payments.PaymentError as e:
        raise HTTPException(409, str(e))
    except ProviderError:
        raise HTTPException(502, "The payment service could not be reached. Please try again.")
    return {"payment_state": pay.state, "status": p.status}


@router.get("/{pid}/trace")
def trace(pid: str, s: Session = Depends(get_session)):
    _project(s, pid)
    return [{"seq": t.seq, "kind": t.kind, "content": t.content} for t in TraceRepository(s).steps(pid)]
