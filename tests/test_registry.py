from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from fleet.registry import (
    REPO_ROOT,
    Budget,
    Project,
    Registry,
    RegistryError,
    load_registry,
    save_registry,
)


def make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True)
    return repo


def make_project(path: Path, **overrides) -> Project:
    fields = {
        "path": path,
        "remote": "https://github.com/esscott1/example.git",
        "goal": "Example",
        "budget": Budget(max_turns=40, max_tokens_per_job=1_000_000),
    }
    fields.update(overrides)
    return Project(**fields)


def test_example_registry_is_valid():
    registry = load_registry(REPO_ROOT / "projects.example.yaml")
    project = registry.get("montecarlo")
    assert project.permission_mode == "acceptEdits"
    assert project.status == "active"


def test_missing_file_is_empty_registry(tmp_path):
    assert load_registry(tmp_path / "projects.yaml").projects == {}


def test_defaults(tmp_path):
    project = Project(path=make_repo(tmp_path), remote="r", goal="g")
    assert project.permission_mode == "plan"
    assert project.status == "active"
    # 100K token cap, report-only; no turn limit unless set.
    assert project.budget == Budget(max_tokens_per_job=100_000, max_turns=None)


def test_bypass_permissions_rejected(tmp_path):
    with pytest.raises(ValidationError, match="bypassPermissions is never allowed"):
        make_project(make_repo(tmp_path), permission_mode="bypassPermissions")


@pytest.mark.parametrize("mode", ["auto", "dontAsk", "manual", "default"])
def test_other_permission_modes_rejected(tmp_path, mode):
    with pytest.raises(ValidationError):
        make_project(make_repo(tmp_path), permission_mode=mode)


def test_relative_path_rejected():
    with pytest.raises(ValidationError, match="path must be absolute"):
        make_project(Path("relative/repo"))


def test_bad_status_rejected(tmp_path):
    with pytest.raises(ValidationError):
        make_project(make_repo(tmp_path), status="archived")


@pytest.mark.parametrize("field", ["max_turns", "max_tokens_per_job"])
def test_budget_must_be_positive(field):
    values = {"max_turns": 40, "max_tokens_per_job": 1_000_000, field: 0}
    with pytest.raises(ValidationError):
        Budget(**values)


def test_runtime_fields_rejected(tmp_path):
    # session_id and last_seen_commit live in sessions.json, not the registry.
    with pytest.raises(ValidationError):
        make_project(make_repo(tmp_path), session_id="abc")


def test_add_requires_git_repo(tmp_path):
    registry = Registry()
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    with pytest.raises(RegistryError, match="not a git repo"):
        registry.add("plain", make_project(not_a_repo))


def test_add_rejects_duplicate(tmp_path):
    registry = Registry()
    registry.add("example", make_project(make_repo(tmp_path)))
    with pytest.raises(RegistryError, match="already registered"):
        registry.add("example", make_project(make_repo(tmp_path, "other")))


def test_add_rejects_bad_name(tmp_path):
    with pytest.raises(ValidationError, match="lowercase"):
        Registry().add("MonteCarlo", make_project(make_repo(tmp_path)))


def test_set_status_and_remove(tmp_path):
    registry = Registry()
    registry.add("example", make_project(make_repo(tmp_path)))
    registry.set_status("example", "paused")
    assert registry.get("example").status == "paused"
    registry.remove("example")
    with pytest.raises(RegistryError, match="no project named"):
        registry.get("example")


def test_save_and_reload_round_trip(tmp_path):
    registry = Registry()
    registry.add("example", make_project(make_repo(tmp_path), permission_mode="acceptEdits"))
    target = tmp_path / "projects.yaml"
    save_registry(registry, target)

    assert load_registry(target) == registry
    assert list(yaml.safe_load(target.read_text(encoding="utf-8"))["projects"]) == ["example"]
    assert [p.name for p in tmp_path.iterdir() if p.suffix == ".tmp"] == []
