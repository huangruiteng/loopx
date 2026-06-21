#!/usr/bin/env python3
"""Smoke-test the Harbor host Codex Goal custom agent helpers."""

from __future__ import annotations

import importlib.util
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
    assert "goal_harness_command_check:" in treatment_packet
    assert "quota should-run" in treatment_packet
    assert "do_not_upload_or_submit_to_leaderboard: true" in treatment_packet
    assert "benchmark_loop_contract:" in treatment_packet
    assert "protocol_id: packet_only_observation" in treatment_packet
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

    treatment_prompt = module.build_host_goal_prompt(
        instruction="Synthetic Harbor instruction placeholder.",
        bridge_command=Path("/tmp/gh-harbor/bin/harbor-env-exec"),
        marker_path=Path("/tmp/gh-harbor/done.marker"),
        task_workdir="/workspace",
        goal_harness_access_packet=treatment_packet,
    )
    assert "Goal Harness treatment access packet:" in treatment_prompt
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
        polling_agent = module.HarborHostCodexGoalAgent(
            logs_dir=Path(tmp) / "polling-logs",
            goal_surface="app_server",
            goal_harness_mode="codex_goal_harness",
            goal_harness_access_packet_mode="compact",
            goal_harness_experiment_protocol="max5_blind_loop_no_feedback",
            goal_harness_max_rounds=5,
        )
        assert polling_agent.goal_harness_prompt_polling_rounds == 5

    print("harbor host Codex Goal agent smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
