#!/usr/bin/env python3
"""Smoke-test the SkillsBench compact adapter and ledger route."""

from __future__ import annotations

import contextlib
import io
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import (  # noqa: E402
    build_benchmark_claim_review,
    build_benchmark_verifier_attribution_review,
    build_skillsbench_benchmark_run,
    build_skillsbench_benchflow_result_benchmark_run,
    build_skillsbench_local_driver_a2a_contract,
    build_skillsbench_worker_handshake_preflight,
    SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION,
    SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION,
)
from goal_harness.benchmark_ledger import (  # noqa: E402
    load_benchmark_run_ledger,
    update_benchmark_run_ledger,
)
from goal_harness.benchmark_adapters.skillsbench_acp_relay import (  # noqa: E402
    SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION,
    run_skillsbench_local_acp_relay_probe,
)
from goal_harness.benchmark_adapters.skillsbench_remote_bridge import (  # noqa: E402
    SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_SCHEMA_VERSION,
    run_skillsbench_remote_command_file_bridge_probe,
)
from goal_harness.status import compact_benchmark_run  # noqa: E402
from scripts.skillsbench_automation_loop import (  # noqa: E402
    CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD,
    CODEX_ACP_RUNTIME_DEPS_SETUP_CMD,
    CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD,
    DEFAULT_MAX_ROUNDS,
    DECLARED_DONE_MARKER,
    DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN,
    DOCKER_APT_RETRY_BEGIN,
    DOCKER_APP_SKILLS_MOUNT_BEGIN,
    DOCKER_HOST_CPU_ENV,
    LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION,
    PRODUCT_MODE_CASE_STATE_PATH,
    PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION,
    _tail,
    _blind_loop_persistent_continuation_clause,
    _build_product_mode_user,
    _merge_app_server_goal_worker_trace_summary,
    _merge_acp_trajectory_summary,
    _merge_final_result_round_reward,
    _round_result_declared_done,
    build_compose_setup_diagnostic,
    build_plan,
    build_runner_failure_compact,
    main as skillsbench_automation_loop_main,
    materialize_local_codex_participant,
    inspect_skillsbench_worker_handshake,
    parse_args,
    product_mode_case_state_seed_text,
    reduce_result,
    summarize_acp_trajectory,
    stage_task_for_sandbox,
)
import scripts.skillsbench_automation_loop as skillsbench_loop  # noqa: E402


GOAL_ID = "skillsbench-benchmark-run-fixture"


def assert_prerequisites_include(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, value in expected.items():
        assert actual.get(key) == value, (key, actual)


def test_skillsbench_default_blind_loop_budget_is_five() -> None:
    args = parse_args([])
    assert args.max_rounds == DEFAULT_MAX_ROUNDS == 5, args
    assert "blind-loop" in args.route, args
    assert args.route != "codex-goal-mode-baseline", args


def test_skillsbench_local_driver_a2a_contract_keeps_codex_local() -> None:
    payload = build_skillsbench_local_driver_a2a_contract(
        task_id="ada-bathroom-plan-repair",
        local_codex_driver_ready=True,
        local_a2a_participant_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_local_codex_cli_participant_not_materialized"
    ), payload
    assert payload["local_driver_contract"]["ready"] is False, payload
    assert (
        payload["local_driver_contract"]["codex_cli_participant_materialized"]
        is False
    ), payload
    assert (
        payload["local_driver_contract"]["a2a_worker_handshake_materialized"]
        is False
    ), payload
    assert payload["local_driver_contract"]["credential_sync_allowed"] is False, payload
    assert payload["remote_executor_contract"]["ready"] is True, payload
    assert (
        payload["remote_executor_contract"]["remote_codex_runtime_allowed"] is False
    ), payload
    assert (
        payload["remote_executor_contract"]["remote_model_api_invocation_allowed"]
        is False
    ), payload
    assert payload["boundary"]["upload_allowed"] is False, payload
    assert payload["boundary"]["submit_allowed"] is False, payload
    assert payload["mini_pair"]["routes"] == [
        "raw-codex-autonomous-max5",
        "goal-harness-product-mode",
    ], payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in (
        "/Users/",
        "~/.codex",
        "OPENAI_API_KEY",
        "HF_TOKEN",
        "raw_task_text_publication_allowed",
    ):
        assert forbidden not in text, forbidden


def test_skillsbench_local_driver_a2a_contract_ready_only_after_both_sides() -> None:
    payload = build_skillsbench_local_driver_a2a_contract(
        task_id="ada-bathroom-plan-repair",
        local_codex_driver_ready=True,
        local_a2a_participant_ready=True,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is True, payload
    assert (
        payload["first_blocker"]
        == "ready_for_skillsbench_local_driver_a2a_mini_pair"
    ), payload
    assert (
        payload["next_action"] == "launch_no_upload_skillsbench_local_driver_a2a_mini_pair"
    ), payload
    assert payload["local_driver_contract"]["ready"] is True, payload
    assert payload["remote_executor_contract"]["ready"] is True, payload
    assert payload["boundary"]["raw_logs_public"] is False, payload
    assert payload["read_boundary"]["compact_only"] is True, payload


def test_skillsbench_local_driver_a2a_contract_distinguishes_cli_from_handshake() -> None:
    payload = build_skillsbench_local_driver_a2a_contract(
        task_id="ada-bathroom-plan-repair",
        local_codex_driver_ready=True,
        local_codex_cli_participant_ready=True,
        local_a2a_worker_handshake_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_local_acp_relay_missing"
    ), payload
    assert (
        payload["next_action"]
        == "wire_local_acp_relay_before_mini_pair"
    ), payload
    assert (
        payload["local_driver_contract"]["codex_cli_participant_materialized"]
        is True
    ), payload
    assert (
        payload["local_driver_contract"]["a2a_worker_handshake_materialized"]
        is False
    ), payload
    assert payload["local_driver_contract"]["worker_protocol"] == "acp_stdio", payload


def test_skillsbench_worker_handshake_preflight_exposes_acp_relay_gap() -> None:
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "skillsbench_local_acp_relay_missing", payload
    assert payload["next_action"] == "implement_local_acp_stdio_relay_before_mini_pair", payload
    assert payload["benchflow_contract"]["worker_protocol"] == "acp_stdio", payload
    assert payload["benchflow_contract"]["stdio_transport_required"] is True, payload
    assert payload["local_driver_contract"]["remote_codex_runtime_allowed"] is False, payload
    assert payload["boundary"]["raw_task_text_read"] is False, payload
    assert payload["boundary"]["credential_values_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_distinguishes_host_transport() -> None:
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=True,
        host_local_acp_transport_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"] == "skillsbench_host_local_acp_transport_missing"
    ), payload
    assert (
        payload["next_action"] == "wire_host_local_acp_transport_before_mini_pair"
    ), payload
    assert (
        payload["local_driver_contract"]["acp_relay_materialized"] is True
    ), payload
    assert (
        payload["local_driver_contract"]["host_local_acp_transport_materialized"]
        is False
    ), payload


def test_skillsbench_worker_handshake_preflight_distinguishes_remote_bridge() -> None:
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=True,
        host_local_acp_transport_ready=True,
        remote_command_file_bridge_ready=False,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "skillsbench_remote_command_file_bridge_missing"
    assert (
        payload["next_action"]
        == "wire_bounded_remote_command_file_bridge_before_mini_pair"
    ), payload
    assert (
        payload["local_driver_contract"]["host_local_acp_transport_materialized"]
        is True
    ), payload
    assert (
        payload["local_driver_contract"]["remote_command_file_bridge_materialized"]
        is False
    ), payload


def test_skillsbench_remote_command_file_bridge_probe_requires_command() -> None:
    payload = run_skillsbench_remote_command_file_bridge_probe(None)
    assert (
        payload["schema_version"]
        == SKILLSBENCH_REMOTE_COMMAND_FILE_BRIDGE_PROBE_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert (
        payload["first_blocker"]
        == "skillsbench_remote_command_file_bridge_probe_command_missing"
    ), payload
    assert payload["bridge_command_invoked"] is False, payload
    assert payload["raw_command_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload


def test_skillsbench_remote_command_file_bridge_probe_fake_bridge_ready() -> None:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/skillsbench_remote_command_file_bridge.py"),
        "--serve-probe",
    ]
    payload = run_skillsbench_remote_command_file_bridge_probe(command)
    assert payload["ready"] is True, payload
    assert (
        payload["first_blocker"] == "skillsbench_remote_command_file_bridge_ready"
    ), payload
    assert payload["bridge_command_invoked"] is True, payload
    assert payload["operation_count"] == 4, payload
    assert payload["missing_operations"] == [], payload
    assert payload["failed_operations"] == [], payload
    assert payload["boundary_violations"] == [], payload
    assert {item["kind"] for item in payload["operations"]} == {
        "exec",
        "write_file",
        "read_file",
        "cleanup",
    }, payload
    assert payload["raw_command_recorded"] is False, payload
    assert payload["raw_stdout_recorded"] is False, payload
    assert payload["raw_stderr_recorded"] is False, payload
    assert payload["raw_task_text_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload
    assert payload["remote_paths_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_accepts_bridge_probe() -> None:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/skillsbench_remote_command_file_bridge.py"),
        "--serve-probe",
    ]
    bridge_probe = run_skillsbench_remote_command_file_bridge_probe(command)
    payload = build_skillsbench_worker_handshake_preflight(
        task_id="ada-bathroom-plan-repair",
        benchflow_available=True,
        benchflow_agent_registry_available=True,
        benchflow_acp_runtime_available=True,
        default_codex_agent="codex-acp",
        codex_agent_protocol="acp",
        codex_agent_launch_registered=True,
        local_codex_cli_participant_ready=True,
        local_acp_relay_ready=True,
        host_local_acp_transport_ready=True,
        remote_command_file_bridge_probe=bridge_probe,
        remote_executor_ready=True,
        remote_task_data_ready=True,
    )
    assert payload["ready"] is True, payload
    assert (
        payload["first_blocker"]
        == "ready_for_skillsbench_local_driver_worker_handshake"
    ), payload
    assert (
        payload["local_driver_contract"]["remote_command_file_bridge_materialized"]
        is True
    ), payload
    assert (
        payload["local_driver_contract"][
            "remote_command_file_bridge_readiness_source"
        ]
        == "probe"
    ), payload
    assert (
        payload["local_driver_contract"]["remote_command_file_bridge_probe"]["ready"]
        is True
    ), payload
    assert payload["remote_executor_contract"]["command_file_bridge_ready"] is True
    assert "skillsbench_remote_command_file_bridge_missing" not in payload["blockers"]


def test_skillsbench_local_acp_relay_probe_completes_stdio_handshake() -> None:
    payload = run_skillsbench_local_acp_relay_probe(timeout_sec=10)
    assert (
        payload["schema_version"]
        == SKILLSBENCH_LOCAL_ACP_RELAY_PROBE_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is True, payload
    assert payload["first_blocker"] == "skillsbench_local_acp_relay_ready", payload
    assert payload["worker_protocol"] == "acp_stdio", payload
    assert payload["request_count"] == 4, payload
    assert payload["codex_cli_invoked"] is False, payload
    assert payload["raw_output_recorded"] is False, payload
    assert payload["raw_event_jsonl_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_host_local_acp_transport_probe_uses_benchflow_client() -> None:
    skillsbench_root = REPO_ROOT / ".local/benchmark/externals/skillsbench"
    if not (skillsbench_root / ".venv").exists():
        return
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/skillsbench_automation_loop.py"),
            "--local-driver-worker-handshake-preflight",
            "--local-codex-cli-participant-ready",
            "--local-acp-relay-probe",
            "--host-local-acp-transport-probe",
            "--task-id",
            "ada-bathroom-plan-repair",
        ],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    probe = payload["local_driver_contract"]["host_local_acp_transport_probe"]
    assert probe["ready"] is True, payload
    assert probe["first_blocker"] == "skillsbench_host_local_acp_transport_ready"
    assert probe["benchflow_acp_client_used"] is True, payload
    assert probe["transport"] == "host_local_stdio", payload
    assert probe["container_transport_used"] is False, payload
    assert probe["request_count"] == 4, payload
    assert probe["codex_cli_invoked"] is False, payload
    assert probe["raw_output_recorded"] is False, payload
    assert probe["raw_event_jsonl_recorded"] is False, payload
    assert probe["credential_values_recorded"] is False, payload
    assert probe["host_paths_recorded"] is False, payload
    assert payload["first_blocker"] == "skillsbench_remote_command_file_bridge_missing"
    assert (
        payload["next_action"]
        == "wire_bounded_remote_command_file_bridge_before_mini_pair"
    ), payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_probe_clears_relay_gap() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-worker-preflight-") as tmp:
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/skillsbench_automation_loop.py"),
                "--local-driver-worker-handshake-preflight",
                "--skillsbench-root",
                str(Path(tmp) / "missing-skillsbench"),
                "--local-codex-cli-participant-ready",
                "--local-acp-relay-probe",
                "--task-id",
                "ada-bathroom-plan-repair",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
    assert payload["local_driver_contract"]["acp_relay_materialized"] is True, payload
    assert (
        payload["local_driver_contract"]["acp_relay_probe"]["ready"] is True
    ), payload
    assert "skillsbench_local_acp_relay_missing" not in payload["blockers"], payload
    assert payload["first_blocker"] == "skillsbench_benchflow_runtime_missing"
    assert payload["next_action"] == "install_or_select_skillsbench_benchflow_runtime"
    assert payload["boundary"]["credential_values_recorded"] is False, payload
    text = json.dumps(payload, sort_keys=True)
    for forbidden in ("/Users/", "~/.codex", "OPENAI_API_KEY", "HF_TOKEN"):
        assert forbidden not in text, forbidden


def test_skillsbench_worker_handshake_preflight_missing_runtime_is_compact() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-worker-preflight-") as tmp:
        payload = inspect_skillsbench_worker_handshake(
            skillsbench_root=Path(tmp) / "missing-skillsbench",
            dataset="skillsbench@1.1",
            task_id="ada-bathroom-plan-repair",
            local_codex_cli_participant_ready=True,
        )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert "skillsbench_local_acp_relay_missing" in payload["blockers"], payload
    assert payload["boundary"]["host_paths_recorded"] is False, payload


def test_local_codex_participant_ping_missing_binary_is_compact() -> None:
    payload = materialize_local_codex_participant(
        codex_bin="/definitely/missing/goal-harness-codex",
        timeout_sec=1,
    )
    assert (
        payload["schema_version"]
        == LOCAL_CODEX_PARTICIPANT_MATERIALIZATION_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "local_codex_cli_not_on_path", payload
    assert payload["codex_cli_invoked"] is False, payload
    assert payload["raw_output_recorded"] is False, payload
    assert payload["raw_event_jsonl_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert payload["host_paths_recorded"] is False, payload


def test_blind_loop_continuation_reprojects_round_one_constraints() -> None:
    clause = _blind_loop_persistent_continuation_clause(
        "Inspect /app/trl only. Do not modify /app/train_grpo.py or "
        "/app/reward_fn.py. Avoid broad rewrites."
    )
    assert "do not invoke /goal mode" in clause, clause
    assert "external Goal Harness CLI" in clause, clause
    assert "upload, submit" in clause, clause
    assert "ask the human" in clause, clause
    assert "/app/train_grpo.py" in clause, clause
    assert "/app/reward_fn.py" in clause, clause
    assert "/app/trl" not in clause, clause


def test_product_mode_declared_done_marker_detection() -> None:
    class FakeRoundResult:
        trajectory = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": f"Done. {DECLARED_DONE_MARKER}",
                    }
                ],
            }
        ]

    assert _round_result_declared_done(FakeRoundResult()) is True


def test_product_mode_case_state_seed_uses_active_goal_shape() -> None:
    seed = product_mode_case_state_seed_text(
        task_id="sample-task",
        route="goal-harness-product-mode",
        max_rounds=5,
    )
    assert f"goal_id: {skillsbench_loop.PRODUCT_MODE_CASE_GOAL_ID}" in seed
    assert f"schema_version: {PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION}" in seed
    assert f"case_state_path: `{PRODUCT_MODE_CASE_STATE_PATH}`" in seed
    assert "## Agent Todo" in seed
    assert "## Local Evidence" in seed
    assert "## Replan Log" in seed
    assert "## Remaining Goals" in seed
    assert ".goal-harness-case-state.md" not in seed


def test_product_mode_declared_done_requires_case_state_depth() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-depth-gate-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_depth_gate_fixture"
        rollout_name = "case__goal_harness_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        trajectory_path.write_text(
            json.dumps(
                {
                    "type": "user_message",
                    "text": f"Maintain {PRODUCT_MODE_CASE_STATE_PATH}.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-product-mode",
            "goal_harness_state_reads": 0,
            "goal_harness_state_writes": 0,
            "goal_harness_case_state_reads": 0,
            "goal_harness_case_state_writes": 0,
            "heartbeat_count": 0,
            "controller_action_decisions": 0,
            "initial_prompt_count": 0,
            "followup_prompt_count": 0,
            "stop_decision_count": 0,
            "reward_observation_count": 0,
            "round_rewards": [],
        }
        plan = {
            "jobs_dir": str(jobs_dir),
            "job_name": job_name,
            "rollout_name": rollout_name,
        }
        saved_modules = {
            name: sys.modules.get(name)
            for name in (
                "benchflow",
                "benchflow.sandbox",
                "benchflow.sandbox.user",
            )
        }
        fake_benchflow = types.ModuleType("benchflow")
        fake_sandbox = types.ModuleType("benchflow.sandbox")
        fake_user = types.ModuleType("benchflow.sandbox.user")

        class FakeBaseUser:
            pass

        class FakeRoundResultBase:
            pass

        fake_user.BaseUser = FakeBaseUser
        fake_user.RoundResult = FakeRoundResultBase
        sys.modules["benchflow"] = fake_benchflow
        sys.modules["benchflow.sandbox"] = fake_sandbox
        sys.modules["benchflow.sandbox.user"] = fake_user
        try:
            user = _build_product_mode_user(
                route="goal-harness-product-mode",
                max_rounds=5,
                trace=trace,
                plan=plan,
            )
        finally:
            for name, module in saved_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        class FakeRoundResult:
            rewards = {}
            trajectory = [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Done. {DECLARED_DONE_MARKER}",
                        }
                    ],
                }
            ]

        prompt = asyncio.run(
            user.run(
                1,
                "Fix the fixture.",
                round_result=FakeRoundResult(),
            )
        )
        assert prompt is not None, trace
        assert "not evidence that the official verifier passed or failed" in prompt
        assert PRODUCT_MODE_CASE_STATE_PATH in prompt
        assert trace["product_mode_depth_gate_gap"] is True, trace
        assert trace["product_mode_depth_gate_gap_round"] == 1, trace
        assert trace["last_decision"] == "send_product_mode_depth_gate_continuation"
        assert trace["followup_prompt_count"] == 1, trace
        assert trace["stop_decision_count"] == 0, trace
        assert trace.get("agent_declared_done") is not True, trace


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_registry(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    registry_path = project / ".goal-harness" / "registry.json"
    (project / Path(state_file).parent).mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active-read-only\n"
        "updated_at: 2026-06-14T00:00:00+00:00\n"
        "---\n\n"
        "# SkillsBench Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Build a compact SkillsBench adapter skeleton.\n",
        encoding="utf-8",
    )
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "updated_at": "2026-06-14T00:00:00+00:00",
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "benchmark-ledger",
                    "status": "active-read-only",
                    "state_file": state_file,
                    "repo": str(project),
                    "adapter": {
                        "kind": "harness_self_improvement",
                        "status": "connected-read-only",
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ],
        },
    )
    return registry_path, runtime


