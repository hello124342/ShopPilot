from __future__ import annotations

import json
import os
import socket
import time

from .infra import Database, RedisCoordinator
from .infra.models import AuditEvent, Job
from .settings import Settings

GROUP = "shopilot-workers"

def process_message(database: Database, coordinator: RedisCoordinator, message_id: str, fields: dict) -> None:
    payload = json.loads(fields["payload"])
    job_id = payload.get("job_id")
    if not job_id:
        coordinator.client.xack(coordinator.JOB_STREAM, GROUP, message_id)
        return
    with database.transaction() as session:
        job = session.get(Job, job_id)
        if job is None or job.status == "completed":
            coordinator.client.xack(coordinator.JOB_STREAM, GROUP, message_id)
            return
        job.status = "running"
        job.attempt += 1
        session.add(AuditEvent(event_type="job_started", aggregate_id=job.id, payload_json={"worker": socket.gethostname(), "attempt": job.attempt}, tenant_id=job.tenant_id))
    # Stage execution is delegated to the fixed Agno campaign workflow by the
    # application service. The queue worker owns idempotency, locking and event
    # delivery; it never implements an agent loop or scheduler.
    coordinator.publish_event(payload["run_id"], {"event_type": "job_started", "job_id": job_id, "stage_id": payload["stage_id"]})
    coordinator.client.xack(coordinator.JOB_STREAM, GROUP, message_id)

def main() -> None:
    settings = Settings()
    database = Database(settings.database_url)
    coordinator = RedisCoordinator(settings.redis_url)
    coordinator.ensure_group(GROUP)
    consumer = f"worker-{socket.gethostname()}-{os.getpid()}"
    while True:
        messages = coordinator.client.xreadgroup(GROUP, consumer, {coordinator.JOB_STREAM: ">"}, count=1, block=5000)
        for _, entries in messages:
            for message_id, fields in entries:
                try:
                    with coordinator.lock(f"stage:{json.loads(fields['payload']).get('stage_run_id', message_id)}"):
                        process_message(database, coordinator, message_id, fields)
                except Exception as exc:
                    coordinator.publish_event(json.loads(fields["payload"]).get("run_id", "unknown"), {"event_type": "job_error", "error_code": type(exc).__name__})
                    time.sleep(1)

if __name__ == "__main__":
    main()
