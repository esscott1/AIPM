import json
import subprocess
from pathlib import Path

from fleet import doctor


def test_python_check_passes_on_supported_version():
    assert doctor.check_python().status == "PASS"


def test_find_git_bash_beside_git(tmp_path, monkeypatch):
    git = tmp_path / "Git" / "cmd" / "git.exe"
    bash = tmp_path / "Git" / "bin" / "bash.exe"
    for f in (git, bash):
        f.parent.mkdir(parents=True)
        f.touch()
    monkeypatch.setattr(doctor.shutil, "which", lambda name: str(git) if name == "git" else None)
    assert doctor.find_git_bash() == bash.resolve()


def test_wsl_bash_on_path_warns(tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_GIT_BASH_PATH", raising=False)
    wsl = r"C:\WINDOWS\system32\bash.exe"
    monkeypatch.setattr(doctor.shutil, "which", lambda name: wsl if name == "bash" else None)
    checks = doctor.check_git_bash()
    assert [c.status for c in checks] == ["FAIL", "WARN"]
    assert "WSL" in checks[1].detail


def test_configured_git_bash_path_missing_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", str(tmp_path / "nope.exe"))
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    assert doctor.check_git_bash()[0].status == "FAIL"


def fake_auth_status(monkeypatch, status: dict | str):
    stdout = status if isinstance(status, str) else json.dumps(status)
    monkeypatch.setattr(doctor.shutil, "which", lambda name: "claude.exe" if name == "claude" else None)
    monkeypatch.setattr(doctor, "run", lambda args, **kw: subprocess.CompletedProcess(args, 0, stdout, ""))
    for name in doctor.API_KEY_VARS:
        monkeypatch.delenv(name, raising=False)


def test_claude_ai_sign_in_passes(monkeypatch):
    fake_auth_status(monkeypatch, {"loggedIn": True, "authMethod": "claude.ai", "email": "someone@example.com"})
    [check] = doctor.check_claude_sign_in()
    assert check.status == "PASS"
    assert "@" not in check.detail


def test_other_sign_in_method_warns(monkeypatch):
    fake_auth_status(monkeypatch, {"loggedIn": True, "authMethod": "api_key"})
    [check] = doctor.check_claude_sign_in()
    assert check.status == "WARN"
    assert "not claude.ai" in check.detail


def test_signed_out_fails(monkeypatch):
    fake_auth_status(monkeypatch, {"loggedIn": False})
    assert doctor.check_claude_sign_in()[0].status == "FAIL"


def test_unreadable_auth_status_warns(monkeypatch):
    fake_auth_status(monkeypatch, "not json")
    assert doctor.check_claude_sign_in()[0].status == "WARN"


def test_api_key_variable_warns_without_showing_value(monkeypatch):
    fake_auth_status(monkeypatch, {"loggedIn": True, "authMethod": "claude.ai"})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-value")
    checks = doctor.check_claude_sign_in()
    assert [c.status for c in checks] == ["PASS", "WARN"]
    assert "ANTHROPIC_API_KEY" in checks[1].detail
    assert "secret-value" not in checks[1].detail


def test_main_exit_code_reflects_failures(monkeypatch, capsys):
    monkeypatch.setattr(doctor, "run_checks", lambda live: [doctor.Check("PASS", "a", ""), doctor.Check("FAIL", "b", "x")])
    assert doctor.main([]) == 1
    monkeypatch.setattr(doctor, "run_checks", lambda live: [doctor.Check("WARN", "a", "")])
    assert doctor.main([]) == 0
    assert "WARN" in capsys.readouterr().out
