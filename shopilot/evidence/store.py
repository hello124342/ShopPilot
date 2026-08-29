from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Citation, EvidenceConflict, EvidenceRecord


class EvidenceStore:
    """Tenant-scoped SQLite catalog for normalized research evidence."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence_records (
                    evidence_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    UNIQUE (tenant_id, run_id, content_hash)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_run
                    ON evidence_records (tenant_id, run_id);
                CREATE TABLE IF NOT EXISTS evidence_citations (
                    citation_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    citation_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_citation_run
                    ON evidence_citations (tenant_id, run_id);
                CREATE TABLE IF NOT EXISTS evidence_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    conflict_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_conflict_run
                    ON evidence_conflicts (tenant_id, run_id);
                """
            )

    def put(self, record: EvidenceRecord) -> EvidenceRecord:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT record_json FROM evidence_records WHERE tenant_id=? AND run_id=? AND content_hash=?",
                (record.tenant_id, record.run_id, record.content_hash),
            ).fetchone()
            if existing:
                return EvidenceRecord.model_validate_json(existing["record_json"])
            connection.execute(
                "INSERT INTO evidence_records VALUES (?, ?, ?, ?, ?)",
                (
                    record.evidence_id,
                    record.tenant_id,
                    record.run_id,
                    record.content_hash,
                    record.model_dump_json(),
                ),
            )
        return record

    def get(self, evidence_id: str, *, tenant_id: str = "default") -> EvidenceRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM evidence_records WHERE evidence_id=? AND tenant_id=?",
                (evidence_id, tenant_id),
            ).fetchone()
        return EvidenceRecord.model_validate_json(row["record_json"]) if row else None

    def list_for_run(self, run_id: str, *, tenant_id: str = "default") -> list[EvidenceRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM evidence_records WHERE tenant_id=? AND run_id=? ORDER BY rowid",
                (tenant_id, run_id),
            ).fetchall()
        return [EvidenceRecord.model_validate_json(row["record_json"]) for row in rows]

    def put_citation(
        self, citation: Citation, *, run_id: str, tenant_id: str = "default"
    ) -> Citation:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO evidence_citations VALUES (?, ?, ?, ?)",
                (citation.citation_id, tenant_id, run_id, citation.model_dump_json()),
            )
        return citation

    def list_citations(self, run_id: str, *, tenant_id: str = "default") -> list[Citation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT citation_json FROM evidence_citations WHERE tenant_id=? AND run_id=? ORDER BY rowid",
                (tenant_id, run_id),
            ).fetchall()
        return [Citation.model_validate_json(row["citation_json"]) for row in rows]

    def put_conflict(self, conflict: EvidenceConflict) -> EvidenceConflict:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO evidence_conflicts VALUES (?, ?, ?, ?)",
                (
                    conflict.conflict_id,
                    conflict.tenant_id,
                    conflict.run_id,
                    conflict.model_dump_json(),
                ),
            )
        return conflict

    def list_conflicts(self, run_id: str, *, tenant_id: str = "default") -> list[EvidenceConflict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT conflict_json FROM evidence_conflicts WHERE tenant_id=? AND run_id=? ORDER BY rowid",
                (tenant_id, run_id),
            ).fetchall()
        return [EvidenceConflict.model_validate_json(row["conflict_json"]) for row in rows]
