# Pre-work — build the MCP / Skill / Subagent / Hooks demo kit from scratch

Do this **before** the session (~30–40 minutes). This is not a Codex CLI
install guide (see Step 0 if you genuinely don't have `codex` yet) — it's a
hands-on build: starting from a plain `main` checkout, which has **none**
of this repo's Codex configuration (verified — `main` has no `.codex/`, no
`.agents/`, not even `AGENTS.md`), you'll write every file yourself: the
MCP server config, a Skill, a Subagent role, two Hooks, and an exec-policy
rules file. By the end you'll have the exact setup demos `02`–`04` walk
through, and — because you typed it — you'll actually know what each line
does instead of just turning something on.

If you'd rather skip the typing and just use a checkout that already has
all of this (e.g. the `session2-codex-demo` branch), you don't need this
file — just trust the project (Step 2) and jump to `01-overview.md`.
Everything below assumes you're building it up yourself on top of `main`.

**How to read each step below:** a short "Do this" block (what to type),
an "Expected" block (what you should see if it worked), and a one-line
"Why" (what's actually happening). If your result doesn't match
"Expected," stop and fix it before moving to the next step — everything
after Step 3 builds on the one before it.

## Step 0 — If you don't have Codex CLI yet

**Do this:**
- Make sure `node`, `npm`, `git`, `docker`, `docker compose` are on your PATH.
- **Windows:** do all of this inside **WSL2**, not PowerShell/cmd —
  `wsl --install` from an elevated PowerShell, reboot, enable Docker
  Desktop's WSL integration for your distro. The `docker compose exec` /
  heredoc commands below assume a POSIX shell.
- Install and log in:
  ```bash
  npm install -g @openai/codex
  codex login        # or: codex login --api-key "sk-..."
  codex --version     # this kit was written/verified against 0.154.0
  ```

**Expected:** `codex --version` prints a version number (0.154.0 or
later); `codex login` finishes without an auth error.

**Why:** everything else in this file assumes a logged-in `codex` binary
already on your PATH.

## Step 1 — Clone `main` and bring up the app's own dependencies

None of this step is Codex-specific yet — it's just getting the app
itself runnable, because the MCP server you'll configure in Step 3 needs a
real Postgres with real data to query.

**Do this:**
```bash
git clone https://github.com/shinq-nguyen/english-translater-agent.git
cd english-translater-agent
cp .env.example .env
```

Generate the two local secrets (throwaway values — never reuse real
secrets here; you'll deliberately try to leak these in Demo 3, so they
need to be real strings, not blank):
```bash
python3 - <<'PY'
import secrets, base64, pathlib
p = pathlib.Path(".env")
t = p.read_text()
t = t.replace("APP_JWT_SECRET=", "APP_JWT_SECRET=" + base64.b64encode(secrets.token_bytes(32)).decode())
t = t.replace("AI_MODEL_ENCRYPTION_KEY=", "AI_MODEL_ENCRYPTION_KEY=" + base64.b64encode(secrets.token_bytes(32)).decode())
p.write_text(t)
PY
```
(No `python3`? `openssl rand -base64 32` twice, paste both values in by
hand.)

> **Windows gotcha:** on some Windows machines `python3` is just the
> Microsoft Store alias stub, not a real interpreter, and the snippet
> above fails instead of running. If that happens, use `python -` instead
> of `python3 -` (or fall back to the `openssl` one-liners above).

Bring up Postgres and load the real schema (backend/frontend containers
aren't needed for the demos):
```bash
docker compose up -d postgres
# wait a few seconds for it to report healthy, then:
for f in backend/src/main/resources/db/migration/V*.sql; do
  docker compose exec -T postgres psql -U translator -d translator -f - < "$f"
done
```

**Expected:**
```bash
docker compose ps
# translator-postgres   ...   running (healthy)
```
`.env` now has non-empty `APP_JWT_SECRET=` and `AI_MODEL_ENCRYPTION_KEY=`
values (open the file and check if unsure).

**Why:** the demos read real seeded data (e.g. the `roles` table) through
a live Postgres, and Demo 3 deliberately targets the two secrets you just
generated — both need to exist before anything else in this file works.

## Step 2 — Trust the project in Codex

**Do this:**
```bash
codex
```
First time opening this folder, Codex asks to trust it — say yes, then
exit (`Ctrl+D`).

**Expected:** Codex opens without an error and the trust prompt appeared
and was accepted (it won't ask again on this machine for this checkout
path).

**Why:** project-level `.codex/config.toml`, `.codex/hooks.json`, and
`.codex/rules/` only take effect in a trusted project — do this now,
before writing any config, so it's one less variable while you build and
test each piece below. (Re-trust is needed again if you re-clone or move
machines.)

## Step 3 — Write the MCP server config

MCP is just another tool source Codex can call — but it runs as its own
process, outside Codex's sandbox (more on that in `02-demo-mcp.md`). This
step points Codex at a read-only Postgres MCP server aimed at the app's
own database.

**Do this:**
```bash
mkdir -p .codex
cat > .codex/config.toml <<'EOF'
# Root-level keys MUST come before any [table] header — TOML gotcha: once a
# [table] header appears, every following key belongs to THAT table, so
# putting sandbox_mode/approval_policy after [agents] would silently make
# them keys of [agents] instead, and Codex fails with something like
# `invalid type: string "workspace-write", expected struct AgentRoleToml`.

sandbox_mode = "workspace-write"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = false

# MCP server — a read-only Postgres tool pointed at the app's own DB.
# Requires `docker compose up -d postgres` (done in Step 1).
[mcp_servers.translator_db]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres", "postgresql://translator:translator@localhost:5432/translator"]
startup_timeout_sec = 15
tool_timeout_sec = 30
enabled = true

# Subagents — cap concurrency so a runaway fan-out can't happen live.
# The secret_auditor role itself is NOT declared here — Codex auto-discovers
# it from .codex/agents/secret-auditor.toml (Step 5), no [agents.secret_auditor]
# entry needed.
[agents]
max_threads = 4
max_depth = 1
EOF
```

Verify (re-trust with `codex` once more if this is the first file you've
added since Step 2, since new project config still needs a trusted
project):
```bash
codex mcp list
codex mcp get translator_db
```

**Expected:**
```
codex mcp list
translator_db   Status: enabled

codex mcp get translator_db
command: npx
startup_timeout_sec: 15
tool_timeout_sec: 30
```

**Why:** this is the one config file every later demo depends on —
`config.toml` is where the MCP server, the sandbox/approval defaults, and
the subagent concurrency caps all live.

## Step 4 — Write the Skill

A Skill is reusable, triggered know-how for *this* repo — loaded only when
relevant (Codex loads just the `name`+`description` frontmatter for every
skill up front; the full body only once it's picked — "progressive
disclosure"). This one encodes how this repo wants a new AI provider added.

**Do this:**
```bash
mkdir -p .agents/skills/add-ai-provider
cat > .agents/skills/add-ai-provider/SKILL.md <<'EOF'
---
name: add-ai-provider
description: Use when asked to add support for a new AI/LLM provider (a new AiProviderClient) to the translator backend, following the existing Anthropic / OpenAI-compatible pattern.
---

# Add a new AI provider client

This backend's AI integration is provider-agnostic by design:
`com.example.translator.translation.AiProviderClient` is a small interface
(`supports()` returns which `AiProviderType` it handles, `callModel(...)`
makes the HTTP call); `AiProviderClientRegistry` collects every Spring bean
that implements it into a `Map<AiProviderType, AiProviderClient>`; the two
existing implementations are `AnthropicProviderClient` and
`OpenAiCompatibleProviderClient`, all in
`backend/src/main/java/com/example/translator/translation/`.

Follow these steps, in order:

1. Read `AiProviderClient.java`, `AiProviderClientRegistry.java`, and BOTH
   existing implementations first. Do not start writing before you've seen
   how the two existing clients build a request and map a response — the
   new one should look like a sibling of those, not a novel design.
2. Add the new provider to the `AiProviderType` enum in
   `com.example.translator.aimodel.AiProviderType`.
3. Create `<Provider>ProviderClient` in the same `translation` package,
   implementing `AiProviderClient`. It only needs to be `@Component`-annotated
   for the registry to pick it up automatically — there is no separate
   registration step to remember.
4. Build a fresh `RestClient` per call from the given `AiModelConfig`
   (baseUrl/model/apiKey) exactly like the existing clients do — do not
   cache a client across calls, so an admin editing the config takes effect
   immediately.
5. Never introduce a second place that stores or logs the raw API key.
   `ApiKeyAttributeConverter` (in `com.example.translator.aimodel`) already
   AES-256-GCM encrypts `AiModelConfig.apiKey` at rest using
   `AI_MODEL_ENCRYPTION_KEY` — that happens transparently via JPA, so as
   long as the new client reads `config.getApiKey()` like the others do, it
   gets this for free. Do not add your own encryption, and do not log the
   key at any log level.
6. Add a test alongside the existing provider-client tests
   (`backend/src/test/java/.../translation/`) that mocks the HTTP call and
   asserts request shape + response mapping, mirroring the existing
   Anthropic/OpenAI-compatible test structure.
7. Only touch the frontend if the new provider needs an admin-form field
   Anthropic/OpenAI-compatible don't already have; if so, follow the
   existing "AI Models" admin page pattern instead of adding a new one.

When done, report: the new enum value, the new class's fully-qualified
name, and which test file you added/extended. Do not report or repeat any
API key value used in a manual test.
EOF
```

Verify inside `codex`:
```
/skills
```

**Expected:** `add-ai-provider` appears in the list with just its one-line
description — not the full body shown above.

**Why:** "progressive disclosure" — Codex keeps every skill's short
description in context all the time (cheap), but only loads the full
step-by-step body once a task actually matches it (Demo 2 makes this
visible live).

## Step 5 — Write the Subagent role

A Subagent buys context isolation, not speed: its own context is thrown
away once it reports back, so the parent thread only inherits a summary,
not every file it read. This one is a read-only investigator for a broad
question — how secrets flow through this repo.

**Do this:**
```bash
mkdir -p .codex/agents
cat > .codex/agents/secret-auditor.toml <<'EOF'
# IMPORTANT (verified against codex-rs source, core/src/agent/role.rs): only
# a whitelist of fields set here reach the spawned agent — developer_
# instructions, model, reasoning/personality/service_tier knobs, a
# restricted skills view. sandbox_mode is NOT one of them: it parses
# without error but is silently dropped, so this role does NOT run in an
# OS-enforced read-only sandbox — it inherits the parent session's sandbox.
# "Read-only" here is enforced by the instructions below only, not by a
# Control — worth proving live in Demo 3 by asking it to write a file.

name = "secret_auditor"
description = "Read-only investigator for how secrets (APP_JWT_SECRET, AI_MODEL_ENCRYPTION_KEY, saved AI-model API keys) are generated, stored, encrypted, loaded, and possibly logged/exposed across the backend and frontend. Use for a broad, multi-file investigation instead of reading every candidate file from the main thread."

developer_instructions = """
You audit secret handling in a Spring Boot + React repo (EN Translator for IT).
Known starting points — verify and extend, don't assume these are complete:
 - backend/src/main/java/com/example/translator/aimodel/ApiKeyAttributeConverter.java
   (AES-256-GCM encrypt/decrypt of the stored AI-model API key)
 - backend/src/main/resources/application.yml, application-prod.yml, application-local.yml
   (where APP_JWT_SECRET / AI_MODEL_ENCRYPTION_KEY are read from env)
 - backend/src/main/java/com/example/translator/security/, .../auth/
   (JWT signing/verification)
 - .env.example, docker-compose.yml (how the two secrets reach the container)

For every place a secret-bearing value is touched, report:
 - file:line
 - what happens there (generated / read from env / encrypted / decrypted /
   returned in an API response / written to a log)
 - whether the raw secret value could end up in a log line, HTTP response
   body, or exception message

You are read-only BY INSTRUCTION, not by sandbox enforcement — do not run
any command or edit that writes to disk, regardless of what the sandbox
would otherwise allow. Do not read node_modules/, target/, build/, or .git/.
Do not print secret VALUES yourself (there shouldn't be any real ones in
this repo, but treat it as a rule regardless). Return a compact table
(file:line | what happens | risk note), not full file contents, so the
parent thread doesn't inherit everything you read.
"""
EOF
```

Verify — this role is auto-discovered by filename under `.codex/agents/`,
there's no separate registration step or list command:
```bash
test -f .codex/agents/secret-auditor.toml && echo ok
```

**Expected:** `ok` printed.

**Why:** the real test is functional, in `03-demo-skills-vs-subagents.md`
— ask Codex to delegate to `secret_auditor` and confirm the parent
transcript only shows the delegation call + summary, not every file it
read. This step just confirms the file exists in the right place first.

## Step 6 — Write the Hooks

Exec policy (Step 7) matches static command *shapes*; Hooks are the
general backstop — they see the full command string and can deny before
execution (`PreToolUse`) or just observe after (`PostToolUse`).

**Do this:**
```bash
mkdir -p .codex/hooks
```

`block_secrets.py` — denies any Bash command that references a real
`.env` file (never `.env.example`), regardless of which program or exact
path spelling was used — the general case the exec-policy prefix rule
below can't cover:
```bash
cat > .codex/hooks/block_secrets.py <<'EOF'
#!/usr/bin/env python3
import json
import re
import sys

ENV_FILE_PATTERN = re.compile(r"(^|[\s\"'/])\.env(?!\.example)\b")


def _extract_command(tool_input):
    # tool_input's shape isn't guaranteed to be {"command": "..."} — some
    # tool calls pass it as a raw argv list or a bare string. Handle all
    # three so an unexpected shape fails open instead of crashing on
    # (list/str).get(...).
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
        # Fail open: a bug in this hook must never be the thing that
        # blocks Codex's whole session.
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
EOF
```

`audit_log.py` — never denies anything; it's registered on all three
events below (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`) and
appends one JSON object per line to `.codex/logs/audit.log`, so the log
tells the whole story of a session — what came in, what the model
proposed next, what actually happened — not just "which tools ran".
Every line carries `session_id`/`turn_id` so grouping by `turn_id`
reconstructs one full round of the exchange. String values inside
`prompt`/`tool_input`/`tool_response` are scanned for the same two secret
shapes `scan_prompt_secrets.py` (next) blocks on and redacted before
writing — a more detailed log is itself a new place a secret could end
up, so it gets the same treatment as the transcript it's supplementing:
```bash
cat > .codex/hooks/audit_log.py <<'EOF'
#!/usr/bin/env python3
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

    return 0


def _record(event, hook_event_name, session_id, turn_id):
    if hook_event_name == "UserPromptSubmit":
        prompt = event.get("prompt", "")
        _write({
            "session_id": session_id,
            "turn_id": turn_id,
            "event": "UserPromptSubmit",
            "prompt": _redact(prompt),
        })
    elif hook_event_name == "PreToolUse":
        _write({
            "session_id": session_id,
            "turn_id": turn_id,
            "event": "PreToolUse",
            "tool_name": event.get("tool_name", "unknown-tool"),
            "tool_use_id": event.get("tool_use_id"),
            "tool_input": _redact(event.get("tool_input")),
        })
    elif hook_event_name == "PostToolUse":
        _write({
            "session_id": session_id,
            "turn_id": turn_id,
            "event": "PostToolUse",
            "tool_name": event.get("tool_name", "unknown-tool"),
            "tool_use_id": event.get("tool_use_id"),
            "tool_input": _redact(event.get("tool_input")),
            "tool_response": _redact(event.get("tool_response")),
        })
    else:
        _write({
            "session_id": session_id,
            "turn_id": turn_id,
            "event": hook_event_name,
            "tool_name": event.get("tool_name"),
            "tool_input": _redact(event.get("tool_input")),
        })


if __name__ == "__main__":
    raise SystemExit(main())
EOF
```

`scan_prompt_secrets.py` — a third script, on `UserPromptSubmit` instead
of `PreToolUse`/`PostToolUse`: catches a teammate pasting a real secret
straight into chat (no tool call involved at all, so `block_secrets.py`
above never sees it), before the prompt reaches the model and before
it's written into this session's on-disk transcript. Only job is
detect-and-block — `audit_log.py` (above) is the one that records
prompts, so this stays single-purpose:
```bash
cat > .codex/hooks/scan_prompt_secrets.py <<'EOF'
#!/usr/bin/env python3
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
        # Fail open: a bug in this hook must never be the thing that
        # blocks a prompt, or the whole session.
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
EOF
chmod +x .codex/hooks/block_secrets.py .codex/hooks/audit_log.py .codex/hooks/scan_prompt_secrets.py
```

Now register everything — five hook entries across the three scripts:
`block_secrets.py` on `PreToolUse`/`Bash` only (can deny);
`scan_prompt_secrets.py` on `UserPromptSubmit`/`*` (can deny);
`audit_log.py` on all three events, matcher `*`, always `async` since it
only ever observes:
```bash
cat > .codex/hooks.json <<'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/block_secrets.py",
            "timeout": 10,
            "statusMessage": "Checking command against .env-file policy"
          }
        ]
      },
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/audit_log.py",
            "timeout": 10,
            "statusMessage": "Recording proposed tool call",
            "async": true
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/audit_log.py",
            "timeout": 10,
            "statusMessage": "Recording tool result",
            "async": true
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/scan_prompt_secrets.py",
            "timeout": 10,
            "statusMessage": "Scanning prompt for pasted tokens/keys"
          }
        ]
      },
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .codex/hooks/audit_log.py",
            "timeout": 10,
            "statusMessage": "Recording prompt",
            "async": true
          }
        ]
      }
    ]
  }
}
EOF
```

Verify each script standalone first, no Codex needed — this is the
fastest way to catch a typo before wiring it into a live session:
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"head -n5 .env"}}' \
  | python3 .codex/hooks/block_secrets.py

echo '{"hook_event_name":"UserPromptSubmit","session_id":"demo","turn_id":"t1","prompt":"run mvn test"}' \
  | python3 .codex/hooks/audit_log.py
echo '{"hook_event_name":"PreToolUse","session_id":"demo","turn_id":"t1","tool_name":"Bash","tool_input":{"command":"mvn test"}}' \
  | python3 .codex/hooks/audit_log.py
echo '{"hook_event_name":"PostToolUse","session_id":"demo","turn_id":"t1","tool_name":"Bash","tool_input":{"command":"mvn test"},"tool_response":{"output":"BUILD SUCCESS"}}' \
  | python3 .codex/hooks/audit_log.py
cat .codex/logs/audit.log

echo '{"prompt":"why does this expire so fast: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlLWhlcmU"}' \
  | python3 .codex/hooks/scan_prompt_secrets.py
```