def compact_skillsbench_run(
    *,
    task_id: str,
    mode: str,
    score: float,
    passed: bool,
    exception_type: str = "",
    round_reward_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trial: dict[str, Any] = {
        "task_id": task_id,
        "trial_name": f"{task_id}_{mode}",
        "source": "skillsbench@1.1",
        "reward": {"reward": score},
        "trajectory_present": False,
        "verifier_reward_present": True,
        "artifact_manifest_present": True,
        "trial_result_present": True,
    }
    if exception_type:
        trial["exception_type"] = exception_type
    payload = {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "job_name": f"skillsbench_1_1_{task_id}_{mode}",
        "mode": mode,
        "agent": {"name": "codex", "model": "gpt-5.5"},
        "official_task_score": {
            "kind": "skillsbench_verifier_reward",
            "value": score,
            "passed": passed,
        },
        "leaderboard_evidence": False,
        "submit_eligible": False,
        "trials": [trial],
    }
    if round_reward_trace is not None:
        payload["round_reward_trace"] = round_reward_trace
    compact = compact_benchmark_run(payload)
    assert compact is not None, payload
    return compact


def test_skillsbench_skeleton_builder() -> None:
    compact = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="goal-harness-blind-loop-treatment",
            task_id="citation-check",
        )
    )
    assert compact is not None
    assert compact["benchmark_id"] == "skillsbench@1.1", compact
    assert compact["mode"] == "skillsbench_goal_harness_blind_loop_treatment"
    assert compact["real_run"] is False, compact
    assert compact["submit_eligible"] is False, compact
    assert compact["leaderboard_evidence"] is False, compact
    assert compact["validation"]["all_passed"] is True, compact
    assert "do_not_read_raw_task_prompt_solution_or_trajectory" in compact[
        "stop_conditions"
    ], compact
    assert compact["goal_harness_inside_case"] is False, compact
    assert compact["episode_policy"]["raw_trace_recorded"] is False, compact
    assert compact["native_goal_mode_invoked"] is False, compact
    assert compact["codex_acp_protocol_used"] is True, compact
    assert compact["blind_loop"] is True, compact
    assert compact["official_feedback_blinded"] is True, compact
    assert compact["reward_feedback_forwarded"] is False, compact
    assert compact["skillsbench_route_semantics"] == (
        "codex_acp_ordinary_agent_with_outer_goal_harness_blind_loop_no_reward_feedback"
    ), compact

    blind_baseline = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="codex-acp-blind-loop-baseline",
            task_id="citation-check",
        )
    )
    assert blind_baseline is not None
    assert blind_baseline["mode"] == "skillsbench_codex_acp_blind_loop_baseline"
    assert blind_baseline["goal_harness_automation_loop"] is False, blind_baseline
    assert blind_baseline["blind_loop"] is True, blind_baseline
    assert blind_baseline["official_feedback_blinded"] is True, blind_baseline
    assert blind_baseline["reward_feedback_forwarded"] is False, blind_baseline

    baseline = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="codex-goal-mode-baseline",
            task_id="citation-check",
        )
    )
    assert baseline is not None
    assert baseline["mode"] == "codex_goal_mode_baseline", baseline
    assert baseline["native_goal_mode_requested"] is True, baseline
    assert baseline["native_goal_mode_invoked"] is False, baseline
    assert baseline["native_goal_mode_confirmation_status"] == (
        "unconfirmed_acp_prompt_text_not_interactive_cli_slash_command"
    ), baseline
    assert baseline["codex_acp_protocol_used"] is True, baseline
    assert baseline["inner_codex_goal_mode"] is True, baseline
    assert baseline["skillsbench_route_semantics"] == (
        "codex_acp_goal_prompt_request_no_reward_followup_unconfirmed_native_goal_mode"
    ), baseline

    raw_product_baseline = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="raw-codex-autonomous-max5",
            task_id="citation-check",
        )
    )
    assert raw_product_baseline is not None
    assert raw_product_baseline["mode"] == (
        "skillsbench_raw_codex_autonomous_max5_baseline"
    ), raw_product_baseline
    assert raw_product_baseline["product_mode"] is True, raw_product_baseline
    assert raw_product_baseline["goal_harness_automation_loop"] is False, (
        raw_product_baseline
    )
    assert raw_product_baseline["official_feedback_blinded"] is True, (
        raw_product_baseline
    )
    assert raw_product_baseline["reward_feedback_forwarded"] is False, (
        raw_product_baseline
    )

    product_treatment = compact_benchmark_run(
        build_skillsbench_benchmark_run(
            route="goal-harness-product-mode",
            task_id="citation-check",
        )
    )
    assert product_treatment is not None
    assert product_treatment["mode"] == (
        "skillsbench_goal_harness_product_mode_treatment"
    ), product_treatment
    assert product_treatment["product_mode"] is True, product_treatment
    assert product_treatment["goal_harness_automation_loop"] is True, (
        product_treatment
    )
    assert product_treatment["goal_harness_inside_case"] is True, product_treatment
    assert product_treatment["case_semantics_changed_by_harness"] is True, (
        product_treatment
    )
    assert product_treatment["official_feedback_blinded"] is True, product_treatment
    assert product_treatment["reward_feedback_forwarded"] is False, product_treatment


def test_skillsbench_verifier_tail_disabled_at_zero() -> None:
    assert _tail("private verifier output", limit=0) == ""
    assert _tail("private verifier output", limit=-1) == ""
    assert _tail("abcdef", limit=3) == "def"
    args = parse_args(["--task-id", "sample-task", "--route", "automation-loop-treatment"])
    assert args.max_verifier_output_chars == 0, args
    default_args = parse_args(["--task-id", "sample-task"])
    assert default_args.route == "goal-harness-blind-loop-treatment", default_args


def write_official_skillsbench_result(
    root: Path,
    *,
    reward: float = 0.0,
    task_id: str = "sample-task",
) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-00" / f"{task_id}__abc123"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": task_id,
            "rollout_name": f"{task_id}__abc123",
            "rewards": {"reward": reward},
            "agent": "codex-acp",
            "agent_name": "codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 7,
            "n_prompts": 1,
            "error": None,
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": "acp",
        },
    )
    write_json(
        run_dir / "timing.json",
        {
            "environment_setup": 2.0,
            "agent_setup": 1.0,
            "agent_execution": 3.0,
            "verifier": 4.0,
            "total": 10.0,
        },
    )
    return result_path


def write_official_skillsbench_reward_artifact_recovery_result(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-00" / "sample-task__abc123"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "sample-task",
            "rollout_name": "sample-task__abc123",
            "agent": "codex-acp",
            "agent_name": "codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 7,
            "n_prompts": 1,
            "error": None,
            "verifier_error": "reward missing from compact result",
            "partial_trajectory": False,
            "trajectory_source": "acp",
        },
    )
    reward_path = run_dir / "verifier" / "reward.txt"
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("1\n", encoding="utf-8")
    return result_path


def write_official_skillsbench_runner_error_zero_reward_result(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-20__06-38-51" / "travel-planning__raw"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "travel-planning",
            "rollout_name": "travel-planning__raw",
            "agent": "codex-acp",
            "agent_name": "codex-acp",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": "agent process ended after verifier wrote reward",
            "verifier_error": "reward missing from compact result",
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    reward_path = run_dir / "verifier" / "reward.txt"
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("0\n", encoding="utf-8")
    return result_path


def write_official_skillsbench_oracle_reward_artifact_recovery_result(
    root: Path,
) -> Path:
    run_dir = root / "official" / "2026-06-19__09-28-56" / "sample-task__oracle"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "sample-task",
            "rollout_name": "sample-task__oracle",
            "agent": "oracle",
            "agent_name": "oracle",
            "model": None,
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": None,
            "verifier_error": "verifier crashed: No reward file found",
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    reward_path = run_dir / "verifier" / "reward.txt"
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text("1\n", encoding="utf-8")
    return result_path


def write_official_skillsbench_app_mount_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-00" / "citation-check__abc123"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "citation-check",
            "rollout_name": "citation-check__abc123",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment citation-check. "
                "Command: docker compose cp tasks/citation-check/environment/skills/. "
                "main:/app/skills. Error response from daemon: Could not find "
                "the file /app in container abc123."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 50.0, "total": 50.0})
    return result_path


def write_official_skillsbench_app_skills_mount_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-01" / "audit__def456"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "audit",
            "rollout_name": "audit__def456",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": (
                "Docker compose command failed while copying task skills to "
                "the /app/skills target in the running container."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 50.0, "total": 50.0})
    return result_path


def write_official_skillsbench_docker_port_conflict_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "setup-fuzzing-py__port"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__port",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment setup-fuzzing-py. "
                "Error response from daemon: driver failed programming external "
                "connectivity: Bind for 0.0.0.0:8080 failed: port is already allocated."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 10.0, "total": 10.0})
    return result_path


def write_official_skillsbench_docker_apt_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "setup-fuzzing-py__apt"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__apt",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment setup-fuzzing-py. "
                "The Dockerfile apt-get update step reported a GPG error and "
                "Hash Sum mismatch before agent execution."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 10.0, "total": 10.0})
    return result_path


def write_official_skillsbench_docker_daemon_unavailable_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "paratransit__daemon"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "paratransit-routing",
            "rollout_name": "paratransit-routing__daemon",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment paratransit-routing. "
                "Cannot connect to the Docker daemon at "
                "unix:///Users/example/.colima/default/docker.sock. "
                "Is the docker daemon running?"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 3.0, "total": 3.0})
    return result_path


def write_official_skillsbench_unclassified_compose_failure(root: Path) -> Path:
    run_dir = (
        root
        / "official"
        / "2026-06-15__00-00-03"
        / "paratransit-routing__compose"
    )
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "paratransit-routing",
            "rollout_name": "paratransit-routing__compose",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": (
                "Docker compose command failed for environment "
                "paratransit-routing under /Users/example/private/job/root. "
                "The underlying compose failure did not include a known "
                "setup-category marker."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"total": 10.0})
    return result_path


def write_official_skillsbench_volume_mount_failure(root: Path) -> Path:
    run_dir = (
        root
        / "official"
        / "2026-06-15__00-00-06"
        / "suricata-custom-exfil__volume"
    )
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "suricata-custom-exfil",
            "rollout_name": "suricata-custom-exfil__volume",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Docker compose command failed for environment "
                "suricata-custom-exfil under /Users/example/private/job/root. "
                "Error response from daemon: invalid mount config for type "
                "bind: bind source path does not exist."
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"total": 10.0})
    return result_path


def write_official_skillsbench_codex_acp_libssl_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-02" / "setup-fuzzing-py__ghi789"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__ghi789",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "Process closed stdout (rc=127): Local subprocess exited with "
                "rc=127 before stdout closed.\nstderr: codex-acp: error while "
                "loading shared libraries: libssl.so.3: cannot open shared "
                "object file: No such file or directory"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 60.0, "total": 70.0})
    return result_path


def write_official_skillsbench_codex_acp_glibc_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-03" / "setup-fuzzing-py__jkl012"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "setup-fuzzing-py",
            "rollout_name": "setup-fuzzing-py__jkl012",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "codex-acp runtime unsupported: glibc >=2.34 required by "
                "@zed-industries/codex-acp-linux-x64; found glibc 2.31"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 60.0, "total": 70.0})
    return result_path


def write_official_skillsbench_codex_acp_launch_preflight_failure(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-04" / "ada-bathroom-plan-repair__mno345"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "ada-bathroom-plan-repair",
            "rollout_name": "ada-bathroom-plan-repair__mno345",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 0,
            "error": (
                "codex-acp runtime launch preflight failed: "
                "codex-acp did not start or expose --version/--help rc=127"
            ),
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"environment_setup": 60.0, "total": 70.0})
    return result_path


