import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = PLUGIN_ROOT / "install.sh"
INSTALL_PS1 = PLUGIN_ROOT / "install.ps1"

# On Windows, resolve "bash" via a plain PATH scan (shutil.which) rather than
# passing the bare string to subprocess. Windows' native CreateProcess search
# order checks System32 *before* PATH, so a bare "bash" can resolve to the
# WSL launcher stub at C:\Windows\System32\bash.exe (which fails immediately
# if no WSL distro is registered) even though Git Bash's real bash.exe
# appears earlier in PATH. shutil.which does a straightforward PATH scan and
# correctly prefers Git Bash. On POSIX this is a no-op equivalent to "bash".
BASH_EXE = shutil.which("bash") or "bash"


def _init_target_repo(tmp_path):
    target = tmp_path / "target-repo"
    target.mkdir()
    subprocess.run(["git", "-C", str(target), "init", "-b", "main"], check=True)
    return target


def _run_install(target):
    if os.name == "nt":
        powershell = shutil.which("powershell") or "powershell"
        return subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(INSTALL_PS1),
            ],
            cwd=str(target),
            capture_output=True,
            text=True,
        )
    return subprocess.run(
        [BASH_EXE, str(INSTALL_SH)],
        cwd=str(target),
        capture_output=True,
        text=True,
    )


def test_install_copies_skill_agents_hooks(tmp_path):
    target = _init_target_repo(tmp_path)
    result = _run_install(target)
    assert result.returncode == 0, result.stderr

    assert (target / ".agents" / "skills" / "implement-ticket" / "SKILL.md").exists()
    for name in ("ticket-investigator", "ticket-be-dev", "ticket-ui-dev", "ticket-tester"):
        assert (target / ".codex" / "agents" / f"{name}.toml").exists()
    for name in ("state_io.py", "merge_config.py", "guard_ticket_commit.py", "ticket_audit.py", "verify_step.py"):
        assert (target / ".codex" / "hooks" / name).exists()


