# Session 2 Demo Kit — overview

Repo used for all four demos: `english-translater-agent` ("EN Translator for
IT" — a real Spring Boot + React app, not a toy repo). Session 2 topics from
the course outline, in order:

| # | Topic | Guide | Has a hands-on demo? |
|---|-------|-------|----|
| 6 | MCP — Extending Codex Capabilities | `02-demo-mcp.md` | Yes |
| 7 | Skills vs Subagents | `03-demo-skills-vs-subagents.md` | Yes |
| 8 | Execution Governance — Exec Policy & Hooks | `04-demo-exec-policy-hooks.md` | Yes |
| 9 | Putting Everything Together | `05-demo-ticket-workflow.md` | Yes — a full Skill+Subagents+MCP+Hooks ticket workflow; needs its own Jira Cloud pre-work, see that file |

Every config file the demos reference already exists in this checkout —
nobody needs to type TOML/JSON live. Presenter and attendees both just run
Codex against this repo and watch the behavior; that's what "step by step,
so anyone can test it themselves" means here.

## Have you done `00-setup.md` yet?

That's the pre-work file — install Codex CLI, log in, install Docker, clone
this repo, generate local secrets, bring up Postgres, trust the project.
It's meant to be done **before** the session, on your own machine, on your
own time, not read together as a group. If you haven't, stop here and do
that first; everything below assumes it's done.

**60-second recap, if you did it a few days ago and want to reconfirm:**

**Do this:**
```bash
cd english-translater-agent
docker compose ps          # translator-postgres should be running/healthy
codex doctor                # auth: not "no credentials"; config.toml parse: ok; MCP servers: 2
codex mcp list               # translator_db, Status: enabled; demo_file_writer, Status: disabled
```

**Expected:**
```
docker compose ps   → translator-postgres   ...   running (healthy)
codex doctor        → auth: <not "no credentials">, config.toml parse: ok, MCP servers: 2
codex mcp list       → translator_db      Status: enabled
                       demo_file_writer   Status: disabled
```

If any of those look wrong, go back to `00-setup.md`'s Step 9 self-check
table rather than debugging from scratch here.

## Demo 4 needs its own setup

`05-demo-ticket-workflow.md` is not covered by `00-setup.md` — it needs a
real Jira Cloud site, which can't be bundled the way the other demos'
local Postgres is. Read that file's own pre-work section before presenting
it; skip it entirely if a Jira site isn't available.

## What's already in the repo

```
AGENTS.md                                        — repo-level instructions
.codex/config.toml                               — MCP server + agents + sandbox settings
.codex/rules/default.rules                       — exec-policy rules (Demo 3)
.codex/hooks.json                                — hook registration (Demo 3)
.codex/hooks/block_secrets.py                    — PreToolUse hook (Demo 3)
.codex/hooks/audit_log.py                        — audit hook, all 3 events (Demo 3)
.codex/hooks/scan_prompt_secrets.py              — UserPromptSubmit hook (Demo 3)
.codex/agents/secret-auditor.toml                — subagent definition (Demo 2)
.agents/skills/add-ai-provider/SKILL.md          — skill definition (Demo 2)
demo-material/mcp-servers/file-writer/           — hand-built MCP server (Demo 1, Step 4b)
demo-material/plugins/ticket-workflow/           — installable Skill+Subagents+MCP+Hooks plugin (Demo 4)
demo-material/                                   — these guides
```

## One thing worth re-checking at the top of the session

Project-level `.codex/config.toml` (MCP server, sandbox/approval settings)
and non-managed hooks (`.codex/hooks.json`) only take effect once this repo
is **trusted** in Codex — `00-setup.md` Step 2 already did this once, but if
anyone re-cloned the repo fresh for the session, or is on a different
machine than they ran the pre-work on, they'll hit the trust prompt again
the first time they open it.

**Quick check:** if a demo "doesn't work," this is the first thing to
check — before assuming the config itself is wrong.

You're now ready for any of `02-demo-mcp.md`, `03-demo-skills-vs-subagents.md`,
`04-demo-exec-policy-hooks.md`, `05-demo-ticket-workflow.md` — each is
self-contained and can run in ~15–20 minutes (Demo 4 only once its own
pre-work is done).

## Ground rules for presenting these live

- Everything destructive is aimed at a **local, throwaway** Postgres
  container and generated dummy secrets — nobody is exposing anything real.
- If you want a clean slate between run-throughs: `docker compose down -v`
  wipes the DB volume — which is also exactly the command Demo 3 teaches
  exec-policy to forbid. Comment out that rule temporarily, or just
  `docker compose down -v && docker compose up -d postgres` and re-run
  `00-setup.md` Step 1's schema-loading command, if you need to reset
  outside the workshop.
