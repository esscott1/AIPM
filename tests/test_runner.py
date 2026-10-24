import json

from fleet import runner


def test_team_env_drops_api_key_vars(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "x")
    monkeypatch.setenv("ANTHROPIC_MODEL", "keep")
    env = runner.team_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert env["ANTHROPIC_MODEL"] == "keep"


def test_report_read_from_result_text_when_no_structured_output():
    report = {"summary": "s", "branch": "feat/x", "changed": ["a.py"], "tests": "ok",
              "blockers": [], "next_step": "n"}
    stdout = json.dumps({"subtype": "success", "is_error": False, "session_id": "s1",
                         "result": json.dumps(report), "usage": {"output_tokens": 7}})
    outcome = runner.parse_output(0, stdout, "")
    assert outcome.error is None
    assert outcome.report.branch == "feat/x"
    assert outcome.tokens_used == 7


def test_result_without_report_fails():
    stdout = json.dumps({"subtype": "success", "is_error": False, "session_id": "s1", "result": "All done!"})
    outcome = runner.parse_output(0, stdout, "")
    assert outcome.session_id == "s1"
    assert "without a structured report" in outcome.error


def test_max_turns_error_reported():
    stdout = json.dumps({"subtype": "error_max_turns", "is_error": False, "session_id": "s1"})
    assert runner.parse_output(0, stdout, "").error.startswith("error_max_turns")


def test_non_json_output_uses_stderr():
    outcome = runner.parse_output(1, "", "first line\nError: something broke\n")
    assert outcome.error == "claude exited 1 without a JSON result: Error: something broke"
    assert outcome.session_id is None
