#!/usr/bin/env python3
"""
Deterministic per-phase gate the Skill calls explicitly after each subagent
returns, before advancing state.json — NOT a Codex lifecycle hook.

CLI:
  python3 verify_step.py <workflow_root> <ticket-id> <phase>
Exit 0 = phase's requirements are satisfied; exit 1 = not yet, reason on
stdout. phase is one of: spec_ready, dev_round, done (dev_round covers both
the initial dev_in_progress round and every fixing round — same check).
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_io import read_state  # noqa: E402

REQUIRED_TRAILERS = ("Ticket-Workflow", "Ticket-Round", "Ticket-Side", "Ticket-Complete")


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )


def parse_bugs_table(path):
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or cells[0].lower() == "id":
            continue
        if set(cells[0]) <= {"-"}:
            continue
        if len(cells) < 5:
            continue
        rows.append(
            {
                "id": cells[0],
                "area": cells[1],
                "severity": cells[2],
                "description": cells[3],
                "status": cells[4],
                "found_commit": cells[5] if len(cells) > 5 else "",
                "fixed_commit": cells[6] if len(cells) > 6 else "",
            }
        )
    return rows


def check_spec_ready(state, workflow_root):
    spec_file = state.get("spec_file")
    if not spec_file:
        return False, "state.json has no spec_file recorded"
    path = Path(workflow_root) / spec_file
    if not path.exists():
        return False, f"spec file not found: {spec_file}"
    return True, "spec file present"


def _has_completion_trailers(repo, sha, ticket_id, round_id, side):
    result = _git(repo, "show", "-s", "--format=%B", sha)
    if result.returncode != 0:
        return False, f"commit {sha} not found in repo"
    body = result.stdout
    values_by_key = {
        "Ticket-Workflow": ticket_id,
        "Ticket-Round": str(round_id),
        "Ticket-Side": side,
        "Ticket-Complete": "true",
    }
    expected = {key: values_by_key[key] for key in REQUIRED_TRAILERS}
    for key, value in expected.items():
        if f"{key}: {value}" not in body:
            return False, f"commit {sha} missing trailer '{key}: {value}'"
    return True, "trailers present"


def check_dev_round(state, workflow_root):
    ticket_id = state.get("ticket_id")
    base_branch = state.get("base_branch")
    dev_round = state.get("dev_round") or {}
    round_id = dev_round.get("round_id")

    for side in ("be", "ui"):
        side_state = dev_round.get(side) or {}
        status = side_state.get("status")

        if status == "no_bugs_assigned":
            continue
        if status not in ("merged", "committed"):
            return False, f"{side} dev_round status is {status!r}, not yet complete"

        sha = side_state.get("commit")
        if not sha:
            return False, f"{side} has status {status!r} but no commit recorded"

        ok, reason = _has_completion_trailers(workflow_root, sha, ticket_id, round_id, side)
        if not ok:
            return False, f"{side}: {reason}"

        if status == "merged":
            result = _git(workflow_root, "merge-base", "--is-ancestor", sha, base_branch)
            if result.returncode == 1:
                return False, f"{side} commit {sha} is not an ancestor of {base_branch} (merge pending)"
            if result.returncode not in (0, 1):
                return False, f"{side} ancestry check errored: {result.stderr.strip()}"

    return True, "dev_round complete"


def check_done(state, workflow_root):
    ticket_id = state.get("ticket_id")
    base_branch = state.get("base_branch")
    bug_track_file = state.get("bug_track_file")
    report = state.get("test_report") or {}

    if report.get("result") != "passed":
        return False, f"test_report.result is {report.get('result')!r}, not 'passed'"

    for flag in ("acceptance_criteria_checked", "clean_before", "clean_after"):
        if not report.get(flag):
            return False, f"test_report.{flag} is not true"

    head = _git(workflow_root, "rev-parse", base_branch).stdout.strip()
    if not head or report.get("commit") != head:
        return False, (
            f"test_report.commit ({report.get('commit')}) is stale — "
            f"{base_branch} is now at {head}"
        )

    status_result = _git(workflow_root, "status", "--porcelain")
    if status_result.returncode != 0:
        return False, f"could not check checkout status: {status_result.stderr.strip()}"
    if status_result.stdout.strip():
        return False, "main checkout is not clean"

    if bug_track_file:
        rows = parse_bugs_table(Path(workflow_root) / bug_track_file)
        for row in rows:
            if row["status"] not in ("verified-fixed", "wont-fix"):
                return False, f"bug {row['id']} status is {row['status']!r}, not resolved"

    return True, f"done: {ticket_id} passed at {head}"


def main(argv):
    if len(argv) != 4:
        print("usage: verify_step.py <workflow_root> <ticket-id> <phase>", file=sys.stderr)
        return 2
    workflow_root, ticket_id, phase = Path(argv[1]), argv[2], argv[3]

    state = read_state(workflow_root / "tickets" / ticket_id / "state.json")
    if state is None:
        print(f"no state.json found for {ticket_id}")
        return 1

    checks = {
        "spec_ready": check_spec_ready,
        "dev_round": check_dev_round,
        "done": check_done,
    }
    check = checks.get(phase)
    if check is None:
        print(f"unknown phase: {phase}")
        return 2

    ok, reason = check(state, workflow_root)
    print(reason)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
