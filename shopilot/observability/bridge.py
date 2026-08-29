from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from .models import (
    Correlation,
    ModelCallMetrics,
    SpanKind,
    SpanStatus,
    ToolCallRecord,
    TraceEvent,
    TraceSpan,
)
from .redaction import TraceRedactor
from .store import TraceStore


class AgnoEventBridge:
    def __init__(self, store: TraceStore, redactor: TraceRedactor | None = None):
        self.store = store
        self.redactor = redactor or TraceRedactor()
        self._open: dict[tuple[str, str, str], TraceSpan] = {}
        self._sequences: dict[str, int] = {}

    @staticmethod
    def _payload(event: Any) -> dict[str, Any]:
        if isinstance(event, BaseModel):
            return event.model_dump(mode="json")
        if hasattr(event, "to_dict"):
            return event.to_dict()
        if isinstance(event, dict):
            return dict(event)
        return {key: value for key, value in vars(event).items() if not key.startswith("_")}

    @staticmethod
    def _event_name(payload: dict[str, Any]) -> str:
        value = payload.get("event") or payload.get("event_type") or payload.get("type") or "Unknown"
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _base_name(name: str) -> str:
        for suffix in ("Started", "Completed", "Error", "Cancelled"):
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return name

    @staticmethod
    def _kind(name: str) -> SpanKind:
        if "ToolCall" in name:
            return SpanKind.TOOL
        if "ModelRequest" in name or "ModelResponse" in name:
            return SpanKind.MODEL
        if name.startswith("Workflow"):
            return SpanKind.WORKFLOW
        if name.startswith("Step"):
            return SpanKind.STAGE
        if name.startswith("Team"):
            return SpanKind.TEAM
        return SpanKind.AGENT

    @staticmethod
    def _status(name: str) -> SpanStatus:
        if name.endswith("Error"):
            return SpanStatus.ERROR
        if name.endswith("Cancelled"):
            return SpanStatus.CANCELLED
        if name.endswith("Completed"):
            return SpanStatus.OK
        return SpanStatus.RUNNING

    def consume(self, event: Any, *, context: dict[str, Any]) -> TraceEvent:
        raw = self._payload(event)
        name = self._event_name(raw)
        run_id = context["run_id"]
        tenant_id = context.get("tenant_id", "default")
        trace_id = context.get("trace_id") or f"trace_{uuid4().hex}"
        agno_run_id = raw.get("run_id") or context.get("agno_run_id")
        component_id = str(
            raw.get("tool_call_id")
            or raw.get("agent_id")
            or raw.get("team_id")
            or raw.get("workflow_id")
            or agno_run_id
            or run_id
        )
        key = (trace_id, component_id, self._base_name(name))
        parent_span_id = context.get("parent_span_id")
        span = self._open.get(key)
        if name.endswith("Started"):
            span = TraceSpan(
                parent_span_id=parent_span_id,
                correlation=Correlation(
                    trace_id=trace_id,
                    shopilot_run_id=run_id,
                    tenant_id=tenant_id,
                    agno_run_id=agno_run_id,
                    workflow_run_id=context.get("workflow_run_id"),
                    team_run_id=context.get("team_run_id") or raw.get("team_id"),
                    member_run_id=context.get("member_run_id"),
                    agent_id=raw.get("agent_id") or context.get("agent_id"),
                    tool_call_id=raw.get("tool_call_id"),
                ),
                kind=self._kind(name),
                name=self._base_name(name),
                attributes=self.redactor.redact(context.get("attributes", {})),
                artifact_ids=context.get("artifact_ids", []),
                evidence_ids=context.get("evidence_ids", []),
                asset_refs=context.get("asset_refs", []),
            )
            self._open[key] = span
            self.store.put_span(span)
        elif self._status(name) != SpanStatus.RUNNING:
            if span is None:
                span = TraceSpan(
                    parent_span_id=parent_span_id,
                    correlation=Correlation(
                        trace_id=trace_id,
                        shopilot_run_id=run_id,
                        tenant_id=tenant_id,
                        agno_run_id=agno_run_id,
                    ),
                    kind=self._kind(name),
                    name=self._base_name(name),
                )
            ended = datetime.now(timezone.utc)
            duration = max(0.0, (ended - span.started_at).total_seconds() * 1000)
            span = span.model_copy(
                update={"status": self._status(name), "ended_at": ended, "duration_ms": duration}
            )
            self.store.put_span(span)
            self._open.pop(key, None)

        sequence = self._sequences.get(run_id, 0)
        self._sequences[run_id] = sequence + 1
        safe_payload = self.redactor.redact(raw)
        canonical = TraceEvent(
            trace_id=trace_id,
            span_id=span.span_id if span else parent_span_id,
            run_id=run_id,
            tenant_id=tenant_id,
            event_type=name,
            sequence=sequence,
            payload=safe_payload,
        )
        self.store.put_event(canonical)
        if span and "ModelRequest" in name and name.endswith(("Completed", "Error")):
            metrics = raw.get("metrics") or {}
            self.store.put_model_metrics(
                ModelCallMetrics(
                    trace_id=trace_id,
                    span_id=span.span_id,
                    provider=raw.get("model_provider") or context.get("provider"),
                    model_id=raw.get("model") or context.get("model_id"),
                    provider_request_id=raw.get("provider_request_id"),
                    input_tokens=int(metrics.get("input_tokens", 0) or 0),
                    output_tokens=int(metrics.get("output_tokens", 0) or 0),
                    cached_tokens=int(metrics.get("cache_read_tokens", 0) or 0),
                    total_tokens=int(metrics.get("total_tokens", 0) or 0),
                    cost=float(metrics.get("cost", 0) or 0),
                    duration_ms=span.duration_ms or 0,
                    retry_attempt=int(context.get("attempt", 1)),
                    status=span.status,
                )
            )
        if span and "ToolCall" in name and name.endswith(("Completed", "Error")):
            self.store.put_tool_call(
                ToolCallRecord(
                    trace_id=trace_id,
                    span_id=span.span_id,
                    tool_call_id=str(raw.get("tool_call_id") or component_id),
                    tool_name=str(raw.get("tool_name") or raw.get("tool") or "unknown"),
                    tool_version=context.get("tool_version"),
                    mcp_server_id=context.get("mcp_server_id"),
                    attempt=int(context.get("attempt", 1)),
                    status=span.status,
                    duration_ms=span.duration_ms or 0,
                    input=self.redactor.redact(raw.get("tool_args") or {}),
                    output=self.redactor.redact(raw.get("tool_result")),
                    error_code=raw.get("error") if span.status == SpanStatus.ERROR else None,
                )
            )
        return canonical
