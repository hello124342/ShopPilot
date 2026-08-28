from enum import StrEnum
class FailureInjection(StrEnum):
    INVALID_SCHEMA="invalid_schema"
    EVIDENCE_CONFLICT="evidence_conflict"
    RESEARCH_TIMEOUT="research_timeout"
    POLICY_VIOLATION="policy_violation"
    DUPLICATE_PUBLISH="duplicate_publish"

