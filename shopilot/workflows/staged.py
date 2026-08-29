from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..agents import AnalyticsAgent, ComplianceAgent, OptimizationAgent, PlatformAdapterAgent, StrategyAgent
from ..assets import AssetReference
from ..domain.stage_store import StageStore
from ..domain.stages import StageApproval, StageRun, StageStatus, initial_stages
from ..runtime.providers import RuntimeMode
from ..schemas import CampaignBrief, CampaignInput, ComplianceReport, CreativePackage, PerformanceReport, PlatformPayload, ResearchPackage, RunRecord
from ..teams import ResearchTeam
from ..tools import MetricsTool, PolicyTool
from .campaign import CampaignWorkflow
from .creative import CreativeWorkflow


STAGE_AGENTS: dict[str, list[str]] = {
    "input": [],
    "research": ["product", "competitor", "audience", "trend", "evidence"],
    "strategy": ["strategy"],
    "creative": ["creative"],
    "compliance": ["compliance"],
    "advertisement": ["creative"],
    "publish_review": [],
    "analytics": ["analytics"],
    "optimization": ["optimization"],
}

STAGE_ARTIFACTS: dict[str, list[str]] = {
    "research": ["ResearchPackage"],
    "strategy": ["CampaignBrief"],
    "creative": ["CreativePackage"],
    "compliance": ["ComplianceReport"],
    "advertisement": ["PlatformPayload"],
    "analytics": ["PerformanceReport"],
    "optimization": ["OptimizationBrief"],
}


