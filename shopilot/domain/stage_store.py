from __future__ import annotations

import json
import os
from pathlib import Path
from .stages import StageApproval, StageRun

class StageStore:
    """Atomic local compatibility store for stage gates.

    It is deliberately isolated from the legacy run JSONL store so existing
    clients remain compatible while PostgreSQL migration is introduced.
    """
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, run_id: str, name: str, create: bool = False) -> Path:
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("invalid_run_id")
        directory = self.root / run_id
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        return directory / name

    def save(self, run_id: str, stages: list[StageRun]) -> None:
        target = self._path(run_id, "stages.json", True)
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps([s.model_dump(mode="json") for s in stages], ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, target)

    def get(self, run_id: str) -> list[StageRun]:
        path = self._path(run_id, "stages.json")
        if not path.exists():
            return []
        return [StageRun.model_validate(v) for v in json.loads(path.read_text(encoding="utf-8"))]

    def save_approvals(self, run_id: str, approvals: list[StageApproval]) -> None:
        self._path(run_id, "stage-approvals.json", True).write_text(json.dumps([a.model_dump(mode="json") for a in approvals], ensure_ascii=False, indent=2), encoding="utf-8")

    def approvals(self, run_id: str) -> list[StageApproval]:
        path = self._path(run_id, "stage-approvals.json")
        if not path.exists():
            return []
        return [StageApproval.model_validate(v) for v in json.loads(path.read_text(encoding="utf-8"))]
