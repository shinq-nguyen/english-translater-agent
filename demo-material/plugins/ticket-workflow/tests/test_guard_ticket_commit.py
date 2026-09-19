import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from guard_ticket_commit import _extract_command, evaluate, find_active_ticket  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "guard_ticket_commit.py"


def test_no_active_ticket_always_allows():
    assert evaluate('git commit -m "bad message"', active_ticket=None) is None


def test_active_ticket_non_git_command_allows():
    assert evaluate("mvn test", active_ticket="PROJ-1") is None


def test_active_ticket_correct_message_allows():
    assert evaluate('git commit -m "[PROJ-1][dev-be] add endpoint"', active_ticket="PROJ-1") is None


def test_active_ticket_wrong_ticket_id_denies():
    result = evaluate('git commit -m "[OTHER-999][dev-be] x"', active_ticket="PROJ-1")
    assert result is not None
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_active_ticket_bad_phase_tag_denies():
    result = evaluate('git commit -m "[PROJ-1][anything] x"', active_ticket="PROJ-1")
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_active_ticket_no_brackets_denies():
    result = evaluate('git commit -m "just a message"', active_ticket="PROJ-1")
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_all_four_phase_tags_allowed():
    for tag in ("dev-be", "dev-ui", "fix-be", "fix-ui"):
        assert evaluate(f'git commit -m "[PROJ-1][{tag}] x"', active_ticket="PROJ-1") is None


def test_compound_command_with_echo_first_is_not_caught_documented_limit():
    # Documented scope limit (spec: guard_ticket_commit.py section): the
    # hook inspects tool_input.command as a single string and only treats
    # it as a commit if the FIRST token is `git`. A chained command whose
    # first token isn't `git` is intentionally out of scope.
    cmd = 'echo hi && git commit -m "bad message"'
    assert evaluate(cmd, active_ticket="PROJ-1") is None


def test_git_status_is_not_treated_as_commit():
    assert evaluate("git status", active_ticket="PROJ-1") is None


def test_extract_command_from_dict():
    assert _extract_command({"command": "git status"}) == "git status"


def test_extract_command_from_list():
    assert _extract_command(["git", "status"]) == "git status"


def test_extract_command_from_string():
    assert _extract_command("git status") == "git status"


def test_extract_command_from_none_or_other():
    assert _extract_command(None) == ""
    assert _extract_command(42) == "42"


def test_find_active_ticket_reads_pointer_file(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "tickets_active").write_text("PROJ-7\n", encoding="utf-8")
    assert find_active_ticket(tmp_path) == "PROJ-7"


def test_find_active_ticket_missing_returns_none(tmp_path):
    assert find_active_ticket(tmp_path) is None


def test_cli_denies_via_stdin(tmp_path, monkeypatch):
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "tickets_active").write_text("PROJ-1", encoding="utf-8")
    event = {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"bad\""}}
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(out.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_cli_allows_prints_nothing(tmp_path):
    event = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == ""
    assert out.returncode == 0


def test_cli_tool_input_as_list_exits_zero_and_prints_nothing(tmp_path):
    # Regression: tool_input isn't guaranteed to be {"command": "..."} —
    # some tool calls pass it as a raw argv list instead. Before
    # _extract_command(), `(event.get("tool_input") or {}).get("command")`
    # crashed with AttributeError ('list' object has no attribute 'get'),
    # exit code 1 — exactly the failure this test guards against.
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "tickets_active").write_text("PROJ-1", encoding="utf-8")
    event = {"tool_name": "Bash", "tool_input": ["bash", "-c", "git commit -m bad"]}
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stderr


def test_cli_non_dict_json_stdin_exits_zero_and_prints_nothing(tmp_path):
    # Non-dict but still valid JSON (a scalar or list) must be treated like
    # the existing JSONDecodeError case: exit 0, no output, no traceback.
    for payload in ('"not an object"', "[1, 2, 3]"):
        out = subprocess.run(
            [sys.executable, str(SCRIPT), str(tmp_path)],
            input=payload,
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == ""
