# Demo Kit — overview

This workshop uses the real `english-translater-agent` repository to show
Codex's runtime, configuration, MCP, Skills, Subagents, and Hooks.

Every demo below supports both tracks:

- **Windows:** native Codex from PowerShell. Docker Desktop is required for
  the database demos.
- **Linux/macOS:** Codex from Bash. Docker and the local Postgres container
  are required for the database demos.

Complete `00-setup.md` first.

## Demo order

| Demo | Topic | Guide | Extra setup |
|---|---|---|---|
| 1 | Harness | `02-demo-harness.md` | None |
| 2 | Sandbox vs. approval | `03-demo-sandbox-approval.md` | None |
| 3 | Configuration | `04-demo-configuration.md` | None |
| 4 | `AGENTS.md` | `05-demo-agents-md.md` | None |
| 5 | Context and compaction | `06-demo-context-compaction.md` | None |
| 6 | MCP | `07-demo-mcp.md` | Postgres and MCP setup |
| 7 | Skills vs. Subagents | `08-demo-skills-vs-subagents.md` | Skill and subagent files |
| 8 | Exec policy and Hooks | `09-demo-exec-policy-hooks.md` | Rules and hooks |
| 9 | Full ticket workflow | `10-demo-ticket-workflow.md` | Jira Cloud and plugin |

Demos 1–5 use only Codex and the local repository. Demos 6–9 use the
prepared project configuration under `.codex/`, `.agents/`, and
`demo-material/`.

## Quick check before a session

### Windows (PowerShell)

```powershell
Set-Location <path-to-english_translater>
codex doctor
docker compose ps
codex mcp list
```

### Linux/macOS (Bash)

```bash
cd <path-to-english_translater>
codex doctor
docker compose ps
codex mcp list
```

Expected: authentication is available, the project is trusted, Postgres is
healthy for Demos 6–9, and `translator_db` is enabled. The file-writer server
should remain disabled until Demo 6 enables it.

## If a demo does not work

Check these in order:

1. You are in the repository root.
2. The project was trusted in Codex.
3. `codex doctor` reports no config error.
4. The required service is running (`docker compose ps` for Postgres).
5. A previous demo restored `.codex/config.toml` to its original values.

Never print `.env` or paste its contents into a transcript. The demo files
use harmless test data when they need to demonstrate file reads.

## Repository pieces used by the demos

```text
AGENTS.md                                  baseline instructions
.codex/config.toml                         sandbox, MCP, and agent settings
.codex/rules/default.rules                 exec-policy rules
.codex/hooks.json                          hook registration
.codex/hooks/                              secret and audit hooks
.codex/agents/secret-auditor.toml          Subagent definition
.agents/skills/add-ai-provider/SKILL.md    Skill definition
demo-material/mcp-servers/file-writer/    local MCP server
demo-material/plugins/ticket-workflow/     Demo 9 plugin
```

Restore temporary settings and remove scratch files at the end of each
demo. Do not run destructive database cleanup commands unless you explicitly
want to reset the local demo database.
