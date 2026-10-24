"""Background jobs, one JSON file each in `fleet/jobs/`.

dispatch creates a job and runs the team in a background thread; get_report
reads the job's file. Job files are machine-local and out of git.
"""

from __future__ import annotations

import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from fleet.files import write_atomic
from fleet.registry import PermissionMode

DEFAULT_JOBS_DIR = Path(__file__).resolve().parent / "jobs"

JobState = Literal["running", "succeeded", "failed", "lost"]

# A running job's thread rewrites its file at least this often. A job still
# marked running whose file is older than STALE_AFTER belonged to a fleet
# server that stopped, so it is reported as lost rather than running forever.
HEARTBEAT_SECONDS = 30
STALE_AFTER = timedelta(seconds=HEARTBEAT_SECONDS * 4)

JOB_ID_PATTERN = r"^[a-z0-9][a-z0-9-]*$"

LOST_MESSAGE = (
    "the fleet server running this job stopped before the job finished. The team "
    "may have finished anyway: check project_status before dispatching again."
)


class JobError(Exception):
    """A job operation that cannot be done, such as a second job for a busy project."""


class Report(BaseModel):
    """The end-of-task report every team returns, enforced with `claude --json-schema`."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="What was done, in two or three sentences.")
    branch: str | None = Field(description="The feature branch with the work, or null if no branch was made.")
    changed: list[str] = Field(description="Files or areas changed. Empty if nothing changed.")
    tests: str = Field(description='Tests run and their result, or "not run".')
    blockers: list[str] = Field(description="Anything that stopped or needs a decision. Empty if none.")
    next_step: str = Field(description="The next step you recommend.")


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project: str
    instruction: str
    permission_mode: PermissionMode
    state: JobState = "running"
    started_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    # The session the job resumed, then the session the team ran in.
    session_id: str | None = None
    report: Report | None = None
    tokens_used: int | None = None
    token_cap: int
    over_token_cap: bool = False
    error: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStore:
    def __init__(self, directory: Path = DEFAULT_JOBS_DIR) -> None:
        self.directory = directory
        # Makes "is this project busy?" and "start a job" one step within this server.
        self._start_lock = threading.Lock()

    def _path(self, job_id: str) -> Path:
        if not re.match(JOB_ID_PATTERN, job_id):
            raise JobError(f"no job with ID {job_id!r}")
        return self.directory / f"{job_id}.json"

    def save(self, job: Job) -> None:
        job.updated_at = utc_now()
        write_atomic(self._path(job.id), job.model_dump_json(indent=2) + "\n")

    def get(self, job_id: str) -> Job:
        """Read a job, marking it lost if the server running it has stopped."""
        path = self._path(job_id)
        if not path.exists():
            raise JobError(f"no job with ID {job_id!r}")
        job = Job.model_validate_json(path.read_text(encoding="utf-8"))
        if job.state == "running" and utc_now() - job.updated_at > STALE_AFTER:
            job.state = "lost"
            job.finished_at = utc_now()
            job.error = LOST_MESSAGE
            self.save(job)
        return job

    def running(self, project: str) -> Job | None:
        if not self.directory.exists():
            return None
        for path in sorted(self.directory.glob(f"{project}-*.json")):
            job = self.get(path.stem)
            if job.project == project and job.state == "running":
                return job
        return None

    def start(
        self,
        project: str,
        instruction: str,
        permission_mode: PermissionMode,
        token_cap: int,
        session_id: str | None,
    ) -> Job:
        """Create a running job. A project runs one job at a time, because two
        runs resuming the same session would fork its history."""
        with self._start_lock:
            busy = self.running(project)
            if busy:
                raise JobError(f"{project} is already running job {busy.id}; wait for it with get_report")
            now = utc_now()
            job = Job(
                id=f"{project}-{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}",
                project=project,
                instruction=instruction,
                permission_mode=permission_mode,
                started_at=now,
                updated_at=now,
                session_id=session_id,
                token_cap=token_cap,
            )
            self.save(job)
            return job
