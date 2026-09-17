# Demo 3 — Execution Governance: Exec Policy & Hooks

Covers outline §8. Prerequisite: `demo-guides/00-setup.md` and
`01-overview.md` done. This demo deliberately breaks things first so the
problem is visible, then fixes them one layer at a time.

Real secret in play: root `.env` in this repo holds `APP_JWT_SECRET` and
`AI_MODEL_ENCRYPTION_KEY` in plaintext (that's the whole point of `.env`
files for local dev) — this demo is about stopping those values from
reaching a transcript from either direction: Codex reading and repeating
them (Steps 0–2), or a human pasting one straight into chat (Step 3) —
plus having a durable, redacted record of the whole prompt↔tool exchange,
not just which commands ran (Step 2).

**How to read each step:** a "Do this" block, an "Expected" block, and a
short "Why." Run Steps 0 → 4 in order — each one only makes sense once the
previous one has been seen. There's also one unnumbered **Note** between
Steps 2 and 3 — no "Do this" there, just the mental model Step 3 makes
concrete.

## Step 0 — see the problem (protections off)

**Do this:** temporarily disable everything this repo ships:
```bash
mv .codex/rules .codex/rules.disabled
mv .codex/hooks.json .codex/hooks.json.disabled
mv .codex/hooks .codex/hooks.scripts.disabled
```
Restart `codex` in the repo, then prompt:
> Run `cat .env` and tell me what's in it.

**Expected (uncomfortable) result:** Codex reads and repeats
`APP_JWT_SECRET=...` and `AI_MODEL_ENCRYPTION_KEY=...` straight into the
transcript.

**Why:** note what did *not* stop this — `sandbox_mode` is
`workspace-write`, but sandbox modes gate writes and network, not reads.
This is Session 1 §2's "read access vs security" point, made concrete.
Even switching to `sandbox_mode = "read-only"` wouldn't help; read-only
still means read access.

> **Verified gotcha:** renaming just `.codex/hooks.json` is **not**
> enough on Codex 0.154.0 — `block_secrets.py` still ran and blocked
> `cat .env` even with the registration file gone. You must also move
> `.codex/hooks/` itself (the scripts, renamed above) for the hook to
> actually stop firing; otherwise Step 0's "uncomfortable result" won't
> reproduce and the demo will look broken.

**Do this:** put all three back before continuing:
```bash
mv .codex/rules.disabled .codex/rules
mv .codex/hooks.json.disabled .codex/hooks.json
mv .codex/hooks.scripts.disabled .codex/hooks
```

## Step 1 — Exec Policy: classify the command, before it ever runs

`.codex/rules/default.rules` has four `prefix_rule()`s.

**Do this:** validate them directly, independent of a live Codex session:
```bash
codex execpolicy check --pretty --rules .codex/rules/default.rules -- cat .env
codex execpolicy check --pretty --rules .codex/rules/default.rules -- git push origin main
codex execpolicy check --pretty --rules .codex/rules/default.rules -- docker compose down -v
```

**Expected:** `forbidden`, `prompt`, and `forbidden` respectively.

**Why:** each verdict comes from matching the command's *shape*, before
Codex would ever get to a sandbox or approval check.

**Do this:** now restart `codex` and prompt exactly:
> Run `cat .env`

