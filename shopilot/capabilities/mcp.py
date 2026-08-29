from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agno.tools.mcp import MCPTools

from .models import CredentialReference, MCPServerConfig
from .registry import CapabilityConfigurationError, CapabilityRegistry


class MCPStatus(StrEnum):
    NOT_CONNECTED = "not_connected"
    CONNECTING = "connecting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"


class MCPUnavailable(RuntimeError):
    code = "mcp_unavailable"


class CredentialResolver:
    def __init__(
        self,
        references: Mapping[str, CredentialReference],
        environ: Mapping[str, str] | None = None,
    ):
        self.references = references
        self.environ = environ if environ is not None else os.environ

    def resolve(self, reference_id: str) -> str:
        try:
            reference = self.references[reference_id]
        except KeyError as exc:
            raise CapabilityConfigurationError(
                f"credential_reference_not_found:{reference_id}"
            ) from exc
        value = self.environ.get(reference.key)
        if reference.required and not value:
            raise CapabilityConfigurationError(
                f"credential_value_missing:{reference.id}"
            )
        return value or ""


@dataclass
class _MCPState:
    toolkit: Any = None
    status: MCPStatus = MCPStatus.NOT_CONNECTED
    failures: int = 0
    last_error_code: str | None = None
    opened_until: float = 0
    last_checked_at: float | None = None


class MCPConnectionManager:
    def __init__(
        self,
        registry: CapabilityRegistry,
        credential_resolver: CredentialResolver | None = None,
        toolkit_factory: Callable[[MCPServerConfig], Any] | None = None,
    ):
        self.registry = registry
        self.credentials = credential_resolver or CredentialResolver(registry.credentials)
        self.toolkit_factory = toolkit_factory
        self._states = {
            reference: _MCPState() for reference in registry.mcp_servers
        }

    def _headers(self, config: MCPServerConfig) -> dict[str, str]:
        return {
            header: self.credentials.resolve(reference)
            for header, reference in config.credential_headers.items()
        }

    def _environment(self, config: MCPServerConfig) -> dict[str, str]:
        return {
            key: self.credentials.resolve(reference)
            for key, reference in config.credential_env.items()
        }

    def build_toolkit(self, reference: str):
        config = self.registry.mcp_server(reference)
        if self.toolkit_factory is not None:
            return self.toolkit_factory(config)
        kwargs: dict[str, Any] = {
            "name": config.id,
            "transport": config.transport.value,
            "timeout_seconds": int(config.timeout_seconds),
            "include_tools": list(config.allowed_tools) or None,
        }
        if config.command:
            kwargs["command"] = config.command
            kwargs["env"] = self._environment(config)
        if config.url:
            kwargs["url"] = config.url
            if config.credential_headers:
                kwargs["header_provider"] = lambda: self._headers(config)
        return MCPTools(**kwargs)

    async def connect(self, reference: str):
        config = self.registry.mcp_server(reference)
        state = self._states[reference]
        now = time.monotonic()
        if state.opened_until > now:
            state.status = MCPStatus.CIRCUIT_OPEN
            raise MCPUnavailable("mcp_circuit_open")
        state.status = MCPStatus.CONNECTING
        for attempt in range(config.retry_budget + 1):
            toolkit = state.toolkit or self.build_toolkit(reference)
            state.toolkit = toolkit
            try:
                connected = await asyncio.wait_for(
                    toolkit.__aenter__(), timeout=config.timeout_seconds
                )
                state.status = MCPStatus.HEALTHY
                state.failures = 0
                state.last_error_code = None
                state.last_checked_at = time.time()
                return connected
            except Exception as exc:
                state.failures += 1
                state.status = MCPStatus.UNHEALTHY
                state.last_error_code = type(exc).__name__
                state.last_checked_at = time.time()
                try:
                    await toolkit.close()
                except Exception:
                    pass
                state.toolkit = None
                if attempt < config.retry_budget and config.retry_delay_seconds:
                    await asyncio.sleep(config.retry_delay_seconds)
        if state.failures >= config.circuit_failure_threshold:
            state.status = MCPStatus.CIRCUIT_OPEN
            state.opened_until = time.monotonic() + config.circuit_reset_seconds
        raise MCPUnavailable("mcp_connection_failed")

    async def close(self, reference: str) -> None:
        state = self._states[reference]
        if state.toolkit is not None:
            await state.toolkit.close()
        state.toolkit = None
        state.status = MCPStatus.NOT_CONNECTED

    async def close_all(self) -> None:
        for reference in self._states:
            await self.close(reference)

    def health(self) -> dict:
        return {
            "servers": [
                {
                    "server_id": self.registry.mcp_servers[reference].id,
                    "status": state.status.value,
                    "failures": state.failures,
                    "last_error_code": state.last_error_code,
                    "last_checked_at": state.last_checked_at,
                }
                for reference, state in sorted(self._states.items())
            ]
        }
