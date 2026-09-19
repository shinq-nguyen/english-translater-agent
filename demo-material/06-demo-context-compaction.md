# Demo 5 — Context & Compaction

Covers deck slides 21–23. Prerequisite: `01-overview.md` done. This one
is a live-session walkthrough — `/compact`/`/clear` are TUI-only, there's
no way to script them from outside a real session, so every step below
runs interactively inside `codex`.

What you're demonstrating: context only grows during a session — nothing
shrinks it on its own — until either automatic compaction fires (around
90% of the model's context window, mid-task if it has to) or you trigger
`/compact`/`/clear` yourself. The three ways to reduce it
(`/compact`, `/clear`, a full restart) are not interchangeable, and the
gap between them is the thing that catches almost everyone at least once.

## Step 1 — Watch the fixed cost, before you've typed anything

**Do this:**
```bash
codex debug prompt-input
```
(Same command as Demo 1's, `02-demo-harness.md`, Step 3 — no model call,
no cost.)

**Expected:** the message list from Demos 1 and 4
(`02-demo-harness.md`/`05-demo-agents-md.md`) — skills catalog,
permissions, environment context, `AGENTS.md`. This is the **fixed**
block: everything here gets re-sent, unchanged, on every single call for
the rest of the session.

**Why:** the baseline to compare against for the rest of this demo.
Whatever grows from here on is conversation history, not this block.

## Step 2 — Do enough work that history visibly grows

**Do this:** open a real `codex` session in this repo and give it a
multi-step task, e.g. Demo 1's (`02-demo-harness.md`) Step 2:
> Find every class in `backend/src/main/java/.../translation/` that
> implements `AiProviderClient`, and for each one, read its file and tell
> me whether it builds a fresh `RestClient` per call or reuses one.

Let it finish. Scroll back through the transcript.

**Expected:** several tool calls and their outputs are now part of this
session's history — the search results, each file's contents,
intermediate reasoning. None of that goes away once the task's done; it's
still there for the *next* message you send, on top of everything from
Step 1.

**Why:** the deck's "budget that only goes one way" — every round of the
task in Step 2 above appended to history; nothing removed anything.
Left alone, a long enough session eventually crosses the model's context
window, and Codex fires automatic compaction on its own — possibly in the
middle of a later task, between tool calls, with no warning first. That's
the deck's explanation for a long session seeming to "forget" something
partway through: nothing broke, the history was summarised away by the
model, mid-task, at a moment you didn't choose.

## Step 3 — The gotcha: edit a file mid-session, then `/compact`

**Do this:** in the **same** session as Step 2 (don't restart), make a
small, obviously-visible edit to `AGENTS.md` — e.g. temporarily add a line:
```
## Demo marker
COMPACT_TEST_MARKER: added mid-session to test /compact
```
Now, still in the same session:
```
/compact
```
Once it finishes, ask:
> What's the "Demo marker" section in AGENTS.md say?

**Expected:** `/compact` runs (keeps a summary, stays in the same
session, costs one model call) — but the model answers as if the
`AGENTS.md` edit doesn't exist, or answers from a stale/summarised
recollection at best. It was never re-read.

**Why:** `/compact` asks the model to summarise the *existing* history —
it does not re-read `AGENTS.md`, `config.toml`, or restart MCP servers.
An edit made after the session started is simply not part of what gets
summarised or re-loaded.

## Step 4 — `/clear` picks the edit up; `/compact` never will

**Do this:** still in the same terminal, same repo, same `AGENTS.md` edit
still in place:
```
/clear
```
Then ask the same question again:
> What's the "Demo marker" section in AGENTS.md say?

**Expected:** now it answers correctly — `COMPACT_TEST_MARKER: added
mid-session to test /compact`.

**Why:** `/clear` throws away history and starts a fresh session **in the
same terminal** — no summary kept, but every config/instruction file gets
re-read from scratch, `AGENTS.md` included. A full restart (closing and
reopening `codex`) does the same, plus re-reads machine-wide
(`~/.codex/config.toml`) config and restarts MCP servers — relevant if
you'd also changed something in `.codex/config.toml`, not just
`AGENTS.md`.

| | keeps a summary | same session | re-reads `AGENTS.md`/`config.toml` | costs a model call |
|---|---|---|---|---|
| `/compact` | yes | yes | **no** | yes |
| `/clear` | no | no | yes | no |
| full restart | no | no | yes (+ restarts MCP servers) | no |

## Step 5 — Give restart its own moment, and see what it does that `/clear` doesn't

Steps 3–4 proved `/compact` skips the reload and `/clear` doesn't — but
`/clear` never actually needed a full restart to prove that; it stayed in
the same terminal. This step gives restart its own concrete test, and is
honest about the one thing it does that this file can't independently
verify without pulling Postgres into a demo that's meant to need nothing
beyond Codex itself.

**Do this:** with the same `## Demo marker` line from Step 3 still in
`AGENTS.md` (don't clean it up yet), close this session entirely —
`Ctrl+D`, or quit the terminal — then reopen it:
```bash
codex
```
Ask the same question again:
> What's the "Demo marker" section in AGENTS.md say?

**Expected:** answers correctly, same as `/clear` did in Step 4 —
`COMPACT_TEST_MARKER: added mid-session to test /compact`.

**Why:** this doesn't show restart doing anything `/clear` couldn't — per
the table above, both re-read `AGENTS.md`/`config.toml`, and this step
confirms that's true rather than just asserting it. What restart alone
does, per the deck, is also **restart the MCP server processes** —
`translator_db` and `demo_file_writer` from Demo 6
(`07-demo-mcp.md`). That part genuinely can't be shown here without
Postgres up, which would break this demo's "nothing beyond Codex itself"
status (`01-overview.md`'s table lists Demo 5 as needing nothing past
`00-setup.md` Steps 0–2) — if you want to see it, Demo 6 is where a live
MCP connection already exists to restart.

**Cleanup:** remove the `## Demo marker` section you added to
`AGENTS.md` before moving on — `git diff AGENTS.md` to confirm it's back
to the committed version, or `git checkout -- AGENTS.md`.

## Step 6 — Compact on your own terms, not the model's

**Do this (discussion, not a new command):** think back to Step 2 — you
don't get to choose *when* automatic compaction fires; it's tied to
context usage, and can land mid-task. `/compact`, run by hand, lets you
pick the moment instead — e.g. right after a big investigation finishes
and before starting unrelated work, so the summary that gets kept is a
clean checkpoint rather than a mid-task snapshot.

**Why:** this is the deck's actual advice, not just a mechanic to know
about — compacting at a checkpoint *you* choose produces a better summary
than one the model is forced to write in the middle of something. Combine
this with Demo 1's (`02-demo-harness.md`) Step 2 point about repeated
tool output cost, and Demo 8's (`09-demo-exec-policy-hooks.md`)
`PostToolUse` hook pattern if you want a durable log of a session that
outlives any compaction anyway.
