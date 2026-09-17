#!/usr/bin/env python3
"""
UserPromptSubmit hook — demo 3 (Exec Policy & Hooks).

A different exposure than block_secrets.py/audit_log.py: those two only
ever see what Codex itself decides to run. This one is the other
direction — a teammate pasting a real secret straight into chat to ask
for help, e.g. "why does my session keep expiring, here's my token:
eyJhbGci...".

UserPromptSubmit fires right after Enter, before the prompt reaches the
model and before it is appended to this session's on-disk transcript.
Verified against Codex 0.154.0's own embedded JSON schema
(`user-prompt-submit.command.input`/`.output`, dumped from the codex.exe
binary itself): the hook's stdin payload already names that file via a
`transcript_path` field, which means the transcript exists as a target
but the prompt text this hook is looking at has not been written into it
yet. Returning `{"decision": "block", ...}` here means the raw value
never reaches the model AND never lands on disk in the first place —
strictly earlier than PreToolUse (which only sees what the model already
decided to do *after* reading the prompt) or PostToolUse (fully
after-the-fact).

Detects two shapes without needing to know any specific secret value:
- a JWT: three dot-separated base64url segments. This repo's own login
  tokens (signed by APP_JWT_SECRET) are shaped exactly like this, and a
  login token is exactly the kind of thing a teammate reaches for when
  asking "why do I keep getting logged out."
- a provider-style API key (`sk-...`, `sk-or-v1-...`), the shape called
  out in `.env.example`'s own comment for AI-model API keys.

This script's only job is detect-and-block — it does not write to
.codex/logs/audit.log itself. `audit_log.py` is registered on
UserPromptSubmit too (see .codex/hooks.json) and records every prompt,
blocked or not, redacting the same two shapes before writing; splitting
"can this deny?" from "does this get recorded?" into two independent
hooks keeps each one single-purpose.

Run manually to see the raw decision, independent of Codex:
    echo '{"prompt":"why does this expire so fast: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlLWhlcmU"}' \
      | python3 .codex/hooks/scan_prompt_secrets.py
"""
import json
import re
import sys

JWT_PATTERN = re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
API_KEY_PATTERN = re.compile(r"\bsk-(?:or-v1-)?[A-Za-z0-9]{16,}\b")


def _classify(prompt):
    if API_KEY_PATTERN.search(prompt):
        return "provider API key"
    if JWT_PATTERN.search(prompt):
        return "JWT-shaped token"
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Fail open on malformed input rather than blocking every prompt.
        return 0
    if not isinstance(event, dict):
        return 0

    try:
        prompt = event.get("prompt", "")
        if not isinstance(prompt, str):
            return 0

        match_kind = _classify(prompt)
        if match_kind is None:
            return 0

        json.dump(
            {
                "decision": "block",
                "reason": (
                    f"Blocked by scan_prompt_secrets.py: this prompt contains what "
                    f"looks like a {match_kind}. Don't paste a real token or API "
                    f"key into chat to debug it — describe the symptom instead "
                    f'(e.g. "my session token keeps expiring after 10 minutes"), '
                    f"or hand the value to a human out of band if someone actually "
                    f"needs to inspect it."
                ),
            },
            sys.stdout,
        )
    except Exception:
        # Fail open: a bug in this hook must never be the thing that blocks
        # a prompt, or the whole session.
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
