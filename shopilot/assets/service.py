from __future__ import annotations

import struct
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .catalog import AssetCatalog
from .models import Asset, AssetKind, AssetLineage, AssetReference, AssetStatus
from .storage import AgnoLocalAssetStorage


class AssetIntegrityError(ValueError):
    pass


class AssetQuotaExceeded(ValueError):
    pass


class AssetService:
    def __init__(
        self,
        catalog: AssetCatalog,
        storage: AgnoLocalAssetStorage,
        *,
        max_asset_bytes: int = 25_000_000,
        tenant_quota_bytes: int = 1_000_000_000,
    ):
        self.catalog = catalog
        self.storage = storage
        self.max_asset_bytes = max_asset_bytes
        self.tenant_quota_bytes = tenant_quota_bytes

    @staticmethod
    def _metadata(content: bytes, mime_type: str) -> dict[str, Any]:
        if mime_type == "image/png" and len(content) >= 24 and content[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", content[16:24])
            return {"width": width, "height": height}
        return {}

    def create(
        self,
        content: bytes,
        *,
        filename: str,
        mime_type: str,
        kind: AssetKind,
        owner_id: str,
        run_id: str,
        created_by: str,
        tenant_id: str = "default",
        tool_call_id: str | None = None,
        retention_until: datetime | None = None,
        parent: AssetReference | None = None,
        model_id: str | None = None,
        prompt_version: str | None = None,
        generation_parameters: dict[str, Any] | None = None,
        asset_id: str | None = None,
    ) -> Asset:
        if not content:
            raise AssetIntegrityError("asset_empty")
        if len(content) > self.max_asset_bytes:
            raise AssetQuotaExceeded("asset_size_limit_exceeded")
        digest = sha256(content).hexdigest()
        existing = self.catalog.find_ready_hash(digest, tenant_id=tenant_id)
        if existing and asset_id is None:
            self.catalog.link_run(existing, run_id)
            self.catalog.event(existing, "asset_deduplicated", {"run_id": run_id})
            return existing
        if self.catalog.usage_bytes(tenant_id=tenant_id) + len(content) > self.tenant_quota_bytes:
            raise AssetQuotaExceeded("tenant_asset_quota_exceeded")

        latest = self.catalog.latest(asset_id, tenant_id=tenant_id) if asset_id else None
        version = latest.version + 1 if latest else 1
        safe_filename = Path(filename).name
        pending = Asset(
            asset_id=asset_id or f"asset_{digest[:24]}",
            version=version,
            tenant_id=tenant_id,
            owner_id=owner_id,
            run_id=run_id,
            kind=kind,
            filename=safe_filename,
            mime_type=mime_type,
            size_bytes=len(content),
            sha256=digest,
            storage_key="pending",
            status=AssetStatus.PENDING,
            media_metadata=self._metadata(content, mime_type),
            created_by=created_by,
            tool_call_id=tool_call_id,
            retention_until=retention_until,
        )
        self.catalog.put(pending)
        self.catalog.event(pending, "asset_pending")
        try:
            key = self.storage.put(
                f"{pending.asset_id}-v{version}",
                content,
                filename=safe_filename,
                mime_type=mime_type,
                metadata={"tenant_id": tenant_id, "run_id": run_id, "version": version},
            )
            stored = self.storage.get(key)
            if sha256(stored).hexdigest() != digest:
                raise AssetIntegrityError("asset_hash_mismatch")
            ready = pending.model_copy(update={"storage_key": key, "status": AssetStatus.READY})
            self.catalog.replace(ready)
            self.catalog.event(ready, "asset_ready")
        except Exception as exc:
            failed = pending.model_copy(
                update={
                    "status": AssetStatus.QUARANTINED if isinstance(exc, AssetIntegrityError) else AssetStatus.FAILED,
                    "failure_reason": getattr(exc, "args", ["asset_storage_failed"])[0],
                }
            )
            self.catalog.replace(failed)
            self.catalog.event(failed, f"asset_{failed.status.value}")
            raise

        reference = AssetReference(asset_id=ready.asset_id, version=ready.version)
        self.catalog.put_lineage(
            AssetLineage(
                tenant_id=tenant_id,
                run_id=run_id,
                parent=parent,
                derived=reference,
                agent_id=created_by,
                tool_call_id=tool_call_id,
                model_id=model_id,
                prompt_version=prompt_version,
                generation_parameters=generation_parameters or {},
            )
        )
        return ready

    def get(self, reference: AssetReference, *, tenant_id: str = "default") -> Asset:
        asset = self.catalog.get(reference.asset_id, reference.version, tenant_id=tenant_id)
        if asset is None:
            raise ValueError("asset_not_found")
        return asset

    def content(self, reference: AssetReference, *, tenant_id: str = "default") -> tuple[Asset, bytes]:
        asset = self.get(reference, tenant_id=tenant_id)
        if asset.status != AssetStatus.READY:
            raise ValueError("asset_not_ready")
        try:
            content = self.storage.get(asset.storage_key)
        except Exception as exc:
            self._quarantine(asset, "asset_storage_missing")
            raise AssetIntegrityError("asset_storage_missing") from exc
        if sha256(content).hexdigest() != asset.sha256:
            self._quarantine(asset, "asset_hash_mismatch")
            raise AssetIntegrityError("asset_hash_mismatch")
        return asset, content

    def _quarantine(self, asset: Asset, reason: str) -> Asset:
        quarantined = asset.model_copy(update={"status": AssetStatus.QUARANTINED, "failure_reason": reason})
        self.catalog.replace(quarantined)
        self.catalog.event(quarantined, "asset_quarantined", {"reason": reason})
        return quarantined

    def archive_expired(self, *, now: datetime | None = None, tenant_id: str = "default") -> int:
        current = now or datetime.now(timezone.utc)
        archived = 0
        with self.catalog._connect() as connection:
            rows = connection.execute(
                "SELECT asset_json FROM assets WHERE tenant_id=? AND status=?",
                (tenant_id, AssetStatus.READY.value),
            ).fetchall()
        for row in rows:
            asset = Asset.model_validate_json(row["asset_json"])
            if asset.retention_until and asset.retention_until <= current:
                updated = asset.model_copy(update={"status": AssetStatus.ARCHIVED})
                self.catalog.replace(updated)
                self.catalog.event(updated, "asset_archived")
                archived += 1
        return archived

    @staticmethod
    def safe_metadata(asset: Asset) -> dict[str, Any]:
        return asset.model_dump(mode="json", exclude={"storage_key"})