class StagedCampaignWorkflow:
    """Business gate around fixed Agno primitives.

    This class owns stage state and approvals only. Model, Team and tool
    execution remains delegated to CampaignWorkflow's Agno factory and native
    Agent/Team components.
    """

    def __init__(self, workflow: CampaignWorkflow, stage_store: StageStore):
        self.workflow = workflow
        self.store = workflow.store
        self.stage_store = stage_store

    def _save(self, stages: list[StageRun]) -> None:
        self.stage_store.save(stages[0].run_id, stages)

    def _stage(self, run_id: str, stage_id: str) -> tuple[list[StageRun], StageRun]:
        stages = self.stage_store.get(run_id)
        stage = next((item for item in stages if item.stage_id == stage_id), None)
        if stage is None:
            raise ValueError("stage_not_found")
        return stages, stage

    def _latest(self, run_id: str, kind: str, schema):
        values = [item for item in self.store.read(run_id, "artifacts.jsonl") if item["kind"] == kind]
        if not values:
            raise ValueError(f"{kind}_not_found")
        return schema.model_validate(values[-1]["data"])

    def start(self, campaign: CampaignInput, *, run_id: str | None = None) -> dict:
        run_id = run_id or uuid.uuid4().hex
        record = RunRecord(
            run_id=run_id,
            campaign=campaign.model_dump(),
            runtime_mode=self.workflow.settings.runtime_mode,
            side_effect_mode=self.workflow.settings.side_effect_mode,
            provider=self.workflow.settings.provider if self.workflow.settings.runtime_mode == RuntimeMode.AGNO else "deterministic",
            model_id=self.workflow.settings.model_id if self.workflow.settings.runtime_mode == RuntimeMode.AGNO else self.workflow.config.model_version,
            status="running",
        )
        self.store.save_run(record)
        stages = initial_stages(run_id)
        for stage in stages:
            stage.agent_ids = STAGE_AGENTS[stage.stage_id]
            stage.artifact_kinds = STAGE_ARTIFACTS.get(stage.stage_id, [])
        stages[1].status = StageStatus.READY
        self._save(stages)
        self.workflow._event(run_id, "run", "started", {"execution_model": "stage-gated", "runtime_mode": self.workflow.settings.runtime_mode})
        self.execute(run_id, "research")
        return self.store.get_run(run_id)

    def execute(self, run_id: str, stage_id: str) -> dict:
        stages, stage = self._stage(run_id, stage_id)
        if stage.status not in {StageStatus.READY, StageStatus.REVISION_REQUIRED, StageStatus.FAILED}:
            raise ValueError("stage_not_executable")
        stage.status = StageStatus.RUNNING
        stage.started_at = datetime.now(timezone.utc)
        stage.error = None
        self._save(stages)
        raw = self.store.get_run(run_id)
        if raw is None:
            raise ValueError("run_not_found")
        record = RunRecord.model_validate(raw)
        campaign = CampaignInput.model_validate(record.campaign)
        record.status = "running"
        record.updated_at = datetime.now(timezone.utc)
        self.store.save_run(record)
        self.workflow._event(run_id, stage_id, "stage_started", {"stage_version": stage.version, "agents": stage.agent_ids})
        try:
            self._execute_payload(run_id, stage_id, campaign, stage.version)
            stage.status = StageStatus.PENDING_REVIEW
            stage.completed_at = datetime.now(timezone.utc)
            stage.updated_at = stage.completed_at
            record.status = "waiting_review"
            record.updated_at = stage.completed_at
            self.workflow._event(run_id, stage_id, "stage_pending_review", {"stage_version": stage.version})
        except Exception as exc:
            stage.status = StageStatus.FAILED
            stage.error = getattr(exc, "code", type(exc).__name__)
            stage.completed_at = datetime.now(timezone.utc)
            record.status = "failed"
            record.error = stage.error
            self.workflow._event(run_id, stage_id, "stage_error", {"error_code": stage.error, "stage_version": stage.version})
        self._save(stages)
        self.store.save_run(record)
        return {"run": self.store.get_run(run_id), "stage": stage.model_dump(mode="json")}

    def _execute_payload(self, run_id: str, stage_id: str, campaign: CampaignInput, version: int) -> None:
        agno = self.workflow.agno
        if stage_id == "research":
            if agno:
                response = self.workflow._run_agno_research(campaign.model_dump(), run_id)
                result = self.workflow._agno_output(response, ResearchPackage)
            else:
                result = ResearchTeam().run(campaign)
            result = self.workflow._review_research(result, run_id)
            self.workflow._artifact(run_id, "ResearchPackage", result, version)
            report = self.workflow.document_exporter.export(
                {"research": result.model_dump(mode="json")}, run_id=run_id,
                tenant_id=self.workflow.settings.tenant_id,
            )
            self.workflow._event(run_id, stage_id, "asset_created", {"asset_id": report.asset_id, "version": report.version})
            return
        if stage_id == "strategy":
            research = self._latest(run_id, "ResearchPackage", ResearchPackage)
            result = self.workflow._agno_agent(run_id, stage_id, "strategy", CampaignBrief, {"campaign": campaign.model_dump(), "research": research.model_dump()}) if agno else StrategyAgent().run(campaign, research)
            self.workflow._artifact(run_id, "CampaignBrief", result, version)
            return
        if stage_id == "creative":
            brief = self._latest(run_id, "CampaignBrief", CampaignBrief)
            result = self.workflow._agno_agent(run_id, stage_id, "creative", CreativePackage, brief.model_dump()) if agno else CreativeWorkflow().run(brief)
            self.workflow._artifact(run_id, "CreativePackage", result, version)
            return
        if stage_id == "compliance":
            creative = self._latest(run_id, "CreativePackage", CreativePackage)
            payload = PlatformAdapterAgent().run(creative, campaign.platform)
            errors = PolicyTool().validate(payload)
            result = self.workflow._agno_agent(run_id, stage_id, "compliance", ComplianceReport, {"payload": payload.model_dump(), "deterministic_rule_errors": errors}) if agno else ComplianceAgent().run(payload, errors)
            self.workflow._artifact(run_id, "ComplianceReport", result, version)
            if not result.passed:
                raise ValueError("compliance_revision_required")
            return
        if stage_id == "advertisement":
            creative = self._latest(run_id, "CreativePackage", CreativePackage)
            payload = PlatformAdapterAgent().run(creative, campaign.platform).model_copy(update={"artifact_version": version})
            image = self.workflow.image_generator.generate(creative.visual_brief, run_id=run_id, tenant_id=self.workflow.settings.tenant_id)
            payload = payload.model_copy(update={"media": [AssetReference(asset_id=image.asset_id, version=image.version, role="creative-image")]})
            self.workflow._artifact(run_id, "PlatformPayload", payload, version)
            document = self.workflow.document_exporter.export({"advertisement": payload.model_dump(mode="json")}, run_id=run_id, tenant_id=self.workflow.settings.tenant_id)
            self.workflow._event(run_id, stage_id, "assets_created", {"assets": [image.asset_id, document.asset_id]})
            return
        if stage_id == "analytics":
            metrics = MetricsTool().get()
            result = self.workflow._agno_agent(run_id, stage_id, "analytics", PerformanceReport, metrics.model_dump()) if agno else AnalyticsAgent().run(metrics)
            self.workflow._artifact(run_id, "PerformanceReport", result, version)
            return
        if stage_id == "optimization":
            performance = self._latest(run_id, "PerformanceReport", PerformanceReport)
            result = self.workflow._agno_agent(run_id, stage_id, "optimization", __import__("shopilot.schemas", fromlist=["OptimizationBrief"]).OptimizationBrief, performance.model_dump()) if agno else OptimizationAgent().run(performance)
            self.workflow._artifact(run_id, "OptimizationBrief", result, version)
            return
        raise ValueError("stage_has_no_execution")

    def approve(self, run_id: str, stage_id: str, feedback: str = "") -> dict:
        stages, stage = self._stage(run_id, stage_id)
        if stage.status != StageStatus.PENDING_REVIEW:
            raise ValueError("stage_not_ready_for_review")
        approval = StageApproval(approval_id=f"stage_approval_{uuid.uuid4().hex}", run_id=run_id, stage_id=stage_id, stage_version=stage.version, decision="approved", feedback=feedback)
        approvals = self.stage_store.approvals(run_id)
        approvals.append(approval)
        self.stage_store.save_approvals(run_id, approvals)
        stage.status = StageStatus.APPROVED
        stage.feedback = feedback
        stage.updated_at = datetime.now(timezone.utc)
        self.workflow._event(run_id, stage_id, "stage_approved", {"stage_version": stage.version})
        if stage_id == "publish_review":
            payload = self._latest(run_id, "PlatformPayload", PlatformPayload)
            self.workflow.approvals.decide(run_id, payload, "approved", feedback)
            result = self.workflow.publisher.publish(payload, True, payload.artifact_version, run_id)
            self.workflow._event(run_id, "publish_review", "publish_completed", result)
        if stage.sequence + 1 >= len(stages):
            record = RunRecord.model_validate(self.store.get_run(run_id))
            record.status = "optimized"
            record.updated_at = datetime.now(timezone.utc)
            self.store.save_run(record)
            self._save(stages)
            return {"run": self.store.get_run(run_id), "stage": stage.model_dump(mode="json"), "next_stage": None, "approval": approval.model_dump(mode="json")}
        next_stage = stages[stage.sequence + 1]
        next_stage.status = StageStatus.READY
        self._save(stages)
        if next_stage.stage_id == "publish_review":
            next_stage.status = StageStatus.PENDING_REVIEW
            next_stage.started_at = next_stage.completed_at = datetime.now(timezone.utc)
            self._save(stages)
        else:
            self.execute(run_id, next_stage.stage_id)
        return {"run": self.store.get_run(run_id), "stage": stage.model_dump(mode="json"), "next_stage": next_stage.model_dump(mode="json"), "approval": approval.model_dump(mode="json")}

    def reject(self, run_id: str, stage_id: str, feedback: str) -> dict:
        stages, stage = self._stage(run_id, stage_id)
        if stage.status not in {StageStatus.PENDING_REVIEW, StageStatus.REVISION_REQUIRED}:
            raise ValueError("stage_not_ready_for_review")
        source_version = stage.version
        approval = StageApproval(approval_id=f"stage_approval_{uuid.uuid4().hex}", run_id=run_id, stage_id=stage_id, stage_version=source_version, decision="rejected", feedback=feedback)
        approvals = self.stage_store.approvals(run_id)
        approvals.append(approval)
        self.stage_store.save_approvals(run_id, approvals)
        stage.version += 1
        stage.status = StageStatus.REVISION_REQUIRED
        stage.feedback = feedback
        for downstream in stages[stage.sequence + 1:]:
            downstream.status = StageStatus.LOCKED
            downstream.version += 1
        self._save(stages)
        self.workflow._event(run_id, stage_id, "stage_rejected", {"source_version": source_version, "new_version": stage.version, "feedback": feedback})
        return {"run": self.store.get_run(run_id), "stage": stage.model_dump(mode="json"), "approval": approval.model_dump(mode="json")}
