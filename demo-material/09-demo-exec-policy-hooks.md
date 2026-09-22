# Demo 8 — Exec policy and Hooks

Covers slides 43–54. Complete `00-setup.md` first. This demo is safe to run
on both Windows and Linux: it never prints the real `.env` file.

## Purpose

Show the order and responsibility of the protections:

1. Exec policy classifies a command shape before it runs.
2. `PreToolUse` Hooks inspect the full proposed command and can deny it.
3. `UserPromptSubmit` Hooks can stop a secret pasted directly into chat.
4. `PostToolUse` Hooks can write a redacted audit trail after a tool runs.
5. `PreToolUse` Hooks can also rewrite a proposed command, not just allow
   or deny it.

## Step 1 — Check exec-policy decisions

Run the platform-specific commands below.

### Windows (PowerShell)

```powershell
codex execpolicy check --pretty --rules .\.codex\rules\default.rules -- type .env
codex execpolicy check --pretty --rules .\.codex\rules\default.rules -- git push origin main
codex execpolicy check --pretty --rules .\.codex\rules\default.rules -- docker compose down -v
```

### Linux/macOS (Bash)

```bash
codex execpolicy check --pretty --rules .codex/rules/default.rules -- cat .env
codex execpolicy check --pretty --rules .codex/rules/default.rules -- git push origin main
codex execpolicy check --pretty --rules .codex/rules/default.rules -- docker compose down -v
```

Expected: `forbidden`, `prompt`, `forbidden`, in that order. The command is
classified before it reaches approval or the sandbox.

## Step 2 — See the prefix-rule gap without reading `.env`

Exec policy matches configured command shapes. A different reader command is
not necessarily covered by the static rule, so use the Hook as the general
backstop.

### Windows (PowerShell)

In a Codex session, ask:

> Run `Get-Content .\.env`.

### Linux/macOS (Bash)

In a Codex session, ask:

> Run `head -n5 .env`.

Expected: the command is denied by `block_secrets.py`. Do not approve or
retry the command. The Hook sees the full command text and blocks the request
without exposing the file contents.

## Step 3 — Inspect the audit Hook

Inside Codex, run:

```text
/hooks
```

Approve the project hooks if Codex asks. Then run a harmless prompt such as:

> Run `git log -3`, then tell me how many commits were shown.

Read the audit file.

Windows (PowerShell):

```powershell
Get-Content .\.codex\logs\audit.log -Tail 20
```

Linux/macOS (Bash):

```bash
tail -n 20 .codex/logs/audit.log
```

Expected: JSON lines for `UserPromptSubmit`, `PreToolUse`, and
`PostToolUse`. Matching `turn_id` values connect one prompt to its proposed
tool call and result. The audit Hook observes; it does not grant permission.

## Step 4 — Block a secret pasted into chat

In the same session, paste this synthetic token (it is not a real secret):

> Why does this expire after 10 minutes: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlLWhlcmU

Expected: `scan_prompt_secrets.py` blocks the prompt before Codex answers.
The audit log records a redacted marker such as `<redacted:jwt>`, not the
token value.

## Step 5 — `PreToolUse` can rewrite the command, not just allow or deny it

A `PreToolUse` hook's decision is not limited to `allow`/`deny`: it can also
return `updatedInput`, and Codex runs the rewritten command instead of the
one the model proposed. `.codex/hooks/rewrite_pytest.py` is wired for
exactly this — scoped to `pytest`, which this Java/Maven repo never runs for
real (`mvn test` is the actual test command), so it cannot interfere with
any other demo in this kit.

In a Codex session, ask:

> Run `pytest` in the shell.

Expected: the command fails with "pytest is not recognized"/"command not
found" — this repo has no Python test suite, so that failure is expected
and not the point. What matters is *which* command actually ran. Check the
audit log:

Windows (PowerShell):

```powershell
Get-Content .\.codex\logs\audit.log -Tail 20
```

Linux/macOS (Bash):

```bash
tail -n 20 .codex/logs/audit.log
```

Expected: the `PreToolUse` line's `tool_input.command` reads
`pytest --maxfail=1`, not the bare `pytest` the model proposed. Nothing in
the chat transcript calls out that the command changed — a rewrite is
invisible unless you go looking for it, which is why a hook that rewrites
should also log what it replaced.

## Step 6 — Compare the layers

| Layer | Sees | Can block | Example |
|---|---|---:|---|
| Exec policy | command shape | Yes | deny `docker compose down -v` |
| Sandbox | operating-system operation | Yes | deny a file write in `read-only` |
| `PreToolUse` | full proposed tool input | Yes | deny any `.env` reference |
| `PostToolUse` | completed tool call/result | No | append audit log |
| `UserPromptSubmit` | submitted prompt | Yes | block a pasted JWT |

The layers complement each other. A Hook is useful for procedural checks,
but a hard boundary should also use sandbox or a forbidden exec-policy rule.
`PreToolUse` is the only row that can also *rewrite* what runs (Step 5),
in addition to allowing or denying it.

## Cleanup

No project settings need to be changed. If you created scratch files while
testing, remove them using `Remove-Item` on Windows or `rm -f` on Linux/macOS.
Never delete the real `.env` or print its contents.
