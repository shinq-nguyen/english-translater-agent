import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from state_io import write_state  # noqa: E402
from verify_step import (  # noqa: E402
    check_dev_round,
    check_done,
    check_spec_ready,
    parse_bugs_table,
)

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "verify_step.py"

BUGS_HEADER = (
    "| ID | Area | Severity | Description | Status | Found in commit | Fixed in commit |\n"
    "|----|------|----------|--------------|--------|------------------|------------------|\n"
)


def test_parse_bugs_table_empty(tmp_path):
    path = tmp_path / "bugs.md"
    path.write_text(BUGS_HEADER, encoding="utf-8")
    assert parse_bugs_table(path) == []


def test_parse_bugs_table_missing_file_is_empty(tmp_path):
    assert parse_bugs_table(tmp_path / "nope.md") == []


def test_parse_bugs_table_reads_rows(tmp_path):
    path = tmp_path / "bugs.md"
    path.write_text(
        BUGS_HEADER + "| BUG-1 | BE | high | crashes | open | abc123 |  |\n",
        encoding="utf-8",
    )
    rows = parse_bugs_table(path)
    assert len(rows) == 1
    assert rows[0]["id"] == "BUG-1"
    assert rows[0]["status"] == "open"


def test_check_spec_ready_missing_file(tmp_path):
    state = {"ticket_id": "PROJ-1", "spec_file": "tickets/PROJ-1/PROJ-1-spec.md"}
    ok, reason = check_spec_ready(state, tmp_path)
    assert ok is False
    assert "spec" in reason.lower()


def test_check_spec_ready_present(tmp_path):
    spec = tmp_path / "tickets" / "PROJ-1" / "PROJ-1-spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# spec\n", encoding="utf-8")
    state = {"ticket_id": "PROJ-1", "spec_file": "tickets/PROJ-1/PROJ-1-spec.md"}
    ok, _ = check_spec_ready(state, tmp_path)
    assert ok is True


def test_check_dev_round_no_bugs_assigned_side_passes_without_commit(git_repo):
    state = {
        "base_branch": "main",
        "dev_round": {
            "round_id": 1,
            "be": {"status": "no_bugs_assigned", "commit": None, "bug_ids": []},
            "ui": {"status": "no_bugs_assigned", "commit": None, "bug_ids": []},
        },
    }
    ok, _ = check_dev_round(state, git_repo)
    assert ok is True


def test_check_dev_round_merged_side_requires_trailers_and_ancestry(git_repo, make_commit):
    sha = make_commit(
        git_repo,
        "backend.txt",
        "code\n",
        "[PROJ-1][dev-be] add endpoint",
        trailers={
            "Ticket-Workflow": "PROJ-1",
            "Ticket-Round": "1",
            "Ticket-Side": "be",
            "Ticket-Complete": "true",
        },
    )
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "dev_round": {
            "round_id": 1,
            "be": {"status": "merged", "commit": sha, "bug_ids": []},
            "ui": {"status": "no_bugs_assigned", "commit": None, "bug_ids": []},
        },
    }
    ok, reason = check_dev_round(state, git_repo)
    assert ok is True, reason


def test_check_dev_round_commit_without_completion_trailer_fails(git_repo, make_commit):
    sha = make_commit(git_repo, "backend.txt", "wip\n", "[PROJ-1][dev-be] wip")
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "dev_round": {
            "round_id": 1,
            "be": {"status": "merged", "commit": sha, "bug_ids": []},
            "ui": {"status": "no_bugs_assigned", "commit": None, "bug_ids": []},
        },
    }
    ok, reason = check_dev_round(state, git_repo)
    assert ok is False
    assert "trailer" in reason.lower()


def test_check_dev_round_merged_but_not_ancestor_of_base_fails(git_repo, make_commit):
    subprocess.run(["git", "-C", str(git_repo), "checkout", "-b", "side"], check=True)
    sha = make_commit(
        git_repo,
        "backend.txt",
        "code\n",
        "[PROJ-1][dev-be] add endpoint",
        trailers={
            "Ticket-Workflow": "PROJ-1",
            "Ticket-Round": "1",
            "Ticket-Side": "be",
            "Ticket-Complete": "true",
        },
    )
    subprocess.run(["git", "-C", str(git_repo), "checkout", "main"], check=True)
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "dev_round": {
            "round_id": 1,
            "be": {"status": "merged", "commit": sha, "bug_ids": []},
            "ui": {"status": "no_bugs_assigned", "commit": None, "bug_ids": []},
        },
    }
    ok, reason = check_dev_round(state, git_repo)
    assert ok is False
    assert "ancestor" in reason.lower() or "merge" in reason.lower()


