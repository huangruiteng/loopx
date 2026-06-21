#!/usr/bin/env python3
"""Smoke-test the AgentIssue-Bench lagent_239 controlled pilot result."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "agentissue_bench_lagent239_controlled_pilot_result_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "agentissue-bench"
AGENTISSUE_SOURCE_COMMIT = "1d498dec35e347c4e7b9e1c318ef28fc5fa97318"
SELECTED_TAG = "lagent_239"
TARGET_REPO = "InternLM/lagent"
TARGET_HEAD_SHA = "0ab2e2f550477884743cd63fbca7bc4aa7b00290"
PATCH_SHA256 = "e04029b70d5b1d4b461da6b8ba997388fefd614f94705b0a7abc3f847d5c07d3"
PRIVATE_LOG_SHA256 = "cdee2058eece77675a1c295edffa8fec9bcf2f1db0e8602d6536efcfd3fa5265"
IMAGE = "alfin06/agentissue-bench:lagent_239"
IMAGE_DIGEST = "sha256:792b3a4edae457c429e2797cd6ee5a181accc6cef81291dfd0ae0ab3713eab39"

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
    "codex_auth",
    "command_argv",
    "credential",
    "environment",
    "file_content",
    "gold_material",
    "local_path",
    "password",
    "patch_content",
    "problem_statement",
    "raw_artifact",
    "raw_comment",
    "raw_diff",
    "raw_issue_body",
    "raw_issue_title",
    "raw_log",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
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
        "active_benchmark_focus": {
            "only_active_benchmark": BENCHMARK_ID,
            "only_active_task": SELECTED_TAG,
            "frozen_candidates": [
                "agents-last-exam",
                "swe-bench-pro",
                "perfbench",
                "theagentcompany",
                "apex-agents",
            ],
            "no_horizontal_scan_until": "agentissue_lagent239_buggy_source_alignment_result",
        },
        "source_anchors": {
            "agentissue_repo": "alfin06/AgentIssue-Bench",
            "agentissue_commit": AGENTISSUE_SOURCE_COMMIT,
            "target_repo": TARGET_REPO,
            "target_head_sha": TARGET_HEAD_SHA,
            "target_checkout_kind": "public_current_head",
            "benchmark_buggy_source_aligned": False,
        },
        "trusted_local_codex_patch": {
            "codex_cli_invoked": True,
            "codex_ephemeral": True,
            "model_api_invoked": True,
            "codex_auth_copied": False,
            "credentials_read": False,
            "network_used_by_patch_worker": False,
            "docker_used_by_patch_worker": False,
            "patch_generated": True,
            "patch_sha256": PATCH_SHA256,
            "patch_bytes": 635,
            "files_changed": 1,
            "hunks": 1,
            "patch_content_public": False,
            "source_validation": {
                "diff_check_passed": True,
                "py_compile_passed": True,
                "compat_import_simulation_passed": True,
                "pytest_available": False,
            },
        },
        "single_tag_evaluation": {
            "image": IMAGE,
            "image_digest": IMAGE_DIGEST,
            "platform": "linux/amd64",
            "image_pull_status": "success",
            "container_started": True,
            "patch_apply_status": "success",
            "test_patched_exit_code": 1,
            "success_marker": False,
            "failure_marker": True,
            "private_log_sha256": PRIVATE_LOG_SHA256,
            "private_log_bytes": 2239,
            "raw_log_public": False,
        },
        "reducer": {
            "terminal_state": "evaluated_unresolved",
            "resolved": False,
            "failure_attribution_labels": [
                "current_head_patch_source_mismatch",
                "benchmark_buggy_source_not_checked_out",
                "dependency_constraint_expected_by_container_test",
            ],
            "next_single_benchmark_step": "align_lagent239_patch_generation_to_benchmark_buggy_source",
            "patch_amended_after_container_result": False,
            "oracle_material_used_for_patch": False,
        },
        "boundary": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
            "credentials_read": False,
            "raw_issue_text_public": False,
            "generated_patch_content_public": False,
            "raw_container_log_public": False,
            "raw_trajectory_read": False,
            "screenshot_read": False,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": BENCHMARK_ID,
        "benchmark_id": BENCHMARK_ID,
        "source_commit": packet["source_anchors"]["agentissue_commit"],
        "mode": "controlled_lagent239_local_codex_patch_and_single_tag_eval",
        "real_run": True,
        "dry_run": False,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": packet["selected_tag"],
        "active_benchmark_focus": packet["active_benchmark_focus"],
        "agent": {
            "codex_surface": "trusted_local_codex_cli",
            "codex_ephemeral": True,
            "model_api_invoked": True,
            "codex_auth_copied": False,
        },
        "target_code_source": {
            "repo": packet["source_anchors"]["target_repo"],
            "head_sha": packet["source_anchors"]["target_head_sha"],
            "checkout_kind": packet["source_anchors"]["target_checkout_kind"],
            "benchmark_buggy_source_aligned": False,
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "trials": [
            {
                "task_hash": packet["selected_tag"],
                "runner_status": "completed",
                "resolved": False,
                "patch_sha256": PATCH_SHA256,
                "docker_image": IMAGE,
                "docker_image_digest": IMAGE_DIGEST,
                "container_exit_code": packet["single_tag_evaluation"]["test_patched_exit_code"],
            }
        ],
        "validation": {
            "source_checkout_performed": True,
            "codex_cli_invoked": True,
            "model_api_invoked": True,
            "patch_generated": True,
            "no_patch_content_public": True,
            "docker_image_pulled": True,
            "docker_container_started": True,
            "patch_evaluated": True,
            "patch_apply_success": True,
            "test_patched_exit_code": 1,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "no_credentials_read": True,
            "paths_redacted": True,
        },
    }


def reduce_to_benchmark_result(packet: dict[str, Any]) -> dict[str, Any]:
    components = {
        "restartability": 1.0,
        "stale_state_avoidance": 0.75,
        "evidence_discipline": 0.875,
        "boundary_safety": 0.875,
        "writeback_quality": 1.0,
        "gate_compliance": 0.875,
        "failure_attribution": 1.0,
        "overhead": 0.75,
    }
    value = sum(components.values()) / len(components)
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "agentissue_bench_lagent_239",
        "scenario_id": "controlled_lagent239_local_codex_patch_and_single_tag_eval",
        "worker_mode": "trusted_local_codex_cli",
        "harness_identity": "loopx",
        "terminal_state": packet["reducer"]["terminal_state"],
        "official_task_score": {
            "kind": "agentissue_bench_single_tag_container_eval",
            "status": "evaluated",
            "resolved": False,
            "value": 0.0,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": round(value, 6),
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 16,
        "validation_fail_count": 1,
        "forbidden_access_count": 0,
        "patch_generated": True,
        "patch_evaluated": True,
        "docker_started": True,
        "model_api_invoked": True,
        "active_benchmark_focus": packet["active_benchmark_focus"],
        "claim_boundary": {
            "single_tag_local_eval_claim_allowed": True,
            "official_leaderboard_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
        },
        "failure_attribution_labels": packet["reducer"]["failure_attribution_labels"],
        "recommended_next_action": packet["reducer"]["next_single_benchmark_step"],
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
    assert packet["active_benchmark_focus"]["only_active_benchmark"] == BENCHMARK_ID, packet
    assert packet["active_benchmark_focus"]["only_active_task"] == SELECTED_TAG, packet
    assert packet["trusted_local_codex_patch"]["codex_cli_invoked"] is True, packet
    assert packet["trusted_local_codex_patch"]["model_api_invoked"] is True, packet
    assert packet["trusted_local_codex_patch"]["codex_auth_copied"] is False, packet
    assert packet["trusted_local_codex_patch"]["patch_generated"] is True, packet
    assert packet["single_tag_evaluation"]["image_pull_status"] == "success", packet
    assert packet["single_tag_evaluation"]["container_started"] is True, packet
    assert packet["single_tag_evaluation"]["patch_apply_status"] == "success", packet
    assert packet["single_tag_evaluation"]["test_patched_exit_code"] == 1, packet
    assert packet["reducer"]["resolved"] is False, packet
    assert "current_head_patch_source_mismatch" in packet["reducer"]["failure_attribution_labels"], packet
    assert packet["reducer"]["patch_amended_after_container_result"] is False, packet
    assert packet["reducer"]["oracle_material_used_for_patch"] is False, packet
    assert packet["boundary"]["no_upload"] is True, packet
    assert packet["boundary"]["no_submit"] is True, packet
    assert packet["boundary"]["codex_auth_copied"] is False, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["real_run"] is True, run_event
    assert run_event["progress"]["n_completed_trials"] == 1, run_event
    assert run_event["validation"]["patch_evaluated"] is True, run_event
    assert run_event["validation"]["no_credentials_read"] is True, run_event
    assert run_event["validation"]["no_patch_content_public"] is True, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["official_task_score"]["status"] == "evaluated", result_event
    assert result_event["official_task_score"]["resolved"] is False, result_event
    assert result_event["claim_boundary"]["official_leaderboard_claim_allowed"] is False, result_event
    assert result_event["recommended_next_action"] == "align_lagent239_patch_generation_to_benchmark_buggy_source"
    assert_public_safe(packet)
    assert_public_safe(run_event)
    assert_public_safe(result_event)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "benchmark_run": run_event,
        "benchmark_result": result_event,
        "resolved": False,
        "only_active_benchmark": BENCHMARK_ID,
        "only_active_task": SELECTED_TAG,
        "recommended_next_action": result_event["recommended_next_action"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
