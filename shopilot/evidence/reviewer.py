from __future__ import annotations

from collections import defaultdict

from ..schemas import Evidence, ResearchPackage
from .models import Citation, EvidenceConflict, EvidenceRecord, EvidenceSourceType
from .store import EvidenceStore


def normalize_legacy_evidence(
    evidence: Evidence,
    *,
    run_id: str,
    collector_id: str = "legacy-fixture",
    tenant_id: str = "default",
) -> EvidenceRecord:
    return EvidenceRecord.from_content(
        content=f"{evidence.source}\n{evidence.claim}",
        tenant_id=tenant_id,
        run_id=run_id,
        subject=evidence.subject or evidence.claim,
        claim=evidence.claim,
        source_type=(
            EvidenceSourceType.WEB
            if evidence.source.startswith(("http://", "https://"))
            else EvidenceSourceType.FIXTURE
        ),
        source_url=evidence.source,
        excerpt=evidence.claim,
        collector_id=collector_id,
        tool_call_id=evidence.tool_call_id or "legacy-fixture-call",
        confidence=evidence.confidence,
    )


class EvidenceReviewService:
    """Deterministic validation after the tool-free Agno reviewer stage."""

    def __init__(self, store: EvidenceStore):
        self.store = store

    @staticmethod
    def _claims(package: ResearchPackage) -> list[str]:
        return [
            *package.product_facts,
            *package.audience_insights,
            *package.competitor_observations,
            *package.trend_signals,
            *package.opportunities,
            *package.risks,
        ]

    def normalize(
        self, package: ResearchPackage, records: list[EvidenceRecord]
    ) -> tuple[ResearchPackage, list[EvidenceRecord]]:
        persisted = [self.store.put(record) for record in records]
        normalized_evidence = [
            Evidence(
                claim=record.claim,
                source=record.source_url,
                confidence=record.confidence,
                evidence_id=record.evidence_id,
                content_hash=record.content_hash,
                subject=record.subject,
                tool_call_id=record.tool_call_id,
            )
            for record in persisted
        ]
        return (
            package.model_copy(
                update={
                    "evidence": normalized_evidence,
                    "evidence_record_ids": [record.evidence_id for record in persisted],
                }
            ),
            persisted,
        )

    def review(
        self,
        package: ResearchPackage,
        records: list[EvidenceRecord],
    ) -> tuple[ResearchPackage, list[Citation], list[EvidenceConflict]]:
        package, persisted = self.normalize(package, records)
        by_claim: dict[str, list[EvidenceRecord]] = defaultdict(list)
        by_subject: dict[str, list[EvidenceRecord]] = defaultdict(list)
        for record in persisted:
            by_claim[record.claim.strip().casefold()].append(record)
            by_subject[record.subject.strip().casefold()].append(record)

        citations: list[Citation] = []
        for claim in self._claims(package):
            matches = by_claim.get(claim.strip().casefold(), [])
            citations.append(
                Citation(
                    claim=claim,
                    evidence_ids=tuple(item.evidence_id for item in matches),
                    supported=bool(matches),
                    reason="" if matches else "unsupported_claim",
                )
            )

        for citation in citations:
            run_id = persisted[0].run_id if persisted else "unknown"
            tenant_id = persisted[0].tenant_id if persisted else "default"
            self.store.put_citation(citation, run_id=run_id, tenant_id=tenant_id)

        conflicts: list[EvidenceConflict] = []
        for subject, candidates in by_subject.items():
            if len({item.claim.strip().casefold() for item in candidates}) < 2:
                continue
            conflict = EvidenceConflict(
                tenant_id=candidates[0].tenant_id,
                run_id=candidates[0].run_id,
                subject=subject,
                evidence_ids=tuple(item.evidence_id for item in candidates),
                description="Sources contain incompatible claims for the same subject.",
            )
            conflicts.append(self.store.put_conflict(conflict))

        coverage = sum(item.supported for item in citations) / len(citations) if citations else 1.0
        reviewed = package.model_copy(
            update={
                "citation_ids": [citation.citation_id for citation in citations],
                "citation_coverage": coverage,
                "conflicts": [conflict.conflict_id for conflict in conflicts],
            }
        )
        return reviewed, citations, conflicts