def test_check_done_requires_passed_result_not_just_empty_bugs(git_repo):
    bugs = git_repo / "tickets" / "PROJ-1" / "bugs.md"
    bugs.parent.mkdir(parents=True)
    bugs.write_text(BUGS_HEADER, encoding="utf-8")
    head = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "bug_track_file": "tickets/PROJ-1/bugs.md",
        "test_report": {
            "commit": head,
            "result": "blocked",
            "acceptance_criteria_checked": True,
            "clean_before": True,
            "clean_after": True,
        },
    }
    ok, reason = check_done(state, git_repo)
    assert ok is False
    assert "blocked" in reason.lower() or "result" in reason.lower()


def test_check_done_passes_with_passed_result_matching_head(git_repo):
    bugs = git_repo / "tickets" / "PROJ-1" / "bugs.md"
    bugs.parent.mkdir(parents=True)
    bugs.write_text(BUGS_HEADER, encoding="utf-8")
    head = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "bug_track_file": "tickets/PROJ-1/bugs.md",
        "test_report": {
            "commit": head,
            "result": "passed",
            "acceptance_criteria_checked": True,
            "clean_before": True,
            "clean_after": True,
        },
    }
    ok, reason = check_done(state, git_repo)
    assert ok is True, reason


def test_check_done_fails_when_report_commit_is_stale(git_repo, make_commit):
    bugs = git_repo / "tickets" / "PROJ-1" / "bugs.md"
    bugs.parent.mkdir(parents=True)
    bugs.write_text(BUGS_HEADER, encoding="utf-8")
    stale_head = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    make_commit(git_repo, "later.txt", "x\n", "[PROJ-1][dev-be] later change")
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "bug_track_file": "tickets/PROJ-1/bugs.md",
        "test_report": {
            "commit": stale_head,
            "result": "passed",
            "acceptance_criteria_checked": True,
            "clean_before": True,
            "clean_after": True,
        },
    }
    ok, reason = check_done(state, git_repo)
    assert ok is False
    assert "stale" in reason.lower() or "commit" in reason.lower()


def test_check_done_fails_with_open_bug_row(git_repo):
    bugs = git_repo / "tickets" / "PROJ-1" / "bugs.md"
    bugs.parent.mkdir(parents=True)
    bugs.write_text(
        BUGS_HEADER + "| BUG-1 | BE | high | x | open | abc |  |\n", encoding="utf-8"
    )
    head = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "bug_track_file": "tickets/PROJ-1/bugs.md",
        "test_report": {
            "commit": head,
            "result": "passed",
            "acceptance_criteria_checked": True,
            "clean_before": True,
            "clean_after": True,
        },
    }
    ok, reason = check_done(state, git_repo)
    assert ok is False


def test_check_done_fails_closed_when_status_check_errors(git_repo):
    # `git rev-parse <branch>` only resolves a ref and works fine without a work
    # tree, but `git status` requires one. Flipping the repo to bare-mode after
    # the fact makes rev-parse keep succeeding while status errors out — this
    # isolates the returncode check on the `git status --porcelain` call itself,
    # independent of the earlier "commit is stale" check.
    head = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(git_repo), "config", "core.bare", "true"], check=True
    )
    state = {
        "ticket_id": "PROJ-1",
        "base_branch": "main",
        "bug_track_file": "tickets/PROJ-1/bugs.md",
        "test_report": {
            "commit": head,
            "result": "passed",
            "acceptance_criteria_checked": True,
            "clean_before": True,
            "clean_after": True,
        },
    }
    ok, reason = check_done(state, git_repo)
    assert ok is False
    assert "status" in reason.lower()


def test_cli_exits_nonzero_and_prints_reason_on_failure(tmp_path):
    write_state(tmp_path / "tickets" / "PROJ-1" / "state.json", {"ticket_id": "PROJ-1", "spec_file": "tickets/PROJ-1/PROJ-1-spec.md"})
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "PROJ-1", "spec_ready"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stdout.strip() != ""
