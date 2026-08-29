from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_.-]{1,63}$"
VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
REFERENCE_PATTERN = r"^[a-z][a-z0-9_.-]{1,63}@[0-9]+\.[0-9]+\.[0-9]+$"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VersionedContract(ContractModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    version: str = Field(pattern=VERSION_PATTERN)

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


class SideEffectClass(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    EXTERNAL_WRITE = "external_write"
    PUBLISH = "publish"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class MCPTransport(StrEnum):
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


class AgentDefinition(VersionedContract):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=500)
    capability_profile_ref: str = Field(pattern=REFERENCE_PATTERN)
    model_policy: str = "default"


class SkillManifest(VersionedContract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    source_path: str = Field(min_length=1)
    applicable_subjects: frozenset[str] = frozenset()
    content_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class ToolDescriptor(VersionedContract):
    name: str = Field(min_length=1, max_length=120)
    function_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    side_effect: SideEffectClass
    timeout_seconds: float = Field(default=30, gt=0, le=600)
    retry_budget: int = Field(default=0, ge=0, le=10)
    idempotent: bool = True


class CredentialReference(ContractModel):
    id: str = Field(pattern=IDENTIFIER_PATTERN)
    source: Literal["env"] = "env"
    key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,127}$")
    required: bool = True


class MCPServerConfig(VersionedContract):
    name: str = Field(min_length=1, max_length=120)
    transport: MCPTransport
    command: str | None = None
    url: str | None = None
    allowed_tools: tuple[str, ...] = ()
    side_effect: SideEffectClass = SideEffectClass.READ_ONLY
    credential_headers: dict[str, str] = Field(default_factory=dict)
    credential_env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=10, gt=0, le=300)
    retry_budget: int = Field(default=1, ge=0, le=10)
    retry_delay_seconds: float = Field(default=0, ge=0, le=60)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=100)
    circuit_reset_seconds: float = Field(default=30, gt=0, le=3600)

    @model_validator(mode="after")
    def validate_transport_target(self):
        if self.transport == MCPTransport.STDIO:
            if not self.command or self.url:
                raise ValueError("stdio_requires_command_only")
        elif not self.url or self.command:
            raise ValueError("http_transport_requires_url_only")
        if self.url and not self.url.startswith(("https://", "http://")):
            raise ValueError("mcp_url_scheme_not_allowed")
        return self


class CapabilityPolicy(VersionedContract):
    subjects: frozenset[str]
    resources: frozenset[str]
    actions: frozenset[str]
    side_effects: frozenset[SideEffectClass]
    tenant: str = "*"
    environment: str = "*"
    effect: PolicyEffect


class CapabilityProfile(VersionedContract):
    skill_refs: tuple[str, ...] = ()
    tool_refs: tuple[str, ...] = ()
    mcp_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_references(self):
        for reference in (*self.skill_refs, *self.tool_refs, *self.mcp_refs):
            if not __import__("re").fullmatch(REFERENCE_PATTERN, reference):
                raise ValueError(f"invalid_capability_reference:{reference}")
        return self


class CapabilityRegistryConfig(ContractModel):
    agents: tuple[AgentDefinition, ...] = ()
    skills: tuple[SkillManifest, ...] = ()
    tools: tuple[ToolDescriptor, ...] = ()
    mcp_servers: tuple[MCPServerConfig, ...] = ()
    credentials: tuple[CredentialReference, ...] = ()
    policies: tuple[CapabilityPolicy, ...] = ()
    profiles: tuple[CapabilityProfile, ...] = ()