def write_official_skillsbench_codex_acp_internal_error(root: Path) -> Path:
    run_dir = root / "official" / "2026-06-15__00-00-05" / "llm-prefix-cache-replay__pqr678"
    result_path = run_dir / "result.json"
    write_json(
        result_path,
        {
            "task_name": "llm-prefix-cache-replay",
            "rollout_name": "llm-prefix-cache-replay__pqr678",
            "rewards": None,
            "agent": "codex-acp",
            "agent_name": "",
            "model": "gpt-5.5",
            "n_tool_calls": 0,
            "n_prompts": 1,
            "error": "ACP error -32603: Internal error",
            "verifier_error": None,
            "partial_trajectory": False,
            "trajectory_source": None,
        },
    )
    write_json(run_dir / "timing.json", {"agent_execution": 5.0, "total": 10.0})
    return result_path


def test_skillsbench_official_result_builder() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-result-builder-") as tmp:
        result_path = write_official_skillsbench_result(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["source_runner"] == "official_skillsbench_benchflow_result"
        assert compact["real_run"] is True
        assert compact["submit_eligible"] is False
        assert compact["leaderboard_evidence"] is False
        assert compact["official_task_score"]["value"] == 0.0
        assert compact["official_task_score"]["passed"] is False
        assert compact["score_failure_attribution"] == (
            "official_verifier_solution_failure"
        )
        assert "official_verifier_solution_failure" in compact[
            "failure_attribution_labels"
        ]
        review = build_benchmark_verifier_attribution_review(benchmark_runs=[compact])
        assert review["decision"]["baseline_claim_caveat_resolved"] is True, review
        assert review["routing"]["treatment_eligible"] is True, review
        assert review["run_reviews"][0]["attribution_class"] == (
            "model_or_solution_failure"
        ), review
        assert compact["trials"][0]["task_id"] == "sample-task"
        assert compact["read_boundary"]["compact_only"] is True
        assert compact["read_boundary"]["trajectory_read"] is False


def test_skillsbench_result_reward_artifact_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-reward-recovery-") as tmp:
        result_path = write_official_skillsbench_reward_artifact_recovery_result(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["official_task_score"]["value"] == 1.0, compact
        assert compact["official_task_score"]["passed"] is True, compact
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score_source"] == (
            "official_skillsbench_rollout_verifier_reward_txt"
        ), compact
        assert compact["score_failure_attribution"] == "none", compact
        assert "verifier_infrastructure_failure" not in compact.get(
            "failure_attribution_labels", []
        ), compact
        assert "official_skillsbench:verifier/reward.txt" in compact[
            "evidence_files"
        ], compact
        assert compact["validation"]["validation_scope"] == (
            "official_benchflow_result_json_plus_rollout_reward_artifact"
        ), compact
        assert compact["progress"]["n_completed_trials"] == 1, compact
        assert compact["progress"]["n_errored_trials"] == 0, compact


def test_skillsbench_runner_error_zero_reward_is_case_score_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-zero-reward-") as tmp:
        result_path = write_official_skillsbench_runner_error_zero_reward_result(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="raw-codex-autonomous-max5",
            )
        )
        assert compact is not None
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_reward_txt",
            "passed": False,
            "value": 0.0,
        }, compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_runner_error"
        ), compact
        assert compact["score_failure_attribution"] == (
            "official_score_zero_case_failure"
        ), compact
        assert "skillsbench_runner_error" in compact["failure_attribution_labels"]
        assert "official_score_zero_case_failure" in compact[
            "failure_attribution_labels"
        ]
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-travel-planning-zero-score",
            dry_run=False,
        )
        assert update["entry"]["score_status"] == "failed", update
        assert update["entry"]["failure_class"] == (
            "official_score_zero_case_failure"
        ), update
        assert update["entry"]["failure_scope"] == "case_or_solution", update


def test_skillsbench_oracle_result_reward_artifact_recovery() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-oracle-reward-") as tmp:
        result_path = (
            write_official_skillsbench_oracle_reward_artifact_recovery_result(
                Path(tmp)
            )
        )
        full_run = build_skillsbench_benchflow_result_benchmark_run(
            result_path,
            route="goal-harness-product-mode",
        )
        compact = compact_benchmark_run(full_run)
        assert compact is not None
        assert compact["agent"]["name"] == "oracle", compact
        assert compact["agent"]["model"] == "not_applicable_oracle_runner", compact
        assert compact["official_task_score"]["value"] == 1.0, compact
        assert compact["official_task_score"]["passed"] is True, compact
        assert compact["progress"]["n_completed_trials"] == 1, compact
        assert compact["progress"]["n_errored_trials"] == 0, compact
        assert compact["model_control"]["control_status"] == (
            "not_applicable_oracle_runner"
        ), compact
        assert compact["model_control"]["actual_model_verified"] is True, compact
        assert full_run["interaction_counters"]["codex_acp_protocol_used"] is False
        assert full_run["episode_policy"]["inner_case_actor"] == (
            "skillsbench_oracle_solution_runner"
        ), full_run
        assert full_run["mode_contract"]["codex_acp_protocol_used"] is False, full_run
        assert full_run["mode_contract"]["goal_harness_inside_case"] is False, full_run
        assert full_run["mode_contract"]["official_score_comparable_to_native_codex"] is False
        assert full_run["mode_contract"][
            "official_score_comparable_to_goal_harness_treatment"
        ] is False
        assert "verifier_infrastructure_failure" not in compact.get(
            "failure_attribution_labels", []
        ), compact


def test_skillsbench_app_mount_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-mount-failure-") as tmp:
        result_path = write_official_skillsbench_app_mount_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_environment_app_mount_missing"
        ), compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["progress"]["n_completed_trials"] == 0, compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        text = json.dumps(compact, sort_keys=True)
        assert "/Users/" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_app_skills_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-skills-failure-") as tmp:
        result_path = write_official_skillsbench_app_skills_mount_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_environment_app_mount_missing"
        ), compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact


def test_skillsbench_docker_port_conflict_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-port-") as tmp:
        result_path = write_official_skillsbench_docker_port_conflict_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_port_conflict"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        text = json.dumps(compact, sort_keys=True)
        assert "port is already allocated" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_docker_apt_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-apt-") as tmp:
        result_path = write_official_skillsbench_docker_apt_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-acp-blind-loop-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_apt_repository_failure"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        text = json.dumps(compact, sort_keys=True)
        assert "Hash Sum mismatch" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_docker_daemon_unavailable_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-daemon-") as tmp:
        result_path = write_official_skillsbench_docker_daemon_unavailable_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="raw-codex-autonomous-max5",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_daemon_unavailable"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert "docker_daemon_unavailable" in fingerprint["matched_patterns"], (
            fingerprint
        )
        plan = {
            "route": "raw-codex-autonomous-max5",
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_status": "pending",
            },
            "task_setup_preflight": {
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "ok",
                "sandbox": "docker",
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "raw_trajectory_read": False,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "dockerfile_present": True,
            },
            "task_staging": {
                "schema_version": "skillsbench_task_staging_v0",
                "staged": True,
                "task_skills_removed": True,
                "codex_acp_runtime_tools_patch_applied": True,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "resource_cap_patch": {"applied": False},
            },
        }
        compact["compose_setup_diagnostic"] = build_compose_setup_diagnostic(
            compact,
            plan,
        )
        reduced = compact_benchmark_run(compact)
        assert reduced is not None
        assert reduced["compose_setup_diagnostic"][
            "docker_daemon_unavailable"
        ] is True, reduced
        assert reduced["compose_setup_diagnostic"][
            "unclassified_compose_failure"
        ] is False, reduced
        text = json.dumps(compact, sort_keys=True)
        assert "docker.sock" not in text, compact
        assert "Docker compose command failed" not in text, compact


def test_skillsbench_unclassified_compose_failure_fingerprint() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-compose-generic-") as tmp:
        result_path = write_official_skillsbench_unclassified_compose_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="raw-codex-autonomous-max5",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_setup_failure"
        ), compact
        assert "skillsbench_docker_compose_unclassified_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert fingerprint["schema_version"] == (
            "skillsbench_runner_failure_fingerprint_v0"
        ), fingerprint
        assert fingerprint["matched_patterns"] == [
            "docker_compose_command_failed"
        ], fingerprint
        assert fingerprint["has_host_paths"] is True, fingerprint
        assert fingerprint["raw_error_recorded"] is False, fingerprint
        plan = {
            "route": "raw-codex-autonomous-max5",
            "task_id": "paratransit-routing",
            "task_setup_preflight": {
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "ok",
                "sandbox": "docker",
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "raw_trajectory_read": False,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "dockerfile_present": True,
            },
            "task_staging": {
                "schema_version": "skillsbench_task_staging_v0",
                "staged": True,
                "task_skills_removed": True,
                "codex_acp_runtime_tools_patch_applied": True,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "resource_cap_patch": {"applied": False},
            },
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_status": "ok",
            },
        }
        compact["compose_setup_diagnostic"] = build_compose_setup_diagnostic(
            compact,
            plan,
        )
        reduced = compact_benchmark_run(compact)
        assert reduced is not None
        diagnostic = reduced["compose_setup_diagnostic"]
        assert diagnostic["schema_version"] == (
            "skillsbench_compose_setup_diagnostic_v0"
        ), diagnostic
        assert diagnostic["status"] == (
            "compose_setup_blocked_before_agent_rounds"
        ), diagnostic
        assert diagnostic["agent_rounds_started"] is False, diagnostic
        assert diagnostic["case_attempt_budget_should_count"] is False, diagnostic
        assert diagnostic["official_score_missing"] is True, diagnostic
        assert diagnostic["raw_logs_read"] is False, diagnostic
        assert diagnostic["raw_task_text_read"] is False, diagnostic
        assert diagnostic["raw_trajectory_read"] is False, diagnostic
        text = json.dumps(compact, sort_keys=True)
        assert "Docker compose command failed" not in text, compact
        assert "/Users/example/private/job/root" not in text, compact


def test_skillsbench_volume_mount_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-volume-mount-") as tmp:
        result_path = write_official_skillsbench_volume_mount_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-product-mode",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_volume_mount_failure"
        ), compact
        assert "skillsbench_docker_compose_setup_failure" in compact[
            "failure_attribution_labels"
        ], compact
        assert "skillsbench_docker_compose_unclassified_setup_failure" not in compact[
            "failure_attribution_labels"
        ], compact
        fingerprint = compact["runner_failure_fingerprint"]
        assert "volume_mount_failure" in fingerprint["matched_patterns"], fingerprint
        plan = {
            "route": "goal-harness-product-mode",
            "task_id": "suricata-custom-exfil",
            "task_setup_preflight": {
                "schema_version": "skillsbench_task_setup_preflight_v0",
                "status": "ok",
                "sandbox": "docker",
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "raw_trajectory_read": False,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "dockerfile_present": True,
            },
            "task_staging": {
                "schema_version": "skillsbench_task_staging_v0",
                "staged": True,
                "task_skills_removed": True,
                "codex_acp_runtime_tools_patch_applied": True,
                "apt_setup_risk_detected": False,
                "apt_retry_patch_required": False,
                "resource_cap_patch": {"applied": False},
            },
            "runner_prerequisites": {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_status": "pending",
            },
        }
        compact["compose_setup_diagnostic"] = build_compose_setup_diagnostic(
            compact,
            plan,
        )
        reduced = compact_benchmark_run(compact)
        assert reduced is not None
        diagnostic = reduced["compose_setup_diagnostic"]
        assert diagnostic["volume_mount_failure"] is True, diagnostic
        assert diagnostic["unclassified_compose_failure"] is False, diagnostic
        assert diagnostic["next_diagnostic_action"] == (
            "repair_task_volume_mount_setup_before_product_treatment"
        ), diagnostic
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=reduced,
            run_group_id="skillsbench-volume-mount-repair-test",
            dry_run=False,
        )
        ledger_diagnostic = update["entry"]["compose_setup_diagnostic"]
        assert ledger_diagnostic["volume_mount_failure"] is True, ledger_diagnostic
        assert ledger_diagnostic["unclassified_compose_failure"] is False, (
            ledger_diagnostic
        )
        text = json.dumps(compact, sort_keys=True)
        assert "bind source path" not in text, compact
        assert "/Users/example/private/job/root" not in text, compact


def test_skillsbench_codex_acp_libssl_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-libssl-") as tmp:
        result_path = write_official_skillsbench_codex_acp_libssl_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_runtime_libssl_missing"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact


def test_skillsbench_codex_acp_glibc_failure_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-glibc-") as tmp:
        result_path = write_official_skillsbench_codex_acp_glibc_failure(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_glibc_incompatible"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact


def test_skillsbench_codex_acp_launch_preflight_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-launch-") as tmp:
        result_path = write_official_skillsbench_codex_acp_launch_preflight_failure(
            Path(tmp)
        )
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="codex-goal-mode-baseline",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-ada-bathroom-plan-repair-pair-test",
            dry_run=False,
        )
        assert update["case_decision"]["decision"] == (
            "baseline_codex_acp_runtime_preflight_required"
        ), update
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "ada-bathroom-plan-repair"
        ]
        run = case["runs"][0]
        repair = run["repair_profile"]
        assert repair["repair_class"] == "skillsbench_codex_acp_runtime_preflight"
        assert "codex_acp_runtime_launch_preflight" in repair["required_preflight"]


def test_skillsbench_codex_acp_internal_error_attribution() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-codex-acp-internal-") as tmp:
        result_path = write_official_skillsbench_codex_acp_internal_error(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-blind-loop-treatment",
            )
        )
        assert compact is not None
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_jsonrpc_internal_error"
        ), compact
        assert "skillsbench_codex_acp_transport_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"] == {
            "exception_type": "skillsbench_codex_acp_jsonrpc_internal_error",
            "failure_class": "skillsbench_codex_acp_jsonrpc_internal_error",
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_runner_failure_v0",
        }, compact
        assert compact["progress"]["n_completed_trials"] == 0, compact
        assert compact["progress"]["n_errored_trials"] == 1, compact
        text = json.dumps(compact, sort_keys=True)
        assert "ACP error -32603" not in text, compact
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-llm-prefix-cache-replay-pair-test",
            dry_run=False,
        )
        assert update["entry"]["failure_class"] == (
            "skillsbench_codex_acp_jsonrpc_internal_error"
        ), update
        assert update["entry"]["repair_class"] == (
            "skillsbench_codex_acp_runtime_preflight"
        ), update
        assert update["case_decision"]["decision"] == "single_arm_recorded", update


def test_skillsbench_codex_acp_post_success_trace_recovers_score() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-trace-score-") as tmp:
        result_path = write_official_skillsbench_codex_acp_internal_error(Path(tmp))
        controller_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 3,
            "controller_action_decisions": 3,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 1,
            "reward_observation_count": 2,
            "official_feedback_blinded_count": 2,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                    "tool_calls": 38,
                },
                {
                    "agent_round": 2,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                    "tool_calls": 30,
                },
                {
                    "agent_round": 3,
                    "reward_present": False,
                    "passed": False,
                },
            ],
            "official_success_observed": True,
            "official_success_observation_count": 2,
            "first_success_round": 1,
            "official_feedback_forwarded": False,
            "product_mode": True,
            "max_rounds_budget": 5,
            "last_decision": (
                "stop_after_product_mode_official_success_observed_without_feedback"
            ),
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_score"] == 1.0, compact
        assert compact["official_task_score"] == {
            "kind": "skillsbench_verifier_reward_recovered_from_controller_trace",
            "passed": True,
            "value": 1.0,
        }, compact
        assert compact["official_score_source"] == (
            "goal_harness_controller_trace_best_round_reward_post_success_acp_closeout"
        ), compact
        assert compact["score_failure_attribution"] == "none", compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_codex_acp_jsonrpc_internal_error"
        ), compact
        assert "skillsbench_codex_acp_transport_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["validation"]["official_case_success"] is True, compact
        assert compact["validation"]["official_verifier_status"] == "completed", compact
        assert compact["validation"]["validation_scope"] == (
            "official_benchflow_result_json_plus_goal_harness_controller_trace"
        ), compact
        round_trace = compact["round_reward_trace"]
        assert round_trace["official_score_recovered_from_controller_trace"] is True
        assert round_trace["official_score_recovered_round"] == 1
        assert round_trace["official_score_policy"] == (
            "best_round_for_post_success_acp_closeout_recovery"
        )
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-acp-post-success-score-recovery",
            dry_run=False,
        )
        assert update["entry"]["score_status"] == "passed", update
        assert update["entry"]["failure_scope"] == "passed", update
        assert update["entry"]["failure_class"] == "none", update
        assert update["entry"]["official_score"] == 1.0, update


