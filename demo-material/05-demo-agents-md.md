# Demo 4 — AGENTS.md

Covers deck slides 17–20. Prerequisite: `01-overview.md` done. This demo
builds a **separate scratch git repo** outside `english-translater-agent`
so nobody has to touch this repo's real `AGENTS.md` — full steps below.

What you're demonstrating: AGENTS.md files are *collected*, not chosen —
every file from the repo root down to your current folder gets glued
together and sent as one block, every call — and that block has a single,
shared size budget, spent from the root down. A big root file can silently
delete your most specific rules before Codex ever sees them, with no
error and nothing in the transcript.

## Step 1 — See this repo's own AGENTS.md reach the model, verbatim

**Do this:** in `english-translater-agent`, with nothing else set up:
```bash
codex debug prompt-input
```
Find the message whose text starts with `# AGENTS.md instructions for`.

**Expected:** the full text of this repo's root `AGENTS.md` — headings,
the "Where things live" list, the `.env` warning — wrapped verbatim inside
an `<INSTRUCTIONS>` tag, as one `user`-role message.

**Why:** this is not a summary or an excerpt — it's the file's exact
content, sent as-is. Whatever tone or precision you write into
`AGENTS.md`, that's exactly what the model reads, unedited.

## Step 2 — Build a throwaway repo to see concatenation happen

**Do this:**
```bash
mkdir -p /tmp/agents-md-demo/sub
cd /tmp/agents-md-demo
git init -q .
echo "ROOT_MARKER: this is the root AGENTS.md" > AGENTS.md
echo "SUB_MARKER: this is sub/AGENTS.md, closer to where you're working" > sub/AGENTS.md
git add -A && git -c user.email=a@b.c -c user.name=demo commit -q -m init
cd sub
codex debug prompt-input | grep -A3 "AGENTS.md instructions"
```

**Expected:** one combined block, containing **both** `ROOT_MARKER` *and*
`SUB_MARKER` — `ROOT_MARKER` first, `SUB_MARKER` after it — even though
you're running from `sub/`, two directories away from the root file.

**Why:** confirms the deck's claim directly — there's no "nearest file
wins." Every `AGENTS.md` on the path from the repo root down to your `cwd`
is joined together, root first, and handed to the model as one message. A
deeper file **adds** to the ones above it; it doesn't replace them.

**Worth noting, not in the deck:** this concatenation only kicked in once
`/tmp/agents-md-demo` was an actual git repo (`git init` above) — the same
two files in a plain, non-git directory only produce the closest one
(`sub/AGENTS.md`), with no root file included at all. Codex appears to use
the git repo boundary to decide how far up to walk — worth keeping in
mind if a demo "isn't finding" a root AGENTS.md and the folder in question
turns out not to be a git repo yet.

## Step 3 — The one exception: `AGENTS.override.md` replaces, not adds

Everything in Step 2 was about concatenation — files *add* to each other.
There's exactly one named exception the deck calls out: an
`AGENTS.override.md` sitting next to a folder's own `AGENTS.md` replaces
that folder's `AGENTS.md` in the assembled block, instead of both being
glued together. It's scoped to its own folder only — it doesn't touch
`AGENTS.md` files anywhere else on the path.

**Do this**, still in `/tmp/agents-md-demo` (from Step 2, `sub/AGENTS.md`
still holds `SUB_MARKER`):
```bash
cd /tmp/agents-md-demo
echo "OVERRIDE_MARKER: this is sub/AGENTS.override.md" > sub/AGENTS.override.md
git add -A && git -c user.email=a@b.c -c user.name=demo commit -q -m "add override"
cd sub
codex debug prompt-input > /tmp/pi.json
grep -c "ROOT_MARKER" /tmp/pi.json
grep -c "SUB_MARKER" /tmp/pi.json
grep -c "OVERRIDE_MARKER" /tmp/pi.json
```

**Expected:** `ROOT_MARKER` still found (**1**) — the parent folder's
`AGENTS.md` is untouched by an override two directories below it.
`SUB_MARKER` is now **gone** (**0**) — `sub/AGENTS.md` itself was never
sent. `OVERRIDE_MARKER` is found (**1**) in its place. Look at the
message header too: it still just reads `# AGENTS.md instructions for
.../sub` — nothing in the label tells you it's actually
`AGENTS.override.md`'s content underneath, not `AGENTS.md`'s.

