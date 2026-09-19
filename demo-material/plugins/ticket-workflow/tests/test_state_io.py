import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from state_io import read_state, write_state  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "state_io.py"


def test_read_missing_returns_none(tmp_path):
    assert read_state(tmp_path / "state.json") is None


def test_write_then_read_roundtrip(tmp_path):
    path = tmp_path / "tickets" / "PROJ-1" / "state.json"
    write_state(path, {"ticket_id": "PROJ-1", "phase": "investigating"})
    assert read_state(path) == {"ticket_id": "PROJ-1", "phase": "investigating"}


def test_write_creates_parent_dirs(tmp_path):
    path = tmp_path / "a" / "b" / "c" / "state.json"
    write_state(path, {"x": 1})
    assert path.exists()


def test_write_does_not_leave_tmp_file(tmp_path):
    path = tmp_path / "state.json"
    write_state(path, {"x": 1})
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_write_overwrites_cleanly(tmp_path):
    path = tmp_path / "state.json"
    write_state(path, {"phase": "investigating"})
    write_state(path, {"phase": "testing"})
    assert read_state(path) == {"phase": "testing"}


def test_cli_write_then_read(tmp_path):
    path = tmp_path / "state.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "write", str(path)],
        input=json.dumps({"ticket_id": "PROJ-2"}),
        text=True,
        check=True,
    )
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "read", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(out.stdout) == {"ticket_id": "PROJ-2"}


def test_cli_read_missing_prints_null(tmp_path):
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "read", str(tmp_path / "nope.json")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "null"
