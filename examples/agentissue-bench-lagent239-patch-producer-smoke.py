#!/usr/bin/env python3
"""Smoke-test the no-run AgentIssue-Bench local Codex patch-producer packet."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "agentissue_bench_local_codex_patch_producer_packet_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "agentissue-bench"
SOURCE_COMMIT = "1d498dec35e347c4e7b9e1c318ef28fc5fa97318"
SELECTED_TAG = "lagent_239"
ISSUE_URL = "https://github.com/InternLM/lagent/issues/239"
ISSUE_BODY_HASH = "f4c8e9fdb337b030730c31e69ea7d62ffa1808fd9843ea17eeb4949d7533bb79"
ISSUE_COMMENTS_HASH = "6602126a5f058a9705f5e733cb4d1d5aad2c483e1a4f9cde114d97dca8fa3357"
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
    "codex_auth",
    "command_argv",
    "credential",
    "docker_output",
    "environment",
    "gold_material",
    "local_path",
    "password",
    "patch_content",
    "problem_statement",
    "raw_comment",
    "raw_diff",
    "raw_issue_body",
    "raw_issue_title",
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


def build_patch_producer_packet() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "benchmark_id": BENCHMARK_ID,
        "source_repo": "alfin06/AgentIssue-Bench",
        "source_commit": SOURCE_COMMIT,
        "selected_tag": SELECTED_TAG,
        "selected_image": "alfin06/agentissue-bench:lagent_239",
        "context": {
            "kind": "public_issue_hash_only",
            "issue_url": ISSUE_URL,
            "issue_body_hash": ISSUE_BODY_HASH,
            "issue_comments_hash": ISSUE_COMMENTS_HASH,
            "raw_issue_text_available_to_future_worker": True,
            "raw_issue_text_recorded_publicly": False,
        },
        "code_source_sync": {
            "required": True,
            "future_source_repo": "InternLM/lagent",
            "future_sync_scope": "public_repo_checkout_or_sparse_checkout",
            "sync_performed": False,
            "source_diffs_recorded": False,
            "local_paths_recorded": False,
        },
        "codex_patch_producer": {
            "surface": "local_codex_cli",
            "trusted_host_only": True,
            "auth_material_copied": False,
            "command_executed": False,
            "command_text_recorded": False,
            "model_api_invoked": False,
            "raw_prompt_recorded": False,
            "raw_completion_recorded": False,
            "expected_output_path": PATCH_OUTPUT_RELATIVE,
            "patch_generated": False,
            "patch_content_recorded": False,
            "patch_hash_recorded": False,
        },
        "docker_evaluator": {
            "future_mount_path": "Patches/lagent_239/",
            "image_pull_allowed_now": False,
            "container_start_allowed_now": False,
            "patch_evaluation_allowed_now": False,
            "docker_pulled": False,
            "docker_started": False,
            "patch_evaluated": False,
        },
        "writeback_contract": {
            "benchmark_run_schema": RUN_SCHEMA,
            "benchmark_result_schema": RESULT_SCHEMA,
            "official_score_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
            "raw_artifacts_public": False,
        },
        "stop_gates": {
            "before_codex_or_model_invocation": True,
            "before_patch_generation": True,
            "before_patch_evaluation": True,
            "before_docker_pull": True,
            "before_docker_run": True,
            "before_upload": True,
            "before_submit": True,
            "before_public_ranking": True,
            "before_credential_access": True,
            "before_raw_artifact_publication": True,
        },
    }


def reduce_to_benchmark_run(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": "agentissue-bench",
        "benchmark_id": packet["benchmark_id"],
        "source_commit": packet["source_commit"],
        "mode": "local_codex_patch_producer_packet_no_run",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": packet["selected_tag"],
        "agent": {
            "codex_surface": packet["codex_patch_producer"]["surface"],
            "trusted_host_only": True,
            "auth_material_copied": False,
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
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        },
        "trials": [
            {
                "task_hash": packet["selected_tag"],
                "runner_status": "blocked",
                "exception_type": "not_run_patch_producer_packet_only",
                "expected_patch_output_path": PATCH_OUTPUT_RELATIVE,
                "patch_generated": False,
                "patch_evaluated": False,
            }
        ],
        "validation": {
            "public_context_hash_available": True,
            "code_source_sync_required": True,
            "code_source_synced": False,
            "raw_issue_text_public": False,
            "raw_patch_or_test_material_public": False,
            "no_codex_cli_invocation": True,
            "no_model_call": True,
            "no_patch_generation": True,
            "no_patch_evaluation": True,
            "no_docker_pull": True,
            "no_docker_run": True,
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
        "overhead": 1.0,
    }
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "agentissue_bench_lagent_239",
        "scenario_id": "local_codex_patch_producer_no_run",
        "worker_mode": "deterministic_fixture",
        "harness_identity": "loopx",
        "worker_surface": packet["codex_patch_producer"]["surface"],
        "terminal_state": "blocked_before_patch_generation",
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
        "validation_pass_count": 12,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "raw_artifact_public_count": 0,
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
            "not_run_patch_producer_packet_only",
            "waiting_for_future_execution_gate",
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
    packet = build_patch_producer_packet()
    run_event = reduce_to_benchmark_run(packet)
    result_event = reduce_to_benchmark_result(packet)

    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["context"]["raw_issue_text_available_to_future_worker"] is True, packet
    assert packet["context"]["raw_issue_text_recorded_publicly"] is False, packet
    assert packet["code_source_sync"]["required"] is True, packet
    assert packet["code_source_sync"]["sync_performed"] is False, packet
    assert packet["codex_patch_producer"]["trusted_host_only"] is True, packet
    assert packet["codex_patch_producer"]["auth_material_copied"] is False, packet
    assert packet["codex_patch_producer"]["command_executed"] is False, packet
    assert packet["codex_patch_producer"]["expected_output_path"] == PATCH_OUTPUT_RELATIVE, packet
    assert packet["codex_patch_producer"]["patch_generated"] is False, packet
    assert packet["docker_evaluator"]["docker_pulled"] is False, packet
    assert packet["docker_evaluator"]["docker_started"] is False, packet
    assert packet["stop_gates"]["before_codex_or_model_invocation"] is True, packet
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["validation"]["no_codex_cli_invocation"] is True, run_event
    assert run_event["validation"]["no_patch_generation"] is True, run_event
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
        "classification": "agentissue_bench_lagent239_patch_producer_packet_v0",
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "issue_url": ISSUE_URL,
        "expected_patch_output_path": PATCH_OUTPUT_RELATIVE,
        "events": [
            packet["schema_version"],
            run_event["schema_version"],
            result_event["schema_version"],
        ],
        "code_source_sync_required": packet["code_source_sync"]["required"],
        "codex_cli_invoked": packet["codex_patch_producer"]["command_executed"],
        "auth_material_copied": packet["codex_patch_producer"]["auth_material_copied"],
        "patch_generated": packet["codex_patch_producer"]["patch_generated"],
        "docker_started": packet["docker_evaluator"]["docker_started"],
        "official_task_score_status": result_event["official_task_score"]["status"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
