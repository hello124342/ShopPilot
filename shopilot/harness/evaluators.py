from __future__ import annotations
from ..domain.artifacts import REQUIRED_CAMPAIGN_ARTIFACTS, COMPLETED_CAMPAIGN_ARTIFACTS
from ..schemas import EvaluationReport
from ..store import RunStore
from ..assets import AssetCatalog

class LLMJudge:
    def judge(self,run_id:str)->dict: return {"enabled":False,"score":None,"reason":"optional_judge_not_configured"}

class Evaluator:
    def __init__(self,store:RunStore,llm_judge:LLMJudge|None=None): self.store=store; self.llm_judge=llm_judge
    def evaluate(self,run_id:str)->EvaluationReport:
        run=self.store.get_run(run_id); arts=self.store.read(run_id,"artifacts.jsonl"); trace=self.store.read(run_id,"trace.jsonl"); approvals=self.store.read(run_id,"approvals.jsonl")
        kinds={a["kind"] for a in arts}; publish_events=[e for e in trace if e["stage"]=="publish" and e["event_type"]=="completed"]
        evidence_ok=any(a["kind"]=="ResearchPackage" and a["data"].get("evidence") for a in arts)
        facts_ok=any(a["kind"]=="ResearchPackage" and set(a["data"].get("product_facts",[])).issubset({e["claim"] for e in a["data"].get("evidence",[])}) for a in arts)
        approval_safe=not publish_events or any(e["decision"]=="approved" for e in approvals)
        policy_ok=all(a["data"].get("passed",True) for a in arts if a["kind"]=="ComplianceReport")
        tool_use_ok=any(e["stage"] in {"platform","research"} for e in trace)
        status=(run or {}).get("status",""); expected=COMPLETED_CAMPAIGN_ARTIFACTS if status=="optimized" else REQUIRED_CAMPAIGN_ARTIFACTS
        checks={"run_exists":bool(run),"schema":bool(arts),"artifact_completeness":expected.issubset(kinds),"evidence":evidence_ok,"facts":facts_ok,"policy":policy_ok,"tool_use":tool_use_ok,"trace":bool(trace),"approval_gate":approval_safe,"side_effect_safe":(run or {}).get("side_effect_mode")!="real"}
        failures=[k for k,v in checks.items() if not v]
        judge=self.llm_judge.judge(run_id) if self.llm_judge else {"enabled":False,"score":None}
        research = next((a["data"] for a in arts if a["kind"] == "ResearchPackage"), {})
        asset_count = len(AssetCatalog(self.store.root / "assets.db").list_for_run(run_id))
        report=EvaluationReport(passed=not failures,checks=checks,metrics={"trace_events":float(len(trace)),"artifact_count":float(len(arts)),"asset_count":float(asset_count),"citation_coverage":float(research.get("citation_coverage", 0)),"retry_count":float(sum(e["event_type"]=="attempt" for e in trace)),"latency_ms":sum(e.get("latency_ms",0) for e in trace),"cost":sum(e.get("cost",0) for e in trace),"llm_judge_score":float(judge["score"]) if judge.get("score") is not None else 0.0},failures=failures)
        self.store.save_evaluation(run_id,report); return report
