from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

class AgentBindingStore:
    """Versioned operator overrides for registry bindings.

    The registry remains the source of approved capability definitions. This
    store only records administrator-selected references and never stores
    credentials or runtime objects.
    """
    def __init__(self, root: str | Path):
        self.path = Path(root) / "capability-bindings.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, agent_id: str) -> dict[str, Any] | None:
        return self.all().get(agent_id)

    def put(self, agent_id: str, *, skills: list[str], tools: list[str], mcp_servers: list[str]) -> dict[str, Any]:
        values = self.all()
        current = values.get(agent_id, {})
        version = int(current.get("binding_version", 0)) + 1
        values[agent_id] = {"agent_id": agent_id, "binding_version": version, "skills": skills, "tools": tools, "mcp_servers": mcp_servers}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        return values[agent_id]
