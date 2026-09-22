#!/usr/bin/env python3
"""
PreToolUse hook — demo 3 (Exec Policy & Hooks).

Backstop for the exec-policy rule in .codex/rules/default.rules. That rule
only matches the exact prefix `cat .env`, so `cat ./.env`, `head -n5 .env`,
`Get-Content .\\.env`, `less .env`, `cat ../.env` from a subdirectory, etc.
all slip through it.
This hook instead pattern-matches the whole command string for ANY
reference to a real .env file (never .env.example) and denies the tool call
outright, regardless of which program was used to read it or what exact
path string was given.

Run manually to see the raw decision, independent of Codex:
    echo '{"tool_name":"Bash","tool_input":{"command":"head -n5 .env"}}' \
      | python3 .codex/hooks/block_secrets.py
"""
import json
import re
import sys

ENV_FILE_PATTERN = re.compile(r"(^|[\s\"'/\\])\.env(?!\.example)\b")


def _extract_command(tool_input):
    """tool_input's shape isn't guaranteed to be {"command": "..."} — some
    tool calls pass it as a raw argv list or a bare string instead of a
    dict. Handle all three so a shape this hook doesn't expect fails open
    (empty command, never matches) instead of crashing with an
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

        if ENV_FILE_PATTERN.search(command):
            json.dump(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "Blocked by block_secrets.py: this command references a "
                            ".env file, which holds plaintext secrets for this repo. "
                            "If you need a specific value, ask a human to check it "
                            "out of band instead of having Codex read/print the file."
                        ),
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
