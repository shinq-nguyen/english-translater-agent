# Demo 6 — MCP

Covers slides 27–33. Run this demo from the trusted repository. Before
starting, make sure Postgres is running and the schema is loaded as described
in `00-setup.md`. Use the Windows or Linux/macOS command variant below.

## Purpose

Show that MCP adds external tools to Codex. An MCP server is a separate
process with its own permissions and trust boundary. Its tool schemas are
also part of the tools available to each model call.

## Step 1 — Check the configured server

Run:

```powershell
codex mcp list
codex mcp get translator_db
```

Then open Codex and run:

```text
/mcp
```

Expected:

- `translator_db` is enabled and connected.
- It exposes one `query` tool.
- The command is `npx`, as configured in `.codex/config.toml`.

If it is not connected, check `docker compose ps` and return to
`00-setup.md` before continuing.

## Step 2 — Call the MCP tool

Ask Codex:

> Using the `translator_db` MCP tool, run a read-only query that lists the
> `name` and `description` columns from the `roles` table.

Expected: Codex asks for approval before the MCP call (MCP tool calls are
approval-gated by default in current Codex builds) — approve it. The
transcript then shows a call to the MCP `query` tool and returns the seeded
roles (five on a fresh database). The important observation is that MCP appears in the same
tool list as shell and file tools.

## Step 3 — Observe the server/context switch

1. In `.codex/config.toml`, change only this entry:

   ```toml
   [mcp_servers.translator_db]
   enabled = false
   ```

2. Run:

   ```powershell
   codex mcp list
   ```

Expected: `translator_db` is `disabled`. Its process does not start and its
tools are not available to a new Codex session. Restore `enabled = true`
before continuing.

Purpose: an MCP server adds capability and also adds tool-schema/context
cost. Keep servers disabled when a workflow does not need them.

## Step 4 — Compare the shell sandbox with an MCP process

This step uses the small local `demo_file_writer` server. Its one tool
creates a new file in the repository root — the same folder the shell is
about to be denied. It never overwrites an existing file.

### 4a. Prepare the server

Run once on Windows (PowerShell):

```powershell
Set-Location .\demo-material\mcp-servers\file-writer
npm install
Set-Location <path-to-english_translater>
```

Run once on Linux/macOS (Bash):

```bash
cd demo-material/mcp-servers/file-writer
npm install
cd <path-to-english_translater>
```

In `.codex/config.toml`, set:

```toml
[mcp_servers.demo_file_writer]
enabled = true
```

Restart Codex and run `/mcp`.

Expected: both `translator_db` and `demo_file_writer` are connected;
`demo_file_writer` exposes one `write_file` tool.

### 4b. Compare two writes

1. Temporarily set the two root settings in `.codex/config.toml` to:

   ```toml
   sandbox_mode = "read-only"
   approval_policy = "never"
   ```

   `approval_policy = "never"` removes every approval prompt, so nothing can
   be "approved through". `demo_file_writer` is already configured with
   `default_tools_approval_mode = "approve"`, which is how a team typically
   trusts an MCP server it uses every day. The only protection left in play
   is the sandbox.

2. Restart Codex.
3. Ask Codex to run this normal shell command:

   > Run `echo test > sandbox_write_test.txt` in the shell.

4. Ask Codex:

   > Using `demo_file_writer`, write `sandbox_write_test.txt` with the
   > content `test`.

Expected:

- The shell write is denied ("Access to the path ... is denied") with no
  prompt, and `sandbox_write_test.txt` does not exist.
- The MCP write succeeds with no prompt. `sandbox_write_test.txt` now exists
  in the repository root — the exact file, in the exact folder, that the
  read-only sandbox just refused the shell.

Same session, same target file, opposite results. This demonstrates that the
Codex shell sandbox does not wrap the separately launched MCP server
process: the server runs with your full user permissions and could have
written anywhere you can. The approval prompt is the only Codex-side gate on
an MCP tool, and it disappears as soon as the server is pre-approved. Treat
every MCP server as a trusted local program with its own access.

## Cleanup

Restore the project config:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[mcp_servers.demo_file_writer]
enabled = false
```

Restart Codex, then remove the test file if it exists.

Windows (PowerShell):

```powershell
Remove-Item .\sandbox_write_test.txt -ErrorAction SilentlyContinue
```

Linux/macOS (Bash):

```bash
rm -f sandbox_write_test.txt
```
