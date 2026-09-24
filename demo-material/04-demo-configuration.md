# Demo 3 — Configuration precedence: who wins?

Covers slides 14–16. Verified on `codex-cli 0.156.1` (Windows).

## The idea

Codex can read the same setting from several places. This demo sets **one
key, `model`**, in each place with a value that names that place:
`L5-user`, `L4-profile`, `L3-project`, `L2-cli`.

Each step adds **one higher layer**, and its value **overrides the previous
step's**. To see the winner, start `codex` and read the `model:` line in the
header. Then exit with `Ctrl+C` **without typing a prompt**. The fake model
names are only displayed and never sent anywhere.

```text
╭──────────────────────────────────────╮
│ >_ OpenAI Codex (v0.156.1)           │
│                                      │
│ model:     L4-profile   /model to…   │  ◀ this line tells you who won
│ directory: ~\…\trusted-workspace     │
╰──────────────────────────────────────╯
```

## Picture 1 — The test folder

Everything lives in one temp folder, which Cleanup deletes. Your real
`~/.codex` and this repo are not touched.

```text
$layerRoot/
├── codex-home/                   ◀ $CODEX_HOME points here during the demo
│   ├── auth.json                 (copied, only so you don't have to log in again)
│   ├── config.toml               ◀ Step 2  USER      model = "L5-user"
│   │                               + Codex saves "trusted" folders in here too
│   └── layer-demo.config.toml    ◀ Step 3  PROFILE   model = "L4-profile"
│
├── trusted-workspace/            ◀ where you run codex (you click "Trust")
│   └── .codex/config.toml        ◀ Step 4  PROJECT   model = "L3-project"
│
└── untrusted-workspace/          ◀ Step 7 (never trusted)
    └── .codex/config.toml          model = "L3-project"  → IGNORED

Not a file:   codex -c model=L2-cli      ◀ Step 5  CLI
Admin only:   requirements.toml          ◀ Step 6  (not created in this demo)
```

## Picture 2 — Who wins, step by step

Higher layer wins. Each step fills in one more row, higher than everything
before it, so the winner moves up one row each time.

```text
                              Step 1    Step 2    Step 3      Step 4      Step 5
                              ──────    ──────    ──────      ──────      ──────
 L1 requirements.toml (admin)  ─── not a value: can BLOCK values from below (Step 6) ───
 L2 -c model=...                                                          ★ L2-cli
 L3 .codex/config.toml (trusted)                              ★ L3-project  L3-project
 L4 --profile layer-demo                        ★ L4-profile  L4-profile  L4-profile
 L5 codex-home/config.toml               ★ L5-user   L5-user   L5-user     L5-user
 L6 system / built-in default  ★ default   default   default   default     default

 header shows →                default   L5-user   L4-profile  L3-project  L2-cli
```

`★` = the winner of that step.

## Step 0 — Set up the test folder

Run this from the repository root.

### Windows (PowerShell)

```powershell
$repoRoot  = (Get-Location).Path
$oldHome   = $env:CODEX_HOME
$realHome  = if ($oldHome) { $oldHome } else { Join-Path $env:USERPROFILE ".codex" }
$layerRoot = Join-Path $env:TEMP "codex-layers-$PID"
$demoHome  = Join-Path $layerRoot "codex-home"
$demoWork  = Join-Path $layerRoot "trusted-workspace"
New-Item -ItemType Directory -Force $demoHome, $demoWork | Out-Null
if (Test-Path "$realHome\auth.json") { Copy-Item "$realHome\auth.json" "$demoHome\auth.json" }
$env:CODEX_HOME = $demoHome
Set-Location $demoWork
```

### Linux/macOS (Bash)

```bash
repoRoot="$PWD"
hadHome="${CODEX_HOME+x}"; oldHome="$CODEX_HOME"
realHome="${CODEX_HOME:-$HOME/.codex}"
layerRoot="${TMPDIR:-/tmp}/codex-layers-$$"
demoHome="$layerRoot/codex-home"
demoWork="$layerRoot/trusted-workspace"
mkdir -p "$demoHome" "$demoWork"
test -f "$realHome/auth.json" && cp "$realHome/auth.json" "$demoHome/"
export CODEX_HOME="$demoHome"
cd "$demoWork"
```

Every command below prints a `WARNING: ... Refusing to create helper binaries
under temporary dir` line, because the demo's home is in the temp folder. It
is expected and harmless.

## Step 1 — Baseline: nothing set yet

```text
codex doctor --no-color | Select-String "^\s+model\s{2}"     # Windows
codex doctor --no-color | grep -E "^[[:space:]]+model[[:space:]]{2}"           # Linux/macOS
```

Expected: `model  <default> · openai`. No layer sets `model`, so Codex uses
its built-in default (or a system/managed value, if the machine has one).

## Step 2 — USER config (`codex-home/config.toml`)

```powershell
Set-Content "$demoHome\config.toml" -Encoding utf8 @'
model = "L5-user"

[windows]
sandbox = "elevated"
'@
codex
```

