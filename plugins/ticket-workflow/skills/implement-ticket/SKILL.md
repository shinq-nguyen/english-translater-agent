---
name: implement-ticket
description: Use when asked to implement, continue, or resume a Jira ticket end-to-end (investigate, spec, implement BE+UI in parallel, test against acceptance criteria, fix-retest loop, report back on the ticket). Trigger phrases include "implement ticket <ID>" and "continue ticket <ID>".
---

# Implement a Jira ticket end-to-end

You orchestrate the full lifecycle for one ticket ID. You never write
application code or touch git yourself for the dev phases — you delegate to
subagents and do only the bookkeeping (state.json, bugs.md, Jira posts,
worktree/merge git commands) described below. Full design rationale:
`docs/specs/2026-09-13-ticket-workflow-plugin-design.md` in the workshop
repo, if present — this file is the operational summary.

`workflow_root` = the repo root you're running in. All relative paths below
are relative to `workflow_root`, never to any subagent's own working
directory.

`state_io.py write` replaces the entire state.json file, not just the
fields mentioned in a given step — so every write below must first `read`
the current state, change only the field(s) that step calls out, and write
the complete merged object back, or earlier fields (like `ticket_id`,
`base_branch`, `bug_track_file`) get silently dropped.

**Autonomy within this workflow:** running builds/tests, downloading
dependencies, creating worktrees, committing, and merging locally are all
already in scope for this skill — do them without stopping to ask each
time. Only stop and ask the user when a step below explicitly says to
(a business decision like `wont-fix`, a merge conflict, a dirty/unexpected
checkout, `retry_count` exhausted) — not for actions this file has already
authorized.

## 0. Resume check and reconciliation — always first, every invocation

```bash
python .codex/hooks/state_io.py read "tickets/<TICKET-ID>/state.json"
```

If it returns `null`: this is a fresh ticket, start at step 1.

If it returns a state object: **do not act on it directly.** Reconcile each
piece against ground truth first:
- For each `jira.*_comment_id` that is `null`: before posting that comment
  type, search the ticket's existing comments (via the Jira MCP tools) for
  the hidden marker `<!-- ticket-workflow:<TICKET-ID>:interface -->` (or
  `:summary` for the final comment). Found → record that comment's real ID
  via `state_io.py write` without posting again. Not found → you'll post it
  when you reach that step.
- For each worktree branch in `state.json.worktrees`: compare its actual
  tip (`git rev-parse <branch>`) against what `dev_round` recorded for that
  side. If it differs, treat the branch tip as ground truth.
- For each side recorded `merged`: verify with
  `git merge-base --is-ancestor <recorded-commit> <base_branch>` — exit 0
  confirms it, anything else means treat it as not yet merged.

Then resume from `state.json.phase`, skipping any subagent dispatch whose
round-scoped status is already `committed`/`merged`/`no_bugs_assigned`, and
never re-posting a Jira comment a marker search already found.

Also re-write `.codex/tickets_active` with the ticket ID before resuming
work — do not assume it's still there, since a prior session may have been
interrupted before step 6 cleared it, or it may be missing for any other
reason.

## 1. Entry preconditions

Confirm the workflow_root checkout is on a named branch (not detached HEAD)
and clean (`git status --porcelain` empty). If either fails, stop and
report the prerequisite to resolve — do not proceed. Initialize a new
`state.json` with `ticket_id: <TICKET-ID>`, the current branch name as
`base_branch`, `bug_track_file: "tickets/<TICKET-ID>/bugs.md"`,
`retry_count: 0`, `max_retries: 5`, and `phase: "investigating"`. Every
later `verify_step.py` check reads `ticket_id` and `bug_track_file` from
this file and they are never written again after this step — set them here
or the `dev_round`/`done` gates fail closed on every real ticket. As part of
this same step, write the ticket ID to `.codex/tickets_active`
(`echo "<TICKET-ID>" > .codex/tickets_active`) — this is the pointer file
`guard_ticket_commit.py` and `ticket_audit.py` read to know a ticket
workflow is active; without it, both hooks stay permanently inert.

## 2. Investigating

