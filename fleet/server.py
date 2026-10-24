"""The fleet MCP server. The PM session reaches it through `.mcp.json`.

    uv run python -m fleet.server

Speaks MCP over stdio, so nothing here may print to stdout. The registry and
sessions file are re-read on every call, because other fleet tools write them.
Set AIPM_REGISTRY or AIPM_SESSIONS to point at other files (tests do).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ValidationError

from fleet.registry import DEFAULT_REGISTRY_PATH, Budget, Registry, RegistryError, load_registry
from fleet.sessions import DEFAULT_SESSIONS_PATH, SessionState, load_sessions

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)

INSTRUCTIONS = (
    "AIPM fleet server. Each managed repo has one project team. "
    "list_projects shows the registry; project_status shows one project's "
    "registry entry, session state and live git state."
)


class ProjectSummary(BaseModel):
    name: str
    path: str
    status: str
    goal: str


class GitState(BaseModel):
    path_exists: bool
    branch: str | None = None
    last_commit: str | None = None
    uncommitted_changes: int | None = None
    error: str | None = None


class ProjectStatus(BaseModel):
    name: str
    path: str
    remote: str
    goal: str
    model: str
    permission_mode: str
    budget: Budget
    status: str
    session: SessionState
    git: GitState


def _git(path: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {args[0]} failed")
    return proc.stdout.strip()


def read_git_state(path: Path) -> GitState:
    """Local facts only: no fetch, so this never touches the network."""
    if not path.exists():
        return GitState(path_exists=False, error="path not found; the repo may have moved")
    try:
        branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
        last_commit = _git(path, "log", "-1", "--format=%h %s (%cr)")
        changes = _git(path, "status", "--porcelain")
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        return GitState(path_exists=True, error=str(e))
    return GitState(
        path_exists=True,
        branch=branch,
        last_commit=last_commit,
        uncommitted_changes=len(changes.splitlines()),
    )


def _load(registry_path: Path) -> Registry:
    # ToolError carries the message to the PM; any other exception reaches it
    # only as "Error executing tool".
    try:
        return load_registry(registry_path)
    except (ValidationError, yaml.YAMLError) as e:
        raise ToolError(f"{registry_path} is invalid: {e}") from e


def create_server(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    sessions_path: Path = DEFAULT_SESSIONS_PATH,
) -> MCPServer:
    server = MCPServer("fleet", instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def list_projects() -> list[ProjectSummary]:
        """List every project AIPM manages, from projects.yaml.

        Returns each project's name, repo path, status (active or paused) and goal.
        An empty list means no repo has been adopted yet. Does not touch the repos;
        use project_status for git state.
        """
        registry = _load(registry_path)
        return [
            ProjectSummary(name=name, path=str(p.path), status=p.status, goal=p.goal)
            for name, p in registry.projects.items()
        ]

    @server.tool(annotations=READ_ONLY)
    def project_status(project: str) -> ProjectStatus:
        """Show one project's registry entry, session state and local git state.

        `project` is the registry name from list_projects (lowercase, e.g. "montecarlo").
        Git state is read from the local checkout without fetching, so it shows the
        current branch, last commit and count of uncommitted changes, but not whether
        the remote has moved. Session fields are empty until the project's team has run.
        Fails if the name is not registered.
        """
        try:
            entry = _load(registry_path).get(project)
        except RegistryError as e:
            raise ToolError(str(e)) from e
        session = load_sessions(sessions_path).get(project, SessionState())
        return ProjectStatus(
            name=project,
            path=str(entry.path),
            remote=entry.remote,
            goal=entry.goal,
            model=entry.model,
            permission_mode=entry.permission_mode,
            budget=entry.budget,
            status=entry.status,
            session=session,
            git=read_git_state(entry.path),
        )

    return server


def main() -> None:
    registry_path = Path(os.environ.get("AIPM_REGISTRY", DEFAULT_REGISTRY_PATH))
    sessions_path = Path(os.environ.get("AIPM_SESSIONS", DEFAULT_SESSIONS_PATH))
    create_server(registry_path, sessions_path).run("stdio")


if __name__ == "__main__":
    main()
