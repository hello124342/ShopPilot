from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, TypeVar

from .models import (
    AgentDefinition,
    CapabilityProfile,
    CapabilityRegistryConfig,
    CredentialReference,
    MCPServerConfig,
    SkillManifest,
    ToolDescriptor,
)


class CapabilityConfigurationError(ValueError):
    code = "capability_config_invalid"


T = TypeVar("T")


def _versioned_index(items: Iterable[T], label: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for item in items:
        reference = item.ref  # type: ignore[attr-defined]
        if reference in result:
            raise CapabilityConfigurationError(f"duplicate_{label}:{reference}")
        result[reference] = item
    return result


class CapabilityRegistry:
    def __init__(self, config: CapabilityRegistryConfig):
        self.config = config
        self.agents = _versioned_index(config.agents, "agent")
        self.skills = _versioned_index(config.skills, "skill")
        self.tools = _versioned_index(config.tools, "tool")
        self.mcp_servers = _versioned_index(config.mcp_servers, "mcp_server")
        self.profiles = _versioned_index(config.profiles, "profile")
        self.policies = tuple(config.policies)
        self.credentials: dict[str, CredentialReference] = {}
        for credential in config.credentials:
            if credential.id in self.credentials:
                raise CapabilityConfigurationError(f"duplicate_credential:{credential.id}")
            self.credentials[credential.id] = credential
        self._validate_references()

    @classmethod
    def load(cls, path: str | Path) -> "CapabilityRegistry":
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            return cls(CapabilityRegistryConfig.model_validate(payload))
        except CapabilityConfigurationError:
            raise
        except Exception as exc:
            raise CapabilityConfigurationError("capability_registry_load_failed") from exc

    def _validate_references(self) -> None:
        for agent in self.agents.values():
            if agent.capability_profile_ref not in self.profiles:
                raise CapabilityConfigurationError(
                    f"agent_profile_not_found:{agent.ref}:{agent.capability_profile_ref}"
                )
        for profile in self.profiles.values():
            for reference in profile.skill_refs:
                if reference not in self.skills:
                    raise CapabilityConfigurationError(f"skill_not_found:{reference}")
            for reference in profile.tool_refs:
                if reference not in self.tools:
                    raise CapabilityConfigurationError(f"tool_not_found:{reference}")
            for reference in profile.mcp_refs:
                if reference not in self.mcp_servers:
                    raise CapabilityConfigurationError(f"mcp_server_not_found:{reference}")
        for server in self.mcp_servers.values():
            refs = (*server.credential_headers.values(), *server.credential_env.values())
            for reference in refs:
                if reference not in self.credentials:
                    raise CapabilityConfigurationError(
                        f"credential_reference_not_found:{server.ref}:{reference}"
                    )

    def agent(self, agent_id: str) -> AgentDefinition:
        matches = [item for item in self.agents.values() if item.id == agent_id]
        if len(matches) != 1:
            raise CapabilityConfigurationError(f"agent_resolution_failed:{agent_id}")
        return matches[0]

    def profile(self, reference: str) -> CapabilityProfile:
        try:
            return self.profiles[reference]
        except KeyError as exc:
            raise CapabilityConfigurationError(f"profile_not_found:{reference}") from exc

    def tool(self, reference: str) -> ToolDescriptor:
        try:
            return self.tools[reference]
        except KeyError as exc:
            raise CapabilityConfigurationError(f"tool_not_found:{reference}") from exc

    def mcp_server(self, reference: str) -> MCPServerConfig:
        try:
            return self.mcp_servers[reference]
        except KeyError as exc:
            raise CapabilityConfigurationError(f"mcp_server_not_found:{reference}") from exc

    def tool_by_function_name(self, function_name: str) -> ToolDescriptor | None:
        matches = [item for item in self.tools.values() if item.function_name == function_name]
        if len(matches) > 1:
            raise CapabilityConfigurationError(f"ambiguous_tool_function:{function_name}")
        return matches[0] if matches else None

    def safe_status(self) -> dict:
        return {
            "valid": True,
            "counts": {
                "agents": len(self.agents),
                "skills": len(self.skills),
                "tools": len(self.tools),
                "mcp_servers": len(self.mcp_servers),
                "profiles": len(self.profiles),
                "policies": len(self.policies),
                "credential_references": len(self.credentials),
            },
            "mcp_server_ids": sorted(item.id for item in self.mcp_servers.values()),
        }
