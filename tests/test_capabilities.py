from __future__ import annotations

import asyncio
import json

import pytest
from agno.tools import Toolkit
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shopilot.app.api import create_app
from shopilot.capabilities import (
    CapabilityAuthorizer,
    CapabilityConfigurationError,
    CapabilityDenied,
    CapabilityPolicy,
    CapabilityProfile,
    CapabilityRegistry,
    CapabilityRegistryConfig,
    CredentialReference,
    CredentialResolver,
    MCPConnectionManager,
    MCPServerConfig,
    MCPStatus,
    MCPTransport,
    MCPUnavailable,
    PolicyEffect,
    SideEffectClass,
    ToolDescriptor,
    default_registry_config,
)
from shopilot.runtime import AgnoCapabilityBindings, AgnoRuntimeFactory
from shopilot.settings import Settings


def search(query: str) -> str:
    return f"result:{query}"


def registry_with_search_tool() -> CapabilityRegistry:
    base = default_registry_config()
    descriptor = ToolDescriptor(
        id="research.search",
        version="1.0.0",
        name="Read-only search",
        function_name="search",
        side_effect=SideEffectClass.READ_ONLY,
    )
    profiles = tuple(
        profile.model_copy(update={"tool_refs": (descriptor.ref,)})
        if profile.id == "research-collector"
        else profile
        for profile in base.profiles
    )
    policy = CapabilityPolicy(
        id="research-search",
        version="1.0.0",
        subjects=frozenset({"*"}),
        resources=frozenset({descriptor.ref}),
        actions=frozenset({"bind", "invoke"}),
        side_effects=frozenset({SideEffectClass.READ_ONLY}),
        effect=PolicyEffect.ALLOW,
    )
    return CapabilityRegistry(
        base.model_copy(
            update={
                "tools": (descriptor,),
                "profiles": profiles,
                "policies": (policy,),
            }
        )
    )


def test_contracts_forbid_inline_secret_and_invalid_mcp_target():
    with pytest.raises(ValidationError):
        CredentialReference(
            id="search-key",
            key="SEARCH_API_KEY",
            value="must-not-be-accepted",
        )
    with pytest.raises(ValidationError):
        MCPServerConfig(
            id="bad-server",
            version="1.0.0",
            name="bad",
            transport=MCPTransport.STREAMABLE_HTTP,
            command="python server.py",
        )


def test_registry_rejects_dangling_profile_reference():
    config = CapabilityRegistryConfig(
        profiles=(
            CapabilityProfile(
                id="broken",
                version="1.0.0",
                tool_refs=("missing.tool@1.0.0",),
            ),
        )
    )
    with pytest.raises(CapabilityConfigurationError, match="tool_not_found"):
        CapabilityRegistry(config)


def test_factory_resolves_profile_and_binds_agno_toolkit():
    registry = registry_with_search_tool()
    toolkit = Toolkit(name="research-search", tools=[search])
    audits = []
    authorizer = CapabilityAuthorizer(registry, audits.append)
    factory = AgnoRuntimeFactory(
        registry=registry,
        bindings=AgnoCapabilityBindings(
            tools={"research.search@1.0.0": toolkit}
        ),
        authorizer=authorizer,
    )

    components = factory.build()
    product = components.agents["product"]

    assert product.tools == [toolkit]
    assert product.tool_hooks
    assert product.tool_hooks[0](
        function_name="search",
        function=lambda **arguments: search(**arguments),
        arguments={"query": "shopilot"},
    ) == "result:shopilot"
    assert {event["event_type"] for event in audits} == {"capability_allowed"}


def test_default_deny_and_denial_audit_do_not_include_arguments():
    registry = registry_with_search_tool()
    audits = []
    authorizer = CapabilityAuthorizer(registry, audits.append)

    with pytest.raises(CapabilityDenied):
        authorizer.authorize(
            subject="unknown@1.0.0",
            resource="research.search@1.0.0",
            action="invoke",
            side_effect=SideEffectClass.EXTERNAL_WRITE,
            tenant="default",
            environment="development",
        )

    serialized = json.dumps(audits)
    assert "capability_denied" in serialized
    assert "password" not in serialized
    assert "arguments" not in serialized


def mcp_registry(*, retry_budget=1, threshold=2) -> CapabilityRegistry:
    credential = CredentialReference(
        id="search-token",
        key="SEARCH_TOKEN",
    )
    server = MCPServerConfig(
        id="research-mcp",
        version="1.0.0",
        name="Research MCP",
        transport=MCPTransport.STREAMABLE_HTTP,
        url="https://mcp.example.test",
        allowed_tools=("search",),
        credential_headers={"Authorization": credential.id},
        retry_budget=retry_budget,
        circuit_failure_threshold=threshold,
        circuit_reset_seconds=60,
    )
    return CapabilityRegistry(
        CapabilityRegistryConfig(
            mcp_servers=(server,),
            credentials=(credential,),
        )
    )


def test_mcp_manager_retries_native_toolkit_and_redacts_health():
    attempts = []
    closes = []

    class FakeToolkit:
        async def __aenter__(self):
            attempts.append("connect")
            if len(attempts) == 1:
                raise TimeoutError("Bearer top-secret")
            return self

        async def close(self):
            closes.append("close")

    registry = mcp_registry()
    manager = MCPConnectionManager(
        registry,
        credential_resolver=CredentialResolver(
            registry.credentials, {"SEARCH_TOKEN": "top-secret"}
        ),
        toolkit_factory=lambda _: FakeToolkit(),
    )

    connected = asyncio.run(manager.connect("research-mcp@1.0.0"))
    health = manager.health()

    assert isinstance(connected, FakeToolkit)
    assert len(attempts) == 2
    assert health["servers"][0]["status"] == MCPStatus.HEALTHY
    assert "top-secret" not in json.dumps(health)
    assert closes


def test_mcp_manager_opens_circuit_after_terminal_failure():
    class FailingToolkit:
        async def __aenter__(self):
            raise ConnectionError("offline")

        async def close(self):
            return None

    registry = mcp_registry(retry_budget=0, threshold=1)
    manager = MCPConnectionManager(
        registry,
        credential_resolver=CredentialResolver(
            registry.credentials, {"SEARCH_TOKEN": "secret"}
        ),
        toolkit_factory=lambda _: FailingToolkit(),
    )

    with pytest.raises(MCPUnavailable, match="mcp_connection_failed"):
        asyncio.run(manager.connect("research-mcp@1.0.0"))
    with pytest.raises(MCPUnavailable, match="mcp_circuit_open"):
        asyncio.run(manager.connect("research-mcp@1.0.0"))
    assert manager.health()["servers"][0]["status"] == MCPStatus.CIRCUIT_OPEN


def test_invalid_registry_blocks_startup_without_leaking_content(tmp_path):
    config = tmp_path / "capabilities.json"
    config.write_text('{"profiles":[{"id":"broken","version":"1.0.0","tool_refs":["missing.tool@1.0.0"]}]}')
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        capability_registry_path=config,
    )

    with TestClient(create_app(settings)) as client:
        ready = client.get("/health/ready")
        health = client.get("/api/capabilities/health")

    assert ready.status_code == 503
    assert ready.json()["error_code"] == "capability_config_invalid"
    assert health.json()["registry"]["valid"] is False
    assert "missing.tool" not in health.text


def test_capability_health_is_safe_by_default(tmp_path):
    secret = "sk-never-return"
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        api_key=secret,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/capabilities/health")

    assert response.status_code == 200
    assert response.json()["registry"]["counts"]["agents"] == 10
    assert secret not in response.text
