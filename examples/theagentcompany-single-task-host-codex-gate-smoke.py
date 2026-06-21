#!/usr/bin/env python3
"""Smoke-test the no-run TheAgentCompany single-task host-Codex gate."""

from __future__ import annotations

import hashlib
import json
from typing import Any


PACKET_SCHEMA = "theagentcompany_single_task_host_codex_gate_packet_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "theagentcompany"
SOURCE_REPOSITORY = "TheAgentCompany/TheAgentCompany"
SOURCE_COMMIT = "98b68ef82a47690c316f42fddb05baafaab56851"
TREE_SHA = "98b68ef82a47690c316f42fddb05baafaab56851"
TREE_PATH_COUNT = 1486
TASK_DIR_COUNT = 182
TASK_MD_COUNT = 175
CONTROL_PLANE_SCORE_COMPONENTS = (
    "restartability",
    "stale_state_avoidance",
    "evidence_discipline",
    "boundary_safety",
    "writeback_quality",
    "gate_compliance",
    "failure_attribution",
    "overhead",
)
FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "command_argv",
    "credential",
    "environment",
    "file_content",
    "gold",
    "instruction",
    "local_path",
    "password",
    "problem_statement",
    "raw_artifact",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
    "task_body",
    "task_file",
    "test_body",
    "test_list",
    "test_patch",
    "trajectory",
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "docker compose up",
    "docker pull",
    "docker run",
)


def stable_hash(label: str, value: str) -> str:
    return hashlib.sha256(f"{label}:{value}".encode("utf-8")).hexdigest()


