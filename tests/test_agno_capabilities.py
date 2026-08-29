from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterator

from agno.agent import Agent
from agno.db.base import SessionType
from agno.db.sqlite import SqliteDb
from agno.media.storage.local import LocalMediaStorage
from agno.metrics import RunMetrics
from agno.models.base import Model
from agno.models.response import ModelResponse
from agno.run.workflow import WorkflowRunEvent
from agno.session.agent import AgentSession
from agno.skills import Skills
from agno.skills.loaders.local import LocalSkills
from agno.team import Team
from agno.team.mode import TeamMode
from agno.tools import Toolkit
from agno.tools.mcp import MCPTools
from agno.workflow import Step, Workflow
from agno.workflow.types import StepOutput
from mcp.types import ListToolsResult, Tool


@dataclass
class OfflineModel(Model):
    """Deterministic Model used only to execute Agno primitives offline."""

    id: str = "offline-smoke"
    name: str = "Offline smoke model"
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


def echo(value: str) -> str:
    return value


def test_agent_skills_and_toolkit_smoke(tmp_path):
    skill_dir = tmp_path / "research-smoke"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: research-smoke\ndescription: Offline audit skill\n---\n"
        "Use normalized evidence only.\n",
        encoding="utf-8",
    )

    skills = Skills(loaders=[LocalSkills(str(skill_dir))])
    toolkit = Toolkit(name="audit-tools", tools=[echo])
    agent = Agent(
        id="audit-agent",
        model=OfflineModel(),
        skills=skills,
        tools=[toolkit],
        telemetry=False,
    )

    assert agent.skills is skills
    assert skills.get_skill_names() == ["research-smoke"]
    assert list(toolkit.functions) == ["echo"]
    assert agent.run("smoke").content == "ok"


def test_team_broadcast_arun_smoke():
    members = [
        Agent(id=f"member-{index}", model=OfflineModel(), telemetry=False)
        for index in range(2)
    ]
    team = Team(
        id="audit-team",
        members=members,
        model=OfflineModel(),
        mode=TeamMode.broadcast,
        store_member_responses=True,
        stream_member_events=True,
        telemetry=False,
    )

    response = asyncio.run(team.arun("smoke"))

    assert team.mode == TeamMode.broadcast
    assert response.content == "ok"
    assert response.team_id == "audit-team"
    assert response.run_id


def test_workflow_and_event_stream_smoke():
    workflow = Workflow(
        id="audit-workflow",
        steps=[
            Step(
                name="offline-step",
                executor=lambda _: StepOutput(step_name="offline-step", content="ok"),
            )
        ],
        stream_events=True,
        telemetry=False,
    )

    events = list(workflow.run({"smoke": True}, stream=True))
    event_types = [event.event for event in events]

    assert event_types[0] == WorkflowRunEvent.workflow_started.value
    assert WorkflowRunEvent.step_started.value in event_types
    assert event_types[-1] == WorkflowRunEvent.workflow_completed.value
    assert events[-1].run_id


def test_mcp_toolkit_initializes_allowlisted_tool_without_network():
    class FakeSession:
        initialized = False

        async def initialize(self):
            self.initialized = True

        async def list_tools(self):
            return ListToolsResult(
                tools=[
                    Tool(
                        name="search",
                        description="Offline search fixture",
                        inputSchema={"type": "object", "properties": {}},
                    ),
                    Tool(
                        name="write",
                        description="Must remain filtered",
                        inputSchema={"type": "object", "properties": {}},
                    ),
                ]
            )

    session = FakeSession()
    toolkit = MCPTools(session=session, include_tools=["search"], timeout_seconds=3)

    asyncio.run(toolkit.initialize())

    assert session.initialized
    assert list(toolkit.functions) == ["search"]
    assert toolkit.timeout_seconds == 3


def test_local_media_storage_round_trip(tmp_path):
    storage = LocalMediaStorage(base_path=str(tmp_path / "media"))

    key = storage.upload(
        "asset-smoke",
        b"shopilot",
        filename="audit.txt",
        mime_type="text/plain",
    )

    assert storage.exists(key)
    assert storage.download(key) == b"shopilot"
    assert storage.get_url(key) is None
    assert storage.delete(key)
    assert not storage.exists(key)


def test_metrics_and_sqlite_session_smoke(tmp_path):
    metrics = RunMetrics(
        input_tokens=10,
        output_tokens=4,
        total_tokens=14,
        cost=0.001,
        duration=0.25,
    )
    assert metrics.total_tokens == 14
    assert metrics.cost == 0.001

    db = SqliteDb(db_file=str(tmp_path / "agno-smoke.db"))
    session = AgentSession(
        session_id="session-smoke",
        agent_id="audit-agent",
        user_id="tenant-user",
        metadata={"purpose": "capability-audit"},
    )
    db.upsert_session(session)
    loaded = db.get_session(
        "session-smoke",
        session_type=SessionType.AGENT,
        user_id="tenant-user",
    )

    assert loaded is not None
    assert loaded.agent_id == "audit-agent"
    assert loaded.metadata == {"purpose": "capability-audit"}