**Expected:**
```
# block_secrets.py call:
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", ...}}

# audit_log.py calls: three JSON lines appended to .codex/logs/audit.log,
# one each for "event": "UserPromptSubmit"/"PreToolUse"/"PostToolUse",
# all sharing "turn_id": "t1"

# scan_prompt_secrets.py call:
{"decision": "block", "reason": "Blocked by scan_prompt_secrets.py: ..."}
```

Then inside `codex`, run `/hooks` and approve everything listed.

**Expected:** `block_secrets.py`, `audit_log.py`, and `scan_prompt_secrets.py`
all listed and approved — project-level, non-managed hooks require this
one-time review before they're active for a session.

**Why:** exec policy (next step) only understands static command shapes;
these three scripts cover what it can't — `block_secrets.py` denies a
command before it runs, `scan_prompt_secrets.py` catches a secret pasted
into the prompt itself before Codex ever sees it, and `audit_log.py`
keeps a durable, redacted record of the full prompt↔tool exchange nobody
can lose by scrolling past it in the transcript.

## Step 7 — Write the exec-policy rules

Exec policy classifies a command's *shape* before it ever reaches
`PreToolUse` or the sandbox — cheaper and earlier than a hook, but only as
precise as the prefix you write (see the prefix-matching gap called out in
`04-demo-exec-policy-hooks.md`, which is exactly why Step 6's hook exists
too — defense in depth, not either/or).

