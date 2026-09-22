# Demo 4 — AGENTS.md

Covers slides 17–20. It uses a throwaway git repository. The real
repository `AGENTS.md` is not modified. Use the Windows or Linux/macOS setup
below.

## Purpose

Show three properties of `AGENTS.md`:

- instructions are collected from the repository root to the current folder;
- `AGENTS.override.md` replaces the instruction file in its own folder;
- a large file near the root can silently exhaust the shared 32 KiB budget
  before Codex ever reaches a smaller, more specific file;
- instructions are guidance for the model, not an enforcement boundary.

## Step 1 — See the real repository instructions

From `english_translater`, run:

```powershell
codex debug prompt-input > (Join-Path $env:TEMP "codex-prompt.json")
Select-String -Path (Join-Path $env:TEMP "codex-prompt.json") -Pattern "AGENTS.md instructions"
```

Expected: the output contains the root `AGENTS.md` text inside the assembled
instructions. It is sent as content; it is not a permission rule.

## Step 2 — Root and nested files are combined

Create a small git repository:

### Windows (PowerShell)

```powershell
$demoRoot = Join-Path $env:TEMP "agents-md-demo"
New-Item -ItemType Directory -Force (Join-Path $demoRoot "sub") | Out-Null
Set-Location $demoRoot
git init -q
Set-Content .\AGENTS.md "ROOT_MARKER: root instructions"
Set-Content .\sub\AGENTS.md "SUB_MARKER: sub instructions"
git add -A
git -c user.email=demo@example.com -c user.name=demo commit -q -m init
Set-Location .\sub
codex debug prompt-input > (Join-Path $env:TEMP "agents-prompt.json")
Select-String -Path (Join-Path $env:TEMP "agents-prompt.json") -Pattern "ROOT_MARKER|SUB_MARKER"
```

### Linux/macOS (Bash)

```bash
demoRoot="${TMPDIR:-/tmp}/agents-md-demo"
mkdir -p "$demoRoot/sub"
cd "$demoRoot"
git init -q
printf '%s\n' 'ROOT_MARKER: root instructions' > AGENTS.md
printf '%s\n' 'SUB_MARKER: sub instructions' > sub/AGENTS.md
git add -A
git -c user.email=demo@example.com -c user.name=demo commit -q -m init
cd sub
codex debug prompt-input > "${TMPDIR:-/tmp}/agents-prompt.json"
grep -E 'ROOT_MARKER|SUB_MARKER' "${TMPDIR:-/tmp}/agents-prompt.json"
```

Expected: both markers appear, with `ROOT_MARKER` before `SUB_MARKER`.
The nested file adds to the root file; it does not replace it.

## Step 3 — An override replaces the local file

From the same `sub` folder:

Both platforms run the same check. Use `Set-Content` on Windows and
`printf` on Linux/macOS:

Windows:

```powershell
Set-Content .\AGENTS.override.md "OVERRIDE_MARKER: replacement instructions"
codex debug prompt-input > (Join-Path $env:TEMP "agents-prompt.json")
Select-String -Path (Join-Path $env:TEMP "agents-prompt.json") -Pattern "ROOT_MARKER|SUB_MARKER|OVERRIDE_MARKER"
```

Linux/macOS:

```bash
printf '%s\n' 'OVERRIDE_MARKER: replacement instructions' > AGENTS.override.md
codex debug prompt-input > "${TMPDIR:-/tmp}/agents-prompt.json"
grep -E 'ROOT_MARKER|SUB_MARKER|OVERRIDE_MARKER' "${TMPDIR:-/tmp}/agents-prompt.json"
```

Expected:

- `ROOT_MARKER` is still present.
- `SUB_MARKER` is absent.
- `OVERRIDE_MARKER` is present.

The override affects only its own folder. It replaces `sub\AGENTS.md`; it
does not replace the root file.

## Step 4 — A large root file can silently drop a smaller, deeper file

`AGENTS.md` instructions share **one** 32 KiB budget, spent from the
repository root down. If a file near the root is large enough on its own,
Codex can run out of budget before it ever reaches a smaller, more specific
file lower in the tree — and nothing reports that it happened.

### Windows (PowerShell)

