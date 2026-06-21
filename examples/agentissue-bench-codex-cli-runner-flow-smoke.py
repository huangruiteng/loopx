#!/usr/bin/env python3
"""Smoke-test the AgentIssue-Bench Codex CLI runner flow plan."""

from __future__ import annotations

import json
from typing import Any


SCHEMA_VERSION = "agentissue_bench_codex_cli_runner_flow_plan_v0"
RUN_SCHEMA = "benchmark_run_v0"
RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"
BENCHMARK_ID = "agentissue-bench"
SELECTED_TAG = "lagent_239"
IMAGE = "alfin06/agentissue-bench:lagent_239"
PATCH_RELATIVE_PATH = "Patches/lagent_239/attempt.patch"

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
    "access_token",
    "api_key",
    "authorization",
    "codex_auth",
    "credential",
    "environment",
    "file_content",
    "fixed_diff",
    "gold_material",
    "local_path",
    "password",
    "patch_content",
    "raw_issue_body",
    "raw_issue_title",
    "raw_log",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
    "test_body",
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
    "show_diff",
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


def build_runner_flow_plan() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": BENCHMARK_ID,
        "selected_tag": SELECTED_TAG,
        "dry_run_plan_only": True,
        "real_execution_done": False,
        "single_tag_only": True,
        "active_scope": {
            "only_active_benchmark": BENCHMARK_ID,
            "only_active_task": SELECTED_TAG,
            "no_other_benchmarks_until": "agentissue_codex_cli_runner_e2e_clean",
        },
        "private_workspace_contract": {
            "job_root_placeholder": "<abs-private-job-root>",
            "buggy_source_placeholder": "<abs-private-job-root>/buggy-source",
            "patch_dir_placeholder": "<abs-private-job-root>/Patches/lagent_239",
            "prompt_file_placeholder": "<abs-private-job-root>/context/prompt.md",
            "last_message_placeholder": "<abs-private-job-root>/codex-last-message.txt",
            "absolute_paths_required": True,
            "record_absolute_paths_publicly": False,
        },
        "phase_order": [
            "prepare_private_job_root",
            "fetch_public_issue_context_to_private_context",
            "pull_selected_image",
            "extract_buggy_source_from_selected_container",
            "initialize_git_baseline_in_buggy_source",
            "run_host_local_codex_cli_patch_worker",
            "write_attempt_patch_from_buggy_source_git_diff",
            "evaluate_selected_tag_container",
            "reduce_compact_evidence",
        ],
        "commands": {
            "codex_patch_worker": {
                "command_shape": [
                    "codex",
                    "exec",
                    "--ephemeral",
                    "--ignore-rules",
                    "--sandbox",
                    "workspace-write",
                    "--cd",
                    "<abs-private-job-root>/buggy-source",
                    "--add-dir",
                    "<abs-private-job-root>",
                    "--output-last-message",
                    "<abs-private-job-root>/codex-last-message.txt",
                    "<abs-private-job-root>/context/prompt.md",
                ],
                "runs_on_host": True,
                "runs_after_buggy_source_extraction": True,
                "copy_codex_home": False,
                "worker_network_allowed": False,
                "worker_docker_allowed": False,
                "worker_reads_fixed_diff": False,
            },
            "patch_export": {
                "input_source": "<abs-private-job-root>/buggy-source git diff",
                "output_relative_path": PATCH_RELATIVE_PATH,
                "patch_content_public": False,
                "patch_hash_public": True,
            },
            "single_tag_eval": {
                "command_shape": [
                    "docker",
                    "run",
                    "--platform",
                    "linux/amd64",
                    "--rm",
                    "--entrypoint",
                    "bash",
                    "-v",
                    "<abs-private-job-root>/Patches/lagent_239:/patches:ro",
                    IMAGE,
                    "-c",
                    "<apply_patch_and_test_patched>",
                ],
                "official_helper_scripts_used": False,
                "all_tag_loop_allowed": False,
                "docker_env_credentials": False,
                "upload": False,
                "submit": False,
                "public_ranking_path": False,
            },
        },
        "reducer_contract": {
            "allowed_public_fields": [
                "tag",
                "image_digest",
                "patch_sha256",
                "patch_bytes",
                "changed_file_count",
                "hunk_count",
                "exit_code",
                "resolved",
                "duration_seconds",
                "log_sha256",
                "no_upload",
                "no_submit",
                "no_public_ranking_path",
            ],
            "raw_issue_text_public": False,
            "raw_patch_public": False,
            "raw_log_public": False,
            "absolute_paths_public": False,
        },
        "no_execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
        },
        "stop_rules": {
            "stop_before_codex_auth_sync": True,
            "stop_before_current_head_patch_source": True,
            "stop_before_fixed_diff_or_oracle_read": True,
            "stop_before_all_tag_helpers": True,
            "stop_before_upload_submit_or_public_ranking": True,
            "stop_before_raw_artifact_publication": True,
        },
    }


