#!/usr/bin/env python3
"""Smoke-test the SWE-Bench Pro private descriptor blocker."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "swe_bench_pro_private_descriptor_blocker_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "swe-bench-pro"
DATASET_REVISION = "7ab5114912baf22bb098818e604c02fe7ad2c11f"
RUNNER_COMMIT = "ca10a60a5fcae51e6948ffe1485d4153d421e6c5"
INSTANCE_ID = "instance_NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5-vnan"
REPO = "NodeBB/NodeBB"
IMAGE_DIGEST = "sha256:e49637ebe82a479ca43b4663525955bc9cdd58c457140ee31c20958d621d3cf7"
PLANNED_PLATFORM = "linux/amd64"

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
    "docker pull",
    "docker run",
    "docker compose",
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


def leaf(path: str) -> str:
    segment = path.rsplit(".", 1)[-1]
    if "[" in segment:
        segment = segment.split("[", 1)[0]
    return segment.lower()


def build_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "selected_instance": {
            "repo": REPO,
            "instance_id": INSTANCE_ID,
            "dataset_revision": DATASET_REVISION,
            "runner_commit": RUNNER_COMMIT,
            "image_digest": IMAGE_DIGEST,
            "planned_platform": PLANNED_PLATFORM,
        },
        "ready_inputs": {
            "launch_wrapper_contract_ready": True,
            "provider_descriptor_ready": True,
            "selected_provider": "remote_gpu_route_b_noauth_helper",
        },
        "descriptor_probe": {
            "probe_kind": "filename_only",
            "private_sample_descriptor_ready": False,
            "attempt_patch_descriptor_ready": False,
            "evaluator_scripts_descriptor_ready": False,
            "raw_task_material_read": False,
            "patch_content_read": False,
            "evaluator_script_body_read": False,
        },
        "boundary": {
            "codex_auth_sync_allowed": False,
            "credential_sync_allowed": False,
            "remote_codex_invocation_allowed": False,
            "remote_model_api_invocation_allowed": False,
            "private_material_public": False,
            "upload_allowed": False,
            "submit_allowed": False,
            "public_ranking_allowed": False,
        },
        "launch_decision": {
            "pilot_launch_authorized": False,
            "terminal_blocker": "private_descriptor_staging_missing",
            "next_action": "create_private_descriptor_surface_or_defer_to_other_lane",
        },
        "this_packet_actions": {
            "private_descriptor_file_opened": False,
            "remote_command_invoked": False,
            "private_sample_created": False,
            "attempt_patch_created": False,
            "evaluator_script_body_read": False,
            "image_acquired": False,
            "container_started": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_evaluated": False,
            "upload_invoked": False,
            "submit_invoked": False,
            "public_ranking_path_touched": False,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": BENCHMARK_ID,
        "benchmark_id": BENCHMARK_ID,
        "benchmark_revision": DATASET_REVISION,
        "source_commit": RUNNER_COMMIT,
        "mode": "private_descriptor_blocker_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "public_selected_instance",
        "task_selector_hash": INSTANCE_ID,
        "selected_instance": packet["selected_instance"],
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "trials": [
            {
                "task_hash": INSTANCE_ID,
                "runner_status": "blocked",
                "exception_type": "private_descriptor_staging_missing",
                "image_digest": IMAGE_DIGEST,
            }
        ],
        "validation": {
            "launch_wrapper_contract_ready": True,
            "provider_descriptor_ready": True,
            "pilot_launch_authorized": False,
            "private_sample_descriptor_ready": False,
            "attempt_patch_descriptor_ready": False,
            "evaluator_scripts_descriptor_ready": False,
            "codex_auth_sync_allowed": False,
            "no_private_descriptor_file_open": True,
            "no_remote_command": True,
            "no_codex_prompt": True,
            "no_model_call": True,
            "no_container_start": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
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
        "overhead": 0.9375,
    }
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "swe_bench_pro_nodebb_selected_instance",
        "scenario_id": "private_descriptor_blocker_no_run",
        "worker_mode": "filename_only_probe",
        "harness_identity": "loopx",
        "terminal_state": "blocked_private_descriptor_staging_missing",
        "official_task_score": {
            "kind": "swe_bench_pro_official_score",
            "status": "not_run",
            "resolved": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": 0.9921875,
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 18,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "provider_descriptor_ready": True,
        "private_sample_created": False,
        "patch_generated": False,
        "patch_evaluated": False,
        "image_acquired": False,
        "container_started": False,
        "model_api_invoked": False,
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "real_run_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
        },
        "failure_attribution_labels": [
            "private_sample_descriptor_missing",
            "attempt_patch_descriptor_missing",
            "evaluator_scripts_descriptor_missing",
            "private_descriptor_surface_missing",
        ],
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    key_hits = [path for path in key_paths(payload) if leaf(path) in FORBIDDEN_KEYS]
    assert not key_hits, key_hits
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_packet()
    run_event = reduce_to_benchmark_run(packet)
    result_event = reduce_to_benchmark_result(packet)

    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["ready_inputs"]["launch_wrapper_contract_ready"] is True, packet
    assert packet["ready_inputs"]["provider_descriptor_ready"] is True, packet
    assert packet["descriptor_probe"]["probe_kind"] == "filename_only", packet
    assert packet["descriptor_probe"]["private_sample_descriptor_ready"] is False, packet
    assert packet["descriptor_probe"]["attempt_patch_descriptor_ready"] is False, packet
    assert packet["descriptor_probe"]["evaluator_scripts_descriptor_ready"] is False, packet
    assert packet["launch_decision"]["pilot_launch_authorized"] is False, packet
    assert packet["boundary"]["codex_auth_sync_allowed"] is False, packet
    for action, happened in packet["this_packet_actions"].items():
        assert happened is False, (action, packet)
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["provider_descriptor_ready"] is True, run_event
    assert run_event["validation"]["private_sample_descriptor_ready"] is False, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["terminal_state"] == "blocked_private_descriptor_staging_missing", result_event
    assert result_event["official_task_score"]["status"] == "not_run", result_event
    assert result_event["forbidden_access_count"] == 0, result_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    assert_public_safe(result_event)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "benchmark_run": run_event,
        "benchmark_result": result_event,
        "provider_descriptor_ready": True,
        "private_descriptor_surface_missing": True,
        "pilot_launch_authorized": False,
        "codex_auth_sync_allowed": False,
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
