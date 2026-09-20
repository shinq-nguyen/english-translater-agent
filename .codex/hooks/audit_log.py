#!/usr/bin/env python3
"""
Agent-loop audit hook — demo 3 (Exec Policy & Hooks). Records Codex's
lifecycle events to .codex/logs/audit.log so a session's turns can be read
back as a trace of the loop the deck describes: user prompt -> harness ->
model -> harness -> tool -> harness -> model -> ... -> harness -> user.

One script, branching on `hook_event_name`, registered in .codex/hooks.json
on every hook event Codex exposes (see that file for the exact
registration) — this is what lets one log file tell the whole story of a
session in the order it happened, not just "which tools ran". Purely
observational: it never denies anything (see block_secrets.py on
PreToolUse and scan_prompt_secrets.py on UserPromptSubmit for the hooks
that can), and every codepath below fails open — a bug in this script must
never be the reason a tool call or the session fails.

What's real vs. reconstructed
------------------------------
Codex's hooks see the *envelope* around a model call, not its body: a
PreToolUse payload carries session_id, turn_id, tool_use_id, tool_name,
tool_input, the active model name and permission_mode — but not the system
prompt, skills catalog, MCP tool schemas, or conversation history that
actually went into that turn's request to the model. This script labels
every record's `body_source` accordingly, and the two records synthesized
around PreToolUse/PostToolUse ("harness_executes_tool",
"harness_sends_tool_result_to_model") are *inferred* bookkeeping that makes
the loop's shape visible — not a capture of the literal wire request.

To see that fixed, re-sent-every-call content for real — skills catalog,
AGENTS.md, environment context, permissions, and the full message history
appended so far — run:
    codex debug prompt-input
(no login, no model call, no cost — see demo-material/02-demo-harness.md
Step 3). Tool JSON schemas (shell, apply_patch, any MCP tool) aren't in
that dump either; they're sent as part of the turn's actual tool list, so
the real fixed cost per call is higher than even that command shows.

Record shape
------------
One JSON object per line (JSON Lines — easy to grep/parse, and each line
stands on its own even if the file is read while still being written to).
Every record carries:
    time, role, type, flow, event, turn_id, request_id, body_source, body
`role` is who the record is about (user/model/tool/harness), `flow` spells
out the hop in arrow form ("model -> harness"), and `body` is the
(redacted) raw hook payload Codex sent this script — deliberately kept
whole, even though some of its fields duplicate the top-level ones, so
nothing about the original payload is lost to the summary. Grouping by
`turn_id` reconstructs one full round of prompt -> proposed call(s) ->
result(s), even across several tool calls in one turn.

Mapping (hook_event_name -> records written):
    UserPromptSubmit -> user_prompt                          (user -> harness)
    PreToolUse        -> model_suggests_tool                 (model -> harness)
                       -> harness_executes_tool               (harness -> tool)
    PostToolUse       -> tool_returns                         (tool -> harness)
                       -> harness_sends_tool_result_to_model  (harness -> model)
    Stop              -> model_response                       (model -> harness)
    SubagentStart     -> subagent_started                     (harness -> model)
    SubagentStop      -> subagent_response                    (model -> harness)
    anything else (SessionStart, SessionEnd, PreCompact, PostCompact,
    Interrupt, ...) -> the raw hook_event_name, role "harness", flow
    "lifecycle" — bookkeeping around the loop, not a hop within it.

Redaction: every string anywhere inside the payload is scanned for a JWT
(three dot-separated base64url segments), a provider-style API key
(sk-...), a `Bearer <token>` header, and any `SOME_KEY: value` /
`SOME_KEY=value` pair whose key looks like a secret (APP_JWT_SECRET,
AI_MODEL_ENCRYPTION_KEY, *_API_KEY, *_PASSWORD, *_TOKEN, *_SECRET) —
matches become "<redacted:...>". Any dict key that itself looks sensitive
(api_key, password, secret, token, authorization) has its whole value
redacted regardless of shape. Long values are then truncated to
MAX_VALUE_LEN so one big tool result (e.g. a large file read) can't blow up
the log file. A more detailed audit log is itself a new place a secret
could end up, so it gets the same treatment as the transcript it's
supplementing.

Concurrency: PreToolUse/PostToolUse can fire for several tool calls in
close succession, so every write takes a lock on the log file itself
(msvcrt on Windows, flock elsewhere) to stop concurrent hook processes from
interleaving partial JSON lines.

Run manually to see records appended for each event shape:
    echo '{"hook_event_name":"UserPromptSubmit","turn_id":"t1","prompt":"run mvn test"}' \
      | python3 .codex/hooks/audit_log.py
    echo '{"hook_event_name":"PreToolUse","turn_id":"t1","tool_use_id":"tu1","tool_name":"Bash","tool_input":{"command":"mvn test"}}' \
      | python3 .codex/hooks/audit_log.py
    echo '{"hook_event_name":"PostToolUse","turn_id":"t1","tool_use_id":"tu1","tool_name":"Bash","tool_input":{"command":"mvn test"},"tool_response":"BUILD SUCCESS"}' \
      | python3 .codex/hooks/audit_log.py
    cat .codex/logs/audit.log
"""
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "audit.log"

