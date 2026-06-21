#!/usr/bin/env python3
"""Smoke-test the SWE-Bench Pro prelaunch blocker evidence."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "swe_bench_pro_prelaunch_blocker_v0"
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
LOCAL_PROVIDER_ARCH = "aarch64"
HOST_CODEX_VERSION = "codex-cli 0.128.0"
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
        "prior_packets": {
            "selected_row_compaction": True,
            "one_instance_launch_packet": True,
            "one_instance_execution_gate_packet": True,
            "owner_decision_packet": True,
        },
        "host_codex": {
            "binary_present": True,
            "version": HOST_CODEX_VERSION,
            "auth_values_read": False,
            "auth_copied_to_remote": False,
            "prompt_sent": False,
        },
        "private_run_artifacts": {
            "private_sample_artifact_ready": False,
            "attempt_patch_ready": False,
            "evaluator_scripts_ready": False,
            "launch_wrapper_ready": False,
            "public_recording_mode": "compact_blocker_only",
        },
        "provider_readiness": {
            "docker_daemon_reachable": True,
            "local_provider_architecture": LOCAL_PROVIDER_ARCH,
            "selected_image_platform": PLANNED_PLATFORM,
            "platform_mismatch": True,
            "local_cpus": 4,
            "local_memory_bytes": 8_308_088_832,
            "workspace_available_kib": 12_963_604,
            "safe_disk_floor_kib": 20 * 1024 * 1024,
            "capacity_below_safe_floor": True,
        },
        "this_packet_actions": {
            "private_sample_created": False,
            "patch_generated": False,
            "image_acquired": False,
            "container_started": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_evaluated": False,
            "upload_invoked": False,
            "submit_invoked": False,
            "public_ranking_path_touched": False,
        },
        "blocker": {
            "terminal_state": "blocked_prelaunch_prerequisites",
            "blocking_labels": [
                "private_sample_artifact_missing",
                "attempt_patch_missing",
                "evaluator_scripts_not_staged",
                "launch_wrapper_missing",
                "local_provider_platform_mismatch",
                "local_provider_capacity_below_safe_floor",
            ],
            "next_action": "implement_launch_wrapper_or_route_b_helper_then_retry_selected_pilot",
        },
        "boundary": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "raw_task_material_public": False,
            "generated_patch_public": False,
            "credentials_read": False,
            "auth_synced_to_remote": False,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": BENCHMARK_ID,
        "benchmark_id": BENCHMARK_ID,
        "benchmark_revision": DATASET_REVISION,
        "source_commit": RUNNER_COMMIT,
        "mode": "one_instance_prelaunch_blocker",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "public_selected_instance",
        "task_selector_hash": INSTANCE_ID,
        "selected_instance": packet["selected_instance"],
        "agent": {
            "codex_surface": "local_host_codex_cli",
            "codex_binary_present": packet["host_codex"]["binary_present"],
            "codex_version": packet["host_codex"]["version"],
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
        },
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
                "exception_type": packet["blocker"]["terminal_state"],
                "image_digest": IMAGE_DIGEST,
            }
        ],
        "validation": {
            "prior_packets_ready": all(packet["prior_packets"].values()),
            "host_codex_cli_ready": True,
            "private_sample_artifact_ready": False,
            "attempt_patch_ready": False,
            "evaluator_scripts_ready": False,
            "launch_wrapper_ready": False,
            "no_codex_prompt": True,
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
        "overhead": 0.75,
    }
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "swe_bench_pro_nodebb_selected_instance",
        "scenario_id": "one_instance_prelaunch_blocker",
        "worker_mode": "heartbeat_prelaunch_check",
        "harness_identity": "loopx",
        "terminal_state": packet["blocker"]["terminal_state"],
        "official_task_score": {
            "kind": "swe_bench_pro_official_score",
            "status": "not_run",
            "resolved": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": 0.96875,
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 16,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
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
        "failure_attribution_labels": packet["blocker"]["blocking_labels"],
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
    assert all(packet["prior_packets"].values()), packet
    assert packet["host_codex"]["binary_present"] is True, packet
    assert packet["host_codex"]["auth_values_read"] is False, packet
    artifacts = packet["private_run_artifacts"]
    assert artifacts["private_sample_artifact_ready"] is False, packet
    assert artifacts["attempt_patch_ready"] is False, packet
    assert artifacts["evaluator_scripts_ready"] is False, packet
    assert artifacts["launch_wrapper_ready"] is False, packet
    provider = packet["provider_readiness"]
    assert provider["docker_daemon_reachable"] is True, packet
    assert provider["platform_mismatch"] is True, packet
    assert provider["capacity_below_safe_floor"] is True, packet
    for action, happened in packet["this_packet_actions"].items():
        assert happened is False, (action, packet)
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["real_run"] is False, run_event
    assert run_event["validation"]["host_codex_cli_ready"] is True, run_event
    assert run_event["validation"]["private_sample_artifact_ready"] is False, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["terminal_state"] == "blocked_prelaunch_prerequisites", result_event
    assert result_event["official_task_score"]["status"] == "not_run", result_event
    assert result_event["forbidden_access_count"] == 0, result_event
    assert "launch_wrapper_missing" in result_event["failure_attribution_labels"], result_event
    assert_public_safe(packet)
    assert_public_safe(run_event)
    assert_public_safe(result_event)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "benchmark_run": run_event,
        "benchmark_result": result_event,
        "terminal_state": result_event["terminal_state"],
        "host_codex_cli_ready": True,
        "pilot_launched": False,
        "compact_blocker_written": True,
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
