# Demo 2 — Sandbox vs. Approval

Covers deck slides 8–13. Prerequisite: `01-overview.md` done.

What you're demonstrating: `sandbox_mode` and `approval_policy` answer two
completely different questions — "what is Codex *allowed* to do" (a wall,
enforced by the OS) vs. "when does Codex *ask* me first" (a question, just
a terminal prompt). The deck's own framing: a command can be dangerous and
never asked about, and a harmless command can prompt every time. Neither
"it asked me" nor "it didn't ask" tells you what the sandbox would have
allowed.

## Step 1 — The three sandbox modes, one command each

**Do this:** run the same write attempt under all three modes, no live
session needed (`codex sandbox` skips the model entirely — see Demo 1's
(`02-demo-harness.md`) Step 1):
```bash
# read-only
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "echo test > sbx_test.txt"
ls sbx_test.txt 2>&1   # should error — no file

# workspace-write
codex sandbox -c 'sandbox_mode="workspace-write"' -- cmd.exe /c "echo test > sbx_test.txt"
ls sbx_test.txt 2>&1   # should exist now
rm -f sbx_test.txt

# danger-full-access
codex sandbox -c 'sandbox_mode="danger-full-access"' -- cmd.exe /c "echo test > sbx_test.txt"
ls sbx_test.txt 2>&1   # should exist
rm -f sbx_test.txt
```
On WSL2/macOS/Linux, swap the `cmd.exe /c "..."` tail for
`sh -c 'echo test > sbx_test.txt'` (see `00-setup.md`'s Step 3 note on why
native-Windows and POSIX forms aren't interchangeable here).

**Expected:** the write is blocked only under `read-only`; it succeeds
under both `workspace-write` and `danger-full-access`.

**Why:** three modes, one axis — what Codex may *change*.
`workspace-write` (this repo's actual default — check
`.codex/config.toml`) allows writes inside the working directory and any
`writable_roots`; `danger-full-access` means no sandbox at all. Reading is
never blocked in *any* of the three — proven next.

## Step 2 — The gap: read-only does not mean it cannot read

**Do this:**
```bash
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "type .env"
```
(WSL2/macOS/Linux: `sh -c 'cat .env'`.)

**Expected:** the command succeeds and prints `.env`'s contents (or, if
your `.env` is empty/missing locally, at minimum the command does **not**
fail with a permission error the way Step 1's write did — compare exit
codes if the file's empty).

**Why:** this is the deck's single most-surprising slide. The sandbox
controls *writes* and *network*, never reads, in any mode — `cat .env`
succeeds in `read-only` exactly as it would in `workspace-write`. A secret
you actually care about needs to live **outside** the folder Codex works
in; `sandbox_mode` was never a confidentiality boundary. (Demo 8,
`09-demo-exec-policy-hooks.md`, covers the one mechanism that *can* stop
this — a `PreToolUse` hook — but a hook is a check that can fail open, not
a wall like the sandbox.)

## Step 3 — Sandbox and approval are independent settings

**Do this:** in a live `codex` session in this repo, with the project
default (`sandbox_mode = "workspace-write"`, `approval_policy =
"on-request"`), ask it to do something that writes inside the repo, e.g.:
> Create a file `demo-material/scratch/step3.txt` containing the text
> "hello".

**Expected:** the write just happens — no approval prompt. Compare
against Step 1: the OS would have refused this same write under
`read-only`, prompt or not. Here, under `workspace-write`, it's silently
allowed — no prompt, because `on-request` only asks about things the
sandbox alone wouldn't already handle.

**Do this next:** ask it to touch a file *outside* the repo and outside
any `writable_roots` in `.codex/config.toml` — e.g. (adjust the path for
your OS):
> Create a file at `~/codex-demo-outside-test.txt` containing "hello".

**Expected:** this time you get an approval prompt (or, on `never`, a
silent refusal) — the write reaches outside what `workspace-write` covers
on its own, so `approval_policy` is what decides whether Codex gets to ask
you for an exception.

**Why:** two axes, not one. `read-only` + `never` runs everything
sandboxed, asks nothing — "the sandbox is already answering," as the deck
puts it. `workspace-write` + `on-request` (this repo's default) only
prompts for the *escalations* the sandbox alone can't grant — exactly what
Step 3 showed. Neither setting is a weaker or stronger version of the
other; they're answers to different questions.

## Step 4 — Check what's actually in effect, live

**Do this:** inside a `codex` session:
```
/status
```
then
```
/permissions
```

**Expected:** `/status` reports the sandbox mode and approval policy
currently in effect for *this* session — which may not match what's on
disk if you passed a `-c` flag or changed it mid-session with
`/permissions`. `/permissions` lets you change either one for the rest of
this session only (doesn't touch `config.toml`).

**Why:** the deck's habit to build: never conclude "it's configured"
because a file on disk says so — conclude it from `/status` in the
session you're actually in. Demo 3 (`04-demo-configuration.md`) is
entirely about why the file on disk and the setting actually in effect
diverge more often than you'd expect.

## Cleanup

Delete anything Step 3 created (`demo-material/scratch/step3.txt`, the
outside-repo test file) and confirm `.codex/config.toml` still has
`sandbox_mode = "workspace-write"` before moving on to another demo.
