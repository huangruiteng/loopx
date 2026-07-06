#!/usr/bin/env python3
"""Smoke-test the canonical SkillsBench Codex CLI /goal route."""

from __future__ import annotations

import json
import contextlib
import io
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
    )
    assert proc.returncode == 2, proc
    payload = _json_from_stderr(proc)
    assert payload["error_type"] == "SkillsBenchCodexCliGoalDriverRequired", payload
    assert payload["host_local_acp_launch"] is True, payload
    assert payload["remote_command_file_bridge_ready"] is False, payload
    assert payload["remote_command_file_bridge_solver_command_configured"] is False
    assert payload["remote_command_file_bridge_sandbox_auto_wiring_pending"] is False

    # The real Docker bridge command is only available after BenchFlow creates
    # the scored sandbox, so this route must allow the auto-wiring state.
    proc = _run_runner(
        "--route",
        "codex-cli-goal-baseline",
        "--host-local-acp-launch",
        "--remote-command-file-bridge-ready",
        "--plan-only",
    )
    assert proc.returncode == 0, proc
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True, payload
    prereq = payload["launch_plan"]["runner_prerequisites"]
    assert prereq["remote_command_file_bridge_materialized"] is True, prereq
    assert (
        prereq["remote_command_file_bridge_consumption_status"]
        == "sandbox_bridge_auto_wiring_pending"
    ), prereq
    assert prereq["remote_command_file_bridge_agent_operation_trace_required"] is True


def _assert_cli_goal_plan_and_relay_command() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_core.loop_protocol import CODEX_CLI_GOAL_BASELINE_ROUTE
    from loopx.benchmark_adapters.skillsbench import skillsbench_route_contract
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
        assert plan["codex_api_egress_preflight"]["required"] is True, plan
        assert plan["codex_api_egress_preflight"]["resolved_mode"] == (
            "reverse-tunnel"
        ), plan
        contract = skillsbench_route_contract(CODEX_CLI_GOAL_BASELINE_ROUTE)
        prerequisites = plan["runner_prerequisites"]
        assert plan["route"] == CODEX_CLI_GOAL_BASELINE_ROUTE, plan
        assert plan["agent"] == "codex-cli-goal", plan
        assert contract["arm_id"] == "codex_cli_goal_baseline", contract
        assert contract["native_goal_mode_invoked"] is True, contract
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
        assert "--goal-active-timeout-sec" in command, command
        assert (
            command[command.index("--goal-active-timeout-sec") + 1]
            == command[command.index("--first-action-timeout-sec") + 1]
        ), command

        proxy_url = "http://127.0.0.1:18182"
        args_with_proxy = parse_args(
            [
                "--route",
                CODEX_CLI_GOAL_BASELINE_ROUTE,
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--remote-command-file-bridge-solver-command",
                "python bridge.py",
                "--reasoning-effort",
                "xhigh",
                "--codex-api-reverse-tunnel-proxy",
                proxy_url,
                "--plan-only",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(temp_path / "jobs-with-proxy"),
                "--ledger-path",
                str(temp_path / "ledger-with-proxy.json"),
                "--global-ledger-path",
                str(temp_path / "global-ledger-with-proxy.json"),
            ]
        )
        proxy_plan = build_plan(args_with_proxy)
        proxy_command = _host_local_acp_launch_command(args_with_proxy, proxy_plan)
        assert "--codex-api-proxy" in proxy_command, proxy_command
        proxy_index = proxy_command.index("--codex-api-proxy")
        assert proxy_command[proxy_index + 1] == proxy_url, proxy_command
        assert proxy_url not in json.dumps(proxy_plan, sort_keys=True), proxy_plan

        retry_args = parse_args(
            [
                "--route",
                CODEX_CLI_GOAL_BASELINE_ROUTE,
                "--host-local-acp-launch",
                "--remote-command-file-bridge-ready",
                "--remote-command-file-bridge-solver-command",
                "python bridge.py",
                "--independent-goal-retries",
                "2",
                "--plan-only",
                "--skillsbench-root",
                str(skillsbench_root),
                "--jobs-dir",
                str(temp_path / "jobs-with-retry"),
                "--ledger-path",
                str(temp_path / "ledger-with-retry.json"),
                "--global-ledger-path",
                str(temp_path / "global-ledger-with-retry.json"),
            ]
        )
        retry_plan = build_plan(retry_args)
        retry_config = retry_plan["independent_goal_retry"]
        assert retry_config["enabled"] is True, retry_config
        assert retry_config["attempt_budget"] == 2, retry_config
        assert retry_config["route_supported"] is True, retry_config

        try:
            with contextlib.redirect_stderr(io.StringIO()):
                parse_args(
                    [
                        "--route",
                        CODEX_CLI_GOAL_BASELINE_ROUTE,
                        "--host-local-acp-launch",
                        "--remote-command-file-bridge-ready",
                        "--remote-command-file-bridge-solver-command",
                        "python bridge.py",
                        "--independent-goal-retries",
                        "2",
                        "--task-ids",
                        "react-performance-debugging,citation-check",
                        "--plan-only",
                        "--skillsbench-root",
                        str(skillsbench_root),
                        "--jobs-dir",
                        str(temp_path / "jobs-with-invalid-retry"),
                        "--ledger-path",
                        str(temp_path / "ledger-with-invalid-retry.json"),
                        "--global-ledger-path",
                        str(temp_path / "global-ledger-with-invalid-retry.json"),
                    ]
                )
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("multi-case independent retries should be rejected")


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


