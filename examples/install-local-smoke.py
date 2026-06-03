#!/usr/bin/env python3
"""Smoke-test local installer wrapper and skill installation."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-local.sh"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="goal-harness-install-smoke-") as tmp:
        root = Path(tmp)
        home = root / "home"
        home.mkdir()
        bin_dir = home / ".local" / "bin"
        codex_home = home / ".codex"
        profile = home / ".zshrc"
        env = {
            **os.environ,
            "HOME": str(home),
            "CODEX_HOME": str(codex_home),
            "GOAL_HARNESS_BIN_DIR": str(bin_dir),
            "GOAL_HARNESS_SHELL_PROFILE": str(profile),
            "GOAL_HARNESS_INSTALL_SKILL": "1",
            "PATH": os.environ.get("PATH", ""),
            "SHELL": "/bin/zsh",
        }

        install = subprocess.run(
            [str(INSTALL_SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        assert "goal-harness installed locally" in install.stdout, install.stdout
        assert f"- executable: {bin_dir / 'goal-harness'}" in install.stdout, install.stdout
        assert f"- skill: {codex_home / 'skills' / 'goal-harness-project'}" in install.stdout, install.stdout

        wrapper = bin_dir / "goal-harness"
        assert wrapper.is_symlink(), wrapper
        assert wrapper.resolve() == REPO_ROOT / "scripts" / "goal-harness", wrapper.resolve()
        assert profile.read_text(encoding="utf-8").count("Goal Harness local CLI") == 1, profile.read_text()

        skill = codex_home / "skills" / "goal-harness-project" / "SKILL.md"
        skill_text = skill.read_text(encoding="utf-8")
        compact_skill_text = " ".join(skill_text.split())
        for phrase in (
            "Set Up Recurring Heartbeats",
            "goal-harness heartbeat-prompt",
            "run a short steering audit before choosing work",
            "at least three plausible next-action candidates",
            "continuation check",
            "compute quota separate from focus quota",
            "--source heartbeat --execute",
            "Generate A Review Packet",
            "goal-harness review-packet --goal-id",
            "goal-harness review-packet --goal-id <STABLE_GOAL_ID> --handoff-only",
            "goal-harness --format json review-packet --goal-id",
            "target project agent must not run this draft",
            "This command is read-only",
        ):
            assert phrase in compact_skill_text, phrase

        cli_env = {**env, "PATH": f"{bin_dir}:{env['PATH']}"}
        cli = subprocess.run(
            [
                "goal-harness",
                "--format",
                "json",
                "heartbeat-prompt",
                "--goal-id",
                "installer-smoke-goal",
                "--active-state",
                "/tmp/public-installer-smoke/ACTIVE_GOAL_STATE.md",
            ],
            cwd=REPO_ROOT,
            env=cli_env,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(cli.stdout)
        assert payload["ok"] is True, payload
        assert payload["quota_guard_command"] == (
            'goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" '
            "quota should-run --goal-id installer-smoke-goal"
        ), payload
        assert payload["quota_spend_command"] == (
            'goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" '
            "quota spend-slot --goal-id installer-smoke-goal --slots 1 --source heartbeat --execute"
        ), payload
        assert "DONT_NOTIFY" in payload["task_body"], payload

    print("install-local-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
