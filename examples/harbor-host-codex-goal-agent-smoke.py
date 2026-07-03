#!/usr/bin/env python3
"""Smoke-test the Harbor host Codex Goal custom agent helpers."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import py_compile
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "harbor_host_codex_goal_agent.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("harbor_host_codex_goal", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_module()

    command = module.build_codex_tui_command(model_name="gpt-5.5")
    assert command[:5] == [
        "codex",
        "--no-alt-screen",
        "--ask-for-approval",
        "never",
        "--sandbox",
    ], command
    assert command[-2:] == ["--model", "gpt-5.5"], command

    prompt = module.build_host_goal_prompt(
        instruction="Synthetic Harbor instruction placeholder.",
        bridge_command=Path("/tmp/gh-harbor/bin/harbor-env-exec"),
        task_workdir="/workspace",
    )
    assert "native Codex Goal mode" in prompt
    assert "harbor-env-exec" in prompt
    assert "--cwd /workspace -- <command>" in prompt
    assert "first verify the bridge" in prompt
    assert "--cwd /workspace -- pwd" in prompt
    assert "Synthetic Harbor instruction placeholder." in prompt
    assert "finish the Codex turn" in prompt
    assert "completion marker" not in prompt
    assert "touch /tmp/gh-harbor/done.marker" not in prompt
    assert "/Users/" not in prompt
    assert "/data/loopx-bench" not in prompt
    assert "/root/loopx-bench" not in prompt

    disabled_packet = module.build_loopx_access_packet(
        mode="codex_goal_mode_baseline",
        packet_mode="none",
    )
    assert disabled_packet == ""

    treatment_packet = module.build_loopx_access_packet(
        mode="codex_loopx",
        packet_mode="compact",
        goal_id="loopx-meta",
        cli_bridge_enabled="true",
        command_prefix="loopx",
        registry_arg="/tmp/gh/registry.global.json",
        runtime_root_arg="/tmp/gh/runtime",
        scan_path="/workspace/loopx/benchmark.py",
        classification="swe_marathon_rust_c_compiler_treatment",
    )
    assert "LoopX Access Packet V0" in treatment_packet
    assert "benchmark_family: harbor" in treatment_packet
    assert "mode: codex_loopx" in treatment_packet
    assert "loopx_cli_bridge_available: true" in treatment_packet
    assert "loopx_product_path_primary_route: prompt_driven_case_local_loopx_cli" in treatment_packet
    assert "loopx_case_local_cli_installed_before_agent: true" in treatment_packet
    assert "loopx_case_cli_path: /app/.local/bin/loopx" in treatment_packet
    assert f"loopx_case_todo_id: {module.BENCHMARK_CASE_LOOPX_TODO_ID}" in treatment_packet
    assert "loopx_case_command_quota_should_run:" in treatment_packet
    assert (
        "/app/.local/bin/loopx --registry /app/.loopx/registry.json "
        "--runtime-root /app/.loopx/runtime --format json quota should-run"
    ) in treatment_packet
    assert "loopx_case_command_claim_todo:" in treatment_packet
    assert "loopx_case_command_mark_todo_done_when_complete:" in treatment_packet
    assert "loopx_completion_source_of_truth: case_local_active_todo" in treatment_packet
    assert "when_task_complete_mark_case_todo_done: true" in treatment_packet
    assert "separate_completion_file_required: false" in treatment_packet
    assert "host_exit_condition: confirmed_no_active_loopx_todo" in treatment_packet
    assert "completion_marker_exit_condition" not in treatment_packet
    assert "loopx_global_command_check_optional_context:" in treatment_packet
    assert "do_not_upload_or_submit_to_leaderboard: true" in treatment_packet
    assert "benchmark_loop_contract:" in treatment_packet
    assert "protocol_id: max5_blind_loop_no_feedback" in treatment_packet
    assert "route: loopx-prompt-polling-test" in treatment_packet
    assert "benchmark_case_lifecycle_contract:" in treatment_packet
    assert "case_isolation_scope: per_benchmark_case_arm" in treatment_packet
    assert "benchmark_case_goal_id: swe-marathon-current-case-codex-loopx-treatment-case" in treatment_packet
    assert "case_state_path: /app/.codex/goals/swe-marathon-current-case-codex-loopx-treatment-case/ACTIVE_GOAL_STATE.md" in treatment_packet
    assert "required_lifecycle_steps: quota_should_run,todo_claim_or_update,bounded_agent_turn,validation_or_case_result,refresh_state,quota_spend" in treatment_packet
    assert "required_rollout_event_kinds: quota_should_run,todo_claim,todo_update,validation,refresh_state,quota_spend,compact_case_result,failure_attribution" in treatment_packet
    assert "strict_loopx_treatment_claim_allowed: false" in treatment_packet
    assert "controller_trace_absent" in treatment_packet
    packet_only_observation = module.build_loopx_access_packet(
        mode="codex_loopx",
        packet_mode="compact",
        cli_bridge_enabled=True,
        goal_id="loopx-meta",
        experiment_protocol="packet_only_observation",
        max_rounds=5,
    )
    assert "protocol_id: packet_only_observation" in packet_only_observation
    assert "route: loopx-packet-only-observation" in packet_only_observation
    assert "packet_only_no_max5_controller" in packet_only_observation
    polling_packet = module.build_loopx_access_packet(
        mode="codex_loopx",
        packet_mode="compact",
        cli_bridge_enabled=True,
        goal_id="loopx-meta",
        experiment_protocol="max5_blind_loop_no_feedback",
        max_rounds=5,
    )
    assert "protocol_id: max5_blind_loop_no_feedback" in polling_packet
    assert "route: loopx-prompt-polling-test" in polling_packet
    assert "strict_loopx_treatment_claim_allowed: false" in polling_packet
    assert "controller_trace_absent" in polling_packet
    missing_prompt_lifecycle_claim = (
        module.classify_loopx_treatment_claim(
            {
                "benchmark_loop_contract": {
                    "protocol_id": "max5_blind_loop_no_feedback",
                    "max_rounds_budget": 5,
                    "official_feedback_forwarded": False,
                    "blind_loop": True,
                    "route": "loopx-prompt-polling-test",
                },
                "controller_trace_present": True,
                "loopx_product_path_primary_route": (
                    "prompt_driven_case_local_loopx_cli"
                ),
                "loopx_prompt_driven_loop_required": True,
            }
        )
    )
    assert (
        missing_prompt_lifecycle_claim[
            "strict_loopx_treatment_claim_allowed"
        ]
        is False
    ), missing_prompt_lifecycle_claim
    assert (
        "prompt_driven_loopx_lifecycle_absent"
        in missing_prompt_lifecycle_claim["loopx_treatment_claim_blocker"]
    ), missing_prompt_lifecycle_claim
    observed_prompt_lifecycle_claim = (
        module.classify_loopx_treatment_claim(
            {
                "benchmark_loop_contract": {
                    "protocol_id": "max5_blind_loop_no_feedback",
                    "max_rounds_budget": 5,
                    "official_feedback_forwarded": False,
                    "blind_loop": True,
                    "route": "loopx-prompt-polling-test",
                },
                "controller_trace_present": True,
                "loopx_product_path_primary_route": (
                    "prompt_driven_case_local_loopx_cli"
                ),
                "loopx_prompt_driven_loop_required": True,
                "loopx_prompt_driven_lifecycle_observed": True,
            }
        )
    )
    assert (
        observed_prompt_lifecycle_claim[
            "strict_loopx_treatment_claim_allowed"
        ]
        is True
    ), observed_prompt_lifecycle_claim
    init_payload = module.build_case_goal_state_init_payload(
        benchmark_id="swe-marathon",
        case_id="find-network-alignments",
        arm_id="loopx_prompt_polling_test",
        route="loopx-prompt-polling-test",
        max_rounds=5,
    )
    assert init_payload["schema_version"] == "loopx_benchmark_case_active_state_v1", init_payload
    assert (
        init_payload["benchmark_case_goal_id"]
        == "swe-marathon-find-network-alignments-loopx-prompt-polling-test-case"
    ), init_payload
    assert init_payload["case_state_path"].startswith("/app/.codex/goals/"), init_payload
    assert init_payload["case_state_path"].endswith("/ACTIVE_GOAL_STATE.md"), init_payload
    assert init_payload["install_flow_schema_version"] == "loopx_benchmark_case_install_flow_v0", init_payload
    assert init_payload["case_cli_path"] == "/app/.local/bin/loopx", init_payload
    assert init_payload["case_todo_id"] == module.BENCHMARK_CASE_LOOPX_TODO_ID, init_payload
    assert init_payload["case_agent_id"] == "codex-benchmark-agent", init_payload
    assert init_payload["product_path_primary_route"] == "prompt_driven_case_local_loopx_cli", init_payload
    assert init_payload["prompt_driven_route_required"] is True, init_payload
    init_command = init_payload["command"]
    assert "mkdir -p" in init_command, init_command
    assert "install-from-github.sh" in init_command, init_command
    assert "mv \"$tmp\"" in init_command, init_command
    assert " bootstrap " in init_command, init_command
    assert " configure-goal " in init_command, init_command
    assert " todo add " in init_command, init_command
    assert "loopx-prompt-polling-test" in init_command, init_command
    assert "find-network-alignments" in init_command, init_command
    assert "/app/.local/bin/loopx" in init_command, init_command
    assert " quota should-run " in init_command, init_command
    assert " refresh-state " in init_command, init_command
    assert " todo claim " not in init_command, init_command
    assert str(init_payload["case_rollout_event_log_path"]).endswith(
        "/rollout-event-log.jsonl"
    ), init_payload
    assert "/Users/" not in init_command, init_command
    init_compact = module._case_goal_state_init_compact(
        init_payload,
        status="initialized",
        initialized_before_agent=True,
    )
    assert init_compact["case_goal_state_init_required"] is True, init_compact
    assert init_compact["case_goal_state_initialized_before_agent"] is True, init_compact
    assert init_compact["case_goal_state_init_status"] == "initialized", init_compact
    assert init_compact["case_goal_state_path"] == init_payload["case_state_path"], init_compact
    assert init_compact["loopx_install_flow_required"] is True, init_compact
    assert init_compact["loopx_install_flow_status"] == "initialized", init_compact
    assert init_compact["loopx_case_cli_installed_before_agent"] is True, init_compact
    assert init_compact["loopx_case_cli_path"] == "/app/.local/bin/loopx", init_compact
    assert init_compact["loopx_case_todo_id"] == module.BENCHMARK_CASE_LOOPX_TODO_ID, init_compact
    assert init_compact["loopx_product_path_primary_route"] == "prompt_driven_case_local_loopx_cli", init_compact
    assert init_compact["loopx_prompt_driven_route_required"] is True, init_compact
    assert init_compact["case_goal_state_raw_output_recorded"] is False, init_compact
    assert (
        module._case_cli_command(
            init_payload,
            "quota",
            "should-run",
            "--goal-id",
            init_payload["benchmark_case_goal_id"],
        ).startswith(
            "/app/.local/bin/loopx --registry /app/.loopx/registry.json "
            "--runtime-root /app/.loopx/runtime --format json quota should-run"
        )
    )

    class _FakeExecResult:
        def __init__(self, stdout: str = "", return_code: int = 0) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.return_code = return_code

    class _FakeEnvironment:
        def __init__(self) -> None:
            self.commands: list[str] = []

        async def exec(self, command: str, cwd: str | None = None, timeout_sec: int = 0):
            self.commands.append(command)
            if command.startswith("cat "):
                return _FakeExecResult(
                    "\n".join(
                        [
                            '{"event_kind":"install"}',
                            '{"event_kind":"quota_should_run"}',
                            '{"event_kind":"todo_claim"}',
                        ]
                    )
                    + "\n"
                )
            return _FakeExecResult(
                '{"ok":true,"goal_id":"demo","should_run":true,'
                '"raw_logs_recorded":false}'
            )

    async def _exercise_case_scheduler() -> dict:
        fake_environment = _FakeEnvironment()
        trace = module._new_case_scheduler_trace(init_payload)
        ok = await module._run_case_loopx_cli(
            fake_environment,
            payload=init_payload,
            trace=trace,
            action="case_quota_should_run_before_agent",
            args=[
                "quota",
                "should-run",
                "--goal-id",
                init_payload["benchmark_case_goal_id"],
                "--agent-id",
                init_payload["case_agent_id"],
            ],
            cwd="/workspace",
        )
        assert ok is True, trace
        await module._collect_case_rollout_event_counts(
            fake_environment,
            payload=init_payload,
            trace=trace,
            cwd="/workspace",
        )
        status_summary = module._compact_json_keys(
            json.dumps(
                {
                    "ok": True,
                    "goal_id": init_payload["benchmark_case_goal_id"],
                    "agent_todo_summary": {
                        "schema_version": "todo_summary_v0",
                        "open_count": 1,
                        "first_open_items": [
                            {
                                "todo_id": init_payload["case_todo_id"],
                                "status": "open",
                                "claimed_by": init_payload["case_agent_id"],
                                "priority": "P0",
                                "task_class": "advancement_task",
                            }
                        ],
                    },
                    "user_todo_summary": {
                        "schema_version": "todo_summary_v0",
                        "open_count": 0,
                    },
                    "interaction_contract": {
                        "schema_version": "loopx_interaction_contract_v0",
                        "mode": "bounded_delivery",
                        "user_channel": {"action_required": False},
                        "agent_channel": {
                            "must_attempt": True,
                            "delivery_allowed": True,
                        },
                        "cli_channel": {"spend_after_validation": True},
                    },
                }
            ),
            case_todo_id=init_payload["case_todo_id"],
        )
        trace["commands"].extend(
            [
                {
                    "action": "timeout_blocker_status",
                    "ok": True,
                    "stdout_summary": status_summary,
                    "raw_output_recorded": False,
                },
                {
                    "action": "timeout_blocker_refresh_state",
                    "ok": True,
                    "stdout_summary": {"json_parse_ok": True, "refreshed": True},
                    "raw_output_recorded": False,
                },
                {
                    "action": "timeout_blocker_quota_spend",
                    "ok": True,
                    "stdout_summary": {"json_parse_ok": True, "spent": True},
                    "raw_output_recorded": False,
                },
            ]
        )
        trace["closeout_summary"] = module._case_scheduler_closeout_summary(
            trace,
            result_kind="timeout_blocker",
        )
        return trace

    scheduler_trace = asyncio.run(_exercise_case_scheduler())
    assert scheduler_trace["route"] == "cli_scheduler_case_local_loopx_cli", scheduler_trace
    assert scheduler_trace["commands"][0]["stdout_summary"]["should_run"] is True, scheduler_trace
    assert scheduler_trace["event_kind_counts"] == {
        "install": 1,
        "quota_should_run": 1,
        "todo_claim": 1,
    }, scheduler_trace
    assert scheduler_trace["closeout_summary"] == {
        "schema_version": "harbor_case_loopx_closeout_summary_v0",
        "result_kind": "timeout_blocker",
        "status_observed": True,
        "refresh_state_observed": True,
        "quota_spend_observed": True,
        "agent_open_count": 1,
        "user_open_count": 0,
        "case_todo_id": module.BENCHMARK_CASE_LOOPX_TODO_ID,
        "case_todo_status": "open",
        "case_todo_claimed_by": "codex-benchmark-agent",
        "timeout_preserves_open_todo": True,
        "raw_logs_recorded": False,
        "raw_output_recorded": False,
    }, scheduler_trace
    assert scheduler_trace["raw_logs_recorded"] is False, scheduler_trace

    open_exit_state = module._case_scheduler_active_todo_exit_state(
        scheduler_trace
    )
    assert open_exit_state["no_active_todo"] is False, open_exit_state
    assert open_exit_state["exit_condition"] == "active_loopx_todo_present", (
        open_exit_state
    )

    done_trace = module._new_case_scheduler_trace(init_payload)
    done_trace["commands"].append(
        {
            "action": "post_turn_round_1_status",
            "ok": True,
            "stdout_summary": module._compact_json_keys(
                json.dumps(
                    {
                        "ok": True,
                        "goal_id": init_payload["benchmark_case_goal_id"],
                        "agent_todo_summary": {
                            "schema_version": "todo_summary_v0",
                            "open_count": 0,
                            "items": [
                                {
                                    "todo_id": init_payload["case_todo_id"],
                                    "status": "done",
                                    "claimed_by": init_payload["case_agent_id"],
                                    "priority": "P0",
                                    "task_class": "advancement_task",
                                }
                            ],
                        },
                        "user_todo_summary": {
                            "schema_version": "todo_summary_v0",
                            "open_count": 0,
                        },
                    }
                ),
                case_todo_id=init_payload["case_todo_id"],
            ),
            "raw_output_recorded": False,
        }
    )
    done_exit_state = module._case_scheduler_active_todo_exit_state(done_trace)
    done_trace["active_todo_exit_state"] = done_exit_state
    assert done_exit_state["no_active_todo"] is True, done_exit_state
    assert done_exit_state["exit_condition"] == "no_active_loopx_todo", (
        done_exit_state
    )
    assert done_exit_state["case_todo_status"] == "done", done_exit_state

    treatment_prompt = module.build_host_goal_prompt(
        instruction="Synthetic Harbor instruction placeholder.",
        bridge_command=Path("/tmp/gh-harbor/bin/harbor-env-exec"),
        task_workdir="/workspace",
        loopx_access_packet=treatment_packet,
    )
    assert "LoopX treatment access packet:" in treatment_prompt
    assert "case-local LoopX CLI" in treatment_prompt
    assert "part of the treatment proof" in treatment_prompt
    assert "LoopX is the completion source of truth" in treatment_prompt
    assert "mark the case-local LoopX todo done" in treatment_prompt
    assert "completion marker" not in treatment_prompt
    assert "touch /tmp/gh-harbor/done.marker" not in treatment_prompt
    assert "host_exit_condition: confirmed_no_active_loopx_todo" in treatment_prompt
    assert "mode: codex_loopx" in treatment_prompt

    with tempfile.TemporaryDirectory(prefix="gh-harbor-host-agent-") as tmp:
        request_dir = Path(tmp) / "requests"
        request_dir.mkdir()
        bridge = Path(tmp) / "harbor-env-exec"
        module.HarborHostCodexGoalAgent._write_bridge_script(bridge, request_dir)
        text = bridge.read_text(encoding="utf-8")
        assert "environment.exec" in text
        assert str(request_dir) in text
        assert bridge.stat().st_mode & 0o111
        py_compile.compile(str(bridge), doraise=True)

        agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "logs",
            goal_timeout_sec="9",
            startup_delay_sec="0",
            poll_interval_sec="0.5",
            task_workdir="/workspace",
            goal_surface="app_server",
            app_server_response_timeout_sec="4",
        )
        assert agent.name() == "harbor-host-codex-goal"
        agent._case_state_init_payload = init_payload
        for index, command in enumerate(
            [
                module._case_cli_command(
                    init_payload,
                    "quota",
                    "should-run",
                    "--goal-id",
                    str(init_payload["benchmark_case_goal_id"]),
                    "--agent-id",
                    "codex-benchmark-agent",
                ),
                module._case_cli_command(
                    init_payload,
                    "todo",
                    "claim",
                    "--goal-id",
                    str(init_payload["benchmark_case_goal_id"]),
                    "--todo-id",
                    module.BENCHMARK_CASE_LOOPX_TODO_ID,
                    "--claimed-by",
                    "codex-benchmark-agent",
                ),
                "python3 - <<'PY'\nopen('solution.py', 'w').write('ok')\nPY",
                "make",
                "python -m pytest tests",
                "ruff check .",
            ]
        ):
            (request_dir / f"case-loopx-{index}.request.json").write_text(
                json.dumps(
                    {
                        "command": command,
                        "cwd": "/workspace",
                        "timeout_sec": 30,
                    }
                ),
                encoding="utf-8",
            )
        asyncio.run(agent._serve_bridge_requests(_FakeEnvironment(), request_dir))
        prompt_trace = module._summarize_prompt_driven_case_trace(
            init_payload,
            agent._prompt_driven_loopx_commands,
        )
        assert prompt_trace["route"] == (
            "prompt_driven_case_local_loopx_cli"
        ), prompt_trace
        assert prompt_trace["command_count"] == 2, prompt_trace
        assert prompt_trace["event_kind_counts"] == {
            "quota_should_run": 1,
            "todo_claim": 1,
        }, prompt_trace
        assert prompt_trace["lifecycle_observed"] is True, prompt_trace
        assert prompt_trace["raw_commands_recorded"] is False, prompt_trace
        assert prompt_trace["raw_output_recorded"] is False, prompt_trace
        assert agent._bridge_phase_counts == {
            "build": 1,
            "edit": 1,
            "loopx_cli": 2,
            "test": 1,
            "verify": 1,
        }, agent._bridge_phase_counts
        phase_counters = module._build_solution_phase_counters(
            bridge_phase_counts=agent._bridge_phase_counts,
            bridge_request_count=agent._served_request_count,
            turn_completed_observed=True,
            case_scheduler_trace=done_trace,
            result_kind="case_result",
            first_blocker="",
        )
        assert phase_counters["schema_version"] == (
            "harbor_public_safe_solution_phase_counters_v0"
        ), phase_counters
        assert phase_counters["edit_command_count"] == 1, phase_counters
        assert phase_counters["build_command_count"] == 1, phase_counters
        assert phase_counters["test_command_count"] == 1, phase_counters
        assert phase_counters["verify_command_count"] == 1, phase_counters
        assert phase_counters["loopx_cli_command_count"] == 2, phase_counters
        assert phase_counters["task_bridge_command_count"] == 4, phase_counters
        assert phase_counters["self_declared_done_count"] == 1, phase_counters
        assert phase_counters["final_active_todo_count"] == 0, phase_counters
        assert phase_counters["raw_commands_recorded"] is False, phase_counters
        assert phase_counters["raw_diffs_recorded"] is False, phase_counters
        assert agent.version() == "0.5.0"
        assert agent.goal_timeout_sec == 9.0
        assert agent.poll_interval_sec == 0.5
        assert agent.task_workdir == "/workspace"
        assert agent.goal_surface == "app_server"
        assert agent.reasoning_effort == "high"
        assert agent.app_server_wait_for_completion is False
        assert agent.app_server_response_timeout_sec == 4.0
        assert agent.loopx_mode == "codex_goal_mode_baseline"
        assert agent.loopx_access_packet_mode == "none"
        assert agent.loopx_experiment_protocol == "max5_blind_loop_no_feedback"
        assert agent.loopx_max_rounds == 5

        no_wait_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "no-wait-logs",
            goal_surface="app_server",
            app_server_wait_for_completion="false",
        )
        assert no_wait_agent.app_server_wait_for_completion is False
        assert no_wait_agent.goal_timeout_sec == 21600.0

        treatment_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "treatment-logs",
            goal_surface="app_server",
            loopx_mode="codex_loopx",
            loopx_access_packet_mode="compact",
            loopx_cli_bridge_enabled="true",
        )
        assert treatment_agent.loopx_mode == "codex_loopx"
        assert treatment_agent.loopx_access_packet_mode == "compact"
        assert treatment_agent.loopx_cli_bridge_enabled is True
        assert treatment_agent.loopx_experiment_protocol == "max5_blind_loop_no_feedback"
        assert treatment_agent.loopx_prompt_polling_rounds == 5
        assert treatment_agent.loopx_benchmark_id == "swe-marathon"
        assert treatment_agent.loopx_case_id == "current-case"
        assert treatment_agent.loopx_arm_id == "codex_loopx_treatment"
        legacy_prefix = "goal_" + "harness_"
        try:
            module.HarborHostCodexGoalAgent(
                logs_dir=Path(tmp) / "legacy-treatment-logs",
                goal_surface="app_server",
                **{
                    legacy_prefix + "mode": "codex_" + legacy_prefix.rstrip("_"),
                    legacy_prefix + "access_packet_mode": "compact",
                    legacy_prefix + "cli_bridge_enabled": "true",
                },
            )
        except ValueError as exc:
            message = str(exc)
            assert "legacy_pre_rename_kwargs_unsupported" in message, message
            assert "use loopx_* kwargs before worker start" in message, message
            assert "count=3" in message, message
        else:
            raise AssertionError("legacy benchmark kwargs must fail closed")
        polling_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "polling-logs",
            goal_surface="app_server",
            loopx_mode="codex_loopx",
            loopx_access_packet_mode="compact",
            loopx_experiment_protocol="max5_blind_loop_no_feedback",
            loopx_max_rounds=5,
            loopx_case_id="find-network-alignments",
        )
        assert polling_agent.loopx_prompt_polling_rounds == 5
        assert polling_agent.loopx_prompt_polling_round_timeout_sec == 21600.0
        assert polling_agent.loopx_case_id == "find-network-alignments"
        long_polling_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "long-polling-logs",
            goal_surface="app_server",
            goal_timeout_sec=18000,
            loopx_mode="codex_loopx",
            loopx_access_packet_mode="compact",
            loopx_experiment_protocol="max5_blind_loop_no_feedback",
            loopx_max_rounds=5,
        )
        assert long_polling_agent.loopx_prompt_polling_round_timeout_sec == 18000.0
        explicit_timeout_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "explicit-timeout-logs",
            goal_surface="app_server",
            loopx_mode="codex_loopx",
            loopx_access_packet_mode="compact",
            loopx_experiment_protocol="max5_blind_loop_no_feedback",
            loopx_prompt_polling_round_timeout_sec=120,
        )
        assert explicit_timeout_agent.loopx_prompt_polling_round_timeout_sec == 120.0

        class _FakeTurn:
            thread_id = "thread_demo"
            turn_id = "turn_demo"
            turn_id_source = "fixture"
            turn_start_response_turn_id_present = True
            turn_event_stream_turn_id_present = False
            goal_status = "active"
            turn_status = "completed"
            turn_completed_observed = True
            assistant_message = ""
            agent_message_delta_count = 0
            agent_message_item_count = 0
            item_completed_count = 0
            non_user_item_completed_count = 0
            user_message_item_count = 0
            session_log_observed = False
            session_event_count = 0
            session_task_complete_observed = False
            stream_eof_observed = True
            stream_error_observed = False
            process_exit_observed = False
            process_returncode = None
            transport_reconnect_attempted = False
            transport_reconnect_succeeded = False
            transport_reconnect_reason = ""
            goal_reactivation_attempted = False
            goal_reactivation_succeeded = False
            goal_reactivation_previous_status = ""
            goal_reactivation_result_status = ""
            notifications: list[str] = []
            _responses = None

            def terminate(self) -> None:
                self.terminated = True

        class _FakeContext:
            metadata: dict = {}

        class _DoneAfterFirstRoundEnvironment(_FakeEnvironment):
            async def exec(
                self,
                command: str,
                cwd: str | None = None,
                timeout_sec: int = 0,
            ):
                self.commands.append(command)
                if command.startswith("cat "):
                    return _FakeExecResult(
                        "\n".join(
                            [
                                '{"event_kind":"install"}',
                                '{"event_kind":"quota_should_run"}',
                                '{"event_kind":"todo_claim"}',
                                '{"event_kind":"todo_update"}',
                                '{"event_kind":"status"}',
                            ]
                        )
                        + "\n"
                    )
                if " status " in command:
                    return _FakeExecResult(
                        json.dumps(
                            {
                                "ok": True,
                                "goal_id": (
                                    "swe-marathon-current-case-"
                                    "codex-loopx-treatment-case"
                                ),
                                "agent_todo_summary": {
                                    "schema_version": "todo_summary_v0",
                                    "open_count": 0,
                                    "items": [
                                        {
                                            "todo_id": (
                                                module.BENCHMARK_CASE_LOOPX_TODO_ID
                                            ),
                                            "status": "done",
                                            "claimed_by": "codex-benchmark-agent",
                                            "priority": "P0",
                                            "task_class": "advancement_task",
                                        }
                                    ],
                                },
                                "user_todo_summary": {
                                    "schema_version": "todo_summary_v0",
                                    "open_count": 0,
                                },
                                "raw_logs_recorded": False,
                            }
                        )
                    )
                return _FakeExecResult(
                    '{"ok":true,"goal_id":"demo","should_run":true,'
                    '"raw_logs_recorded":false}'
                )

        original_start = module.start_codex_app_server_goal_turn
        original_followup = module.start_codex_app_server_goal_followup_turn

        def _fake_start(*args, **kwargs):
            del args, kwargs
            return _FakeTurn()

        def _fake_followup(*args, **kwargs):
            del args, kwargs
            raise module.CodexAppServerGoalDriverError("synthetic follow-up failure")

        module.start_codex_app_server_goal_turn = _fake_start
        module.start_codex_app_server_goal_followup_turn = _fake_followup
        try:
            no_active_agent = module.HarborHostCodexGoalAgent(
                logs_dir=Path(tmp) / "no-active-stop-logs",
                goal_surface="app_server",
                goal_timeout_sec=60,
                startup_delay_sec=0,
                poll_interval_sec=0.01,
                task_workdir="/workspace",
                loopx_mode="codex_loopx",
                loopx_access_packet_mode="compact",
                loopx_cli_bridge_enabled=True,
                loopx_experiment_protocol="max5_blind_loop_no_feedback",
                loopx_max_rounds=5,
            )
            no_active_context = _FakeContext()
            asyncio.run(
                no_active_agent.run(
                    "Synthetic Harbor instruction placeholder.",
                    _DoneAfterFirstRoundEnvironment(),
                    no_active_context,
                )
            )
        finally:
            module.start_codex_app_server_goal_turn = original_start
            module.start_codex_app_server_goal_followup_turn = original_followup

        no_active_compact_paths = sorted(
            (Path(tmp) / "no-active-stop-logs").glob(
                "host-codex-goal-*/app_server_goal_turn.compact.json"
            )
        )
        assert no_active_compact_paths, "no-active stop should write compact closeout"
        no_active_compact = json.loads(
            no_active_compact_paths[-1].read_text(encoding="utf-8")
        )
        assert no_active_compact["loopx_controller_trace"]["last_decision"] == (
            "stop_after_confirmed_no_active_loopx_todo"
        ), no_active_compact
        assert no_active_compact["loopx_controller_trace"][
            "followup_prompt_count"
        ] == 0, no_active_compact
        assert no_active_compact["loopx_controller_trace"][
            "no_active_todo_confirmed_count"
        ] == 1, no_active_compact
        assert "completion_marker_observed" not in no_active_compact, (
            no_active_compact
        )
        assert no_active_compact["loopx_case_active_todo_exit_state"][
            "no_active_todo"
        ] is True, no_active_compact
        assert no_active_compact["loopx_case_closeout_summary"][
            "case_todo_status"
        ] == "done", no_active_compact
        no_active_phase = no_active_compact["loopx_solution_phase_counters"]
        assert no_active_phase["result_kind"] == "case_result", no_active_phase
        assert no_active_phase["self_declared_done_count"] == 1, no_active_phase
        assert no_active_phase["final_active_todo_count"] == 0, no_active_phase
        assert no_active_phase["final_no_active_todo"] is True, no_active_phase
        assert no_active_phase["raw_commands_recorded"] is False, no_active_phase
        assert no_active_phase["raw_verifier_output_recorded"] is False, no_active_phase
        assert no_active_context.metadata["first_blocker"] == "", (
            no_active_context.metadata
        )
        assert (
            no_active_context.metadata["loopx_solution_phase_counters"][
                "final_active_todo_count"
            ]
            == 0
        ), no_active_context.metadata

        module.start_codex_app_server_goal_turn = _fake_start
        module.start_codex_app_server_goal_followup_turn = _fake_followup
        try:
            followup_failure_agent = module.HarborHostCodexGoalAgent(
                logs_dir=Path(tmp) / "followup-failure-logs",
                goal_surface="app_server",
                goal_timeout_sec=60,
                startup_delay_sec=0,
                poll_interval_sec=0.01,
                task_workdir="/workspace",
                loopx_mode="codex_loopx",
                loopx_access_packet_mode="compact",
                loopx_cli_bridge_enabled=True,
                loopx_experiment_protocol="max5_blind_loop_no_feedback",
                loopx_max_rounds=2,
            )
            context = _FakeContext()
            asyncio.run(
                followup_failure_agent.run(
                    "Synthetic Harbor instruction placeholder.",
                    _FakeEnvironment(),
                    context,
                )
            )
        finally:
            module.start_codex_app_server_goal_turn = original_start
            module.start_codex_app_server_goal_followup_turn = original_followup

        compact_paths = sorted(
            (Path(tmp) / "followup-failure-logs").glob(
                "host-codex-goal-*/app_server_goal_turn.compact.json"
            )
        )
        assert compact_paths, "follow-up failure should still write compact closeout"
        followup_compact = json.loads(compact_paths[-1].read_text(encoding="utf-8"))
        assert followup_compact["first_blocker"] == (
            "codex_app_server_goal_followup_turn_failed"
        ), followup_compact
        assert followup_compact["loopx_controller_trace_present"] is True
        assert followup_compact["loopx_controller_trace"]["last_decision"] == (
            "codex_app_server_goal_followup_turn_failed"
        )
        assert followup_compact["loopx_controller_trace"]["raw_error_recorded"] is False
        assert followup_compact["loopx_case_closeout_summary"][
            "result_kind"
        ] == "runtime_exception_blocker"
        assert followup_compact["loopx_case_closeout_summary"][
            "status_observed"
        ] is True
        assert followup_compact["loopx_case_closeout_summary"][
            "refresh_state_observed"
        ] is True
        assert followup_compact["loopx_case_closeout_summary"][
            "quota_spend_observed"
        ] is True
        assert followup_compact["loopx_case_closeout_summary"][
            "timeout_preserves_open_todo"
        ] is False
        followup_phase = followup_compact["loopx_solution_phase_counters"]
        assert followup_phase["result_kind"] == "runtime_exception_blocker", (
            followup_phase
        )
        assert followup_phase["first_blocker_present"] is True, followup_phase
        assert followup_phase["raw_agent_trajectory_recorded"] is False, (
            followup_phase
        )
        assert context.metadata["first_blocker"] == (
            "codex_app_server_goal_followup_turn_failed"
        )

    print("harbor host Codex Goal agent smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