**Why:** this is the one place in the whole collection model where a file
*replaces* instead of adding — scoped strictly to its own folder, not
inherited or applied to any other folder on the path (Step 2's
`ROOT_MARKER` proves that: an override two levels down never touched it).
Worth knowing before you go looking for why an `AGENTS.md` you just wrote
in a folder doesn't seem to be taking effect — check for a sibling
`AGENTS.override.md` first, since nothing in the transcript announces
that substitution either, the same "silent" theme as Step 4's budget cut.

## Step 4 — Blow the budget, and watch a file vanish with no error

**Do this**, still in `/tmp/agents-md-demo` — first remove Step 3's
override so it doesn't confound this test (its whole point was replacing
`sub/AGENTS.md`, which would make `SUB_MARKER` look "gone" for the wrong
reason here):
```bash
rm /tmp/agents-md-demo/sub/AGENTS.override.md
cd /tmp/agents-md-demo
git add -A && git -c user.email=a@b.c -c user.name=demo commit -q -m "remove override, back to plain AGENTS.md"
{ echo "ROOT_MARKER: this is the root AGENTS.md"; head -c 40000 /dev/zero | tr '\0' 'x'; echo; } > AGENTS.md
wc -c AGENTS.md          # ~40 KB — comfortably over the ~32 KiB budget
git add -A && git -c user.email=a@b.c -c user.name=demo commit -q -m "oversized root"
cd sub
codex debug prompt-input > /tmp/pi.json
grep -c "ROOT_MARKER" /tmp/pi.json
grep -c "SUB_MARKER" /tmp/pi.json
```

**Expected:** `ROOT_MARKER` still found (**1**) — it's near the *top* of
the now-40 KB root file. `SUB_MARKER` — the file physically closest to
where you're working, and the one most likely to hold your most specific,
most recently-written rule — is **gone** (**0**). No error anywhere in
that output. No warning in the transcript. `sub/AGENTS.md` still exists on
disk, completely untouched; it simply never made it into this call.

**Why:** the budget (~32 KiB, per the deck) is spent from the repo root
**down** — a large file at the root can exhaust it before Codex ever
reaches a file closer to your actual work. The file that goes missing is
the one you're most likely to have written most recently, for the area
you're currently touching — and there is no signal anywhere that it
happened. The only way to catch this is to print the assembled block
yourself, exactly like Step 2/3 just did.

**Cleanup:** `rm -rf /tmp/agents-md-demo` when done. (On native Windows
without WSL2, use an equivalent temp path and `Remove-Item -Recurse
-Force`; `head -c N /dev/zero` won't exist under plain PowerShell — swap
in `fsutil file createnew` or a short `for` loop to pad the file instead.)

## Step 5 — AGENTS.md is advice, not a boundary

**Do this:** back in `english-translater-agent`, re-read the line already
in this repo's `AGENTS.md`:
> "Treat it as sensitive: never cat/print it, never put its contents in a
> commit, PR description, or chat."

Now recall Demo 2's (`03-demo-sandbox-approval.md`) Step 2: `cat .env`
**succeeds** under every `sandbox_mode`, including `read-only` — the
sandbox never blocks reads, in any mode.

**Expected (discussion, not a command):** the *only* thing standing
between the model and printing `.env`'s contents right now is that one
sentence in `AGENTS.md` — text the model is very likely to follow, but
text competing for attention with everything else in the fixed block
(Demo 1's, `02-demo-harness.md`, Step 3), not an enforced rule. Nothing
about `sandbox_mode` or `approval_policy` makes that instruction real.

**Why:** the deck's test to apply to any rule you're about to write in
AGENTS.md: "would I be upset if the model ignored this once?" If yes, it
doesn't belong in AGENTS.md alone — it belongs in an exec-policy rule or a
`PreToolUse` hook (Demo 8, `09-demo-exec-policy-hooks.md`, builds exactly
that: `.codex/hooks/block_secrets.py` in this repo denies any
command that references a real `.env` file, regardless of what
`AGENTS.md` says). Write instructions to make the model *useful*. Write
config to make a boundary *real*.
