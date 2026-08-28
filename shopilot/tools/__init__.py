from ..fixtures import METRICS, POLICY, PRODUCT, RESEARCH
from ..runtime.providers import SideEffectMode
from ..schemas import Metrics, PlatformPayload

class ToolError(RuntimeError): pass
class ProductTool:
    def get(self,product): return PRODUCT if product==PRODUCT["product"] else {}
class ResearchTool:
    def search(self): return RESEARCH
class PolicyTool:
    def validate(self,payload):
        errors=[]
        if len(payload.title)>POLICY["max_title_length"]: errors.append("title_too_long")
        if len(payload.media)>POLICY["max_media"]: errors.append("too_many_media")
        errors += [f"prohibited:{w}" for w in POLICY["prohibited"] if w in payload.title+payload.body]
        return errors
class MetricsTool:
    def get(self): return Metrics(**METRICS)
class MockPublishTool:
    def __init__(self,side_effect_mode=SideEffectMode.MOCK): self.side_effect_mode=side_effect_mode; self.published={}
    def publish(self,payload:PlatformPayload,approved:bool,approved_version:int|None,idempotency_key:str,request_real:bool=False):
        if not approved: raise ToolError("approval_required")
        if approved_version != payload.artifact_version: raise ToolError("approval_version_mismatch")
        if request_real and self.side_effect_mode != SideEffectMode.REAL: raise ToolError("real_side_effect_disabled")
        if idempotency_key in self.published: raise ToolError("duplicate_idempotency_key")
        result={"status":"published","mode":self.side_effect_mode,"platform":payload.platform,"artifact_version":payload.artifact_version,"idempotency_key":idempotency_key}
        self.published[idempotency_key]=result; return result
