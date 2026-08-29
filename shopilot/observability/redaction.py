from __future__ import annotations

import re
from typing import Any


SECRET_KEYS = frozenset({"api_key", "authorization", "token", "secret", "password", "credential", "cookie"})
SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/-]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)(api[_-]?key|password|secret)\s*[:=]\s*[^\s,;]+"),
)


class TraceRedactor:
    def __init__(self, configured_secrets: list[str] | None = None):
        self.configured_secrets = tuple(value for value in (configured_secrets or []) if value)

    def redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): "[REDACTED]"
                if any(secret in str(key).lower() for secret in SECRET_KEYS)
                else self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            redacted = value
            for secret in self.configured_secrets:
                redacted = redacted.replace(secret, "[REDACTED]")
            for pattern in SECRET_PATTERNS:
                redacted = pattern.sub("[REDACTED]", redacted)
            return redacted
        return value

    def contains_secret(self, value: Any) -> bool:
        return self.redact(value) != value
