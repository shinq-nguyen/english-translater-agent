#!/usr/bin/env python3
"""
PreToolUse hook — demo 8 (Exec Policy & Hooks), "PreToolUse can rewrite the
command" step.

A PreToolUse hook is not limited to allow/deny: it can hand back
`updatedInput` and Codex runs the rewritten command instead of the one the
model proposed. This hook demonstrates that by appending `--maxfail=1` to
any proposed `pytest` invocation that does not already have it.

Scoped deliberately to `pytest`: this repo is Java/Maven (tests run via
`mvn test`), so `pytest` is never a command any other demo or real workflow
here issues. That makes it safe to leave wired into .codex/hooks.json
permanently without touching any other demo's behavior — the rewrite is a
no-op for every command except the one this step asks you to type.

Run manually to see the raw decision, independent of Codex:
    echo '{"tool_input":{"command":"pytest"}}' \
      | python3 .codex/hooks/rewrite_pytest.py
"""
import json
import sys


def _extract_command(tool_input):
    """Same defensive shape-handling as block_secrets.py: tool_input may be
    a dict, a raw argv list, or a bare string depending on the tool call."""
    if isinstance(tool_input, dict):
        command = tool_input.get("command", "")
    else:
        command = tool_input
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    if not isinstance(command, str):
        command = "" if command is None else str(command)
    return command


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Fail open on malformed input rather than blocking Codex entirely.
        return 0
    if not isinstance(event, dict):
        return 0

    try:
        command = _extract_command(event.get("tool_input"))
        first_word = command.strip().split(" ", 1)[0] if command.strip() else ""

        if first_word == "pytest" and "--maxfail" not in command:
            json.dump(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": {"command": f"{command} --maxfail=1"},
                    }
                },
                sys.stdout,
            )
    except Exception:
        # Fail open: a bug in this hook must never be the thing that blocks
        # Codex's whole session.
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