```powershell
$budgetRoot = Join-Path $env:TEMP "agents-md-budget-demo"
New-Item -ItemType Directory -Force (Join-Path $budgetRoot "deep") | Out-Null
Set-Location $budgetRoot
git init -q
# The root AGENTS.md alone is bigger than the 32 KiB budget.
$filler = "x" * 40000
Set-Content .\AGENTS.md "PADDING: $filler"
Set-Content .\deep\AGENTS.md "DEEP_MARKER: the most specific instruction in this repo"
git add -A
git -c user.email=demo@example.com -c user.name=demo commit -q -m init
Set-Location .\deep
codex debug prompt-input > (Join-Path $env:TEMP "budget-prompt.json")
Select-String -Path (Join-Path $env:TEMP "budget-prompt.json") -Pattern "DEEP_MARKER"
```

Expected: no match is printed. `deep\AGENTS.md` exists, sits on the
collection path, and was never touched after being written — it simply
never made it into the assembled instructions, because the oversized root
file used up the whole budget first.

Now shrink only the root file and rerun the same check:

```powershell
Set-Content (Join-Path $budgetRoot "AGENTS.md") "PADDING: small root file now"
codex debug prompt-input > (Join-Path $env:TEMP "budget-prompt.json")
Select-String -Path (Join-Path $env:TEMP "budget-prompt.json") -Pattern "DEEP_MARKER"
```

Expected: `DEEP_MARKER` now appears. Nothing about `deep\AGENTS.md` changed
— only the size of the file above it in the path did.

### Linux/macOS (Bash)

```bash
budgetRoot="${TMPDIR:-/tmp}/agents-md-budget-demo"
mkdir -p "$budgetRoot/deep"
cd "$budgetRoot"
git init -q
# The root AGENTS.md alone is bigger than the 32 KiB budget.
filler=$(python3 -c "print('x' * 40000)")
printf 'PADDING: %s\n' "$filler" > AGENTS.md
printf '%s\n' 'DEEP_MARKER: the most specific instruction in this repo' > deep/AGENTS.md
git add -A
git -c user.email=demo@example.com -c user.name=demo commit -q -m init
cd deep
codex debug prompt-input > "${TMPDIR:-/tmp}/budget-prompt.json"
grep -o "DEEP_MARKER.*" "${TMPDIR:-/tmp}/budget-prompt.json" || echo "(not present)"
```

Expected: `(not present)`. Now shrink only the root file and rerun:

```bash
printf 'PADDING: small root file now\n' > "$budgetRoot/AGENTS.md"
codex debug prompt-input > "${TMPDIR:-/tmp}/budget-prompt.json"
grep -o "DEEP_MARKER.*" "${TMPDIR:-/tmp}/budget-prompt.json"
```

Expected: `DEEP_MARKER` now appears.

Purpose: this is the failure mode the deck calls out — the budget is spent
top-down, a big file at the root can use it all up before Codex reaches the
file next to your code, and there is no error, no prompt, nothing in the
transcript. Keep `AGENTS.md` small on purpose: not to save money, but to
stay correct.

## Step 5 — Instructions are not a security boundary

Return to the real repository and remember: `sandbox_mode = "read-only"`
still allows a command to read a file. `AGENTS.md` can tell the model not to
print `.env`, but it cannot technically prevent that action.

Expected conclusion: use `AGENTS.md` for behavior and workflow guidance.
Use sandbox rules, exec-policy rules, or hooks when an operation must be
blocked. Demo 8 shows the hook-based secret check.

## Cleanup

Run this from outside `$demoRoot` and `$budgetRoot`.

Windows:

```powershell
Set-Location <path-to-english_translater>
Remove-Item -Recurse -Force $demoRoot
Remove-Item -Recurse -Force $budgetRoot
Remove-Item (Join-Path $env:TEMP "agents-prompt.json") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:TEMP "codex-prompt.json") -ErrorAction SilentlyContinue
Remove-Item (Join-Path $env:TEMP "budget-prompt.json") -ErrorAction SilentlyContinue
```

Linux/macOS:

```bash
cd <path-to-english_translater>
rm -rf "$demoRoot" "$budgetRoot"
rm -f "${TMPDIR:-/tmp}/agents-prompt.json" "${TMPDIR:-/tmp}/codex-prompt.json" "${TMPDIR:-/tmp}/budget-prompt.json"
```
