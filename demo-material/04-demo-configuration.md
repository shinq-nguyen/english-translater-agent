# Demo 3 — Configuration

Covers deck slides 14–16. Prerequisite: `01-overview.md` done, this repo
trusted in Codex.

What you're demonstrating: six places can hold the same setting, and only
one of them wins per key. Highest to lowest:

| # | Layer | Where | Wins over |
|---|---|---|---|
| 1 | `requirements.toml` | `/etc/codex/` (org policy) | everything, even `-c` |
| 2 | `-c`/`--config` flags | the command line | everything below |
| 3 | `config.toml` | `<repo>/.codex/` — **only if the repo is trusted** | your personal config, defaults |
| 4 | `<name>.config.toml` | `~/.codex/` — activated with `--profile` | your personal config, defaults |
| 5 | `config.toml` | `~/.codex/` (your normal settings) | machine-wide config, defaults |
| 6 | `config.toml` | `/etc/codex/` (machine-wide — **low** priority) | only the built-in defaults |
| — | built-in defaults | shipped with Codex | nothing |

This file gives every rung its own "who actually wins" moment, in order.
Rungs 3 and 2 are already fully hands-on. Rung 4 (profile) gets a real,
live test. Rungs 1 and 6 are explained rather than hand-built — see why
under each.

## Step 1 — Prove the project config is the one actually in effect

Your personal `~/.codex/config.toml` almost certainly has no
`sandbox_mode`, `approval_policy`, or `mcp_servers` in it at all — check:

**Do this:**
```bash
# Windows: type "$USERPROFILE\.codex\config.toml"
cat ~/.codex/config.toml
```

**Expected:** no `sandbox_mode`, `approval_policy`, or `[mcp_servers.*]`
keys anywhere in it (it typically only has things like `model`,
`approvals_reviewer`, `[tui]`, and a `[projects.'<path>']` trust table).

**Do this next:**
```bash
codex doctor
```
Look at the **Configuration** section.

**Expected:**
```
✓ config       loaded
    ...
    MCP servers              2
✓ mcp          2 server (2 stdio) · 1 disabled
✓ sandbox      restricted fs + enabled network · approval OnRequest
    approval policy          OnRequest
```

**Why:** none of `MCP servers: 2`, `network sandbox: enabled`, or
`approval policy: OnRequest` come from your global config — Step 1 just
showed it doesn't define any of them. They can only be coming from
`<repo>/.codex/config.toml` (rung 3), which does (`sandbox_mode =
"workspace-write"`, `approval_policy = "on-request"`,
`[mcp_servers.translator_db]`, `[mcp_servers.demo_file_writer]`). This is
the precedence ladder's rung 3, made concrete: the repo's config is what
actually won, silently, over whatever your personal defaults (rung 5)
would otherwise have been.

## Step 2 — A `-c` flag beats the repo's config

**Do this:**
```bash
codex doctor -c approval_policy='"never"'
```

**Expected:**
```
approval policy          Never
```
— flipped from `OnRequest` (Step 1) to `Never`, for this one invocation
only; `.codex/config.toml` on disk is untouched.

**Why:** `-c`/`--config` (rung 2) sits one rung **above**
`<repo>/.codex/config.toml` (rung 3) — it wins regardless of what the repo
or your personal config say, which is exactly why it's the tool Demos 1
and 2 (`02-demo-harness.md`, `03-demo-sandbox-approval.md`) use throughout
to test one setting in isolation without editing any file.

## Step 3 — The profile layer: real, but outranked by a trusted repo

