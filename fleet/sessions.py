"""Per-run project state, `fleet/sessions.json`.

Holds what changes on every run: each project's Claude Code session ID and the
last commit AIPM has seen. Machine-local and out of git. The fleet server
writes it once dispatch and reconcile exist; until then it is read only.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_SESSIONS_PATH = Path(__file__).resolve().parent / "sessions.json"


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    last_seen_commit: str | None = None


def load_sessions(path: Path = DEFAULT_SESSIONS_PATH) -> dict[str, SessionState]:
    """Read sessions.json. A missing file means no project has run yet."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8")) or {}
    return {name: SessionState.model_validate(state) for name, state in data.items()}
