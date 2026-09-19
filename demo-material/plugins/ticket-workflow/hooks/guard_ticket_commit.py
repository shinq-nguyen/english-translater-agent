#!/usr/bin/env python3
"""
PreToolUse hook (matcher: Bash). While a ticket workflow is active
(.codex/tickets_active names one), denies any `git commit` whose message
doesn't match `[<ACTIVE-TICKET-ID>][dev-be|dev-ui|fix-be|fix-ui] ...`.

Scope limit, by design (see docs/specs/2026-09-13-ticket-workflow-plugin-design.md,
Hooks section): only the literal tool_input.command string is inspected, and
only when its first whitespace-separated token is `git` with `commit` among
the remaining args. A message via `-F <file>`, `--amend`, or a `git commit`
issued as a later command in a `&&`/`;` chain are not caught — the workflow
itself never issues those forms.

CLI:
  python3 guard_ticket_commit.py [workflow_root]
  (reads a PreToolUse JSON event on stdin; workflow_root defaults to this
  script's own repo root, resolved from its own file location)
"""
import json
import re
import sys
from pathlib import Path

PHASE_TAGS = ("dev-be", "dev-ui", "fix-be", "fix-ui")


def _resolve_workflow_root(argv):
    if len(argv) > 1:
        return Path(argv[1])
    # <root>/.codex/hooks/guard_ticket_commit.py -> parents[2] is <root>
    return Path(__file__).resolve().parents[2]


def find_active_ticket(workflow_root):
    pointer = Path(workflow_root) / ".codex" / "tickets_active"
    if not pointer.exists():
        return None
    value = pointer.read_text(encoding="utf-8").strip()
    return value or None


def _is_git_commit(command):
    tokens = command.strip().split()
    return bool(tokens) and tokens[0] == "git" and "commit" in tokens[1:]


def _extract_command(tool_input):
    """tool_input's shape isn't guaranteed to be {"command": "..."} — some
    tool calls pass it as a raw argv list or a bare string instead of a
    dict. Handle all three so a shape this hook doesn't expect fails open
    (empty command, never treated as a commit) instead of crashing with an
    AttributeError on ``.get()``."""
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")
    else:
        command = tool_input
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    if not isinstance(command, str):
        command = "" if command is None else str(command)
    return command


def evaluate(command, active_ticket):
    if not active_ticket:
        return None
    if not _is_git_commit(command):
        return None

    escaped_ticket = re.escape(active_ticket)
    phase_group = "|".join(PHASE_TAGS)
    pattern = rf"\[{escaped_ticket}\]\[({phase_group})\]"
    if re.search(pattern, command):
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Blocked by guard_ticket_commit.py: while ticket {active_ticket} is "
                f"active, every commit message must match "
                f"[{active_ticket}][dev-be|dev-ui|fix-be|fix-ui] <summary>. "
                f"Got: {command!r}"
            ),
        }
    }


def main(argv):
    workflow_root = _resolve_workflow_root(argv)
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(event, dict):
        return 0

    try:
        command = _extract_command(event.get("tool_input"))
        active_ticket = find_active_ticket(workflow_root)
        result = evaluate(command, active_ticket)
        if result is not None:
            json.dump(result, sys.stdout)
    except Exception:
        # Fail open: a bug in this hook must never be the thing that blocks
        # a commit, or the whole session.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