JWT_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
API_KEY_PATTERN = re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9]{16,}\b")
BEARER_PATTERN = re.compile(r"(?i)(\bbearer\s+)[-\w.~+/=]{16,}")
# Generic "<PREFIX>_(KEY|PASSWORD|TOKEN|SECRET) = value" shape. Catches this
# repo's two real secrets (APP_JWT_SECRET, AI_MODEL_ENCRYPTION_KEY) along
# with any provider's *_API_KEY without needing to enumerate provider names.
KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?im)(\b[A-Z0-9_]*(?:KEY|PASSWORD|TOKEN|SECRET)\s*[:=]\s*)([^\s,;}\"']+)"
)
SENSITIVE_KEY_PATTERN = re.compile(r"(?i)(api[_-]?key|password|secret|token|authorization)")
MAX_VALUE_LEN = 4000

# Flow labels, named once so the loop's hops read the same way everywhere
# they're recorded (a hop can be recorded from more than one hook event).
FLOW_USER_TO_HARNESS = "user -> harness"
FLOW_MODEL_TO_HARNESS = "model -> harness"
FLOW_HARNESS_TO_TOOL = "harness -> tool"
FLOW_TOOL_TO_HARNESS = "tool -> harness"
FLOW_HARNESS_TO_MODEL = "harness -> model"
FLOW_LIFECYCLE = "lifecycle"


def _redact(value, key=None):
    """Recursively redact/truncate strings inside arbitrary JSON-shaped
    data (a hook payload can be any shape: dict, list, string, ...).
    Preserves the body's shape and non-secret content; only credentials
    are touched."""
    if key is not None and SENSITIVE_KEY_PATTERN.search(str(key)):
        return "<redacted:secret>"
    if isinstance(value, str):
        value = KEY_VALUE_SECRET_PATTERN.sub(r"\1<redacted:secret>", value)
        value = BEARER_PATTERN.sub(r"\1<redacted:bearer-token>", value)
        value = API_KEY_PATTERN.sub("<redacted:api-key>", value)
        value = JWT_PATTERN.sub("<redacted:jwt>", value)
        if len(value) > MAX_VALUE_LEN:
            value = value[:MAX_VALUE_LEN] + f"...<truncated, {len(value)} chars total>"
        return value
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {item_key: _redact(item, item_key) for item_key, item in value.items()}
    return value


