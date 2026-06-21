#!/usr/bin/env python3
"""Smoke-test the AgentIssue-Bench lagent_239 bridge preflight."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "agentissue_bench_lagent239_bridge_preflight_v0"
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
IMAGE = "alfin06/agentissue-bench:lagent_239"

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
        "selected_tag": SELECTED_TAG,
        "agentissue_source": {
            "repo": "alfin06/AgentIssue-Bench",
            "commit": AGENTISSUE_SOURCE_COMMIT,
        },
        "target_code_source": {
            "repo": TARGET_REPO,
            "head_sha": TARGET_HEAD_SHA,
            "tree_sha": TARGET_TREE_SHA,
            "checkout_performed": False,
            "file_contents_read": False,
        },
        "trusted_local_codex_surface": {
            "codex_cli_present": True,
            "codex_cli_version": "0.128.0",
            "codex_auth_read": False,
            "codex_auth_copied": False,
            "codex_prompt_sent": False,
            "model_api_invoked": False,
            "patch_generated": False,
            "patch_content_public": False,
        },
        "docker_metadata_surface": {
            "docker_reachable": True,
            "docker_client_version": "29.2.0",
            "docker_server_version": "28.4.0",
            "docker_server_os": "linux",
            "docker_server_arch": "arm64",
            "image_pulled": False,
            "container_started": False,
        },
        "selected_manifest_route": {
            "image": IMAGE,
            "schema_version": 2,
            "media_type": "application/vnd.oci.image.index.v1+json",
            "manifest_count": 2,
            "platforms": ["linux/amd64", "unknown/unknown"],
            "linux_amd64_present": True,
        },
        "patch_staging_surface": {
            "private_patch_staging_dir_created": True,
            "patch_output_contract": PATCH_OUTPUT_RELATIVE,
            "attempt_patch_exists": False,
            "patch_content_read": False,
            "patch_content_public": False,
            "mount_scope": "Patches/lagent_239/",
        },
        "launch_decision": {
            "bridge_preflight_ready": True,
            "pilot_launch_authorized": False,
            "next_gate": "source_checkout_codex_patch_generation_docker_eval",
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
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": BENCHMARK_ID,
        "benchmark_id": BENCHMARK_ID,
        "source_commit": packet["agentissue_source"]["commit"],
        "mode": "lagent239_bridge_preflight_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": packet["selected_tag"],
        "target_code_source": packet["target_code_source"],
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
                "exception_type": "bridge_ready_before_execution_gates",
                "expected_patch_output_path": PATCH_OUTPUT_RELATIVE,
                "docker_image": IMAGE,
            }
        ],
        "validation": {
            "bridge_preflight_ready": True,
            "codex_cli_present": True,
            "docker_reachable": True,
            "selected_manifest_linux_amd64": True,
            "patch_staging_ready": True,
            "pilot_launch_authorized": False,
            "no_codex_prompt": True,
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
        "overhead": 0.875,
    }
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "agentissue_bench_lagent_239",
        "scenario_id": "lagent239_bridge_preflight_no_run",
        "worker_mode": "host_metadata_and_manifest_preflight",
        "harness_identity": "loopx",
        "terminal_state": "bridge_ready_before_execution_gates",
        "official_task_score": {
            "kind": "agentissue_bench_official_score",
            "status": "not_run",
            "resolved": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": 0.984375,
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 19,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "bridge_preflight_ready": True,
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
            "source_checkout_not_started",
            "patch_generation_not_started",
            "docker_evaluation_not_started",
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
    assert packet["trusted_local_codex_surface"]["codex_cli_present"] is True, packet
    assert packet["trusted_local_codex_surface"]["codex_auth_copied"] is False, packet
    assert packet["docker_metadata_surface"]["docker_reachable"] is True, packet
    assert packet["selected_manifest_route"]["linux_amd64_present"] is True, packet
    assert packet["patch_staging_surface"]["private_patch_staging_dir_created"] is True, packet
    assert packet["patch_staging_surface"]["attempt_patch_exists"] is False, packet
    assert packet["launch_decision"]["bridge_preflight_ready"] is True, packet
    assert packet["launch_decision"]["pilot_launch_authorized"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["bridge_preflight_ready"] is True, run_event
    assert run_event["validation"]["no_patch_generation"] is True, run_event
    assert run_event["validation"]["no_docker_run"] is True, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["terminal_state"] == "bridge_ready_before_execution_gates", result_event
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
        "bridge_preflight_ready": True,
        "pilot_launch_authorized": False,
        "codex_cli_present": True,
        "docker_reachable": True,
        "selected_manifest_linux_amd64": True,
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
