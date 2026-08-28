from pydantic import ValidationError
import uuid
from ..schemas import Artifact,CampaignInput,EvaluationReport,RunRecord,TraceEvent
from ..store import RunStore
from ..tools import ToolError
from ..workflows import CampaignWorkflow
from .evaluators import Evaluator
from .scenarios import SCENARIOS

def run_scenario(scenario_id:str,store:RunStore):
    scenario=SCENARIOS[scenario_id]
    try: campaign=CampaignInput(**scenario.campaign)
    except ValidationError as exc:
        run_id=uuid.uuid4().hex; record=RunRecord(run_id=run_id,status="failed",campaign=scenario.campaign,error="validation_error")
        store.save_run(record); store.artifact(run_id,Artifact(kind="ValidationError",version=1,data={"errors":exc.errors(include_url=False)})); store.trace(TraceEvent(run_id=run_id,sequence=0,stage="input",event_type="error",payload={"error":"validation_error"}))
        report=EvaluationReport(passed=False,checks={"input_schema":False},metrics={"error_count":float(exc.error_count())},failures=["input_schema"]); store.save_evaluation(run_id,report)
        return {"scenario":scenario_id,"run_id":run_id,"status":"failed","evaluation":report.model_dump()}
    workflow=CampaignWorkflow(store); result=workflow.run(campaign,inject=scenario.inject)
    if scenario.inject.get("duplicate_publish") and result["status"]=="waiting_review":
        workflow.approve_and_analyze(result["run_id"])
        try: workflow.publisher.publish(workflow.latest_payload(result["run_id"]),True,1,result["run_id"])
        except ToolError: result={**result,"status":"tool_error"}
    if result.get("run_id"): result={**result,"evaluation":Evaluator(store).evaluate(result["run_id"]).model_dump()}
    return {"scenario":scenario_id,**result}

def run_all(store:RunStore): return [run_scenario(s,store) for s in SCENARIOS]
