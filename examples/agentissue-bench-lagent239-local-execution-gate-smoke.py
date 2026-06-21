#!/usr/bin/env python3
"""Smoke-test the no-run AgentIssue-Bench lagent_239 local execution gate."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "agentissue_bench_local_execution_gate_packet_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "agentissue-bench"
AGENTISSUE_SOURCE_COMMIT = "1d498dec35e347c4e7b9e1c318ef28fc5fa97318"
SELECTED_TAG = "lagent_239"
TARGET_REPO = "InternLM/lagent"
TARGET_HEAD_SHA = "0ab2e2f550477884743cd63fbca7bc4aa7b00290"
TARGET_TREE_SHA = "e1fbfc26536a3bdb688c98a9a97732db84a0a2db"
PATCH_OUTPUT_RELATIVE = "Patches/lagent_239/attempt.patch"
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
    "local_path",
    "password",
    "patch_content",
    "problem_statement",
    "raw_artifact",
    "raw_comment",
    "raw_diff",
    "raw_issue_body",
    "raw_issue_title",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "source_diff",
    "test_body",
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
)


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


def build_execution_gate_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "agentissue_source": {
            "repo": "alfin06/AgentIssue-Bench",
            "commit": AGENTISSUE_SOURCE_COMMIT,
        },
        "prior_packets": {
            "manifest_context_gate": True,
            "public_context_packet": True,
            "patch_producer_packet": True,
            "code_source_sync_plan": True,
        },
        "target_code_source": {
            "repo": TARGET_REPO,
            "head_sha": TARGET_HEAD_SHA,
            "tree_sha": TARGET_TREE_SHA,
            "checkout_location_recorded": False,
            "checkout_performed": False,
            "file_contents_read": False,
            "cleanup_required_after_future_run": True,
        },
        "trusted_local_patch_phase": {
            "phase_id": "trusted_local_codex_patch_generation",
            "execution_gate_required": True,
            "allowed_host_kind": "trusted_local_host_only",
            "codex_surface": "local_codex_cli",
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "prompt_text_recorded_publicly": False,
            "completion_text_recorded_publicly": False,
            "patch_generated": False,
            "patch_output_path": PATCH_OUTPUT_RELATIVE,
            "patch_hash_public_only_after_generation": True,
            "patch_content_recorded_publicly": False,
        },
        "single_tag_evaluation_phase": {
            "phase_id": "single_tag_docker_evaluation",
            "execution_gate_required": True,
            "image": "alfin06/agentissue-bench:lagent_239",
            "image_manifest_ready": True,
            "image_pull_allowed_now": False,
            "container_start_allowed_now": False,
            "patch_evaluation_allowed_now": False,
            "mount_scope": "Patches/lagent_239/",
            "all_tag_loop_allowed": False,
            "global_docker_cleanup_allowed": False,
            "host_credential_mount_allowed": False,
            "docker_pulled": False,
            "docker_started": False,
            "patch_evaluated": False,
        },
        "result_reducer_contract": {
            "benchmark_run_schema": RUN_SCHEMA,
            "benchmark_result_schema": RESULT_SCHEMA,
            "compact_fields": [
                "selected_tag",
                "target_head_sha",
                "patch_hash",
                "docker_image",
                "evaluation_status",
                "resolved",
                "duration_seconds",
                "no_upload",
                "no_submit",
                "no_public_ranking_path",
            ],
            "official_score_claim_allowed_before_evaluation": False,
            "official_score_claim_allowed_after_protocol_match": True,
            "raw_logs_public": False,
            "patch_content_public": False,
        },
        "boundary": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "credentials_read": False,
            "local_paths_recorded": False,
            "raw_issue_text_public": False,
            "source_diff_public": False,
            "generated_patch_content_public": False,
            "test_material_public": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
        },
        "stop_conditions": [
            "stop_before_codex_or_model_invocation_without_execution_gate",
            "stop_before_patch_generation_without_execution_gate",
            "stop_before_docker_pull_without_execution_gate",
            "stop_before_docker_run_without_execution_gate",
            "stop_before_patch_evaluation_without_execution_gate",
            "stop_before_upload_submit_or_public_ranking",
            "stop_before_credential_or_private_material_access",
        ],
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "agentissue-bench",
        "benchmark_id": packet["benchmark_id"],
        "source_commit": packet["agentissue_source"]["commit"],
        "mode": "local_execution_gate_packet_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": packet["selected_tag"],
        "agent": {
            "codex_surface": packet["trusted_local_patch_phase"]["codex_surface"],
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
        },
        "target_code_source": {
            "repo": TARGET_REPO,
            "head_sha": TARGET_HEAD_SHA,
            "tree_sha": TARGET_TREE_SHA,
            "checkout_performed": False,
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
                "task_hash": packet["selected_tag"],
                "runner_status": "blocked",
                "exception_type": "not_run_local_execution_gate_packet_only",
                "expected_patch_output_path": PATCH_OUTPUT_RELATIVE,
                "docker_image": packet["single_tag_evaluation_phase"]["image"],
            }
        ],
        "validation": {
            "prior_packets_ready": all(packet["prior_packets"].values()),
            "execution_gate_required": True,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_patch_generation": True,
            "no_patch_evaluation": True,
            "no_docker_pull": True,
            "no_docker_run": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "credentials_read": False,
            "paths_redacted": True,
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
        "task_id": "agentissue_bench_lagent_239",
        "scenario_id": "local_execution_gate_no_run",
        "worker_mode": "deterministic_fixture",
        "harness_identity": "loopx",
        "terminal_state": "blocked_before_execution_gate",
        "official_task_score": {
            "kind": "agentissue_bench_official_score",
            "status": "not_run",
            "resolved": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": 1.0,
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 14,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "patch_generated": False,
        "patch_evaluated": False,
        "docker_started": False,
        "model_api_invoked": False,
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "real_run_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
        },
        "failure_attribution_labels": [
            "not_run_local_execution_gate_packet_only",
            "waiting_for_explicit_execution_gate",
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    key_hits = []
    for path in key_paths(payload):
        leaf = path.rsplit(".", 1)[-1].strip("[]").lower()
        if leaf in FORBIDDEN_KEYS:
            key_hits.append(path)
    assert not key_hits, key_hits
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_execution_gate_packet()
    run_event = reduce_to_benchmark_run(packet)
    result_event = reduce_to_benchmark_result(packet)

    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert all(packet["prior_packets"].values()), packet
    assert packet["target_code_source"]["checkout_performed"] is False, packet
    assert packet["target_code_source"]["file_contents_read"] is False, packet
    patch_phase = packet["trusted_local_patch_phase"]
    assert patch_phase["execution_gate_required"] is True, packet
    assert patch_phase["codex_auth_local_only"] is True, packet
    assert patch_phase["codex_auth_copied"] is False, packet
    assert patch_phase["codex_cli_invoked"] is False, packet
    assert patch_phase["patch_generated"] is False, packet
    eval_phase = packet["single_tag_evaluation_phase"]
    assert eval_phase["image_manifest_ready"] is True, packet
    assert eval_phase["image_pull_allowed_now"] is False, packet
    assert eval_phase["container_start_allowed_now"] is False, packet
    assert eval_phase["patch_evaluated"] is False, packet
    assert packet["result_reducer_contract"]["raw_logs_public"] is False, packet
    assert packet["boundary"]["no_upload"] is True, packet
    assert packet["boundary"]["no_submit"] is True, packet
    assert packet["boundary"]["no_public_ranking_path"] is True, packet
    assert packet["boundary"]["credentials_read"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["prior_packets_ready"] is True, run_event
    assert run_event["validation"]["no_codex_cli_invocation"] is True, run_event
    assert run_event["validation"]["no_docker_run"] is True, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["official_task_score"]["status"] == "not_run", result_event
    assert result_event["claim_boundary"]["official_score_claim_allowed"] is False, result_event
    assert result_event["forbidden_access_count"] == 0, result_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    assert_public_safe(result_event)
    return {
        "ok": True,
        "classification": "agentissue_bench_lagent239_local_execution_gate_packet_v0",
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "events": [
            packet["schema_version"],
            run_event["schema_version"],
            result_event["schema_version"],
        ],
        "execution_gate_required": patch_phase["execution_gate_required"],
        "codex_cli_invoked": patch_phase["codex_cli_invoked"],
        "codex_auth_copied": patch_phase["codex_auth_copied"],
        "patch_generated": patch_phase["patch_generated"],
        "docker_started": eval_phase["docker_started"],
        "patch_evaluated": eval_phase["patch_evaluated"],
        "official_task_score_status": result_event["official_task_score"]["status"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
