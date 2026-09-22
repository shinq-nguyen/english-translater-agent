# Demo 3 — Configuration precedence: identify the winner

Covers slides 14–16. Run this demo from a trusted checkout. The commands
below use `approval_policy` as the test key because `codex doctor` prints its
effective value clearly.

## Purpose

Show the six configurable layers and make the winning value visible. Each
layer gets a different value; after each command, compare the `approval
policy` line in `codex doctor` with the table below.

For this demo, show the six configuration surfaces in effective order. The
requirements layer is listed first because it can reject a value resolved
from any lower layer; it is not an ordinary personal override.

| Layer | Source | What it proves |
|---|---|---|
| 1 | `requirements.toml` | An organization can reject unsafe values; this is a constraint, not a normal personal override. |
| 2 | CLI `-c` / `--config` | A one-run override beats local config. |
| 3 | Trusted project `.codex/config.toml` | The repository config beats profile and user config. |
| 4 | `--profile <name>` | A profile beats the normal user config. |
| 5 | User `$CODEX_HOME/config.toml` | The user's baseline beats the machine fallback. |
| 6 | System/managed config | A fallback supplied by an administrator or the operating system. |

Built-in defaults are the fallback when none of the six sources supplies a
value. `requirements.toml` is special: when it forbids a value, lower layers
cannot force that value with `-c`.

## Step 1 — Prepare an isolated, disposable test

`CODEX_HOME` contains more than config: it can also contain `auth.json`,
history, logs, and caches. A completely empty temporary home can therefore
make an interactive `codex` command ask for login again. The commands below
copy only an existing `auth.json` into the disposable home when it exists;
they never print it. If credentials are stored in the OS keychain, no copy is
needed.

Run the **dry-run** (`codex doctor`) before the live trust prompt. If it opens
a login flow, press `Ctrl+C`, restore the original `CODEX_HOME`, and do not
continue with the demo until the machine-specific auth setup is fixed.

Start from the repository root.

### Windows (PowerShell)

```powershell
$repoRoot = (Get-Location).Path
$originalCodexHome = $env:CODEX_HOME
$originalCodexHomePath = if ([string]::IsNullOrWhiteSpace($originalCodexHome)) { Join-Path $env:USERPROFILE ".codex" } else { $originalCodexHome }
$layerRoot = Join-Path $env:TEMP "codex-config-layers-$PID"
$demoHome = Join-Path $layerRoot "codex-home"
$demoWork = Join-Path $layerRoot "trusted-workspace"
New-Item -ItemType Directory -Force $demoHome, $demoWork | Out-Null
if (Test-Path (Join-Path $originalCodexHomePath "auth.json")) {
    Copy-Item (Join-Path $originalCodexHomePath "auth.json") (Join-Path $demoHome "auth.json")
}
$env:CODEX_HOME = $demoHome
Set-Location $demoWork
codex doctor --no-color
codex
```

Expected for the dry-run: `codex doctor` completes without starting a login
flow. Then, at the trust prompt, choose **Trust and continue**, and exit
Codex. This scratch folder deliberately has no project config yet.

### Linux/macOS (Bash)

```bash
repoRoot="$PWD"
hadCodexHome="${CODEX_HOME+x}"
originalCodexHome="${CODEX_HOME:-$HOME/.codex}"
layerRoot="${TMPDIR:-/tmp}/codex-config-layers-$$"
demoHome="$layerRoot/codex-home"
demoWork="$layerRoot/trusted-workspace"
mkdir -p "$demoHome" "$demoWork"
if test -f "$originalCodexHome/auth.json"; then
  cp "$originalCodexHome/auth.json" "$demoHome/auth.json"
fi
export CODEX_HOME="$demoHome"
cd "$demoWork"
codex doctor --no-color
codex
```

Expected for the dry-run: `codex doctor` completes without starting a login
flow. Then, at the trust prompt, choose **Trust and continue**, and exit
Codex.

## Step 2 — Show the current winner, before adding local values

Run from `demoWork`:

### Windows (PowerShell)

```powershell
codex doctor --no-color | Select-String "approval policy|configuration"
```

### Linux/macOS (Bash)

```bash
codex doctor --no-color | grep -Ei "approval policy|configuration"
```

Expected: the value comes from the system/managed layer if one exists;
otherwise it is the built-in default. This is the Layer 6 baseline. Do not
assume that a machine-wide file exists on a developer laptop.

## Step 3 — Layer 5: user config wins over the baseline

Create a user config in the disposable `CODEX_HOME`:

### Windows (PowerShell)

```powershell
Set-Content (Join-Path $demoHome "config.toml") 'approval_policy = "on-failure"'
codex doctor --no-color | Select-String "approval policy"
```

### Linux/macOS (Bash)

```bash
printf 'approval_policy = "on-failure"\n' > "$demoHome/config.toml"
codex doctor --no-color | grep -Ei "approval policy"
```

Expected: `approval policy` is `OnFailure`. Layer 5 now beats the Layer 6
baseline.

## Step 4 — Layer 4: profile wins over user config

Add a profile with a different value, then select it explicitly:

### Windows (PowerShell)