```bash
printf 'model = "L5-user"\n' > "$demoHome/config.toml"
codex
```

The `[windows]` block reuses the sandbox mode already set up on this machine.
Without it, Codex asks you to set up a sandbox for the new, empty home. If
your real config uses `"unelevated"`, copy that value instead.

When the prompt *Trust this folder?* appears, choose **1. Trust and continue**.
Codex saves that choice as a `[projects.'…']` entry in this same
`config.toml`, below the `model` line.

Expected header: **`model: L5-user`**. User config beats the default.
Exit with `Ctrl+C`.

## Step 3 — PROFILE (`--profile layer-demo`)

A profile is a file `codex-home/<name>.config.toml`. It is only used when
you pass `--profile <name>`.

```powershell
Set-Content "$demoHome\layer-demo.config.toml" -Encoding utf8 'model = "L4-profile"'
codex --profile layer-demo
```

```bash
printf 'model = "L4-profile"\n' > "$demoHome/layer-demo.config.toml"
codex --profile layer-demo
```

Expected header: **`model: L4-profile`**. Profile beats user config.
(Run plain `codex` and you are back to `L5-user`: no flag, no profile.)

## Step 4 — PROJECT config (`.codex/config.toml` in a trusted folder)

```powershell
New-Item -ItemType Directory -Force "$demoWork\.codex" | Out-Null
Set-Content "$demoWork\.codex\config.toml" -Encoding utf8 'model = "L3-project"'
codex --profile layer-demo
```

```bash
mkdir -p "$demoWork/.codex"
printf 'model = "L3-project"\n' > "$demoWork/.codex/config.toml"
codex --profile layer-demo
```

Expected header: **`model: L3-project`**. Project config beats the profile
even though `--profile` is still passed. This is why this repo's own
`.codex/config.toml` takes effect.

## Step 5 — CLI flag (`-c`)

```text
codex --profile layer-demo -c model=L2-cli
```

Expected header: **`model: L2-cli`**. A `-c` flag beats every file, for this
one run only. Run the command again without `-c` and you are back to
`L3-project`. No file was changed.

## Step 6 — requirements.toml (explain, don't run)

`requirements.toml` is written by an administrator
(`%ProgramData%\OpenAI\Codex\requirements.toml` on Windows,
`/etc/codex/requirements.toml` on Linux/macOS, or pushed as a cloud-managed
policy). It does not **set** a value. It **forbids** values for
security-relevant keys such as `approval_policy` or `sandbox_mode`. If it
forbids `approval_policy = "never"`, even `-c approval_policy=never` is
rejected. It sits above every other layer as a guard.

Do not create it on your own laptop for this demo. See the
[managed configuration docs](https://learn.chatgpt.com/docs/enterprise/managed-configuration).

## Step 7 — Bonus: no trust, no project config

Copy the same project config into a new folder that has **never been
trusted**. The trust prompt only offers *Trust and continue* or *Quit*, so
read the value with `codex doctor` instead, which doesn't ask:

```powershell
$untrusted = Join-Path $layerRoot "untrusted-workspace"
New-Item -ItemType Directory -Force "$untrusted\.codex" | Out-Null
Copy-Item "$demoWork\.codex\config.toml" "$untrusted\.codex\config.toml"
Set-Location $untrusted
codex doctor --no-color | Select-String "^\s+model\s{2}"
```

```bash
untrusted="$layerRoot/untrusted-workspace"
mkdir -p "$untrusted/.codex"
cp "$demoWork/.codex/config.toml" "$untrusted/.codex/"
cd "$untrusted"
codex doctor --no-color | grep -E "^[[:space:]]+model[[:space:]]{2}"
```

Expected: **`model  L5-user`**, not `L3-project`. An untrusted folder's
`.codex/config.toml` isn't a lower layer; it is **skipped entirely**, so
the user config wins again. (If you now ran `codex` here and chose *Trust and
continue*, the header would switch to `L3-project`.)

## Cleanup

```powershell
Set-Location $repoRoot
Remove-Item -Recurse -Force $layerRoot
if ($oldHome) { $env:CODEX_HOME = $oldHome } else { Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue }
```

```bash
cd "$repoRoot"
rm -rf "$layerRoot"
if test -n "$hadHome"; then export CODEX_HOME="$oldHome"; else unset CODEX_HOME; fi
```

## Cheat sheet

| Step | You add | Command | Header shows |
|---|---|---|---|
| 1 | nothing | `codex doctor` | `<default>` |
| 2 | `codex-home/config.toml` | `codex` | `L5-user` |
| 3 | `codex-home/layer-demo.config.toml` | `codex --profile layer-demo` | `L4-profile` |
| 4 | `trusted-workspace/.codex/config.toml` | `codex --profile layer-demo` | `L3-project` |
| 5 | nothing (flag only) | `codex --profile layer-demo -c model=L2-cli` | `L2-cli` |
| 7 | untrusted copy of step 4 | `codex doctor` | `L5-user` |
