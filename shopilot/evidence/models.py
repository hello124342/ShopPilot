from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceSourceType(StrEnum):
    SEARCH = "search"
    WEB = "web"
    MCP = "mcp"
    UPLOAD = "upload"
    FIXTURE = "fixture"


class ConflictResolutionStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    NOT_A_CONFLICT = "not_a_conflict"


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    rank: int = Field(ge=0)


class ExtractedDocument(BaseModel):
    url: str
    title: str = ""
    text: str
    content_type: str
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieved_at: datetime = Field(default_factory=utc_now)
    prompt_injection_suspected: bool = False


class EvidenceRecord(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev_{uuid4().hex}")
    tenant_id: str = "default"
    run_id: str
    subject: str
    claim: str
    source_type: EvidenceSourceType
    source_url: str
    source_title: str = ""
    excerpt: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    collector_id: str
    tool_call_id: str
    confidence: float = Field(ge=0, le=1)
    prompt_injection_suspected: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_content(cls, *, content: str, **values: Any) -> "EvidenceRecord":
        return cls(content_hash=sha256(content.encode("utf-8")).hexdigest(), **values)


class Citation(BaseModel):
    citation_id: str = Field(default_factory=lambda: f"cit_{uuid4().hex}")
    claim: str
    evidence_ids: tuple[str, ...]
    supported: bool
    reason: str = ""

    @model_validator(mode="after")
    def require_evidence_for_supported_claim(self):
        if self.supported and not self.evidence_ids:
            raise ValueError("supported_citation_requires_evidence")
        return self


class EvidenceConflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: f"conf_{uuid4().hex}")
    tenant_id: str = "default"
    run_id: str
    subject: str
    evidence_ids: tuple[str, ...]
    description: str
    resolution_status: ConflictResolutionStatus = ConflictResolutionStatus.UNRESOLVED
    resolution: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def require_multiple_evidence_records(self):
        if len(set(self.evidence_ids)) < 2:
            raise ValueError("conflict_requires_multiple_evidence_records")
        return self
