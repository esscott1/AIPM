import json
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from mcp.client import Client

from fleet.jobs import Job, JobStore, utc_now
from fleet.registry import Budget, Project, Registry, save_registry
from fleet.server import create_server

pytestmark = pytest.mark.anyio

FAKE_CLAUDE = [sys.executable, str(Path(__file__).with_name("fake_claude.py"))]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "example"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    return repo


class Fleet:
    """A registry with one project, a sessions file, a jobs folder and a fake claude."""

    def __init__(self, tmp_path: Path, monkeypatch, **project_fields):
        self.repo = make_git_repo(tmp_path)
        self.registry_path = tmp_path / "projects.yaml"
        self.sessions_path = tmp_path / "sessions.json"
        self.jobs_dir = tmp_path / "jobs"
        self.log = tmp_path / "claude-calls.jsonl"
        self.log.touch()
        monkeypatch.setenv("FAKE_CLAUDE_LOG", str(self.log))
        self.set_project(**project_fields)

    def set_project(self, **fields):
        registry = Registry()
        registry.add("example", Project(
            path=self.repo,
            remote="https://github.com/esscott1/example.git",
            goal="Example project",
            **fields,
        ))
        save_registry(registry, self.registry_path)

    def client(self) -> Client:
        return Client(create_server(self.registry_path, self.sessions_path, self.jobs_dir, claude=FAKE_CLAUDE))

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def sessions(self) -> dict:
        return json.loads(self.sessions_path.read_text(encoding="utf-8"))


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    return Fleet(tmp_path, monkeypatch)


async def dispatch(client: Client, **args) -> dict:
    result = await client.call_tool("dispatch", {"project": "example", "instruction": "Report your current state.", **args})
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def wait_for(client: Client, job_id: str, timeout: float = 20) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        result = await client.call_tool("get_report", {"job": job_id})
        assert not result.is_error, result.content[0].text
        job = result.structured_content
        if job["state"] != "running":
            return job
        assert time.monotonic() < deadline, "job still running"
        await anyio.sleep(0.1)


def arg(call: dict, flag: str) -> str | None:
    args = call["args"]
    return args[args.index(flag) + 1] if flag in args else None


async def test_dispatch_returns_running_job_then_report(fleet, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    async with fleet.client() as client:
        job = await dispatch(client)
        assert job["state"] == "running"
        assert job["permission_mode"] == "plan"
        assert job["token_cap"] == 100_000
        done = await wait_for(client, job["id"])

    assert done["state"] == "succeeded", done["error"]
    assert done["report"]["summary"] == "Reported the current state."
    assert done["report"]["branch"] is None
    assert done["tokens_used"] == 51_510
    assert done["over_token_cap"] is False
    assert done["session_id"] == "session-1"
    assert (fleet.jobs_dir / f"{job['id']}.json").exists()


async def test_team_runs_headless_in_repo_with_clean_env(fleet, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "not-a-real-token")
    async with fleet.client() as client:
        await wait_for(client, (await dispatch(client))["id"])

    [call] = fleet.calls()
    assert Path(call["cwd"]).resolve() == fleet.repo.resolve()
    assert call["api_key_vars"] == []
    assert call["stdin_is_empty"] is True
    assert arg(call, "--output-format") == "json"
    assert arg(call, "--permission-mode") == "plan"
    assert arg(call, "--model") == "sonnet"
    assert json.loads(arg(call, "--json-schema"))["required"] == [
        "summary", "branch", "changed", "tests", "blockers", "next_step",
    ]
    assert "--max-turns" not in call["args"]
    assert "--resume" not in call["args"]
    prompt = arg(call, "-p")
    assert prompt.startswith("Report your current state.")
    assert "Don't open a pull request" in prompt


async def test_next_dispatch_resumes_saved_session(fleet):
    async with fleet.client() as client:
        await wait_for(client, (await dispatch(client))["id"])
        assert fleet.sessions()["example"]["session_id"] == "session-1"
        second = await dispatch(client)
        assert second["session_id"] == "session-1"
        await wait_for(client, second["id"])

    first_call, second_call = fleet.calls()
    assert "--resume" not in first_call["args"]
    assert arg(second_call, "--resume") == "session-1"


async def test_sessions_file_keeps_other_fields(fleet):
    fleet.sessions_path.write_text(json.dumps({
        "example": {"session_id": None, "last_seen_commit": "abc1234"},
        "other": {"session_id": "keep-me", "last_seen_commit": None},
    }))
    async with fleet.client() as client:
        await wait_for(client, (await dispatch(client))["id"])
    assert fleet.sessions() == {
        "example": {"session_id": "session-1", "last_seen_commit": "abc1234"},
        "other": {"session_id": "keep-me", "last_seen_commit": None},
    }


async def test_max_turns_passed_only_when_set(tmp_path, monkeypatch):
    fleet = Fleet(tmp_path, monkeypatch, budget=Budget(max_turns=25))
    async with fleet.client() as client:
        await wait_for(client, (await dispatch(client))["id"])
    assert arg(fleet.calls()[0], "--max-turns") == "25"


async def test_over_token_cap_is_flagged_not_stopped(tmp_path, monkeypatch):
    fleet = Fleet(tmp_path, monkeypatch, budget=Budget(max_tokens_per_job=1_000))
    async with fleet.client() as client:
        done = await wait_for(client, (await dispatch(client))["id"])
    assert done["state"] == "succeeded"
    assert done["over_token_cap"] is True


async def test_usage_limit_fails_with_reason_and_keeps_session(fleet, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "limit")
    async with fleet.client() as client:
        done = await wait_for(client, (await dispatch(client))["id"])
    assert done["state"] == "failed"
    assert "usage limit reached" in done["error"]
    assert "reset at 5pm" in done["error"]
    assert done["report"] is None
    assert fleet.sessions()["example"]["session_id"] == "session-1"


async def test_failed_resume_never_starts_fresh_session(fleet, monkeypatch):
    fleet.sessions_path.write_text(json.dumps({"example": {"session_id": "gone", "last_seen_commit": None}}))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "garbage")
    async with fleet.client() as client:
        done = await wait_for(client, (await dispatch(client))["id"])
    assert done["state"] == "failed"
    assert "No conversation found with session ID: gone" in done["error"]
    [call] = fleet.calls()
    assert arg(call, "--resume") == "gone"
    assert fleet.sessions()["example"]["session_id"] == "gone"


