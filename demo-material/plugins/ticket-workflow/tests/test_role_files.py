import tomllib
import yaml  # noqa: E402  (only used by skill frontmatter test)
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
EXPECTED = ["ticket-investigator", "ticket-be-dev", "ticket-ui-dev", "ticket-tester"]
SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "implement-ticket" / "SKILL.md"


def test_all_four_role_files_exist_and_parse():
    for name in EXPECTED:
        path = AGENTS_DIR / f"{name}.toml"
        assert path.exists(), f"missing {path}"
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == name
        assert isinstance(data["description"], str) and data["description"]
        assert isinstance(data["developer_instructions"], str) and data["developer_instructions"]


def test_investigator_mentions_spec_file_and_no_jira_access():
    text = (AGENTS_DIR / "ticket-investigator.toml").read_text(encoding="utf-8")
    assert "spec" in text.lower()
    assert "jira" in text.lower()  # instructed that it does NOT call Jira itself


def test_dev_roles_mention_worktree_root_and_never_read_ticket():
    for name in ("ticket-be-dev", "ticket-ui-dev"):
        text = (AGENTS_DIR / f"{name}.toml").read_text(encoding="utf-8")
        assert "worktree_root" in text
        assert "spec" in text.lower()


def test_tester_mentions_ticket_not_spec():
    text = (AGENTS_DIR / "ticket-tester.toml").read_text(encoding="utf-8")
    assert "ticket" in text.lower()
    assert "bugs.md" in text or "bug" in text.lower()


def test_skill_file_has_valid_frontmatter():
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---", 4)
    frontmatter = yaml.safe_load(text[4:end])
    assert frontmatter["name"] == "implement-ticket"
    assert isinstance(frontmatter["description"], str) and frontmatter["description"]


def test_skill_mentions_all_four_subagents_and_verify_step():
    text = SKILL_PATH.read_text(encoding="utf-8")
    for name in ("ticket-investigator", "ticket-be-dev", "ticket-ui-dev", "ticket-tester"):
        assert name in text
    assert "verify_step.py" in text
    assert "state_io.py" in text