def key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(key_paths(child, prefix=path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(key_paths(child, prefix=f"{prefix}[{index}]"))
        return paths
    return []


def leaf_segment(path: str) -> str:
    segment = path.rsplit(".", 1)[-1]
    if "[" in segment:
        segment = segment.split("[", 1)[0]
    return segment.lower()


def build_gate_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "source": {
            "repository": SOURCE_REPOSITORY,
            "default_branch": "main",
            "source_commit": SOURCE_COMMIT,
            "tree_sha": TREE_SHA,
            "tree_truncated": False,
            "tree_path_count": TREE_PATH_COUNT,
            "task_dir_count": TASK_DIR_COUNT,
            "task_md_count": TASK_MD_COUNT,
            "runner_readme_present": True,
            "runner_entry_present": True,
            "task_paths_dumped": False,
            "task_bodies_read": False,
        },
        "prior_packets": {
            "setup_readiness": True,
            "source_preflight": True,
        },
        "service_stack_phase": {
            "phase_id": "service_stack_gate",
            "runner_source_ready": True,
            "execution_gate_required": True,
            "service_setup_allowed_now": False,
            "service_stack_started": False,
            "server_images_pulled": False,
            "task_images_pulled": False,
            "host_networking_approved": False,
            "docker_socket_scope_approved": False,
            "root_or_openhands_runner_used": False,
            "shared_host_workload_inspection": False,
        },
        "single_task_selection_phase": {
            "phase_id": "single_task_selection_gate",
            "execution_gate_required": True,
            "task_selected": False,
            "task_selector_hash": stable_hash("task-selector", "single-task-not-selected"),
            "image_ref_hash": stable_hash("image-ref", "single-task-not-selected"),
            "task_material_access_allowed_now": False,
            "task_instruction_allowed_now": False,
            "task_material_read": False,
            "task_instruction_read": False,
            "future_selector_public_mode": "hash_only_after_private_selection",
            "raw_task_material_public": False,
        },
        "host_codex_worker_phase": {
            "phase_id": "host_codex_worker_gate",
            "execution_gate_required": True,
            "local_codex_cli_route_plausible": True,
            "codex_surface": "local_codex_cli",
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
            "remote_or_container_auth_copied": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "action_adapter_implemented": False,
            "task_prompt_public": False,
            "container_shell_actions_routed": False,
            "browser_actions_routed": False,
            "file_actions_routed": False,
        },
        "artifact_phase": {
            "phase_id": "artifact_and_reducer_gate",
            "execution_gate_required": True,
            "private_output_dir_created": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
            "raw_artifact_material_public": False,
            "compact_reducer_ready": True,
            "future_public_fields": [
                "source_commit",
                "task_selector_hash",
                "image_ref_hash",
                "runner_status",
                "official_score_status",
                "duration_seconds",
                "no_upload",
                "no_submit",
                "no_public_ranking_path",
            ],
        },
        "result_reducer_contract": {
            "benchmark_run_schema": RUN_SCHEMA,
            "benchmark_result_schema": RESULT_SCHEMA,
            "official_score_status": "not_run",
            "task_selector_hash": stable_hash("task-selector", "single-task-not-selected"),
            "image_ref_hash": stable_hash("image-ref", "single-task-not-selected"),
            "compact_duration_seconds": None,
            "compact_status": "blocked_before_single_task_execution_scope",
            "raw_logs_public": False,
            "private_outputs_public": False,
        },
        "boundary": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "credentials_read": False,
            "local_paths_recorded": False,
            "raw_task_material_public": False,
            "raw_trajectory_public": False,
            "screenshot_public": False,
            "docker_or_service_started": False,
            "codex_or_model_called": False,
            "production_action": False,
        },
        "stop_conditions": [
            "stop_before_service_stack_without_execution_scope",
            "stop_before_single_task_selection_without_material_scope",
            "stop_before_task_instruction_access_without_material_scope",
            "stop_before_codex_or_model_invocation_without_execution_scope",
            "stop_before_container_or_browser_action_adapter",
            "stop_before_raw_trajectory_or_screenshot_access",
            "stop_before_upload_submit_or_public_ranking",
            "stop_before_credential_or_private_material_access",
        ],
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "theagentcompany",
        "benchmark_id": packet["benchmark_id"],
        "benchmark_revision": packet["source"]["source_commit"],
        "source_commit": packet["source"]["source_commit"],
        "mode": "single_task_host_codex_gate_packet_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "single_task_not_selected",
        "task_selector_hash": packet["single_task_selection_phase"]["task_selector_hash"],
        "image_ref_hash": packet["single_task_selection_phase"]["image_ref_hash"],
        "agent": {
            "codex_surface": packet["host_codex_worker_phase"]["codex_surface"],
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 1,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "trials": [
            {
                "task_hash": packet["single_task_selection_phase"]["task_selector_hash"],
                "image_ref_hash": packet["single_task_selection_phase"]["image_ref_hash"],
                "runner_status": "blocked",
                "exception_type": "not_run_single_task_host_codex_gate_packet_only",
            }
        ],
        "validation": {
            "prior_packets_ready": all(packet["prior_packets"].values()),
            "source_metadata_ready": True,
            "task_paths_dumped": False,
            "task_material_read": False,
            "service_stack_started": False,
            "task_selected": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "credentials_read": False,
        },
    }


def reduce_to_benchmark_result(packet: dict[str, Any]) -> dict[str, Any]:
    components = {
        "restartability": 1.0,
        "stale_state_avoidance": 1.0,
        "evidence_discipline": 1.0,
        "boundary_safety": 1.0,
        "writeback_quality": 1.0,
        "gate_compliance": 1.0,
        "failure_attribution": 1.0,
        "overhead": 1.0,
    }
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "theagentcompany_single_task_not_selected",
        "scenario_id": "single_task_host_codex_gate_no_run",
        "worker_mode": "deterministic_fixture",
        "harness_identity": "loopx",
        "worker_surface": "host_codex_cli_gate_packet",
        "terminal_state": "blocked_before_single_task_execution_scope",
        "official_task_score": {
            "kind": "theagentcompany_official_score",
            "status": "not_run",
            "final_score": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": 1.0,
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 18,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "task_selected": packet["single_task_selection_phase"]["task_selected"],
        "service_stack_started": packet["service_stack_phase"]["service_stack_started"],
        "codex_cli_invoked": packet["host_codex_worker_phase"]["codex_cli_invoked"],
        "model_api_invoked": packet["host_codex_worker_phase"]["model_api_invoked"],
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "real_run_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
        },
        "failure_attribution_labels": [
            "not_run_single_task_host_codex_gate_packet_only",
            "waiting_for_explicit_execution_scope",
            "waiting_for_task_material_boundary",
            "waiting_for_service_stack_boundary",
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    key_hits = []
    for path in key_paths(payload):
        if leaf_segment(path) in FORBIDDEN_KEYS:
            key_hits.append(path)
    assert not key_hits, key_hits
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_gate_packet()
    run_event = reduce_to_benchmark_run(packet)
    result_event = reduce_to_benchmark_result(packet)

    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert all(packet["prior_packets"].values()), packet
    assert packet["source"]["source_commit"] == SOURCE_COMMIT, packet
    assert packet["source"]["tree_truncated"] is False, packet
    assert packet["source"]["task_md_count"] == TASK_MD_COUNT, packet
    assert packet["source"]["task_paths_dumped"] is False, packet
    assert packet["source"]["task_bodies_read"] is False, packet
    assert packet["service_stack_phase"]["runner_source_ready"] is True, packet
    assert packet["service_stack_phase"]["service_setup_allowed_now"] is False, packet
    assert packet["service_stack_phase"]["service_stack_started"] is False, packet
    assert packet["single_task_selection_phase"]["task_selected"] is False, packet
    assert packet["single_task_selection_phase"]["task_material_access_allowed_now"] is False, packet
    assert packet["single_task_selection_phase"]["task_material_read"] is False, packet
    assert packet["host_codex_worker_phase"]["local_codex_cli_route_plausible"] is True, packet
    assert packet["host_codex_worker_phase"]["codex_auth_local_only"] is True, packet
    assert packet["host_codex_worker_phase"]["codex_auth_copied"] is False, packet
    assert packet["host_codex_worker_phase"]["codex_cli_invoked"] is False, packet
    assert packet["host_codex_worker_phase"]["model_api_invoked"] is False, packet
    assert packet["host_codex_worker_phase"]["action_adapter_implemented"] is False, packet
    assert packet["artifact_phase"]["raw_trajectory_read"] is False, packet
    assert packet["artifact_phase"]["screenshot_read"] is False, packet
    assert packet["boundary"]["no_upload"] is True, packet
    assert packet["boundary"]["credentials_read"] is False, packet
    assert packet["boundary"]["docker_or_service_started"] is False, packet
    assert packet["boundary"]["codex_or_model_called"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["prior_packets_ready"] is True, run_event
    assert run_event["validation"]["task_material_read"] is False, run_event
    assert run_event["validation"]["service_stack_started"] is False, run_event
    assert run_event["validation"]["codex_cli_invoked"] is False, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["official_task_score"]["status"] == "not_run", result_event
    assert result_event["claim_boundary"]["official_score_claim_allowed"] is False, result_event
    assert result_event["forbidden_access_count"] == 0, result_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    assert_public_safe(result_event)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "source_commit": SOURCE_COMMIT,
        "tree_path_count": TREE_PATH_COUNT,
        "task_md_count": TASK_MD_COUNT,
        "task_selected": False,
        "service_stack_started": False,
        "codex_cli_invoked": False,
        "model_api_invoked": False,
        "events": [
            packet["schema_version"],
            run_event["schema_version"],
            result_event["schema_version"],
        ],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