def _assert_cli_goal_tui_ready_wait_tolerates_startup_warnings() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    import loopx.codex_cli_goal_tui as goal_tui

    captures = iter(
        [
            "",
            "Codex startup\nMCP server failed: HTTP request failed\n› \n",
        ]
    )

    def fake_capture(_tmux_name: str) -> str:
        try:
            return next(captures)
        except StopIteration:
            return "Codex startup\nMCP server failed: HTTP request failed\n› \n"

    original_capture = goal_tui.tmux_capture
    try:
        goal_tui.tmux_capture = fake_capture  # type: ignore[assignment]
        assert goal_tui.wait_for_codex_cli_tui_ready(
            "fake-session",
            timeout_sec=1.0,
        )
    finally:
        goal_tui.tmux_capture = original_capture  # type: ignore[assignment]


def _assert_cli_goal_paste_submit_falls_back_to_plain_enter() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    import loopx.codex_cli_goal_tui as goal_tui

    prompt_text = "Start this persisted Codex thread."
    assert goal_tui.codex_cli_tui_active_input_prompt_contains(
        f"Header\n› {prompt_text}\n",
        prompt_text,
    )
    assert not goal_tui.codex_cli_tui_active_input_prompt_contains(
        f"User message: {prompt_text}\nThinking\n",
        prompt_text,
    )

    calls: list[object] = []

    def fake_run(args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_submit(tmux_name: str) -> None:
        calls.append(("kitty-enter", tmux_name))

    def fake_plain_enter(tmux_name: str) -> None:
        calls.append(("plain-enter", tmux_name))

    def fake_capture(_tmux_name: str) -> str:
        return f"Codex\n› {prompt_text}\n"

    original_run = goal_tui.subprocess.run
    original_sleep = goal_tui.time.sleep
    original_submit = goal_tui.tmux_submit_enter
    original_plain_enter = goal_tui.tmux_send_plain_enter
    original_capture = goal_tui.tmux_capture
    try:
        goal_tui.subprocess.run = fake_run  # type: ignore[assignment]
        goal_tui.time.sleep = lambda _seconds: None  # type: ignore[assignment]
        goal_tui.tmux_submit_enter = fake_submit  # type: ignore[assignment]
        goal_tui.tmux_send_plain_enter = fake_plain_enter  # type: ignore[assignment]
        goal_tui.tmux_capture = fake_capture  # type: ignore[assignment]
        with tempfile.TemporaryDirectory() as temp:
            prompt_path = Path(temp) / "prompt.txt"
            prompt_path.write_text(prompt_text, encoding="utf-8")
            goal_tui.tmux_paste_file_and_submit(
                tmux_name="fake-session",
                prompt_path=prompt_path,
                buffer_suffix="prewarm",
            )
    finally:
        goal_tui.subprocess.run = original_run  # type: ignore[assignment]
        goal_tui.time.sleep = original_sleep  # type: ignore[assignment]
        goal_tui.tmux_submit_enter = original_submit  # type: ignore[assignment]
        goal_tui.tmux_send_plain_enter = original_plain_enter  # type: ignore[assignment]
        goal_tui.tmux_capture = original_capture  # type: ignore[assignment]

    assert ("kitty-enter", "fake-session") in calls, calls
    assert ("plain-enter", "fake-session") in calls, calls


def _assert_cli_goal_typed_submit_avoids_paste_buffer() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    import loopx.codex_cli_goal_tui as goal_tui

    goal_text = "/goal Complete the task using ./skillsbench-task-prompt.md"
    calls: list[object] = []

    def fake_run(args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0)

    def fake_submit(tmux_name: str) -> None:
        calls.append(("kitty-enter", tmux_name))

    def fake_plain_enter(tmux_name: str) -> None:
        calls.append(("plain-enter", tmux_name))

    def fake_capture(_tmux_name: str) -> str:
        return f"Codex\n› {goal_text}\n"

    original_run = goal_tui.subprocess.run
    original_sleep = goal_tui.time.sleep
    original_submit = goal_tui.tmux_submit_enter
    original_plain_enter = goal_tui.tmux_send_plain_enter
    original_capture = goal_tui.tmux_capture
    try:
        goal_tui.subprocess.run = fake_run  # type: ignore[assignment]
        goal_tui.time.sleep = lambda _seconds: None  # type: ignore[assignment]
        goal_tui.tmux_submit_enter = fake_submit  # type: ignore[assignment]
        goal_tui.tmux_send_plain_enter = fake_plain_enter  # type: ignore[assignment]
        goal_tui.tmux_capture = fake_capture  # type: ignore[assignment]
        goal_tui.tmux_type_text_and_submit(
            tmux_name="fake-session",
            text=goal_text,
        )
    finally:
        goal_tui.subprocess.run = original_run  # type: ignore[assignment]
        goal_tui.time.sleep = original_sleep  # type: ignore[assignment]
        goal_tui.tmux_submit_enter = original_submit  # type: ignore[assignment]
        goal_tui.tmux_send_plain_enter = original_plain_enter  # type: ignore[assignment]
        goal_tui.tmux_capture = original_capture  # type: ignore[assignment]

    assert any(
        isinstance(call, list)
        and call[:5] == ["tmux", "send-keys", "-t", "fake-session", "-l"]
        and call[-1] == goal_text
        for call in calls
    ), calls
    assert ("kitty-enter", "fake-session") in calls, calls
    assert ("plain-enter", "fake-session") in calls, calls
    assert not any(
        isinstance(call, list)
        and any(part in {"load-buffer", "paste-buffer"} for part in call)
        for call in calls
    ), calls


def _assert_cli_goal_rate_limit_is_public_safe_retryable_stage() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
        _codex_cli_tui_retryable_startup_blocker_stage,
    )
    from scripts.skillsbench_automation_loop import (
        _merge_host_local_acp_relay_trace_summary,
        _public_runner_prerequisites,
    )

    assert (
        _codex_cli_tui_retryable_startup_blocker_stage(
            "Codex CLI\nrate limit reached\n› "
        )
        == "rate_limit_before_goal_active"
    )
    assert _codex_cli_tui_retryable_startup_blocker_stage("Goal active") == ""

    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp) / "trace"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="rate_limit_before_goal_active",
            goal_active_observed=False,
            goal_terminal_observed=False,
            first_action_observed=False,
            bridge_summary_path=None,
        )
        plan = {
            "route": "codex-cli-goal-baseline",
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {},
        }
        trace: dict[str, object] = {}
        _merge_host_local_acp_relay_trace_summary(plan, trace)

    prerequisites = plan["runner_prerequisites"]
    assert trace["codex_cli_goal_tui_trace_present"] is True, trace
    assert trace["codex_cli_goal_tui_ok_count"] == 0, trace
    assert trace["codex_cli_goal_tui_stage"] == "rate_limit_before_goal_active"
    assert trace["codex_cli_goal_tui_goal_active_observed_count"] == 0
    assert trace["codex_cli_goal_tui_first_action_observed_count"] == 0
    assert trace["codex_cli_goal_tui_raw_material_recorded"] is False, trace

    public_prerequisites = _public_runner_prerequisites(prerequisites)
    assert public_prerequisites["codex_cli_goal_tui_stage"] == (
        "rate_limit_before_goal_active"
    )
    assert public_prerequisites["codex_cli_goal_tui_stages"] == [
        "rate_limit_before_goal_active"
    ]


