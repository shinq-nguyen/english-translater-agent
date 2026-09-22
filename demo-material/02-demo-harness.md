# Demo 1 — The Harness

Covers slides 4–7. Prerequisite: `01-overview.md` is complete and the
repository is trusted.

## Purpose

Show that Codex proposes commands and tools, while the harness and operating
system decide whether they can run. The same decision path can be tested
without a model using `codex sandbox`.

## Step 1 — The harness enforces the sandbox

### Windows (PowerShell)

```powershell
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "echo test > sandbox_write_test.txt"
Test-Path .\sandbox_write_test.txt
Remove-Item .\sandbox_write_test.txt -ErrorAction SilentlyContinue
```

### Linux/macOS (Bash)

```bash
codex sandbox -c 'sandbox_mode="read-only"' -- sh -c 'echo test > sandbox_write_test.txt'
test -e sandbox_write_test.txt
rm -f sandbox_write_test.txt
```

Expected: the write is denied and the file does not exist. No model call is
involved; this isolates the enforcement layer.

## Step 2 — One request can create many model/tool rounds

Open Codex and ask:

> Find every class under `backend/src/main/java/com/example/translator/translation/`
> that implements `AiProviderClient`. For each one, tell me whether it
> creates a fresh `RestClient` per call or reuses one.

Expected: the transcript shows a search, file reads, and a final answer. Each
tool result creates another round with the model; it is not one model call.

Purpose: the conversation and tool results grow across the rounds. Demo 5
shows how that history is reduced.

## Step 3 — Inspect the fixed prompt input

Run on either platform:

```text
codex debug prompt-input
```

Expected: the output contains the skills catalog, permissions,
environment context, and the repository `AGENTS.md` instructions. This is
the fixed context sent on each model call. Tool schemas are sent separately.

## Step 4 — See progressive disclosure for a Skill

Start a **fresh** Codex session and ask:

> I need to add support for a new AI provider to the translation backend.
> Where do I start?

Expected: Codex uses `add-ai-provider` and follows its workflow. The live
transcript now contains the Skill's full body, whereas Step 3 showed only its
catalog description.

## Cleanup

Remove `sandbox_write_test.txt` if it exists. No project configuration is
changed by this demo.
