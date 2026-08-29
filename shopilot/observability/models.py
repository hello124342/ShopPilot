from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SpanKind(StrEnum):
    CAMPAIGN = "campaign"
    WORKFLOW = "workflow"
    STAGE = "stage"
    TEAM = "team"
    AGENT = "agent"
    MODEL = "model"
    TOOL = "tool"
    MCP = "mcp"
    EXTERNAL = "external"


class SpanStatus(StrEnum):
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


class Correlation(BaseModel):
    trace_id: str
    shopilot_run_id: str
    tenant_id: str = "default"
    agno_run_id: str | None = None
    workflow_run_id: str | None = None
    team_run_id: str | None = None
    member_run_id: str | None = None
    agent_id: str | None = None
    tool_call_id: str | None = None


class TraceSpan(BaseModel):
    span_id: str = Field(default_factory=lambda: f"span_{uuid4().hex}")
    parent_span_id: str | None = None
    correlation: Correlation
    kind: SpanKind
    name: str
    status: SpanStatus = SpanStatus.RUNNING
    started_at: datetime = Field(default_factory=utc_now)
    ended_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)
    artifact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    asset_refs: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"event_{uuid4().hex}")
    trace_id: str
    span_id: str | None = None
    run_id: str
    tenant_id: str = "default"
    event_type: str
    source: str = "agno"
    sequence: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ModelCallMetrics(BaseModel):
    trace_id: str
    span_id: str
    provider: str | None = None
    model_id: str | None = None
    provider_request_id: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    duration_ms: float = Field(default=0, ge=0)
    retry_attempt: int = Field(default=1, ge=1)
    status: SpanStatus


class ToolCallRecord(BaseModel):
    trace_id: str
    span_id: str
    tool_call_id: str
    tool_name: str
    tool_version: str | None = None
    mcp_server_id: str | None = None
    attempt: int = Field(default=1, ge=1)
    status: SpanStatus
    duration_ms: float = Field(default=0, ge=0)
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    error_code: str | None = None
