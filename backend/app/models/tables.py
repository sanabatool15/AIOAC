"""Database schema. See docs/architecture.md for the diagram.

Money is stored as integer cents. Ledger and webhook rows are insert-only.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    described = "described"
    data_checked = "data_checked"
    baseline_done = "baseline_done"
    quoted = "quoted"
    awaiting_payment = "awaiting_payment"
    paid = "paid"          # set only after SERVER-confirmed capture
    training = "training"
    done = "done"
    failed = "failed"
    refunded = "refunded"


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.described)
    dataset_path: Mapped[str | None] = mapped_column(String, nullable=True)
    readiness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    instance_type: Mapped[str] = mapped_column(String)
    estimated_cost_cents: Mapped[int] = mapped_column(Integer)  # an estimate
    spend_cap_cents: Mapped[int] = mapped_column(Integer)       # hard cap
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    provider: Mapped[str] = mapped_column(String)
    provider_order_id: Mapped[str] = mapped_column(String, unique=True)
    provider_capture_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    captured_confirmed: Mapped[bool] = mapped_column(default=False)  # server-verified only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LedgerEntry(Base):
    """Append-only. Never update or delete. Corrections are new entries."""
    __tablename__ = "ledger_entries"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String)  # capture | usage | refund
    amount_cents: Mapped[int] = mapped_column(Integer)  # signed: capture +, usage -, refund -
    idempotency_key: Mapped[str] = mapped_column(String)  # e.g. capture id / refund id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebhookEvent(Base):
    """Insert-only. Unique event_id makes webhook handling idempotent."""
    __tablename__ = "webhook_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
