# Demo 2 — Sandbox vs. Approval

Covers slides 8–13. No database or model-specific setup is required. Use the
Windows or Linux/macOS command variant shown in each step.

## Purpose

Show the difference between two independent controls:

- `sandbox_mode`: what a command is allowed to change.
- `approval_policy`: when Codex asks the user for permission to go beyond
  the sandbox.

An approval prompt does not mean that the sandbox allowed the operation, and
no prompt does not mean that the operation was safe.

## Step 1 — Compare the three sandbox modes

Run the same write once in each mode.

### Windows (PowerShell)

```powershell
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "echo test > sbx_test.txt"
Test-Path .\sbx_test.txt

codex sandbox -c 'sandbox_mode="workspace-write"' -- cmd.exe /c "echo test > sbx_test.txt"
Test-Path .\sbx_test.txt
Remove-Item .\sbx_test.txt -ErrorAction SilentlyContinue

codex sandbox -c 'sandbox_mode="danger-full-access"' -- cmd.exe /c "echo test > sbx_test.txt"
Test-Path .\sbx_test.txt
Remove-Item .\sbx_test.txt -ErrorAction SilentlyContinue
```

### Linux/macOS (Bash)

```bash
codex sandbox -c 'sandbox_mode="read-only"' -- sh -c 'echo test > sbx_test.txt'
test -e sbx_test.txt

codex sandbox -c 'sandbox_mode="workspace-write"' -- sh -c 'echo test > sbx_test.txt'
test -e sbx_test.txt
rm -f sbx_test.txt

codex sandbox -c 'sandbox_mode="danger-full-access"' -- sh -c 'echo test > sbx_test.txt'
test -e sbx_test.txt
rm -f sbx_test.txt
```

Expected:

- `read-only`: the command is denied and the file does not exist.
- `workspace-write`: the command succeeds and the file exists.
- `danger-full-access`: the command succeeds and the file exists.

The only variable is `sandbox_mode`; there is no model or approval prompt in
this command. This isolates the enforcement boundary.

## Step 2 — `read-only` does not block reads

Use a harmless test file, never `.env`.

### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force .\demo-material\scratch | Out-Null
Set-Content .\demo-material\scratch\read-test.txt "readable"
codex sandbox -c 'sandbox_mode="read-only"' -- cmd.exe /c "type demo-material\scratch\read-test.txt"
Remove-Item .\demo-material\scratch\read-test.txt
```

### Linux/macOS (Bash)

```bash
mkdir -p demo-material/scratch
printf 'readable\n' > demo-material/scratch/read-test.txt
codex sandbox -c 'sandbox_mode="read-only"' -- sh -c 'cat demo-material/scratch/read-test.txt'
rm -f demo-material/scratch/read-test.txt
```

Expected: the command prints `readable`. `read-only` blocks writes; it does
not protect file contents from being read. Do not use a real secret file for
this test.

## Step 3 — See approval and sandbox work independently

1. Start a Codex session in this repository. Confirm the project defaults
   with `/status`: `workspace-write` and `on-request`.
2. Ask Codex:

   > Create `demo-material/scratch/step3.txt` containing `hello`.

Expected: the file is created without an approval prompt because the project
sandbox already allows writes inside the workspace.

3. Ask Codex to create a file outside the repository, for example:

   > Create `<TEMP>\codex-approval-test.txt` containing `hello`.

   Replace `<TEMP>` with the path printed by PowerShell:

   Windows PowerShell: `$env:TEMP`
   Linux/macOS Bash: `${TMPDIR:-/tmp}`

Expected: Codex asks for approval because the write is outside the normal
workspace boundary. If the policy is `never`, it is refused instead.

The same operation can therefore be allowed silently, asked about, or
refused depending on both settings.

## Step 4 — Check the effective settings

Inside the same Codex session, run:

```text
/status
/permissions
```

Expected: `/status` shows the settings active in this session. `/permissions`
can change them for the session, but does not edit `.codex/config.toml`.

## Cleanup

Remove `demo-material/scratch/step3.txt` and the temporary file outside the
repository. On Windows use `Remove-Item`; on Linux/macOS use `rm -f`.
Confirm that `.codex/config.toml` still has:

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"
```
