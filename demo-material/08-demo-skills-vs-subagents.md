# Demo 7 — Skills vs Subagents

Covers deck slides 34–42. Prerequisite: `demo-material/00-setup.md` and
`01-overview.md` done.

The point of this demo is NOT "look, Codex can do these two cool things."
It's that Skills and Subagents solve *different* problems — reusable
know-how vs. context isolation — and mixing them up leads to the wrong
tool for the job. AGENTS.md is the third mechanism in the same family;
it's already in play the whole workshop (this repo's root `AGENTS.md`),
so this demo focuses on telling Skills and Subagents apart.

**How to read each step:** a "Do this" block, an "Expected" block, and a
short "Why." Part A and Part B are independent — run either first.

## Part A — Skills: reusable, triggered workflow

`.agents/skills/add-ai-provider/SKILL.md` encodes how *this specific repo*
wants a new AI provider added (which interface to implement, where the
registry lives, "reuse the existing encryption path, don't invent a new
one"). It only costs context when it's actually relevant — Codex loads just
the `name` + `description` frontmatter for every skill up front, and only
pulls in the full body once it picks this one (outline: "progressive
disclosure").

The frontmatter needs only `name` and `description`. There is no separate
`trigger` field: trigger phrases belong in the description, because that is
the text Codex matches against a task. `/skills` shows the catalog, while
`$add-ai-provider` explicitly selects this skill when the presenter wants
to remove matching uncertainty from the demo.

### A1 — see what Codex knows about

**Do this:**
```
/skills
```

**Expected:** `add-ai-provider` is listed with just its one-line
description — not its full contents.

**Why:** confirms progressive disclosure is working before you rely on it
in the next step.

### A2 — trigger it implicitly

**Do this:** don't name the skill, just describe the task:
> I want to add Google Gemini as a new AI provider option in this app,
> using its native API (not the OpenAI-compatible path).

**Expected:** Codex indicates it's using the `add-ai-provider` skill
before it starts, and follows the skill's steps in order: reads
`AiProviderClient` + the two existing implementations first, adds
`GEMINI` to `AiProviderType`, creates `GeminiProviderClient` as a
`@Component`, reuses `ApiKeyAttributeConverter` rather than inventing new
encryption, adds a test next to the existing provider-client tests.

**Why:** this is what "model-matched" triggering means — the skill fires
because the task description matches it, not because anyone typed its
name.

### A3 — trigger it explicitly, to contrast

**Do this:**
```
$add-ai-provider
```
(or whatever your Codex build's explicit-invocation syntax is — check
`/skills` help)

**Expected:** the outcome should be the same as A2 either way; only *how*
it got selected differs.

**Why:** this is what "Skills" are for per the outline: specialized,
reusable knowledge/workflow, loaded when relevant, not per-conversation
improvised.

## Part B — Subagents: context isolation for a broad investigation

`.codex/agents/secret-auditor.toml` defines `secret_auditor`: an investigator
whose job is to trace every place `APP_JWT_SECRET`, `AI_MODEL_ENCRYPTION_KEY`,
and stored AI-model API keys get touched across the backend. That's a
*broad*, multi-file question — exactly the shape of task the outline says
subagents are for, not because it's slower or faster, but because of what
ends up in whose context.

One thing to flag as you introduce it: the file's `developer_instructions`
tell it to be read-only, but — verified against Codex's own source
(`core/src/agent/role.rs`) — a role file's `sandbox_mode` is silently
dropped rather than applied; only `developer_instructions`, `model`, and a
handful of other fields actually reach the spawned agent. So `secret_auditor`
is read-only **by instruction, not by sandbox enforcement** — it inherits
whatever sandbox the parent session is using. It's the clearest example in
this whole kit of something that *looks* like a Control (it names a security
property, "read-only") but is actually only an Instruction — the kind of
distinction worth calling out every time you add a subagent.

The same inheritance applies to the parent's MCP servers. A role cannot
make its own `sandbox_mode`, `approval_policy`, or `mcp_servers` stricter by
putting those keys in its TOML; those keys parse but are ignored. The
supported narrowing mechanism is disable-only features, for example
`[features]` with `shell_tool = false`. Set the parent session's permissions
before delegating when a child must start from a tighter boundary. Also
avoid presenting `agents.max_depth` as an enforcement guarantee: the V2
implementation marks it ignored, so inspect the effective behavior instead
of trusting that setting in a config file.

### B1 — Run 1: no delegation (do it "by hand" in the main thread)

**Do this:**
1. Start a fresh Codex session in the repo (`codex`, fresh — not
   continuing from Part A).
2. Prompt:
   > Investigate how APP_JWT_SECRET, AI_MODEL_ENCRYPTION_KEY, and saved AI
   > model API keys are generated, stored, encrypted, and could possibly be
   > exposed (logs, API responses, exceptions), across this whole repo.
   > Read whatever files you need yourself and give me a report.
3. Let it finish, then look at the transcript itself (no special command
   needed — it's the plainest, most reliable evidence): count how many
   distinct files got opened/quoted along the way (config YAMLs,
   `ApiKeyAttributeConverter.java`, the security/auth package,
   `docker-compose.yml`, etc.).

**Expected:** several distinct files' contents visible directly in the
transcript.

**Why:** all of that is now sitting in the main thread's history, whether
or not the final report needed to quote all of it — and it stays there,
taking up budget, for the rest of the session.

### B2 — Run 2: delegate to the subagent

**Do this:**
1. Start another fresh Codex session.
2. Prompt:
   > Delegate an investigation of how this repo generates, stores,
   > encrypts, and might expose APP_JWT_SECRET, AI_MODEL_ENCRYPTION_KEY,
   > and saved AI model API keys to the `secret_auditor` subagent. Just
   > give me its summary.
3. Let it finish, then look at the parent thread's transcript the same way.

**Expected:** the transcript shows the delegation call and
`secret_auditor`'s final compact table, but **not** the full text of every
file the subagent opened to produce that table — that reading happened in
the subagent's own, separate context, which is discarded once it reports
back.

### B3 — compare

**Do this:** compare the two transcripts side by side.

**Expected:** Run 1's main-thread history has every file it read; Run 2's
has only the delegation + the summary. Same underlying investigation, very
different footprint left in the parent.

**Why:** that's "context isolation is the main value, not automatically
speed" (outline §7) made concrete: Run 2 probably isn't faster (spinning
up a subagent has its own overhead), but the parent's context stays clean
enough to keep working on something else afterward, while Run 1's
doesn't.

## Triggering mechanisms — side by side

| Mechanism | How it's invoked | What the parent context gets |
|---|---|---|
| Custom prompt file | Explicit `/prompts:<name>` invocation | The prompt content only when called; plain language does not discover the file |
| AGENTS.md | Always loaded, no invocation | Its full text, every turn (this repo's `AGENTS.md` has been in context since session start) |
| Skill | Model-matched (implicit) or `$name` (explicit) | Just the description until selected, then the full `SKILL.md` body |
| Subagent | Explicit ask, or model decides parallelization helps | Only the subagent's final report — its working context is thrown away |

## When each is the wrong tool

- Don't write a Skill for something that's really just "always relevant" —
  that belongs in `AGENTS.md`.
- Don't reach for a Subagent for a one-file lookup — the spin-up overhead
  and lost shared context isn't worth it for something the main thread could
  just read in one step. Save it for genuinely broad, "read a lot to answer
  one question" work like the secret audit above.

Skills shape the workflow and knowledge available to the current agent;
Subagents move the reading or implementation into another context. Neither
one is a security boundary: the child inherits the parent's sandbox and MCP
access, and instructions in either mechanism can still be ignored.