@contextmanager
def _locked_log_file():
    """Prevent concurrent hook processes (e.g. several tool calls fired in
    the same turn) from interleaving JSON lines."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a+b") as fh:
        if fh.seek(0, os.SEEK_END) == 0:
            fh.write(b"\n")
            fh.flush()
        fh.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
            try:
                yield fh
            finally:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield fh
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _write(role, record_type, flow, event_name, body, *, source, request_id, turn_id, extra=None):
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "type": record_type,
        "flow": flow,
        "event": event_name,
        "turn_id": turn_id,
        "request_id": request_id,
        "body_source": source,
        "body": _redact(body),
    }
    if extra:
        record.update(extra)
    with _locked_log_file() as fh:
        fh.seek(0, os.SEEK_END)
        fh.write((json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
        fh.flush()


def _tool_request(event):
    return {
        "tool_name": event.get("tool_name"),
        "tool_use_id": event.get("tool_use_id"),
        "tool_input": event.get("tool_input"),
    }


def _record(event):
    hook_event = event.get("hook_event_name", "unknown")
    turn_id = event.get("turn_id", "unknown-turn")
    tool_id = event.get("tool_use_id")

    if hook_event == "UserPromptSubmit":
        _write(
            "user", "message", FLOW_USER_TO_HARNESS, "user_prompt", event,
            source="UserPromptSubmit hook stdin payload; raw model wire body is not exposed",
            request_id=turn_id, turn_id=turn_id,
        )
    elif hook_event == "PreToolUse":
        _write(
            "model", "tool_call", FLOW_MODEL_TO_HARNESS, "model_suggests_tool", event,
            source="PreToolUse hook stdin payload", request_id=tool_id, turn_id=turn_id,
        )
        _write(
            "harness", "tool_execution", FLOW_HARNESS_TO_TOOL, "harness_executes_tool", event,
            source="PreToolUse hook stdin payload; also mirrored concisely in the top-level tool_request field",
            request_id=tool_id, turn_id=turn_id, extra={"tool_request": _tool_request(event)},
        )
    elif hook_event == "PostToolUse":
        _write(
            "tool", "tool_result", FLOW_TOOL_TO_HARNESS, "tool_returns", event,
            source="PostToolUse hook stdin payload", request_id=tool_id, turn_id=turn_id,
        )
        _write(
            "harness", "model_request", FLOW_HARNESS_TO_MODEL, "harness_sends_tool_result_to_model", event,
            source="reconstructed from PostToolUse; exact raw model wire body is not exposed",
            request_id=tool_id, turn_id=turn_id,
        )
    elif hook_event == "Stop":
        _write(
            "model", "message", FLOW_MODEL_TO_HARNESS, "model_response", event,
            source="Stop hook stdin payload", request_id=turn_id, turn_id=turn_id,
        )
    elif hook_event == "SubagentStart":
        _write(
            "harness", "model_request", FLOW_HARNESS_TO_MODEL, "subagent_started", event,
            source="SubagentStart hook stdin payload", request_id=event.get("agent_id"), turn_id=turn_id,
        )
    elif hook_event == "SubagentStop":
        _write(
            "model", "message", FLOW_MODEL_TO_HARNESS, "subagent_response", event,
            source="SubagentStop hook stdin payload", request_id=event.get("agent_id"), turn_id=turn_id,
        )
    else:
        # SessionStart, SessionEnd, PreCompact, PostCompact, Interrupt, and
        # any future event this script hasn't been updated for yet: record
        # it as generic lifecycle bookkeeping rather than dropping it.
        _write(
            "harness", "lifecycle", FLOW_LIFECYCLE, hook_event, event,
            source=f"{hook_event} hook stdin payload", request_id=turn_id, turn_id=turn_id,
        )


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if isinstance(event, dict):
            _record(event)
    except Exception:
        # Fail open: a bug in this hook (or a payload shape it doesn't
        # expect yet) must never be the thing that fails the tool call or
        # the session — it only ever gets to observe, never to block.
        pass

    # Purely observational: exit 0, no JSON output, so the session
    # continues exactly as it would without this hook.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