def _assert_cli_goal_post_bridge_blocker_is_public_safe_stage() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
    )
    from loopx.benchmark_adapters.skillsbench_codex_goal_recovery import (
        CODEX_CLI_GOAL_POST_BRIDGE_CLOSEOUT_PROMPT,
        POST_BRIDGE_CLOSEOUT_ATTEMPT_LIMIT,
        POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
        PRE_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
        codex_cli_tui_post_bridge_blocker_stage,
        codex_cli_tui_post_bridge_closeout_recovery_action,
        codex_cli_tui_post_bridge_recovery_action,
        codex_cli_tui_post_bridge_recovery_skip_reason,
        codex_cli_tui_pre_bridge_blocker_stage,
        codex_cli_tui_pre_bridge_recovery_action,
        codex_cli_tui_pre_bridge_recovery_skip_reason,
    )
    from scripts.skillsbench_automation_loop import (
        _merge_host_local_acp_relay_trace_summary,
        _public_runner_prerequisites,
    )

    assert POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT == 6
    assert POST_BRIDGE_CLOSEOUT_ATTEMPT_LIMIT == 8
    assert PRE_BRIDGE_RECOVERY_ATTEMPT_LIMIT == 2
    assert "Close out the active SkillsBench goal" in (
        CODEX_CLI_GOAL_POST_BRIDGE_CLOSEOUT_PROMPT
    )
    assert (
        codex_cli_tui_pre_bridge_blocker_stage(
            "request timed out while waiting for model\n› ",
            prompt_visible=True,
        )
        == "pre_bridge_tui_model_timeout"
    )
    assert (
        codex_cli_tui_pre_bridge_recovery_action(
            "request timed out while waiting for model\npress enter to retry\n› ",
            stage="pre_bridge_tui_model_timeout",
        )
        == "press_enter"
    )
    assert (
        codex_cli_tui_pre_bridge_recovery_action(
            "request timed out while waiting for model\n› ",
            stage="pre_bridge_tui_model_timeout",
        )
        == "typed_goal_resubmit"
    )
    assert (
        codex_cli_tui_pre_bridge_recovery_skip_reason(
            "rate limit reached\npress enter to retry\n› ",
            stage="pre_bridge_tui_rate_limit",
            recovery_action="",
        )
        == "rate_limit_no_retry"
    )
    assert (
        codex_cli_tui_pre_bridge_blocker_stage(
            "request timed out while waiting for model\n",
            prompt_visible=False,
        )
        == ""
    )
    assert (
        codex_cli_tui_post_bridge_blocker_stage(
            "request timed out while waiting for model\n› ",
            prompt_visible=True,
        )
        == "post_bridge_tui_model_timeout"
    )
    assert (
        codex_cli_tui_post_bridge_recovery_action(
            "request timed out while waiting for model\npress enter to retry\n› ",
            stage="post_bridge_tui_model_timeout",
        )
        == "press_enter"
    )
    assert (
        codex_cli_tui_post_bridge_recovery_action(
            "request timed out while waiting for model\n› ",
            stage="post_bridge_tui_model_timeout",
        )
        == "typed_continue"
    )
    assert (
        codex_cli_tui_post_bridge_recovery_skip_reason(
            "request timed out while waiting for model\n› ",
            stage="post_bridge_tui_model_timeout",
            recovery_action="typed_continue",
        )
        == ""
    )
    assert (
        codex_cli_tui_post_bridge_recovery_action(
            "rate limit reached\npress enter to retry\n› ",
            stage="post_bridge_tui_rate_limit",
        )
        == ""
    )
    assert (
        codex_cli_tui_post_bridge_recovery_skip_reason(
            "rate limit reached\npress enter to retry\n› ",
            stage="post_bridge_tui_rate_limit",
            recovery_action="",
        )
        == "rate_limit_no_retry"
    )
    assert (
        codex_cli_tui_post_bridge_recovery_skip_reason(
            "request timed out while waiting for model\npress enter to retry\n› ",
            stage="post_bridge_tui_model_timeout",
            recovery_action="press_enter",
        )
        == ""
    )
    assert (
        codex_cli_tui_post_bridge_closeout_recovery_action(
            recovery_action="typed_continue",
            recovery_attempt_count=POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
            closeout_attempted=False,
        )
        == "typed_closeout"
    )
    assert (
        codex_cli_tui_post_bridge_closeout_recovery_action(
            recovery_action="typed_continue",
            recovery_attempt_count=POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
            closeout_attempted=True,
        )
        == "typed_closeout"
    )
    assert (
        codex_cli_tui_post_bridge_closeout_recovery_action(
            recovery_action="typed_continue",
            recovery_attempt_count=POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
            closeout_attempted=True,
            closeout_attempt_count=POST_BRIDGE_CLOSEOUT_ATTEMPT_LIMIT,
        )
        == ""
    )
    assert (
        codex_cli_tui_post_bridge_blocker_stage(
            "rate limit reached\n› ",
            prompt_visible=True,
        )
        == "post_bridge_tui_rate_limit"
    )
    assert (
        codex_cli_tui_post_bridge_blocker_stage(
            "rate limit reached\n",
            prompt_visible=False,
        )
        == ""
    )

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        trace_dir = temp_path / "trace"
        bridge_summary = temp_path / "remote-bridge-agent-ops.jsonl"
        bridge_summary.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "record_phase": "start",
                            "task_facing_operation": True,
                        }
                    ),
                    json.dumps(
                        {
                            "record_phase": "complete",
                            "task_facing_operation": True,
                            "success": True,
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="post_bridge_tui_error_prompt",
            goal_active_observed=False,
            goal_terminal_observed=False,
            first_action_observed=True,
            bridge_summary_path=bridge_summary,
            post_bridge_recovery_attempt_count=1,
            post_bridge_recovery_action="press_enter",
        )
        plan = {
            "route": "codex-cli-goal-baseline",
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {},
        }
        trace: dict[str, object] = {}
        _merge_host_local_acp_relay_trace_summary(plan, trace)

    prerequisites = plan["runner_prerequisites"]
    assert trace["codex_cli_goal_tui_trace_present"] is True, trace
    assert trace["codex_cli_goal_tui_stage"] == "post_bridge_tui_error_prompt"
    assert trace["codex_cli_goal_tui_stages"] == ["post_bridge_tui_error_prompt"]
    assert trace["codex_cli_goal_tui_first_action_observed_count"] == 1
    assert trace["codex_cli_goal_tui_task_facing_success_count"] == 1
    assert trace["codex_cli_goal_tui_post_bridge_recovery_attempt_count"] == 1
    assert trace["codex_cli_goal_tui_post_bridge_recovery_action"] == "press_enter"
    assert trace["codex_cli_goal_tui_post_bridge_recovery_skip_reason"] == ""
    assert trace["codex_cli_goal_tui_raw_material_recorded"] is False, trace

    public_prerequisites = _public_runner_prerequisites(prerequisites)
    assert public_prerequisites["codex_cli_goal_tui_stage"] == (
        "post_bridge_tui_error_prompt"
    )
    assert public_prerequisites["codex_cli_goal_tui_stages"] == [
        "post_bridge_tui_error_prompt"
    ]
    assert public_prerequisites["codex_cli_goal_tui_task_facing_success_count"] == 1
    assert (
        public_prerequisites["codex_cli_goal_tui_post_bridge_recovery_attempt_count"]
        == 1
    )
    assert (
        public_prerequisites["codex_cli_goal_tui_post_bridge_recovery_action"]
        == "press_enter"
    )

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        trace_dir = temp_path / "trace"
        bridge_summary = temp_path / "remote-bridge-agent-ops.jsonl"
        bridge_summary.write_text(
            json.dumps(
                {
                    "record_phase": "complete",
                    "task_facing_operation": True,
                    "success": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="post_bridge_tui_model_timeout",
            goal_active_observed=False,
            goal_terminal_observed=False,
            first_action_observed=True,
            bridge_summary_path=bridge_summary,
            post_bridge_recovery_attempt_count=POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT,
            post_bridge_recovery_action="typed_closeout",
            post_bridge_recovery_skip_reason="closeout_retry_limit_reached",
        )
        plan = {
            "route": "codex-cli-goal-baseline",
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {},
        }
        trace = {}
        _merge_host_local_acp_relay_trace_summary(plan, trace)

    prerequisites = plan["runner_prerequisites"]
    assert trace["codex_cli_goal_tui_stage"] == "post_bridge_tui_model_timeout"
    assert (
        trace["codex_cli_goal_tui_post_bridge_recovery_attempt_count"]
        == POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT
    )
    assert trace["codex_cli_goal_tui_post_bridge_recovery_action"] == "typed_closeout"
    assert (
        trace["codex_cli_goal_tui_post_bridge_recovery_skip_reason"]
        == "closeout_retry_limit_reached"
    )
    assert trace["codex_cli_goal_tui_post_bridge_recovery_skip_reasons"] == [
        "closeout_retry_limit_reached"
    ]
    public_prerequisites = _public_runner_prerequisites(prerequisites)
    assert (
        public_prerequisites["codex_cli_goal_tui_post_bridge_recovery_action"]
        == "typed_closeout"
    )
    assert (
        public_prerequisites[
            "codex_cli_goal_tui_post_bridge_recovery_skip_reason"
        ]
        == "closeout_retry_limit_reached"
    )
    assert public_prerequisites[
        "codex_cli_goal_tui_post_bridge_recovery_skip_reasons"
    ] == ["closeout_retry_limit_reached"]


def _assert_cli_goal_active_timeout_is_public_countability_stage() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
    )
    from loopx.benchmark_core.loop_protocol import CODEX_CLI_GOAL_BASELINE_ROUTE
    from scripts.skillsbench_automation_loop import (
        _apply_codex_cli_goal_countability_guard_attribution,
        _merge_host_local_acp_relay_trace_summary,
        _public_runner_prerequisites,
    )

    assert CodexExecConfig().goal_active_timeout_sec > 0

    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp) / "trace"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="goal_active_timeout",
            goal_active_observed=False,
            goal_terminal_observed=False,
            first_action_observed=False,
            bridge_summary_path=None,
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
    assert trace["codex_cli_goal_tui_stage"] == "goal_active_timeout", trace
    assert trace["codex_cli_goal_tui_goal_active_observed_count"] == 0
    assert trace["codex_cli_goal_tui_first_action_observed_count"] == 0
    assert trace["codex_cli_goal_tui_raw_material_recorded"] is False, trace

    public_prerequisites = _public_runner_prerequisites(prerequisites)
    assert public_prerequisites["codex_cli_goal_tui_stage"] == (
        "goal_active_timeout"
    )
    assert public_prerequisites["codex_cli_goal_tui_stages"] == [
        "goal_active_timeout"
    ]

    compact = {
        "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
        "official_score_status": "completed",
        "interaction_counters": trace,
        "runner_prerequisites": prerequisites,
        "failure_attribution_labels": ["official_score_zero_case_failure"],
    }
    assert _apply_codex_cli_goal_countability_guard_attribution(compact) is True
    assert compact["score_failure_attribution"] == (
        "skillsbench_codex_cli_goal_uncountable_goal_active_timeout"
    )
    contract = compact["codex_cli_goal_countability_contract"]
    assert contract["goal_stage"] == "goal_active_timeout", contract
    assert contract["raw_material_recorded"] is False, contract

    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp) / "trace"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="pre_bridge_tui_model_timeout",
            goal_active_observed=False,
            goal_terminal_observed=False,
            first_action_observed=False,
            bridge_summary_path=None,
            post_bridge_recovery_attempt_count=2,
            post_bridge_recovery_action="typed_goal_resubmit",
            post_bridge_recovery_skip_reason="retry_limit_reached",
        )
        plan = {
            "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {},
        }
        trace = {}
        _merge_host_local_acp_relay_trace_summary(plan, trace)

    compact = {
        "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
        "official_score_status": "completed",
        "interaction_counters": trace,
        "runner_prerequisites": plan["runner_prerequisites"],
        "failure_attribution_labels": ["official_score_zero_case_failure"],
    }
    assert _apply_codex_cli_goal_countability_guard_attribution(compact) is True
    assert compact["score_failure_attribution"] == (
        "skillsbench_codex_cli_goal_uncountable_pre_bridge_model_timeout"
    )
    assert (
        trace["codex_cli_goal_tui_post_bridge_recovery_action"]
        == "typed_goal_resubmit"
    )
    contract = compact["codex_cli_goal_countability_contract"]
    assert contract["goal_stage"] == "pre_bridge_tui_model_timeout", contract

    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp) / "trace"
        bridge_summary = Path(temp) / "bridge-summary.jsonl"
        bridge_summary.write_text(
            json.dumps({"record_phase": "start", "task_facing_operation": True})
            + "\n"
            + json.dumps(
                {
                    "record_phase": "complete",
                    "task_facing_operation": True,
                    "success": True,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="goal_failed",
            goal_active_observed=True,
            goal_terminal_observed=True,
            first_action_observed=True,
            bridge_summary_path=bridge_summary,
            post_bridge_recovery_action="typed_closeout",
        )
        plan = {
            "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
            "host_local_acp_relay_trace_dir": str(trace_dir),
            "runner_prerequisites": {},
        }
        trace = {}
        _merge_host_local_acp_relay_trace_summary(plan, trace)

    compact = {
        "route": CODEX_CLI_GOAL_BASELINE_ROUTE,
        "official_score_status": "completed",
        "interaction_counters": trace,
        "runner_prerequisites": plan["runner_prerequisites"],
        "failure_attribution_labels": ["official_score_zero_case_failure"],
    }
    assert _apply_codex_cli_goal_countability_guard_attribution(compact) is False
    assert "codex_cli_goal_countability_contract" not in compact


def _assert_cli_goal_uses_short_file_backed_objective_for_bridge_packet() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.codex_cli_goal_tui import (
        CODEX_CLI_GOAL_OBJECTIVE_MAX_CHARS,
        CODEX_CLI_GOAL_TASK_PROMPT_FILENAME,
        CODEX_CLI_GOAL_THREAD_PREWARM_MARKER,
        CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT,
        build_codex_cli_goal_file_objective,
        build_codex_cli_goal_tui_input,
    )
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
        _prompt_requires_bridge_first_action,
        _prompt_requires_meaningful_bridge_progress,
    )

    assert CODEX_CLI_GOAL_THREAD_PREWARM_MARKER not in (
        CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT
    )
    objective = build_codex_cli_goal_file_objective(
        CODEX_CLI_GOAL_TASK_PROMPT_FILENAME
    )
    assert CODEX_CLI_GOAL_TASK_PROMPT_FILENAME in objective, objective
    assert len(objective) < CODEX_CLI_GOAL_OBJECTIVE_MAX_CHARS
    assert build_codex_cli_goal_tui_input(objective).startswith("/goal "), objective
    packet = SkillsBenchLocalAcpRelay(
        CodexExecConfig(remote_command_file_bridge_command="/tmp/private-bridge")
    )._prompt_with_remote_bridge_packet(
        "Task",
        bridge_probe={"operation_count": 1},
        bridge_command_for_agent="/tmp/private-bridge",
    )
    assert "FIRST ACTION REQUIRED" in packet, packet
    assert _prompt_requires_bridge_first_action(packet) is True
    assert (
        _prompt_requires_meaningful_bridge_progress(
            packet,
            route="codex-cli-goal-baseline",
        )
        is True
    )
    for relative in (
        "loopx/benchmark_adapters/skillsbench_acp_relay.py",
        "scripts/harbor_host_codex_goal_agent.py",
        "scripts/terminal_bench_host_codex_goal_agent.py",
    ):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert '"/goal", "C-m"' not in source, relative
        assert '_tmux_send_literal(tmux_name, "/goal ")' not in source, relative
    source = (
        REPO_ROOT / "loopx/benchmark_adapters/skillsbench_acp_relay.py"
    ).read_text(encoding="utf-8")
    assert "CODEX_CLI_GOAL_TASK_PROMPT_FILENAME" in source
    assert "prompt_instruction_path.write_text(" in source
    assert "build_codex_cli_goal_file_objective(" in source
    assert "tmux_type_text_and_submit(" in source
    assert "build_codex_cli_goal_tui_input(prompt_for_codex)" not in source
    assert "codex_cli_goal_thread_prewarm: bool = False" in source
    assert "if self._config.codex_cli_goal_thread_prewarm:" in source
    assert "prewarm_codex_cli_goal_thread(" in source
    assert "thread_prewarm_timeout" in source
    assert "timeout_sec=max(" in source
    assert "self._config.first_action_timeout_sec" in source
    assert "post_bridge_recovery_attempt_count" in source
    assert "post_bridge_closeout_attempt_count" in source
    assert "POST_BRIDGE_RECOVERY_ATTEMPT_LIMIT" in source
    assert "CODEX_CLI_GOAL_POST_BRIDGE_CLOSEOUT_PROMPT" in source
    assert "typed_closeout" in source
    assert "post_bridge_recovery_attempt_count < 2" not in source
    assert "last_bridge_activity_at >= 30.0" in source
    tui_source = (REPO_ROOT / "loopx/codex_cli_goal_tui.py").read_text(
        encoding="utf-8"
    )
    assert "goal-thread-prewarm.txt" in tui_source
    assert CODEX_CLI_GOAL_TASK_PROMPT_FILENAME in tui_source
    assert "tmux_send_plain_enter" in tui_source
    assert "tmux_type_text_and_submit" in tui_source

    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp) / "trace"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(worker_public_trace_dir=str(trace_dir))
        )
        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="goal_active_timeout",
            goal_active_observed=False,
            goal_terminal_observed=False,
            first_action_observed=False,
            bridge_summary_path=None,
            goal_prompt_file_used=True,
            goal_command_submission_method="typed",
        )
        traces = list(trace_dir.glob("*.compact.json"))
        assert len(traces) == 1, traces
        payload = json.loads(traces[0].read_text(encoding="utf-8"))
        trace = payload["codex_cli_goal"]
        assert trace["goal_prompt_file_used"] is True, trace
        assert trace["goal_prompt_file_raw_path_recorded"] is False, trace
        assert trace["goal_command_submission_method"] == "typed", trace


