from __future__ import annotations
import json
import os
from pathlib import Path
from .schemas import Artifact, ApprovalEvent, RunRecord, TraceEvent

class RunStore:
    """Small, single-process local store with append-only event streams."""

    def __init__(self, root: str | Path = ".shopilot"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id: str, create: bool = False) -> Path:
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("invalid_run_id")
        path = self.root / run_id
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def _path(self, run_id: str, name: str, create: bool = False) -> Path:
        return self._run_dir(run_id, create=create) / name
    def append(self, run_id: str, name: str, value: object) -> None:
        with self._path(run_id, name, create=True).open("a", encoding="utf-8") as f:
            f.write(json.dumps(value.model_dump(mode="json"), ensure_ascii=False) + "\n")
            f.flush()
    def read(self, run_id: str, name: str) -> list[dict]:
        p = self._path(run_id, name)
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    def artifact(self, run_id: str, artifact: Artifact) -> None: self.append(run_id, "artifacts.jsonl", artifact)
    def trace(self, event: TraceEvent) -> None: self.append(event.run_id, "trace.jsonl", event)
    def approval(self, event: ApprovalEvent) -> None: self.append(event.run_id, "approvals.jsonl", event)
    def save_run(self, run: RunRecord) -> None:
        target = self._path(run.run_id, "run.json", create=True)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(run.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, target)
    def get_run(self, run_id: str) -> dict | None:
        p=self._path(run_id,"run.json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    def save_evaluation(self, run_id: str, value: object) -> None:
        self.append(run_id, "evaluations.jsonl", value)
        self._path(run_id,"evaluation.json",create=True).write_text(json.dumps(value.model_dump(mode="json"),ensure_ascii=False,indent=2),encoding="utf-8")

    def get_evaluation(self, run_id: str) -> dict | None:
        path = self._path(run_id, "evaluation.json")
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def list_runs(self, limit: int = 100) -> list[dict]:
        runs: list[dict] = []
        for directory in self.root.iterdir():
            path = directory / "run.json"
            if directory.is_dir() and path.exists():
                try:
                    runs.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
        return sorted(runs, key=lambda item: item.get("updated_at", ""), reverse=True)[:limit]

    def health(self) -> dict:
        probe = self.root / ".write-probe"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return {"writable": True, "path": str(self.root)}
        except OSError:
            return {"writable": False, "path": str(self.root)}