async def test_report_missing_fields_fails(fleet, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "bad_report")
    async with fleet.client() as client:
        done = await wait_for(client, (await dispatch(client))["id"])
    assert done["state"] == "failed"
    assert "didn't match the schema" in done["error"]


async def test_one_job_per_project(fleet, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    async with fleet.client() as client:
        first = await dispatch(client)
        second = await client.call_tool("dispatch", {"project": "example", "instruction": "Another task."})
        assert second.is_error
        assert f"already running job {first['id']}" in second.content[0].text
        await wait_for(client, first["id"])
        third = await dispatch(client)
        await wait_for(client, third["id"])


async def test_paused_project_refused(tmp_path, monkeypatch):
    fleet = Fleet(tmp_path, monkeypatch, status="paused")
    async with fleet.client() as client:
        result = await client.call_tool("dispatch", {"project": "example", "instruction": "Go."})
    assert result.is_error
    assert "paused" in result.content[0].text
    assert fleet.calls() == []


async def test_mode_cannot_exceed_registry(fleet):
    async with fleet.client() as client:
        result = await client.call_tool(
            "dispatch", {"project": "example", "instruction": "Go.", "mode": "acceptEdits"},
        )
    assert result.is_error
    assert "limited to plan mode" in result.content[0].text


async def test_mode_can_tighten_registry(tmp_path, monkeypatch):
    fleet = Fleet(tmp_path, monkeypatch, permission_mode="acceptEdits")
    async with fleet.client() as client:
        await wait_for(client, (await dispatch(client, mode="plan"))["id"])
        await wait_for(client, (await dispatch(client))["id"])
    assert [arg(c, "--permission-mode") for c in fleet.calls()] == ["plan", "acceptEdits"]


async def test_bypass_mode_rejected(fleet):
    async with fleet.client() as client:
        result = await client.call_tool(
            "dispatch", {"project": "example", "instruction": "Go.", "mode": "bypassPermissions"},
        )
    assert result.is_error
    assert fleet.calls() == []


async def test_empty_instruction_rejected(fleet):
    async with fleet.client() as client:
        result = await client.call_tool("dispatch", {"project": "example", "instruction": "  "})
    assert result.is_error
    assert "instruction is empty" in result.content[0].text


async def test_missing_repo_rejected(fleet):
    fleet.repo.rename(fleet.repo.with_name("moved"))
    async with fleet.client() as client:
        result = await client.call_tool("dispatch", {"project": "example", "instruction": "Go."})
    assert result.is_error
    assert "may have moved" in result.content[0].text


async def test_unknown_job(fleet):
    async with fleet.client() as client:
        for job_id in ("example-20260101-000000-abcd", "../projects"):
            result = await client.call_tool("get_report", {"job": job_id})
            assert result.is_error
            assert "no job with ID" in result.content[0].text


async def test_job_from_stopped_server_is_lost(fleet):
    store = JobStore(fleet.jobs_dir)
    job = store.start("example", "Go.", "plan", 100_000, None)
    stale = job.model_copy(update={"updated_at": utc_now() - timedelta(minutes=10)})
    path = fleet.jobs_dir / f"{job.id}.json"
    path.write_text(stale.model_dump_json(), encoding="utf-8")

    async with fleet.client() as client:
        done = await wait_for(client, job.id)
        assert done["state"] == "lost"
        assert "check project_status" in done["error"]
        # A lost job no longer blocks the project.
        await wait_for(client, (await dispatch(client))["id"])
    assert Job.model_validate_json(path.read_text(encoding="utf-8")).state == "lost"
