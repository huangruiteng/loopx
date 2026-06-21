#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench host Codex Goal custom agent helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "terminal_bench_host_codex_goal_agent.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tb_host_codex_goal_agent", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_module()

    command = module.build_codex_tui_command(
        codex_bin="codex",
        model_name="gpt-5.5",
    )
    assert command == [
        "codex",
        "--no-alt-screen",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "danger-full-access",
        "--model",
        "gpt-5.5",
    ], command

    marker = Path("/tmp/loopx-terminal-bench/done.marker")
    prompt = module.build_host_goal_prompt(
        container_name="example-container",
        instruction="Synthetic instruction placeholder.",
        marker_path=marker,
        task_workdir="/app",
    )
    assert "native Codex Goal mode" in prompt
    assert "docker exec example-container" in prompt
    assert "cd /app" in prompt
    assert "first verify container command execution" in prompt
    assert "docker exec example-container bash -lc 'cd /app && pwd'" in prompt
    assert "Synthetic instruction placeholder." in prompt
    assert str(marker) in prompt
    assert "/Users/" not in prompt
    assert "/data/loopx-bench" not in prompt
    assert "/root/loopx-bench" not in prompt
    assert "benchmark_case_lifecycle_contract:" not in prompt

    lifecycle_packet, lifecycle_contract = module.build_loopx_case_lifecycle_packet(
        mode="codex_loopx",
        packet_mode="compact",
        benchmark_id="terminal-bench",
        case_id="build-cython-ext",
        arm_id="loopx_prompt_polling_test",
        max_rounds=5,
    )
    assert lifecycle_contract is not None
    assert "terminal_bench_loopx_case_lifecycle_packet_v0:" in lifecycle_packet
    assert "packet_mode: compact" in lifecycle_packet
    assert "benchmark_family: harbor" in lifecycle_packet
    assert "benchmark_case_lifecycle_contract:" in lifecycle_packet
    assert "benchmark_id: terminal-bench" in lifecycle_packet
    assert "case_id: build-cython-ext" in lifecycle_packet
    assert "arm_id: loopx_prompt_polling_test" in lifecycle_packet
    assert (
        "benchmark_case_goal_id: terminal-bench-build-cython-ext-loopx-prompt-polling-test-case"
        in lifecycle_packet
    )
    assert "case_state_path: /app/.codex/goals/" in lifecycle_packet
    assert "required_lifecycle_steps: quota_should_run,todo_claim_or_update,bounded_agent_turn,validation_or_case_result,refresh_state,quota_spend" in lifecycle_packet
    assert "runner_internal_prompt_polling_only_allowed: false" in lifecycle_packet
    assert "/Users/" not in lifecycle_packet

    treatment_prompt = module.build_host_goal_prompt(
        container_name="example-container",
        instruction="Synthetic instruction placeholder.",
        marker_path=marker,
        task_workdir="/app",
        loopx_case_lifecycle_packet=lifecycle_packet,
    )
    assert "LoopX case lifecycle packet:" in treatment_prompt
    assert "benchmark_case_lifecycle_contract:" in treatment_prompt
    assert "official Terminal-Bench scorer authoritative" in treatment_prompt
    assert "/Users/" not in treatment_prompt

    agent = module.HostCodexGoalAgent(
        goal_timeout_sec="7",
        startup_delay_sec="0",
        poll_interval_sec="0.5",
        goal_surface="app_server",
        app_server_response_timeout_sec="4",
    )
    assert agent.name() == "host-codex-goal"
    assert agent.goal_timeout_sec == 7.0
    assert agent.poll_interval_sec == 0.5
    assert agent.goal_surface == "app_server"
    assert agent.reasoning_effort == "high"
    assert agent.app_server_wait_for_completion is False
    assert agent.app_server_response_timeout_sec == 4.0
    assert str(agent.work_root) == "/tmp/loopx-terminal-bench"
    assert agent.network_bootstrap_script is None
    assert agent.loopx_mode == "codex_goal_mode_baseline"
    assert agent.loopx_access_packet_mode == "none"
    assert agent.loopx_benchmark_id == "terminal-bench"
    assert agent.loopx_case_id == "current-case"
    assert agent.loopx_arm_id == "codex_loopx_treatment"
    assert agent.loopx_max_rounds == 5

    treatment_agent = module.HostCodexGoalAgent(
        goal_surface="app_server",
        loopx_mode="codex_loopx",
        loopx_access_packet_mode="compact",
        loopx_case_id="build-cython-ext",
        loopx_arm_id="loopx_prompt_polling_test",
        loopx_max_rounds="5",
    )
    assert treatment_agent.loopx_mode == "codex_loopx"
    assert treatment_agent.loopx_access_packet_mode == "compact"
    assert treatment_agent.loopx_case_id == "build-cython-ext"
    assert treatment_agent.loopx_arm_id == "loopx_prompt_polling_test"

    no_wait_agent = module.HostCodexGoalAgent(
        goal_surface="app_server",
        app_server_wait_for_completion="false",
    )
    assert no_wait_agent.app_server_wait_for_completion is False
    assert no_wait_agent.goal_timeout_sec == 10800.0

    print("terminal-bench host Codex Goal agent smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
