# Demo 6 — MCP: Extending Codex Capabilities

Covers deck slides 27–33. Prerequisite: `demo-material/00-setup.md` and
`01-overview.md` done (repo trusted, Postgres up, schema loaded).

What you're demonstrating: MCP is just another tool source Codex can pull
from — but one that runs as its own process, with its own trust boundary,
and its own cost to every single model call, whether you use it that turn
or not. The local examples use stdio; Demo 9 adds a remote Streamable HTTP
server so the two transport choices are visible in the same workshop.

**How to read each step:** a "Do this" block (what to type/run), an
"Expected" block (what you should see), and a short "Why" (the concept
it's proving). Run these in order — later steps build on earlier ones.

## Step 1 — See the server Codex already knows about

`.codex/config.toml` in this repo has:
```toml
[mcp_servers.translator_db]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-postgres", "postgresql://translator:translator@localhost:5432/translator"]
```

**Do this:** open Codex in the repo (`codex`) and run:
```
/mcp
```

**Expected:** `translator_db` listed as connected, exposing exactly
**one** tool: `query` ("Run a read-only SQL query"). That's the whole
surface area — this reference server deliberately does one thing. (It's
the archived `@modelcontextprotocol/server-postgres` package — fine for a
local demo, not actively maintained; say so if someone asks.)

You can confirm the same thing outside any session, no Codex prompt needed:
```bash
codex mcp list
codex mcp get translator_db
```

**Expected:**
```
translator_db, Status: enabled
command: npx, startup_timeout_sec / tool_timeout_sec from config.toml
```

**Why:** an MCP server isn't magic — it's one config block that Codex
connects to and asks "what tools do you have?" `/mcp` shows you exactly
what that negotiation produced.

> **By the way — `codex mcp add`:** Codex CLI also has a command for
> registering a server without hand-editing TOML. Concretely, before
> running anything, `~/.codex/config.toml` has no `mcp_servers` table at
> all; after:
> ```bash
> $ codex mcp add demo_file_writer -- node demo-material/mcp-servers/file-writer/index.js
> Added global MCP server 'demo_file_writer'.
> ```
> ```toml
> # appended to ~/.codex/config.toml
> [mcp_servers.demo_file_writer]
> command = "node"
> args = ["demo-material/mcp-servers/file-writer/index.js"]
> ```
> The name before `--` becomes the table name; everything after `--`
> splits into `command` (first word) and `args` (the rest, as a list). No
> `enabled` line gets written at all — it's just implicitly `true` — which
> is one reason this repo's entries write `enabled` explicitly instead.
>
> The key fact (verified — this is **not** documented behavior, it's from
> actually reading the output): that `~/` is fixed. `codex mcp add`/`codex
> mcp remove` always write to `$CODEX_HOME/config.toml`
> (`~/.codex/config.toml` if `CODEX_HOME` isn't set) — there is no
> `--project`/`--local` flag. So the server above would follow you into
> every other repo you open Codex in, not this one, and its relative
> `args` path would only resolve when Codex happens to start with this
> exact repo as its working directory — a global entry can't guarantee
> that.
>
> You *can* redirect where it writes by setting `CODEX_HOME` to this
> repo's own `.codex/` folder for that one command:
> ```bash
> CODEX_HOME="$(pwd)/.codex" codex mcp add demo_file_writer -- node demo-material/mcp-servers/file-writer/index.js
> ```
> **Do not run this against this repo's real `.codex/config.toml`,
> though** — verified by actually doing it and diffing the result: it
> doesn't append cleanly. It re-serializes the *entire* `[mcp_servers.*]`
> table it touches, silently dropping every comment inside that table
> (this repo's config has whole paragraphs explaining each server — all
> of that would be gone), dropping `enabled = true` (falls back to the
> implicit default instead), and rewriting `startup_timeout_sec = 15` as
> `startup_timeout_sec = 15.0`. Tables outside the one it edits are left
> alone, so the damage is scoped but real. That's why every server in
> this repo — `translator_db` and `demo_file_writer` both — is written
> directly into `.codex/config.toml` with a text editor (or the heredoc in
> `00-setup.md`), never through `codex mcp add`, `CODEX_HOME` trick or not.

## Step 2 — Execute a simple MCP tool call

**Do this:** prompt Codex:
> Using the `translator_db` MCP tool, run a read-only query that lists the
> `name` and `description` of every row in the `roles` table.

**Expected:** Codex calls the `query` tool (you'll see it in the
transcript as something like `mcp__translator_db__query` — MCP tools show
up alongside `Bash` and `apply_patch` as just another named tool, not a
special case), and comes back with the 5 real seeded roles (Developer,
Tech Lead, BA, PM, QA/Tester) in Vietnamese. First call may prompt for
approval — that's the per-tool `approval_mode` from `config.toml` (unset
here, so it falls back to the ambient `approval_policy`).

**Why:** nothing about *this* app changed. You added ~10 lines of TOML and
Codex gained a new capability — a live read path into the translator's own
database — with no code written.

### The two connection shapes

The `translator_db` and `demo_file_writer` entries use **stdio**: Codex
starts a program on the machine and exchanges JSON over its standard input
and output. Credentials for a local server are normally passed through its
environment. Demo 9's `atlassian` entry uses **Streamable HTTP** instead:
Codex connects to a URL owned by someone else and authenticates through
OAuth (`codex mcp login atlassian`) or a bearer-token environment variable.

The transport changes where the trust sits, not whether the tools become
available to the model. Both transports add their tools to the same flat
tool list. Use `/mcp` and `codex mcp list` to verify what actually loaded;
the presence of a config entry on disk is not evidence that its server is
connected.

## Step 3 — Context cost, made visible

Every model call includes the schema of every enabled tool, MCP or not —
that's the "context cost of MCP" line in the outline.

One honest note before you run this: `codex debug prompt-input` (Demo 1's
tool, `02-demo-harness.md`) renders the assembled *instructions*
(AGENTS.md, skills list, permissions text) — checked directly against a
real build of this kit, toggling `mcp_servers.translator_db.enabled`
produces **no difference** in that dump. Tool schemas (what actually
costs the tokens) are sent separately, as part of the turn's tools list,
not in this instructions dump — so don't present `prompt-input` as
showing the MCP cost.

What *is* real and checkable, in two parts:

**3a — the schema block itself.** In the TUI, `/mcp` (Step 1) shows you
the live tool and its JSON `inputSchema` — that block, however small
here, is what gets attached to every single turn from now on, whether or
not that turn calls it.

**3b — the on/off switch.**

**Do this:** set `enabled = false` under `[mcp_servers.translator_db]` in
`.codex/config.toml`, then:
```bash
codex mcp list
```

**Expected:** `Status` flips to `disabled`.

Set `enabled` back to `true` when done — later steps and demos need it on.

When a server exposes many tools, narrow the list with its
`enabled_tools = [...]` setting instead of paying the schema/context cost
for tools the workflow never uses. Keep a server configured with
`enabled = false` when it is only needed for one demo: the configuration
stays available, but the server does not start and its tools do not occupy
the prompt on every model call.

## Step 4 — MCP vs Codex's sandbox (the trust-boundary demo)

This is the part that surprises people: Codex's own sandbox does not wrap
an MCP server's process. That's not an inference from behavior — it's
visible in Codex's own source (`rmcp-client`'s stdio launcher spawns the
MCP server with a plain `Command::new(...)`, no sandbox, vs. the shell
tool's exec path, which always goes through a sandboxing wrapper).

Prove it with a **filesystem write**, not a network connection — see
`00-setup.md`'s "Known limitation" note for why: on native Windows, Codex's
"block network" enforcement is frequently a no-op (either nothing is
applied at all, or it's only an env-var hint that a tool opening a raw
socket, like `psql`, simply ignores — and even at its strongest enforcement
level, loopback connections to `localhost:5432` are explicitly exempted),
so a network-based version of this step can silently pass on every
enforcement level Windows actually has. A file write is checked by the
OS's own permission system on every platform Codex runs on — that's the
version to actually put in front of an audience.

4c below asks the shell to write a file and asks MCP to write a file too —
the same kind of operation, blocked or not, attempted through each of the
two paths. Comparing a shell write against an MCP *read* would be a
weaker demo than it looks: a `SELECT` succeeding under `sandbox_mode =
"read-only"` proves nothing by itself, since reads are what "read-only"
is supposed to allow anyway.

That rules out `translator_db` for the MCP side of this specific
comparison: its `query` tool wraps every call in `BEGIN TRANSACTION READ
ONLY` at the Postgres level (verified in its source — see Step 1), so an
`INSERT` through it fails the exact same way regardless of `sandbox_mode`
— there's no contrast to see, just a database error whose origin you'd
have to read carefully to appreciate. 4b builds a second, tiny MCP server
with one tool that actually writes a file, so 4c is a real write-vs-write
comparison: same kind of operation, one path blocked by Codex, the other
not — and this time the write really happens, visibly, which is a much
more convincing thing to put in front of an audience than a rejected
`INSERT`.

### 4a — prove it without needing a live Codex turn at all

`codex sandbox` runs one command under a given sandbox config directly —
no model, no auth needed, so this works even before anyone's logged in.

**Do this:** use whichever form matches where you're actually running
(mixing them up matters here — see the note below).

Inside WSL2, or on macOS/Linux:
```bash
codex sandbox -c 'sandbox_mode="read-only"' -- sh -c 'echo test > ./sandbox_write_test.txt'
```
On native Windows (PowerShell/cmd, not WSL2):
```powershell
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "echo test > sandbox_write_test.txt"
```

**Expected:** this fails — `Permission denied` (bash) or `Access is
denied.` (cmd) — no file created either way (confirmed on both: exit code
1, `sandbox_write_test.txt` never appears; `Remove-Item`/`rm` it if a
prior attempt did create one).

**Why:** `read-only` means exactly that; the shell tool's exec path always
goes through the OS-level sandbox wrapper, on every platform, unlike the
network case above.

> **Windows gotcha:** the Windows form must use `cmd.exe` (or a full path
> to `sh.exe`), not a bare `sh` — `codex sandbox` spawns the child
> directly via `CreateProcessAsUserW`, which (unlike a normal shell) does
> **not** search `PATH` for an unqualified name, so a bare `sh` fails with
> "the system cannot find the file specified" before the sandbox even
> gets a chance to allow or deny anything. `cmd.exe` always resolves
> because `C:\Windows\System32` is searched unconditionally.

### 4b — build the demo's own MCP server

Everything so far used someone else's MCP server (`npx`-installed,
someone else's code). This step builds a tiny one from scratch, with the
same SDK `translator_db` itself is built with (`@modelcontextprotocol/sdk`
— its source is public; Step 1's archived `server-postgres` uses the exact
same `Server` / `StdioServerTransport` / tool-handler shape below), so
"what is an MCP server, really" stops being an abstraction. It ends up
being the one thing this repo's `translator_db` structurally cannot be: a
server that can actually write a file, so 4c has something real to
compare against a blocked shell write.

The whole server, `demo-material/mcp-servers/file-writer/index.js`, is
about 60 lines. The part that matters:

```js
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name !== "write_file") {
    throw new Error(`Unknown tool: ${request.params.name}`);
  }
  const { name, content } = request.params.arguments ?? {};
  const safeName = basename(String(name ?? "")); // no "../" escapes
  writeFileSync(join(WRITE_DIR, safeName), String(content ?? ""), "utf8");
  return { content: [{ type: "text", text: `wrote ...` }], isError: false };
});
```

One tool, `write_file`, that writes into its own `writes/` folder next to
the script. No sandboxing code anywhere in this file — and there doesn't
need to be, because nothing Codex does wraps this process either way; the
point of 4c is to see that directly.

**Do this:**
```bash
cd demo-material/mcp-servers/file-writer
npm install
```
Then in `.codex/config.toml`, flip this repo's `demo_file_writer` entry
on:
```toml
[mcp_servers.demo_file_writer]
enabled = true
```
(Not `codex mcp add` — see Step 1's callout on why: this entry needs to
stay project-scoped, in this repo's own config.toml, not your global one.)
Restart `codex` in the repo, then:
```
/mcp
```

**Expected:** `npm install` finishes without error (adds
`@modelcontextprotocol/sdk` under `file-writer/node_modules/`, gitignored
— nothing to commit). `/mcp` now lists two servers: `translator_db` and
`demo_file_writer`, the latter exposing exactly one tool, `write_file`.

**Why:** this is the same negotiation Step 1 showed for `translator_db` —
Codex spawned `node demo-material/mcp-servers/file-writer/index.js`,
asked it "what tools do you have?", and got back the one tool this file
declares. There's nothing more privileged or more magical about a server
you wrote yourself than one you `npx`'d off npm — both are just a
`command`/`args` pair Codex spawns and talks JSON to.

**Do this after 4c:** set `enabled` back to `false` — it doesn't need to
stay running (and paying context rent, per Step 3) once 4c is done.

### 4c — see it with an actual session

**Do this:**
1. Temporarily tighten the sandbox. In `.codex/config.toml`:
   ```toml
   sandbox_mode = "read-only"
   ```
   Restart `codex` in the repo.
2. Ask Codex to write a file directly, via a normal shell command:
   > Run `echo test > ./sandbox_write_test.txt` in the shell.
3. Now ask Codex to attempt a **write of the same kind** as Step 2, through
   MCP instead of the shell:
   > Using the `demo_file_writer` MCP tool, write a file named
   > `mcp_write_test.txt` with the content `test`.

**Expected:**
- Step 2 above (direct shell write): blocked or needs explicit approval —
  same permission-denied reason as 4a. Check: `sandbox_write_test.txt`
  never appears.
- Step 3 above (MCP write): succeeds — check
  `demo-material/mcp-servers/file-writer/writes/mcp_write_test.txt`: it's
  there, with `test` inside, written while the session's own
  `sandbox_mode` was `"read-only"`. No Codex denial, no approval prompt
  for it either — `demo_file_writer` was spawned once, outside Codex's
  sandbox wrapper entirely, the moment it started; tightening the
  *shell's* sandbox afterward doesn't retroactively apply to a process
  that was never wrapped by it in the first place.

**Why it has to be a write, not a read:** a read succeeding here would
prove nothing — reads are what `sandbox_mode = "read-only"` is *supposed*
to allow, MCP or not. A write is exactly the kind of operation that mode
exists to block, so watching one actually land, unrestricted, through the
tool built in 4b — while the identical kind of write through the shell
gets denied — isolates the one thing being demonstrated: the shell tool's
exec path goes through Codex's sandbox wrapper, every time; an MCP
server's process never did, from the moment it was spawned, independent
of whatever `sandbox_mode` says.

**Do this next:** set `sandbox_mode` back to `"workspace-write"` when
you're done, and delete the `writes/` folder's contents if you want a
clean slate for a re-run.

**Why:** say the quiet part out loud here: an MCP server is a trusted
program with its own execution capabilities (outline §6), not a sandboxed
extension of Codex. Anyone who can edit `.codex/config.toml` — or anyone
who published the npm package in `command`/`args` — has exactly the
access that process has, sandbox settings notwithstanding. That's why
"more MCP servers" is a bigger trust surface, not just a bigger context
bill.
