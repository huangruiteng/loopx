#!/usr/bin/env python3
"""Check Codex CLI Goal host-local ACP first-action timeout policy."""

from __future__ import annotations

import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.skillsbench_automation_loop import (  # noqa: E402
    DEFAULT_CODEX_CLI_GOAL_ACTIVE_TIMEOUT_SEC,
    DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC,
    _effective_local_codex_first_action_timeout_sec,
    _effective_local_codex_goal_active_timeout_sec,
    _host_local_acp_launch_command,
    build_plan,
    parse_args,
)


def test_codex_cli_goal_first_action_timeout_defaults_to_bounded_watchdog() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-goal-timeout-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "civ6-adjacency-optimizer",
                "--route",
                "codex-cli-goal-baseline",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--agent-idle-timeout",
                "3600",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-cli-goal-timeout-fixture",
            ]
        )
        assert (
            _effective_local_codex_first_action_timeout_sec(args)
            == DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC
        )
        assert (
            _effective_local_codex_goal_active_timeout_sec(args)
            == DEFAULT_CODEX_CLI_GOAL_ACTIVE_TIMEOUT_SEC
        )
        command = _host_local_acp_launch_command(args, build_plan(args))
        assert (
            command[command.index("--first-action-timeout-sec") + 1]
            == str(DEFAULT_CODEX_CLI_GOAL_FIRST_ACTION_TIMEOUT_SEC)
        )
        assert (
            command[command.index("--goal-active-timeout-sec") + 1]
            == str(DEFAULT_CODEX_CLI_GOAL_ACTIVE_TIMEOUT_SEC)
        )
        assert "--codex-cli-goal-thread-prewarm" not in command

        disabled_args = parse_args(
            [
                "--task-id",
                "civ6-adjacency-optimizer",
                "--route",
                "codex-cli-goal-baseline",
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--local-codex-first-action-timeout-sec",
                "0",
                "--jobs-dir",
                str(Path(tmp) / "disabled-jobs"),
                "--job-name",
                "skillsbench-cli-goal-timeout-disabled-fixture",
            ]
        )
        assert _effective_local_codex_first_action_timeout_sec(disabled_args) == 0
        assert _effective_local_codex_goal_active_timeout_sec(disabled_args) == 0
        disabled_command = _host_local_acp_launch_command(
            disabled_args,
            build_plan(disabled_args),
        )
        assert (
            disabled_command[disabled_command.index("--goal-active-timeout-sec") + 1]
            == "0"
        )


if __name__ == "__main__":
    test_codex_cli_goal_first_action_timeout_defaults_to_bounded_watchdog()
    print("skillsbench-cli-goal-first-action-timeout-smoke: ok")
