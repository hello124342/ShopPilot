from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class StageStatus(StrEnum):
    LOCKED = "locked"
    READY = "ready"
    RUNNING = "running"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUIRED = "revision_required"
    FAILED = "failed"
    SKIPPED = "skipped"

STAGE_DEFINITIONS: tuple[tuple[str, str], ...] = (("input", "输入"), ("research", "市场调研"), ("strategy", "策略"), ("creative", "创意"), ("compliance", "合规"), ("advertisement", "广告交付"), ("publish_review", "发布审批"), ("analytics", "效果分析"), ("optimization", "优化实验"))

class StageRun(BaseModel):
    stage_id: str
    run_id: str
    sequence: int = Field(ge=0)
    name: str
    status: StageStatus
    version: int = Field(default=1, ge=1)
    agent_ids: list[str] = Field(default_factory=list)
    artifact_kinds: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    asset_count: int = 0
    error: str | None = None
    feedback: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

class StageApproval(BaseModel):
    approval_id: str
    run_id: str
    stage_id: str
    stage_version: int
    decision: str
    feedback: str = ""
    created_at: datetime = Field(default_factory=utc_now)

def initial_stages(run_id: str) -> list[StageRun]:
    return [StageRun(stage_id=stage_id, run_id=run_id, sequence=index, name=name, status=StageStatus.APPROVED if index == 0 else StageStatus.LOCKED) for index, (stage_id, name) in enumerate(STAGE_DEFINITIONS)]

def stage_graph(stages: list[StageRun]) -> dict[str, Any]:
    return {"nodes": [item.model_dump(mode="json") for item in stages], "edges": [{"from": stages[i].stage_id, "to": stages[i + 1].stage_id} for i in range(max(0, len(stages) - 1))]}
