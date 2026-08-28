from __future__ import annotations
from ..schemas import ApprovalEvent, PlatformPayload
from ..store import RunStore

class ApprovalService:
    def __init__(self, store: RunStore): self.store = store
    def decide(self, run_id: str, payload: PlatformPayload, decision: str, feedback: str = "") -> ApprovalEvent:
        event = ApprovalEvent(run_id=run_id, artifact_version=payload.artifact_version, decision=decision, feedback=feedback)
        self.store.approval(event)
        return event
    def is_approved(self, run_id: str, artifact_version: int) -> bool:
        events = self.store.read(run_id, "approvals.jsonl")
        return bool(events and events[-1]["decision"] == "approved" and events[-1]["artifact_version"] == artifact_version)