**Do this:**
```bash
mkdir -p .codex/rules
cat > .codex/rules/default.rules <<'EOF'
# Decisions, most restrictive wins when several rules match: forbidden > prompt > allow.
# Validate any change with:
#   codex execpolicy check --pretty --rules .codex/rules/default.rules -- <command...>

# 1. Never let Codex print the root .env (APP_JWT_SECRET, AI_MODEL_ENCRYPTION_KEY
#    live there in plaintext) straight into the transcript.
#    NOTE: pattern matches an exact argument PREFIX — this only catches the
#    literal command `cat .env`, not `cat ./.env`, `head .env`, etc. That gap
#    is what the PreToolUse hook in .codex/hooks.json backstops.
prefix_rule(
    pattern = ["cat", ".env"],
    decision = "forbidden",
    justification = "Root .env holds APP_JWT_SECRET and AI_MODEL_ENCRYPTION_KEY in plaintext.",
    match = ["cat .env"],
    not_match = ["cat .env.example", "cat ./.env", "head .env"],
)

# 2. printenv can dump secrets that are only in the shell's environment
#    (e.g. exported by docker compose), not in a file exec-policy can name.
#    Ask instead of silently allowing or silently blocking.
prefix_rule(
    pattern = ["printenv"],
    decision = "prompt",
    justification = "printenv can leak APP_JWT_SECRET / AI_MODEL_ENCRYPTION_KEY / DB_PASSWORD from the environment.",
    match = ["printenv", "printenv APP_JWT_SECRET"],
)

# 3. Pushing should always be a deliberate, approved action, even though
#    workspace-write + on-request would otherwise let network-free git
#    subcommands run without a prompt.
prefix_rule(
    pattern = ["git", "push"],
    decision = "prompt",
    justification = "A push is externally visible and hard to fully undo; always confirm.",
    match = ["git push", "git push origin main"],
)

# 4. This wipes the translator-pgdata named volume — every saved user,
#    note, and AI model config, gone. Never let it run unattended.
prefix_rule(
    pattern = ["docker", "compose", "down", "-v"],
    decision = "forbidden",
    justification = "Deletes the translator-pgdata volume; irreversible data loss.",
    match = ["docker compose down -v"],
)
EOF
```

