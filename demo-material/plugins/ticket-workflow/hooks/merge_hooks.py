"""Merge a plugin hooks snippet into a Codex hooks.json file."""

import json
import sys
from pathlib import Path


def main() -> int:
    target_path = Path(sys.argv[1])
    snippet_path = Path(sys.argv[2])

    target = {"hooks": {"PreToolUse": [], "PostToolUse": []}}
    if target_path.exists():
        target = json.loads(target_path.read_text(encoding="utf-8"))
        target.setdefault("hooks", {})

    snippet = json.loads(snippet_path.read_text(encoding="utf-8"))
    for event_name, entries in snippet.get("hooks", {}).items():
        existing_entries = target["hooks"].setdefault(event_name, [])
        for entry in entries:
            commands = {
                hook.get("command")
                for existing in existing_entries
                for hook in existing.get("hooks", [])
            }
            if any(hook.get("command") in commands for hook in entry.get("hooks", [])):
                continue
            existing_entries.append(entry)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