def test_skillsbench_codex_acp_post_success_finalization_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-post-success-") as tmp:
        result_path = write_official_skillsbench_codex_acp_internal_error(Path(tmp))
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-product-mode",
            )
        )
        assert compact is not None
        compact["runner_prerequisites"] = {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "codex_acp_runtime_launch_preflight": True,
            "codex_acp_runtime_launch_preflight_status": "passed",
        }
        compact["round_reward_trace"] = {
            "schema_version": "benchmark_round_reward_trace_v0",
            "source": "goal_harness_controller_trace",
            "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
            "records": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                }
            ],
            "first_success_round": 1,
            "success_observed": True,
            "max_rounds_budget": 5,
            "official_feedback_blinded": True,
            "reward_feedback_forwarded": False,
        }
        ledger_path = Path(tmp) / "ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-post-success-acp-finalization-test",
            dry_run=False,
        )
        entry = update["entry"]
        assert entry["repair_class"] == (
            "skillsbench_codex_acp_post_success_finalization"
        ), update
        assert entry["round_success_observed"] is True, update
        assert entry["first_success_round"] == 1, update
        assert entry["codex_acp_runtime_preflight_passed"] is True, update
        assert entry["score_status"] == "missing", update
        assert entry["failure_scope"] == "score_missing", update
        repair = entry["repair_profile"]
        assert "round_reward_trace.success_observed" in repair["required_preflight"]
        ledger = load_benchmark_run_ledger(ledger_path)
        run = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "llm-prefix-cache-replay"
        ]["runs"][0]
        assert run["repair_class"] == (
            "skillsbench_codex_acp_post_success_finalization"
        ), run


def test_skillsbench_docker_task_staging_adds_app_skills_mount() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-docker-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "citation-check"
        dockerfile = task / "environment" / "Dockerfile"
        skills = task / "environment" / "skills" / "citation"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: citation\n---\n", encoding="utf-8")
        original_text = "FROM ubuntu:24.04\n\nWORKDIR /root\n"
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="citation-check-setup-probe",
            sandbox="docker",
        )

        assert metadata["staged"] is True, metadata
        assert metadata["app_skills_mount_patch_applied"] is True, metadata
        assert metadata["original_task_mutated"] is False, metadata
        assert staged_path != task, staged_path
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_dockerfile = staged_path / "environment" / "Dockerfile"
        staged_text = staged_dockerfile.read_text(encoding="utf-8")
        assert DOCKER_APP_SKILLS_MOUNT_BEGIN in staged_text, staged_text
        assert "RUN mkdir -p /app /app/skills" in staged_text, staged_text


def test_skillsbench_no_skill_route_removes_staged_task_skills() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-no-skill-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "software-dependency-audit"
        dockerfile = task / "environment" / "Dockerfile"
        skills = task / "environment" / "skills" / "audit"
        skills.mkdir(parents=True)
        (skills / "SKILL.md").write_text("---\nname: audit\n---\n", encoding="utf-8")
        original_text = "FROM ubuntu:24.04\n\nWORKDIR /root\n"
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="software-dependency-audit-baseline",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["staged"] is True, metadata
        assert metadata["include_task_skills"] is False, metadata
        assert metadata["task_skills_removed"] is True, metadata
        assert metadata["app_skills_mount_patch_applied"] is True, metadata
        assert (task / "environment" / "skills").exists()
        assert not (staged_path / "environment" / "skills").exists()
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APP_SKILLS_MOUNT_BEGIN in staged_text, staged_text
        assert "RUN mkdir -p /app /app/skills" in staged_text, staged_text


def test_skillsbench_docker_task_staging_adds_apt_retry_patch() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-apt-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "setup-fuzzing-py"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_text = (
            "FROM ubuntu:20.04\n\n"
            "RUN apt-get update && apt-get install -y curl\n"
        )
        dockerfile.write_text(original_text, encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="setup-fuzzing-py-baseline",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["staged"] is True, metadata
        assert metadata["apt_setup_risk_detected"] is True, metadata
        assert metadata["apt_retry_patch_required"] is True, metadata
        assert metadata["apt_risk_preflight_blocked"] is False, metadata
        assert metadata["apt_retry_patch_applied"] is True, metadata
        assert metadata["codex_acp_runtime_tools_patch_applied"] is True, metadata
        assert metadata["original_task_mutated"] is False, metadata
        assert dockerfile.read_text(encoding="utf-8") == original_text
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APT_RETRY_BEGIN in staged_text, staged_text
        assert DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN in staged_text, staged_text
        assert 'Acquire::Retries "5";' in staged_text, staged_text


def test_skillsbench_runtime_tools_patch_has_own_apt_retry_defaults() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runtime-tools-apt-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "runtime-tools"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text("FROM ubuntu:20.04\n", encoding="utf-8")
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        staged_path, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="runtime-tools-apt",
            sandbox="docker",
            include_task_skills=False,
        )

        assert metadata["apt_retry_patch_required"] is False, metadata
        assert metadata["apt_retry_patch_applied"] is False, metadata
        assert metadata["codex_acp_runtime_tools_patch_applied"] is True, metadata
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert DOCKER_APT_RETRY_BEGIN not in staged_text, staged_text
        assert DOCKER_CODEX_ACP_RUNTIME_TOOLS_BEGIN in staged_text, staged_text
        assert 'Acquire::Retries "5";' in staged_text, staged_text
        assert staged_text.index('Acquire::Retries "5";') < staged_text.index(
            "apt-get update -qq"
        ), staged_text
        assert "curl-minimal" in staged_text, staged_text
        assert "microdnf install -y ca-certificates tar xz" in staged_text, staged_text
        assert "dnf -y install ca-certificates tar xz" in staged_text, staged_text
        assert "dnf -y install ca-certificates curl tar xz" not in staged_text, (
            staged_text
        )


def test_skillsbench_apt_risk_preflight_blocks_full_run_without_benchflow() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-apt-preflight-") as tmp:
        root = Path(tmp)
        task = root / "skillsbench" / "tasks" / "setup-fuzzing-py"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text(
            "FROM ubuntu:20.04\n\nRUN apt-get update && apt-get install -y curl\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        jobs = root / "jobs"
        ledger = root / "benchmark-run-ledger.json"
        args = [
            "--task-id",
            "setup-fuzzing-py",
            "--route",
            "codex-acp-blind-loop-baseline",
            "--skillsbench-root",
            str(root / "skillsbench"),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "setup-fuzzing-py-apt-risk-preflight",
            "--run-group-id",
            "setup-fuzzing-py-apt-risk-preflight",
            "--ledger-path",
            str(ledger),
            "--fail-fast-on-apt-risk",
            "--update-ledger",
        ]
        plan = build_plan(parse_args(args))
        assert plan["task_setup_preflight"]["apt_setup_risk_detected"] is True, plan
        assert plan["task_setup_preflight"]["raw_task_text_read"] is False, plan

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "setup-fuzzing-py-apt-risk-preflight"
            / "setup-fuzzing-py__codex_acp_blind_loop"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_apt_setup_risk_preflight_blocked"
        ), compact
        assert compact["task_staging"]["apt_setup_risk_detected"] is True, compact
        assert compact["task_staging"]["apt_retry_patch_required"] is True, compact
        assert compact["task_staging"]["apt_risk_preflight_blocked"] is True, compact
        assert compact["validation"]["no_raw_task_text_read"] is True, compact

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"][
            "setup-fuzzing-py"
        ]
        assert case["latest_decision"]["decision"] == (
            "baseline_setup_preflight_selection_required"
        ), case
        entry = case["runs"][0]
        assert entry["repair_class"] == "skillsbench_setup_preflight_selection", (
            entry
        )
        assert entry["task_staging"]["apt_risk_preflight_blocked"] is True, (
            entry
        )


def test_skillsbench_docker_task_staging_caps_local_cpu_request() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cpu-cap-stage-") as tmp:
        root = Path(tmp)
        task = root / "tasks" / "debug-trl-grpo"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        original_dockerfile = "FROM python:3.11-slim\n"
        original_task_toml = (
            'version = "1.1"\n\n'
            "[environment]\n"
            "cpus = 4  # four project shards in the official task\n"
            "memory_mb = 2048\n"
        )
        dockerfile.write_text(original_dockerfile, encoding="utf-8")
        (task / "task.toml").write_text(original_task_toml, encoding="utf-8")

        previous = os.environ.get(DOCKER_HOST_CPU_ENV)
        os.environ[DOCKER_HOST_CPU_ENV] = "2"
        try:
            staged_path, metadata = stage_task_for_sandbox(
                task_path=task,
                jobs_dir=root / "jobs",
                job_name="debug-trl-grpo-baseline",
                sandbox="docker",
                include_task_skills=False,
            )
        finally:
            if previous is None:
                os.environ.pop(DOCKER_HOST_CPU_ENV, None)
            else:
                os.environ[DOCKER_HOST_CPU_ENV] = previous

        assert metadata["staged"] is True, metadata
        cap = metadata["resource_cap_patch"]
        assert cap["applied"] is True, metadata
        assert cap["requested_cpus"] == 4.0, metadata
        assert cap["effective_cpus"] == 2.0, metadata
        assert cap["original_task_mutated"] is False, metadata
        assert metadata["codex_acp_runtime_tools_patch_applied"] is True, metadata
        assert "cpus = 4  # four project shards" in (task / "task.toml").read_text(
            encoding="utf-8"
        )
        assert "cpus = 2  # four project shards" in (staged_path / "task.toml").read_text(
            encoding="utf-8"
        )
        assert dockerfile.read_text(encoding="utf-8") == original_dockerfile


def test_skillsbench_runner_plan_supports_baseline_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-plan-") as tmp:
        root = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "software-dependency-audit",
                "--route",
                "codex-goal-mode-baseline",
                "--jobs-dir",
                str(root / "jobs"),
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        plan = payload["launch_plan"]
        assert plan["schema_version"] == "skillsbench_runner_launch_plan_v0", plan
        assert plan["route"] == "codex-goal-mode-baseline", plan
        assert plan["include_task_skills"] is False, plan
        assert plan["outer_timeout_sec"] == 7200, plan
        assert plan["sandbox_setup_timeout_sec"] == 7200, plan
        runner_prerequisites = plan["runner_prerequisites"]
        expected_runner_prerequisites = {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "agent_execution_mode": "container_codex_acp",
            "codex_acp_runtime_container_bootstrap": True,
            "codex_acp_runtime_dependency_preflight": True,
            "codex_acp_runtime_launch_preflight": False,
            "codex_acp_runtime_launch_preflight_stage": (
                "after_agent_install_before_acp_connect"
            ),
            "codex_acp_runtime_launch_preflight_status": "pending",
            "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            "container_codex_acp_install_skipped": False,
            "benchflow_agent_install_skipped_by_runtime_layer": False,
            "host_local_acp_launch": False,
            "host_local_acp_launch_status": "not_requested",
            "remote_command_file_bridge_materialized": False,
        }
        assert_prerequisites_include(
            runner_prerequisites,
            expected_runner_prerequisites,
        )
        assert (
            runner_prerequisites["preinstalled_benchflow_agent_runtime_required"]
            is False
        ), plan
        assert (
            runner_prerequisites["benchflow_agent_runtime_layer_status"]
            == "not_requested"
        ), plan
        assert "curl" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "curl-minimal" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "microdnf install -y ca-certificates tar xz" in (
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        )
        assert "dnf -y install ca-certificates curl tar xz" not in (
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        )
        assert "xz-utils" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert (
            CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD.index("command -v curl")
            < CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD.index("apt-get")
        )
        assert "/tmp/goal-harness-apt-cache" not in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "/var/cache/apt/archives" in CODEX_ACP_RUNTIME_CONTAINER_BOOTSTRAP_CMD
        assert "libssl.so.3" in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "microdnf install -y openssl-libs" in (
            CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        )
        assert "glibc >=2.34" in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "/tmp/goal-harness-apt-cache" not in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "/var/cache/apt/archives" in CODEX_ACP_RUNTIME_DEPS_SETUP_CMD
        assert "/opt/benchflow/bin/codex-acp" in CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD
        assert '"$agent_bin" --version' in CODEX_ACP_RUNTIME_LAUNCH_PREFLIGHT_CMD
        assert plan["rollout_name"].endswith("__codex_goal_mode_baseline"), plan
        assert plan["public_boundary"]["leaderboard_upload"] is False, plan


def test_skillsbench_codex_acp_model_control_warning() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-model-control-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root)
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="automation-loop-treatment",
                runner_warning_labels=["codex_acp_set_model_unsupported"],
            )
        )
        assert compact is not None
        assert compact["runner_warning_labels"] == [
            "codex_acp_set_model_unsupported"
        ], compact
        model_control = compact["model_control"]
        assert model_control["requested_model"] == "gpt-5.5", compact
        assert model_control["reported_model"] == "gpt-5.5", compact
        assert model_control["actual_model_verified"] is False, compact
        assert model_control["control_status"] == (
            "requested_model_not_enforced_by_acp"
        ), compact

        ledger_path = root / "benchmark-run-ledger.json"
        update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-model-control-warning",
            notes="compact runner model-control warning fixture",
            dry_run=False,
        )
        entry = update["entry"]
        assert entry["model_control_status"] == (
            "requested_model_not_enforced_by_acp"
        ), entry
        assert entry["actual_model_verified"] is False, entry
        assert entry["model_warning_labels"] == [
            "codex_acp_set_model_unsupported"
        ], entry


def test_skillsbench_runner_prerequisites_are_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-prereq-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=1.0)
        benchmark_run = build_skillsbench_benchflow_result_benchmark_run(
            result_path,
            route="codex-acp-blind-loop-baseline",
        )
        benchmark_run["runner_prerequisites"] = {
            "schema_version": "skillsbench_runner_prerequisites_v0",
            "codex_acp_runtime_container_bootstrap": True,
            "codex_acp_runtime_dependency_preflight": True,
            "codex_acp_runtime_launch_preflight": True,
            "codex_acp_runtime_launch_preflight_stage": (
                "preinstalled_benchflow_layer_after_sandbox_setup_before_acp_connect"
            ),
            "codex_acp_runtime_launch_preflight_status": "passed",
            "codex_acp_runtime_launch_preflight_rc": 0,
            "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            "container_codex_acp_install_skipped": True,
            "benchflow_agent_install_skipped_by_runtime_layer": True,
            "preinstalled_benchflow_agent_runtime_required": True,
            "benchflow_agent_runtime_layer_ready": True,
            "benchflow_agent_runtime_layer_status": "ready",
            "benchflow_agent_runtime_layer_mount_target": "/opt/benchflow",
            "benchflow_agent_runtime_mount_injected": True,
            "benchflow_agent_runtime_mount_read_only": True,
            "benchflow_agent_runtime_mount_source_recorded": False,
            "codex_acp_runtime_dependency_setup_skipped": True,
            "private_unlisted_detail": "must not compact",
        }
        compact = compact_benchmark_run(benchmark_run)
        assert compact is not None
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_container_bootstrap": True,
                "codex_acp_runtime_dependency_preflight": True,
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_stage": (
                    "preinstalled_benchflow_layer_after_sandbox_setup_before_acp_connect"
                ),
                "codex_acp_runtime_launch_preflight_status": "passed",
                "codex_acp_runtime_launch_preflight_rc": 0,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                "container_codex_acp_install_skipped": True,
                "benchflow_agent_install_skipped_by_runtime_layer": True,
                "preinstalled_benchflow_agent_runtime_required": True,
                "benchflow_agent_runtime_layer_ready": True,
                "benchflow_agent_runtime_layer_status": "ready",
                "benchflow_agent_runtime_layer_mount_target": "/opt/benchflow",
                "benchflow_agent_runtime_mount_injected": True,
                "benchflow_agent_runtime_mount_read_only": True,
                "benchflow_agent_runtime_mount_source_recorded": False,
                "codex_acp_runtime_dependency_setup_skipped": True,
            },
        )
        assert "private_unlisted_detail" not in json.dumps(compact), compact


