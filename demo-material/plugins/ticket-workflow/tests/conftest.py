import subprocess
from pathlib import Path

import pytest


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def git_repo(tmp_path):
    """A throwaway git repo on branch 'main' with one initial commit.

    Includes a .gitignore for tickets/ and .worktrees/, matching the real
    target-repo setup install.sh produces (see Task 6's gitignore-snippet).
    Without this, files check_done writes under tickets/<id>/ (e.g. bugs.md)
    show up as untracked in `git status --porcelain`, which would trip the
    "checkout must be clean" check for a reason that has nothing to do with
    what the test is actually verifying — tickets/ is never meant to be
    tracked at all.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    (repo / ".gitignore").write_text("tickets/\n.worktrees/\n", encoding="utf-8")
    _git(repo, "add", "README.md", ".gitignore")
    _git(repo, "commit", "-m", "init")
    return repo


@pytest.fixture
def make_commit():
    def _make(repo, filename, content, message, trailers=None):
        (repo / filename).write_text(content, encoding="utf-8")
        _git(repo, "add", filename)
        full_message = message
        if trailers:
            full_message += "\n\n" + "\n".join(f"{k}: {v}" for k, v in trailers.items())
        _git(repo, "commit", "-m", full_message)
        return _git(repo, "rev-parse", "HEAD").stdout.strip()

    return _make
