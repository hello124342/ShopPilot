from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any


SECRET_KEYS = {"api_key", "authorization", "token", "secret", "password"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if any(secret in key.lower() for secret in SECRET_KEYS) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(bearer\s+)[a-z0-9._-]+", r"\1[REDACTED]", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in ("request_id", "run_id", "runtime_mode", "status", "method", "path", "latency_ms"):
            if hasattr(record, name):
                document[name] = getattr(record, name)
        return json.dumps(redact(document), ensure_ascii=False)


def configure_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("shopilot")
    logger.setLevel(level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.propagate = False
    return logger
