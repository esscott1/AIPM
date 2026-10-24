"""Runs one team task through the unmodified `claude` CLI, headless.

    claude -p <instruction + AIPM brief> --output-format json
           --permission-mode <mode> --model <model> --json-schema <report schema>
           [--max-turns <n>] [--resume <session_id>]

The command runs in the project's registered folder, because Claude Code stores
sessions per folder. A failed resume fails the job; it never falls back to a
fresh session, which would silently drop the team's context.
"""

from __future__ import annotations

import json
import os
import subprocess
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from fleet.jobs import HEARTBEAT_SECONDS, Job, JobStore, Report, utc_now
from fleet.registry import PermissionMode, Project
from fleet.sessions import record_session_id

# If either is set, claude bills that API account instead of the claude.ai
# sign-in. Teams always run on the sign-in, so these names are dropped from the
# team's environment. Their values are never read.
API_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")

# Sent with every task rather than through --append-system-prompt, which is
# recorded once per session and would never reach existing teams if it changed.
TEAM_BRIEF = """

---
From AIPM, the program manager that sent this task:
- Follow this repo's CLAUDE.md and memory.md.
- Make changes on a feature branch, never on main, and commit them there.
- Don't open a pull request. Name your branch in the report; AIPM handles PR approval.
- Finish with the structured report: summary, branch (null if you made none), changed, tests, blockers (empty if none) and next_step.
"""

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def count_tokens(usage: dict | None) -> int:
    return sum((usage or {}).get(k) or 0 for k in USAGE_KEYS)


def build_prompt(instruction: str) -> str:
    return instruction.strip() + TEAM_BRIEF


def build_command(
    claude: Sequence[str],
    project: Project,
    prompt: str,
    mode: PermissionMode,
    session_id: str | None,
) -> list[str]:
    command = [
        *claude, "-p", prompt,
        "--output-format", "json",
        "--permission-mode", mode,
        "--model", project.model,
        "--json-schema", json.dumps(Report.model_json_schema()),
    ]
    if project.budget.max_turns is not None:
        command += ["--max-turns", str(project.budget.max_turns)]
    if session_id:
        command += ["--resume", session_id]
    return command


def team_env() -> dict[str, str]:
    """This process's environment minus the API key variables."""
    return {k: v for k, v in os.environ.items() if k.upper() not in API_KEY_VARS}


@dataclass
class Outcome:
    session_id: str | None = None
    report: Report | None = None
    tokens_used: int | None = None
    error: str | None = None


def _last_line(*texts: str) -> str:
    for text in texts:
        lines = (text or "").strip().splitlines()
        if lines:
            return lines[-1]
    return "no output"


def parse_output(returncode: int, stdout: str, stderr: str) -> Outcome:
    """Turn claude's JSON result into a report, or say why there is none."""
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return Outcome(error=f"claude exited {returncode} without a JSON result: {_last_line(stderr, stdout)}")
    if not isinstance(result, dict):
        return Outcome(error=f"claude exited {returncode} with unexpected output: {_last_line(stdout)}")

    outcome = Outcome(session_id=result.get("session_id"), tokens_used=count_tokens(result.get("usage")))
    if result.get("is_error") or result.get("subtype") != "success":
        # Includes hitting the plan's usage limit; claude's message says when it resets.
        outcome.error = f"{result.get('subtype')}: {result.get('result')}"
        return outcome
    if returncode != 0:
        outcome.error = f"claude exited {returncode}: {_last_line(stderr)}"
        return outcome

    raw = result.get("structured_output")
    if raw is None:
        try:
            raw = json.loads(result.get("result") or "")
        except json.JSONDecodeError:
            outcome.error = f"the team finished without a structured report: {_last_line(result.get('result') or '')}"
            return outcome
    try:
        outcome.report = Report.model_validate(raw)
    except ValidationError as e:
        outcome.error = f"the team's report didn't match the schema: {e}"
    return outcome


def run_job(
    job: Job,
    project: Project,
    claude: Sequence[str],
    store: JobStore,
    sessions_path: Path,
) -> None:
    """Run the job to the end and save the result. Meant for a background thread."""
    try:
        outcome = _run(job, project, claude, store)
        if outcome.session_id:
            record_session_id(job.project, outcome.session_id, sessions_path)
            job.session_id = outcome.session_id
        job.report = outcome.report
        job.tokens_used = outcome.tokens_used
        job.over_token_cap = (outcome.tokens_used or 0) > job.token_cap
        job.error = outcome.error
        job.state = "failed" if outcome.error else "succeeded"
    except Exception:
        job.state = "failed"
        job.error = "fleet server error while running the job:\n" + traceback.format_exc(limit=5)
    job.finished_at = utc_now()
    store.save(job)


def _run(job: Job, project: Project, claude: Sequence[str], store: JobStore) -> Outcome:
    command = build_command(claude, project, build_prompt(job.instruction), job.permission_mode, job.session_id)
    try:
        proc = subprocess.Popen(
            command,
            cwd=project.path,
            env=team_env(),
            # The fleet server speaks MCP on its own stdin; the team must not read it.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as e:
        return Outcome(error=f"could not start claude: {e}")
    while True:
        try:
            stdout, stderr = proc.communicate(timeout=HEARTBEAT_SECONDS)
            break
        except subprocess.TimeoutExpired:
            store.save(job)  # heartbeat, so get_report can tell running from lost
    return parse_output(proc.returncode, stdout, stderr)
