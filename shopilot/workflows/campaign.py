from __future__ import annotations
import json, time, uuid
from datetime import datetime, timezone

from ..agents import AnalyticsAgent, ComplianceAgent, OptimizationAgent, PlatformAdapterAgent, StrategyAgent
from ..config import RuntimeConfig
from ..domain.states import RunStatus
from ..runtime.agno_factory import AgnoRuntimeFactory
from ..runtime.errors import ProviderError, classify_provider_error
from ..runtime.providers import RuntimeMode, RuntimeSettings, SideEffectMode
from ..schemas import Artifact, CampaignBrief, CampaignInput, ComplianceReport, CreativePackage, OptimizationBrief, PerformanceReport, PlatformPayload, ResearchPackage, RunRecord, TraceEvent
from ..store import RunStore
from ..teams import ResearchTeam
from ..tools import MetricsTool, MockPublishTool, PolicyTool
from .approval import ApprovalService
from .creative import CreativeWorkflow

class CampaignWorkflow:
    def __init__(self,store:RunStore|None=None,settings:RuntimeSettings|None=None,config:RuntimeConfig|None=None):
        self.store=store or RunStore(); self.settings=settings or RuntimeSettings(); self.config=config or RuntimeConfig()
        self.publisher=MockPublishTool(self.settings.side_effect_mode); self.approvals=ApprovalService(self.store)
        self.agno=AgnoRuntimeFactory().build_from_settings(self.settings) if self.settings.runtime_mode==RuntimeMode.AGNO else None

    def _event(self,run_id,stage,event_type,payload=None,started=None):
        seq=len(self.store.read(run_id,"trace.jsonl")); latency=(time.perf_counter()-started)*1000 if started else 0
        self.store.trace(TraceEvent(run_id=run_id,sequence=seq,stage=stage,event_type=event_type,payload=payload or {},latency_ms=latency,model_version=self.config.model_version,prompt_version=self.config.prompt_version))

    def _status(self,record:RunRecord,status:RunStatus,error:str|None=None):
        record.status=status.value; record.error=error; record.updated_at=datetime.now(timezone.utc); self.store.save_run(record)

    def _artifact(self,run_id,kind,data,version=1): self.store.artifact(run_id,Artifact(kind=kind,version=version,data=data.model_dump()))

    def _agno_output(self, response, schema):
        content = response.content
        if isinstance(content, schema): return content
        if isinstance(content, str): return schema.model_validate_json(content)
        return schema.model_validate(content)

    def _agno_agent(self, run_id, stage, agent_name, schema, payload):
        for attempt in range(self.settings.retry_budget+1):
            started=time.perf_counter(); self._event(run_id,stage,"model_started",{"provider":self.settings.provider,"model_id":self.settings.model_id,"attempt":attempt+1})
            try:
                response=self.agno.agents[agent_name].run(json.dumps(payload,ensure_ascii=False))
                result=self._agno_output(response,schema); self._event(run_id,stage,"model_completed",{"provider":self.settings.provider,"model_id":self.settings.model_id},started)
                return result
            except Exception as exc:
                error=classify_provider_error(exc); self._event(run_id,stage,"model_error",{"error_code":error.code,"retryable":error.retryable,"attempt":attempt+1},started)
                if not error.retryable or attempt>=self.settings.retry_budget: raise error from exc

    def run(self,campaign:CampaignInput,run_id:str|None=None,inject:dict|None=None,replayed_from:str|None=None):
        run_id=run_id or uuid.uuid4().hex; inject=inject or {}
        record=RunRecord(
            run_id=run_id,campaign=campaign.model_dump(),runtime_mode=self.settings.runtime_mode,
            side_effect_mode=self.settings.side_effect_mode,replayed_from=replayed_from,
            provider=self.settings.provider if self.settings.runtime_mode==RuntimeMode.AGNO else "deterministic",
            model_id=(self.settings.model_id or "unknown") if self.settings.runtime_mode==RuntimeMode.AGNO else self.config.model_version,
        )
        self.store.save_run(record); self._status(record,RunStatus.RUNNING); self._event(run_id,"run","started",{"runtime_mode":self.settings.runtime_mode})
        try:
            if self.agno:
                output=self.agno.campaign_workflow.run(campaign.model_dump())
                metadata=AgnoRuntimeFactory().provider_metadata(self.settings)
                self._event(run_id,"agno_runtime","completed",{"status":output.status.value,**metadata})
            if inject.get("invalid_schema"): raise ValueError("invalid_schema")
            research=None; research_error="research_timeout"
            for attempt in range(self.settings.retry_budget+1):
                started=time.perf_counter(); self._event(run_id,"research","attempt",{"attempt":attempt+1})
                if inject.get("research_timeout"):
                    self._event(run_id,"research","error",{"error":"research_timeout","attempt":attempt+1},started); continue
                if self.agno:
                    try:
                        response=self.agno.research_team.run(json.dumps(campaign.model_dump(),ensure_ascii=False))
                        research=self._agno_output(response,ResearchPackage)
                    except Exception as exc:
                        error=classify_provider_error(exc); research_error=error.code
                        self._event(run_id,"research","error",{"error_code":error.code,"retryable":error.retryable,"attempt":attempt+1},started)
                        if error.retryable: continue
                        raise error from exc
                else: research=ResearchTeam().run(campaign)
                self._event(run_id,"research","completed",started=started); break
            if research is None:
                self.store.artifact(run_id,Artifact(kind="RunError",version=1,data={"stage":"research","error":research_error})); self._status(record,RunStatus.HUMAN_HANDOFF,research_error); return self.store.get_run(run_id)
            if inject.get("evidence_conflict"): research.conflicts.append("续航数据存在冲突")
            self._artifact(run_id,"ResearchPackage",research)
            brief=self._agno_agent(run_id,"strategy","strategy",CampaignBrief,{"campaign":campaign.model_dump(),"research":research.model_dump()}) if self.agno else StrategyAgent().run(campaign,research)
            self._artifact(run_id,"CampaignBrief",brief); self._event(run_id,"strategy","completed")
            creative=self._agno_agent(run_id,"creative","creative",CreativePackage,brief.model_dump()) if self.agno else CreativeWorkflow().run(brief)
            self._artifact(run_id,"CreativePackage",creative); self._event(run_id,"creative","completed")
            payload=PlatformAdapterAgent().run(creative,campaign.platform)
            if inject.get("policy_violation"): payload.body += " 百分百有效"
            self._artifact(run_id,"PlatformPayload",payload); errors=PolicyTool().validate(payload); self._event(run_id,"platform","validated",{"errors":errors})
            compliance=self._agno_agent(run_id,"compliance","compliance",ComplianceReport,{"payload":payload.model_dump(),"deterministic_rule_errors":errors}) if self.agno else ComplianceAgent().run(payload,errors)
            self._artifact(run_id,"ComplianceReport",compliance)
            if not compliance.passed:
                self._status(record,RunStatus.REVISION_REQUIRED); return self.store.get_run(run_id)
            self._status(record,RunStatus.WAITING_REVIEW); return self.store.get_run(run_id)
        except Exception as exc:
            error = exc if isinstance(exc, ProviderError) else classify_provider_error(exc) if self.agno else exc
            code = error.code if isinstance(error, ProviderError) else str(error)
            self.store.artifact(run_id,Artifact(kind="RunError",version=1,data={"stage":"run","error_code":code}))
            self._event(run_id,"run","error",{"error_code":code,"retryable":getattr(error,"retryable",False)})
            status = RunStatus.HUMAN_HANDOFF if getattr(error,"retryable",False) else RunStatus.FAILED
            self._status(record,status,code); return self.store.get_run(run_id)

    def latest_payload(self,run_id):
        values=[a for a in self.store.read(run_id,"artifacts.jsonl") if a["kind"]=="PlatformPayload"]
        if not values: raise ValueError("platform_payload_not_found")
        return PlatformPayload(**values[-1]["data"])

    def approve_and_analyze(self,run_id:str,payload:PlatformPayload|None=None,feedback="",inject:dict|None=None):
        inject=inject or {}
        raw=self.store.get_run(run_id)
        if not raw: raise ValueError("run_not_found")
        record=RunRecord(**raw); payload=payload or self.latest_payload(run_id)
        if payload.artifact_version != record.current_artifact_version: raise ValueError("artifact_version_mismatch")
        self.approvals.decide(run_id,payload,"approved",feedback); self._status(record,RunStatus.APPROVED); self._event(run_id,"approval","approved",{"version":payload.artifact_version})
        result=None
        for attempt in range(self.settings.retry_budget+1):
            self._event(run_id,"publish","attempt",{"attempt":attempt+1})
            if inject.get("publish_timeout"): continue
            result=self.publisher.publish(payload,self.approvals.is_approved(run_id,payload.artifact_version),payload.artifact_version,run_id); break
        if result is None:
            self._status(record,RunStatus.HUMAN_HANDOFF,"publish_timeout"); self._event(run_id,"publish","error",{"error":"retry_budget_exhausted"}); return {"run":self.store.get_run(run_id)}
        self._status(record,RunStatus.PUBLISHED); self._event(run_id,"publish","completed",result)
        if inject.get("metrics_failure"):
            self._status(record,RunStatus.HUMAN_HANDOFF,"metrics_failure"); self._event(run_id,"analytics","error",{"error":"metrics_failure","partial_success":"published"}); return {"run":self.store.get_run(run_id),"publish":result}
        metrics=MetricsTool().get()
        performance=self._agno_agent(run_id,"analytics","analytics",PerformanceReport,metrics.model_dump()) if self.agno else AnalyticsAgent().run(metrics)
        self._artifact(run_id,"PerformanceReport",performance); self._status(record,RunStatus.ANALYZED)
        optimization=self._agno_agent(run_id,"optimization","optimization",OptimizationBrief,performance.model_dump()) if self.agno else OptimizationAgent().run(performance)
        self._artifact(run_id,"OptimizationBrief",optimization); self._status(record,RunStatus.OPTIMIZED)
        return {"run":self.store.get_run(run_id),"publish":result,"performance":performance.model_dump(),"optimization":optimization.model_dump()}

    def reject(self,run_id:str,payload:PlatformPayload|None=None,feedback="需要修改"):
        raw=self.store.get_run(run_id)
        if not raw: raise ValueError("run_not_found")
        record=RunRecord(**raw); payload=payload or self.latest_payload(run_id)
        self.approvals.decide(run_id,payload,"rejected",feedback)
        revised=payload.model_copy(update={"artifact_version":payload.artifact_version+1,"body":payload.body+f"\n修改要求：{feedback}"})
        self._artifact(run_id,"PlatformPayload",revised,revised.artifact_version); record.current_artifact_version=revised.artifact_version
        self._status(record,RunStatus.REVISION_REQUIRED); self._event(run_id,"approval","rejected",{"source_version":payload.artifact_version,"new_version":revised.artifact_version})
        return {"run":self.store.get_run(run_id),"payload":revised.model_dump()}

    def cancel(self,run_id):
        raw=self.store.get_run(run_id)
        if not raw: raise ValueError("run_not_found")
        record=RunRecord(**raw); self._status(record,RunStatus.CANCELLED); self._event(run_id,"run","cancelled"); return self.store.get_run(run_id)

    def replay(self,run_id):
        raw=self.store.get_run(run_id)
        if not raw: raise ValueError("run_not_found")
        settings=self.settings.model_copy(update={"side_effect_mode":SideEffectMode.DISABLED})
        clone=CampaignWorkflow(self.store,settings,self.config)
        return clone.run(CampaignInput(**raw["campaign"]),replayed_from=run_id)