def test_skillsbench_runner_plan_supports_product_mode_routes() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-product-plan-") as tmp:
        root = Path(tmp)
        for route, suffix in (
            ("raw-codex-autonomous-max5", "raw_codex_autonomous_max5"),
            ("goal-harness-product-mode", "goal_harness_product_mode"),
        ):
            args = parse_args(
                [
                    "--task-id",
                    "software-dependency-audit",
                    "--route",
                    route,
                    "--jobs-dir",
                    str(root / "jobs"),
                ]
            )
            plan = build_plan(args)
            assert plan["route"] == route, plan
            assert plan["max_rounds"] == DEFAULT_MAX_ROUNDS, plan
            assert plan["rollout_name"] == (
                f"software-dependency-audit__{suffix}"
            ), plan


def test_skillsbench_task_staging_metadata_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-task-staging-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        args = parse_args(
            [
                "--task-id",
                "setup-fuzzing-py",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(root / "jobs"),
                "--job-name",
                "setup-fuzzing-py-task-staging-fixture",
            ]
        )
        plan = build_plan(args)
        plan["task_staging"] = {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": True,
            "staged_task_path": "/private/path/must/not/compact",
            "include_task_skills": False,
            "apt_setup_risk_detected": True,
            "apt_retry_patch_required": True,
            "app_skills_mount_patch_applied": False,
            "apt_retry_patch_applied": True,
            "apt_risk_preflight_blocked": False,
            "codex_acp_runtime_tools_patch_applied": True,
            "task_skills_removed": False,
            "original_task_mutated": False,
            "resource_cap_patch": {
                "schema_version": "skillsbench_local_docker_resource_cap_v0",
                "applied": False,
                "host_cpus": 2.0,
                "requested_cpus": 1.0,
                "effective_cpus": 1.0,
                "private_detail": "must not compact",
            },
        }

        compact = reduce_result(args, result_path, plan)

        assert compact["task_staging"] == {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": True,
            "include_task_skills": False,
            "apt_setup_risk_detected": True,
            "apt_retry_patch_required": True,
            "app_skills_mount_patch_applied": False,
            "apt_retry_patch_applied": True,
            "apt_risk_preflight_blocked": False,
            "codex_acp_runtime_tools_patch_applied": True,
            "task_skills_removed": False,
            "original_task_mutated": False,
            "resource_cap_patch": {
                "schema_version": "skillsbench_local_docker_resource_cap_v0",
                "applied": False,
                "host_cpus": 2.0,
                "requested_cpus": 1.0,
                "effective_cpus": 1.0,
            },
        }, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "staged_task_path" not in compact_text, compact
        assert "/private/path" not in compact_text, compact
        assert "private_detail" not in compact_text, compact
        update = update_benchmark_run_ledger(
            ledger_path=root / "ledger.json",
            benchmark_run=compact,
            run_group_id="setup-fuzzing-py-task-staging-fixture",
            dry_run=False,
        )
        entry_staging = update["entry"]["task_staging"]
        assert entry_staging["apt_retry_patch_applied"] is True, update
        assert entry_staging["apt_setup_risk_detected"] is True, update
        assert entry_staging["codex_acp_runtime_tools_patch_applied"] is True, update
        assert "staged_task_path" not in json.dumps(update, sort_keys=True), update


def test_skillsbench_reduce_only_recovers_prepared_task_staging_metadata() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-task-staging-recover-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        args = parse_args(
            [
                "--task-id",
                "setup-fuzzing-py",
                "--route",
                "codex-acp-blind-loop-baseline",
                "--jobs-dir",
                str(root / "jobs"),
                "--job-name",
                "setup-fuzzing-py-task-staging-recover-fixture",
            ]
        )
        plan = build_plan(args)
        prepared = (
            root
            / "jobs"
            / "setup-fuzzing-py-task-staging-recover-fixture"
            / "prepared-tasks"
            / "setup-fuzzing-py"
        )
        dockerfile = prepared / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text(
            "FROM ubuntu:20.04\n"
            f"{DOCKER_APT_RETRY_BEGIN}\n"
            "RUN true\n"
            "# END GOAL_HARNESS_SKILLSBENCH_APT_RETRY\n",
            encoding="utf-8",
        )

        compact = reduce_result(args, result_path, plan)

        assert compact["task_staging"]["staged"] is True, compact
        assert compact["task_staging"]["apt_retry_patch_applied"] is True, compact
        assert compact["task_staging"]["codex_acp_runtime_tools_patch_applied"] is False, compact
        assert compact["task_staging"]["task_skills_removed"] is True, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "prepared-tasks" not in compact_text, compact
        assert "FROM ubuntu" not in compact_text, compact


def test_skillsbench_controller_trace_counts_are_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-controller-trace-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=1.0)
        blind_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-blind-loop-treatment",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 3,
            "controller_action_decisions": 3,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 1,
            "reward_observation_count": 2,
            "verifier_feedback_observation_count": 0,
            "official_feedback_blinded_count": 2,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                    "tool_calls": 5,
                },
                {
                    "agent_round": 2,
                    "reward_present": True,
                    "reward": 1.0,
                    "passed": True,
                    "tool_calls": 7,
                },
            ],
            "official_success_observed": True,
            "official_success_observation_count": 1,
            "first_success_round": 2,
            "official_feedback_forwarded": False,
            "blind_loop": True,
            "max_rounds_budget": 2,
            "goal_harness_state_reads": 0,
            "goal_harness_state_writes": 0,
            "last_decision": "stop_after_blind_loop_official_success_observed_without_feedback",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        blind_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-blind-loop-treatment",
                controller_trace=blind_trace,
            )
        )
        assert blind_compact is not None
        assert blind_compact["blind_loop"] is True, blind_compact
        assert blind_compact["official_feedback_blinded"] is True, blind_compact
        assert blind_compact["reward_feedback_forwarded"] is False, blind_compact
        blind_counters = blind_compact["interaction_counters"]
        assert blind_counters["controller_reward_observation_count"] == 2, blind_compact
        assert blind_counters["controller_round_reward_count"] == 2, blind_compact
        assert blind_counters["controller_official_success_observed"] is True, blind_compact
        assert blind_counters["controller_official_success_observation_count"] == 1, blind_compact
        assert blind_counters["controller_first_success_round"] == 2, blind_compact
        assert blind_counters["controller_verifier_feedback_observation_count"] == 0, blind_compact
        assert blind_counters["controller_official_feedback_blinded_count"] == 2, blind_compact
        assert blind_counters["controller_official_feedback_forwarded"] is False, blind_compact
        assert blind_counters["controller_blind_loop"] is True, blind_compact
        assert blind_counters["controller_max_rounds_budget"] == 2, blind_compact
        round_trace = blind_compact["round_reward_trace"]
        assert round_trace["first_success_round"] == 2, blind_compact
        assert round_trace["success_observed"] is True, blind_compact
        assert round_trace["official_feedback_blinded"] is True, blind_compact
        assert round_trace["reward_feedback_forwarded"] is False, blind_compact
        assert round_trace["final_round"] == 2, blind_compact
        assert round_trace["final_round_reward"] == 1.0, blind_compact
        assert round_trace["best_reward_round"] == 2, blind_compact
        assert round_trace["best_round_reward"] == 1.0, blind_compact
        assert round_trace["best_round_is_final"] is True, blind_compact
        assert round_trace["loop_score_policy"] == (
            "best_round_for_offline_controller_analysis"
        ), blind_compact
        assert round_trace["official_score_policy"] == (
            "final_workspace_official_result"
        ), blind_compact
        assert [item["reward"] for item in round_trace["records"]] == [0.0, 1.0], blind_compact
        assert round_trace["records"][1]["passed"] is True, blind_compact
        assert blind_compact["episode_policy"]["reward_feedback_forwarded"] is False
        assert blind_compact["episode_policy"]["official_feedback_blinded"] is True

        final_result_path = root / "final-result.json"
        write_json(
            final_result_path,
            {
                "rewards": {"reward": 1.0},
                "n_tool_calls": 9,
            },
        )
        partial_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "codex-acp-blind-loop-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "blind_loop": True,
            "max_round_observed": 1,
            "last_decision": "send_blind_scheduled_continuation",
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                }
            ],
            "reward_observation_count": 1,
            "official_success_observed": False,
            "official_success_observation_count": 0,
            "first_success_round": None,
        }
        _merge_final_result_round_reward(partial_trace, final_result_path)
        assert partial_trace["reward_observation_count"] == 2, partial_trace
        assert partial_trace["official_feedback_blinded_count"] == 2, partial_trace
        assert partial_trace["official_success_observed"] is True, partial_trace
        assert partial_trace["official_success_observation_count"] == 1, partial_trace
        assert partial_trace["first_success_round"] == 2, partial_trace
        assert partial_trace["round_rewards"][1]["agent_round"] == 2, partial_trace
        assert partial_trace["round_rewards"][1]["reward"] == 1.0, partial_trace
        assert partial_trace["round_rewards"][1]["source"] == "benchflow_final_result", partial_trace

        depth_gate_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "max_round_observed": 4,
            "last_decision": "continue_after_declared_done_depth_gate_gap",
            "round_rewards": [
                {
                    "agent_round": index,
                    "reward_present": True,
                    "reward": 0.0,
                    "passed": False,
                }
                for index in range(1, 5)
            ],
            "reward_observation_count": 4,
            "official_success_observed": False,
            "official_success_observation_count": 0,
            "first_success_round": None,
        }
        _merge_final_result_round_reward(depth_gate_trace, final_result_path)
        assert depth_gate_trace["reward_observation_count"] == 5, depth_gate_trace
        assert depth_gate_trace["official_success_observed"] is True, depth_gate_trace
        assert depth_gate_trace["first_success_round"] == 5, depth_gate_trace
        assert depth_gate_trace["round_rewards"][4]["agent_round"] == 5, depth_gate_trace
        assert depth_gate_trace["round_rewards"][4]["reward"] == 1.0, depth_gate_trace


def test_skillsbench_round_trace_records_best_round_score() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-best-round-score-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-blind-loop-treatment",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 5,
            "controller_action_decisions": 5,
            "initial_prompt_count": 1,
            "followup_prompt_count": 4,
            "reward_observation_count": 5,
            "official_feedback_blinded_count": 5,
            "round_rewards": [
                {"agent_round": 1, "reward_present": True, "reward": 0.25, "passed": False},
                {"agent_round": 2, "reward_present": True, "reward": 0.25, "passed": False},
                {"agent_round": 3, "reward_present": True, "reward": 0.0, "passed": False},
                {"agent_round": 4, "reward_present": True, "reward": 0.0, "passed": False},
                {"agent_round": 5, "reward_present": True, "reward": 0.0, "passed": False},
            ],
            "official_success_observed": False,
            "first_success_round": None,
            "official_feedback_forwarded": False,
            "blind_loop": True,
            "max_rounds_budget": 5,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-blind-loop-treatment",
                controller_trace=trace,
            )
        )
        assert compact is not None
        round_trace = compact["round_reward_trace"]
        assert compact["official_score"] == 0.0, compact
        assert round_trace["final_round"] == 5, round_trace
        assert round_trace["final_round_reward"] == 0.0, round_trace
        assert round_trace["best_reward_round"] == 1, round_trace
        assert round_trace["best_round_reward"] == 0.25, round_trace
        assert round_trace["best_round_passed"] is False, round_trace
        assert round_trace["best_round_is_final"] is False, round_trace
        assert round_trace["loop_score_policy"] == (
            "best_round_for_offline_controller_analysis"
        ), round_trace

        controller_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "automation-loop-treatment",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "heartbeat_count": 2,
            "controller_action_decisions": 2,
            "initial_prompt_count": 1,
            "followup_prompt_count": 1,
            "stop_decision_count": 0,
            "reward_observation_count": 1,
            "verifier_feedback_observation_count": 1,
            "goal_harness_state_reads": 0,
            "goal_harness_state_writes": 0,
            "last_decision": "send_followup_after_failed_reward",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="automation-loop-treatment",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["controller_trace_present"] is True, compact
        assert counters["heartbeat_count"] == 2, compact
        assert counters["controller_action_decisions"] == 2, compact
        assert counters["controller_initial_prompt_count"] == 1, compact
        assert counters["controller_followup_prompt_count"] == 1, compact
        assert counters["counter_trust_level"] == (
            "official_benchflow_compact_result_plus_goal_harness_controller_trace"
        ), compact
        assert "goal_harness:controller_trace.public.json" in compact["evidence_files"]
        assert compact["read_boundary"]["controller_trace_read"] is True, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "private_verifier_output" not in compact_text
        assert "TASK INSTRUCTION" not in compact_text

        worker_trace_dir = root / "native-worker-traces"
        worker_trace_dir.mkdir()
        write_json(
            worker_trace_dir / "worker-000001.compact.json",
            {
                "schema_version": "skillsbench_host_codex_goal_worker_public_trace_v0",
                "ok": True,
                "route": "codex-app-server-goal-baseline",
                "benchmark_id": "skillsbench@1.1",
                "task_id": "llm-prefix-cache-replay",
                "turn": {
                    "thread_id_present": True,
                    "goal_get_present": True,
                    "goal_status": "active",
                    "turn_id_present": True,
                    "turn_status": "completed",
                    "turn_completed_observed": True,
                    "assistant_message_present": True,
                    "assistant_message_chars": 42,
                    "raw_transcript_recorded": False,
                    "raw_assistant_message_recorded": False,
                },
                "boundary": {
                    "raw_task_text_recorded": False,
                    "raw_logs_recorded": False,
                    "raw_trajectory_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                },
            },
        )
        app_server_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "codex-app-server-goal-baseline",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "native_goal_worker_route": True,
            "native_goal_worker_connected": True,
            "native_goal_worker_connect_count": 1,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_app_server_goal_worker_trace_summary(
            {
                "route": "codex-app-server-goal-baseline",
                "app_server_goal_worker_trace_dir": str(worker_trace_dir),
            },
            app_server_trace,
        )
        native_compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(
                    root / "native",
                    reward=0.0,
                    task_id="llm-prefix-cache-replay",
                ),
                route="codex-app-server-goal-baseline",
                controller_trace=app_server_trace,
            )
        )
        assert native_compact is not None
        assert native_compact["case_id"] == "llm-prefix-cache-replay", native_compact
        assert native_compact["case_ids"] == ["llm-prefix-cache-replay"], native_compact
        assert native_compact["validation"]["goal_harness_controller_trace_present"] is True
        assert native_compact["validation"]["failed_checks"] == [], native_compact
        native_counters = native_compact["interaction_counters"]
        assert native_counters["controller_trace_present"] is True, native_compact
        assert native_counters["native_goal_worker_route"] is True, native_compact
        assert native_counters["native_goal_worker_trace_count"] == 1, native_compact
        assert native_counters["native_goal_worker_ok_count"] == 1, native_compact
        assert native_counters["native_goal_worker_goal_get_count"] == 1, native_compact
        assert native_counters["native_goal_worker_turn_start_count"] == 1, native_compact
        assert native_counters["native_goal_worker_turn_completed_observed_count"] == 1, native_compact
        assert native_counters["native_goal_worker_raw_material_recorded"] is False, native_compact

        baseline = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                write_official_skillsbench_result(root / "baseline", reward=0.0),
                route="codex-goal-mode-baseline",
            )
        )
        assert baseline["native_goal_mode_requested"] is True, baseline
        assert baseline["native_goal_mode_invoked"] is False, baseline
        assert baseline["native_goal_mode_confirmation_status"] == (
            "unconfirmed_acp_prompt_text_not_interactive_cli_slash_command"
        ), baseline
        assert baseline["codex_acp_protocol_used"] is True, baseline
        assert baseline["skillsbench_route_semantics"] == (
            "codex_acp_goal_prompt_request_no_reward_followup_unconfirmed_native_goal_mode"
        ), baseline
        comparison = {
            "schema_version": "benchmark_comparison_v0",
            "task_id": "skillsbench@1.1/sample-task",
            "comparison_id": "skillsbench-controller-trace-fixture",
            "official_task_score_delta": 1.0,
            "claim_boundary": {
                "leaderboard_claim_allowed": False,
                "official_score_uplift_claim_allowed": False,
                "assisted_collaboration_claim_allowed": False,
                "raw_trace_excluded": True,
            },
        }
        review = build_benchmark_claim_review(
            comparison,
            benchmark_runs=[baseline, compact],
        )
        assert "missing_treatment_worker_goal_harness_evidence" not in review[
            "decision"
        ]["blockers"], review
        assert review["treatment_worker_evidence"][
            "outer_goal_harness_controller_present"
        ] is True, review


