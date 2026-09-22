# Demo 5 — Context and compaction

Covers slides 21–23. Run this demo in one Codex session. No database or MCP
setup is required.

## Purpose

Show the practical difference between:

- `/compact`: keep a summary and continue the session;
- `/clear`: discard the conversation and reload the current project context;
- a full restart: start fresh and restart external processes as well.

The key point is that `/compact` summarizes the existing conversation. It
does not re-read files that changed after the session started.

## Step 1 — Start a session and create history

Open Codex from the repository and ask:

> Find the classes under `backend/src/main/java/com/example/translator/translation/`
> that implement `AiProviderClient`. List each class and say whether it
> creates a new `RestClient` for each call.

Expected: Codex performs several searches/reads. Those tool results remain
part of the session history after the answer is complete.

## Step 2 — Change AGENTS.md after the session starts

Keep the Codex session open. In a second terminal, from the repository,
append this temporary marker.

Windows (PowerShell):

```powershell
Add-Content .\AGENTS.md "`r`n## Demo marker`r`nCOMPACT_TEST_MARKER: added after the session started"
```

Linux/macOS (Bash):

```bash
printf '\n## Demo marker\nCOMPACT_TEST_MARKER: added after the session started\n' >> AGENTS.md
```

Do not use a real secret or change any other instruction.

## Step 3 — `/compact` keeps history but does not reload the file

In the original Codex session, run:

```text
/compact
```

Then ask:

> What does the `Demo marker` section in AGENTS.md say?

Expected: the answer does not reliably contain the new marker. `/compact`
summarized the conversation that already existed; the edit was made later
and was not re-read.

## Step 4 — `/clear` starts with current files

In the same terminal, run:

```text
/clear
```

Ask the same question again.

Expected: the answer contains
`COMPACT_TEST_MARKER: added after the session started`. `/clear` discards
the old conversation and loads the current project instructions again.

## Step 5 — Understand when to restart

A full restart also reloads `AGENTS.md` and project configuration. It
additionally restarts MCP server processes, so use it after changing MCP
configuration or when an external process must be recreated. `/clear` is
enough for a simple instruction-file change.

## Cleanup

Remove the temporary `Demo marker` heading and marker line from `AGENTS.md`.
Then check with either platform:

```powershell
git diff -- .\AGENTS.md
```

Expected: no diff remains.