def _assert_cli_goal_codex_api_proxy_is_runtime_only() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.codex_cli_goal_tui import (
        codex_cli_tui_environment,
        codex_cli_tui_shell_command,
    )
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
    )

    proxy_url = "http://127.0.0.1:18182"
    with tempfile.TemporaryDirectory() as temp:
        trace_dir = Path(temp) / "trace"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                codex_api_proxy=proxy_url,
                worker_public_trace_dir=str(trace_dir),
            )
        )
        env = codex_cli_tui_environment(proxy_url)
        for key in (
            "HTTPS_PROXY",
            "HTTP_PROXY",
            "ALL_PROXY",
            "https_proxy",
            "http_proxy",
            "all_proxy",
        ):
            assert env[key] == proxy_url, env
        assert "127.0.0.1" in env["NO_PROXY"], env

        shell_command = codex_cli_tui_shell_command(
            ["codex", "--version"],
            env=env,
        )
        assert shell_command.startswith("env "), shell_command
        assert "HTTPS_PROXY=" in shell_command, shell_command

        relay._publish_codex_cli_goal_trace(
            ok=False,
            stage="goal_failed",
            goal_active_observed=False,
            goal_terminal_observed=True,
            first_action_observed=False,
            bridge_summary_path=None,
        )
        traces = list(trace_dir.glob("*.compact.json"))
        assert len(traces) == 1, traces
        payload = json.loads(traces[0].read_text(encoding="utf-8"))
        assert proxy_url not in json.dumps(payload, sort_keys=True), payload
        assert payload["codex_cli_goal"]["codex_api_proxy_env_injected"] is True
        assert payload["codex_cli_goal"]["codex_api_proxy_raw_url_recorded"] is False
        assert payload["codex_cli_goal"]["goal_thread_prewarm_observed"] is False

        relay._publish_codex_cli_goal_trace(
            ok=True,
            stage="goal_achieved",
            goal_active_observed=True,
            goal_terminal_observed=True,
            first_action_observed=True,
            bridge_summary_path=None,
            thread_prewarm_observed=True,
        )
        traces = sorted(trace_dir.glob("*.compact.json"))
        assert len(traces) == 2, traces
        payloads = [
            json.loads(trace.read_text(encoding="utf-8")) for trace in traces
        ]
        achieved_payload = next(
            payload
            for payload in payloads
            if payload["codex_cli_goal"]["stage"] == "goal_achieved"
        )
        assert (
            achieved_payload["codex_cli_goal"]["goal_thread_prewarm_observed"]
            is True
        )


def main() -> int:
    _assert_app_server_goal_route_deprecated()
    _assert_cli_goal_route_requires_materialized_solver_bridge()
    _assert_cli_goal_plan_and_relay_command()
    _assert_cli_goal_trace_merges_into_public_prerequisites()
    _assert_cli_goal_tui_ready_wait_tolerates_startup_warnings()
    _assert_cli_goal_paste_submit_falls_back_to_plain_enter()
    _assert_cli_goal_typed_submit_avoids_paste_buffer()
    _assert_cli_goal_rate_limit_is_public_safe_retryable_stage()
    _assert_cli_goal_post_bridge_blocker_is_public_safe_stage()
    _assert_cli_goal_active_timeout_is_public_countability_stage()
    _assert_cli_goal_uses_short_file_backed_objective_for_bridge_packet()
    _assert_cli_goal_codex_api_proxy_is_runtime_only()
    print("skillsbench-codex-cli-goal-route-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