def test_skillsbench_product_mode_declared_done_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-product-done-") as tmp:
        root = Path(tmp)
        result_path = write_official_skillsbench_result(root, reward=0.25)
        controller_trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "agent_declared_done": True,
            "declared_done_round": 1,
            "declared_done_score": 0.25,
            "heartbeat_count": 1,
            "controller_action_decisions": 1,
            "initial_prompt_count": 1,
            "followup_prompt_count": 0,
            "stop_decision_count": 1,
            "reward_observation_count": 1,
            "official_feedback_blinded_count": 1,
            "official_feedback_forwarded": False,
            "round_rewards": [
                {
                    "agent_round": 1,
                    "reward_present": True,
                    "reward": 0.25,
                    "passed": False,
                }
            ],
            "official_success_observed": False,
            "first_success_round": None,
            "blind_loop": False,
            "case_goal_state_packet_present": True,
            "case_goal_state_init_required": True,
            "case_goal_state_initialized_before_agent": True,
            "case_goal_state_init_status": "passed",
            "case_goal_state_path": PRODUCT_MODE_CASE_STATE_PATH,
            "case_goal_state_schema_version": PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION,
            "declared_done_requires_no_remaining_goals": True,
            "max_rounds_budget": 5,
            "goal_harness_state_reads": 1,
            "goal_harness_state_writes": 1,
            "goal_harness_case_state_reads": 1,
            "goal_harness_case_state_writes": 1,
            "last_decision": "stop_after_agent_declared_done_without_official_feedback",
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="goal-harness-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        assert compact["product_mode"] is True, compact
        assert compact["official_feedback_blinded"] is True, compact
        assert compact["reward_feedback_forwarded"] is False, compact
        counters = compact["interaction_counters"]
        assert counters["product_mode"] is True, compact
        assert counters["case_goal_state_packet_present"] is True, compact
        assert counters["case_goal_state_init_required"] is True, compact
        assert counters["case_goal_state_initialized_before_agent"] is True, compact
        assert counters["case_goal_state_init_status"] == "passed", compact
        assert (
            counters["case_goal_state_schema_version"]
            == PRODUCT_MODE_CASE_STATE_SCHEMA_VERSION
        ), compact
        assert counters["case_goal_state_path"] == PRODUCT_MODE_CASE_STATE_PATH, compact
        assert counters["declared_done_requires_no_remaining_goals"] is True, compact
        assert counters["agent_declared_done"] is True, compact
        assert counters["declared_done_round"] == 1, compact
        assert counters["goal_harness_case_state_reads"] == 1, compact
        assert counters["goal_harness_case_state_writes"] == 1, compact
        round_trace = compact["round_reward_trace"]
        assert round_trace["agent_declared_done"] is True, compact
        assert round_trace["declared_done_round"] == 1, compact
        assert round_trace["declared_done_score"] == 0.25, compact
        assert round_trace["final_round"] == 1, compact
        assert round_trace["final_round_reward"] == 0.25, compact
        assert round_trace["best_reward_round"] == 1, compact
        assert round_trace["best_round_reward"] == 0.25, compact
        assert compact["episode_policy"]["product_mode"] is True, compact

        update = update_benchmark_run_ledger(
            ledger_path=root / "ledger.json",
            benchmark_run=compact,
            run_group_id="product-mode-declared-done-fixture",
            dry_run=False,
        )
        run = update["entry"]
        assert run["agent_declared_done"] is True, update
        assert run["declared_done_round"] == 1, update
        assert run["declared_done_score"] == 0.25, update
        assert run["final_round"] == 1, update
        assert run["final_round_reward"] == 0.25, update
        assert run["best_reward_round"] == 1, update
        assert run["best_round_reward"] == 0.25, update


def test_skillsbench_product_mode_case_state_usage_is_compacted() -> None:
    assert PRODUCT_MODE_CASE_STATE_PATH == (
        "/app/.codex/goals/skillsbench-case/ACTIVE_GOAL_STATE.md"
    )
    with tempfile.TemporaryDirectory(prefix="skillsbench-case-state-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "skillsbench_case_state_fixture"
        rollout_name = "case__goal_harness_product_mode"
        trajectory_path = (
            jobs_dir / job_name / rollout_name / "agent" / "acp_trajectory.jsonl"
        )
        trajectory_path.parent.mkdir(parents=True)
        events = [
            {
                "type": "user_message",
                "text": (
                    "Goal Harness product-mode treatment. Maintain "
                    f"{PRODUCT_MODE_CASE_STATE_PATH}."
                ),
            },
            {
                "type": "tool_call",
                "title": f"cat {PRODUCT_MODE_CASE_STATE_PATH}",
                "status": "success",
            },
            {
                "type": "tool_call",
                "title": (
                    "python - <<'PY'\n"
                    "from pathlib import Path\n"
                    f"Path('{PRODUCT_MODE_CASE_STATE_PATH}').write_text('ok')\n"
                    "PY"
                ),
                "status": "success",
            },
        ]
        with trajectory_path.open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, sort_keys=True) + "\n")

        summary = summarize_acp_trajectory(trajectory_path)
        assert summary["goal_harness_case_state_path_count"] == 1, summary
        assert summary["goal_harness_case_state_paths"] == [
            PRODUCT_MODE_CASE_STATE_PATH
        ], summary
        assert summary["goal_harness_case_state_read_count"] == 1, summary
        assert summary["goal_harness_case_state_write_count"] == 1, summary

        trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-product-mode",
            "goal_harness_state_reads": 0,
            "goal_harness_state_writes": 0,
            "goal_harness_case_state_reads": 0,
            "goal_harness_case_state_writes": 0,
        }
        _merge_acp_trajectory_summary(
            {
                "jobs_dir": str(jobs_dir),
                "job_name": job_name,
                "rollout_name": rollout_name,
            },
            trace,
        )
        assert trace["goal_harness_case_state_reads"] == 1, trace
        assert trace["goal_harness_case_state_writes"] == 1, trace
        assert trace["goal_harness_state_reads"] == 1, trace
        assert trace["goal_harness_state_writes"] == 1, trace


def test_skillsbench_product_mode_legacy_case_state_path_is_not_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-legacy-case-state-") as tmp:
        root = Path(tmp)
        trajectory_path = root / "acp_trajectory.jsonl"
        legacy_path = "/app/.goal-harness-case-state.md"
        events = [
            {
                "type": "tool_call",
                "title": f"cat {legacy_path}",
                "status": "success",
            },
            {
                "type": "tool_call",
                "title": (
                    "python - <<'PY'\n"
                    "from pathlib import Path\n"
                    f"Path('{legacy_path}').write_text('ok')\n"
                    "PY"
                ),
                "status": "success",
            },
        ]
        with trajectory_path.open("w", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, sort_keys=True) + "\n")

        summary = summarize_acp_trajectory(trajectory_path)
        assert summary["goal_harness_case_state_path_count"] == 0, summary
        assert summary["goal_harness_case_state_paths"] == [], summary
        assert summary["goal_harness_case_state_read_count"] == 0, summary
        assert summary["goal_harness_case_state_write_count"] == 0, summary


def test_skillsbench_acp_trajectory_summary_is_compacted() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-acp-trace-summary-") as tmp:
        root = Path(tmp)
        jobs_dir = root / "jobs"
        job_name = "debug-trl-grpo-trace-summary"
        rollout_name = "debug-trl-grpo__goal_harness_blind_loop"
        run_dir = jobs_dir / job_name / rollout_name
        trajectory_path = run_dir / "agent" / "acp_trajectory.jsonl"
        trajectory_path.parent.mkdir(parents=True)
        events = [
            {
                "type": "user_message",
                "text": (
                    "Round 1. Do not modify /app/train_grpo.py or "
                    "/app/reward_fn.py. Inspect /app/trl instead."
                ),
            },
            {
                "type": "tool_call",
                "title": "goal-harness status",
                "status": "completed",
                "content": [],
            },
            {
                "type": "tool_call",
                "title": (
                    "perl -0pi -e 's/config=config,/args=config,/' "
                    "/app/train_grpo.py"
                ),
                "status": "completed",
                "content": [],
            },
            {
                "type": "tool_call",
                "title": (
                    "python -m py_compile /app/train_grpo.py "
                    "/app/reward_fn.py /app/trl/trl/trainer/grpo_trainer.py"
                ),
                "status": "completed",
                "content": [],
            },
            {"type": "agent_message", "text": "Finished local validation."},
        ]
        trajectory_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )
        (run_dir / "agent" / "codex_acp.txt").write_text("", encoding="utf-8")

        summary = summarize_acp_trajectory(trajectory_path)
        assert summary["event_count"] == 5, summary
        assert summary["round_count"] == 1, summary
        assert summary["tool_call_count"] == 3, summary
        assert summary["goal_harness_cli_call_count"] == 1, summary
        assert summary["goal_harness_cli_calls"] == [
            {
                "round": 1,
                "command": "goal-harness status",
                "subcommands": ["status"],
                "flags": [],
                "state_usage": "state_read",
                "raw_title_copied": False,
                "raw_output_copied": False,
            }
        ], summary
        assert summary["action_category_counts"] == {
            "edit": 1,
            "goal_harness_cli": 1,
            "validation": 1,
        }, summary
        assert summary["goal_harness_cli_state_usage_counts"] == {
            "state_read": 1,
        }, summary
        assert summary["goal_harness_cli_state_read_count"] == 1, summary
        assert summary["goal_harness_cli_state_write_count"] == 0, summary
        assert summary["protected_path_mentions"] == [
            "/app/reward_fn.py",
            "/app/train_grpo.py",
        ], summary
        assert summary["protected_path_edit_signal_count"] == 1, summary
        assert summary["protected_path_edit_rounds"] == {"/app/train_grpo.py": [1]}, summary

        args = parse_args(
            [
                "--task-id",
                "debug-trl-grpo",
                "--route",
                "goal-harness-blind-loop-treatment",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                job_name,
                "--rollout-name",
                rollout_name,
            ]
        )
        plan = build_plan(args)
        trace = {
            "schema_version": "skillsbench_goal_harness_controller_trace_v0",
            "route": "goal-harness-blind-loop-treatment",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "blind_loop": True,
            "official_feedback_forwarded": False,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        _merge_acp_trajectory_summary(plan, trace)
        assert trace["private_agent_trajectory_summary_recorded"] is True, trace
        assert trace["raw_agent_trajectory_recorded"] is False, trace
        assert trace["acp_trajectory_summary"]["codex_acp_text_bytes"] == 0, trace

        trace_path = jobs_dir / job_name / "goal_harness_controller_trace.public.json"
        write_json(trace_path, trace)
        result_path = write_official_skillsbench_result(root, reward=0.0)
        compact = reduce_result(args, result_path, plan)
        counters = compact["interaction_counters"]
        assert counters["private_trajectory_summary_present"] is True, compact
        assert counters["private_trajectory_event_count"] == 5, compact
        assert counters["private_trajectory_tool_call_count"] == 3, compact
        assert counters["goal_harness_cli_call_count"] == 1, compact
        assert counters["goal_harness_cli_calls"] == [
            {
                "round": 1,
                "command": "goal-harness status",
                "raw_title_copied": False,
                "raw_output_copied": False,
            }
        ], compact
        assert counters["trajectory_action_category_counts"] == {
            "edit": 1,
            "goal_harness_cli": 1,
            "validation": 1,
        }, compact
        assert counters["goal_harness_cli_state_usage_counts"] == {
            "state_read": 1,
        }, compact
        assert counters["goal_harness_cli_state_read_count"] == 1, compact
        assert counters["goal_harness_cli_state_write_count"] == 0, compact
        assert counters["protected_path_mention_count"] == 2, compact
        assert counters["protected_path_edit_signal_count"] == 1, compact
        assert "goal_harness:acp_trajectory_summary" in compact["evidence_files"], compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "Do not modify" not in compact_text, compact
        assert "Finished local validation" not in compact_text, compact
        assert str(root) not in compact_text, compact


def test_cli_dry_run_skillsbench_skeleton() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-smoke-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run",
                "skillsbench",
                "--goal-id",
                GOAL_ID,
                "--skillsbench-route",
                "automation-loop-treatment",
                "--include-task-name",
                "citation-check",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["dry_run"] is True, payload
        assert payload["benchmark_run"]["benchmark_id"] == "skillsbench@1.1", payload
        assert payload["benchmark_cli"]["benchmark"] == "skillsbench", payload
        assert payload["benchmark_cli"]["skillsbench_route"] == (
            "automation-loop-treatment"
        ), payload
        assert payload["benchmark_cli"]["real_runner_invoked"] is False, payload
        assert payload["benchmark_cli"]["real_codex_invoked"] is False, payload


def test_cli_dry_run_skillsbench_official_result() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-cli-result-smoke-") as tmp:
        root = Path(tmp)
        registry_path, runtime = write_registry(root)
        result_path = write_official_skillsbench_result(root)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "benchmark",
                "run",
                "skillsbench",
                "--goal-id",
                GOAL_ID,
                "--skillsbench-route",
                "codex-goal-mode-baseline",
                "--skillsbench-result-json",
                str(result_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["dry_run"] is True, payload
        assert payload["benchmark_run"]["source_runner"] == (
            "official_skillsbench_benchflow_result"
        ), payload
        assert payload["benchmark_run"]["official_task_score"]["value"] == 0.0
        assert payload["benchmark_cli"]["skillsbench_result_ingested"] is True, payload


def test_skillsbench_runner_plan_supports_controller_trace_path() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-trace-plan-") as tmp:
        root = Path(tmp)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "software-dependency-audit",
                "--route",
                "automation-loop-treatment",
                "--jobs-dir",
                str(root / "jobs"),
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        plan = payload["launch_plan"]
        assert plan["route"] == "automation-loop-treatment", plan
        assert plan["controller_trace_json"].endswith(
            "goal_harness_controller_trace.public.json"
        ), plan
        assert plan["include_task_skills"] is False, plan


def test_skillsbench_compact_runs_update_ledger_pair() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-ledger-smoke-") as tmp:
        root = Path(tmp)
        ledger_path = root / "benchmark-run-ledger.json"
        baseline = compact_skillsbench_run(
            task_id="citation-check",
            mode="codex_goal_mode_baseline",
            score=0.0,
            passed=False,
            exception_type="AgentRuntimeError",
        )
        treatment = compact_skillsbench_run(
            task_id="citation-check",
            mode="skillsbench_goal_harness_automation_loop_treatment",
            score=1.0,
            passed=True,
            round_reward_trace={
                "schema_version": "benchmark_round_reward_trace_v0",
                "source": "goal_harness_controller_trace",
                "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
                "records": [
                    {
                        "agent_round": 1,
                        "reward_present": True,
                        "reward": 0.0,
                        "passed": False,
                    },
                    {
                        "agent_round": 2,
                        "reward_present": True,
                        "reward": 1.0,
                        "passed": True,
                    },
                ],
                "first_success_round": 2,
                "success_observed": True,
                "max_rounds_budget": 2,
                "official_feedback_blinded": False,
                "reward_feedback_forwarded": True,
            },
        )
        baseline_update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=baseline,
            run_group_id="skillsbench-citation-check-pair",
            notes="compact baseline failure fixture; no raw task/log material",
            dry_run=False,
        )
        assert baseline_update["entry"]["arm_id"] == "codex_goal_mode_baseline"
        assert baseline_update["case_decision"]["decision"] == (
            "baseline_failed_treatment_candidate"
        )
        treatment_update = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=treatment,
            run_group_id="skillsbench-citation-check-pair",
            notes="compact automation-loop treatment fixture; no raw task/log material",
            dry_run=False,
        )
        assert treatment_update["entry"]["arm_id"] == (
            "goal_harness_automation_loop_treatment"
        )
        assert treatment_update["case_decision"]["decision"] == (
            "paired_treatment_improved"
        )
        assert treatment_update["entry"]["first_success_round"] == 2
        assert treatment_update["entry"]["round_rewards"][1]["passed"] is True
        assert treatment_update["entry"]["reward_feedback_forwarded"] is True
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"]["citation-check"]
        assert len(case["runs"]) == 2, case
        assert case["latest_decision"]["official_score_delta"] == 1.0, case
        rendered = (ledger_path.with_suffix(".md")).read_text(encoding="utf-8")
        assert "First Success Round" in rendered, rendered
        assert "`1:0,2:1*`" in rendered, rendered


