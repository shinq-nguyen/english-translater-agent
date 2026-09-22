# Pre-work — prepare the demo kit

Complete this once before presenting the demos. The commands below have two
variants:

- **Windows:** PowerShell, native Windows Codex, and Docker Desktop.
- **Linux/macOS:** Bash, Docker, and the native Codex CLI.

This checkout already contains the demo configuration under `.codex/`,
`.agents/`, and `demo-material/`. Do not recreate those files during the
live demo; this setup only installs prerequisites, starts Postgres, and
verifies the checkout.

## Step 0 — Install prerequisites

Both platforms need Git, Node.js/npm, Python 3.11+, Docker, Docker Compose,
and Codex CLI. Log in with `codex login`.

### Windows (PowerShell)

Install Docker Desktop and Git if they are not already installed. Then run:

```powershell
node --version
npm --version
git --version
python --version
docker --version
docker compose version
npm install -g @openai/codex
codex login
codex --version
```

Expected: every version command succeeds and `codex login` completes without
an authentication error. Native Windows Codex can run from PowerShell; WSL2
is optional, not a prerequisite.

### Linux/macOS (Bash)

Install the same tools with the platform package manager. On Ubuntu/Debian,
the usual prerequisites are:

```bash
sudo apt update
sudo apt install -y git python3 python3-pip docker.io docker-compose-plugin bubblewrap
```

Install Node.js/npm using the preferred Node version manager, then run:

```bash
node --version
npm --version
git --version
python3 --version
docker --version
docker compose version
npm install -g @openai/codex
codex login
codex --version
```

Expected: every version command succeeds and `codex login` completes without
an authentication error.

## Step 1 — Clone the repository and create local secrets

Clone the repository, then enter its root.

### Windows (PowerShell)

```powershell
git clone https://github.com/shinq-nguyen/english-translater-agent.git
Set-Location .\english-translater-agent
Copy-Item .env.example .env
```

Generate throwaway local secrets without printing them:

```powershell
$envFile = Get-Content .\.env -Raw
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$jwtBytes = New-Object byte[] 32
$encryptionBytes = New-Object byte[] 32
$rng.GetBytes($jwtBytes)
$rng.GetBytes($encryptionBytes)
$rng.Dispose()
$jwt = [Convert]::ToBase64String($jwtBytes)
$encryption = [Convert]::ToBase64String($encryptionBytes)
$envFile = $envFile -replace 'APP_JWT_SECRET=.*', "APP_JWT_SECRET=$jwt"
$envFile = $envFile -replace 'AI_MODEL_ENCRYPTION_KEY=.*', "AI_MODEL_ENCRYPTION_KEY=$encryption"
[IO.File]::WriteAllText((Resolve-Path .\.env), $envFile)
```

### Linux/macOS (Bash)

```bash
git clone https://github.com/shinq-nguyen/english-translater-agent.git
cd english-translater-agent
cp .env.example .env
python3 - <<'PY'
import base64
import pathlib
import secrets

path = pathlib.Path('.env')
text = path.read_text()
text = text.replace('APP_JWT_SECRET=', 'APP_JWT_SECRET=' + base64.b64encode(secrets.token_bytes(32)).decode(), 1)
text = text.replace('AI_MODEL_ENCRYPTION_KEY=', 'AI_MODEL_ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode(), 1)
path.write_text(text)
PY
```

Expected: `.env` exists and contains non-empty values. Do not print it or
paste its contents into chat.

## Step 2 — Start Postgres and load the schema

### Windows (PowerShell)

```powershell
docker compose up -d postgres
docker compose ps
```

Wait until `translator-postgres` is healthy, then load migrations in order:

```powershell
Get-ChildItem .\backend\src\main\resources\db\migration\V*.sql |
  Sort-Object Name |
  ForEach-Object {
    Get-Content $_.FullName -Raw |
      docker compose exec -T postgres psql -U translator -d translator -f -
  }
```

### Linux/macOS (Bash)

```bash
docker compose up -d postgres
docker compose ps
for file in backend/src/main/resources/db/migration/V*.sql; do
  docker compose exec -T postgres psql -U translator -d translator -f - < "$file"
done
```

Expected: `translator-postgres` is `running (healthy)`, and the migration
commands finish without a SQL error.

## Step 3 — Trust the project

From the repository root, run:

```text
codex
```

Accept the trust prompt, then exit Codex. Project configuration and hooks are
not loaded until the project is trusted.

Expected: Codex opens without a configuration error and does not ask for
trust again for this local path.

## Step 4 — Verify the prepared demo files

Run:

```text
codex doctor
codex mcp list
```

Expected:

- authentication is available;
- project config loads successfully;
- `translator_db` is enabled;
- `demo_file_writer` is disabled.

### Windows (PowerShell)

```powershell
Test-Path .\.codex\config.toml
Test-Path .\.codex\hooks.json
Test-Path .\.codex\agents\secret-auditor.toml
Test-Path .\.agents\skills\add-ai-provider\SKILL.md
```

### Linux/macOS (Bash)

```bash
test -f .codex/config.toml
test -f .codex/hooks.json
test -f .codex/agents/secret-auditor.toml
test -f .agents/skills/add-ai-provider/SKILL.md
```

All checks should return success/`True`.

## Step 5 — Prepare the local MCP file-writer

Demo 6 uses this only in its final step. Run once:

### Windows (PowerShell)

```powershell
Set-Location .\demo-material\mcp-servers\file-writer
npm install
Set-Location <path-to-english_translater>
```

### Linux/macOS (Bash)

```bash
cd demo-material/mcp-servers/file-writer
npm install
cd <path-to-english_translater>
```

Expected: `npm install` succeeds. `node_modules/` is gitignored.

## Troubleshooting

- **Windows Docker error:** start Docker Desktop and confirm `docker compose
  ps` works from PowerShell.
- **Linux sandbox error:** install `bubblewrap` and ensure `bwrap` is on
  `PATH`.
- **Trust/config not active:** exit Codex, return to the repository root, and
  open `codex` again; confirm the trust prompt was accepted.
- **Postgres query fails:** check `docker compose ps` and rerun only the
  migration that failed after fixing the database state.
- **MCP file-writer fails:** run `npm install` in its directory and confirm
  `demo_file_writer` remains disabled until Demo 6 enables it.
