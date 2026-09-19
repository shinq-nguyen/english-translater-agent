# Demo Kit — overview

Source: `Codex-Full-Workshop.pdf` — "The Codex Harness," a two-part deck.
Repo used for every demo: `english-translater-agent` ("EN Translator for
IT" — a real Spring Boot + React app, not a toy repo), so each mechanism
gets demonstrated against code with actual secrets, a real database, and
real architectural seams, not a contrived example.

One continuous sequence, Part One first, then Part Two:

| Demo | Topic (deck slides) | Guide | Needs beyond `00-setup.md` Steps 0–2? |
|---|---|---|---|
| 1 | The harness (4–7) | `02-demo-harness.md` | No |
| 2 | Sandbox vs. approval (8–13) | `03-demo-sandbox-approval.md` | No |
| 3 | Configuration (14–16) | `04-demo-configuration.md` | No |
| 4 | AGENTS.md (17–20) | `05-demo-agents-md.md` | No |
| 5 | Context & compaction (21–23) | `06-demo-context-compaction.md` | No |
| 6 | MCP (27–33) | `07-demo-mcp.md` | Yes — Postgres up, `.codex/config.toml`'s MCP servers |
| 7 | Skills vs. subagents (34–42) | `08-demo-skills-vs-subagents.md` | Yes — the `add-ai-provider` skill, `secret_auditor` subagent |
| 8 | Exec policy & hooks (43–54) | `09-demo-exec-policy-hooks.md` | Yes — `.codex/rules/`, `.codex/hooks/` |
| 9 | Putting it together (55–65) | `10-demo-ticket-workflow.md` | Yes — all of the above, **plus its own Jira Cloud pre-work** |

Demos 1–5 are deliberately light: none of them touch Postgres, MCP, hooks,
skills, or subagents — they're about the runtime itself (sandbox,
approval, config precedence, AGENTS.md, context), so `codex` installed,
logged in, and this repo trusted is the whole prerequisite. Demos 6–9 are
where this repo's purpose-built `.codex/`/`.agents/` configuration
actually gets used, and each of those files says so at the top.

Every config file demos 6–9 reference already exists in this checkout —
nobody needs to type TOML/JSON live. Presenter and attendees both just run
Codex against this repo and watch the behavior; that's what "step by step,
so anyone can test it themselves" means here.

## Have you done `00-setup.md` yet?

That's the pre-work file. Its early steps are all any of Demos 1–5 need:
**Step 0** (install Codex CLI, log in), the `git clone` /
`cp .env.example .env` part of **Step 1**, and **Step 2** (trust the
project). Demos 6–9 need the rest of it too — generated local secrets,
Postgres up, and Steps 3–8 (writing the MCP server, skill, subagent,
hooks, and exec-policy rules this checkout already has).

It's meant to be done **before** the session, on your own machine, on your
own time, not read together as a group. If you haven't done at least
Steps 0–2, stop here and do that first.

**60-second recap, if you did it a few days ago and want to reconfirm:**

**Do this:**
```bash
cd english-translater-agent
codex doctor                # auth: not "no credentials"
```
Only needed for Demos 6–9:
```bash
docker compose ps           # translator-postgres should be running/healthy
codex doctor                # config.toml parse: ok; MCP servers: 2
codex mcp list               # translator_db, Status: enabled; demo_file_writer, Status: disabled
```

**Expected:**
```
codex doctor        → auth: <not "no credentials">
docker compose ps   → translator-postgres   ...   running (healthy)
codex doctor        → config.toml parse: ok, MCP servers: 2
codex mcp list       → translator_db      Status: enabled
                       demo_file_writer   Status: disabled
```

If any of those look wrong, go back to `00-setup.md`'s Step 9 self-check
table rather than debugging from scratch here.

## Demo 9 needs its own setup

`10-demo-ticket-workflow.md` is not covered by `00-setup.md` — it needs a
real Jira Cloud site, which can't be bundled the way the other demos'
local Postgres is. Read that file's own pre-work section before presenting
it; skip it entirely if a Jira site isn't available.

## What's already in the repo

```
AGENTS.md                                        — repo-level instructions (Demos 1, 4)
.codex/config.toml                               — sandbox/approval settings (Demos 2, 3), MCP servers + agents (Demo 6, 7)
.codex/rules/default.rules                       — exec-policy rules (Demo 8)
.codex/hooks.json                                — hook registration (Demo 8)
.codex/hooks/block_secrets.py                    — PreToolUse hook (Demo 8)
.codex/hooks/audit_log.py                        — audit hook, all 3 events (Demo 8)
.codex/hooks/scan_prompt_secrets.py              — UserPromptSubmit hook (Demo 8)
.codex/agents/secret-auditor.toml                — subagent definition (Demo 7)
.agents/skills/add-ai-provider/SKILL.md          — skill definition (Demo 7)
demo-material/mcp-servers/file-writer/           — hand-built MCP server (Demo 6, Step 4b)
demo-material/plugins/ticket-workflow/           — installable Skill+Subagents+MCP+Hooks plugin (Demo 9)
demo-material/                                   — these guides
```

## One thing worth re-checking at the top of any session

Project-level `.codex/config.toml` (MCP server, sandbox/approval settings)
and non-managed hooks (`.codex/hooks.json`) only take effect once this repo
is **trusted** in Codex — `00-setup.md` Step 2 already did this once, but if
anyone re-cloned the repo fresh for the session, or is on a different
machine than they ran the pre-work on, they'll hit the trust prompt again
the first time they open it. Demo 3 (`04-demo-configuration.md`) is built
entirely around this fact.

**Quick check:** if a demo "doesn't work," this is the first thing to
check — before assuming the config itself is wrong.

You're now ready for Demo 1 (`02-demo-harness.md`) onward, in order —
each guide is self-contained and runs in about 10–20 minutes, and Demos
1–5 read naturally straight through even in one sitting. Demos 6–9 are
usually presented as a separate, later session, once Postgres and the rest
of `00-setup.md` are in place.

## Ground rules for presenting these live

- Everything destructive is aimed at a **local, throwaway** Postgres
  container and generated dummy secrets, or at scratch files/repos outside
  this checkout — nobody is exposing anything real.
- Demos 2 and 6 deliberately flip `sandbox_mode` in `.codex/config.toml`
  for a few minutes at a time. Set it back to `workspace-write` when a
  step's "Do this next" says to — later demos assume the default is
  restored.
- Demo 8's network comparison assumes the baseline
  `[sandbox_workspace_write] network_access = false`. If Demo 9's Maven
  pre-work has already been completed, restore that baseline before
  presenting Demo 8; Demo 9 turns network access on deliberately and adds
  the Maven cache to `writable_roots`.
- If you want a clean Postgres slate between run-throughs of Demos 6–9:
  `docker compose down -v` wipes the DB volume — which is also exactly the
  command Demo 8 teaches exec-policy to forbid. Comment out that rule
  temporarily, or just `docker compose down -v && docker compose up -d
  postgres` and re-run `00-setup.md` Step 1's schema-loading command, if
  you need to reset outside the workshop.
