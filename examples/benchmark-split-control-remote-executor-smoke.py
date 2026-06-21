#!/usr/bin/env python3
"""Smoke-test the shared split-control remote benchmark executor gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import (  # noqa: E402
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_EXECUTION_SEAM_SCHEMA_VERSION,
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_LAUNCH_PLAN_SCHEMA_VERSION,
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_RUNNER_BATCH_SCHEMA_VERSION,
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION,
    build_split_control_remote_executor_execution_seam,
    build_split_control_remote_executor_launch_plan,
    build_split_control_remote_executor_readiness,
    build_split_control_remote_executor_runner_batch,
)
from loopx.benchmark_adapters.terminal_bench import (  # noqa: E402
    TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
    TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS,
    build_terminal_bench_remote_executor_command_adapter,
    build_terminal_bench_remote_executor_launch_adapter,
    build_terminal_bench_remote_executor_materializer,
)


FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "password",
    "secret",
)


def ready_local_driver_contract(label: str = "local_codex_driver") -> dict[str, object]:
    return {
        "ready": True,
        "driver_label": label,
        "owns": [
            "codex_cli",
            "codex_auth",
            "loopx_state",
            "model_invocation",
            "planning_and_patch_generation",
        ],
        "remote_request_fields": [
            "benchmark_id",
            "case_handle",
            "execution_mode",
            "no_upload",
            "compact_artifact_ref",
        ],
        "keeps_local": [
            "codex_auth",
            "model_invocation",
            "loopx_state",
            "raw_reasoning_trace",
        ],
    }


def ready_remote_sandbox_contract(label: str = "remote_executor_sandbox") -> dict[str, object]:
    return {
        "ready": True,
        "sandbox_label": label,
        "owns": [
            "docker",
            "runner_dependencies",
            "task_data_staging",
            "bounded_command_execution",
            "compact_result_reduction",
        ],
        "allowed_actions": [
            "runner_dependency_check",
            "bounded_command_execution",
            "compact_result_reduction",
        ],
        "disallowed_actions": [
            "codex_auth_sync",
            "credential_sync",
            "remote_agent_runtime",
            "remote_codex_runtime",
            "remote_model_api_invocation",
            "raw_task_text_publication",
            "raw_log_publication",
            "upload",
            "submit",
        ],
        "returns": [
            "readiness_state",
            "job_handle",
            "compact_result_or_blocker",
            "cleanup_state",
        ],
    }


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [item for item in FORBIDDEN_TEXT if item in text]
    assert not leaked, leaked


def test_remote_codex_is_not_required_for_split_control() -> None:
    payload = build_split_control_remote_executor_readiness(
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
            "hf_available": True,
            "huggingface_cli_available": True,
            "high_capacity_storage_available": True,
            "codex_available": False,
            "codex_acp_available": False,
            "node_available": False,
            "npm_available": False,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": False,
                "task_data_ready": True,
                "known_blockers": ["harbor_or_runner_wrapper_missing"],
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": False,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "agents-last-exam@local-docker": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": False,
                "known_blockers": ["ale_image_or_task_data_missing"],
            },
        },
    )
    assert (
        payload["schema_version"]
        == BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "split_control_adapter_missing", payload
    assert payload["local_agent"]["ready"] is True, payload
    assert payload["remote_executor"]["base_ready"] is True, payload
    assert payload["remote_executor"]["remote_agent_components_blocking"] is False, payload
    assert payload["remote_executor"]["remote_agent_components_missing"] == {
        "codex_available": True,
        "codex_acp_available": True,
    }, payload
    assert payload["boundary"]["codex_auth_sync_allowed"] is False, payload
    assert payload["boundary"]["remote_codex_invocation_allowed"] is False, payload
    assert payload["boundary"]["remote_codex_acp_invocation_allowed"] is False, payload
    assert payload["boundary"]["remote_model_api_invocation_allowed"] is False, payload
    for status in payload["benchmark_statuses"]:
        assert status["remote_codex_required"] is False, status
        assert status["remote_codex_acp_required"] is False, status
        assert status["remote_codex_missing_is_blocker"] is False, status
        assert "remote_codex_missing" not in status["blockers"], status
    assert_public_safe(payload)


def test_ready_parallel_batch_size_is_capped() -> None:
    payload = build_split_control_remote_executor_readiness(
        benchmark_ids=("terminal-bench@2.0", "skillsbench@1.1"),
        max_parallel_cases=4,
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
        },
    )
    assert payload["ready"] is True, payload
    assert payload["first_blocker"] == "ready_for_parallel_remote_executor_rotation", payload
    assert payload["parallel_policy"]["suggested_next_batch_size"] == 2, payload
    assert payload["next_action"] == "launch bounded parallel remote-executor batch", payload
    assert_public_safe(payload)


def test_partial_ready_subset_can_launch_without_remote_codex() -> None:
    payload = build_split_control_remote_executor_readiness(
        max_parallel_cases=4,
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
            "codex_available": False,
            "codex_acp_available": False,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "agents-last-exam@local-docker": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": False,
                "known_blockers": ["ale_task_data_staging_venue_missing"],
            },
        },
    )
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "remote_task_data_or_image_missing", payload
    assert payload["next_action"] == "launch bounded parallel remote-executor batch", payload
    matrix = payload["readiness_matrix"]
    assert matrix["has_launchable_subset"] is True, payload
    assert matrix["ready_benchmark_ids"] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], payload
    assert matrix["blocked_benchmark_ids"] == [
        "agents-last-exam@local-docker"
    ], payload
    assert matrix["next_ready_batch_benchmark_ids"] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], payload
    assert matrix["next_repair_target"] == {
        "benchmark_id": "agents-last-exam@local-docker",
        "first_blocker": "remote_task_data_or_image_missing",
        "blockers": [
            "remote_task_data_or_image_missing",
            "ale_task_data_staging_venue_missing",
        ],
    }, payload
    assert payload["parallel_policy"]["suggested_next_batch_size"] == 2, payload
    assert payload["remote_executor"]["remote_agent_components_blocking"] is False, payload
    plan = build_split_control_remote_executor_launch_plan(payload)
    assert (
        plan["schema_version"]
        == BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_LAUNCH_PLAN_SCHEMA_VERSION
    ), plan
    assert plan["ready_to_launch"] is True, plan
    assert [case["benchmark_id"] for case in plan["launch_cases"]] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], plan
    assert all(
        case["execution_mode"] == "local_agent_remote_executor"
        and case["requires_fresh_readiness_recheck"] is True
        and case["compact_evidence_required"] is True
        and case["raw_material_allowed"] is False
        and case["upload_allowed"] is False
        and case["submit_allowed"] is False
        for case in plan["launch_cases"]
    ), plan
    assert plan["third_gate"] == {
        "benchmark_id": "agents-last-exam@local-docker",
        "required": True,
        "status": "provider_or_task_data_gate",
        "first_blocker": "remote_task_data_or_image_missing",
        "blockers": [
            "remote_task_data_or_image_missing",
            "ale_task_data_staging_venue_missing",
        ],
        "repair_action": "validate ALE provider/task-data substrate before formal launch",
    }, plan
    assert plan["boundary"]["codex_auth_stays_local"] is True, plan
    assert plan["boundary"]["remote_codex_invocation_allowed"] is False, plan
    assert plan["post_launch_evidence_contract"]["required_fields"] == [
        "benchmark_id",
        "route",
        "readiness_rechecked",
        "compact_result_or_blocker",
        "raw_material_read",
        "upload_attempted",
        "submit_attempted",
    ], plan
    batch = build_split_control_remote_executor_runner_batch(
        plan,
        fresh_readiness=payload,
    )
    assert (
        batch["schema_version"]
        == BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_RUNNER_BATCH_SCHEMA_VERSION
    ), batch
    assert batch["ready_to_execute"] is True, batch
    assert batch["ready_to_spend"] is False, batch
    assert batch["blockers"] == [], batch
    assert [case["benchmark_id"] for case in batch["runner_cases"]] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], batch
    assert all(
        case["route"] == "local_agent_remote_executor"
        and case["execution_mode"] == "compact_no_upload_dry_run"
        and case["raw_material_allowed"] is False
        and case["upload_allowed"] is False
        and case["submit_allowed"] is False
        and "shell_command" not in case
        for case in batch["runner_cases"]
    ), batch
    assert batch["next_action"] == "execute runner_cases and record compact evidence", batch
    assert_public_safe(batch)

    completed = build_split_control_remote_executor_runner_batch(
        plan,
        fresh_readiness=payload,
        case_results={
            "terminal-bench@2.0": {
                "status": "blocked",
                "readiness_rechecked": True,
                "compact_result_or_blocker": "runner wrapper missing",
                "best_score": 0.0,
            },
            "skillsbench@1.1": {
                "status": "passed",
                "readiness_rechecked": True,
                "compact_result_or_blocker": "one compact fixture passed",
                "best_score": 1.0,
            },
        },
    )
    assert completed["ready_to_execute"] is True, completed
    assert completed["ready_to_spend"] is True, completed
    assert completed["post_launch_evidence_boundary"]["violations"] == [], completed
    assert completed["next_action"] == "write compact evidence and score summary", completed
    assert_public_safe(completed)

    missing_seam = build_split_control_remote_executor_execution_seam(batch)
    assert (
        missing_seam["schema_version"]
        == BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_EXECUTION_SEAM_SCHEMA_VERSION
    ), missing_seam
    assert missing_seam["ready_to_execute"] is False, missing_seam
    assert missing_seam["blockers"] == [
        "command_adapter_missing",
        "compact_result_reducer_missing",
    ], missing_seam
    assert missing_seam["missing_command_adapter_ids"] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], missing_seam
    assert missing_seam["missing_result_reducer_ids"] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], missing_seam
    assert missing_seam["boundary"]["shell_commands_embedded"] is False, missing_seam
    assert missing_seam["boundary"]["argv_embedded"] is False, missing_seam
    assert missing_seam["next_action"] == "implement missing remote-executor command adapter(s)", missing_seam
    assert_public_safe(missing_seam)

    ready_seam = build_split_control_remote_executor_execution_seam(
        batch,
        command_adapters={
            "terminal-bench@2.0": {
                "command_adapter_ready": True,
                "result_reducer_ready": True,
                "command_adapter_status": "ready",
                "entrypoint_label": "terminal-bench remote-executor no-upload adapter",
                "result_reducer_label": "terminal-bench compact result reducer",
                "local_driver_contract": ready_local_driver_contract(
                    "terminal_bench_local_codex_driver"
                ),
                "remote_sandbox_contract": ready_remote_sandbox_contract(
                    "terminal_bench_remote_sandbox"
                ),
            },
            "skillsbench@1.1": {
                "command_adapter_ready": True,
                "result_reducer_ready": True,
                "command_adapter_status": "ready",
                "entrypoint_label": "skillsbench remote-executor no-upload adapter",
                "result_reducer_label": "skillsbench compact result reducer",
                "local_driver_contract": ready_local_driver_contract(
                    "skillsbench_local_codex_driver"
                ),
                "remote_sandbox_contract": ready_remote_sandbox_contract(
                    "skillsbench_remote_sandbox"
                ),
            },
        },
    )
    assert ready_seam["ready_to_execute"] is True, ready_seam
    assert ready_seam["blockers"] == [], ready_seam
    assert ready_seam["next_action"] == "launch execution seam cases and ingest compact evidence", ready_seam
    assert all(
        case["command_materialization"]["shell_command_embedded"] is False
        and case["result_reducer"]["raw_values_copied"] is False
        and case["local_driver_contract"]["ready"] is True
        and case["remote_sandbox_contract"]["ready"] is True
        and case["local_driver_contract"]["credential_sync_allowed"] is False
        and case["remote_sandbox_contract"]["remote_codex_runtime_allowed"] is False
        and case["ready_to_execute_remote_command"] is True
        for case in ready_seam["execution_cases"]
    ), ready_seam
    assert_public_safe(ready_seam)


def test_terminal_bench_command_adapter_facts_feed_execution_seam() -> None:
    adapter_payload = build_terminal_bench_remote_executor_command_adapter()
    assert (
        adapter_payload["schema_version"]
        == TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA
    ), adapter_payload
    assert adapter_payload["ready"] is False, adapter_payload
    assert (
        adapter_payload["first_blocker"]
        == "terminal_bench_remote_executor_materializer_missing"
    ), adapter_payload
    terminal_adapter = adapter_payload["command_adapters"]["terminal-bench@2.0"]
    assert terminal_adapter["command_adapter_ready"] is True, terminal_adapter
    assert terminal_adapter["result_reducer_ready"] is True, terminal_adapter
    assert terminal_adapter["surface_contract"]["remote_materializer_ready"] is False
    assert terminal_adapter["local_driver_contract"]["ready"] is False
    assert terminal_adapter["remote_sandbox_contract"]["ready"] is False
    assert terminal_adapter["boundary"]["shell_command_embedded"] is False
    assert terminal_adapter["boundary"]["argv_embedded"] is False
    assert terminal_adapter["boundary"]["host_path_embedded"] is False
    assert terminal_adapter["surface_contract"]["local_codex_owns_auth_model_state"] is True
    assert terminal_adapter["surface_contract"]["remote_executor_owns_docker_runner_data"] is True
    assert_public_safe(adapter_payload)

    materializer_without_driver = build_terminal_bench_remote_executor_command_adapter(
        remote_materializer_ready=True,
    )
    assert materializer_without_driver["ready"] is False, materializer_without_driver
    assert materializer_without_driver["first_blocker"] == (
        "terminal_bench_local_codex_driver_missing"
    )
    assert_public_safe(materializer_without_driver)

    incomplete_materializer = build_terminal_bench_remote_executor_materializer(
        present_handle_fields=("runner_handle",),
    )
    assert (
        incomplete_materializer["schema_version"]
        == TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA
    ), incomplete_materializer
    assert incomplete_materializer["ready"] is False, incomplete_materializer
    assert incomplete_materializer["first_blocker"] == (
        "terminal_bench_remote_executor_handle_manifest_incomplete"
    )
    assert "runner_handle" in incomplete_materializer["materializer"][
        "present_handle_fields"
    ]
    assert "jobs_dir_handle" in incomplete_materializer["materializer"][
        "missing_handle_fields"
    ]
    assert incomplete_materializer["materializer"][
        "public_handle_values_recorded"
    ] is False
    assert incomplete_materializer["boundary"][
        "codex_credentials_synced_to_remote"
    ] is False
    assert_public_safe(incomplete_materializer)

    handle_only_materializer = build_terminal_bench_remote_executor_materializer(
        present_handle_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
    )
    assert handle_only_materializer["ready"] is False, handle_only_materializer
    assert handle_only_materializer["first_blocker"] == (
        "terminal_bench_local_codex_driver_missing"
    )
    assert handle_only_materializer["materializer"][
        "local_codex_driver_ready"
    ] is False
    assert handle_only_materializer["boundary"][
        "remote_agent_runtime_allowed"
    ] is False
    assert_public_safe(handle_only_materializer)

    remote_agent_runtime_materializer = build_terminal_bench_remote_executor_materializer(
        present_handle_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
        local_codex_driver_ready=True,
        remote_agent_runtime_required=True,
    )
    assert remote_agent_runtime_materializer["ready"] is False
    assert remote_agent_runtime_materializer["first_blocker"] == (
        "terminal_bench_remote_agent_runtime_forbidden"
    )
    assert_public_safe(remote_agent_runtime_materializer)

    readiness = build_split_control_remote_executor_readiness(
        benchmark_ids=("terminal-bench@2.0", "skillsbench@1.1"),
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
        },
    )
    plan = build_split_control_remote_executor_launch_plan(readiness)
    batch = build_split_control_remote_executor_runner_batch(
        plan,
        fresh_readiness=readiness,
    )
    partial_seam = build_split_control_remote_executor_execution_seam(
        batch,
        command_adapters=adapter_payload["command_adapters"],
    )
    assert partial_seam["ready_to_execute"] is False, partial_seam
    assert partial_seam["missing_command_adapter_ids"] == ["skillsbench@1.1"], partial_seam
    assert partial_seam["missing_remote_materializer_ids"] == [
        "terminal-bench@2.0"
    ], partial_seam
    assert partial_seam["missing_result_reducer_ids"] == ["skillsbench@1.1"], partial_seam
    terminal_case = next(
        case
        for case in partial_seam["execution_cases"]
        if case["benchmark_id"] == "terminal-bench@2.0"
    )
    assert terminal_case["ready_to_execute_remote_command"] is False, partial_seam
    assert "remote_executor_materializer_missing" in terminal_case["blockers"]
    assert (
        "terminal_bench_remote_executor_materializer_missing"
        in terminal_case["blockers"]
    )
    assert (
        terminal_case["command_materialization"]["remote_materializer_ready"] is False
    )
    assert terminal_case["command_materialization"]["entrypoint_label"] == (
        "terminal_bench_no_upload_case_run_surface"
    )
    assert_public_safe(partial_seam)

    materialized_adapter_payload = build_terminal_bench_remote_executor_materializer(
        present_handle_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
        local_codex_driver_ready=True,
    )
    assert materialized_adapter_payload["ready"] is True, materialized_adapter_payload
    materialized_seam = build_split_control_remote_executor_execution_seam(
        batch,
        command_adapters=materialized_adapter_payload["command_adapters"],
    )
    materialized_terminal_case = next(
        case
        for case in materialized_seam["execution_cases"]
        if case["benchmark_id"] == "terminal-bench@2.0"
    )
    assert materialized_terminal_case["ready_to_execute_remote_command"] is True
    assert materialized_terminal_case["command_materialization"]["ready"] is True
    assert materialized_terminal_case["local_driver_contract"]["ready"] is True
    assert materialized_terminal_case["remote_sandbox_contract"]["ready"] is True
    assert materialized_terminal_case["local_driver_contract"][
        "raw_task_text_sent_to_remote"
    ] is False
    assert materialized_terminal_case["remote_sandbox_contract"][
        "remote_agent_runtime_allowed"
    ] is False
    assert materialized_seam["missing_command_adapter_ids"] == ["skillsbench@1.1"]
    assert_public_safe(materialized_seam)


def test_terminal_bench_remote_launch_adapter_reduces_private_launch_result() -> None:
    missing_request = build_terminal_bench_remote_executor_launch_adapter(
        local_codex_driver_ready=True,
        remote_sandbox_ready=True,
    )
    assert (
        missing_request["schema_version"]
        == TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA
    ), missing_request
    assert missing_request["ready"] is False, missing_request
    assert missing_request["first_blocker"] == (
        "terminal_bench_local_driver_request_incomplete"
    )
    assert missing_request["launch_adapter"]["private_request_values_recorded"] is False
    assert_public_safe(missing_request)

    sandbox_missing = build_terminal_bench_remote_executor_launch_adapter(
        present_request_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS,
        local_codex_driver_ready=True,
        remote_sandbox_ready=False,
    )
    assert sandbox_missing["ready"] is False, sandbox_missing
    assert sandbox_missing["first_blocker"] == (
        "terminal_bench_remote_sandbox_contract_missing"
    )
    assert sandbox_missing["launch_adapter"][
        "ready_to_request_remote_sandbox"
    ] is False
    assert_public_safe(sandbox_missing)

    result_missing = build_terminal_bench_remote_executor_launch_adapter(
        present_request_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS,
        local_codex_driver_ready=True,
        remote_sandbox_ready=True,
    )
    assert result_missing["ready"] is False, result_missing
    assert result_missing["first_blocker"] == (
        "terminal_bench_remote_launch_result_missing"
    )
    assert result_missing["launch_adapter"][
        "ready_to_request_remote_sandbox"
    ] is True
    assert result_missing["next_action"] == (
        "execute_private_remote_sandbox_and_feed_compact_launch_result_manifest"
    )
    assert_public_safe(result_missing)

    ready = build_terminal_bench_remote_executor_launch_adapter(
        present_request_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS,
        present_launch_result_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
        local_codex_driver_ready=True,
        remote_sandbox_ready=True,
    )
    assert ready["ready"] is True, ready
    assert ready["first_blocker"] == "ready_for_terminal_bench_execution_seam"
    assert ready["launch_adapter"]["private_launch_result_values_recorded"] is False
    assert ready["materializer"]["public_handle_values_recorded"] is False
    assert ready["command_adapter"]["command_adapter_ready"] is True
    assert ready["command_adapter"]["local_driver_contract"]["ready"] is True
    assert ready["command_adapter"]["remote_sandbox_contract"]["ready"] is True
    assert_public_safe(ready)

    forbidden = build_terminal_bench_remote_executor_launch_adapter(
        present_request_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS,
        present_launch_result_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
        local_codex_driver_ready=True,
        remote_sandbox_ready=True,
        local_codex_credential_sync=True,
    )
    assert forbidden["ready"] is False, forbidden
    assert forbidden["first_blocker"] == (
        "terminal_bench_codex_credential_sync_forbidden"
    )
    assert forbidden["boundary"]["codex_credentials_synced_to_remote"] is False
    assert_public_safe(forbidden)


def test_runner_batch_requires_fresh_readiness_recheck() -> None:
    payload = build_split_control_remote_executor_readiness(
        benchmark_ids=("terminal-bench@2.0",),
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
        },
    )
    plan = build_split_control_remote_executor_launch_plan(payload)
    missing = build_split_control_remote_executor_runner_batch(plan)
    assert missing["ready_to_execute"] is False, missing
    assert missing["runner_cases"] == [], missing
    assert missing["blockers"] == ["fresh_readiness_recheck_missing"], missing

    stale = build_split_control_remote_executor_runner_batch(
        plan,
        fresh_readiness=build_split_control_remote_executor_readiness(
            benchmark_ids=("terminal-bench@2.0",),
            local_agent={
                "codex_cli_available": True,
                "loopx_available": True,
                "codex_auth_ready": True,
                "codex_auth_local_only": True,
                "model_invocation_local": True,
            },
            remote_executor={
                "docker_available": True,
                "python_available": True,
                "git_available": True,
                "rsync_available": True,
            },
            adapter_readiness={
                "terminal-bench@2.0": {
                    "split_control_adapter_ready": True,
                    "runner_tooling_ready": False,
                    "task_data_ready": True,
                },
            },
        ),
    )
    assert stale["ready_to_execute"] is False, stale
    assert stale["blockers"] == ["fresh_readiness_recheck_changed"], stale
    assert stale["stale_launch_case_ids"] == ["terminal-bench@2.0"], stale
    assert_public_safe(missing)
    assert_public_safe(stale)


def test_runner_batch_sanitizes_post_launch_evidence() -> None:
    payload = build_split_control_remote_executor_readiness(
        benchmark_ids=("skillsbench@1.1",),
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
        },
        adapter_readiness={
            "skillsbench@1.1": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
        },
    )
    plan = build_split_control_remote_executor_launch_plan(payload)
    batch = build_split_control_remote_executor_runner_batch(
        plan,
        fresh_readiness=payload,
        case_results={
            "skillsbench@1.1": {
                "status": "passed",
                "readiness_rechecked": True,
                "compact_result_or_blocker": "public compact summary only",
                "raw_logs": "private verifier body must not be copied",
                "upload_attempted": True,
            },
            "unexpected@bench": {"status": "ignored"},
        },
    )
    assert batch["ready_to_execute"] is True, batch
    assert batch["ready_to_spend"] is False, batch
    boundary = batch["post_launch_evidence_boundary"]
    assert boundary["raw_result_key_hits"] == {
        "skillsbench@1.1": ["raw_logs"]
    }, batch
    assert boundary["unexpected_case_ids"] == ["unexpected@bench"], batch
    assert boundary["unsafe_flags"] == {"skillsbench@1.1": ["upload_attempted"]}, batch
    assert set(boundary["violations"]) == {
        "raw_result_keys_present",
        "unexpected_case_result",
        "unsafe_result_flag_true",
    }, batch
    assert "private verifier body must not be copied" not in json.dumps(batch), batch
    assert_public_safe(plan)
    assert_public_safe(batch)


def test_launch_plan_blocks_when_no_subset_is_ready() -> None:
    payload = build_split_control_remote_executor_readiness(
        benchmark_ids=("agents-last-exam@local-docker",),
        local_agent={
            "codex_cli_available": True,
            "loopx_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
        },
        adapter_readiness={
            "agents-last-exam@local-docker": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": False,
            },
        },
    )
    plan = build_split_control_remote_executor_launch_plan(payload)
    assert plan["ready_to_launch"] is False, plan
    assert plan["launch_cases"] == [], plan
    assert plan["third_gate"]["required"] is True, plan
    assert plan["next_action"] == "repair third_gate before launch", plan
    assert_public_safe(payload)
    assert_public_safe(plan)


def main() -> int:
    test_remote_codex_is_not_required_for_split_control()
    test_ready_parallel_batch_size_is_capped()
    test_partial_ready_subset_can_launch_without_remote_codex()
    test_terminal_bench_command_adapter_facts_feed_execution_seam()
    test_terminal_bench_remote_launch_adapter_reduces_private_launch_result()
    test_runner_batch_requires_fresh_readiness_recheck()
    test_runner_batch_sanitizes_post_launch_evidence()
    test_launch_plan_blocks_when_no_subset_is_ready()
    print("benchmark-split-control-remote-executor-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
