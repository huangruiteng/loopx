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
        marker_path=Path("/tmp/gh-harbor/done.marker"),
        task_workdir="/workspace",
    )
    assert "native Codex Goal mode" in prompt
    assert "harbor-env-exec" in prompt
    assert "--cwd /workspace -- <command>" in prompt
    assert "first verify the bridge" in prompt
    assert "--cwd /workspace -- pwd" in prompt
    assert "Synthetic Harbor instruction placeholder." in prompt
    assert "/Users/" not in prompt
    assert "/data/goal-harness-bench" not in prompt
    assert "/root/goal-harness-bench" not in prompt

    disabled_packet = module.build_goal_harness_access_packet(
        mode="codex_goal_mode_baseline",
        packet_mode="none",
    )
    assert disabled_packet == ""

    treatment_packet = module.build_goal_harness_access_packet(
        mode="codex_goal_harness",
        packet_mode="compact",
        goal_id="goal-harness-meta",
        cli_bridge_enabled="true",
        command_prefix="goal-harness",
        registry_arg="/tmp/gh/registry.global.json",
        runtime_root_arg="/tmp/gh/runtime",
        scan_path="/workspace/goal_harness/benchmark.py",
        classification="swe_marathon_rust_c_compiler_treatment",
    )
    assert "Goal Harness Access Packet V0" in treatment_packet
    assert "benchmark_family: harbor" in treatment_packet
    assert "mode: codex_goal_harness" in treatment_packet
    assert "goal_harness_cli_bridge_available: true" in treatment_packet
    assert "goal_harness_product_path_primary_route: prompt_driven_case_local_goal_harness_cli" in treatment_packet
    assert "goal_harness_case_local_cli_installed_before_agent: true" in treatment_packet
    assert "goal_harness_case_cli_path: /app/.local/bin/goal-harness" in treatment_packet
    assert "goal_harness_case_todo_id: todo_benchmark_case_main" in treatment_packet
    assert "goal_harness_case_command_quota_should_run:" in treatment_packet
    assert "/app/.local/bin/goal-harness --format json quota should-run" in treatment_packet
    assert "goal_harness_case_command_claim_todo:" in treatment_packet
    assert "goal_harness_global_command_check_optional_context:" in treatment_packet
    assert "do_not_upload_or_submit_to_leaderboard: true" in treatment_packet
    assert "benchmark_loop_contract:" in treatment_packet
    assert "protocol_id: packet_only_observation" in treatment_packet
    assert "benchmark_case_lifecycle_contract:" in treatment_packet
    assert "case_isolation_scope: per_benchmark_case_arm" in treatment_packet
    assert "benchmark_case_goal_id: swe-marathon-current-case-codex-goal-harness-treatment-case" in treatment_packet
    assert "case_state_path: /app/.codex/goals/swe-marathon-current-case-codex-goal-harness-treatment-case/ACTIVE_GOAL_STATE.md" in treatment_packet
    assert "required_lifecycle_steps: quota_should_run,todo_claim_or_update,bounded_agent_turn,validation_or_case_result,refresh_state,quota_spend" in treatment_packet
    assert "required_rollout_event_kinds: quota_should_run,todo_claim,todo_update,validation,refresh_state,quota_spend,compact_case_result,failure_attribution" in treatment_packet
    assert "strict_goal_harness_treatment_claim_allowed: false" in treatment_packet
    assert "goal_harness_treatment_claim_blocker:" in treatment_packet
    polling_packet = module.build_goal_harness_access_packet(
        mode="codex_goal_harness",
        packet_mode="compact",
        cli_bridge_enabled=True,
        goal_id="goal-harness-meta",
        experiment_protocol="max5_blind_loop_no_feedback",
        max_rounds=5,
    )
    assert "protocol_id: max5_blind_loop_no_feedback" in polling_packet
    assert "route: goal-harness-prompt-polling-test" in polling_packet
    assert "strict_goal_harness_treatment_claim_allowed: false" in polling_packet
    assert "controller_trace_absent" in polling_packet
    missing_prompt_lifecycle_claim = (
        module.classify_goal_harness_treatment_claim(
            {
                "benchmark_loop_contract": {
                    "protocol_id": "max5_blind_loop_no_feedback",
                    "max_rounds_budget": 5,
                    "official_feedback_forwarded": False,
                    "blind_loop": True,
                    "route": "goal-harness-prompt-polling-test",
                },
                "controller_trace_present": True,
                "goal_harness_product_path_primary_route": (
                    "prompt_driven_case_local_goal_harness_cli"
                ),
                "goal_harness_prompt_driven_loop_required": True,
            }
        )
    )
    assert (
        missing_prompt_lifecycle_claim[
            "strict_goal_harness_treatment_claim_allowed"
        ]
        is False
    ), missing_prompt_lifecycle_claim
    assert (
        "prompt_driven_goal_harness_lifecycle_absent"
        in missing_prompt_lifecycle_claim["goal_harness_treatment_claim_blocker"]
    ), missing_prompt_lifecycle_claim
    observed_prompt_lifecycle_claim = (
        module.classify_goal_harness_treatment_claim(
            {
                "benchmark_loop_contract": {
                    "protocol_id": "max5_blind_loop_no_feedback",
                    "max_rounds_budget": 5,
                    "official_feedback_forwarded": False,
                    "blind_loop": True,
                    "route": "goal-harness-prompt-polling-test",
                },
                "controller_trace_present": True,
                "goal_harness_product_path_primary_route": (
                    "prompt_driven_case_local_goal_harness_cli"
                ),
                "goal_harness_prompt_driven_loop_required": True,
                "goal_harness_prompt_driven_lifecycle_observed": True,
            }
        )
    )
    assert (
        observed_prompt_lifecycle_claim[
            "strict_goal_harness_treatment_claim_allowed"
        ]
        is True
    ), observed_prompt_lifecycle_claim
    init_payload = module.build_case_goal_state_init_payload(
        benchmark_id="swe-marathon",
        case_id="find-network-alignments",
        arm_id="goal_harness_prompt_polling_test",
        route="goal-harness-prompt-polling-test",
        max_rounds=5,
    )
    assert init_payload["schema_version"] == "goal_harness_benchmark_case_active_state_v1", init_payload
    assert (
        init_payload["benchmark_case_goal_id"]
        == "swe-marathon-find-network-alignments-goal-harness-prompt-polling-test-case"
    ), init_payload
    assert init_payload["case_state_path"].startswith("/app/.codex/goals/"), init_payload
    assert init_payload["case_state_path"].endswith("/ACTIVE_GOAL_STATE.md"), init_payload
    assert init_payload["install_flow_schema_version"] == "goal_harness_benchmark_case_install_flow_v0", init_payload
    assert init_payload["case_cli_path"] == "/app/.local/bin/goal-harness", init_payload
    assert init_payload["case_todo_id"] == "todo_benchmark_case_main", init_payload
    assert init_payload["case_agent_id"] == "codex-benchmark-agent", init_payload
    assert init_payload["product_path_primary_route"] == "prompt_driven_case_local_goal_harness_cli", init_payload
    assert init_payload["prompt_driven_route_required"] is True, init_payload
    init_command = init_payload["command"]
    assert "mkdir -p" in init_command, init_command
    assert "mv \"$tmp\"" in init_command, init_command
    assert "## Agent Todo" in init_command, init_command
    assert "goal-harness-prompt-polling-test" in init_command, init_command
    assert "find-network-alignments" in init_command, init_command
    assert "/app/.local/bin/goal-harness" in init_command, init_command
    assert "quota_should_run" in init_command, init_command
    assert "todo_claim" in init_command, init_command
    assert "rollout-event-log.jsonl" in init_command, init_command
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
    assert init_compact["goal_harness_install_flow_required"] is True, init_compact
    assert init_compact["goal_harness_install_flow_status"] == "initialized", init_compact
    assert init_compact["goal_harness_case_cli_installed_before_agent"] is True, init_compact
    assert init_compact["goal_harness_case_cli_path"] == "/app/.local/bin/goal-harness", init_compact
    assert init_compact["goal_harness_case_todo_id"] == "todo_benchmark_case_main", init_compact
    assert init_compact["goal_harness_product_path_primary_route"] == "prompt_driven_case_local_goal_harness_cli", init_compact
    assert init_compact["goal_harness_prompt_driven_route_required"] is True, init_compact
    assert init_compact["case_goal_state_raw_output_recorded"] is False, init_compact
    assert (
        module._case_cli_command(
            init_payload,
            "quota",
            "should-run",
            "--goal-id",
            init_payload["benchmark_case_goal_id"],
        ).startswith("/app/.local/bin/goal-harness --format json quota should-run")
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
        ok = await module._run_case_goal_harness_cli(
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
        return trace

    scheduler_trace = asyncio.run(_exercise_case_scheduler())
    assert scheduler_trace["route"] == "cli_scheduler_case_local_goal_harness_cli", scheduler_trace
    assert scheduler_trace["commands"][0]["stdout_summary"]["should_run"] is True, scheduler_trace
    assert scheduler_trace["event_kind_counts"] == {
        "install": 1,
        "quota_should_run": 1,
        "todo_claim": 1,
    }, scheduler_trace
    assert scheduler_trace["raw_logs_recorded"] is False, scheduler_trace

    treatment_prompt = module.build_host_goal_prompt(
        instruction="Synthetic Harbor instruction placeholder.",
        bridge_command=Path("/tmp/gh-harbor/bin/harbor-env-exec"),
        marker_path=Path("/tmp/gh-harbor/done.marker"),
        task_workdir="/workspace",
        goal_harness_access_packet=treatment_packet,
    )
    assert "Goal Harness treatment access packet:" in treatment_prompt
    assert "case-local Goal Harness CLI" in treatment_prompt
    assert "part of the treatment proof" in treatment_prompt
    assert "mode: codex_goal_harness" in treatment_prompt

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
                (
                    "/app/.local/bin/goal-harness --format json quota "
                    "should-run --goal-id "
                    f"{init_payload['benchmark_case_goal_id']} "
                    "--agent-id codex-benchmark-agent"
                ),
                (
                    "/app/.local/bin/goal-harness --format json todo claim "
                    "--goal-id "
                    f"{init_payload['benchmark_case_goal_id']} "
                    "--todo-id todo_benchmark_case_main "
                    "--claimed-by codex-benchmark-agent"
                ),
            ]
        ):
            (request_dir / f"case-gh-{index}.request.json").write_text(
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
            agent._prompt_driven_goal_harness_commands,
        )
        assert prompt_trace["route"] == (
            "prompt_driven_case_local_goal_harness_cli"
        ), prompt_trace
        assert prompt_trace["command_count"] == 2, prompt_trace
        assert prompt_trace["event_kind_counts"] == {
            "quota_should_run": 1,
            "todo_claim": 1,
        }, prompt_trace
        assert prompt_trace["lifecycle_observed"] is True, prompt_trace
        assert prompt_trace["raw_commands_recorded"] is False, prompt_trace
        assert prompt_trace["raw_output_recorded"] is False, prompt_trace
        assert agent.version() == "0.5.0"
        assert agent.goal_timeout_sec == 9.0
        assert agent.poll_interval_sec == 0.5
        assert agent.task_workdir == "/workspace"
        assert agent.goal_surface == "app_server"
        assert agent.reasoning_effort == "high"
        assert agent.app_server_wait_for_completion is False
        assert agent.app_server_response_timeout_sec == 4.0
        assert agent.goal_harness_mode == "codex_goal_mode_baseline"
        assert agent.goal_harness_access_packet_mode == "none"
        assert agent.goal_harness_experiment_protocol == "packet_only_observation"
        assert agent.goal_harness_max_rounds == 5

        no_wait_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "no-wait-logs",
            goal_surface="app_server",
            app_server_wait_for_completion="false",
        )
        assert no_wait_agent.app_server_wait_for_completion is False

        treatment_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "treatment-logs",
            goal_surface="app_server",
            goal_harness_mode="codex_goal_harness",
            goal_harness_access_packet_mode="compact",
            goal_harness_cli_bridge_enabled="true",
        )
        assert treatment_agent.goal_harness_mode == "codex_goal_harness"
        assert treatment_agent.goal_harness_access_packet_mode == "compact"
        assert treatment_agent.goal_harness_cli_bridge_enabled is True
        assert treatment_agent.goal_harness_experiment_protocol == "packet_only_observation"
        assert treatment_agent.goal_harness_prompt_polling_rounds == 1
        assert treatment_agent.goal_harness_benchmark_id == "swe-marathon"
        assert treatment_agent.goal_harness_case_id == "current-case"
        assert treatment_agent.goal_harness_arm_id == "codex_goal_harness_treatment"
        polling_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "polling-logs",
            goal_surface="app_server",
            goal_harness_mode="codex_goal_harness",
            goal_harness_access_packet_mode="compact",
            goal_harness_experiment_protocol="max5_blind_loop_no_feedback",
            goal_harness_max_rounds=5,
            goal_harness_case_id="find-network-alignments",
        )
        assert polling_agent.goal_harness_prompt_polling_rounds == 5
        assert polling_agent.goal_harness_prompt_polling_round_timeout_sec == 300.0
        assert polling_agent.goal_harness_case_id == "find-network-alignments"
        long_polling_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "long-polling-logs",
            goal_surface="app_server",
            goal_timeout_sec=18000,
            goal_harness_mode="codex_goal_harness",
            goal_harness_access_packet_mode="compact",
            goal_harness_experiment_protocol="max5_blind_loop_no_feedback",
            goal_harness_max_rounds=5,
        )
        assert long_polling_agent.goal_harness_prompt_polling_round_timeout_sec == 900.0
        explicit_timeout_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "explicit-timeout-logs",
            goal_surface="app_server",
            goal_harness_mode="codex_goal_harness",
            goal_harness_access_packet_mode="compact",
            goal_harness_experiment_protocol="max5_blind_loop_no_feedback",
            goal_harness_prompt_polling_round_timeout_sec=120,
        )
        assert explicit_timeout_agent.goal_harness_prompt_polling_round_timeout_sec == 120.0

    print("harbor host Codex Goal agent smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
