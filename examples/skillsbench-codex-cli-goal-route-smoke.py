#!/usr/bin/env python3
"""Smoke-test the canonical SkillsBench Codex CLI /goal route."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_runner(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/skillsbench_automation_loop.py", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _json_from_stderr(proc: subprocess.CompletedProcess[str]) -> dict[str, object]:
    try:
        payload = json.loads(proc.stderr)
    except json.JSONDecodeError as exc:
        raise AssertionError(proc.stderr) from exc
    assert isinstance(payload, dict), payload
    return payload


def _assert_app_server_goal_route_deprecated() -> None:
    proc = _run_runner("--route", "codex-app-server-goal-baseline")
    assert proc.returncode == 2, proc
    payload = _json_from_stderr(proc)
    assert payload["error_type"] == "SkillsBenchAppServerGoalRouteDeprecated", payload
    assert "codex-cli-goal-baseline" in str(payload["next_action"]), payload


def _assert_cli_goal_route_requires_materialized_solver_bridge() -> None:
    proc = _run_runner(
        "--route",
        "codex-cli-goal-baseline",
        "--host-local-acp-launch",
        "--remote-command-file-bridge-ready",
    )
    assert proc.returncode == 2, proc
    payload = _json_from_stderr(proc)
    assert payload["error_type"] == "SkillsBenchCodexCliGoalDriverRequired", payload
    assert payload["host_local_acp_launch"] is True, payload
    assert payload["remote_command_file_bridge_ready"] is True, payload
    assert payload["remote_command_file_bridge_solver_command_configured"] is False


def _assert_cli_goal_plan_and_relay_command() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_core.loop_protocol import CODEX_CLI_GOAL_BASELINE_ROUTE
    from scripts.skillsbench_automation_loop import (
        _host_local_acp_launch_command,
        build_plan,
        parse_args,
    )

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        skillsbench_root = temp_path / "skillsbench"
        (skillsbench_root / "tasks" / "react-performance-debugging").mkdir(
            parents=True
        )
        args = parse_args(
            [
                "--route",
                CODEX_CLI_GOAL_BASELINE_ROUTE,
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--remote-command-file-bridge-solver-command",
                "python bridge.py",
                "--reasoning-effort",
                "xhigh",
                "--plan-only",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(temp_path / "jobs"),
                "--ledger-path",
                str(temp_path / "ledger.json"),
                "--global-ledger-path",
                str(temp_path / "global-ledger.json"),
            ]
        )
        plan = build_plan(args)
        prerequisites = plan["runner_prerequisites"]
        assert plan["route"] == CODEX_CLI_GOAL_BASELINE_ROUTE, plan
        assert plan["agent"] == "codex-cli-goal", plan
        assert plan["codex_cli_reasoning_effort"] == "xhigh", plan
        assert prerequisites["container_codex_acp_install_skipped"] is True
        assert prerequisites["remote_command_file_bridge_command_configured"] is True
        assert (
            prerequisites["remote_command_file_bridge_agent_operation_trace_required"]
            is True
        )

        command = _host_local_acp_launch_command(args, plan)
        assert "--codex-cli-goal-worker" in command, command
        assert "--app-server-goal-worker" not in command, command
        assert "--reasoning-effort" in command, command
        assert command[command.index("--reasoning-effort") + 1] == "xhigh", command
        assert "--remote-command-file-bridge-command" in command, command
        bridge_index = command.index("--remote-command-file-bridge-command")
        assert command[bridge_index + 1] == "python bridge.py", command


def _assert_cli_goal_trace_merges_into_public_prerequisites() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_core.loop_protocol import CODEX_CLI_GOAL_BASELINE_ROUTE
    from scripts.skillsbench_automation_loop import (
        _merge_host_local_acp_relay_trace_summary,
        _public_runner_prerequisites,
    )

    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp)
        (trace_dir / "codex-cli-goal.compact.json").write_text(
            json.dumps(
                {
                    "schema_version": (
                        "skillsbench_host_local_acp_relay_public_trace_v0"
                    ),
                    "ok": True,
                    "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
                    "trace_kind": "codex_cli_goal_tui",
                    "codex_cli_goal": {
                        "schema_version": "skillsbench_codex_cli_goal_tui_v0",
                        "stage": "goal_achieved",
                        "goal_slash_command_submitted": True,
                        "goal_active_observed": True,
                        "goal_terminal_observed": True,
                        "first_action_observed": True,
                        "bridge_request_count": 2,
                        "task_facing_success_count": 1,
                        "reasoning_effort": "xhigh",
                        "raw_tui_capture_recorded": False,
                        "raw_task_text_recorded": False,
                        "raw_stdout_recorded": False,
                        "raw_stderr_recorded": False,
                        "credential_values_recorded": False,
                    },
                    "boundary": {
                        "raw_command_recorded": False,
                        "raw_stdout_recorded": False,
                        "raw_stderr_recorded": False,
                        "raw_task_text_recorded": False,
                        "raw_logs_recorded": False,
                        "raw_trajectory_recorded": False,
                        "credential_values_recorded": False,
                        "host_paths_recorded": False,
                        "remote_paths_recorded": False,
                        "upload_performed": False,
                        "submit_performed": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        plan = {
            "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {},
        }
        trace: dict[str, object] = {}
        _merge_host_local_acp_relay_trace_summary(plan, trace)

    prerequisites = plan["runner_prerequisites"]
    assert trace["codex_cli_goal_tui_trace_present"] is True, trace
    assert trace["codex_cli_goal_tui_ok_count"] == 1, trace
    assert trace["codex_cli_goal_tui_stage"] == "goal_achieved", trace
    assert trace["codex_cli_goal_tui_reasoning_effort"] == "xhigh", trace
    assert trace["codex_cli_goal_tui_task_facing_success_count"] == 1, trace
    assert trace["codex_cli_goal_tui_raw_material_recorded"] is False, trace
    assert prerequisites["codex_cli_goal_tui_trace_present"] is True, prerequisites
    assert prerequisites["codex_cli_goal_tui_goal_active_observed_count"] == 1
    assert prerequisites["codex_cli_goal_tui_task_facing_success_count"] == 1

    public_prerequisites = _public_runner_prerequisites(prerequisites)
    assert public_prerequisites["codex_cli_goal_tui_trace_present"] is True
    assert public_prerequisites["codex_cli_goal_tui_stage"] == "goal_achieved"
    assert public_prerequisites["codex_cli_goal_tui_reasoning_effort"] == "xhigh"
    assert public_prerequisites["codex_cli_goal_tui_goal_active_observed_count"] == 1
    assert public_prerequisites["codex_cli_goal_tui_task_facing_success_count"] == 1
    assert public_prerequisites["codex_cli_goal_tui_stages"] == ["goal_achieved"]


def main() -> int:
    _assert_app_server_goal_route_deprecated()
    _assert_cli_goal_route_requires_materialized_solver_bridge()
    _assert_cli_goal_plan_and_relay_command()
    _assert_cli_goal_trace_merges_into_public_prerequisites()
    print("skillsbench-codex-cli-goal-route-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
