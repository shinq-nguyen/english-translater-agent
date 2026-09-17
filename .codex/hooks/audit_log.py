#!/usr/bin/env python3
"""
Audit hook — demo 3 (Exec Policy & Hooks). Registered on THREE events in
.codex/hooks.json (UserPromptSubmit, PreToolUse, PostToolUse), all
non-blocking (`async: true` where the event allows async), alongside the
two hooks that can actually deny (block_secrets.py on PreToolUse,
scan_prompt_secrets.py on UserPromptSubmit) — this script never denies
anything, it only records.

One script, branching on `hook_event_name`, so .codex/logs/audit.log ends
up telling the whole story of a session in the order it happened, not
just "which tools ran":
  UserPromptSubmit  -> what came in: the prompt text
  PreToolUse        -> what the model proposed next: tool name + full args,
                       BEFORE it runs (this is "the model suggested X")
  PostToolUse       -> what actually happened: same tool call, plus its
                       result (this is "the tool ran and returned Y")
...then the next UserPromptSubmit, and so on. Every line carries
`session_id` and `turn_id`, so grouping by `turn_id` reconstructs one full
round of the exchange even when a turn makes several tool calls.

Redaction: any string inside `prompt`/`tool_input`/`tool_response` is
scanned for the same two secret shapes scan_prompt_secrets.py blocks on (a
JWT, or a provider API key) and matches are replaced with
"<redacted:...>" before the line is written — a more detailed audit log is
itself a new place a secret could end up, so it gets the same treatment
as the transcript it's supplementing. Long values are also truncated so
one big tool result (e.g. a large file read) can't blow up the log file.

Writes one JSON object per line (JSON Lines — easy to `grep`/parse, and
each line stands on its own even if the file is read while still being
written to).

Run manually to see a line appended for each event shape:
    echo '{"hook_event_name":"UserPromptSubmit","session_id":"demo","turn_id":"t1","prompt":"run mvn test"}' \
      | python3 .codex/hooks/audit_log.py
    echo '{"hook_event_name":"PreToolUse","session_id":"demo","turn_id":"t1","tool_name":"Bash","tool_input":{"command":"mvn test"}}' \
      | python3 .codex/hooks/audit_log.py
    echo '{"hook_event_name":"PostToolUse","session_id":"demo","turn_id":"t1","tool_name":"Bash","tool_input":{"command":"mvn test"},"tool_response":{"output":"BUILD SUCCESS","exit_code":0}}' \
      | python3 .codex/hooks/audit_log.py
    cat .codex/logs/audit.log
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "audit.log"

JWT_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
API_KEY_PATTERN = re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9]{16,}\b")
MAX_VALUE_LEN = 4000


def _redact_text(value):
    value = API_KEY_PATTERN.sub("<redacted:api-key>", value)
    value = JWT_PATTERN.sub("<redacted:jwt>", value)
    if len(value) > MAX_VALUE_LEN:
        value = value[:MAX_VALUE_LEN] + f"...<truncated, {len(value)} chars total>"
    return value


def _redact(value):
    """Recursively redact/truncate strings inside arbitrary JSON-shaped data
    (tool_input/tool_response can be any shape — dict, list, string, ...)."""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def _write(record):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(), **record}
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(event, dict):
        return 0

    hook_event_name = event.get("hook_event_name", "unknown")
    session_id = event.get("session_id", "unknown-session")
    turn_id = event.get("turn_id", "unknown-turn")

    try:
        _record(event, hook_event_name, session_id, turn_id)
    except Exception:
        # Fail open: a bug in this hook (or a payload shape it doesn't
        # expect yet) must never be the thing that fails the tool call or
        # the session — it only ever gets to observe, never to block.
        return 0

    # Purely observational: exit 0, no JSON output, so the session
    # continues exactly as it would without this hook.
    return 0


def _record(event, hook_event_name, session_id, turn_id):
    if hook_event_name == "UserPromptSubmit":
        prompt = event.get("prompt", "")
        _write(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "event": "UserPromptSubmit",
                "prompt": _redact(prompt),
            }
        )
    elif hook_event_name == "PreToolUse":
        _write(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "event": "PreToolUse",
                "tool_name": event.get("tool_name", "unknown-tool"),
                "tool_use_id": event.get("tool_use_id"),
                "tool_input": _redact(event.get("tool_input")),
            }
        )
    elif hook_event_name == "PostToolUse":
        _write(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "event": "PostToolUse",
                "tool_name": event.get("tool_name", "unknown-tool"),
                "tool_use_id": event.get("tool_use_id"),
                "tool_input": _redact(event.get("tool_input")),
                "tool_response": _redact(event.get("tool_response")),
            }
        )
    else:
        # Back-compat with older manual test snippets that omit
        # hook_event_name entirely, and a safe fallback for any event this
        # script gets registered for later without an update here.
        _write(
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "event": hook_event_name,
                "tool_name": event.get("tool_name"),
                "tool_input": _redact(event.get("tool_input")),
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
