from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

class User(Base, TenantMixin, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"user_{uuid.uuid4().hex}")
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)

class Session(Base, TenantMixin):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Campaign(Base, TenantMixin, TimestampMixin):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"campaign_{uuid.uuid4().hex}")
    name: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)

class CampaignRun(Base, TenantMixin, TimestampMixin):
    __tablename__ = "campaign_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"run_{uuid.uuid4().hex}")
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    runtime_mode: Mapped[str] = mapped_column(String(32), default="agno")
    agent_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    replayed_from_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)

class StageRun(Base, TenantMixin, TimestampMixin):
    __tablename__ = "stage_runs"
    __table_args__ = (UniqueConstraint("run_id", "stage_id", "version", name="uq_stage_run_version"), Index("ix_stage_run_status", "tenant_id", "status"))
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"stage_{uuid.uuid4().hex}")
    run_id: Mapped[str] = mapped_column(ForeignKey("campaign_runs.id", ondelete="CASCADE"), index=True)
    stage_id: Mapped[str] = mapped_column(String(48))
    sequence: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="locked")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)

class StageApproval(Base, TenantMixin):
    __tablename__ = "stage_approvals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"approval_{uuid.uuid4().hex}")
    stage_run_id: Mapped[str] = mapped_column(ForeignKey("stage_runs.id", ondelete="CASCADE"), index=True)
    stage_version: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(24))
    feedback: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class CapabilityVersion(Base, TenantMixin):
    __tablename__ = "capability_versions"
    __table_args__ = (UniqueConstraint("kind", "capability_id", "version", name="uq_capability_version"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"cap_{uuid.uuid4().hex}")
    kind: Mapped[str] = mapped_column(String(24), index=True)
    capability_id: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(32))
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class CapabilityBinding(Base, TenantMixin):
    __tablename__ = "capability_bindings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"binding_{uuid.uuid4().hex}")
    agent_version_id: Mapped[str] = mapped_column(ForeignKey("capability_versions.id", ondelete="CASCADE"), index=True)
    capability_version_id: Mapped[str] = mapped_column(ForeignKey("capability_versions.id", ondelete="CASCADE"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class DomainRecord(Base, TenantMixin, TimestampMixin):
    """Immutable payload index for artifacts/evidence/assets/trace metadata."""
    __tablename__ = "domain_records"
    __table_args__ = (UniqueConstraint("kind", "record_id", "version", name="uq_domain_record_version"), Index("ix_domain_run_stage", "tenant_id", "run_id", "stage_run_id"))
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"record_{uuid.uuid4().hex}")
    kind: Mapped[str] = mapped_column(String(32), index=True)
    record_id: Mapped[str] = mapped_column(String(96), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stage_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)

class Job(Base, TenantMixin, TimestampMixin):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"job_{uuid.uuid4().hex}")
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    stage_run_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

class OutboxEvent(Base, TenantMixin):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"outbox_{uuid.uuid4().hex}")
    topic: Mapped[str] = mapped_column(String(120), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(96), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class AuditEvent(Base, TenantMixin):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"audit_{uuid.uuid4().hex}")
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(96), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
