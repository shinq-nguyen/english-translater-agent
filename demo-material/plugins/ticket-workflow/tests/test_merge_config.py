import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from merge_config import MergeError, merge_toml_file, merge_toml_text  # noqa: E402

SNIPPET = (
    "[features]\n"
    "rmcp_client = true\n"
    "\n"
    "[mcp_servers.atlassian]\n"
    'url = "https://mcp.atlassian.com/v2/mcp"\n'
)


def test_empty_target_gets_both_tables():
    merged, report = merge_toml_text("", SNIPPET)
    parsed = tomllib.loads(merged)
    assert parsed["features"]["rmcp_client"] is True
    assert parsed["mcp_servers"]["atlassian"]["url"] == "https://mcp.atlassian.com/v2/mcp"
    assert report["features_table_added"] is True
    assert report["mcp_table_added"] is True


def test_existing_features_table_without_key_gets_key_inserted():
    target = 'sandbox_mode = "workspace-write"\n\n[features]\nsome_other_flag = true\n'
    merged, report = merge_toml_text(target, SNIPPET)
    parsed = tomllib.loads(merged)
    assert parsed["features"]["some_other_flag"] is True
    assert parsed["features"]["rmcp_client"] is True
    assert report["features_table_added"] is False
    assert report["features_key_inserted"] is True
    # only one [features] header in the result
    assert merged.count("[features]") == 1


def test_existing_features_table_with_key_already_true_is_idempotent():
    target = "[features]\nrmcp_client = true\n"
    merged, report = merge_toml_text(target, SNIPPET)
    assert merged.count("rmcp_client") == 1
    assert report["features_key_inserted"] is False


def test_existing_mcp_atlassian_table_is_skipped_not_duplicated():
    target = '[mcp_servers.atlassian]\nurl = "https://old-url.example"\n'
    merged, report = merge_toml_text(target, SNIPPET)
    assert merged.count("[mcp_servers.atlassian]") == 1
    assert "old-url.example" in merged
    assert report["mcp_table_skipped_existing"] is True


def test_root_keys_before_first_table_rule_preserved():
    # The gotcha documented at the top of this repo's own .codex/config.toml:
    # root scalar keys must precede the first [table]. A correct merge must
    # never insert a table header before an existing root key.
    target = 'sandbox_mode = "workspace-write"\napproval_policy = "on-request"\n'
    merged, report = merge_toml_text(target, SNIPPET)
    lines = [l for l in merged.splitlines() if l.strip()]
    first_table_index = next(i for i, l in enumerate(lines) if l.startswith("["))
    assert all(not lines[i].startswith("[") for i in range(0, 2))
    assert lines[0] == 'sandbox_mode = "workspace-write"'
    assert lines[1] == 'approval_policy = "on-request"'
    assert first_table_index == 2


def test_merge_toml_file_writes_backup_and_result(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text('sandbox_mode = "workspace-write"\n', encoding="utf-8")
    snippet = tmp_path / "snippet.toml"
    snippet.write_text(SNIPPET, encoding="utf-8")

    report = merge_toml_file(target, snippet)

    assert report["features_table_added"] is True
    backup = target.with_name(target.name + ".bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == 'sandbox_mode = "workspace-write"\n'
    parsed = tomllib.loads(target.read_text(encoding="utf-8"))
    assert parsed["features"]["rmcp_client"] is True


def test_merge_toml_file_creates_new_config_when_none_exists(tmp_path):
    target = tmp_path / "config.toml"
    snippet = tmp_path / "snippet.toml"
    snippet.write_text(SNIPPET, encoding="utf-8")

    merge_toml_file(target, snippet)

    assert target.exists()
    assert not target.with_name(target.name + ".bak").exists()
    tomllib.loads(target.read_text(encoding="utf-8"))


def test_merge_toml_file_rejects_unparseable_base_without_modifying_it(tmp_path):
    target = tmp_path / "config.toml"
    broken = "sandbox_mode = \n[features\n"  # deliberately invalid TOML
    target.write_text(broken, encoding="utf-8")
    snippet = tmp_path / "snippet.toml"
    snippet.write_text(SNIPPET, encoding="utf-8")

    with pytest.raises(MergeError):
        merge_toml_file(target, snippet)

    assert target.read_text(encoding="utf-8") == broken


import pytest  # noqa: E402