```powershell
Set-Content (Join-Path $demoHome "layer-demo.config.toml") 'approval_policy = "never"'
codex --profile layer-demo doctor --no-color | Select-String "approval policy"
```

### Linux/macOS (Bash)

```bash
printf 'approval_policy = "never"\n' > "$demoHome/layer-demo.config.toml"
codex --profile layer-demo doctor --no-color | grep -Ei "approval policy"
```

Expected: `approval policy` is `Never`. The profile (Layer 4) beats the user
config (Layer 5). Without `--profile layer-demo`, it returns to `OnFailure`.

## Step 5 — Layer 3: trusted project config beats the profile

Create a project config in the already trusted scratch folder:

### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force (Join-Path $demoWork ".codex") | Out-Null
Set-Content (Join-Path $demoWork ".codex\config.toml") 'approval_policy = "on-request"'
codex --profile layer-demo doctor --no-color | Select-String "approval policy"
```

### Linux/macOS (Bash)

```bash
mkdir -p "$demoWork/.codex"
printf 'approval_policy = "on-request"\n' > "$demoWork/.codex/config.toml"
codex --profile layer-demo doctor --no-color | grep -Ei "approval policy"
```

Expected: `approval policy` is `OnRequest`. The trusted project config
(Layer 3) beats the selected profile and the user config. This is the same
precedence that makes this repository's `.codex/config.toml` effective.

## Step 6 — Layer 2: CLI override wins for one invocation

Run the same command with a CLI override:

### Windows and Linux/macOS

```text
codex doctor -c approval_policy='"never"'
```

Expected: `approval policy` is `Never` for this invocation. Run the command
again without `-c`; it returns to `OnRequest`. No file changed.

## Step 7 — Layer 1: requirements.toml is the unbreakable guardrail

`requirements.toml` is controlled by an organization administrator. Do not
create or edit it on a personal machine just to make this demo work.

The [current official OpenAI managed-configuration documentation](https://learn.chatgpt.com/docs/enterprise/managed-configuration)
lists these system requirements locations:

- Windows: `%ProgramData%\OpenAI\Codex\requirements.toml`
- Linux/macOS: `/etc/codex/requirements.toml`

This is an administrator-managed file, not a file to create during a local
demo. If the installed Codex version reports a different managed source,
follow `codex doctor` and that version's official documentation.

### Windows (PowerShell)

```powershell
$requirementsPath = Join-Path $env:ProgramData "OpenAI\Codex\requirements.toml"
if (Test-Path $requirementsPath) { "Managed requirements found" } else { "No managed requirements on this machine" }
codex doctor -c approval_policy='"never"'
```

### Linux/macOS (Bash)

```bash
if test -f /etc/codex/requirements.toml; then echo "Managed requirements found"; else echo "No managed requirements on this machine"; fi
codex doctor -c approval_policy='"never"'
```

Expected on an unmanaged laptop: the CLI value is still `Never`, because no
Layer 1 policy is installed. On a managed machine whose requirements forbid
`approval_policy = "never"`, Codex rejects or replaces that value and reports
the managed restriction. That is the Layer 1 win: a lower layer cannot
override the requirement.

## Step 8 — Trust is the gate for Layer 3

This is a separate check: a project config in an untrusted folder is not a
lower-priority value; it is ignored completely.

### Windows (PowerShell)

```powershell
$untrusted = Join-Path $layerRoot "untrusted-workspace"
New-Item -ItemType Directory -Force (Join-Path $untrusted ".codex") | Out-Null
Copy-Item (Join-Path $demoWork ".codex\config.toml") (Join-Path $untrusted ".codex\config.toml")
Set-Location $untrusted
codex
```

Decline trust, exit Codex, then run:

```powershell
codex doctor --no-color | Select-String "approval policy"
```

### Linux/macOS (Bash)

```bash
untrusted="$layerRoot/untrusted-workspace"
mkdir -p "$untrusted/.codex"
cp "$demoWork/.codex/config.toml" "$untrusted/.codex/config.toml"
cd "$untrusted"
codex
```

Decline trust, exit Codex, then run:

```bash
codex doctor --no-color | grep -Ei "approval policy"
```

Expected: `approval policy` is `OnFailure`, not the copied `OnRequest`. The
untrusted folder's `.codex/config.toml` (Layer 3) is not loaded at all, so
the effective value falls all the way back to Layer 5 — the same
`$demoHome/config.toml` set in Step 3 — not to Layer 6 or the built-in
default, since that user-level file is still present and still applies
without needing trust.

## Cleanup

Return to the repository, remove the disposable folder, and clear the
temporary environment variable.

### Windows (PowerShell)

```powershell
Set-Location $repoRoot
Remove-Item -Recurse -Force $layerRoot
if ([string]::IsNullOrWhiteSpace($originalCodexHome)) {
    Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
} else {
    $env:CODEX_HOME = $originalCodexHome
}
```

### Linux/macOS (Bash)

```bash
cd "$repoRoot"
rm -rf "$layerRoot"
if test -n "${hadCodexHome:-}"; then export CODEX_HOME="$originalCodexHome"; else unset CODEX_HOME; fi
```

Final check: the repository's `.codex/config.toml` and the real user
`config.toml` were not edited by this demo.
