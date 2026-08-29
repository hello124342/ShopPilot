from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Asset, AssetLineage, AssetStatus


class AssetCatalog:
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
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    asset_json TEXT NOT NULL,
                    PRIMARY KEY (asset_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_asset_tenant_hash
                    ON assets (tenant_id, sha256, status);
                CREATE INDEX IF NOT EXISTS idx_asset_run
                    ON assets (tenant_id, run_id);
                CREATE TABLE IF NOT EXISTS asset_run_links (
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    asset_version INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, run_id, asset_id, asset_version)
                );
                CREATE TABLE IF NOT EXISTS asset_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    asset_version INTEGER NOT NULL,
                    lineage_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    asset_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def put(self, asset: Asset) -> Asset:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    asset.asset_id,
                    asset.version,
                    asset.tenant_id,
                    asset.run_id,
                    asset.sha256,
                    asset.status.value,
                    asset.size_bytes,
                    asset.model_dump_json(),
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO asset_run_links VALUES (?, ?, ?, ?)",
                (asset.tenant_id, asset.run_id, asset.asset_id, asset.version),
            )
        return asset

    def link_run(self, asset: Asset, run_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO asset_run_links VALUES (?, ?, ?, ?)",
                (asset.tenant_id, run_id, asset.asset_id, asset.version),
            )

    def replace(self, asset: Asset) -> Asset:
        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE assets SET status=?, asset_json=? WHERE asset_id=? AND version=? AND tenant_id=?",
                (
                    asset.status.value,
                    asset.model_dump_json(),
                    asset.asset_id,
                    asset.version,
                    asset.tenant_id,
                ),
            ).rowcount
        if not changed:
            raise ValueError("asset_not_found")
        return asset

    def get(self, asset_id: str, version: int, *, tenant_id: str = "default") -> Asset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT asset_json FROM assets WHERE asset_id=? AND version=? AND tenant_id=?",
                (asset_id, version, tenant_id),
            ).fetchone()
        return Asset.model_validate_json(row["asset_json"]) if row else None

    def latest(self, asset_id: str, *, tenant_id: str = "default") -> Asset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT asset_json FROM assets WHERE asset_id=? AND tenant_id=? ORDER BY version DESC LIMIT 1",
                (asset_id, tenant_id),
            ).fetchone()
        return Asset.model_validate_json(row["asset_json"]) if row else None

    def find_ready_hash(self, digest: str, *, tenant_id: str = "default") -> Asset | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT asset_json FROM assets WHERE tenant_id=? AND sha256=? AND status=? ORDER BY rowid LIMIT 1",
                (tenant_id, digest, AssetStatus.READY.value),
            ).fetchone()
        return Asset.model_validate_json(row["asset_json"]) if row else None

    def list_for_run(self, run_id: str, *, tenant_id: str = "default") -> list[Asset]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT a.asset_json FROM assets a JOIN asset_run_links l ON a.asset_id=l.asset_id AND a.version=l.asset_version AND a.tenant_id=l.tenant_id WHERE l.tenant_id=? AND l.run_id=? ORDER BY a.rowid",
                (tenant_id, run_id),
            ).fetchall()
        return [Asset.model_validate_json(row["asset_json"]) for row in rows]

    def usage_bytes(self, *, tenant_id: str = "default") -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) AS total FROM assets WHERE tenant_id=? AND status NOT IN (?, ?)",
                (tenant_id, AssetStatus.DELETED.value, AssetStatus.FAILED.value),
            ).fetchone()
        return int(row["total"])

    def put_lineage(self, lineage: AssetLineage) -> AssetLineage:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO asset_lineage VALUES (?, ?, ?, ?, ?, ?)",
                (
                    lineage.lineage_id,
                    lineage.tenant_id,
                    lineage.run_id,
                    lineage.derived.asset_id,
                    lineage.derived.version,
                    lineage.model_dump_json(),
                ),
            )
        return lineage

    def lineage(self, asset_id: str, version: int, *, tenant_id: str = "default") -> list[AssetLineage]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT lineage_json FROM asset_lineage WHERE tenant_id=? AND asset_id=? AND asset_version=? ORDER BY rowid",
                (tenant_id, asset_id, version),
            ).fetchall()
        return [AssetLineage.model_validate_json(row["lineage_json"]) for row in rows]

    def event(self, asset: Asset, event_type: str, payload: dict[str, Any] | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO asset_events (tenant_id, asset_id, asset_version, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    asset.tenant_id,
                    asset.asset_id,
                    asset.version,
                    event_type,
                    json.dumps(payload or {}, ensure_ascii=True),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def events(self, asset_id: str, *, tenant_id: str = "default") -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM asset_events WHERE tenant_id=? AND asset_id=? ORDER BY sequence",
                (tenant_id, asset_id),
            ).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload_json"])} for row in rows]