**Expected:** refused outright (`forbidden` — no approval prompt to click
through, it simply won't run).

### The prefix-matching gap

`pattern` matches an exact argument prefix.

**Do this:** prove the gap live:
> Run `head -n5 .env`

**Expected: not** blocked by exec policy — `["cat", ".env"]` never matches
a command whose program is `head`.

**Why:** this is real and not a trick: exec policy rules are static
command-shape rules, and covering "any way to read this file" with prefix
rules alone means enumerating every program and every path spelling.
That's exactly the gap Step 2's hook is for.

(Optional: also try `git push` and `docker compose down -v` here — the
first should prompt for approval instead of running silently, the second
should be refused with the data-loss justification from the rules file.)

## Step 2 — Hooks: the general backstop, and a full audit trail

`.codex/hooks.json` registers three scripts (in `.codex/hooks/`) across
five hook entries — `audit_log.py` is wired into all three events so the
log ends up telling the whole story of a session, not just "which tools
ran":

- **`block_secrets.py`** on `PreToolUse` (matcher: `Bash`) — regex-matches
  the *whole* command string for any real `.env` reference and denies the
  tool call, regardless of program or exact path spelling.
- **`scan_prompt_secrets.py`** on `UserPromptSubmit` (matcher: `*`) —
  Step 3's hook; denies a prompt that contains a JWT- or API-key-shaped
  string.
- **`audit_log.py`** on `UserPromptSubmit`, `PreToolUse`, *and*
  `PostToolUse` (all matcher `*`, all `async` — it never denies anything)
  — appends one JSON object per line to `.codex/logs/audit.log`: what
  came in (`UserPromptSubmit` → the prompt), what the model proposed next
  (`PreToolUse` → tool name + full arguments, *before* it runs), and what
  actually happened (`PostToolUse` → the same call, plus its result).
  Every line carries the same `session_id`/`turn_id`, so grouping by
  `turn_id` reconstructs one full round of prompt → proposed call(s) →
  result(s), even across several tool calls in one turn.

> **Verified gotcha:** every hook script here (and
> `plugins/ticket-workflow/hooks/guard_ticket_commit.py`, if that plugin's
> installed) originally only caught `json.JSONDecodeError` around
> `json.load(sys.stdin)` — nothing else. `tool_input` is documented as
> "any shape" (Codex's own schema: `"tool_input": true`), and a Bash call
> whose `tool_input` arrives as a raw argv list — `["bash", "-c", "..."]`
> — instead of `{"command": "..."}` made `(event.get("tool_input") or
> {}).get("command", "")` crash with `AttributeError: 'list' object has
> no attribute 'get'`, exit code 1, reproduced by piping that shape into
> the script directly. A hook that can only ever *observe* or *deny* must
> never itself become the reason a tool call fails — every script here
> now normalizes `tool_input` defensively and wraps its real logic in a
> broad `except Exception: return 0`, not just the narrow JSON-parsing
> one. Worth remembering for any hook you write: fail-open has to cover
> "this hook has a bug," not only "the input didn't parse."

**Do this:** first, Codex needs to trust these hooks — project-level,
non-managed hooks require a one-time review:
```
/hooks
```
Approve everything listed (all five entries across the three scripts) —
Step 3 needs `scan_prompt_secrets.py` already approved too.

**Do this:** now re-run the exact command that slipped through exec
policy:
> Run `head -n5 .env`

**Expected:** denied this time, with `block_secrets.py`'s reason surfaced
— because this hook matches on the full command text with a regex, not an
exact prefix, `.env` under any name/path variant is caught.

**Do this:** run a couple more turns, one with more than one tool call,
e.g.:
> Run `git log -3`, then run `mvn -v`

then read the trail `audit_log.py` has been writing the whole time,
independent of the transcript UI:
```bash
cat .codex/logs/audit.log
```

**Expected:** one JSON object per line. For each turn: a
`"event": "UserPromptSubmit"` line (the prompt you sent), then a matching
`"event": "PreToolUse"` / `"event": "PostToolUse"` pair for every tool
call the model made in response — same `turn_id` across that whole
round, a new `turn_id` for the next prompt. Reading it top to bottom
*is* the model↔tool conversation: what you asked, what the model decided
to run, what it got back, and so on — including the MCP tool call from
Demo 1 if you ran that in the same session.

**Why:** `PreToolUse`/`PostToolUse` fire for every tool, MCP tools
included — the "MCP is just another tool" point from Demo 1 showing up
again here. Logging the *proposed* call separately from its *result* is
what makes this replayable as a conversation instead of just a list of
completed actions: a `PreToolUse` line with no matching `PostToolUse`
line means that call never finished (e.g. Codex was interrupted).

**Note — where each mechanism sits in the lifecycle** (no hands-on step here, just the model to hold before Step 3)

Codex's hook events, in the order they can fire during a turn:
`SessionStart` → `UserPromptSubmit` → (`PreToolUse` → tool executes →
`PostToolUse`, once per tool call, can repeat many times per turn) → … →
`PreCompact`/`PostCompact` (only if compaction happens) → `Stop` →
`SessionEnd`.

- **Exec Policy** runs *before* `PreToolUse` even fires for a shell command
  — a `forbidden` verdict means Codex never proposes running it in a form
  that would reach a hook or the sandbox.
- **`PreToolUse`** hooks run after exec policy/sandbox would otherwise
  allow the call, but before it executes — the last point where you can
  still deny or rewrite it (`block_secrets.py` uses this to deny).
- **`PostToolUse`** hooks run after the tool already executed — useful for
  logging/auditing (`audit_log.py`) or for feeding back extra context, but
  too late to prevent the action itself.

**Why:** that maps directly onto the outline's distinction: Exec Policy is
command-level rules evaluated up front; Sandbox is the broader
execution-boundary that's active throughout; Hooks are custom logic you can
attach at any of several specific lifecycle points, before or after the
fact, for whatever Exec Policy's static rules don't express (a full
`.env`-shaped regex, a durable log file, anything else procedural).

## Step 3 — `UserPromptSubmit`: catching a secret a human pastes in

Steps 1–2 are both about the same exposure: Codex deciding to run a
command. This step is the other direction — a teammate pasting a real
secret straight into chat to ask for help debugging it, e.g. "why does my
session keep expiring, here's my token: `eyJhbGci...`". Nothing about
Exec Policy or `PreToolUse` sees this: no tool call is even involved, the
secret is just sitting in the prompt text.

`.codex/hooks.json` registers a third hook on `UserPromptSubmit`:

- **`scan_prompt_secrets.py`** — regex-matches the raw prompt for a
  JWT-shaped string (three dot-separated base64url segments — exactly
  what this app's own login tokens, signed by `APP_JWT_SECRET`, look
  like) or a provider-style API key (`sk-...`, `sk-or-v1-...`), and
  returns `{"decision": "block", ...}` if either shape is found.

**Do this:** in a `codex` session with the hooks approved (from Step 2),
paste this exact prompt (a synthetic, made-up JWT — not a real secret):
> Why does this keep expiring after 10 minutes: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlLWhlcmU

**Expected:** the prompt is refused before Codex ever responds to it —
`scan_prompt_secrets.py`'s reason is surfaced, asking you to describe the
symptom instead of pasting the value.

**Do this:** check the audit log again:
```bash
cat .codex/logs/audit.log
```

**Expected:** a new `"event": "UserPromptSubmit"` line for the prompt you
just sent — but its `"prompt"` field reads `<redacted:jwt>` where the
token was, not the real value. `audit_log.py` is a separate, independent
hook registration on the same event (not code inside
`scan_prompt_secrets.py`), and it applies the same JWT/API-key scan to
everything it writes — so even "we caught something" gets recorded
without ever writing down the thing that was caught.

**Why this event, not `PreToolUse`:** `UserPromptSubmit` fires right after
you hit Enter — before the prompt reaches the model, and before it's
written into this session's on-disk transcript (Codex's own hook input
schema for this event includes a `transcript_path` field naming that
file, which is how you know it's a target still being written to, not
already-written history). `PreToolUse`/`PostToolUse` only ever see what
*Codex* decides to do after it's already read a prompt — they can't undo
a human having already pasted a secret into a prompt the model has seen
and that's now sitting in the transcript. `UserPromptSubmit` is the one
point in the lifecycle early enough to stop that from happening at all.

## Step 4 — Exec Policy vs Sandbox, not either/or

**Do this:** look back at `.codex/config.toml`:
```toml
sandbox_mode = "workspace-write"
[sandbox_workspace_write]
network_access = false
```

**Expected takeaway:** with `network_access = false`, a `git push` would
likely already need elevated permission from the sandbox alone (it needs
the network).

**Why the exec-policy rule still earns its place:** the `git push`
exec-policy rule in `default.rules` is a floor that holds even if someone
later flips `network_access = true` for an unrelated reason (say, to let
Codex hit an API during a different demo) — defense in depth, not a
single point of control. That's outline §8's "Exec Policy vs Sandbox:
command-level rules vs. the broader execution boundary" — two layers, on
purpose, not a redundancy to simplify away.
