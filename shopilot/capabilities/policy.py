from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict

from .models import PolicyEffect, SideEffectClass
from .registry import CapabilityRegistry


class CapabilityDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    allowed: bool
    policy_ref: str | None
    subject: str
    resource: str
    action: str
    side_effect: SideEffectClass
    tenant: str
    environment: str
    reason: str


class CapabilityDenied(PermissionError):
    code = "capability_denied"

    def __init__(self, decision: CapabilityDecision):
        super().__init__(decision.reason)
        self.decision = decision


class CapabilityAuthorizer:
    def __init__(
        self,
        registry: CapabilityRegistry,
        audit_sink: Callable[[dict[str, Any]], None] | None = None,
    ):
        self.registry = registry
        self.audit_sink = audit_sink

    @staticmethod
    def _matches(value: str, allowed: frozenset[str]) -> bool:
        return "*" in allowed or value in allowed

    def decide(
        self,
        *,
        subject: str,
        resource: str,
        action: str,
        side_effect: SideEffectClass,
        tenant: str,
        environment: str,
    ) -> CapabilityDecision:
        matches = [
            policy
            for policy in self.registry.policies
            if self._matches(subject, policy.subjects)
            and self._matches(resource, policy.resources)
            and self._matches(action, policy.actions)
            and side_effect in policy.side_effects
            and policy.tenant in {"*", tenant}
            and policy.environment in {"*", environment}
        ]
        selected = next((item for item in matches if item.effect == PolicyEffect.DENY), None)
        if selected is None:
            selected = next((item for item in matches if item.effect == PolicyEffect.ALLOW), None)
        allowed = bool(selected and selected.effect == PolicyEffect.ALLOW)
        decision = CapabilityDecision(
            allowed=allowed,
            policy_ref=selected.ref if selected else None,
            subject=subject,
            resource=resource,
            action=action,
            side_effect=side_effect,
            tenant=tenant,
            environment=environment,
            reason="allowed" if allowed else "no_matching_allow_policy",
        )
        if self.audit_sink is not None:
            self.audit_sink(
                {
                    "event_type": "capability_allowed" if allowed else "capability_denied",
                    "subject": subject,
                    "resource": resource,
                    "action": action,
                    "side_effect": side_effect.value,
                    "tenant": tenant,
                    "environment": environment,
                    "policy_ref": decision.policy_ref,
                }
            )
        return decision

    def authorize(self, **context: Any) -> CapabilityDecision:
        decision = self.decide(**context)
        if not decision.allowed:
            raise CapabilityDenied(decision)
        return decision


def build_tool_authorization_hook(
    *,
    registry: CapabilityRegistry,
    authorizer: CapabilityAuthorizer,
    subject: str,
    tenant: str,
    environment: str,
):
    def authorize_tool(function_name, function, arguments):
        descriptor = registry.tool_by_function_name(function_name)
        if descriptor is None:
            decision = CapabilityDecision(
                allowed=False,
                policy_ref=None,
                subject=subject,
                resource=function_name,
                action="invoke",
                side_effect=SideEffectClass.EXTERNAL_WRITE,
                tenant=tenant,
                environment=environment,
                reason="unregistered_tool",
            )
            if authorizer.audit_sink is not None:
                authorizer.audit_sink(
                    {
                        "event_type": "capability_denied",
                        "subject": subject,
                        "resource": function_name,
                        "action": "invoke",
                        "side_effect": SideEffectClass.EXTERNAL_WRITE.value,
                        "tenant": tenant,
                        "environment": environment,
                        "policy_ref": None,
                    }
                )
            raise CapabilityDenied(decision)
        authorizer.authorize(
            subject=subject,
            resource=descriptor.ref,
            action="invoke",
            side_effect=descriptor.side_effect,
            tenant=tenant,
            environment=environment,
        )
        return function(**arguments)

    return authorize_tool