1. Read the ticket via the Jira MCP tools (discover the available tool
   names live via the MCP tool list — don't assume specific identifiers).
2. Delegate to `ticket-investigator`, passing the full ticket text.
3. On its return: `python .codex/hooks/state_io.py write "tickets/<TICKET-ID>/state.json"`
   with `spec_file` set and `phase: "spec_ready"`.
4. Run `python .codex/hooks/verify_step.py . <TICKET-ID> spec_ready` — non-zero exit
   means stop and report, do not proceed.
5. Post the investigator's returned interface-design section as a Jira
   comment on the ticket, with the hidden marker
   `<!-- ticket-workflow:<TICKET-ID>:interface -->` embedded in the body.
   Record the returned comment ID as `jira.interface_comment_id`.

## 3. Dev round (initial) — `dev_in_progress`

1. Create the two worktrees (first time only):
   ```bash
   git worktree add .worktrees/<TICKET-ID>-be -b ticket/<TICKET-ID>-be
   git worktree add .worktrees/<TICKET-ID>-ui -b ticket/<TICKET-ID>-ui
   ```
   Record their absolute paths and branch names under `state.json.worktrees`.
2. Write `dev_round` with `kind: "initial"`, `round_id: 0`, both sides
   `status: "pending"`, before dispatching anyone.
3. Dispatch `ticket-be-dev` and `ticket-ui-dev` **in true parallel**, each
   given: `workflow_root` (absolute), its `worktree_root` (absolute), the
   ticket ID, `round_id` (from `dev_round.round_id`, `0` for this initial
   round), round kind `initial`, and the spec file's absolute path.
4. As each reports back (independently — do not wait for both): record its
   completion SHA under `dev_round.<side>.commit`, set `status: "committed"`,
   then from a clean `workflow_root` checkout on `base_branch`:
   ```bash
   git merge --no-ff <completion-sha>
   ```
   On success, record the resulting merge commit SHA under
   `dev_round.<side>.merge_commit` and set `status: "merged"`. On conflict:
   `git merge --abort`, set `phase: "dev_conflict"`, stop and report to the
   user — never guess a resolution.
5. Run `python .codex/hooks/verify_step.py . <TICKET-ID> dev_round` after both
   sides are `merged` — non-zero exit means stop and report.
6. Set `phase: "testing"`.

## 4. Testing

1. Confirm `workflow_root` checkout is clean and on `base_branch`.
2. Delegate to `ticket-tester`, passing the ticket text, the current
   `base_branch` HEAD SHA, and — on a retest round only — the list of
   currently-`open`/`fixed-pending-retest` bug IDs with descriptions.
3. On its return, write `test_report` (`commit`, `result`,
   `acceptance_criteria_checked`, `clean_before`, `clean_after`,
   `tested_at`).
4. From its findings list: create new `bugs.md` rows (`status: "open"`) for
   anything not already tracked; for previously-open IDs it says no longer
   reproduce, set `status: "verified-fixed"`. `bugs.md` is a markdown table
   and must use exactly this header (column order is a contract with
   `verify_step.py`'s `parse_bugs_table`):
   ```
   | ID | Area | Severity | Description | Status | Found in commit | Fixed in commit |
   |----|------|----------|--------------|--------|------------------|------------------|
   ```
5. If `test_report.result == "passed"` and every `bugs.md` row is
   `verified-fixed`/`wont-fix`: go to step 6 (done). Otherwise: set
   `phase: "fixing"`, go to step 5 below.

## 5. Fixing round

If resuming and `state.json.dev_round.kind == "fix"` with its sides not yet
all `merged`/`no_bugs_assigned`, resume that existing round instead of
starting a new one: skip step 3's `retry_count` increment and new
`dev_round` creation, and skip re-running step 4's reset/resync for any
side already at `sync_status: "ready"`. Otherwise, proceed with steps 1-7
below to start a fresh fixing round — only if
`state.json.retry_count < max_retries` (default 5), otherwise stop, report
the unresolved bugs, and ask the user how to proceed.

1. Confirm no dev subagent from a previous round is still running, and
   `workflow_root` is clean, on `base_branch`, at `test_report.commit`.
2. Confirm both worktrees are clean and each old tip is an ancestor of
   `test_report.commit`. If not, stop for reconciliation — never stash,
   clean, or discard uncommitted work in a worktree.
3. Increment `retry_count`. Write a new `dev_round` (`kind: "fix"`,
   `round_id` incremented, `synced_from_commit: test_report.commit`), each
   side's `pre_sync_commit` = its current tip, `sync_status: "pending"`,
   `bug_ids` = the open bugs assigned to that area (a side with none gets
   `status: "no_bugs_assigned"`, `bug_ids: []`, and is never dispatched).
4. For each side with assigned bugs:
   ```bash
   git -C .worktrees/<TICKET-ID>-be reset --hard <synced_from_commit>
   git -C .worktrees/<TICKET-ID>-ui reset --hard <synced_from_commit>
   ```
   then checkpoint that side's `sync_status: "ready"`.
5. Dispatch only the sides with assigned bugs, in parallel, each given its
   `round_id` (from `dev_round.round_id`) plus its specific bug IDs and
   descriptions from `bugs.md` (not the full spec).
6. As each reports back: same merge/verify sequence as step 3.4-3.5 above,
   using `[fix-be]`/`[fix-ui]`-tagged commits. Update `bugs.md`: rows for
   addressed bug IDs move to `status: "fixed-pending-retest"` (never
   straight to `verified-fixed`).
7. Set `phase: "testing"`, go back to step 4 (Testing).

If the user ever needs to mark a bug `wont-fix`: stop and ask explicitly —
this is never automatic, and the row records it as user-approved.

## 6. Done

1. Run `python .codex/hooks/verify_step.py . <TICKET-ID> done` — non-zero exit
   means stop and report, the gate isn't actually satisfied yet.
2. Write a human-readable summary of what was implemented and how it was
   verified.
3. Search existing Jira comments for the `:summary` marker (see step 0);
   if absent, post the summary with marker
   `<!-- ticket-workflow:<TICKET-ID>:summary -->` and record the returned
   comment ID as `jira.summary_comment_id`.
4. Remove worktrees whose tips are clean and confirmed integrated into
   `base_branch` (never force-remove a dirty or unmerged one):
   ```bash
   git worktree remove .worktrees/<TICKET-ID>-be
   git worktree remove .worktrees/<TICKET-ID>-ui
   ```
5. Set `phase: "summarized"`. Clear the active-ticket pointer file
   (`rm -f .codex/tickets_active`). Report the summary to the user. Done.
