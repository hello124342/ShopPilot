from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AssetStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"
    DELETED = "deleted"


class AssetKind(StrEnum):
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    OTHER = "other"


class AssetReference(BaseModel):
    model_config = ConfigDict(frozen=True)
    asset_id: str
    version: int = Field(ge=1)
    role: str = "media"


class Asset(BaseModel):
    model_config = ConfigDict(frozen=True)
    asset_id: str = Field(default_factory=lambda: f"asset_{uuid4().hex}")
    version: int = Field(default=1, ge=1)
    tenant_id: str = "default"
    owner_id: str
    run_id: str
    kind: AssetKind
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    storage_key: str
    status: AssetStatus
    media_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    tool_call_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    retention_until: datetime | None = None
    failure_reason: str | None = None


class AssetLineage(BaseModel):
    model_config = ConfigDict(frozen=True)
    lineage_id: str = Field(default_factory=lambda: f"lineage_{uuid4().hex}")
    tenant_id: str = "default"
    run_id: str
    parent: AssetReference | None = None
    derived: AssetReference
    agent_id: str
    tool_call_id: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def prevent_self_parent(self):
        if self.parent == self.derived:
            raise ValueError("asset_cannot_derive_from_itself")
        return self
