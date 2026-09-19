#!/usr/bin/env python3
"""
Key-aware merge of the ticket-workflow plugin's MCP/feature config into an
existing Codex config.toml.

Blindly appending a snippet is unsafe: if the target already has its own
[features] table, TOML forbids a second [features] header and the file
stops parsing entirely. This merges by inspecting existing table headers
line-by-line instead of round-tripping through a TOML *writer* (the stdlib
only ships a reader, tomllib) — insert missing keys into an existing table,
append whole new tables at EOF (safe: table names are unique), and always
re-parse the result before trusting it, restoring a backup on failure.

CLI:
  python3 merge_config.py <target-config.toml> <snippet.toml>
"""
import shutil
import sys
import tomllib
from pathlib import Path


class MergeError(Exception):
    pass


def _header_line(lines, table_name):
    target = f"[{table_name}]"
    for i, line in enumerate(lines):
        if line.strip() == target:
            return i
    return None


def _block_end(lines, start_index):
    for i in range(start_index + 1, len(lines)):
        if lines[i].strip().startswith("["):
            return i
    return len(lines)


def _key_present(lines, start, end, key):
    prefix = f"{key} ="
    return any(lines[i].strip().startswith(prefix) for i in range(start, end))


def merge_toml_text(target_text, snippet_text):
    lines = target_text.splitlines()
    snippet_lines = snippet_text.splitlines()
    report = {
        "features_table_added": False,
        "features_key_inserted": False,
        "mcp_table_added": False,
        "mcp_table_skipped_existing": False,
    }

    snip_features_start = _header_line(snippet_lines, "features")
    rmcp_line = None
    if snip_features_start is not None:
        snip_features_end = _block_end(snippet_lines, snip_features_start)
        for i in range(snip_features_start + 1, snip_features_end):
            if snippet_lines[i].strip().startswith("rmcp_client"):
                rmcp_line = snippet_lines[i]
                break

    target_features_start = _header_line(lines, "features")
    if target_features_start is not None:
        target_features_end = _block_end(lines, target_features_start)
        if rmcp_line is not None and not _key_present(
            lines, target_features_start, target_features_end, "rmcp_client"
        ):
            lines.insert(target_features_start + 1, rmcp_line)
            report["features_key_inserted"] = True
    elif snip_features_start is not None:
        snip_features_end = _block_end(snippet_lines, snip_features_start)
        block = snippet_lines[snip_features_start:snip_features_end]
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.extend(block)
        report["features_table_added"] = True

    mcp_table = "mcp_servers.atlassian"
    if _header_line(lines, mcp_table) is not None:
        report["mcp_table_skipped_existing"] = True
    else:
        snip_mcp_start = _header_line(snippet_lines, mcp_table)
        if snip_mcp_start is not None:
            snip_mcp_end = _block_end(snippet_lines, snip_mcp_start)
            block = snippet_lines[snip_mcp_start:snip_mcp_end]
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.extend(block)
            report["mcp_table_added"] = True

    merged = "\n".join(lines)
    if merged and not merged.endswith("\n"):
        merged += "\n"

    try:
        tomllib.loads(merged)
    except tomllib.TOMLDecodeError as exc:
        raise MergeError(f"merged config.toml would not parse: {exc}") from exc

    return merged, report


def merge_toml_file(target_path, snippet_path):
    target_path = Path(target_path)
    snippet_path = Path(snippet_path)

    if target_path.exists():
        original_text = target_path.read_text(encoding="utf-8")
        try:
            tomllib.loads(original_text)
        except tomllib.TOMLDecodeError as exc:
            raise MergeError(f"existing config.toml does not parse, refusing to merge: {exc}") from exc
    else:
        original_text = ""

    snippet_text = snippet_path.read_text(encoding="utf-8")

    backup_path = target_path.with_name(target_path.name + ".bak")
    if target_path.exists():
        shutil.copyfile(target_path, backup_path)

    merged, report = merge_toml_text(original_text, snippet_text)

    target_path.write_text(merged, encoding="utf-8")

    try:
        tomllib.loads(target_path.read_text(encoding="utf-8"))
    # Defense-in-depth check against I/O-level corruption (e.g., disk error) between write
    # and read. The primary safety guarantee—never write an unparseable result—is already
    # provided by merge_toml_text's pre-write tomllib.loads(merged) validation. This catch
    # is cheap insurance that's unlikely to ever trigger but worth keeping.
    except tomllib.TOMLDecodeError as exc:
        if backup_path.exists():
            shutil.copyfile(backup_path, target_path)
        raise MergeError(f"post-write validation failed, restored backup: {exc}") from exc

    return report


def main(argv):
    if len(argv) != 3:
        print("usage: merge_config.py <target-config.toml> <snippet.toml>", file=sys.stderr)
        return 2
    try:
        report = merge_toml_file(argv[1], argv[2])
    except MergeError as exc:
        print(f"merge_config.py: {exc}", file=sys.stderr)
        return 1
    for key, value in report.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
