from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

from .assets.models import AssetReference

def now() -> datetime: return datetime.now(timezone.utc)

class CampaignInput(BaseModel):
    product: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)

class Evidence(BaseModel):
    claim: str
    source: str
    confidence: float = Field(ge=0, le=1)
    evidence_id: str | None = None
    content_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    subject: str | None = None
    tool_call_id: str | None = None

class ResearchPackage(BaseModel):
    product_facts: list[str] = Field(default_factory=list)
    audience_insights: list[str] = Field(default_factory=list)
    competitor_observations: list[str] = Field(default_factory=list)
    trend_signals: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    evidence_record_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    citation_coverage: float = Field(default=0, ge=0, le=1)

class CampaignBrief(BaseModel):
    goal: str
    audience: str
    core_selling_point: str
    creative_angles: list[str]
    platform: str
    cta: str
    success_metrics: list[str]
    test_hypothesis: str
    evidence_refs: list[str] = Field(default_factory=list)

class CreativeVariant(BaseModel):
    angle: str
    title: str
    body: str
    cta: str
    hashtags: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    target_metric: str

class CreativePackage(BaseModel):
    variants: list[CreativeVariant]
    visual_brief: str
    video_script: str

class PlatformPayload(BaseModel):
    platform: str
    title: str
    body: str
    media: list[AssetReference | str] = Field(default_factory=list)
    cta: str
    artifact_version: int = 1

class ComplianceReport(BaseModel):
    passed: bool
    status: Literal["passed", "revision_required"]
    risks: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

class Metrics(BaseModel):
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    conversions: int = Field(ge=0)
    cost: float = Field(ge=0)
    revenue: float = Field(ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)

class PerformanceReport(BaseModel):
    metrics: Metrics
    derived: dict[str, float]
    observations: list[str]
    hypotheses: list[str]
    recommendations: list[str]
    evidence: list[str]

class OptimizationBrief(BaseModel):
    observation: str
    hypothesis: str
    change_variable: str
    keep_constant: str
    next_action: str
    success_metric: str

class Artifact(BaseModel):
    kind: str
    version: int
    data: dict[str, Any]
    created_at: datetime = Field(default_factory=now)

class TraceEvent(BaseModel):
    run_id: str
    sequence: int
    stage: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0
    cost: float = 0
    model_version: str = "deterministic-mock"
    prompt_version: str = "v1"
    created_at: datetime = Field(default_factory=now)

class ApprovalEvent(BaseModel):
    run_id: str
    artifact_version: int
    asset_versions: dict[str, int] = Field(default_factory=dict)
    decision: Literal["approved", "rejected"]
    feedback: str = ""
    created_at: datetime = Field(default_factory=now)

class EvaluationReport(BaseModel):
    passed: bool
    checks: dict[str, bool]
    metrics: dict[str, float]
    failures: list[str] = Field(default_factory=list)

class RunRecord(BaseModel):
    replay_mode: Literal["live_external", "recorded", "recompute_local"] = "live_external"
    run_id: str
    status: str = "pending"
    campaign: dict[str, Any]
    runtime_mode: Literal["mock", "agno"] = "mock"
    side_effect_mode: Literal["disabled", "mock", "real"] = "mock"
    current_artifact_version: int = 1
    error: str | None = None
    replayed_from: str | None = None
    provider: str = "deterministic"
    model_id: str = "deterministic-mock"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
