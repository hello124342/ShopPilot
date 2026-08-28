from enum import StrEnum

class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ANALYZED = "analyzed"
    OPTIMIZED = "optimized"
    REVISION_REQUIRED = "revision_required"
    FAILED = "failed"
    CANCELLED = "cancelled"
    HUMAN_HANDOFF = "human_handoff"

