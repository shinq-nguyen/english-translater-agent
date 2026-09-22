# Demo 9 — Putting Everything Together: a full Skill+Subagents+MCP+Hooks workflow

Covers deck slides 55–65. This is the session's synthesis demo: the mechanisms from
Demos 6–8 — a Skill deciding the steps, Subagents doing isolated BE/UI/test
work, MCP as the Jira connection, and Hooks as the guardrail — running
together in one real workflow instead of one mechanism at a time.

Unlike Demos 1–8, this demo needs its own pre-work — a real Jira Cloud
site — since it exercises a real OAuth-based remote MCP server rather than
this repo's local Postgres. If a Jira site isn't available, this demo can't
run; there's no local substitute for it.

**Platform:** Windows uses PowerShell and `install.ps1`; Linux/macOS uses
Bash and `install.sh`. Codex prompts and Jira OAuth steps are the same on
both platforms.

## Purpose

Show the complete workflow in one place: a Skill orchestrates, Subagents
implement and test in isolated worktrees, MCP connects Jira, and Hooks record
and guard the workflow. This demo requires a real throwaway Jira ticket.

**How to read this file:** a "Do this" block per step, an "Expected"
block for what should appear, and a short "Why" where it's not obvious.
Complete every "Pre-work" step before the "Running the demo" section.

## Pre-work (do this before presenting)

### P1 — a Jira Cloud site

**Do this:** set up a Jira Cloud site (a free trial site is fine) with one
throwaway project and one small, concrete sample ticket — small enough
that BE-dev/UI-dev produce a handful of files, not a sprawling feature.

**Expected:** you can open the Jira site in a browser and see the sample
ticket.

### P2 — install the plugin

**Do this — Windows (PowerShell):** from this repo's root:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\demo-material\plugins\ticket-workflow\install.ps1
codex
```

**Do this — Linux/macOS (Bash):** from this repo's root:
```bash
bash demo-material/plugins/ticket-workflow/install.sh
codex                        # trust (if not already)
```
Inside that `codex` session:
```
/hooks
```
Approve the two new hooks.

**Expected:** the installer finishes without error; `/hooks` shows the two
new hooks approved.

### P3 — commit or stash what the installer touched

**Do this:** commit (or stash) the files the installer just added/modified
(`.agents/skills/`, `.codex/agents/`, `.codex/hooks/`, `.codex/config.toml`,
`.codex/hooks.json`, `.gitignore`) so the checkout is clean.

**Expected:** `git status` shows a clean working tree.

**Why:** the Skill's entry preconditions refuse to start a ticket on a
dirty tree — this isn't optional housekeeping, the demo won't start
without it.

### P3.5 — let Maven write to its shared cache

**Do this:** in `.codex/config.toml`'s `[sandbox_workspace_write]` table,
set `network_access = true` and add `writable_roots` pointing at your local
Maven repo. On Windows use `C:/Users/<name>/.m2/repository`; on Linux/macOS
use `/home/<name>/.m2/repository`.

**Expected:** `mvn test` inside a worktree can fetch missing dependencies
and write them to the shared cache without a per-run approval prompt, and
without needing to copy `.m2` into each worktree.

**Why:** `ticket-be-dev` runs the backend's own build/test commands
(`mvn test`) inside `.worktrees/<id>-be` — the worktree itself is inside
the sandbox's writable workspace, but Maven's local repository is not, and
without network access it can't fetch anything it doesn't already have
cached. Demo 9 deliberately leaves both settings restrictive to make its
own point; this is the flip it anticipates for "an unrelated reason" later
in the session.

### P4 — sanity-check the guard

**Do this:** see `demo-material/plugins/ticket-workflow/README.md`'s install section for
the exact commands.

**Expected:** the guard check passes (README's own success output).

### P5 — log in to Jira

**Do this (same command on both platforms):**
```bash
codex mcp login atlassian
```

**Expected:** OAuth flow completes in the browser and returns you to the
terminal successfully.

### P6 — self-check

**Do this:**
```bash
codex mcp list
```

**Expected:** `atlassian`, `Status: enabled`.

## Running the demo

### R1 — kick off the ticket

**Do this:** in `codex`, in this repo:
```
implement ticket <YOUR-TICKET-ID>
```

**Expected:** Codex starts working through the ticket workflow (skill →
subagents → MCP calls).

### R2 — narrate what's happening

**Do this:** as it runs, point out:
- the Jira comment it posts with the BE/UI interface design
- the two worktrees under `.worktrees/` and their parallel commits
- `tickets/<ID>/state.json`'s phase changing
- `tickets/<ID>/bugs.md`, if the tester finds anything
- `tickets/<ID>/audit.log` growing alongside `.codex/logs/audit.log` —
  `ticket_audit.py` (one of the plugin's own two hooks, from P2) extends
  Demo 8's `audit_log.py` pattern with the active ticket ID and phase, so
  a session that gets interrupted (next step) still leaves a durable
  trace of exactly where it was, independent of the transcript.

**Why:** each of these is a different mechanism from Demos 6–8 showing up
together in one real workflow — the Skill decides the steps, Subagents do
the isolated BE/UI/test work, MCP is the Jira connection, `state.json` is
what makes the whole thing resumable (next step), and the audit trail is
Demo 8's Hooks mechanism reused for this workflow's own bookkeeping.

### R3 — show resumability live

**Do this:**
1. Interrupt the session (`Ctrl+C`) mid-`fixing`.
2. Start a fresh `codex` session, say `implement ticket <YOUR-TICKET-ID>`
   again.

**Expected:** it resumes from `state.json` instead of starting over —
including **not** re-posting the interface-design Jira comment, which a
marker search finds already there.

### R4 — wrap-up evidence

**Do this:** at the end, check:
- the final Jira comment with the summary
- `git log --oneline` on the current branch

**Expected:** the Jira comment is visible on the ticket; `git log
--oneline` shows the `[<ID>][dev-be]`/`[dev-ui]`/`[fix-*]`-tagged merge
commits.

Ground rules: same as the other demos — everything here is aimed at a
throwaway Jira ticket and a local git branch; nothing production-facing is
touched.
