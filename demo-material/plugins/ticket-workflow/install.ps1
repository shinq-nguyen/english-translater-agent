$ErrorActionPreference = "Stop"

# Installs the ticket-workflow plugin into the current repository.
# Run this script from the target repository root in PowerShell.
$pluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetRoot = (Get-Location).Path

Write-Host "Installing ticket-workflow plugin into: $targetRoot"

$skillTarget = Join-Path $targetRoot ".agents\skills\implement-ticket"
if (Test-Path $skillTarget) {
    Remove-Item -Recurse -Force $skillTarget
}
New-Item -ItemType Directory -Force (Split-Path $skillTarget) | Out-Null
Copy-Item (Join-Path $pluginRoot "skills\implement-ticket") $skillTarget -Recurse -Force

$agentsTarget = Join-Path $targetRoot ".codex\agents"
New-Item -ItemType Directory -Force $agentsTarget | Out-Null
Copy-Item (Join-Path $pluginRoot "agents\*.toml") $agentsTarget -Force

$hooksTarget = Join-Path $targetRoot ".codex\hooks"
New-Item -ItemType Directory -Force $hooksTarget | Out-Null
Copy-Item (Join-Path $pluginRoot "hooks\*.py") $hooksTarget -Force

$configTarget = Join-Path $targetRoot ".codex\config.toml"
$configSnippet = Join-Path $pluginRoot "config-snippet.toml"
& python (Join-Path $pluginRoot "hooks\merge_config.py") $configTarget $configSnippet

$hooksJsonTarget = Join-Path $targetRoot ".codex\hooks.json"
$hooksSnippet = Join-Path $pluginRoot "hooks-snippet.json"
& python (Join-Path $pluginRoot "hooks\merge_hooks.py") $hooksJsonTarget $hooksSnippet

$gitignore = Join-Path $targetRoot ".gitignore"
if (-not (Test-Path $gitignore)) {
    New-Item -ItemType File -Path $gitignore | Out-Null
}
$existing = @(Get-Content $gitignore -ErrorAction SilentlyContinue)
foreach ($line in Get-Content (Join-Path $pluginRoot "gitignore-snippet")) {
    if ($line -and $line -notin $existing) {
        Add-Content -Path $gitignore -Value $line
        $existing += $line
    }
}

Write-Host ""
Write-Host "Installed. Next steps:"
Write-Host "  1. codex                          # trust the project"
Write-Host "  2. inside codex: /hooks           # approve the two plugin hooks"
Write-Host "  3. codex mcp login atlassian      # OAuth login to Jira"
Write-Host "  4. see README.md for the guard sanity check and how to start a ticket"
