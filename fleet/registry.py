"""The project registry, `projects.yaml`.

The registry lists the repos AIPM manages and how to run each team. Fleet
tools write it (adopt, create, pause, resume, retire); it stays out of git
because it holds machine-local paths. `projects.example.yaml` documents the
format.

Per-run state (session ID, last seen commit) lives in `fleet/sessions.json`,
not here, so each field has one home.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = REPO_ROOT / "projects.yaml"

# Teams start in plan or acceptEdits mode. bypassPermissions is never allowed.
PermissionMode = Literal["plan", "acceptEdits"]
Status = Literal["active", "paused"]

PROJECT_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*$"


class RegistryError(Exception):
    """A registry operation that cannot be done, such as adding a duplicate."""


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_turns: PositiveInt
    max_tokens_per_job: PositiveInt


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path
    remote: str
    goal: str
    model: str = "sonnet"
    permission_mode: PermissionMode = "plan"
    budget: Budget
    status: Status = "active"

    @field_validator("path")
    @classmethod
    def _path_is_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError(f"path must be absolute, got {value}")
        return value

    @field_validator("permission_mode", mode="before")
    @classmethod
    def _no_bypass(cls, value: object) -> object:
        if value == "bypassPermissions":
            raise ValueError("bypassPermissions is never allowed for a project team")
        return value


class Registry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: dict[str, Project] = Field(default_factory=dict)

    @field_validator("projects")
    @classmethod
    def _names_are_slugs(cls, value: dict[str, Project]) -> dict[str, Project]:
        for name in value:
            if not re.match(PROJECT_NAME_PATTERN, name):
                raise ValueError(
                    f"project name {name!r} must be lowercase letters, digits and hyphens"
                )
        return value

    def get(self, name: str) -> Project:
        try:
            return self.projects[name]
        except KeyError:
            raise RegistryError(f"no project named {name!r}") from None

    def add(self, name: str, project: Project) -> None:
        """Register a project. Its path must be an existing git repo."""
        if name in self.projects:
            raise RegistryError(f"project {name!r} is already registered")
        if not (project.path / ".git").exists():
            raise RegistryError(f"{project.path} is not a git repo")
        updated = dict(self.projects)
        updated[name] = project
        # Re-validate so the name check runs.
        self.projects = Registry(projects=updated).projects

    def remove(self, name: str) -> Project:
        project = self.get(name)
        del self.projects[name]
        return project

    def set_status(self, name: str, status: Status) -> None:
        project = self.get(name)
        self.projects[name] = project.model_copy(update={"status": status})


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> Registry:
    """Read the registry. A missing file is an empty registry."""
    if not path.exists():
        return Registry()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Registry.model_validate(data)


def save_registry(registry: Registry, path: Path = DEFAULT_REGISTRY_PATH) -> None:
    """Write the registry atomically, so a crash never leaves a half-written file."""
    data = registry.model_dump(mode="json")
    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
