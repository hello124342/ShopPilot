from __future__ import annotations

from .models import (
    AgentDefinition,
    CapabilityPolicy,
    CapabilityProfile,
    CapabilityRegistryConfig,
    PolicyEffect,
    SideEffectClass,
    ToolDescriptor,
)
from .registry import CapabilityRegistry


_AGENT_SPECS = {
    "product": ("Product Analyst", "Extract product facts", "research-collector@1.0.0"),
    "competitor": ("Competitor Analyst", "Analyze competitor claims", "research-collector@1.0.0"),
    "audience": ("Audience Analyst", "Analyze audiences", "research-collector@1.0.0"),
    "trend": ("Trend Analyst", "Analyze market trends", "research-collector@1.0.0"),
    "evidence": ("Evidence Reviewer", "Review normalized evidence", "evidence-reviewer@1.0.0"),
    "strategy": ("Strategy Agent", "Create marketing strategy", "internal-agent@1.0.0"),
    "creative": ("Creative Agent", "Create campaign content", "internal-agent@1.0.0"),
    "compliance": ("Compliance Agent", "Explain deterministic policy results", "internal-agent@1.0.0"),
    "analytics": ("Analytics Agent", "Explain deterministic metrics", "internal-agent@1.0.0"),
    "optimization": ("Optimization Agent", "Create the next experiment", "internal-agent@1.0.0"),
}


def default_registry_config() -> CapabilityRegistryConfig:
    tools = (
        ToolDescriptor(
            id="research.search",
            version="1.0.0",
            name="Agno web search",
            function_name="search_web",
            side_effect=SideEffectClass.READ_ONLY,
            timeout_seconds=10,
            retry_budget=1,
        ),
        ToolDescriptor(
            id="research.browser",
            version="1.0.0",
            name="Safe browser extraction",
            function_name="extract_web_page",
            side_effect=SideEffectClass.READ_ONLY,
            timeout_seconds=10,
            retry_budget=1,
        ),
    )
    profiles = (
        CapabilityProfile(
            id="research-collector",
            version="1.0.0",
            tool_refs=tuple(tool.ref for tool in tools),
        ),
        CapabilityProfile(id="evidence-reviewer", version="1.0.0"),
        CapabilityProfile(id="internal-agent", version="1.0.0"),
    )
    agents = tuple(
        AgentDefinition(
            id=agent_id,
            version="1.0.0",
            name=name,
            role=role,
            capability_profile_ref=profile,
        )
        for agent_id, (name, role, profile) in _AGENT_SPECS.items()
    )
    policy = CapabilityPolicy(
        id="research-read",
        version="1.0.0",
        subjects=frozenset(
            f"{agent_id}@1.0.0"
            for agent_id in ("product", "competitor", "audience", "trend")
        ),
        resources=frozenset(tool.ref for tool in tools),
        actions=frozenset({"bind", "invoke"}),
        side_effects=frozenset({SideEffectClass.READ_ONLY}),
        effect=PolicyEffect.ALLOW,
    )
    return CapabilityRegistryConfig(
        agents=agents,
        tools=tools,
        policies=(policy,),
        profiles=profiles,
    )


def default_registry() -> CapabilityRegistry:
    return CapabilityRegistry(default_registry_config())