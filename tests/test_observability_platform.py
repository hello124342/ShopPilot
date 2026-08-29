from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Iterator

from agno.agent import Agent
from agno.models.base import Model
from agno.models.response import ModelResponse

from shopilot.observability import (
    AgnoEventBridge,
    LocalOnlyExporter,
    OpenTelemetryExporter,
    TraceRedactor,
    TraceStore,
)
from shopilot.runtime import AgnoRuntimeFactory


@dataclass
class OfflineModel(Model):
    id: str = "offline-events"
    name: str = "Offline event model"
    provider: str = "test"

    def invoke(self, *_: Any, **__: Any) -> ModelResponse:
        return ModelResponse(content="ok")

    async def ainvoke(self, *_: Any, **__: Any) -> ModelResponse:
        return ModelResponse(content="ok")

    def invoke_stream(self, *_: Any, **__: Any) -> Iterator[ModelResponse]:
        yield ModelResponse(content="ok")

    async def ainvoke_stream(self, *_: Any, **__: Any) -> AsyncIterator[ModelResponse]:
        yield ModelResponse(content="ok")

    def _parse_provider_response(self, response: Any, **__: Any) -> ModelResponse:
        return ModelResponse(content=str(response))

    def _parse_provider_response_delta(self, response: Any) -> ModelResponse:
        return ModelResponse(content=str(response))


def test_actual_agno_agent_workflow_and_team_events_are_bridgeable(tmp_path):
    store = TraceStore(tmp_path / "trace.db")
    bridge = AgnoEventBridge(store)
    context = {"run_id": "campaign-1", "tenant_id": "tenant-a", "trace_id": "trace-1"}

    agent = Agent(id="event-agent", model=OfflineModel(), stream_events=True, telemetry=False)
    agent_events = list(agent.run("test", stream=True, stream_events=True))
    for event in agent_events:
        bridge.consume(event, context=context)

    components = AgnoRuntimeFactory().build(OfflineModel())
    workflow_events = list(components.campaign_workflow.run({"test": True}, stream=True))
    for event in workflow_events:
        bridge.consume(event, context=context)

    assert agent_events[0].run_id
    assert components.research_team.stream_events
    assert components.research_team.stream_member_events
    assert components.agents["product"].stream_events
    names = [event.event_type for event in store.events("campaign-1", tenant_id="tenant-a")]
    assert "RunStarted" in names and "RunCompleted" in names
    assert "WorkflowStarted" in names and "WorkflowCompleted" in names


def test_hierarchy_metrics_retries_errors_and_redaction(tmp_path):
    store = TraceStore(tmp_path / "trace.db")
    bridge = AgnoEventBridge(store, TraceRedactor(["configured-secret"]))
    base = {"run_id": "campaign", "tenant_id": "tenant", "trace_id": "trace"}

    team = bridge.consume(
        {"event": "TeamRunStarted", "run_id": "team-run", "team_id": "research"},
        context=base,
    )
    member = bridge.consume(
        {"event": "RunStarted", "run_id": "member-run", "agent_id": "product"},
        context=base | {"parent_span_id": team.span_id, "team_run_id": "team-run"},
    )
    tool_context = base | {
        "parent_span_id": member.span_id,
        "team_run_id": "team-run",
        "member_run_id": "member-run",
        "agent_id": "product@1.0.0",
        "tool_version": "1.0.0",
        "mcp_server_id": "search-mcp@1.0.0",
        "evidence_ids": ["ev-1"],
        "asset_refs": ["asset-1@1"],
    }
    bridge.consume(
        {
            "event": "ToolCallStarted",
            "run_id": "member-run",
            "agent_id": "product",
            "tool_call_id": "tool-1",
            "tool_name": "search",
            "tool_args": {"authorization": "Bearer configured-secret"},
        },
        context=tool_context | {"attempt": 1},
    )
    bridge.consume(
        {
            "event": "ToolCallError",
            "run_id": "member-run",
            "agent_id": "product",
            "tool_call_id": "tool-1",
            "tool_name": "search",
            "error": "timeout sk-123456789",
        },
        context=tool_context | {"attempt": 1},
    )
    bridge.consume(
        {"event": "ToolCallStarted", "tool_call_id": "tool-1", "tool_name": "search"},
        context=tool_context | {"attempt": 2},
    )
    bridge.consume(
        {
            "event": "ToolCallCompleted",
            "tool_call_id": "tool-1",
            "tool_name": "search",
            "tool_result": "Bearer configured-secret",
        },
        context=tool_context | {"attempt": 2},
    )
    bridge.consume(
        {"event": "ModelRequestStarted", "agent_id": "product", "run_id": "member-run"},
        context=base | {"parent_span_id": member.span_id, "provider": "test", "model_id": "offline"},
    )
    bridge.consume(
        {
            "event": "ModelRequestCompleted",
            "agent_id": "product",
            "run_id": "member-run",
            "metrics": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14, "cost": 0.02},
        },
        context=base | {"parent_span_id": member.span_id, "provider": "test", "model_id": "offline"},
    )
    bridge.consume(
        {"event": "RunCompleted", "run_id": "member-run", "agent_id": "product"},
        context=base | {"parent_span_id": team.span_id},
    )
    bridge.consume(
        {"event": "TeamRunCompleted", "run_id": "team-run", "team_id": "research"},
        context=base,
    )

    spans = store.spans("campaign", tenant_id="tenant")
    serialized_events = "".join(item.model_dump_json() for item in store.events("campaign", tenant_id="tenant"))
    aggregate = store.aggregate(tenant_id="tenant")
    assert any(span.parent_span_id == team.span_id for span in spans)
    assert len([span for span in spans if span.name == "ToolCall"]) == 2
    assert aggregate["error_count"] >= 1
    assert aggregate["total_tokens"] == 14 and aggregate["estimated_cost"] == 0.02
    assert "configured-secret" not in serialized_events and "sk-123456789" not in serialized_events
    assert "[REDACTED]" in serialized_events


def test_trace_pagination_retention_and_exporters(tmp_path):
    store = TraceStore(tmp_path / "trace.db")
    bridge = AgnoEventBridge(store)
    context = {"run_id": "run", "trace_id": "trace"}
    bridge.consume({"event": "RunStarted", "agent_id": "a"}, context=context)
    bridge.consume({"event": "RunCompleted", "agent_id": "a"}, context=context)
    assert len(store.events("run", limit=1)) == 1
    assert len(store.events("run", limit=1, offset=1)) == 1

    span = store.spans("run")[0]
    LocalOnlyExporter().export(span)

    class Target:
        def set_attribute(self, *_):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    class Tracer:
        def start_as_current_span(self, name):
            assert name == "Run"
            return Target()

    OpenTelemetryExporter(Tracer()).export(span)
    assert store.prune(datetime.now(timezone.utc) + timedelta(seconds=1)) == 1
    assert store.spans("run") == []