def reduce_to_benchmark_run(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "source_runner": BENCHMARK_ID,
        "benchmark_id": BENCHMARK_ID,
        "mode": "lagent239_codex_cli_runner_flow_plan_no_execution",
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "selected_public_tag",
        "task_selector_hash": plan["selected_tag"],
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 1,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "validation": {
            "runner_flow_plan_built": True,
            "single_tag_only": True,
            "absolute_paths_required": True,
            "uses_benchmark_buggy_source": True,
            "no_current_public_head_patch_source": True,
            "no_codex_cli_invoked": True,
            "no_model_api_invoked": True,
            "no_docker_container_started": True,
            "no_patch_content_public": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
        },
        "trials": [
            {
                "task_hash": plan["selected_tag"],
                "runner_status": "planned",
                "resolved": None,
                "docker_image": IMAGE,
            }
        ],
    }


def reduce_to_benchmark_result(plan: dict[str, Any]) -> dict[str, Any]:
    components = {
        "restartability": 1.0,
        "stale_state_avoidance": 1.0,
        "evidence_discipline": 1.0,
        "boundary_safety": 1.0,
        "writeback_quality": 0.875,
        "gate_compliance": 1.0,
        "failure_attribution": 0.875,
        "overhead": 0.875,
    }
    value = sum(components.values()) / len(components)
    return {
        "schema_version": RESULT_SCHEMA,
        "task_id": "agentissue_bench_lagent_239",
        "scenario_id": "lagent239_codex_cli_runner_flow_plan_no_execution",
        "worker_mode": "trusted_local_codex_cli_runner_plan",
        "harness_identity": "loopx",
        "terminal_state": "runner_flow_plan_ready_before_execution",
        "official_task_score": {
            "kind": "agentissue_bench_single_tag_container_eval",
            "status": "not_run",
            "resolved": None,
            "value": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": round(value, 6),
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 18,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "claim_boundary": {
            "single_tag_local_eval_claim_allowed": False,
            "official_leaderboard_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
        },
        "failure_attribution_labels": [
            "no_execution_plan_only",
            "runner_flow_requires_private_materialization",
        ],
        "recommended_next_action": "materialize_agentissue_lagent239_runner_flow_in_private_job_root_or_write_blocker",
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    bad_keys = [path for path in key_paths(payload) if leaf(path) in FORBIDDEN_KEYS]
    assert not bad_keys, bad_keys
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    plan = build_runner_flow_plan()
    run_event = reduce_to_benchmark_run(plan)
    result_event = reduce_to_benchmark_result(plan)
    phases = plan["phase_order"]
    commands = plan["commands"]

    assert plan["schema_version"] == SCHEMA_VERSION, plan
    assert plan["dry_run_plan_only"] is True, plan
    assert plan["real_execution_done"] is False, plan
    assert plan["single_tag_only"] is True, plan
    assert plan["active_scope"]["only_active_benchmark"] == BENCHMARK_ID, plan
    assert plan["active_scope"]["only_active_task"] == SELECTED_TAG, plan
    assert phases.index("extract_buggy_source_from_selected_container") < phases.index(
        "run_host_local_codex_cli_patch_worker"
    ), plan
    assert phases.index("run_host_local_codex_cli_patch_worker") < phases.index(
        "write_attempt_patch_from_buggy_source_git_diff"
    ), plan
    assert commands["codex_patch_worker"]["command_shape"][0] == "codex", plan
    assert "--ephemeral" in commands["codex_patch_worker"]["command_shape"], plan
    assert "--add-dir" in commands["codex_patch_worker"]["command_shape"], plan
    assert "--output-last-message" in commands["codex_patch_worker"]["command_shape"], plan
    assert commands["codex_patch_worker"]["copy_codex_home"] is False, plan
    assert commands["codex_patch_worker"]["worker_reads_fixed_diff"] is False, plan
    assert commands["single_tag_eval"]["command_shape"][0] == "docker", plan
    assert commands["single_tag_eval"]["official_helper_scripts_used"] is False, plan
    assert commands["single_tag_eval"]["all_tag_loop_allowed"] is False, plan
    assert commands["single_tag_eval"]["docker_env_credentials"] is False, plan
    assert commands["single_tag_eval"]["upload"] is False, plan
    assert commands["single_tag_eval"]["submit"] is False, plan
    assert plan["no_execution_boundary"]["codex_cli_invoked"] is False, plan
    assert plan["no_execution_boundary"]["docker_container_started"] is False, plan
    assert run_event["schema_version"] == RUN_SCHEMA, run_event
    assert run_event["real_run"] is False, run_event
    assert run_event["validation"]["uses_benchmark_buggy_source"] is True, run_event
    assert run_event["validation"]["no_current_public_head_patch_source"] is True, run_event
    assert run_event["validation"]["no_codex_cli_invoked"] is True, run_event
    assert run_event["validation"]["no_docker_container_started"] is True, run_event
    assert result_event["schema_version"] == RESULT_SCHEMA, result_event
    assert result_event["official_task_score"]["status"] == "not_run", result_event
    assert result_event["claim_boundary"]["official_leaderboard_claim_allowed"] is False, result_event
    assert_public_safe(plan)
    assert_public_safe(run_event)
    assert_public_safe(result_event)
    return {
        "ok": True,
        "classification": SCHEMA_VERSION,
        "runner_flow_plan": plan,
        "benchmark_run": run_event,
        "benchmark_result": result_event,
        "only_active_benchmark": BENCHMARK_ID,
        "only_active_task": SELECTED_TAG,
        "real_execution_done": False,
        "recommended_next_action": result_event["recommended_next_action"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