Verify directly, no live session needed:
```bash
codex execpolicy check --pretty --rules .codex/rules/default.rules -- cat .env
codex execpolicy check --pretty --rules .codex/rules/default.rules -- git push origin main
codex execpolicy check --pretty --rules .codex/rules/default.rules -- docker compose down -v
```

**Expected:** `forbidden`, `prompt`, `forbidden` — in that order.

**Why:** exec policy runs *before* Codex ever proposes the command in a
form that would reach a hook or the sandbox — it's the cheapest, earliest
layer, but only as good as the exact prefixes you wrote (Demo 3 shows the
gap live).

## Step 8 — (Optional but recommended) Write `AGENTS.md`

Not a new mechanism — just always-loaded instructions, in context every
turn without any invocation. The demos assume it's already in play.

**Do this:** add a short `AGENTS.md` describing the repo (see the version
in `01-overview.md`'s "what's already in the repo" list for a template) —
even a few lines pointing at where the translation pipeline and secrets
live is enough for the demos to make sense.

**Expected:** `AGENTS.md` exists at the repo root with at least a couple
of lines about where the translation pipeline and secrets live.

**Why:** unlike Skills or Subagents, `AGENTS.md` needs no trigger or
invocation — it's the baseline instruction layer every demo can assume is
already loaded.

## Step 9 — Self-check: confirm all five pieces actually work

| Check | Command | Expect |
|---|---|---|
| Codex installed & logged in | `codex --version` / `codex doctor` → `auth` | Version prints; auth not "no credentials" |
| Config loads clean | `codex doctor` → "Configuration" | `config.toml parse: ok`, `MCP servers: 1` |
| Database up | `docker compose ps` | `translator-postgres` `running`/`healthy` |
| **MCP** | `codex mcp list` | `translator_db`, `Status: enabled` |
| **Skill** | inside `codex`, `/skills` | `add-ai-provider` listed |
| **Subagent** | `test -f .codex/agents/secret-auditor.toml` | file exists (auto-discovered) |
| **Hooks** | inside `codex`, `/hooks` | `block_secrets.py` + `audit_log.py` listed, approved |
| **Exec policy** | `codex execpolicy check --pretty --rules .codex/rules/default.rules -- cat .env` | `forbidden` |

**Why:** run this table top to bottom before the session starts — it's
the same order the config depends on (app up → trusted → MCP → Skill →
Subagent → Hooks → exec policy), so the first row that fails is usually
the actual root cause, even if a later row also looks wrong.

If `codex doctor` prints `Error loading config.toml: ...`, re-check the
TOML-gotcha comment at the top of Step 3's snippet before debugging
further — root keys after a `[table]` header silently become keys of that
table.

## Known limitation — Codex's sandbox and network access on native Windows

Verified on a real Windows 11 machine, not inferred: `sandbox_mode =
"read-only"` does **not** reliably block a raw network connection (e.g.
`psql -h localhost`) when Codex runs natively on Windows (PowerShell/cmd,
outside WSL2). This is why Step 0 says WSL2, and why `02-demo-mcp.md`'s
Step 4 demo uses a **filesystem write**, not a network call, to show the
sandbox boundary — that part is enforced reliably on every platform.

Codex's Windows network enforcement has three levels, and only the last
one is a real OS-level barrier:

1. **Disabled** — no `[windows] sandbox` / `features.windows_sandbox*` set
   (the state of this kit's plain `.codex/config.toml`) → nothing is
   enforced at all. A tool like `psql` just connects.
2. **Unelevated (restricted token)** — "no network" is implemented as
   environment-variable hints only (`HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`
   pointed at a dead address, `NPM_CONFIG_OFFLINE`, `CARGO_NET_OFFLINE`,
   `PIP_NO_INDEX`, a stubbed `ssh`/`scp`, deleted `curl.bat`/`wget.cmd`).
   Any tool that opens a raw socket directly instead of reading a proxy env
   var — `psql` via libpq included — ignores all of it and connects anyway.
3. **Elevated** — runs under a dedicated sandboxed Windows user with
   firewall rules bound to that user's SID; this is real enforcement, but
   even here loopback (`localhost`/`127.0.0.1`) is explicitly exempted
   (`allow_local_binding`), so a connection to Postgres on `localhost:5432`
   still isn't blocked. Only a handful of specific ports/protocols (DNS 53,
   DoT 853, SMB 139/445, ICMP) are blocked outright.

Check which level you're on before trusting any network-based sandbox demo:
```bash
# any output here (e.g. "1 http://127.0.0.1:9") = level 2 (env-only, still
# bypassable); no output at all = level 1 (disabled)
codex sandbox -c 'sandbox_mode="read-only"' -- cmd /c set | findstr "SBX_NONET_ACTIVE HTTP_PROXY"
```
```powershell
# any rows here = level 3 (elevated, real firewall enforcement)
Get-NetFirewallRule -DisplayName "Codex Sandbox Offline*"
```
Filesystem writes don't have this problem — they're checked by the OS's
own permission system at every level, which is why `02-demo-mcp.md`'s
trust-boundary demo is built around a blocked file write instead. If you
specifically want to demo the *network* case, do it inside a real WSL2
distro (`wsl --install -d Ubuntu` — not the internal `docker-desktop`
distro Docker Desktop manages, which has no dev tools and isn't meant for
this) or on macOS/Linux, where enforcement goes through
seccomp/Landlock/sandbox-exec instead of this Windows-specific path.

## Troubleshooting

- **Trust prompt keeps reappearing** — it's tied to the exact local path;
  a fresh clone or a different machine triggers it again, expected.
- **`npm install -g` fails with `EACCES`** — use [nvm](https://github.com/nvm-sh/nvm)
  instead of `sudo npm install -g`.
- **WSL2: `docker` not found inside Ubuntu** — enable Docker Desktop's WSL
  integration for your distro, restart the Ubuntu terminal.
- **Port 5432 already in use** — stop the other local Postgres, or change
  the `ports:` mapping in `docker-compose.yml` for your copy only.
- **`codex mcp list` shows `translator_db` but queries fail** — check
  `docker compose ps` first; almost always Postgres isn't actually up.
- **Hook doesn't fire in a live session but the manual `echo | python3 ...`
  test worked** — you likely skipped the `/hooks` approval step (Step 6);
  it's required once per session for non-managed project hooks.
- **`codex doctor` shows `reachability`/`websocket` failures** — as long as
  `auth` doesn't say "no credentials" and a real prompt gets a response,
  those two probes failing is usually just a corporate proxy, not a real
  problem.
