"""Real Git hooks: fast read paths must not weaken write or delegation fences."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from loopx.capabilities.repository_change_window import git_hook as owner
from loopx.capabilities.repository_change_window.policy import build_policy


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "empty-config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("LOOPX_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("LOOPX_REGISTRY", str(tmp_path / "registry.json"))
    source = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PYTHONPATH", str(source))
    binary = tmp_path / "bin"
    binary.mkdir()
    launcher = binary / "loopx"
    launcher.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m loopx.entrypoint "$@"\n'
    )
    launcher.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary}:/usr/bin:/bin:" + os.environ["PATH"])
    remote = tmp_path / "remote"
    subprocess.run(
        ["git", "init", "-b", "main", str(remote)], check=True, capture_output=True
    )

    def git(repo, *args, check=True):
        result = subprocess.run(
            ["git", "-C", str(repo), *args], check=False, capture_output=True, text=True
        )
        if check and result.returncode:
            pytest.fail(
                f"git {args!r} exited {result.returncode}:\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    git(remote, "config", "user.name", "Synthetic User")
    git(remote, "config", "user.email", "user@example.invalid")
    (remote / "file").write_text("base\n")
    git(remote, "add", "file")
    git(remote, "commit", "-m", "base")
    repo = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(remote), str(repo)], check=True, capture_output=True
    )
    git(repo, "config", "user.name", "Synthetic User")
    git(repo, "config", "user.email", "user@example.invalid")
    previous = tmp_path / "previous"
    previous.mkdir()
    hook = previous / "reference-transaction"
    hook.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$1" >> "'
        + str(tmp_path / "phases")
        + '"\ncat >> "'
        + str(tmp_path / "payloads")
        + '"\n'
    )
    hook.chmod(0o755)
    git(repo, "config", "core.hooksPath", str(previous))
    policy = build_policy(
        timezone_name="UTC",
        weekdays=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        blocked_start="00:00",
        blocked_end="23:59",
    )
    owner.install_git_hook_provider(
        repo_path=repo, policy=policy, enforcement_level="reference_guard", execute=True
    )
    return repo, remote, git, policy


def test_real_fetch_pull_quiet_and_new_commit_still_denied(installed, tmp_path):
    repo, remote, git, _policy = installed
    (remote / "file").write_text("remote advancement\n")
    git(remote, "commit", "-am", "advance")
    fetched = git(repo, "fetch", "origin")
    assert fetched.stdout == ""
    pulled = git(repo, "pull", "--ff-only")
    assert "repository_change_window" not in pulled.stdout + pulled.stderr
    assert (
        git(repo, "rev-parse", "HEAD").stdout == git(remote, "rev-parse", "HEAD").stdout
    )
    assert "prepared" in (tmp_path / "phases").read_text()
    assert "committed" in (tmp_path / "phases").read_text()
    assert "refs/remotes/origin/main" in (tmp_path / "payloads").read_text()
    # Actual detached worktree initialization must not require an existing HEAD.
    git(repo, "worktree", "add", "--detach", str(tmp_path / "linked"), "origin/main")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    tree = git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    candidate = git(
        repo, "commit-tree", tree, "-p", head, "-m", "new local commit"
    ).stdout.strip()
    denied = git(repo, "update-ref", "refs/heads/main", candidate, check=False)
    assert denied.returncode != 0
    assert "blocked_by_policy" in denied.stdout + denied.stderr
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == head
    denied_commit = git(
        repo,
        "commit",
        "--allow-empty",
        "--no-verify",
        "-m",
        "must be denied",
        check=False,
    )
    assert denied_commit.returncode != 0
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == head


def test_read_phases_skip_policy_but_preserve_drift_and_previous_hook(
    installed, tmp_path, monkeypatch
):
    repo, _remote, _git, _policy = installed

    def unexpected(*args, **kwargs):
        raise AssertionError("read-only hook evaluated the time policy")

    monkeypatch.setattr(owner, "evaluate_policy", unexpected)
    row = ("0" * 40 + " " + "1" * 40 + " refs/remotes/origin/example\n").encode()
    for phase in ("prepared", "committed", "aborted"):
        result = owner.run_git_hook_provider(
            repo_path=repo,
            runtime_root=tmp_path / "runtime",
            event="reference-transaction",
            hook_args=[phase],
            hook_stdin=row,
        )
        assert result["ok"] and not result["policy_evaluated"]
        assert result["decision"] is None
    previous = tmp_path / "previous" / "reference-transaction"
    previous.write_text("#!/bin/sh\necho previous-failure >&2\nexit 7\n")
    result = owner.run_git_hook_provider(
        repo_path=repo,
        runtime_root=tmp_path / "runtime",
        event="reference-transaction",
        hook_args=["prepared"],
        hook_stdin=row,
    )
    assert result["exit_code"] == 7 and result["status"] == "previous_hook_failed"
    managed = repo / ".git/loopx/repository-change-window/hooks/pre-push"
    managed.write_text("#!/bin/sh\nexit 0\n")
    result = owner.run_git_hook_provider(
        repo_path=repo,
        runtime_root=tmp_path / "runtime",
        event="reference-transaction",
        hook_args=["prepared"],
        hook_stdin=row,
    )
    assert result["status"] == "provider_drift"


def test_selected_cli_does_not_import_full_cli(installed):
    _repo, _remote, _git, _policy = installed
    program = 'import sys; from loopx.entrypoint import main; assert main(["--format","json","change-window","hook-runtime"]) == 0; assert "loopx.cli" not in sys.modules'
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("phase", ["preparing", "prepared"])
def test_empty_transaction_is_noop_but_keeps_hook_guards(
    installed, tmp_path, monkeypatch, phase
):
    repo, _remote, _git, _policy = installed

    def unexpected(*args, **kwargs):
        raise AssertionError("empty transaction evaluated the time policy")

    monkeypatch.setattr(owner, "evaluate_policy", unexpected)
    args = {
        "repo_path": repo,
        "runtime_root": tmp_path / "runtime",
        "event": "reference-transaction",
        "hook_args": [phase],
        "hook_stdin": b"",
    }
    result = owner.run_git_hook_provider(**args)
    assert result["ok"] and result["previous_hook_invoked"]
    assert not result["guarded_change"] and not result["policy_evaluated"]
    assert result["decision"] is None
    assert (tmp_path / "phases").read_text().splitlines() == [phase]
    assert (tmp_path / "payloads").read_bytes() == b""
    # An empty batch is legal; a nonempty malformed row is not.
    with pytest.raises(ValueError, match="at least one ref update"):
        owner.run_git_hook_provider(**{**args, "hook_stdin": b" \n"})
    previous = tmp_path / "previous" / "reference-transaction"
    previous.write_text("#!/bin/sh\nexit 7\n")
    result = owner.run_git_hook_provider(**args)
    assert result["status"] == "previous_hook_failed" and result["exit_code"] == 7
    managed = repo / ".git/loopx/repository-change-window/hooks/reference-transaction"
    managed.write_text(managed.read_text() + "# modified\n")
    assert owner.run_git_hook_provider(**args)["status"] == "provider_drift"


def test_old_valid_hook_generation_requires_explicit_refresh(installed):
    repo, _remote, _git, policy = installed
    state_path = repo / ".git/loopx/repository-change-window/provider.json"
    state = json.loads(state_path.read_text())
    for event in state["hook_digests"]:
        hook = state_path.parent / "hooks" / event
        old = hook.read_text().replace("export LOOPX_GIT_HOOK_QUIET_SUCCESS=1\n", "")
        hook.write_text(old)
        state["hook_digests"][event] = owner._digest_text(old)
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="--replace"):
        owner.install_git_hook_provider(
            repo_path=repo, policy=policy, enforcement_level="reference_guard"
        )
    refreshed = owner.install_git_hook_provider(
        repo_path=repo,
        policy=policy,
        enforcement_level="reference_guard",
        replace=True,
        execute=True,
    )
    assert refreshed["changed"]
    assert (
        "LOOPX_GIT_HOOK_QUIET_SUCCESS=1"
        in (state_path.parent / "hooks/reference-transaction").read_text()
    )
