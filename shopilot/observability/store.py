from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ModelCallMetrics, ToolCallRecord, TraceEvent, TraceSpan


class TraceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS trace_spans (
                    span_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL, parent_span_id TEXT, status TEXT NOT NULL,
                    started_at TEXT NOT NULL, ended_at TEXT, span_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_spans_run ON trace_spans (tenant_id, run_id, started_at);
                CREATE TABLE IF NOT EXISTS trace_events (
                    event_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL, sequence INTEGER NOT NULL, created_at TEXT NOT NULL,
                    event_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_run ON trace_events (tenant_id, run_id, sequence);
                CREATE TABLE IF NOT EXISTS model_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL, span_id TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT NOT NULL, span_id TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL, record_json TEXT NOT NULL
                );
                """
            )

    def put_span(self, span: TraceSpan) -> TraceSpan:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO trace_spans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    span.span_id,
                    span.correlation.trace_id,
                    span.correlation.shopilot_run_id,
                    span.correlation.tenant_id,
                    span.parent_span_id,
                    span.status.value,
                    span.started_at.isoformat(),
                    span.ended_at.isoformat() if span.ended_at else None,
                    span.model_dump_json(),
                ),
            )
        return span

    def put_event(self, event: TraceEvent) -> TraceEvent:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO trace_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.trace_id,
                    event.run_id,
                    event.tenant_id,
                    event.sequence,
                    event.created_at.isoformat(),
                    event.model_dump_json(),
                ),
            )
        return event

    def put_model_metrics(self, metrics: ModelCallMetrics) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO model_metrics (trace_id, span_id, metrics_json) VALUES (?, ?, ?)",
                (metrics.trace_id, metrics.span_id, metrics.model_dump_json()),
            )

    def put_tool_call(self, record: ToolCallRecord) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO tool_calls (trace_id, span_id, tool_call_id, record_json) VALUES (?, ?, ?, ?)",
                (record.trace_id, record.span_id, record.tool_call_id, record.model_dump_json()),
            )

    def spans(self, run_id: str, *, tenant_id: str = "default", limit: int = 200, offset: int = 0) -> list[TraceSpan]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT span_json FROM trace_spans WHERE tenant_id=? AND run_id=? ORDER BY started_at LIMIT ? OFFSET ?",
                (tenant_id, run_id, limit, offset),
            ).fetchall()
        return [TraceSpan.model_validate_json(row["span_json"]) for row in rows]

    def events(self, run_id: str, *, tenant_id: str = "default", limit: int = 500, offset: int = 0) -> list[TraceEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_json FROM trace_events WHERE tenant_id=? AND run_id=? ORDER BY sequence LIMIT ? OFFSET ?",
                (tenant_id, run_id, limit, offset),
            ).fetchall()
        return [TraceEvent.model_validate_json(row["event_json"]) for row in rows]

    def aggregate(self, *, tenant_id: str = "default") -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT span_json FROM trace_spans WHERE tenant_id=?",
                (tenant_id,),
            ).fetchall()
            metrics_rows = connection.execute(
                "SELECT metrics_json FROM model_metrics"
            ).fetchall()
        spans = [TraceSpan.model_validate_json(row["span_json"]) for row in rows]
        metrics = [ModelCallMetrics.model_validate_json(row["metrics_json"]) for row in metrics_rows]
        durations = [span.duration_ms for span in spans if span.duration_ms is not None]
        return {
            "span_count": len(spans),
            "error_count": sum(span.status.value == "error" for span in spans),
            "average_latency_ms": sum(durations) / len(durations) if durations else 0,
            "total_tokens": sum(item.total_tokens for item in metrics),
            "estimated_cost": sum(item.cost for item in metrics),
        }

    def prune(self, ended_before: datetime, *, tenant_id: str = "default") -> int:
        with self._connect() as connection:
            trace_rows = connection.execute(
                "SELECT DISTINCT trace_id FROM trace_spans WHERE tenant_id=? AND ended_at IS NOT NULL AND ended_at<?",
                (tenant_id, ended_before.isoformat()),
            ).fetchall()
            trace_ids = [row["trace_id"] for row in trace_rows]
            for trace_id in trace_ids:
                connection.execute("DELETE FROM trace_events WHERE trace_id=?", (trace_id,))
                connection.execute("DELETE FROM model_metrics WHERE trace_id=?", (trace_id,))
                connection.execute("DELETE FROM tool_calls WHERE trace_id=?", (trace_id,))
                connection.execute("DELETE FROM trace_spans WHERE trace_id=?", (trace_id,))
        return len(trace_ids)
