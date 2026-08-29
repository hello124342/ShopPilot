from __future__ import annotations

from typing import Protocol

from .models import TraceSpan


class SpanExporter(Protocol):
    def export(self, span: TraceSpan) -> None: ...


class LocalOnlyExporter:
    def export(self, span: TraceSpan) -> None:
        return None


class OpenTelemetryExporter:
    """Optional adapter; OpenTelemetry packages are not required for local mode."""

    def __init__(self, tracer=None):
        if tracer is None:
            try:
                from opentelemetry import trace
            except ImportError as exc:
                raise RuntimeError("opentelemetry_not_installed") from exc
            tracer = trace.get_tracer("shopilot")
        self.tracer = tracer

    def export(self, span: TraceSpan) -> None:
        with self.tracer.start_as_current_span(span.name) as target:
            target.set_attribute("shopilot.trace_id", span.correlation.trace_id)
            target.set_attribute("shopilot.run_id", span.correlation.shopilot_run_id)
            target.set_attribute("shopilot.kind", span.kind.value)
            target.set_attribute("shopilot.status", span.status.value)
