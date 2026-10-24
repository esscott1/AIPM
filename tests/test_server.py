import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from fleet.registry import REPO_ROOT, Budget, Project, Registry, save_registry
from fleet.server import create_server

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "example"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("hello\n")
    git(repo, "add", "README.md")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "first commit")
    return repo


@pytest.fixture
def files(tmp_path):
    repo = make_git_repo(tmp_path)
    registry = Registry()
    registry.add("example", Project(
        path=repo,
        remote="https://github.com/esscott1/example.git",
        goal="Example project",
        budget=Budget(max_turns=40, max_tokens_per_job=1_000_000),
    ))
    registry_path = tmp_path / "projects.yaml"
    save_registry(registry, registry_path)
    sessions_path = tmp_path / "sessions.json"
    return repo, registry_path, sessions_path


async def test_tools_are_listed_and_annotated(tmp_path):
    async with Client(create_server(tmp_path / "none.yaml", tmp_path / "none.json", tmp_path / "jobs")) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"list_projects", "project_status", "dispatch", "get_report"}
    assert all(tools[name].annotations.read_only_hint for name in ("list_projects", "project_status", "get_report"))
    assert tools["dispatch"].annotations.read_only_hint is False
    assert tools["dispatch"].annotations.destructive_hint is False


async def test_list_projects_empty_registry(tmp_path):
    async with Client(create_server(tmp_path / "none.yaml", tmp_path / "none.json")) as client:
        result = await client.call_tool("list_projects", {})
    assert not result.is_error
    assert result.structured_content == {"result": []}


async def test_list_projects(files):
    repo, registry_path, sessions_path = files
    async with Client(create_server(registry_path, sessions_path)) as client:
        result = await client.call_tool("list_projects", {})
    assert result.structured_content == {"result": [
        {"name": "example", "path": str(repo), "status": "active", "goal": "Example project"},
    ]}


async def test_project_status_reads_git_and_session(files):
    repo, registry_path, sessions_path = files
    (repo / "notes.txt").write_text("uncommitted\n")
    sessions_path.write_text(json.dumps({"example": {"session_id": "abc", "last_seen_commit": "1234567"}}))

    async with Client(create_server(registry_path, sessions_path)) as client:
        result = await client.call_tool("project_status", {"project": "example"})

    assert not result.is_error
    status = result.structured_content
    assert status["permission_mode"] == "plan"
    assert status["budget"] == {"max_turns": 40, "max_tokens_per_job": 1_000_000}
    assert status["session"] == {"session_id": "abc", "last_seen_commit": "1234567"}
    assert status["git"]["path_exists"] is True
    assert status["git"]["branch"] == "main"
    assert "first commit" in status["git"]["last_commit"]
    assert status["git"]["uncommitted_changes"] == 1


async def test_project_status_without_session(files):
    _, registry_path, sessions_path = files
    async with Client(create_server(registry_path, sessions_path)) as client:
        result = await client.call_tool("project_status", {"project": "example"})
    assert result.structured_content["session"] == {"session_id": None, "last_seen_commit": None}


async def test_project_status_missing_repo(files):
    repo, registry_path, sessions_path = files
    repo.rename(repo.with_name("moved"))
    async with Client(create_server(registry_path, sessions_path)) as client:
        result = await client.call_tool("project_status", {"project": "example"})
    assert not result.is_error
    assert result.structured_content["git"]["path_exists"] is False


async def test_project_status_unknown_project(files):
    _, registry_path, sessions_path = files
    async with Client(create_server(registry_path, sessions_path)) as client:
        result = await client.call_tool("project_status", {"project": "nope"})
    assert result.is_error
    assert "no project named 'nope'" in result.content[0].text


async def test_invalid_registry_reports_why(tmp_path):
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text("projects:\n  example:\n    permission_mode: bypassPermissions\n")
    async with Client(create_server(registry_path, tmp_path / "none.json")) as client:
        result = await client.call_tool("list_projects", {})
    assert result.is_error
    assert "is invalid" in result.content[0].text


async def test_server_runs_over_stdio(files):
    repo, registry_path, sessions_path = files
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fleet.server"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "AIPM_REGISTRY": str(registry_path), "AIPM_SESSIONS": str(sessions_path)},
    )
    async with Client(params) as client:
        result = await client.call_tool("list_projects", {})
    assert result.structured_content["result"][0]["name"] == "example"


def test_mcp_json_registers_fleet_server():
    config = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    fleet = config["mcpServers"]["fleet"]
    assert fleet["command"] == "uv"
    assert fleet["args"][-3:] == ["python", "-m", "fleet.server"]
