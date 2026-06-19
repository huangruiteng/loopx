#!/usr/bin/env python3
"""Smoke-test the public fresh-clone quickstart path.

This intentionally starts from a git clone and an isolated HOME so the README
install path proves more than the current developer checkout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "fresh-clone-quickstart-smoke-goal"


def run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def run_goal_harness(
    *args: str,
    cwd: Path,
    env: dict[str, str],
) -> dict:
    result = run(["goal-harness", "--format", "json", *args], cwd=cwd, env=env)
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-fresh-clone-smoke-") as tmp:
        root = Path(tmp)
        clone = root / "goal-harness"
        run(
            ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(clone)],
            cwd=root,
            env=os.environ.copy(),
        )

        home = root / "home"
        bin_dir = home / ".local" / "bin"
        codex_home = home / ".codex"
        profile = home / ".zshrc"
        home.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "GOAL_HARNESS_BIN_DIR": str(bin_dir),
            "GOAL_HARNESS_SHELL_PROFILE": str(profile),
            "GOAL_HARNESS_INSTALL_SKILL": "1",
            "GOAL_HARNESS_INSTALL_CANARY": "1",
            "GOAL_HARNESS_RELEASE_ID": "fresh-clone-smoke-release",
            "PATH": os.environ.get("PATH", ""),
            "SHELL": "/bin/zsh",
        }

        install = run([str(clone / "scripts" / "install-local.sh")], cwd=clone, env=env)
        assert "goal-harness installed locally" in install.stdout, install.stdout
        assert f"- executable: {bin_dir / 'goal-harness'}" in install.stdout, install.stdout
        assert f"- canary executable: {bin_dir / 'goal-harness-canary'}" in install.stdout, install.stdout
        assert f"- skill: {codex_home / 'skills' / 'goal-harness-project'}" in install.stdout, install.stdout
        assert "promotion-readiness evidence is missing" in install.stderr, install.stderr
        assert "non-blocking" in install.stderr, install.stderr

        wrapper = bin_dir / "goal-harness"
        canary_wrapper = bin_dir / "goal-harness-canary"
        assert wrapper.is_symlink(), wrapper
        assert canary_wrapper.is_symlink(), canary_wrapper
        assert canary_wrapper.resolve() == clone.resolve() / "scripts" / "goal-harness", canary_wrapper.resolve()
        release_root = wrapper.resolve().parents[1]
        assert release_root != clone, release_root
        assert (release_root / "goal_harness" / "cli.py").is_file(), release_root
        assert (codex_home / "skills" / "goal-harness-project" / "SKILL.md").is_file()
        assert (codex_home / "skills" / "goal-harness-self-repair" / "SKILL.md").is_file()

        cli_env = {**env, "PATH": f"{bin_dir}:{env['PATH']}"}
        doctor = run_goal_harness("doctor", cwd=root, env=cli_env)
        assert doctor["ok"] is True, doctor
        assert doctor["path"]["goal_harness"] == str(wrapper), doctor
        assert doctor["path"]["goal_harness_canary"] == str(canary_wrapper), doctor
        assert doctor["package"]["release_root"] == str(release_root), doctor
        assert doctor["skills"]["goal-harness-project"]["exists"] is True, doctor
        assert doctor["skills"]["goal-harness-self-repair"]["exists"] is True, doctor

        project = root / "sample-project"
        project.mkdir()
        (project / "README.md").write_text(
            "# Sample Project\n\nUse Goal Harness to coordinate this sample goal.\n",
            encoding="utf-8",
        )
        bootstrap = run_goal_harness(
            "bootstrap",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
            "--objective",
            "Keep a sample project coordinated with Goal Harness.",
            "--domain",
            "fresh-clone-smoke",
            "--goal-doc",
            "README.md",
            "--no-global-sync",
            "--accept-onboarding-agent-todos",
            "--begin-autonomous-advance",
            cwd=project,
            env=cli_env,
        )
        assert bootstrap["ok"] is True, bootstrap
        assert bootstrap["goal_id"] == GOAL_ID, bootstrap
        assert (project / ".goal-harness" / "registry.json").is_file(), bootstrap
        assert (project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md").is_file(), bootstrap

        registry = project / ".goal-harness" / "registry.json"
        status = run_goal_harness("--registry", str(registry), "status", cwd=project, env=cli_env)
        assert status["ok"] is True, status
        assert status["status_contract"]["minimum_dashboard_schema_version"] >= 2, status
        assert status["attention_queue"]["item_count"] == 1, status
        assert status["attention_queue"]["items"][0]["goal_id"] == GOAL_ID, status

        check = run_goal_harness(
            "--registry",
            str(registry),
            "check",
            "--scan-root",
            str(project),
            cwd=project,
            env=cli_env,
        )
        assert check["ok"] is True, check
        assert check["summary"]["errors"] == 0, check

        heartbeat = run_goal_harness(
            "--registry",
            str(registry),
            "heartbeat-prompt",
            "--goal-id",
            GOAL_ID,
            cwd=project,
            env=cli_env,
        )
        assert heartbeat["ok"] is True, heartbeat
        assert "quota should-run" in heartbeat["quota_guard_command"], heartbeat
        assert "--source heartbeat --execute" in heartbeat["quota_spend_command"], heartbeat

    print("fresh-clone-quickstart-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
