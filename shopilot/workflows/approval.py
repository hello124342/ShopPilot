from __future__ import annotations

from ..assets import AssetReference
from ..schemas import ApprovalEvent, PlatformPayload
from ..store import RunStore


def payload_asset_versions(payload: PlatformPayload) -> dict[str, int]:
    return {
        item.asset_id: item.version
        for item in payload.media
        if isinstance(item, AssetReference)
    }


class ApprovalService:
    def __init__(self, store: RunStore):
        self.store = store

    def decide(
        self,
        run_id: str,
        payload: PlatformPayload,
        decision: str,
        feedback: str = "",
    ) -> ApprovalEvent:
        event = ApprovalEvent(
            run_id=run_id,
            artifact_version=payload.artifact_version,
            asset_versions=payload_asset_versions(payload),
            decision=decision,
            feedback=feedback,
        )
        self.store.approval(event)
        return event

    def is_approved(
        self,
        run_id: str,
        artifact_version: int,
        asset_versions: dict[str, int] | None = None,
    ) -> bool:
        events = self.store.read(run_id, "approvals.jsonl")
        return bool(
            events
            and events[-1]["decision"] == "approved"
            and events[-1]["artifact_version"] == artifact_version
            and events[-1].get("asset_versions", {}) == (asset_versions or {})
        )