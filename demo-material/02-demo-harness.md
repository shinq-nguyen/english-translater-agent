# Demo 1 — The Harness

Covers deck slides 4–7. Prerequisite: `01-overview.md` done (Codex
installed, logged in, this repo trusted).

What you're demonstrating: Codex is not "an LLM with a terminal." The
model only ever *proposes* — a request, a tool call, a piece of text.
Something else — the harness — decides whether that request actually
executes, and it decides that by consulting a specific, inspectable stack
of state on every single call, not just at session start.

**How to read each step:** a "Do this" block, an "Expected" block, and a
short "Why." Run them in order.

## Step 1 — The model proposes, the harness decides

**Do this:** with `.codex/config.toml`'s `sandbox_mode` at its default
(`workspace-write`), tighten it for one command only, no config edit
needed:
```bash
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "echo test > sandbox_write_test.txt"
```

**Expected:** the write fails (`Access is denied.`, or `Permission
denied.` on WSL2/macOS/Linux using the `sh -c` form from
`00-setup.md`'s Step 3/`07-demo-mcp.md`'s Step 4a) — no
`sandbox_write_test.txt` appears. Confirm with `ls sandbox_write_test.txt`
(errors — file doesn't exist).

**Why:** nothing about the *model* changed between this command and one
that would have been allowed — there's no model call here at all, in
fact. `codex sandbox` runs one command through the exact same enforcement
path a live session's shell tool goes through, with no model in the loop,
which is the cleanest possible demonstration of the deck's core claim:
execution is decided by the harness/OS layer, downstream of whatever gets
proposed. In a live session the same rule applies to what the *model*
proposes — the model asking to run `echo test > out.txt` under
`sandbox_mode = "read-only"` gets refused by the OS for the identical
reason, whether or not it ever sees the refusal coming.

## Step 2 — One message, many calls to the model

**Do this:** open `codex` in the repo and give it a task that needs
several tool calls to answer, e.g.:
> Find every class in `backend/src/main/java/.../translation/` that
> implements `AiProviderClient`, and for each one, read its file and tell
> me whether it builds a fresh `RestClient` per call or reuses one.

**Expected:** the transcript shows multiple rounds — a search/list call,
then one read per implementation file found, then a final text answer —
all before you get control back. That's several separate calls to the
model (search results → next proposal → more results → next proposal
→ ... → final answer), not one.

**Why:** each of those rounds re-sends the *entire* conversation so far —
your original message, every tool result already returned, the whole
fixed block from Step 3 below — appended to, never replaced. A "simple"
question that needed four tool calls just paid for the fixed block five
times over (once per round), not once. This is the mechanical reason a
long agentic task gets slower and more expensive as it goes, independent
of how hard the underlying problem is — Demo 5 (`06-demo-context-compaction.md`)
picks up directly from this.

## Step 3 — See exactly what gets sent, every call

**Do this:**
```bash
codex debug prompt-input
```
(No login, no model call, no cost — it renders the message list the
*next* turn would send and stops.)

**Expected:** a JSON array of `developer`/`user` messages. In this repo,
in order, you'll see:
- A `<skills_instructions>` block — one line per skill: `name`,
  `description`, and a path token (`r0`/`r1`) resolved against a **skill
  roots** table underneath. Note what's *not* there: no step-by-step body
  for any skill, `add-ai-provider` included — just its one-line
  description, same as every other skill in the list.
- A `<permissions instructions>` block — spells out `sandbox_mode`
  (`workspace-write` here), the exact `writable_roots`, and whether
  network access is enabled, in plain English, not just as config keys.
- An `<environment_context>` block — `cwd`, `shell`, the resolved
  filesystem permission profile (read/write roots), current date/timezone.
- A message literally titled `# AGENTS.md instructions for <this path>`,
  wrapping this repo's root `AGENTS.md` verbatim inside an
  `<INSTRUCTIONS>` tag.

**Why:** this is the deck's "what the harness sends every single call"
slide, made concrete — everything above is the **fixed** cost, re-sent
and paid for on every model call this session makes, whether that call
uses any of it or not. Note the one thing this command does *not* show:
tool JSON schemas (`shell`, `apply_patch`, and any MCP tool) are sent as
part of the turn's actual tool list, not in this instructions dump — so
the real fixed cost per call is higher than what's printed here. That's
the deck's own caveat, not a gap in this demo.

## Step 4 — Prove a skill's body really does arrive late

This repo already has one skill, `add-ai-provider`
(`.agents/skills/add-ai-provider/SKILL.md`) — Step 3 showed you its
one-line catalog entry costs almost nothing. Now watch the full body show
up only once it actually fires.

**Do this:** in a **fresh** `codex` session in this repo, ask something
that matches the skill's description closely:
> I need to add support for a new AI provider to the translation backend.
> Where do I start?

Let it respond (it should follow the skill's numbered steps — reading
`AiProviderClient.java` and both existing implementations first). Then,
**without starting a new session**, run:
```
codex debug prompt-input
```
from a second terminal in the same repo — or, simpler, just scroll the
live transcript.

**Expected:** the session's message history now contains a `developer` (or
tool-result-adjacent) message with the skill's **full body** — the
numbered steps, the warning about `ApiKeyAttributeConverter`, all of it —
not just the one-line description from Step 3.

**Why:** this is "progressive disclosure," the deck's name for it. The
catalog entry (Step 3) is what's paid on every call, always, whether the
skill is ever used. The full `SKILL.md` body is a one-time cost paid only
on the turn where it actually gets picked, and never again after that
(it stays in history from then on, same as any other tool result — no new
cost for having it "loaded," just the cost of it now being part of a
growing conversation, per Step 2).

## Cleanup

Nothing in this file edits `.codex/config.toml` or `AGENTS.md` — Step 1's
`codex sandbox` run doesn't touch the live session's settings at all. If
Step 1's command somehow did create `sandbox_write_test.txt` (it
shouldn't), delete it before moving on.
