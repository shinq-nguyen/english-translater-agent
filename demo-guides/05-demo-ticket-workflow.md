# Demo 4 — Putting Everything Together: a full Skill+Subagents+MCP+Hooks workflow

Covers outline §9. This is the session's synthesis demo: everything from
Demos 1–3 — a Skill deciding the steps, Subagents doing isolated BE/UI/test
work, MCP as the Jira connection, Hooks as the guardrail — running together
in one real workflow instead of one mechanism at a time.

Unlike `02`–`04`, this demo needs its own pre-work — a real Jira Cloud
site — since it exercises a real OAuth-based remote MCP server rather than
this repo's local Postgres. If a Jira site isn't available, this demo can't
run; there's no local substitute for it.

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

**Do this:** from this repo's root:
```bash
bash plugins/ticket-workflow/install.sh
codex                        # trust (if not already)
```
Inside that `codex` session:
```
/hooks
```
Approve the two new hooks.

**Expected:** `install.sh` finishes without error; `/hooks` shows the two
new hooks approved.

### P3 — commit or stash what the installer touched

**Do this:** commit (or stash) the files `install.sh` just added/modified
(`.agents/skills/`, `.codex/agents/`, `.codex/hooks/`, `.codex/config.toml`,
`.codex/hooks.json`, `.gitignore`) so the checkout is clean.

**Expected:** `git status` shows a clean working tree.

**Why:** the Skill's entry preconditions refuse to start a ticket on a
dirty tree — this isn't optional housekeeping, the demo won't start
without it.

### P4 — sanity-check the guard

**Do this:** see `plugins/ticket-workflow/README.md`'s install section for
the exact commands.

**Expected:** the guard check passes (README's own success output).

### P5 — log in to Jira

**Do this:**
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

**Why:** each of these is a different mechanism from Demos 1–3 showing up
together in one real workflow — the Skill decides the steps, Subagents do
the isolated BE/UI/test work, MCP is the Jira connection, and
`state.json` is what makes the whole thing resumable (next step).

### R3 — show resumability live

**Do this:**
1. Interrupt the session (`Ctrl+D`) mid-`fixing`.
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
