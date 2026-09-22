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

Expected: the transcript shows a call to the MCP `query` tool and returns the
five seeded roles. The important observation is that MCP appears in the same
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

This step uses the small local `demo_file_writer` server. It writes only to
`demo-material\mcp-servers\file-writer\writes`.

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

1. Temporarily set the root setting in `.codex/config.toml` to:

   ```toml
   sandbox_mode = "read-only"
   ```

2. Restart Codex.
3. Ask Codex to run this normal shell command:

   > Run `echo test > sandbox_write_test.txt` in the shell.

4. Ask Codex:

   > Using `demo_file_writer`, write `mcp_write_test.txt` with the content
   > `test`.

Expected:

- The shell write is denied and `sandbox_write_test.txt` does not exist.
- The MCP write succeeds. The file exists at
  `demo-material\mcp-servers\file-writer\writes\mcp_write_test.txt`.

This demonstrates that the Codex shell sandbox does not automatically wrap
the separately launched MCP server process. Treat every MCP server as a
trusted local program with its own access.

## Cleanup

Restore the project config:

```toml
sandbox_mode = "workspace-write"

[mcp_servers.demo_file_writer]
enabled = false
```

Restart Codex, then remove the test files if they exist.

Windows (PowerShell):

```powershell
Remove-Item .\sandbox_write_test.txt -ErrorAction SilentlyContinue
Remove-Item .\demo-material\mcp-servers\file-writer\writes\mcp_write_test.txt -ErrorAction SilentlyContinue
```

Linux/macOS (Bash):

```bash
rm -f sandbox_write_test.txt
rm -f demo-material/mcp-servers/file-writer/writes/mcp_write_test.txt
```
