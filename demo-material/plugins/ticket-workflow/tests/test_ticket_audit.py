import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from ticket_audit import format_log_line  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "ticket_audit.py"


def test_format_log_line_includes_ticket_and_phase():
    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "mvn test"}}
    line = format_log_line(event, ticket_id="PROJ-1", phase="testing")
    assert "PROJ-1" in line
    assert "testing" in line
    assert "mvn test" in line
    assert "s1" in line


def test_format_log_line_without_active_ticket():
    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    line = format_log_line(event, ticket_id=None, phase=None)
    assert "ticket=none" in line


def test_cli_appends_line_and_creates_dirs(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "tickets_active").write_text("PROJ-1", encoding="utf-8")
    ticket_dir = tmp_path / "tickets" / "PROJ-1"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "state.json").write_text(
        json.dumps({"phase": "dev_in_progress"}), encoding="utf-8"
    )

    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "mvn test"}}
    subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        input=json.dumps(event),
        text=True,
        check=True,
    )

    log_path = ticket_dir / "audit.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "dev_in_progress" in content
    assert "mvn test" in content


def test_cli_two_calls_append_two_lines(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "tickets_active").write_text("PROJ-1", encoding="utf-8")
    (tmp_path / "tickets" / "PROJ-1").mkdir(parents=True)

    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(SCRIPT), str(tmp_path)],
            input=json.dumps(event),
            text=True,
            check=True,
        )

    log_path = tmp_path / "tickets" / "PROJ-1" / "audit.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_cli_no_active_ticket_does_not_crash(tmp_path):
    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0


def test_cli_corrupt_state_json_does_not_crash(tmp_path):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "tickets_active").write_text("PROJ-1", encoding="utf-8")
    ticket_dir = tmp_path / "tickets" / "PROJ-1"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "state.json").write_text("{invalid json", encoding="utf-8")

    event = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