def test_install_merges_config_toml(tmp_path):
    target = _init_target_repo(tmp_path)
    (target / ".codex").mkdir()
    (target / ".codex" / "config.toml").write_text(
        'sandbox_mode = "workspace-write"\n', encoding="utf-8"
    )
    _run_install(target)

    parsed = tomllib.loads((target / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert parsed["features"]["rmcp_client"] is True
    assert parsed["mcp_servers"]["atlassian"]["url"] == "https://mcp.atlassian.com/v2/mcp"


def test_install_creates_config_toml_when_absent(tmp_path):
    target = _init_target_repo(tmp_path)
    _run_install(target)
    config_path = target / ".codex" / "config.toml"
    assert config_path.exists()
    tomllib.loads(config_path.read_text(encoding="utf-8"))


def test_install_merges_hooks_json_into_existing(tmp_path):
    # Real shape, matching this repo's own .codex/hooks.json: everything
    # nested under a top-level "hooks" key.
    target = _init_target_repo(tmp_path)
    (target / ".codex").mkdir()
    existing = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 x.py"}]}
            ]
        }
    }
    (target / ".codex" / "hooks.json").write_text(json.dumps(existing), encoding="utf-8")

    _run_install(target)

    merged = json.loads((target / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    pre_commands = [
        h["command"] for entry in merged["hooks"]["PreToolUse"] for h in entry["hooks"]
    ]
    pre_windows_commands = [
        h.get("command_windows")
        for entry in merged["hooks"]["PreToolUse"]
        for h in entry["hooks"]
    ]
    assert "python3 x.py" in pre_commands
    assert "python3 .codex/hooks/guard_ticket_commit.py" in pre_commands
    assert "python .codex/hooks/guard_ticket_commit.py" in pre_windows_commands
    assert "PostToolUse" in merged["hooks"]


def test_install_appends_gitignore_lines(tmp_path):
    target = _init_target_repo(tmp_path)
    (target / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    _run_install(target)

    content = (target / ".gitignore").read_text(encoding="utf-8")
    assert "tickets/" in content
    assert ".worktrees/" in content
    assert ".codex/tickets_active" in content
    assert "node_modules/" in content


def test_install_is_idempotent(tmp_path):
    target = _init_target_repo(tmp_path)
    _run_install(target)
    result = _run_install(target)
    assert result.returncode == 0, result.stderr

    content = (target / ".gitignore").read_text(encoding="utf-8")
    assert content.count("tickets/") == 1

    hooks = json.loads((target / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    pre_commands = [
        h["command"] for entry in hooks["hooks"]["PreToolUse"] for h in entry["hooks"]
    ]
    assert pre_commands.count("python3 .codex/hooks/guard_ticket_commit.py") == 1

    skill_dir = target / ".agents" / "skills" / "implement-ticket"
    assert (skill_dir / "SKILL.md").exists()
    assert not (skill_dir / "implement-ticket").exists(), (
        "second install run nested implement-ticket/implement-ticket/ "
        "instead of replacing the directory"
    )


def test_installed_hooks_resolve_workflow_root_with_no_argv(tmp_path):
    # Carried-forward requirement from Task 3's review (see progress.md):
    # guard_ticket_commit.py and ticket_audit.py's no-argv `workflow_root`
    # default assumes the script lives at <root>/.codex/hooks/<script>.py,
    # which is only true post-install. Exercise that exact path here: run
    # install.sh into a fresh target repo, then invoke the INSTALLED hook
    # scripts with NO argv (matching the literal hooks.json command lines
    # "python3 .codex/hooks/guard_ticket_commit.py" / "...ticket_audit.py"),
    # cwd set to the target repo root, and confirm workflow_root resolves to
    # the target repo root rather than crashing or resolving somewhere else.
    target = _init_target_repo(tmp_path)
    result = _run_install(target)
    assert result.returncode == 0, result.stderr

    (target / ".codex" / "tickets_active").write_text("PROJ-1\n", encoding="utf-8")

    # guard_ticket_commit.py: a commit message missing the required tag must
    # be denied, and the denial reason must name the active ticket read from
    # the INSTALLED target repo's own .codex/tickets_active (not some other
    # workflow_root) -- this proves parents[2] resolved to the target root.
    bad_event = {"tool_name": "Bash", "tool_input": {"command": "git commit -m \"no tag\""}}
    bad_result = subprocess.run(
        [sys.executable, ".codex/hooks/guard_ticket_commit.py"],
        cwd=str(target),
        input=json.dumps(bad_event),
        capture_output=True,
        text=True,
    )
    assert bad_result.returncode == 0, bad_result.stderr
    payload = json.loads(bad_result.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "PROJ-1" in payload["hookSpecificOutput"]["permissionDecisionReason"]

    # A correctly tagged commit message for the same active ticket must be
    # allowed (no stdout output at all).
    good_event = {
        "tool_name": "Bash",
        "tool_input": {"command": "git commit -m \"[PROJ-1][dev-be] add thing\""},
    }
    good_result = subprocess.run(
        [sys.executable, ".codex/hooks/guard_ticket_commit.py"],
        cwd=str(target),
        input=json.dumps(good_event),
        capture_output=True,
        text=True,
    )
    assert good_result.returncode == 0, good_result.stderr
    assert good_result.stdout.strip() == ""

    # ticket_audit.py: with no argv, it must resolve workflow_root to the
    # target repo root and write tickets/PROJ-1/audit.log THERE (not under
    # the plugin source tree or anywhere else).
    audit_event = {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
    }
    audit_result = subprocess.run(
        [sys.executable, ".codex/hooks/ticket_audit.py"],
        cwd=str(target),
        input=json.dumps(audit_event),
        capture_output=True,
        text=True,
    )
    assert audit_result.returncode == 0, audit_result.stderr

    log_path = target / "tickets" / "PROJ-1" / "audit.log"
    assert log_path.exists(), "ticket_audit.py did not resolve workflow_root to the target repo"
    log_content = log_path.read_text(encoding="utf-8")
    assert "ticket=PROJ-1" in log_content
    assert "session=sess-1" in log_content