def test_skillsbench_repeat_same_mode_keeps_distinct_ledger_runs() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-ledger-repeat-") as tmp:
        root = Path(tmp)
        ledger_path = root / "benchmark-run-ledger.json"
        compact = compact_skillsbench_run(
            task_id="software-dependency-audit",
            mode="skillsbench_goal_harness_automation_loop_treatment",
            score=0.0,
            passed=False,
        )
        first = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture",
            compact_artifact_ref=root / "first" / "benchmark_run.compact.json",
            notes="first compact treatment fixture",
            cwd=root,
            dry_run=False,
        )
        second = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture",
            compact_artifact_ref=root / "second" / "benchmark_run.compact.json",
            notes="second compact treatment fixture",
            cwd=root,
            dry_run=False,
        )
        assert first["entry"]["run_id"] != second["entry"]["run_id"], second
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "software-dependency-audit"
        ]
        assert len(case["runs"]) == 2, case
        third = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture-no-artifact-a",
            notes="third compact treatment fixture without artifact ref",
            dry_run=False,
        )
        fourth = update_benchmark_run_ledger(
            ledger_path=ledger_path,
            benchmark_run=compact,
            run_group_id="skillsbench-repeat-fixture-no-artifact-b",
            notes="fourth compact treatment fixture without artifact ref",
            dry_run=False,
        )
        assert third["entry"]["run_id"] != fourth["entry"]["run_id"], fourth
        ledger = load_benchmark_run_ledger(ledger_path)
        case = ledger["benchmarks"]["skillsbench@1.1"]["cases"][
            "software-dependency-audit"
        ]
        assert len(case["runs"]) == 4, case


def test_skillsbench_runner_failure_compact_closeout() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-failure-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "debug-trl-grpo",
                "--route",
                "codex-goal-mode-baseline",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-debug-trl-grpo-failure-fixture",
            ]
        )
        plan = build_plan(args)
        compact = build_runner_failure_compact(
            args,
            plan,
            FileNotFoundError("BenchFlow result.json not found"),
        )
        assert compact["schema_version"] == "benchmark_run_v0", compact
        assert compact["benchmark_id"] == "skillsbench@1.1", compact
        assert compact["source_runner"] == (
            "official_skillsbench_benchflow_launch_failure"
        ), compact
        assert compact["mode"] == "codex_goal_mode_baseline", compact
        assert compact["real_run"] is True, compact
        assert compact["official_score_status"] == "missing", compact
        assert compact["first_blocker"] == (
            "skillsbench_result_json_missing_after_runner_exit"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_result_json_missing_after_runner_exit"
        ), compact
        assert "skillsbench_result_json_missing_after_runner_exit" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"] == {
            "exception_type": "FileNotFoundError",
            "failure_class": "skillsbench_result_json_missing_after_runner_exit",
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_runner_failure_v0",
        }, compact
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_container_bootstrap": True,
                "codex_acp_runtime_dependency_preflight": True,
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_stage": (
                    "after_agent_install_before_acp_connect"
                ),
                "codex_acp_runtime_launch_preflight_status": "pending",
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            },
        )
        assert "do_not_run_benchflow_from_skeleton" not in compact[
            "stop_conditions"
        ], compact
        assert "classify_compact_runner_failure_before_rerun" in compact[
            "stop_conditions"
        ], compact
        assert (
            "do_not_read_raw_task_prompt_solution_log_or_trajectory"
            in compact["stop_conditions"]
        ), compact
        assert "BenchFlow result.json not found" not in json.dumps(compact), compact


def test_skillsbench_runner_failure_prefers_structured_preflight_blocker() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-preflight-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "debug-trl-grpo",
                "--route",
                "raw-codex-autonomous-max5",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-debug-trl-grpo-preflight-fixture",
            ]
        )
        plan = build_plan(args)
        plan["runner_prerequisites"].update(
            {
                "codex_acp_runtime_launch_preflight": False,
                "codex_acp_runtime_launch_preflight_status": "failed",
                "codex_acp_runtime_launch_preflight_rc": 127,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            }
        )
        compact = build_runner_failure_compact(
            args,
            plan,
            RuntimeError("BenchFlow runner exited before official result"),
        )
        assert compact["first_blocker"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_codex_acp_launch_preflight_failed"
        ), compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_status"
        ] == "failed", compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_raw_logs_read"
        ] is False, compact
        assert "BenchFlow runner exited before official result" not in json.dumps(
            compact
        ), compact


def test_skillsbench_runner_failure_marks_pre_agent_install_stage() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-runner-pre-agent-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "hello-world",
                "--route",
                "raw-codex-autonomous-max5",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-hello-world-pre-agent-fixture",
            ]
        )
        plan = build_plan(args)
        compact = build_runner_failure_compact(
            args,
            plan,
            RuntimeError("BenchFlow runner exited before official result"),
        )
        assert compact["first_blocker"] == (
            "skillsbench_runner_failed_before_agent_install"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_runner_failed_before_agent_install"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_failure"]["failure_class"] == (
            "skillsbench_runner_failed_before_agent_install"
        ), compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_container_bootstrap"
        ] is True, compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_dependency_preflight"
        ] is True, compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_status"
        ] == "pending", compact
        assert compact["runner_prerequisites"][
            "codex_acp_runtime_launch_preflight_stage"
        ] == "after_agent_install_before_acp_connect", compact
        assert "BenchFlow runner exited before official result" not in json.dumps(
            compact
        ), compact


def test_skillsbench_reduce_only_missing_result_records_closeout_exit_zero() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-missing-result-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "pddl-airport-planning",
                    "--route",
                    "codex-goal-mode-baseline",
                    "--allow-unverified-goal-prefix-baseline",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    "skillsbench-pddl-missing-result-fixture",
                    "--rollout-name",
                    "pddl-airport-planning__missing_result_fixture",
                    "--run-group-id",
                    "skillsbench-pddl-missing-result-fixture",
                    "--reduce-only",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        assert payload["ok"] is False, payload
        assert payload["error_recorded"] is True, payload
        assert payload["compact_closeout_recorded"] is True, payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        assert compact_path.exists(), payload
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["score_failure_attribution"] == (
            "skillsbench_result_json_missing_after_runner_exit"
        ), compact


def test_skillsbench_reduce_only_discovers_nested_official_result() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-nested-result-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-pddl-nested-result-fixture"
        nested_run_dir = (
            jobs_dir
            / job_name
            / "jobs"
            / "2026-06-15__04-24-04"
            / "pddl-airport-planning__69640c62"
        )
        write_json(
            nested_run_dir / "result.json",
            {
                "task_name": "pddl-airport-planning",
                "rollout_name": "pddl-airport-planning__69640c62",
                "rewards": {"reward": 0.0},
                "agent": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 5,
                "n_prompts": 1,
                "error": None,
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(nested_run_dir / "timing.json", {"total": 12.0})
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "pddl-airport-planning",
                    "--route",
                    "codex-goal-mode-baseline",
                    "--allow-unverified-goal-prefix-baseline",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    job_name,
                    "--rollout-name",
                    "pddl-airport-planning__requested_rollout_fixture",
                    "--run-group-id",
                    "skillsbench-pddl-nested-result-fixture",
                    "--reduce-only",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        assert payload["ok"] is True, payload
        assert payload["result_discovery"]["status"] == "found", payload
        assert payload["result_discovery"]["selection_policy"] == (
            "planned_path_then_job_root_scan_best_match"
        ), payload
        assert payload["result_discovery"]["tie_breaker"] == (
            "highest_match_score_then_newest_mtime"
        ), payload
        assert "jobs/2026-06-15__04-24-04/pddl-airport-planning__69640c62" in (
            payload["result_discovery"]["selected_relative_to_job"]
        ), payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        assert compact_path.exists(), payload
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_task_score"]["value"] == 0.0, compact
        assert compact["result_discovery"]["status"] == "found", compact


def test_skillsbench_main_failure_closeout_preserves_mutated_prerequisites() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-main-prereq-closeout-") as tmp:
        jobs_dir = Path(tmp) / "jobs"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "codex_acp_runtime_launch_preflight": True,
                    "codex_acp_runtime_launch_preflight_status": "passed",
                    "codex_acp_runtime_launch_preflight_rc": 0,
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            raise RuntimeError("BenchFlow result.json not found")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "bike-rebalance",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--job-name",
                        "skillsbench-prereq-closeout-fixture",
                        "--rollout-name",
                        "bike-rebalance__codex_acp_blind_loop",
                        "--run-group-id",
                        "skillsbench-prereq-closeout-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        assert payload["compact_closeout_recorded"] is True, payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "schema_version": "skillsbench_runner_prerequisites_v0",
                "codex_acp_runtime_container_bootstrap": True,
                "codex_acp_runtime_dependency_preflight": True,
                "codex_acp_runtime_launch_preflight": True,
                "codex_acp_runtime_launch_preflight_stage": (
                    "after_agent_install_before_acp_connect"
                ),
                "codex_acp_runtime_launch_preflight_status": "passed",
                "codex_acp_runtime_launch_preflight_rc": 0,
                "codex_acp_runtime_launch_preflight_raw_logs_read": False,
            },
        )


def test_skillsbench_main_recovers_official_result_after_runner_exception() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-result-recovery-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-result-recovery-fixture"
        exception_message = "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__codex_acp_blind_loop",
                    "rewards": {"reward": 0.0},
                    "agent": "codex-acp",
                    "agent_name": "codex-acp",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 1,
                    "error": "compact-safe official runner error",
                    "error_category": "idle_timeout",
                    "verifier_error": None,
                    "partial_trajectory": False,
                    "trajectory_source": "acp",
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError(exception_message)

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__codex_acp_blind_loop",
                        "--run-group-id",
                        "skillsbench-result-recovery-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        assert stderr.getvalue() == "", stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        assert payload["ok"] is True, payload
        assert payload["recovered_after_runner_exception"] is True, payload
        assert payload["runner_exception_type"] == "RuntimeError", payload
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["official_score_status"] == "completed", compact
        assert compact["official_task_score"]["value"] == 0.0, compact
        assert compact["runner_return_status"] == (
            "official_result_recovered_after_runner_exception"
        ), compact
        assert compact["result_recovery"] == {
            "exception_type": "RuntimeError",
            "official_result_json_materialized": True,
            "raw_exception_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "schema_version": "skillsbench_result_recovery_v0",
            "status": "official_result_recovered_after_runner_exception",
        }, compact
        assert exception_message not in json.dumps(payload), payload
        assert exception_message not in json.dumps(compact), compact


