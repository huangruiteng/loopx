#!/usr/bin/env python3
"""Smoke-test the no-run SWE-Bench Pro one-instance execution gate."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "swe_bench_pro_one_instance_execution_gate_packet_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "swe-bench-pro"
DATASET_REVISION = "7ab5114912baf22bb098818e604c02fe7ad2c11f"
RUNNER_COMMIT = "ca10a60a5fcae51e6948ffe1485d4153d421e6c5"
INSTANCE_ID = "instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan"
REPO = "NodeBB/NodeBB"
BASE_COMMIT = "1e137b07052bc3ea0da44ed201702c94055b8ad2"
IMAGE_REPOSITORY = "jefzda/sweap-images"
IMAGE_TAG = "nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5"
IMAGE_DIGEST = "sha256:e49637ebe82a479ca43b4663525955bc9cdd58c457140ee31c20958d621d3cf7"
IMAGE_SIZE_BYTES = 845_713_884
PLANNED_PLATFORM = "linux/amd64"
LOCAL_PROVIDER_ARCH = "arm64/aarch64"
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
    "gold_patch",
    "local_path",
    "password",
    "patch_content",
    "problem_statement",
    "raw_artifact",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
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
    "docker pull",
    "docker run",
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
        "source": {
            "dataset_revision": DATASET_REVISION,
            "runner_commit": RUNNER_COMMIT,
        },
        "selected_instance": {
            "repo": REPO,
            "instance_id": INSTANCE_ID,
            "base_commit": BASE_COMMIT,
            "repo_language": "js",
        },
        "prior_packets": {
            "selected_row_compaction": True,
            "one_instance_launch_packet": True,
        },
        "private_sample_reducer_phase": {
            "phase_id": "private_raw_sample_reducer",
            "execution_gate_required": True,
            "private_material_allowed_now": False,
            "private_sample_created": False,
            "public_recording_mode": "hash_count_metadata_only",
            "task_text_recorded_publicly": False,
            "gold_change_recorded_publicly": False,
            "test_change_recorded_publicly": False,
            "test_selection_recorded_publicly": False,
            "setup_command_recorded_publicly": False,
            "required_private_classes": [
                "task_prompt",
                "gold_change",
                "test_change",
                "test_selection",
                "dependency_spec",
                "setup_action",
            ],
            "allowed_public_reducer_fields_after_gate": [
                "sample_sha256",
                "sample_bytes",
                "instance_id",
                "base_commit",
                "image_tag",
            ],
        },
        "trusted_local_patch_phase": {
            "phase_id": "trusted_local_codex_patch_producer",
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
            "patch_output_kind": "private_attempt_patch",
            "patch_hash_public_only_after_generation": True,
            "patch_content_recorded_publicly": False,
        },
        "selected_image_phase": {
            "phase_id": "selected_image_acquisition_and_container_start",
            "execution_gate_required": True,
            "repository": IMAGE_REPOSITORY,
            "tag": IMAGE_TAG,
            "digest": IMAGE_DIGEST,
            "size_bytes": IMAGE_SIZE_BYTES,
            "planned_platform": PLANNED_PLATFORM,
            "local_provider_architecture": LOCAL_PROVIDER_ARCH,
            "platform_mismatch_requires_explicit_platform": True,
            "runtime_emulation_not_verified": True,
            "image_acquisition_allowed_now": False,
            "container_start_allowed_now": False,
            "host_credential_mount_allowed": False,
            "broad_cleanup_allowed": False,
            "image_acquired": False,
            "container_started": False,
        },
        "official_evaluator_phase": {
            "phase_id": "official_local_evaluator",
            "execution_gate_required": True,
            "raw_sample_input_ready": False,
            "patch_input_ready": False,
            "scripts_input_ready": False,
            "output_dir_private_only": True,
            "network_blocking_policy_required": True,
            "patch_evaluation_allowed_now": False,
            "patch_evaluated": False,
        },
        "compact_result_reducer_contract": {
            "benchmark_run_schema": RUN_SCHEMA,
            "benchmark_result_schema": RESULT_SCHEMA,
            "compact_fields": [
                "instance_id",
                "dataset_revision",
                "runner_commit",
                "image_digest",
                "patch_sha256",
                "sample_sha256",
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
            "private_output_public": False,
            "patch_content_public": False,
            "task_material_public": False,
        },
        "boundary": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "credentials_read": False,
            "local_paths_recorded": False,
            "raw_task_material_public": False,
            "generated_patch_content_public": False,
            "test_material_public": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
        },
        "stop_conditions": [
            "stop_before_private_sample_material_without_execution_scope",
            "stop_before_codex_or_model_invocation_without_execution_scope",
            "stop_before_patch_generation_without_execution_scope",
            "stop_before_selected_image_acquisition_without_execution_scope",
            "stop_before_container_start_without_execution_scope",
            "stop_before_patch_evaluation_without_execution_scope",
            "stop_before_upload_submit_or_public_ranking",
            "stop_before_credential_or_private_material_access",
        ],
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "swe-bench-pro",
        "benchmark_id": packet["benchmark_id"],
        "benchmark_revision": packet["source"]["dataset_revision"],
        "source_commit": packet["source"]["runner_commit"],
        "mode": "one_instance_execution_gate_packet_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "public_selected_instance",
        "task_selector_hash": packet["selected_instance"]["instance_id"],
        "selected_instance": {
            "repo": packet["selected_instance"]["repo"],
            "instance_id": packet["selected_instance"]["instance_id"],
            "image_digest": packet["selected_image_phase"]["digest"],
            "planned_platform": packet["selected_image_phase"]["planned_platform"],
        },
        "agent": {
            "codex_surface": packet["trusted_local_patch_phase"]["codex_surface"],
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
                "task_hash": packet["selected_instance"]["instance_id"],
                "runner_status": "blocked",
                "exception_type": "not_run_execution_gate_packet_only",
                "image_digest": packet["selected_image_phase"]["digest"],
            }
        ],
        "validation": {
            "prior_packets_ready": all(packet["prior_packets"].values()),
            "execution_gate_required": True,
            "private_material_allowed_now": False,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_patch_generation": True,
            "no_patch_evaluation": True,
            "no_image_acquisition": True,
            "no_container_start": True,
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
        "task_id": "swe_bench_pro_nodebb_selected_instance",
        "scenario_id": "one_instance_execution_gate_no_run",
        "worker_mode": "deterministic_fixture",
        "harness_identity": "loopx",
        "terminal_state": "blocked_before_execution_scope",
        "official_task_score": {
            "kind": "swe_bench_pro_official_score",
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
        "validation_pass_count": 18,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "private_sample_created": packet["private_sample_reducer_phase"]["private_sample_created"],
        "patch_generated": packet["trusted_local_patch_phase"]["patch_generated"],
        "patch_evaluated": packet["official_evaluator_phase"]["patch_evaluated"],
        "image_acquired": packet["selected_image_phase"]["image_acquired"],
        "container_started": packet["selected_image_phase"]["container_started"],
        "model_api_invoked": packet["trusted_local_patch_phase"]["model_api_invoked"],
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "real_run_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
        },
        "failure_attribution_labels": [
            "not_run_execution_gate_packet_only",
            "waiting_for_explicit_execution_scope",
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
    sample_phase = packet["private_sample_reducer_phase"]
    assert sample_phase["execution_gate_required"] is True, packet
    assert sample_phase["private_material_allowed_now"] is False, packet
    assert sample_phase["private_sample_created"] is False, packet
    assert sample_phase["task_text_recorded_publicly"] is False, packet
    patch_phase = packet["trusted_local_patch_phase"]
    assert patch_phase["codex_auth_local_only"] is True, packet
    assert patch_phase["codex_auth_copied"] is False, packet
    assert patch_phase["codex_cli_invoked"] is False, packet
    assert patch_phase["patch_generated"] is False, packet
    image_phase = packet["selected_image_phase"]
    assert image_phase["planned_platform"] == PLANNED_PLATFORM, packet
    assert image_phase["platform_mismatch_requires_explicit_platform"] is True, packet
    assert image_phase["image_acquisition_allowed_now"] is False, packet
    assert image_phase["container_start_allowed_now"] is False, packet
    assert image_phase["image_acquired"] is False, packet
    eval_phase = packet["official_evaluator_phase"]
    assert eval_phase["raw_sample_input_ready"] is False, packet
    assert eval_phase["patch_input_ready"] is False, packet
    assert eval_phase["patch_evaluation_allowed_now"] is False, packet
    assert eval_phase["patch_evaluated"] is False, packet
    assert packet["boundary"]["no_upload"] is True, packet
    assert packet["boundary"]["no_submit"] is True, packet
    assert packet["boundary"]["credentials_read"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["prior_packets_ready"] is True, run_event
    assert run_event["validation"]["no_codex_cli_invocation"] is True, run_event
    assert run_event["validation"]["no_container_start"] is True, run_event
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
        "instance_id": INSTANCE_ID,
        "image_digest": IMAGE_DIGEST,
        "planned_platform": PLANNED_PLATFORM,
        "private_sample_created": False,
        "patch_generated": False,
        "image_acquired": False,
        "container_started": False,
        "patch_evaluated": False,
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
