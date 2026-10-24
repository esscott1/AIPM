"""The fleet MCP server. The PM session reaches it through `.mcp.json`.

    uv run python -m fleet.server

Speaks MCP over stdio, so nothing here may print to stdout. The registry and
sessions file are re-read on every call, because other fleet tools write them.
Set AIPM_REGISTRY, AIPM_SESSIONS or AIPM_JOBS to point at other files (tests do).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from collections.abc import Sequence
from pathlib import Path

import yaml
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ValidationError

from fleet.jobs import DEFAULT_JOBS_DIR, Job, JobError, JobStore
from fleet.registry import (
    DEFAULT_REGISTRY_PATH,
    Budget,
    PermissionMode,
    Project,
    Registry,
    RegistryError,
    load_registry,
)
from fleet.runner import run_job
from fleet.sessions import DEFAULT_SESSIONS_PATH, SessionState, load_sessions

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True)
# A team may edit and commit in its repo, but only on feature branches.
DISPATCH = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True)

INSTRUCTIONS = (
    "AIPM fleet server. Each managed repo has one project team. "
    "list_projects shows the registry; project_status shows one project's "
    "registry entry, session state and live git state. dispatch starts a task "
    "for a team in the background and returns a job; get_report returns the "
    "job's state and, when it finishes, the team's report."
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


def _get_project(registry_path: Path, name: str) -> Project:
    try:
        return _load(registry_path).get(name)
    except RegistryError as e:
        raise ToolError(str(e)) from e


def choose_mode(name: str, allowed: PermissionMode, requested: PermissionMode | None) -> PermissionMode:
    """The registry's permission_mode is the ceiling; a dispatch may only tighten it."""
    if requested is None:
        return allowed
    if requested == "acceptEdits" and allowed == "plan":
        raise ToolError(
            f"{name} is limited to plan mode; change its permission_mode in projects.yaml to allow acceptEdits"
        )
    return requested


def create_server(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    sessions_path: Path = DEFAULT_SESSIONS_PATH,
    jobs_dir: Path = DEFAULT_JOBS_DIR,
    claude: Sequence[str] | None = None,
) -> MCPServer:
    """`claude` is the command that starts Claude Code; tests pass a stand-in."""
    server = MCPServer("fleet", instructions=INSTRUCTIONS)
    store = JobStore(jobs_dir)

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
        entry = _get_project(registry_path, project)
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

    @server.tool(annotations=DISPATCH)
    def dispatch(project: str, instruction: str, mode: PermissionMode | None = None) -> Job:
        """Send a task to a project's team. Returns at once with a running job; the team works in the background.

        `project` is the registry name from list_projects. `instruction` is the task, in
        plain words. `mode` is "plan" (read-only: the team investigates and proposes) or
        "acceptEdits" (the team may edit files); it defaults to the project's
        permission_mode and can never exceed it.

        The team resumes its saved session in its own repo folder, works on a feature
        branch, doesn't open a pull request, and ends with a structured report. Poll
        get_report with the job's id. Tasks often take several minutes.

        Fails if the project is unknown or paused, its repo folder is missing, or it is
        already running a job (one at a time per project).
        """
        if not instruction.strip():
            raise ToolError("instruction is empty")
        entry = _get_project(registry_path, project)
        if entry.status == "paused":
            raise ToolError(f"{project} is paused; resume it before dispatching")
        run_mode = choose_mode(project, entry.permission_mode, mode)
        if not entry.path.exists():
            raise ToolError(f"{entry.path} not found; the repo may have moved")
        command = list(claude) if claude else [shutil.which("claude") or ""]
        if not command[0]:
            raise ToolError("claude is not on PATH; install Claude Code and sign in")

        session = load_sessions(sessions_path).get(project, SessionState())
        try:
            job = store.start(project, instruction, run_mode, entry.budget.max_tokens_per_job, session.session_id)
        except JobError as e:
            raise ToolError(str(e)) from e
        threading.Thread(
            target=run_job,
            args=(job.model_copy(), entry, command, store, sessions_path),
            name=f"job {job.id}",
            daemon=True,
        ).start()
        return job

    @server.tool(annotations=READ_ONLY)
    def get_report(job: str) -> Job:
        """Show a dispatched job's state and, once it has finished, the team's report.

        `job` is the id that dispatch returned. state is one of:
        - running: the team is still working; ask again later.
        - succeeded: `report` holds summary, branch, changed, tests, blockers and next_step.
        - failed: `error` says why, for example hitting the plan's usage limit (with its
          reset time) or a session that could not be resumed.
        - lost: the fleet server stopped mid-job; check project_status before retrying.

        tokens_used counts all tokens the run reported. over_token_cap is true when that
        exceeds the project's max_tokens_per_job; the job is flagged, never stopped.
        """
        try:
            return store.get(job)
        except JobError as e:
            raise ToolError(str(e)) from e

    return server


def main() -> None:
    registry_path = Path(os.environ.get("AIPM_REGISTRY", DEFAULT_REGISTRY_PATH))
    sessions_path = Path(os.environ.get("AIPM_SESSIONS", DEFAULT_SESSIONS_PATH))
    jobs_dir = Path(os.environ.get("AIPM_JOBS", DEFAULT_JOBS_DIR))
    create_server(registry_path, sessions_path, jobs_dir).run("stdio")


if __name__ == "__main__":
    main()
