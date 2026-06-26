#!/usr/bin/env python3
"""Smoke-test benchmark-specific agent runtime layer plans."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "benchmark_agent_runtime_layer.py"


def _run_json(args: list[str]) -> dict:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-runtime-layer-") as tmp:
        workspace = Path(tmp) / "loopx-bench"
        public = _run_json(
            [
                "--benchmark",
                "all",
                "--workspace",
                str(workspace),
                "--pretty",
            ]
        )
        public_text = json.dumps(public, sort_keys=True)

        assert (
            public["schema_version"] == "benchmark_agent_runtime_layer_plan_v0"
        ), public
        assert public["ready"] is True, public
        assert public["boundary"]["private_paths_recorded"] is False, public
        assert public["workspace"]["path_recorded"] is False, public
        assert str(workspace) not in public_text, public_text

        profiles = {
            profile["benchmark_id"]: profile for profile in public["profiles"]
        }
        assert set(profiles) == {
            "terminal-bench",
            "swe-marathon",
            "skillsbench",
        }, profiles
        assert (
            profiles["terminal-bench"]["layer_id"]
            == profiles["swe-marathon"]["layer_id"]
            == "harbor_codex_cli_tools"
        ), profiles
        assert profiles["skillsbench"]["layer_id"] == "benchflow_js_agent_runtime"
        assert profiles["skillsbench"]["runtime_family"] == "benchflow"

        terminal = profiles["terminal-bench"]
        terminal_args = terminal["runner_fragments"]["harbor_cli_args"]
        assert terminal["runner_fragments"]["recommended_agent"] == (
            "codex-api-key-no-search"
        )
        assert "uv run --no-default-groups harbor run" in terminal[
            "runner_fragments"
        ]["local_harbor_checkout_command_prefix"]
        assert "terminal_bench_no_rebuild_guard.py" in terminal[
            "runner_fragments"
        ]["terminal_bench_no_rebuild_guard_command"]
        assert "terminal_bench_task_image_bootstrap.py" in terminal[
            "runner_fragments"
        ]["terminal_bench_task_image_bootstrap_command"]
        assert "terminal_bench_safe_run_id.py" in terminal["runner_fragments"][
            "terminal_bench_safe_run_id_command"
        ]
        host_goal = terminal["runner_fragments"][
            "terminal_bench_host_codex_goal_agent"
        ]
        assert host_goal["agent_import_path"] == (
            "terminal_bench_host_codex_goal_agent:HostCodexGoalAgent"
        )
        assert host_goal["pythonpath_source"] == "scripts/"
        assert host_goal["required_host_commands"] == ["codex", "tmux", "docker"]
        assert "--agent-import-path" in host_goal["recommended_tb_args"]
        assert "goal_surface=app_server" in host_goal["recommended_tb_args"]
        baseline_tb_args = host_goal["recommended_goal_baseline_tb_args"]
        baseline_tb_text = " ".join(baseline_tb_args)
        assert "--dataset-path" in baseline_tb_args
        assert "--task-id" in baseline_tb_args
        assert "--output-path" in baseline_tb_args
        assert "--run-id" in baseline_tb_args
        assert "$RUN_ID" in baseline_tb_args
        assert "--no-upload-results" in baseline_tb_args
        assert "--no-rebuild" in baseline_tb_args
        assert "goal_surface=app_server" in baseline_tb_args
        assert "HostCodexGoalAgent" in baseline_tb_text
        treatment_tb_args = host_goal["recommended_loopx_prompt_polling_tb_args"]
        assert "loopx_mode=codex_loopx" in treatment_tb_args
        assert "loopx_access_packet_mode=compact" in treatment_tb_args
        assert "loopx_case_id=<case-id>" in treatment_tb_args
        assert "loopx_arm_id=loopx_prompt_polling_test" in treatment_tb_args
        assert "loopx_max_rounds=5" in treatment_tb_args
        proof_gate = host_goal["official_hello_world_proof_gate"]
        assert proof_gate["case_id"] == "hello-world"
        assert "terminal_bench_safe_run_id.py" in proof_gate["safe_run_id_command"]
        assert "hello-world-host-codex-goal" in proof_gate["safe_run_id_command"]
        assert proof_gate["no_upload_required"] is True
        assert proof_gate["runner_or_scorer_behavior_changed"] is False
        assert "hello-world" in proof_gate["tb_args"]
        assert "--no-upload-results" in proof_gate["tb_args"]
        assert "--no-rebuild" in proof_gate["tb_args"]
        assert "task_image_exists_or_bootstrap_done" in (
            proof_gate["required_prelaunch_gates"]
        )
        assert "terminal_bench_official_result_reducer.py" in (
            proof_gate["compact_result_reducer"]
        )
        assert "--results-json" in proof_gate["compact_result_reducer"]
        assert "--run-metadata-json" in proof_gate["compact_result_reducer"]
        assert host_goal["goal_surface"] == "app_server"
        assert host_goal["fallback_goal_surface"] == "tui"
        assert "thread/goal/set" in host_goal["preflight_gate"]
        assert (
            "terminal_bench_no_rebuild_guard_command"
            not in profiles["swe-marathon"]["runner_fragments"]
        )
        assert (
            "terminal_bench_task_image_bootstrap_command"
            not in profiles["swe-marathon"]["runner_fragments"]
        )
        assert (
            "terminal_bench_safe_run_id_command"
            not in profiles["swe-marathon"]["runner_fragments"]
        )
        assert (
            "terminal_bench_host_codex_goal_agent"
            not in profiles["swe-marathon"]["runner_fragments"]
        )
        swe_host_goal = profiles["swe-marathon"]["runner_fragments"][
            "harbor_host_codex_goal_agent"
        ]
        assert swe_host_goal["agent_import_path"] == (
            "harbor_host_codex_goal_agent:HarborHostCodexGoalAgent"
        )
        assert swe_host_goal["pythonpath_source"] == "scripts/"
        assert swe_host_goal["required_host_commands"] == ["codex", "tmux"]
        assert swe_host_goal["command_bridge"] == "harbor-env-exec"
        assert swe_host_goal["goal_surface"] == "app_server"
        assert swe_host_goal["fallback_goal_surface"] == "tui"
        assert "goal_surface=app_server" in swe_host_goal["recommended_harbor_args"]
        assert swe_host_goal["pre_rename_agent_kwargs_allowed"] is False
        assert swe_host_goal["recommended_goal_baseline_harbor_args"] == (
            swe_host_goal["recommended_harbor_args"]
        )
        swe_treatment_args = swe_host_goal[
            "recommended_loopx_prompt_polling_harbor_args"
        ]
        swe_treatment_text = " ".join(swe_treatment_args)
        assert "goal_surface=app_server" in swe_treatment_args
        assert "reasoning_effort=high" in swe_treatment_args
        assert "loopx_mode=codex_loopx" in swe_treatment_args
        assert "loopx_access_packet_mode=compact" in swe_treatment_args
        assert "loopx_cli_bridge_enabled=true" in swe_treatment_args
        assert (
            "loopx_experiment_protocol=max5_blind_loop_no_feedback"
            in swe_treatment_args
        )
        assert "loopx_prompt_polling_rounds=5" in swe_treatment_args
        assert (
            "loopx_prompt_polling_round_timeout_sec=<seconds>"
            in swe_treatment_args
        )
        assert "loopx_case_id=<case-id>" in swe_treatment_args
        assert "loopx_arm_id=loopx_prompt_polling_test" in swe_treatment_args
        assert "goal_harness" not in swe_treatment_text
        assert "goal-harness" not in swe_treatment_text
        assert "thread/goal/get" in swe_host_goal["preflight_gate"]
        assert "--mounts" in terminal_args, terminal_args
        assert "--agent-env" in terminal_args, terminal_args
        assert (
            "loopx_codex_install_strategy=require_existing_codex"
            in terminal_args
        ), terminal_args
        assert terminal["container_contract"]["required_commands"] == [
            "codex",
            "rg",
        ], terminal
        assert terminal["container_contract"]["optional_commands"] == ["curl"]
        assert "nvm_install_per_case" in terminal["forbidden_case_runtime_steps"]
        assert "npm_global_agent_runtime_install_per_case" in (
            terminal["forbidden_case_runtime_steps"]
        )

        skillsbench = profiles["skillsbench"]
        assert (
            skillsbench["host_materialization"]["materializer_status"]
            == "implemented"
        )
        assert (
            skillsbench["host_materialization"]["script"]
            == "scripts/skillsbench_agent_runtime_layer.py"
        )
        assert "codex-acp" in skillsbench["container_contract"]["required_commands"]
        assert "/opt/benchflow" in skillsbench["container_contract"]["environment"][
            "PATH"
        ]

        private = _run_json(
            [
                "--benchmark",
                "terminal-bench",
                "--workspace",
                str(workspace),
                "--emit-private-runner-fragments",
            ]
        )
        assert private["boundary"]["private_paths_recorded"] is True, private
        assert private["workspace"]["path_recorded"] is True, private
        assert str(workspace) in json.dumps(private), private

    print("benchmark-agent-runtime-layer smoke passed")


if __name__ == "__main__":
    main()
