#!/usr/bin/env python3
"""
PostToolUse hook (matcher: *). Extends this repo's existing audit_log.py
pattern: appends one line per tool call to tickets/<id>/audit.log, with the
current ticket ID and phase (read from state.json) included, so a session
that gets interrupted still leaves a durable trace independent of the
transcript UI. Pure observability — never denies anything.

CLI:
  python3 ticket_audit.py [workflow_root]
  (reads a PostToolUse JSON event on stdin)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guard_ticket_commit import find_active_ticket  # noqa: E402
from state_io import read_state  # noqa: E402


def _resolve_workflow_root(argv):
    if len(argv) > 1:
        return Path(argv[1])
    return Path(__file__).resolve().parents[2]


def format_log_line(event, ticket_id, phase):
    session_id = event.get("session_id", "unknown-session")
    tool_name = event.get("tool_name", "unknown-tool")
    tool_input = event.get("tool_input") or {}
    command = tool_input.get("command", "")
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    return (
        f"{datetime.now(timezone.utc).isoformat()} "
        f"ticket={ticket_id or 'none'} phase={phase or 'none'} "
        f"session={session_id} tool={tool_name} command={command!r}\n"
    )


def main(argv):
    workflow_root = _resolve_workflow_root(argv)
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    try:
        ticket_id = find_active_ticket(workflow_root)
        phase = None
        if ticket_id:
            state = read_state(workflow_root / "tickets" / ticket_id / "state.json")
            if state:
                phase = state.get("phase")

        if ticket_id:
            log_path = workflow_root / "tickets" / ticket_id / "audit.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(format_log_line(event, ticket_id, phase))
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
