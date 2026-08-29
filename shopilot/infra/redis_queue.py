from __future__ import annotations

import json
from contextlib import contextmanager
from redis import Redis

class RedisCoordinator:
    JOB_STREAM = "shopilot:jobs"
    DEAD_LETTER_STREAM = "shopilot:jobs:dead-letter"

    def __init__(self, url: str):
        self.client = Redis.from_url(url, decode_responses=True, health_check_interval=30)

    def health(self) -> dict:
        try:
            return {"status": "ready" if self.client.ping() else "not_ready"}
        except Exception as exc:
            return {"status": "not_ready", "error_code": "redis_unavailable", "detail": type(exc).__name__}

    def ensure_group(self, group: str = "shopilot-workers") -> None:
        try:
            self.client.xgroup_create(self.JOB_STREAM, group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(self, payload: dict, *, idempotency_key: str) -> str:
        marker = f"shopilot:idempotency:{idempotency_key}"
        if not self.client.set(marker, "1", nx=True, ex=7 * 24 * 3600):
            return "duplicate"
        return str(self.client.xadd(self.JOB_STREAM, {"payload": json.dumps(payload, ensure_ascii=False), "idempotency_key": idempotency_key}))

    def publish_event(self, run_id: str, event: dict) -> str:
        return str(self.client.xadd(f"shopilot:run:{run_id}:events", {"event": json.dumps(event, ensure_ascii=False)}, maxlen=5000, approximate=True))

    @contextmanager
    def lock(self, name: str, timeout: int = 300):
        lock = self.client.lock(f"shopilot:lock:{name}", timeout=timeout, blocking_timeout=1)
        if not lock.acquire():
            raise RuntimeError("execution_lock_unavailable")
        try:
            yield
        finally:
            lock.release()
