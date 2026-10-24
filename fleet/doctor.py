"""Check that this machine can run the fleet server and its project teams.

    uv run python -m fleet.doctor          # local checks, no tokens used
    uv run python -m fleet.doctor --live   # also one tiny headless `claude -p` call

Only runs commands and reads their exit codes and version output. It never
reads credential files or prints auth output.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MIN_PYTHON = (3, 12)

Status = Literal["PASS", "WARN", "FAIL"]


@dataclass
class Check:
    status: Status
    name: str
    detail: str


def run(args: list[str], timeout: int = 30, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, cwd=cwd,
    )


def check_python() -> Check:
    version = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info[:2] >= MIN_PYTHON:
        return Check("PASS", "Python", version)
    return Check("FAIL", "Python", f"{version}; need {'.'.join(map(str, MIN_PYTHON))} or newer")


def check_git() -> Check:
    git = shutil.which("git")
    if not git:
        return Check("FAIL", "git", "not on PATH; install Git for Windows")
    out = run([git, "--version"]).stdout.strip()
    return Check("PASS", "git", f"{out} ({git})")


def find_git_bash() -> Path | None:
    """Git Bash ships beside git.exe: <root>\\cmd\\git.exe -> <root>\\bin\\bash.exe."""
    git = shutil.which("git")
    if not git:
        return None
    root = Path(git).resolve().parent.parent
    for candidate in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
        if candidate.exists():
            return candidate
    return None


def check_git_bash() -> list[Check]:
    checks: list[Check] = []
    configured = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured:
        if Path(configured).exists():
            checks.append(Check("PASS", "Git Bash", f"CLAUDE_CODE_GIT_BASH_PATH={configured}"))
        else:
            checks.append(Check("FAIL", "Git Bash", f"CLAUDE_CODE_GIT_BASH_PATH points to a missing file: {configured}"))
    else:
        found = find_git_bash()
        if found:
            checks.append(Check("PASS", "Git Bash", f"{found}; if claude can't find it, set CLAUDE_CODE_GIT_BASH_PATH to this path"))
        else:
            checks.append(Check("FAIL", "Git Bash", "bash.exe not found beside git.exe; install Git for Windows or set CLAUDE_CODE_GIT_BASH_PATH"))

    bash_on_path = shutil.which("bash")
    if bash_on_path and "system32" in bash_on_path.lower():
        checks.append(Check(
            "WARN", "bash on PATH",
            f"{bash_on_path} is WSL; anything that runs plain `bash` gets WSL, not Git Bash",
        ))
    return checks


def check_gh() -> Check:
    gh = shutil.which("gh")
    if not gh:
        return Check("FAIL", "gh", "not on PATH; install the GitHub CLI")
    # Exit code only: auth output is never printed.
    if run([gh, "auth", "status"]).returncode != 0:
        return Check("FAIL", "gh", "not signed in; run `gh auth login`")
    version = run([gh, "--version"]).stdout.splitlines()[0]
    return Check("PASS", "gh", f"{version}, signed in")


def check_claude() -> Check:
    claude = shutil.which("claude")
    if not claude:
        return Check("FAIL", "claude", "not on PATH; install Claude Code")
    out = run([claude, "--version"]).stdout.strip()
    return Check("PASS", "claude", f"{out} ({claude})")


def check_claude_live() -> Check:
    """One headless call, the way the fleet server will run teams, minus --resume."""
    claude = shutil.which("claude")
    if not claude:
        return Check("FAIL", "claude -p", "claude not on PATH")
    with tempfile.TemporaryDirectory(prefix="aipm-doctor-") as cwd:
        try:
            proc = run(
                [claude, "-p", "Reply with the single word: ok",
                 "--output-format", "json", "--permission-mode", "plan",
                 "--no-session-persistence"],
                timeout=180, cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            return Check("FAIL", "claude -p", "timed out after 180s")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        return Check("FAIL", "claude -p", f"exit {proc.returncode}, not JSON: {tail[0]}")
    if result.get("is_error"):
        return Check("FAIL", "claude -p", f"error result: {result.get('subtype')}: {result.get('result')}")
    usage = result.get("usage") or {}
    tokens = sum(usage.get(k) or 0 for k in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
    ))
    return Check("PASS", "claude -p", f"replied {result.get('result')!r}; {tokens} tokens")


def run_checks(live: bool) -> list[Check]:
    checks = [check_python(), check_git()]
    if sys.platform == "win32":
        checks.extend(check_git_bash())
    checks.extend([check_gh(), check_claude()])
    if live:
        checks.append(check_claude_live())
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="also make one headless claude -p call (uses a few tokens)")
    args = parser.parse_args(argv)

    checks = run_checks(args.live)
    width = max(len(c.name) for c in checks)
    for c in checks:
        print(f"{c.status}  {c.name:<{width}}  {c.detail}")
    return 1 if any(c.status == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main())