A **profile** is not a section inside `config.toml` — verified directly
against this machine's real Codex install, `codex --help` says exactly
this:
```
-p, --profile <CONFIG_PROFILE_V2>
        Layer $CODEX_HOME/<name>.config.toml on top of the base user config
```
A profile is its own **file**: `~/.codex/<name>.config.toml` (or
`$CODEX_HOME/<name>.config.toml` if you've set that env var), activated
per-invocation with `-p`/`--profile <name>`. It sits at rung 4 — above
your personal `config.toml` (rung 5), but **below** a trusted repo's own
`.codex/config.toml` (rung 3). That last part is the counter-intuitive bit
this step proves: an explicit `--profile` flag on the command line does
**not** act like a `-c` override. It loses to this repo's own settings.

**Do this:** create a profile that tries to tighten the sandbox:
```bash
# Windows: notepad "$USERPROFILE\.codex\demo-profile.config.toml"
cat > ~/.codex/demo-profile.config.toml <<'EOF'
sandbox_mode = "read-only"
EOF
```
Now, **in this repo** (`english-translater-agent`, which has its own
`sandbox_mode = "workspace-write"` in `.codex/config.toml`):
```bash
codex --profile demo-profile debug prompt-input | grep -o 'sandbox_mode. is .[a-z-]*'
```

**Expected:** `sandbox_mode` is `workspace-write` — **unchanged**. The
profile's `read-only` never took effect here.

**Do this next:** prove the profile isn't simply broken — run the exact
same profile somewhere this repo's config can't reach. Pick (or make) a
folder that's **trusted** but has no `.codex/config.toml` of its own —
e.g. any other project you've already opened Codex in and accepted the
trust prompt for, or a fresh folder you trust now for this test:
```bash
mkdir -p /tmp/codex-profile-demo && cd /tmp/codex-profile-demo
codex   # accept the trust prompt this time — "1. Trust and continue"
# exit codex (Ctrl+D), then:
codex --profile demo-profile debug prompt-input | grep -o 'sandbox_mode. is .[a-z-]*'
```

**Expected:** `sandbox_mode` is `read-only` — the profile **did** take
effect, flipping this trusted-but-configless folder away from its own
default (`workspace-write`, per Demo 2's "which one you get by default").

**Why:** both runs used the identical `~/.codex/demo-profile.config.toml`.
The only variable was whether the folder had its own `.codex/config.toml`
(rung 3). When it did, rung 3 won. When it didn't, rung 4 (the profile)
was free to act — confirming profiles are real and functional, just
outranked by the one thing this whole repo's demo kit revolves around: a
trusted repo's own configuration.

**Cleanup:**
```bash
rm ~/.codex/demo-profile.config.toml
rm -rf /tmp/codex-profile-demo
```
(Windows without WSL2: delete `%USERPROFILE%\.codex\demo-profile.config.toml`
and the equivalent temp folder with `Remove-Item -Recurse -Force`.) Also
remove the `/tmp/codex-profile-demo` entry from your own
`~/.codex/config.toml`'s `[projects.*]` trust table if you don't want to
keep that scratch folder trusted going forward.

## Rung 1 — `requirements.toml`: the org-policy layer (explained, not built)

**What it is:** `/etc/codex/requirements.toml` — a file an organization's
admin controls, not an individual session. It's the only rung that beats
even a `-c` flag, by design: it exists so an org can enforce a guardrail
(e.g. "never allow `danger-full-access`") that no developer, script, or CI
job invocation can talk their way around with a flag.

**Why this file isn't hand-built here:** it's admin/root-owned by
convention — writing to `/etc/codex/` needs root on Linux/macOS, and
Windows has no `/etc` at all (this deck's examples are written
Unix-path-first; there's no confirmed Windows equivalent path surfaced by
`codex --help` or `codex doctor` on this machine). Asking workshop
attendees to fabricate an org-policy file on their own laptop would also
misrepresent what this layer is for — it's fleet-managed, not
personal-machine config.

**Do this (the one live, checkable trace that this layer is real):**
```bash
codex doctor | grep "configuration scope"
```

**Expected:**
```
configuration scope      invocation config, including cloud-managed policy
```

**Why:** `codex doctor` explicitly checks for and reports on a
cloud-/org-managed policy layer as part of the *same* resolution pipeline
that produced everything in Steps 1–3 — it's just empty on a personal dev
machine (`managed filesystem source: none`, if you look a few lines below
this one). If your organization ever rolls one out, it slots in above
even the `-c` flags this whole demo kit relies on for isolated testing.

## Rung 6 — the machine-wide `/etc/codex/config.toml`: low priority despite the path

**The one genuinely counter-intuitive row in the whole ladder:**
`/etc/codex/config.toml` — a machine-wide default, in the same
system-sounding location as rung 1's `requirements.toml` — ranks **below**
your own personal `~/.codex/config.toml` (rung 5), not above it. A
system administrator's machine-wide baseline is meant to be a *fallback*
you can freely override for yourself, not a policy (that's what
`requirements.toml`, rung 1, is for). Same reasoning as rung 1 for why
this isn't hand-built in the demo: no confirmed Windows path, and root
access is needed even on Linux/macOS to test it for real. Worth stating
out loud in a live session, since "machine-wide" reads as "should win,"
and here it's the second-weakest rung on the entire ladder — only the
built-in defaults rank lower.

## Step 4 — Untrusted means not loaded at all, not "loaded but weaker"

**Do this:** pick (or create) a folder Codex has never opened before —
e.g. a fresh `mkdir /tmp/codex-untrusted-demo && cd` into it, or ask
someone in the room for a folder they haven't opened Codex in yet. Copy
this repo's `.codex/config.toml` into it:
```bash
mkdir -p /tmp/codex-untrusted-demo/.codex
cp .codex/config.toml /tmp/codex-untrusted-demo/.codex/
cd /tmp/codex-untrusted-demo
codex
```

**Expected:** Codex shows the trust prompt (`Trust this folder?`). Choose
**"2. Quit"** or otherwise decline. Then:
```bash
codex doctor
```

**Expected:** `MCP servers: 0` (or whatever your personal global config
has, not 2), `approval policy` back to whatever your personal default is
— the exact same `config.toml` content as this repo's, sitting right
there on disk, produces **none** of the same effective settings, because
the folder was never trusted.

**Why:** this is the deck's sharpest point on configuration — a repo's
`.codex/config.toml` isn't "loaded but sandboxed" when untrusted, it's not
loaded **at all**. `git clone` alone was never enough to make a cloned
repo's settings (or hooks) take effect; only accepting the trust prompt
does. `01-overview.md`'s "one thing worth re-checking" section calls out
the same thing for the same reason: it's the single most common cause of
"the repo's config doesn't seem to be working."

**Cleanup:** `rm -rf /tmp/codex-untrusted-demo` when done (adjust path on
Windows: `Remove-Item -Recurse -Force` on the equivalent temp folder).

## Step 5 — Check the winner live, never by reading a file

**Do this:** back in this repo, inside a `codex` session:
```
/status
```
```
/debug-config
```

**Expected:** `/status` shows the sandbox/approval settings actually in
effect right now for this session. `/debug-config` goes further — it
shows **which config layer** won for a given key and why (e.g. "from
project config.toml" vs. "from CLI override" vs. "built-in default").

**Why:** the habit the deck asks you to build, restated from Demo 2
(`03-demo-sandbox-approval.md`): never conclude a setting is active
because a file on disk says so. Six configuration layers can define the
same key; only `/status`/`/debug-config`, run in the actual session
you're in, tell you which one actually won.

## Summary — every rung, and how this file covers it

| Rung | Layer | This file | Where |
|---|---|---|---|
| 1 | `requirements.toml` (org) | Explained + one live check (`codex doctor`) | "Rung 1" section |
| 2 | `-c` flags | **Live** — beats rung 3 | Step 2 |
| 3 | `<repo>/.codex/config.toml` | **Live** — beats rung 5, needs trust | Steps 1, 4 |
| 4 | `<profile>.config.toml` (`--profile`) | **Live** — beats rung 5, loses to rung 3 | Step 3 |
| 5 | `~/.codex/config.toml` (personal) | **Live** — the baseline every other step compares against | Step 1 |
| 6 | `/etc/codex/config.toml` (machine-wide) | Explained only | "Rung 6" section |
| — | built-in defaults | Implicit — what's left once nothing else applies | throughout |
