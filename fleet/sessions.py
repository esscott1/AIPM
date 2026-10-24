"""Per-run project state, `fleet/sessions.json`.

Holds what changes on every run: each project's Claude Code session ID and the
last commit AIPM has seen. Machine-local and out of git. dispatch writes
`session_id`; reconcile will write `last_seen_commit`.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from fleet.files import write_atomic

DEFAULT_SESSIONS_PATH = Path(__file__).resolve().parent / "sessions.json"

# Jobs for different projects can finish at once; each update is a
# read-modify-write of the whole file.
_write_lock = threading.Lock()


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


def save_sessions(sessions: dict[str, SessionState], path: Path = DEFAULT_SESSIONS_PATH) -> None:
    data = {name: state.model_dump() for name, state in sessions.items()}
    write_atomic(path, json.dumps(data, indent=2) + "\n")


def record_session_id(project: str, session_id: str, path: Path = DEFAULT_SESSIONS_PATH) -> None:
    """Save the session a project's team last ran in, so the next dispatch resumes it."""
    with _write_lock:
        sessions = load_sessions(path)
        state = sessions.get(project, SessionState())
        sessions[project] = state.model_copy(update={"session_id": session_id})
        save_sessions(sessions, path)
