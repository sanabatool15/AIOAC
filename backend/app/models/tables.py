"""Schema from specs/db.md. Money is integer cents.

LedgerEntry and WebhookEvent are insert-only. `org_id` is reserved for later
multi-tenancy and is not enforced anywhere.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Stamped:
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    org_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Stamped, Base):
    __tablename__ = "users"
    email: Mapped[str | None] = mapped_column(String, nullable=True)


class Project(Stamped, Base):
    __tablename__ = "projects"
    goal: Mapped[str] = mapped_column(String)
    task_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="described")
    chosen_dataset_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    readiness_grade: Mapped[str | None] = mapped_column(String, nullable=True)
    trust_level: Mapped[str | None] = mapped_column(String, nullable=True)
    baseline_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class DatasetCandidate(Stamped, Base):
    __tablename__ = "dataset_candidates"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="candidate")  # candidate | chosen | discarded


class DatasetVersion(Stamped, Base):
    __tablename__ = "dataset_versions"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_key: Mapped[str] = mapped_column(String)
    rows: Mapped[int] = mapped_column(Integer)
    columns: Mapped[int] = mapped_column(Integer)
    target_column: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)


class InsightReport(Stamped, Base):
    __tablename__ = "insight_reports"
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    measurements: Mapped[dict] = mapped_column(JSON)
    findings: Mapped[list] = mapped_column(JSON)
    grade: Mapped[str] = mapped_column(String)


class BaselineRun(Stamped, Base):
    __tablename__ = "baseline_runs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    accuracy: Mapped[float] = mapped_column()
    simple_guess_accuracy: Mapped[float] = mapped_column()
    samples: Mapped[list] = mapped_column(JSON)  # [[rows, seconds], ...] used by the cost estimator


class Quote(Stamped, Base):
    __tablename__ = "quotes"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    instance_type: Mapped[str] = mapped_column(String)
    estimate_cents: Mapped[int] = mapped_column(Integer)
    low_cents: Mapped[int] = mapped_column(Integer)
    high_cents: Mapped[int] = mapped_column(Integer)
    cap_cents: Mapped[int] = mapped_column(Integer)
    breakdown: Mapped[dict] = mapped_column(JSON)
    prices_version: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payment(Stamped, Base):
    __tablename__ = "payments"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), unique=True)
    provider: Mapped[str] = mapped_column(String)
    provider_order_id: Mapped[str] = mapped_column(String, unique=True)
    provider_capture_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # set by the server only
    approve_url: Mapped[str | None] = mapped_column(String, nullable=True)  # kept so a reload can resume the payment


class LedgerEntry(Base):
    """Append-only. Corrections are new entries."""
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # capture | usage | refund
    amount_cents: Mapped[int] = mapped_column(Integer)  # signed
    idempotency_key: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebhookEvent(Base):
    """Insert-only. The primary key makes webhook handling idempotent."""
    __tablename__ = "webhook_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TrainingRun(Stamped, Base):
    __tablename__ = "training_runs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    backend: Mapped[str] = mapped_column(String)
    instance_type: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running", index=True)  # running | done | stopped | failed
    progress_stage: Mapped[str] = mapped_column(String, default="getting ready")  # plain words for the UI
    progress_fraction: Mapped[float] = mapped_column(Float, default=0.0)
    stop_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)  # heartbeat, used by crash recovery
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    stopped_at_cap: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Model(Stamped, Base):
    __tablename__ = "models"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    training_run_id: Mapped[str] = mapped_column(ForeignKey("training_runs.id"))
    storage_key: Mapped[str] = mapped_column(String)
    quality: Mapped[dict] = mapped_column(JSON)
    visibility: Mapped[str] = mapped_column(String, default="private")


class AgentRun(Stamped, Base):
    __tablename__ = "agent_runs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="running")
    steps_used: Mapped[int] = mapped_column(Integer, default=0)


class AgentStep(Stamped, Base):
    """Trace: user/assistant messages, tool calls and results, gate decisions."""
    __tablename__ = "agent_steps"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String)  # user | assistant | tool_call | tool_result | gate
    content: Mapped[dict] = mapped_column(JSON)


class SpendBudget(Base):
    """Single row (id=1): running total of actual AWS spend."""
    __tablename__ = "spend_budget"
    id: Mapped[int] = mapped_column(primary_key=True)
    spent_cents: Mapped[int] = mapped_column(Integer, default=0)


class FundingCampaign(Stamped, Base):
    """Stretch. Simulated."""
    __tablename__ = "funding_campaigns"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    goal_cents: Mapped[int] = mapped_column(Integer)
    raised_cents: Mapped[int] = mapped_column(Integer, default=0)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license_note: Mapped[str | None] = mapped_column(String, nullable=True)


class Contribution(Stamped, Base):
    __tablename__ = "contributions"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("funding_campaigns.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