def test_skillsbench_main_recovers_missing_reward_with_structured_prereq_blocker() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-missing-reward-prereq-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-missing-reward-prereq-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "agent_execution_mode": "host_local_acp",
                    "host_local_acp_launch": True,
                    "host_local_acp_launch_status": "sandbox_install_failed",
                    "host_local_acp_install_stage": "deploy_skills",
                    "host_local_acp_install_failed_stage": "deploy_skills",
                    "container_codex_acp_install_skipped": True,
                    "codex_acp_runtime_container_bootstrap": False,
                    "codex_acp_runtime_dependency_preflight": False,
                    "codex_acp_runtime_launch_preflight": True,
                    "codex_acp_runtime_launch_preflight_status": "skipped",
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__goal_harness_blind_loop",
                    "rewards": None,
                    "agent": "codex-acp",
                    "agent_name": "",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 1,
                    "error": "compact-safe official runner error",
                    "error_category": "setup",
                    "verifier_error": None,
                    "partial_trajectory": False,
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError("PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "goal-harness-blind-loop-treatment",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__goal_harness_blind_loop",
                        "--run-group-id",
                        "skillsbench-missing-reward-prereq-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_host_local_acp_sandbox_install_failed"
        ), compact
        assert compact["first_blocker"] == (
            "skillsbench_host_local_acp_sandbox_install_failed"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert compact["runner_prerequisites"]["host_local_acp_install_stage"] == (
            "deploy_skills"
        ), compact
        assert compact["runner_prerequisites"][
            "host_local_acp_install_failed_stage"
        ] == "deploy_skills", compact
        assert "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_main_marks_empty_acp_trajectory_after_host_install() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-empty-acp-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-empty-acp-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "agent_execution_mode": "host_local_acp",
                    "host_local_acp_launch": True,
                    "host_local_acp_launch_status": "sandbox_installed",
                    "host_local_acp_install_stage": "sandbox_installed",
                    "container_codex_acp_install_skipped": True,
                    "codex_acp_runtime_container_bootstrap": False,
                    "codex_acp_runtime_dependency_preflight": False,
                    "codex_acp_runtime_launch_preflight": True,
                    "codex_acp_runtime_launch_preflight_status": "skipped",
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            write_json(
                Path(plan["controller_trace_json"]),
                {
                    "schema_version": "skillsbench_goal_harness_controller_trace_v0",
                    "route": "goal-harness-blind-loop-treatment",
                    "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                    "heartbeat_count": 1,
                    "controller_action_decisions": 1,
                    "initial_prompt_count": 1,
                    "round_rewards": [
                        {
                            "agent_round": 1,
                            "reward_present": False,
                            "passed": False,
                        }
                    ],
                    "official_success_observed": False,
                    "raw_task_text_recorded": False,
                    "raw_verifier_output_recorded": False,
                    "raw_agent_trajectory_recorded": False,
                    "acp_trajectory_summary": {
                        "schema_version": "skillsbench_acp_trajectory_summary_v0",
                        "private_trajectory_present": True,
                        "raw_text_copied_to_public": False,
                        "event_count": 0,
                        "round_count": 0,
                        "user_message_count": 0,
                        "agent_message_count": 0,
                        "tool_call_count": 0,
                        "codex_acp_text_present": False,
                        "codex_acp_text_bytes": 0,
                    },
                },
            )
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__goal_harness_blind_loop",
                    "rewards": None,
                    "agent": "codex-acp",
                    "agent_name": "",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 1,
                    "error": "compact-safe official runner error",
                    "error_category": "setup",
                    "verifier_error": None,
                    "partial_trajectory": False,
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError("PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "goal-harness-blind-loop-treatment",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__goal_harness_blind_loop",
                        "--run-group-id",
                        "skillsbench-empty-acp-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["runner_prerequisites"]["host_local_acp_launch_status"] == (
            "sandbox_installed"
        ), compact
        assert compact["interaction_counters"]["private_trajectory_event_count"] == 0
        assert compact["score_failure_attribution"] == (
            "skillsbench_host_local_acp_empty_trajectory_after_install"
        ), compact
        assert compact["first_blocker"] == (
            "skillsbench_host_local_acp_empty_trajectory_after_install"
        ), compact
        assert "skillsbench_runner_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_main_marks_agent_message_only_no_tool_calls() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-agent-message-only-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-agent-message-only-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, plan: dict[str, Any]) -> Path:
            prerequisites = plan.setdefault("runner_prerequisites", {})
            prerequisites.update(
                {
                    "agent_execution_mode": "container_local_acp",
                    "container_codex_acp_install_skipped": False,
                    "codex_acp_runtime_container_bootstrap": True,
                    "codex_acp_runtime_dependency_preflight": True,
                    "codex_acp_runtime_launch_preflight": False,
                    "codex_acp_runtime_launch_preflight_stage": (
                        "after_agent_install_before_acp_connect"
                    ),
                    "codex_acp_runtime_launch_preflight_status": "pending",
                    "codex_acp_runtime_launch_preflight_raw_logs_read": False,
                }
            )
            write_json(
                Path(plan["controller_trace_json"]),
                {
                    "schema_version": "skillsbench_goal_harness_controller_trace_v0",
                    "route": "goal-harness-blind-loop-treatment",
                    "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                    "heartbeat_count": 2,
                    "controller_action_decisions": 2,
                    "initial_prompt_count": 1,
                    "followup_prompt_count": 1,
                    "round_rewards": [
                        {
                            "agent_round": 1,
                            "reward_present": False,
                            "passed": False,
                        },
                        {
                            "agent_round": 2,
                            "reward_present": False,
                            "passed": False,
                        },
                    ],
                    "official_success_observed": False,
                    "raw_task_text_recorded": False,
                    "raw_verifier_output_recorded": False,
                    "raw_agent_trajectory_recorded": False,
                    "acp_trajectory_summary": {
                        "schema_version": "skillsbench_acp_trajectory_summary_v0",
                        "private_trajectory_present": True,
                        "raw_text_copied_to_public": False,
                        "event_count": 4,
                        "round_count": 2,
                        "user_message_count": 2,
                        "agent_message_count": 2,
                        "tool_call_count": 0,
                        "codex_acp_text_present": False,
                        "codex_acp_text_bytes": 0,
                    },
                },
            )
            result_path = Path(plan["result_json"])
            write_json(
                result_path,
                {
                    "task_name": "tictoc-unnecessary-abort-detection",
                    "rollout_name": "tictoc-unnecessary-abort-detection__goal_harness_blind_loop",
                    "rewards": None,
                    "agent": "codex-acp",
                    "agent_name": "codex-acp",
                    "model": "gpt-5.5",
                    "n_tool_calls": 0,
                    "n_prompts": 2,
                    "error": "compact-safe official runner error",
                    "error_category": "agent_behavior",
                    "verifier_error": None,
                    "partial_trajectory": False,
                    "trajectory_source": "acp",
                },
            )
            write_json(result_path.with_name("timing.json"), {"total": 2.0})
            raise RuntimeError("PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "tictoc-unnecessary-abort-detection",
                        "--route",
                        "goal-harness-blind-loop-treatment",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "tictoc-unnecessary-abort-detection__goal_harness_blind_loop",
                        "--run-group-id",
                        "skillsbench-agent-message-only-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact = json.loads(
            Path(payload["compact_benchmark_run_json"]).read_text(encoding="utf-8")
        )
        assert compact["official_score_status"] == "missing", compact
        assert compact["interaction_counters"]["private_trajectory_event_count"] == 4
        assert compact["interaction_counters"]["private_trajectory_tool_call_count"] == 0
        assert compact["score_failure_attribution"] == (
            "skillsbench_acp_agent_message_only_no_tool_calls"
        ), compact
        assert compact["first_blocker"] == (
            "skillsbench_acp_agent_message_only_no_tool_calls"
        ), compact
        assert "skillsbench_agent_behavior_gap" in compact[
            "failure_attribution_labels"
        ], compact
        assert "PRIVATE_EXCEPTION_DETAIL_SHOULD_NOT_ESCAPE" not in json.dumps(
            compact
        ), compact


def test_skillsbench_main_redirects_runner_output_to_private_log() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-private-runner-output-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-private-output-fixture"

        original_ensure = skillsbench_loop.ensure_benchflow_runtime
        original_run = skillsbench_loop.run_benchflow_case

        def fake_ensure(_args: Any) -> None:
            return None

        async def fake_run(_args: Any, _plan: dict[str, Any]) -> Path:
            print("PRIVATE_BENCHFLOW_STDOUT_MARKER")
            print("PRIVATE_BENCHFLOW_STDERR_MARKER", file=sys.stderr)
            raise RuntimeError("Docker compose command failed for environment fixture")

        skillsbench_loop.ensure_benchflow_runtime = fake_ensure
        skillsbench_loop.run_benchflow_case = fake_run
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = skillsbench_automation_loop_main(
                    [
                        "--task-id",
                        "private-output-fixture",
                        "--route",
                        "codex-acp-blind-loop-baseline",
                        "--jobs-dir",
                        str(jobs_dir),
                        "--job-name",
                        job_name,
                        "--rollout-name",
                        "private-output-fixture__codex_acp_blind_loop",
                        "--run-group-id",
                        "skillsbench-private-output-fixture",
                    ]
                )
        finally:
            skillsbench_loop.ensure_benchflow_runtime = original_ensure
            skillsbench_loop.run_benchflow_case = original_run

        assert rc == 0, stderr.getvalue()
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" not in stdout.getvalue()
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" not in stderr.getvalue()
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" not in stdout.getvalue()
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" not in stderr.getvalue()
        payload = json.loads(stderr.getvalue())
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["runner_output_capture"] == {
            "schema_version": "skillsbench_runner_output_capture_v0",
            "enabled": True,
            "stdout_stderr_redirected": True,
            "raw_output_public": False,
            "private_log_path_public": False,
        }, compact
        compact_text = json.dumps(compact, sort_keys=True)
        assert "runner-output.private.log" not in compact_text, compact
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" not in compact_text, compact
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" not in compact_text, compact
        private_log = jobs_dir / job_name / "runner-output.private.log"
        private_log_text = private_log.read_text(encoding="utf-8")
        assert "begin private BenchFlow stdout/stderr capture" in private_log_text
        assert "end private BenchFlow stdout/stderr capture" in private_log_text
        assert "PRIVATE_BENCHFLOW_STDOUT_MARKER" in private_log_text
        assert "PRIVATE_BENCHFLOW_STDERR_MARKER" in private_log_text


def test_skillsbench_reduce_only_preserves_round_reward_trace() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-round-reward-main-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_name = "skillsbench-round-trace-fixture"
        rollout_name = "sample-task__goal_harness_blind_loop"
        run_dir = jobs_dir / job_name / rollout_name
        write_json(
            run_dir / "result.json",
            {
                "task_name": "sample-task",
                "rollout_name": rollout_name,
                "rewards": {"reward": 1.0},
                "agent": "codex-acp",
                "agent_name": "codex-acp",
                "model": "gpt-5.5",
                "n_tool_calls": 9,
                "n_prompts": 2,
                "error": None,
                "verifier_error": None,
                "partial_trajectory": False,
                "trajectory_source": "acp",
            },
        )
        write_json(run_dir / "timing.json", {"total": 3.0})
        write_json(
            jobs_dir / job_name / "goal_harness_controller_trace.public.json",
            {
                "schema_version": "skillsbench_goal_harness_controller_trace_v0",
                "route": "goal-harness-blind-loop-treatment",
                "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
                "heartbeat_count": 3,
                "controller_action_decisions": 3,
                "initial_prompt_count": 1,
                "followup_prompt_count": 1,
                "stop_decision_count": 1,
                "reward_observation_count": 2,
                "verifier_feedback_observation_count": 0,
                "official_feedback_blinded_count": 2,
                "round_rewards": [
                    {
                        "agent_round": 1,
                        "reward_present": True,
                        "reward": 0.0,
                        "passed": False,
                    },
                    {
                        "agent_round": 2,
                        "reward_present": True,
                        "reward": 1.0,
                        "passed": True,
                    },
                ],
                "official_success_observed": True,
                "official_success_observation_count": 1,
                "first_success_round": 2,
                "official_feedback_forwarded": False,
                "blind_loop": True,
                "max_rounds_budget": 2,
                "last_decision": (
                    "stop_after_blind_loop_official_success_observed_without_feedback"
                ),
                "raw_task_text_recorded": False,
                "raw_verifier_output_recorded": False,
                "raw_agent_trajectory_recorded": False,
            },
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(
                [
                    "--task-id",
                    "sample-task",
                    "--route",
                    "goal-harness-blind-loop-treatment",
                    "--jobs-dir",
                    str(jobs_dir),
                    "--job-name",
                    job_name,
                    "--rollout-name",
                    rollout_name,
                    "--ledger-path",
                    str(Path(tmp) / "ledger.json"),
                    "--reduce-only",
                    "--update-ledger",
                ]
            )
        assert rc == 0, stderr.getvalue()
        payload = json.loads(stdout.getvalue())
        compact_path = Path(payload["compact_benchmark_run_json"])
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        round_trace = compact["round_reward_trace"]
        assert round_trace["first_success_round"] == 2, compact
        assert [item["reward"] for item in round_trace["records"]] == [0.0, 1.0], compact
        assert round_trace["records"][1]["passed"] is True, compact
        ledger = load_benchmark_run_ledger(Path(tmp) / "ledger.json")
        run = ledger["benchmarks"]["skillsbench@1.1"]["cases"]["sample-task"]["runs"][0]
        assert run["first_success_round"] == 2, run
        assert run["final_round"] == 2, run
        assert run["final_round_reward"] == 1.0, run
        assert run["best_reward_round"] == 2, run
        assert run["best_round_reward"] == 1.0, run
        assert run["best_round_is_final"] is True, run
        assert run["loop_score_policy"] == "best_round_for_offline_controller_analysis", run
        assert run["official_score_policy"] == "final_workspace_official_result", run
        assert run["round_rewards"][1]["passed"] is True, run


if __name__ == "__main__":
    test_skillsbench_default_blind_loop_budget_is_five()
    test_skillsbench_local_driver_a2a_contract_keeps_codex_local()
    test_skillsbench_local_driver_a2a_contract_ready_only_after_both_sides()
    test_skillsbench_local_driver_a2a_contract_distinguishes_cli_from_handshake()
    test_skillsbench_worker_handshake_preflight_exposes_acp_relay_gap()
    test_skillsbench_worker_handshake_preflight_distinguishes_host_transport()
    test_skillsbench_worker_handshake_preflight_distinguishes_remote_bridge()
    test_skillsbench_remote_command_file_bridge_probe_requires_command()
    test_skillsbench_remote_command_file_bridge_probe_fake_bridge_ready()
    test_skillsbench_worker_handshake_preflight_accepts_bridge_probe()
    test_skillsbench_local_acp_relay_probe_completes_stdio_handshake()
    test_skillsbench_host_local_acp_transport_probe_uses_benchflow_client()
    test_skillsbench_worker_handshake_preflight_probe_clears_relay_gap()
    test_skillsbench_worker_handshake_preflight_missing_runtime_is_compact()
    test_local_codex_participant_ping_missing_binary_is_compact()
    test_blind_loop_continuation_reprojects_round_one_constraints()
    test_product_mode_declared_done_marker_detection()
    test_product_mode_case_state_seed_uses_active_goal_shape()
    test_product_mode_declared_done_requires_case_state_depth()
    test_skillsbench_skeleton_builder()
    test_skillsbench_official_result_builder()
    test_skillsbench_result_reward_artifact_recovery()
    test_skillsbench_oracle_result_reward_artifact_recovery()
    test_skillsbench_app_mount_failure_attribution()
    test_skillsbench_app_skills_failure_attribution()
    test_skillsbench_docker_port_conflict_attribution()
    test_skillsbench_docker_apt_failure_attribution()
    test_skillsbench_docker_daemon_unavailable_attribution()
    test_skillsbench_unclassified_compose_failure_fingerprint()
    test_skillsbench_codex_acp_libssl_failure_attribution()
    test_skillsbench_codex_acp_glibc_failure_attribution()
    test_skillsbench_codex_acp_launch_preflight_attribution()
    test_skillsbench_codex_acp_internal_error_attribution()
    test_skillsbench_codex_acp_post_success_trace_recovers_score()
    test_skillsbench_codex_acp_post_success_finalization_route()
    test_skillsbench_docker_task_staging_adds_app_skills_mount()
    test_skillsbench_no_skill_route_removes_staged_task_skills()
    test_skillsbench_docker_task_staging_adds_apt_retry_patch()
    test_skillsbench_runtime_tools_patch_has_own_apt_retry_defaults()
    test_skillsbench_docker_task_staging_caps_local_cpu_request()
    test_skillsbench_volume_mount_failure_attribution()
    test_skillsbench_runner_plan_supports_baseline_route()
    test_skillsbench_runner_plan_supports_product_mode_routes()
    test_skillsbench_codex_acp_model_control_warning()
    test_skillsbench_runner_prerequisites_are_compacted()
    test_skillsbench_task_staging_metadata_is_compacted()
    test_skillsbench_reduce_only_recovers_prepared_task_staging_metadata()
    test_skillsbench_controller_trace_counts_are_compacted()
    test_skillsbench_product_mode_declared_done_is_compacted()
    test_skillsbench_product_mode_case_state_usage_is_compacted()
    test_skillsbench_product_mode_legacy_case_state_path_is_not_compacted()
    test_skillsbench_round_trace_records_best_round_score()
    test_skillsbench_acp_trajectory_summary_is_compacted()
    test_cli_dry_run_skillsbench_skeleton()
    test_cli_dry_run_skillsbench_official_result()
    test_skillsbench_runner_plan_supports_controller_trace_path()
    test_skillsbench_compact_runs_update_ledger_pair()
    test_skillsbench_repeat_same_mode_keeps_distinct_ledger_runs()
    test_skillsbench_runner_failure_compact_closeout()
    test_skillsbench_runner_failure_prefers_structured_preflight_blocker()
    test_skillsbench_runner_failure_marks_pre_agent_install_stage()
    test_skillsbench_reduce_only_missing_result_records_closeout_exit_zero()
    test_skillsbench_main_failure_closeout_preserves_mutated_prerequisites()
    test_skillsbench_main_recovers_official_result_after_runner_exception()
    test_skillsbench_main_recovers_missing_reward_with_structured_prereq_blocker()
    test_skillsbench_main_marks_empty_acp_trajectory_after_host_install()
    test_skillsbench_main_marks_agent_message_only_no_tool_calls()
    test_skillsbench_main_redirects_runner_output_to_private_log()
    test_skillsbench_reduce_only_discovers_nested_official_result()
    test_skillsbench_reduce_only_preserves_round_reward_trace()
    print("skillsbench-benchmark-run-smoke: ok")
