#!/usr/bin/env bash
# demo-material/plugins/ticket-workflow/install.sh
#
# Installs the ticket-workflow plugin into the CURRENT directory (run this
# from the target repo's root). Copies the skill, subagent roles, and hook
# scripts; key-merges the MCP/feature config and hooks registration instead
# of overwriting; appends the required .gitignore lines. Idempotent.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="$(pwd)"

echo "Installing ticket-workflow plugin into: $TARGET_ROOT"

mkdir -p "$TARGET_ROOT/.agents/skills"
rm -rf "$TARGET_ROOT/.agents/skills/implement-ticket"
cp -R "$PLUGIN_ROOT/skills/implement-ticket" "$TARGET_ROOT/.agents/skills/implement-ticket"

mkdir -p "$TARGET_ROOT/.codex/agents"
cp "$PLUGIN_ROOT"/agents/*.toml "$TARGET_ROOT/.codex/agents/"

mkdir -p "$TARGET_ROOT/.codex/hooks"
cp "$PLUGIN_ROOT"/hooks/*.py "$TARGET_ROOT/.codex/hooks/"
chmod +x "$TARGET_ROOT"/.codex/hooks/*.py

python "$PLUGIN_ROOT/hooks/merge_config.py" \
  "$TARGET_ROOT/.codex/config.toml" \
  "$PLUGIN_ROOT/config-snippet.toml"

python - "$TARGET_ROOT/.codex/hooks.json" "$PLUGIN_ROOT/hooks-snippet.json" <<'PYEOF'
# Both files nest their event lists under a top-level "hooks" key -- this
# matches the real shape of Codex's hooks.json (verified against this
# repo's own .codex/hooks.json), not a flat {"PreToolUse": [...]} object.
import json
import sys
from pathlib import Path

target_path = Path(sys.argv[1])
snippet_path = Path(sys.argv[2])

target = {"hooks": {"PreToolUse": [], "PostToolUse": []}}
if target_path.exists():
    target = json.loads(target_path.read_text(encoding="utf-8"))
    target.setdefault("hooks", {})
    target["hooks"].setdefault("PreToolUse", [])
    target["hooks"].setdefault("PostToolUse", [])

snippet = json.loads(snippet_path.read_text(encoding="utf-8"))

for event_name, entries in snippet["hooks"].items():
    for entry in entries:
        for hook in entry["hooks"]:
            already_present = any(
                h.get("command") == hook["command"]
                for existing_entry in target["hooks"].get(event_name, [])
                for h in existing_entry.get("hooks", [])
            )
            if not already_present:
                target["hooks"].setdefault(event_name, []).append(entry)

target_path.parent.mkdir(parents=True, exist_ok=True)
target_path.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
PYEOF

GITIGNORE="$TARGET_ROOT/.gitignore"
touch "$GITIGNORE"
while IFS= read -r line; do
  line="${line%$'\r'}"  # strip a trailing CR (checkouts with core.autocrlf=true)
  if ! grep -qxF "$line" "$GITIGNORE"; then
    echo "$line" >> "$GITIGNORE"
  fi
done < "$PLUGIN_ROOT/gitignore-snippet"

echo ""
echo "Installed. Next steps:"
echo "  1. codex                          # trust the project"
echo "  2. inside codex: /hooks           # approve guard_ticket_commit.py and ticket_audit.py"
echo "  3. codex mcp login atlassian      # OAuth login to Jira"
echo "  4. see README.md for the guard sanity check and how to start a ticket"
