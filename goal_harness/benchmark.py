from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .worker_bridge import (
    ACTIVE_USER_INTERVENTION_CHANNEL_CONTRACT_VERSION,
    ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
    ACTIVE_USER_INTERVENTION_OBSERVATION_VERSION,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON as TERMINAL_BENCH_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON as TERMINAL_BENCH_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    GOAL_HARNESS_ACTIVE_USER_HOST_DIR_PLACEHOLDER as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_HOST_DIR_PLACEHOLDER,
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER as TERMINAL_BENCH_WORKER_BRIDGE_PROJECT_ROOT_PLACEHOLDER,
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER as TERMINAL_BENCH_WORKER_BRIDGE_RUNTIME_ROOT_PLACEHOLDER,
    WORKER_BRIDGE_BENCHMARK_RUN_FORBIDDEN_PUBLIC_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_FIXED_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_TOP_LEVEL_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION,
    WORKER_BRIDGE_SURFACE,
    build_active_user_codex_simulator_contract,
    build_active_user_intervention,
    build_worker_bridge_install_contract,
)


TERMINAL_BENCH_MODES = (
    "hardened-codex",
    "passive-observed-codex",
    "codex-goal-harness",
    "goal-harness-managed-codex",
)

TERMINAL_BENCH_DEFAULT_DATASET = "terminal-bench@2.0"
TERMINAL_BENCH_DEFAULT_TASK = "build-cython-ext"
TERMINAL_BENCH_DEFAULT_MODEL = "gpt-5.5"
BENCHMARK_CLAIM_REVIEW_SCHEMA_VERSION = "benchmark_claim_review_v0"
BENCHMARK_VERIFIER_ATTRIBUTION_REVIEW_SCHEMA_VERSION = (
    "benchmark_verifier_attribution_review_v0"
)
TERMINAL_BENCH_HARBOR_REF = (
    "git+https://github.com/harbor-framework/harbor@"
    "a56546feb7d2da0b3196bbd7b05adacb72449391"
)
TERMINAL_BENCH_PREFLIGHT_MODE = "goal_harness_managed_codex_real_run_preflight_guard"
TERMINAL_BENCH_CODEX_GOAL_HARNESS_PREFLIGHT_MODE = (
    "codex_goal_harness_no_upload_preflight_guard"
)
TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_MODE = (
    "codex_goal_harness_active_user_assisted_treatment_preflight"
)
TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_SCHEMA = (
    "terminal_bench_active_user_assisted_treatment_preflight_v0"
)
TERMINAL_BENCH_ACTIVE_USER_ASSISTED_OBSERVATION_FIXTURE_MODE = (
    "codex_goal_harness_active_user_assisted_observation_fixture"
)
TERMINAL_BENCH_ACTIVE_USER_ASSISTED_OBSERVATION_FIXTURE_SCHEMA = (
    "terminal_bench_active_user_assisted_observation_fixture_v0"
)
TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_CHANNEL_SCHEMA = (
    "terminal_bench_active_user_simulator_injection_channel_v0"
)
TERMINAL_BENCH_ACTIVE_USER_PRIVATE_LAUNCHER_PLAN_SCHEMA = (
    "terminal_bench_active_user_private_launcher_plan_v0"
)
TERMINAL_BENCH_TASK_MATERIAL_READINESS_SCHEMA = (
    "terminal_bench_task_material_readiness_v0"
)
TERMINAL_BENCH_POST_LAUNCH_MATERIALIZATION_SCHEMA = (
    "terminal_bench_post_launch_materialization_v0"
)
TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_SETTING = "codex_cli_user_simulator"
TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_FIRST_BLOCKER = (
    "missing_simulator_to_worker_injection_channel"
)
TERMINAL_BENCH_ACTIVE_USER_REAL_WORKER_OBSERVATION_FIRST_BLOCKER = (
    "missing_real_assisted_worker_observation"
)
TERMINAL_BENCH_ACTIVE_USER_OBSERVATION_FIXTURE_FIRST_BLOCKER = (
    "real_assisted_worker_observation_fixture_only_no_real_case"
)
TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE = (
    "hardened_codex_baseline_preflight_guard"
)
TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE = "hardened_codex_baseline"
TERMINAL_BENCH_HARDENED_CODEX_LEGACY_CALIBRATION_MODE = (
    "hardened_codex_calibration"
)
TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES = (
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE,
    TERMINAL_BENCH_HARDENED_CODEX_LEGACY_CALIBRATION_MODE,
)
TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE = (
    "hardened_codex_baseline_no_goal_harness_state"
)
# Backward-compatible aliases for older compact run files and running jobs.
TERMINAL_BENCH_HARDENED_CODEX_CALIBRATION_MODE = (
    TERMINAL_BENCH_HARDENED_CODEX_LEGACY_CALIBRATION_MODE
)
TERMINAL_BENCH_HARDENED_CODEX_CALIBRATION_SURFACE = (
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE
)
TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH = (
    "goal_harness.terminal_bench_agent:GoalHarnessManagedCodex"
)
TERMINAL_BENCH_MANAGED_POLICY_VERSION = "goal_harness_terminal_bench_policy_v0"
TERMINAL_BENCH_MANAGED_BEHAVIOR_SPEC_ID = (
    "terminal_bench_goal_harness_managed_codex_v0"
)
TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION = (
    "terminal_bench_goal_harness_access_packet_v0"
)
TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL = "full"
TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_COMPACT = "compact"
TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE = "none"
TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES = (
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_COMPACT,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE,
)
TERMINAL_BENCH_GOAL_HARNESS_INTERACTION_COUNTERS_VERSION = (
    "terminal_bench_goal_harness_interaction_counters_v0"
)
TERMINAL_BENCH_OVERHEAD_ATTRIBUTION_COUNTERS_VERSION = (
    "terminal_bench_overhead_attribution_counters_v0"
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION = (
    "terminal_bench_goal_harness_cli_bridge_contract_v0"
)
TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS = (
    "status",
    "quota_should_run",
    "todo_list",
    "history",
    "check",
    "append_benchmark_run",
)
TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND = "active_user_observe"
TERMINAL_BENCH_GOAL_HARNESS_COUNTER_TRACE_COMMANDS = (
    *TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS,
    TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND,
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_VERSION = (
    "terminal_bench_goal_harness_cli_bridge_call_policy_v1"
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_MODE = (
    "lean_preflight_check_and_final_append"
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS = (
    "check",
    "append_benchmark_run",
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS = (
    "status",
    "quota_should_run",
    "todo_list",
    "history",
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM = 1
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_PLACEHOLDER_POLICY_VERSION = (
    "terminal_bench_goal_harness_cli_bridge_placeholder_policy_v0"
)
TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE = (
    "prompt_packet_only_no_cli_bridge"
)
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE = False
TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_SURFACE = (
    "host_agent_goal_harness_cli_bridge_v0"
)
TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE = (
    "codex_worker_goal_harness_cli_bridge_v0"
)
AGENTS_LAST_EXAM_BENCHMARK_ID = "agents-last-exam"
AGENTS_LAST_EXAM_RESULT_INGEST_POLICY_VERSION = "ale-result-ingest-contract-v0"
AGENTS_LAST_EXAM_TRACE_PUBLICNESS = (
    "compact_public_safe_no_task_body_no_trajectory_no_output"
)
AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED = (
    "trajectory.json",
    "origin_log",
    "output",
)
AGENTISSUE_BENCHMARK_ID = "agentissue-bench"
AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_dry_run_wrapper_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_BENCHMARK_RUN_MODE = (
    "agentissue_codex_cli_runner_dry_run_wrapper"
)
AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_synthetic_staging_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_MODE = (
    "agentissue_codex_cli_runner_synthetic_staging_fixture"
)
AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_execution_gate_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_MODE = (
    "agentissue_codex_cli_runner_execution_gate"
)
AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_first_run_handoff_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_MODE = (
    "agentissue_codex_cli_runner_first_run_handoff_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_workflow_check_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_MODE = (
    "agentissue_codex_cli_runner_workflow_check_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION = (
    "agentissue_bench_codex_cli_runner_run_gate_v0"
)
AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_MODE = (
    "agentissue_codex_cli_runner_run_gate_packet"
)
AGENTISSUE_CODEX_CLI_RUNNER_SOURCE_RUNNER = (
    "goal_harness_agentissue_codex_cli_runner"
)
AGENTISSUE_DEFAULT_TAG = "lagent_239"
AGENTISSUE_DEFAULT_IMAGE = "alfin06/agentissue-bench:lagent_239"
AGENTISSUE_PATCH_RELATIVE_PATH = "Patches/lagent_239/attempt.patch"
BENCHMARK_PUBLIC_ARTIFACT_SUFFIXES = (
    ".compact.json",
    ".public.json",
)
BENCHMARK_PUBLIC_ARTIFACT_FILENAMES = (
    "paired_comparison.compact.json",
    "launch_status.public.json",
    "launch_summaries.public.json",
    "goal-harness-active-user-observation.json",
)
BENCHMARK_RAW_PRIVATE_PATH_MARKERS = (
    "/agent/trajectory.json",
    "/sessions/",
    "/logs/",
    "/raw/",
    "trajectory.json",
    "origin_log",
    "instruction.md",
    "task.md",
)
BENCHMARK_PRIVATE_MANIFEST_SUFFIXES = (
    ".local.json",
    ".private.json",
)


def classify_benchmark_artifact_path(path: str | Path) -> dict[str, Any]:
    """Classify a benchmark artifact path without echoing host directories."""

    normalized = str(path).replace("\\", "/").rstrip("/")
    basename = normalized.rsplit("/", 1)[-1] if normalized else ""
    lower_path = normalized.lower()
    lower_basename = basename.lower()
    public_compact_candidate = (
        lower_basename.endswith(BENCHMARK_PUBLIC_ARTIFACT_SUFFIXES)
        or lower_basename in BENCHMARK_PUBLIC_ARTIFACT_FILENAMES
    )
    raw_marker = next(
        (marker for marker in BENCHMARK_RAW_PRIVATE_PATH_MARKERS if marker in lower_path),
        "",
    )
    private_manifest = lower_basename.endswith(BENCHMARK_PRIVATE_MANIFEST_SUFFIXES)

    allowed_to_read = (
        public_compact_candidate
        and not raw_marker
        and not private_manifest
    )
    if allowed_to_read:
        first_blocker = ""
        recommended_action = "read only this compact/public artifact, then ingest its reduced fields"
    elif raw_marker:
        first_blocker = "raw_private_surface"
        recommended_action = "do not read; use a compact/public sibling artifact or runner-side reducer"
    elif private_manifest:
        first_blocker = "private_or_local_manifest"
        recommended_action = "do not read; summarize via a public compact launch summary instead"
    else:
        first_blocker = "not_compact_public_artifact"
        recommended_action = "skip unless a benchmark-specific reducer explicitly whitelists it"

    return {
        "schema_version": "benchmark_artifact_path_classification_v0",
        "path_recorded": False,
        "basename": basename,
        "public_compact_candidate": public_compact_candidate,
        "private_raw_surface": bool(raw_marker or private_manifest),
        "first_blocker": first_blocker,
        "allowed_to_read": allowed_to_read,
        "recommended_action": recommended_action,
    }


def filter_public_benchmark_artifact_paths(
    paths: Iterable[str | Path],
) -> dict[str, Any]:
    classifications = [classify_benchmark_artifact_path(path) for path in paths]
    allowed = [item for item in classifications if item["allowed_to_read"]]
    blocked = [item for item in classifications if not item["allowed_to_read"]]
    blocked_reasons: dict[str, int] = {}
    for item in blocked:
        reason = str(item.get("first_blocker") or "unknown")
        blocked_reasons[reason] = blocked_reasons.get(reason, 0) + 1
    return {
        "schema_version": "benchmark_artifact_path_filter_v0",
        "path_recorded": False,
        "allowed_to_read_count": len(allowed),
        "blocked_count": len(blocked),
        "allowed_artifact_basenames": [item["basename"] for item in allowed],
        "blocked_artifact_basenames": [item["basename"] for item in blocked],
        "blocked_reasons": blocked_reasons,
        "classifications": classifications,
        "public_boundary": {
            "full_paths_recorded": False,
            "raw_task_text_read": False,
            "trajectory_or_origin_log_read": False,
            "intended_use": "preflight benchmark artifact reads before compact ingest",
        },
    }



def _agentissue_public_label(value: Any, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("agentissue label is required")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", text):
        raise ValueError("agentissue label must be public-safe")
    return text[:limit]


def build_agentissue_codex_cli_runner_wrapper(
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
    job_root_placeholder: str = "<abs-private-job-root>",
) -> dict[str, Any]:
    """Build a dry-run-default AgentIssue-Bench Codex CLI runner wrapper.

    The wrapper deliberately renders command and staging shapes only. It never
    calls Codex, Docker, model APIs, or benchmark helpers; callers that append
    the embedded benchmark_run_v0 are recording readiness, not a task score.
    """

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner wrapper currently only supports selected tag lagent_239"
        )
    codex = _agentissue_public_label(codex_binary, limit=80)
    docker = _agentissue_public_label(docker_binary, limit=80)
    image = AGENTISSUE_DEFAULT_IMAGE
    buggy_source = f"{job_root_placeholder}/buggy-source"
    context_dir = f"{job_root_placeholder}/context"
    patch_dir = f"{job_root_placeholder}/Patches/lagent_239"
    prompt_path = f"{context_dir}/prompt.md"
    last_message = f"{job_root_placeholder}/codex-last-message.txt"
    compact_run_path = f"{job_root_placeholder}/benchmark_run.compact.json"

    phase_order = [
        "prepare_private_job_root",
        "write_public_issue_context_to_private_context",
        "pull_selected_image_opt_in",
        "extract_buggy_source_from_selected_container_opt_in",
        "initialize_git_baseline_in_buggy_source",
        "run_host_local_codex_cli_patch_worker_opt_in",
        "write_attempt_patch_from_buggy_source_git_diff",
        "evaluate_selected_tag_container_opt_in",
        "reduce_compact_public_evidence",
    ]
    codex_argv = [
        codex,
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--sandbox",
        "workspace-write",
        "--cd",
        buggy_source,
        "--add-dir",
        job_root_placeholder,
        "--output-last-message",
        last_message,
        prompt_path,
    ]
    eval_argv = [
        docker,
        "run",
        "--platform",
        "linux/amd64",
        "--rm",
        "--entrypoint",
        "bash",
        "-v",
        f"{patch_dir}:/patches:ro",
        image,
        "-c",
        "<apply_patch_and_test_patched>",
    ]
    wrapper = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": image,
        "dry_run_default": True,
        "real_execution_done": False,
        "single_tag_only": True,
        "staging_plan": {
            "private_job_root_placeholder": job_root_placeholder,
            "path_recorded": False,
            "buggy_source_placeholder": buggy_source,
            "context_dir_placeholder": context_dir,
            "patch_dir_placeholder": patch_dir,
            "prompt_path_placeholder": prompt_path,
            "last_message_placeholder": last_message,
            "compact_run_placeholder": compact_run_path,
            "phase_order": phase_order,
        },
        "commands": {
            "codex_patch_worker": {
                "argv": codex_argv,
                "runs_on_host": True,
                "runs_after_buggy_source_extraction": True,
                "copy_codex_home": False,
                "auth_material_synced": False,
                "worker_network_allowed": False,
                "worker_docker_allowed": False,
                "reads_fixed_diff_or_oracle": False,
                "execute_by_default": False,
            },
            "patch_export": {
                "input_source": "buggy_source_git_diff",
                "output_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
                "raw_patch_public": False,
                "patch_hash_public": True,
            },
            "single_tag_eval": {
                "argv": eval_argv,
                "official_all_tag_helper_allowed": False,
                "docker_env_credentials": False,
                "upload": False,
                "submit": False,
                "public_ranking_path": False,
                "execute_by_default": False,
            },
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "raw_issue_text_read": False,
            "raw_patch_recorded": False,
            "raw_log_recorded": False,
            "credential_values_recorded": False,
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
        "stop_rules": {
            "stop_before_codex_auth_sync": True,
            "stop_before_current_head_patch_source": True,
            "stop_before_fixed_diff_or_oracle_read": True,
            "stop_before_all_tag_helpers": True,
            "stop_before_upload_submit_or_public_ranking": True,
            "stop_before_raw_artifact_publication": True,
            "stop_before_destructive_git_or_production": True,
        },
    }
    benchmark_run = {
        "schema_version": "benchmark_run_v0",
        "source_runner": AGENTISSUE_CODEX_CLI_RUNNER_SOURCE_RUNNER,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "job_name": "agentissue_lagent_239_codex_cli_runner_dry_run",
        "mode": AGENTISSUE_CODEX_CLI_RUNNER_BENCHMARK_RUN_MODE,
        "worker_mode": "trusted_host_codex_cli_dry_run_wrapper",
        "trace_publicness": "compact_public_no_issue_text_no_patch_no_logs",
        "first_blocker": "dry_run_wrapper_only_no_real_case",
        "score_failure_attribution": "not_run_wrapper_readiness_only",
        "real_run": False,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_score_comparable_to_native_codex": False,
        "official_score_claim_allowed": False,
        "control_plane_score_applicable": True,
        "official_task_score": {
            "kind": "agentissue_bench_single_tag_container_eval_not_run",
            "status": "not_run",
            "value": None,
            "resolved": None,
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
            "cost_usd": 0,
        },
        "validation": {
            "runner_wrapper_built": True,
            "dry_run_default": True,
            "single_tag_only": True,
            "absolute_private_job_root_placeholders": True,
            "buggy_source_before_codex_patch": True,
            "patch_from_buggy_source_git_diff": True,
            "selected_tag_eval_only": True,
            "compact_reducer_declared": True,
            "no_codex_cli_invoked": True,
            "no_model_api_invoked": True,
            "no_docker_container_started": True,
            "no_patch_generated": True,
            "no_patch_evaluated": True,
            "no_auth_material_sync": True,
            "no_current_public_head_patch_source": True,
            "no_fixed_diff_or_oracle_read": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
        },
        "trials": [
            {
                "task_id": tag,
                "trial_name": tag,
                "source": "selected_public_tag",
                "exception_type": "dry_run_wrapper_only_no_real_case",
                "trajectory_present": False,
                "artifact_manifest_present": False,
                "trial_result_present": False,
            }
        ],
        "failure_attribution_labels": [
            "no_execution_wrapper_only",
            "ready_for_synthetic_job_root_staging",
        ],
        "evidence_files": [
            "benchmark_run.compact.json",
            "runner-flow-plan.public.json",
        ],
        "stop_conditions": [
            "codex_auth_sync_requested",
            "current_head_patch_source_requested",
            "fixed_diff_or_oracle_requested",
            "all_tag_helper_requested",
            "upload_submit_or_public_ranking_requested",
            "raw_artifact_publication_requested",
        ],
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }
    return {
        **wrapper,
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "run this wrapper against a synthetic private job root, then gate any real "
            "Codex/Docker execution behind explicit opt-in"
        ),
    }


def materialize_agentissue_codex_cli_runner_synthetic_staging(
    staging_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a synthetic AgentIssue runner job root without real task material."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner synthetic staging currently only supports selected tag lagent_239"
        )
    root = Path(staging_root).expanduser()
    if not str(root):
        raise ValueError("synthetic staging root is required")

    wrapper = build_agentissue_codex_cli_runner_wrapper(
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    context_dir = root / "context"
    buggy_source_dir = root / "buggy-source"
    patch_dir = root / "Patches" / tag
    prompt_path = context_dir / "prompt.md"
    runner_plan_path = root / "runner-flow-plan.public.json"
    compact_run_path = root / "benchmark_run.compact.json"

    prompt_text = (
        "# Synthetic AgentIssue-Bench lagent_239 Prompt Placeholder\n\n"
        "This fixture contains no real issue statement, source diff, test patch, "
        "expected patch, auth value, trajectory, screenshot, or raw log.\n\n"
        f"Expected patch output path: {AGENTISSUE_PATCH_RELATIVE_PATH}\n\n"
        "Run boundary: do not invoke Codex, Docker, model APIs, upload, submit, "
        "or public ranking paths from this fixture.\n"
    )
    benchmark_run = json.loads(json.dumps(wrapper["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_synthetic_staging",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_MODE,
            "worker_mode": "trusted_host_codex_cli_synthetic_staging_fixture",
            "first_blocker": "synthetic_staging_only_no_real_case",
            "score_failure_attribution": "not_run_synthetic_staging_only",
            "failure_attribution_labels": [
                "synthetic_staging_fixture_only",
                "ready_for_guarded_private_source_extraction_gate",
            ],
            "evidence_files": [
                "benchmark_run.compact.json",
                "runner-flow-plan.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "synthetic_private_job_root_materialized": True,
            "context_dir_created": True,
            "buggy_source_dir_created": True,
            "patch_dir_created": True,
            "prompt_placeholder_written": True,
            "prompt_path_rendered": True,
            "patch_output_parent_reserved": True,
            "compact_run_filename_reserved": True,
            "runner_flow_plan_public_json_written": True,
            "no_absolute_paths_public": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "synthetic_staging_only_no_real_case"

    runner_plan = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "path_recorded": False,
        "relative_paths": {
            "context_dir": "context",
            "buggy_source_dir": "buggy-source",
            "patch_dir": "Patches/lagent_239",
            "prompt": "context/prompt.md",
            "expected_patch": AGENTISSUE_PATCH_RELATIVE_PATH,
            "compact_run": "benchmark_run.compact.json",
            "runner_plan": "runner-flow-plan.public.json",
        },
        "command_placeholders": wrapper["commands"],
        "execution_boundary": wrapper["execution_boundary"],
        "stop_rules": wrapper["stop_rules"],
    }

    context_dir.mkdir(parents=True, exist_ok=True)
    buggy_source_dir.mkdir(parents=True, exist_ok=True)
    patch_dir.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    (buggy_source_dir / ".gitkeep").write_text("", encoding="utf-8")
    (patch_dir / ".gitkeep").write_text("", encoding="utf-8")
    runner_plan_path.write_text(
        json.dumps(runner_plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    created_relative_paths = [
        "context/",
        "context/prompt.md",
        "buggy-source/",
        "buggy-source/.gitkeep",
        "Patches/lagent_239/",
        "Patches/lagent_239/.gitkeep",
        "runner-flow-plan.public.json",
        "benchmark_run.compact.json",
    ]
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "staging_root_path_recorded": False,
        "created_relative_paths": created_relative_paths,
        "prompt_relative_path": "context/prompt.md",
        "expected_patch_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
        "compact_run_relative_path": "benchmark_run.compact.json",
        "runner_plan_relative_path": "runner-flow-plan.public.json",
        "command_rendering_checks": {
            "codex_argv_uses_prompt_placeholder": True,
            "codex_argv_uses_buggy_source_placeholder": True,
            "eval_argv_uses_selected_image": True,
            "patch_output_parent_reserved": True,
            "compact_reducer_filename_reserved": True,
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "raw_issue_text_read": False,
            "raw_patch_recorded": False,
            "raw_log_recorded": False,
            "credential_values_recorded": False,
        },
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "add a guarded opt-in real-source extraction and host-Codex execution "
            "gate for lagent_239, still defaulting to no-execute"
        ),
    }


def materialize_agentissue_codex_cli_runner_execution_gate(
    gate_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute gate packet for the first real AgentIssue runner step."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner execution gate currently only supports selected tag lagent_239"
        )
    root = Path(gate_root).expanduser()
    staging = materialize_agentissue_codex_cli_runner_synthetic_staging(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    wrapper = build_agentissue_codex_cli_runner_wrapper(
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    docker = _agentissue_public_label(docker_binary, limit=80)
    image = AGENTISSUE_DEFAULT_IMAGE
    container_label = "<tmp-agentissue-lagent-239-container>"
    job_root = "<abs-private-job-root>"
    buggy_source = f"{job_root}/buggy-source"
    patch_path = f"{job_root}/{AGENTISSUE_PATCH_RELATIVE_PATH}"
    gate_path = root / "execution-gate.public.json"
    compact_run_path = root / "benchmark_run.compact.json"

    extraction_commands = {
        "inspect_selected_image": [docker, "image", "inspect", image],
        "create_selected_container": [
            docker,
            "create",
            "--name",
            container_label,
            image,
        ],
        "copy_buggy_source": [
            docker,
            "cp",
            f"{container_label}:/workspace/.",
            buggy_source,
        ],
        "remove_selected_container": [docker, "rm", container_label],
    }
    git_baseline_commands = {
        "init": ["git", "-C", buggy_source, "init"],
        "add": ["git", "-C", buggy_source, "add", "."],
        "commit": [
            "git",
            "-C",
            buggy_source,
            "commit",
            "-m",
            "agentissue-bench-buggy-source-baseline",
        ],
    }
    patch_export = {
        "input_source": "buggy_source_git_diff",
        "command_shape": f"git -C {buggy_source} diff --binary > {patch_path}",
        "output_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
    }
    gate = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": image,
        "path_recorded": False,
        "default_mode": "no_execute",
        "future_opt_in_required": True,
        "single_tag_only": True,
        "relative_paths": {
            "context_prompt": "context/prompt.md",
            "buggy_source_dir": "buggy-source",
            "attempt_patch": AGENTISSUE_PATCH_RELATIVE_PATH,
            "execution_gate": "execution-gate.public.json",
            "compact_run": "benchmark_run.compact.json",
        },
        "source_extraction_gate": {
            "commands": extraction_commands,
            "selected_container_only": True,
            "execute_by_default": False,
            "docker_invoked": False,
            "docker_pull_or_start_allowed": False,
        },
        "private_git_baseline_gate": {
            "commands": git_baseline_commands,
            "execute_by_default": False,
            "destructive_git": False,
        },
        "host_codex_gate": {
            "command": wrapper["commands"]["codex_patch_worker"],
            "execute_by_default": False,
            "codex_cli_invoked": False,
            "auth_material_synced": False,
        },
        "patch_output_gate": patch_export,
        "eval_gate": wrapper["commands"]["single_tag_eval"],
        "stop_rules": {
            **wrapper["stop_rules"],
            "stop_before_real_source_extraction_without_future_gate": True,
            "stop_before_host_codex_execution_without_future_gate": True,
        },
    }

    benchmark_run = json.loads(json.dumps(staging["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_execution_gate",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_gate",
            "first_blocker": "execution_gate_only_no_real_case",
            "score_failure_attribution": "not_run_execution_gate_only",
            "failure_attribution_labels": [
                "execution_gate_fixture_only",
                "ready_for_future_run_specific_opt_in",
            ],
            "evidence_files": [
                "execution-gate.public.json",
                "benchmark_run.compact.json",
                "runner-flow-plan.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "execution_gate_materialized": True,
            "synthetic_staging_reused": True,
            "selected_container_source_extraction_commands_rendered": True,
            "private_git_baseline_commands_rendered": True,
            "host_codex_command_readiness_rendered": True,
            "attempt_patch_output_placement_checked": True,
            "compact_run_filename_checked": True,
            "future_execution_opt_in_required": True,
            "no_real_source_extraction": True,
            "no_real_codex_execution": True,
            "no_docker_pull_or_start": True,
            "no_auth_sync_to_shared_host": True,
            "no_fixed_diff_or_oracle_read": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "execution_gate_only_no_real_case"

    gate_path.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": image,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "gate_root_path_recorded": False,
        "synthetic_staging": {
            "schema_version": staging["schema_version"],
            "ready": staging["ready"],
            "created_relative_paths": staging["created_relative_paths"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *staging["created_relative_paths"],
            "execution-gate.public.json",
        ],
        "gate_relative_path": "execution-gate.public.json",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "attempt_patch_relative_path": AGENTISSUE_PATCH_RELATIVE_PATH,
        "gate_checks": {
            "selected_container_source_extraction_commands_rendered": True,
            "private_git_baseline_commands_rendered": True,
            "host_codex_command_readiness_rendered": True,
            "attempt_patch_output_placement_checked": True,
            "future_execution_opt_in_required": True,
        },
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "source_extracted": False,
            "git_baseline_created": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "credential_values_recorded": False,
            "auth_material_synced": False,
        },
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "build a no-execute first-run handoff packet for lagent_239"
        ),
    }


def materialize_agentissue_codex_cli_runner_first_run_handoff(
    handoff_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute first-run handoff packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner first-run handoff currently only supports selected tag lagent_239"
        )
    root = Path(handoff_root).expanduser()
    gate = materialize_agentissue_codex_cli_runner_execution_gate(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    handoff_path = root / "first-run-handoff.public.json"
    handoff_markdown_path = root / "first-run-handoff.md"
    compact_run_path = root / "benchmark_run.compact.json"

    no_execute_cli_argv = [
        "goal-harness",
        "benchmark",
        "agentissue-codex-runner-flow",
        "--goal-id",
        "<goal-id>",
        "--tag",
        tag,
        "--execution-gate-root",
        "<private-gate-root>",
        "--delivery-batch-scale",
        "multi_surface",
        "--delivery-outcome",
        "outcome_progress",
        "--execute",
    ]
    safety_checklist = [
        {
            "item": "private_job_root_selected",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": False,
        },
        {
            "item": "codex_auth_stays_on_host",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
        {
            "item": "no_codex_home_sync_to_shared_host",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
        {
            "item": "selected_container_source_extraction_planned",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": False,
        },
        {
            "item": "attempt_patch_compact_reducer_planned",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
        {
            "item": "upload_submit_public_ranking_disabled",
            "required_before_later_e2e": True,
            "satisfied_by_this_packet": True,
        },
    ]
    handoff = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "path_recorded": False,
        "default_mode": "no_execute",
        "later_operator_triggered_e2e": True,
        "real_run_done": False,
        "exact_command_shape": {
            "argv": no_execute_cli_argv,
            "runs_real_benchmark": False,
            "appends_compact_no_run_event": True,
        },
        "private_artifact_boundary": {
            "root_placeholder": "<private-gate-root>",
            "root_path_recorded": False,
            "public_relative_files": [
                "runner-flow-plan.public.json",
                "execution-gate.public.json",
                "first-run-handoff.public.json",
                "first-run-handoff.md",
                "benchmark_run.compact.json",
            ],
            "private_relative_dirs": [
                "context/",
                "buggy-source/",
                "Patches/lagent_239/",
            ],
            "raw_artifacts_public": False,
            "absolute_paths_public": False,
        },
        "expected_compact_outputs": {
            "benchmark_run_mode": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_MODE,
            "compact_run": "benchmark_run.compact.json",
            "history_event": "benchmark_run_v0",
            "official_score_claim_allowed": False,
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
        "budget_auth_boundary": {
            "codex_auth_values_read": False,
            "codex_home_synced": False,
            "model_api_invoked": False,
            "model_budget_spent_by_packet": False,
            "docker_invoked_by_packet": False,
            "shared_remote_host_receives_codex_auth": False,
        },
        "safety_checklist": safety_checklist,
        "no_execute_assertions": {
            "source_extracted": False,
            "codex_cli_invoked": False,
            "docker_container_started": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
            "destructive_git": False,
            "production_action": False,
        },
    }
    handoff_markdown = (
        "# AgentIssue-Bench lagent_239 First-Run Handoff\n\n"
        "This packet is no-execute. It names the command shape, private artifact "
        "boundary, compact outputs, budget/auth boundary, and safety checklist "
        "for a later operator-triggered e2e run.\n\n"
        "## Command Shape\n\n"
        "```text\n"
        + " ".join(no_execute_cli_argv)
        + "\n```\n\n"
        "## Boundary\n\n"
        "- Codex auth stays on the host and is not copied to a shared machine.\n"
        "- Public files are limited to `*.public.json`, `*.compact.json`, and this packet.\n"
        "- No source extraction, Docker start, Codex invocation, patch generation, "
        "evaluation, upload, submit, public ranking, destructive git, or production "
        "action is performed by this packet.\n"
    )

    benchmark_run = json.loads(json.dumps(gate["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_first_run_handoff",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_first_run_handoff",
            "first_blocker": "first_run_handoff_only_no_real_case",
            "score_failure_attribution": "not_run_first_run_handoff_only",
            "failure_attribution_labels": [
                "first_run_handoff_packet_only",
                "ready_for_later_operator_triggered_e2e_run",
            ],
            "evidence_files": [
                "first-run-handoff.public.json",
                "first-run-handoff.md",
                "execution-gate.public.json",
                "benchmark_run.compact.json",
                "runner-flow-plan.public.json",
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "first_run_handoff_materialized": True,
            "exact_command_shape_rendered": True,
            "private_artifact_boundary_declared": True,
            "expected_compact_outputs_declared": True,
            "budget_auth_boundary_declared": True,
            "safety_checklist_declared": True,
            "no_execute_packet": True,
            "no_codex_auth_value_read": True,
            "no_codex_home_sync": True,
            "no_model_budget_spent_by_packet": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "first_run_handoff_only_no_real_case"

    handoff_path.write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    handoff_markdown_path.write_text(handoff_markdown, encoding="utf-8")
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": True,
        "materialized": True,
        "path_recorded": False,
        "handoff_root_path_recorded": False,
        "execution_gate": {
            "schema_version": gate["schema_version"],
            "ready": gate["ready"],
            "gate_relative_path": gate["gate_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *gate["created_relative_paths"],
            "first-run-handoff.public.json",
            "first-run-handoff.md",
        ],
        "handoff_relative_path": "first-run-handoff.public.json",
        "handoff_markdown_relative_path": "first-run-handoff.md",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "handoff_checks": {
            "exact_command_shape_rendered": True,
            "private_artifact_boundary_declared": True,
            "expected_compact_outputs_declared": True,
            "budget_auth_boundary_declared": True,
            "safety_checklist_declared": True,
            "later_operator_triggered_e2e": True,
        },
        "execution_boundary": handoff["no_execute_assertions"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "use the no-execute first-run handoff packet as the checklist for a "
            "later operator-triggered AgentIssue-Bench lagent_239 e2e run"
        ),
    }


def materialize_agentissue_codex_cli_runner_workflow_check(
    workflow_check_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute workflow check packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner workflow check currently only supports selected tag lagent_239"
        )
    root = Path(workflow_check_root).expanduser()
    handoff = materialize_agentissue_codex_cli_runner_first_run_handoff(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    runner_plan_path = root / "runner-flow-plan.public.json"
    gate_path = root / "execution-gate.public.json"
    handoff_path = root / "first-run-handoff.public.json"
    workflow_path = root / "workflow-check.public.json"
    compact_run_path = root / "benchmark_run.compact.json"

    runner_plan = json.loads(runner_plan_path.read_text(encoding="utf-8"))
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    handoff_public = json.loads(handoff_path.read_text(encoding="utf-8"))

    codex_command = runner_plan["command_placeholders"]["codex_patch_worker"]
    eval_command = runner_plan["command_placeholders"]["single_tag_eval"]
    patch_export = runner_plan["command_placeholders"]["patch_export"]
    budget_auth = handoff_public["budget_auth_boundary"]
    no_execute = handoff_public["no_execute_assertions"]
    required_public_files = [
        "runner-flow-plan.public.json",
        "execution-gate.public.json",
        "first-run-handoff.public.json",
        "first-run-handoff.md",
        "workflow-check.public.json",
        "benchmark_run.compact.json",
    ]
    required_private_dirs = [
        "context/",
        "buggy-source/",
        "Patches/lagent_239/",
    ]
    checks = {
        "single_selected_tag": runner_plan["selected_tag"] == gate["selected_tag"] == handoff_public["selected_tag"] == tag,
        "selected_image_consistent": runner_plan["selected_image"] == gate["selected_image"] == handoff_public["selected_image"],
        "source_extracted_before_codex": bool(codex_command.get("runs_after_buggy_source_extraction")),
        "host_codex_uses_ephemeral": "--ephemeral" in codex_command.get("argv", []),
        "host_codex_auth_not_synced": codex_command.get("auth_material_synced") is False and budget_auth["codex_home_synced"] is False,
        "worker_no_network_or_docker": codex_command.get("worker_network_allowed") is False and codex_command.get("worker_docker_allowed") is False,
        "patch_from_buggy_source_git_diff": patch_export["input_source"] == "buggy_source_git_diff",
        "attempt_patch_relative_path": patch_export["output_relative_path"] == AGENTISSUE_PATCH_RELATIVE_PATH,
        "single_tag_eval_no_upload_submit": eval_command["upload"] is False and eval_command["submit"] is False,
        "single_tag_eval_no_public_ranking": eval_command["public_ranking_path"] is False,
        "no_execute_packet": all(value is False for value in no_execute.values()),
        "public_files_compact_or_public": all(
            path.endswith((".public.json", ".compact.json", ".md"))
            for path in required_public_files
        ),
        "private_dirs_not_public_artifacts": all(path.endswith("/") for path in required_private_dirs),
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    workflow_check = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": not failed_checks,
        "materialized": True,
        "path_recorded": False,
        "default_mode": "no_execute",
        "input_packets": {
            "runner_plan": "runner-flow-plan.public.json",
            "execution_gate": "execution-gate.public.json",
            "first_run_handoff": "first-run-handoff.public.json",
        },
        "required_public_files": required_public_files,
        "required_private_dirs": required_private_dirs,
        "workflow_checks": checks,
        "failed_checks": failed_checks,
        "execution_boundary": {
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_image_pulled": False,
            "docker_container_started": False,
            "source_extracted": False,
            "git_baseline_created": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "credential_values_recorded": False,
            "auth_material_synced": False,
            "upload": False,
            "submit": False,
            "public_ranking_path": False,
        },
        "stop_before_later_e2e_unless": [
            "private_job_root_selected",
            "operator_explicitly_triggers_real_run",
            "runner_artifact_reducer_writes_compact_public_result",
        ],
    }

    benchmark_run = json.loads(json.dumps(handoff["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_workflow_check",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_workflow_check",
            "first_blocker": "workflow_check_only_no_real_case",
            "score_failure_attribution": "not_run_workflow_check_only",
            "failure_attribution_labels": [
                "workflow_check_packet_only",
                "ready_for_later_operator_triggered_e2e_run"
                if not failed_checks
                else "workflow_check_failed_before_real_run",
            ],
            "evidence_files": required_public_files,
        }
    )
    benchmark_run["validation"].update(
        {
            "workflow_check_materialized": True,
            "workflow_check_all_passed": not failed_checks,
            "workflow_check_failed_checks": failed_checks,
            "single_selected_tag": checks["single_selected_tag"],
            "selected_image_consistent": checks["selected_image_consistent"],
            "source_extracted_before_codex": checks["source_extracted_before_codex"],
            "host_codex_uses_ephemeral": checks["host_codex_uses_ephemeral"],
            "host_codex_auth_not_synced": checks["host_codex_auth_not_synced"],
            "worker_no_network_or_docker": checks["worker_no_network_or_docker"],
            "patch_from_buggy_source_git_diff": checks["patch_from_buggy_source_git_diff"],
            "single_tag_eval_no_upload_submit": checks["single_tag_eval_no_upload_submit"],
            "single_tag_eval_no_public_ranking": checks["single_tag_eval_no_public_ranking"],
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "workflow_check_only_no_real_case"

    workflow_path.write_text(
        json.dumps(workflow_check, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready": not failed_checks,
        "materialized": True,
        "path_recorded": False,
        "workflow_check_root_path_recorded": False,
        "first_run_handoff": {
            "schema_version": handoff["schema_version"],
            "ready": handoff["ready"],
            "handoff_relative_path": handoff["handoff_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *handoff["created_relative_paths"],
            "workflow-check.public.json",
        ],
        "workflow_check_relative_path": "workflow-check.public.json",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "workflow_checks": checks,
        "failed_checks": failed_checks,
        "execution_boundary": workflow_check["execution_boundary"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "use workflow-check.public.json as the pre-run invariant packet before "
            "any later operator-triggered AgentIssue-Bench lagent_239 e2e run"
        ),
    }

def materialize_agentissue_codex_cli_runner_run_gate(
    run_gate_root: str | Path,
    *,
    selected_tag: str = AGENTISSUE_DEFAULT_TAG,
    codex_binary: str = "codex",
    docker_binary: str = "docker",
) -> dict[str, Any]:
    """Create a no-execute run-specific gate packet for AgentIssue lagent_239."""

    tag = _agentissue_public_label(selected_tag)
    if tag != AGENTISSUE_DEFAULT_TAG:
        raise ValueError(
            "agentissue Codex runner run-specific gate currently only supports selected tag lagent_239"
        )
    root = Path(run_gate_root).expanduser()
    workflow = materialize_agentissue_codex_cli_runner_workflow_check(
        root,
        selected_tag=tag,
        codex_binary=codex_binary,
        docker_binary=docker_binary,
    )
    workflow_path = root / "workflow-check.public.json"
    gate_path = root / "execution-gate.public.json"
    handoff_path = root / "first-run-handoff.public.json"
    run_gate_path = root / "run-specific-gate.public.json"
    run_gate_markdown_path = root / "run-specific-gate.md"
    compact_run_path = root / "benchmark_run.compact.json"

    workflow_check = json.loads(workflow_path.read_text(encoding="utf-8"))
    execution_gate = json.loads(gate_path.read_text(encoding="utf-8"))
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

    gate_items = [
        {
            "id": "selected_tag_and_image_locked",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["single_selected_tag"]
            and workflow_check["workflow_checks"]["selected_image_consistent"],
            "public_evidence": "workflow-check.public.json",
        },
        {
            "id": "host_codex_auth_local_only",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["host_codex_auth_not_synced"],
            "public_evidence": "workflow-check.public.json",
        },
        {
            "id": "private_job_root_selected",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "stop_if_missing": True,
        },
        {
            "id": "operator_explicit_real_run_trigger",
            "owner": "owner",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "stop_if_missing": True,
        },
        {
            "id": "selected_container_source_extracted",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "public_command_shape": "execution-gate.public.json",
            "stop_if_missing": True,
        },
        {
            "id": "private_git_baseline_created_before_codex",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "public_command_shape": "execution-gate.public.json",
            "stop_if_missing": True,
        },
        {
            "id": "host_codex_exec_ephemeral_from_buggy_source",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": False,
            "public_command_shape": "execution-gate.public.json",
            "stop_if_missing": True,
        },
        {
            "id": "attempt_patch_reducer_configured",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["patch_from_buggy_source_git_diff"]
            and workflow_check["workflow_checks"]["attempt_patch_relative_path"],
            "public_evidence": AGENTISSUE_PATCH_RELATIVE_PATH,
        },
        {
            "id": "selected_tag_eval_no_upload_submit_ranking",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["single_tag_eval_no_upload_submit"]
            and workflow_check["workflow_checks"]["single_tag_eval_no_public_ranking"],
            "public_evidence": "workflow-check.public.json",
        },
        {
            "id": "compact_public_reducer_enabled",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": workflow_check["workflow_checks"]["public_files_compact_or_public"],
            "public_evidence": "benchmark_run.compact.json",
        },
        {
            "id": "raw_artifact_and_auth_leak_stop_rules_enabled",
            "owner": "agent",
            "required_before_real_run": True,
            "satisfied_by_packet": True,
            "stop_if_raw_task_patch_log_trajectory_screenshot_or_auth_material_public": True,
        },
    ]
    blocking_gate_ids = [
        item["id"]
        for item in gate_items
        if item["required_before_real_run"] and not item["satisfied_by_packet"]
    ]
    run_gate = {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "default_mode": "no_execute",
        "materialized": True,
        "path_recorded": False,
        "real_run_authorized": False,
        "ready_for_real_run": False,
        "ready_for_operator_review": True,
        "blocking_gate_ids": blocking_gate_ids,
        "input_packets": {
            "workflow_check": "workflow-check.public.json",
            "first_run_handoff": "first-run-handoff.public.json",
            "execution_gate": "execution-gate.public.json",
        },
        "owner_agent_gate_items": gate_items,
        "phase_order": [
            "select_private_job_root",
            "extract_selected_container_buggy_source",
            "create_private_git_baseline",
            "run_host_codex_exec_ephemeral_from_buggy_source",
            "export_attempt_patch_from_buggy_source_git_diff",
            "run_selected_tag_eval_no_upload_submit_ranking",
            "reduce_to_compact_public_result",
        ],
        "public_artifact_policy": {
            "allowed_public_relative_files": [
                "runner-flow-plan.public.json",
                "execution-gate.public.json",
                "first-run-handoff.public.json",
                "workflow-check.public.json",
                "run-specific-gate.public.json",
                "run-specific-gate.md",
                "benchmark_run.compact.json",
            ],
            "raw_task_material_public": False,
            "patch_content_public": False,
            "raw_logs_public": False,
            "trajectories_public": False,
            "screenshots_public": False,
            "absolute_paths_public": False,
            "credential_values_public": False,
        },
        "credential_boundary": {
            "codex_auth_values_read_by_packet": False,
            "codex_home_synced": False,
            "shared_remote_host_receives_codex_auth": False,
            "host_codex_auth_local_only": True,
        },
        "stop_conditions": [
            "private_job_root_missing",
            "operator_real_run_trigger_missing",
            "selected_container_source_not_extracted",
            "private_git_baseline_missing_before_codex",
            "host_codex_not_ephemeral_or_not_from_buggy_source",
            "attempt_patch_missing_or_not_from_buggy_source_git_diff",
            "eval_attempts_upload_submit_or_public_ranking",
            "public_artifact_contains_raw_task_patch_log_trajectory_screenshot_auth_or_absolute_path",
        ],
        "execution_boundary": {
            **workflow_check["execution_boundary"],
            "real_run_authorized": False,
            "operator_trigger_recorded": False,
        },
        "rendered_command_sources": {
            "source_extraction_gate": execution_gate["source_extraction_gate"]["commands"],
            "private_git_baseline_gate": execution_gate["private_git_baseline_gate"]["commands"],
            "host_codex_gate": execution_gate["host_codex_gate"]["command"],
            "patch_output_gate": execution_gate["patch_output_gate"],
            "eval_gate": execution_gate["eval_gate"],
        },
    }
    markdown = (
        "# AgentIssue-Bench lagent_239 Run-Specific Gate\n\n"
        "This packet is no-execute. It separates the gates that are already "
        "covered by public/compact no-run packets from the gates that still "
        "block a real no-upload run.\n\n"
        "## Blocking Gates\n\n"
        + "\n".join(f"- {gate_id}" for gate_id in blocking_gate_ids)
        + "\n\n## Public Boundary\n\n"
        "- Codex auth stays on the host; no Codex home or auth material is synced.\n"
        "- Public artifacts stay compact/public and relative-path only.\n"
        "- Raw task material, patch content, raw logs, trajectories, screenshots, "
        "credentials, and absolute private paths remain private.\n"
    )

    benchmark_run = json.loads(json.dumps(workflow["benchmark_run"]))
    benchmark_run.update(
        {
            "job_name": "agentissue_lagent_239_codex_cli_runner_run_gate",
            "mode": AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_MODE,
            "worker_mode": "trusted_host_codex_cli_no_execute_run_gate",
            "first_blocker": "run_gate_packet_only_real_run_not_authorized",
            "score_failure_attribution": "not_run_run_gate_only",
            "failure_attribution_labels": [
                "run_specific_gate_packet_only",
                "real_run_blocked_until_gate_items_satisfied",
            ],
            "evidence_files": run_gate["public_artifact_policy"][
                "allowed_public_relative_files"
            ],
        }
    )
    benchmark_run["validation"].update(
        {
            "run_specific_gate_materialized": True,
            "owner_agent_gate_items_declared": True,
            "blocking_gate_ids_declared": True,
            "ready_for_operator_review": True,
            "real_run_authorized": False,
            "private_job_root_required": True,
            "operator_trigger_required": True,
            "phase_order_declared": True,
            "credential_boundary_declared": True,
            "public_artifact_policy_declared": True,
            "stop_conditions_declared": True,
            "no_execute_packet": True,
            "no_real_source_extraction": True,
            "no_real_codex_execution": True,
            "no_docker_pull_or_start": True,
            "no_auth_sync_to_shared_host": True,
        }
    )
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            trial["exception_type"] = "run_gate_packet_only_no_real_case"

    run_gate_path.write_text(
        json.dumps(run_gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run_gate_markdown_path.write_text(markdown, encoding="utf-8")
    compact_run_path.write_text(
        json.dumps(benchmark_run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTISSUE_BENCHMARK_ID,
        "selected_tag": tag,
        "selected_image": AGENTISSUE_DEFAULT_IMAGE,
        "ready_for_operator_review": True,
        "ready_for_real_run": False,
        "materialized": True,
        "path_recorded": False,
        "run_gate_root_path_recorded": False,
        "blocking_gate_ids": blocking_gate_ids,
        "workflow_check": {
            "schema_version": workflow["schema_version"],
            "ready": workflow["ready"],
            "workflow_check_relative_path": workflow["workflow_check_relative_path"],
            "path_recorded": False,
        },
        "created_relative_paths": [
            *workflow["created_relative_paths"],
            "run-specific-gate.public.json",
            "run-specific-gate.md",
        ],
        "run_gate_relative_path": "run-specific-gate.public.json",
        "run_gate_markdown_relative_path": "run-specific-gate.md",
        "compact_run_relative_path": "benchmark_run.compact.json",
        "gate_checks": {
            "owner_agent_gate_items_declared": True,
            "blocking_gate_ids_declared": True,
            "credential_boundary_declared": True,
            "public_artifact_policy_declared": True,
            "stop_conditions_declared": True,
            "real_run_authorized": False,
        },
        "execution_boundary": run_gate["execution_boundary"],
        "benchmark_run": benchmark_run,
        "recommended_next_action": (
            "review run-specific gate packet before any later real no-upload "
            "AgentIssue-Bench lagent_239 Docker/Codex execution"
        ),
    }

def _claim_review_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _claim_review_run_mode(run: dict[str, Any]) -> str:
    return str(run.get("mode") or "").strip().lower().replace("_", "-")


def _claim_review_run_score(run: dict[str, Any]) -> float | None:
    official = run.get("official_task_score") if isinstance(run.get("official_task_score"), dict) else {}
    return _claim_review_numeric(official.get("value"))


def _claim_review_worker_evidence(run: dict[str, Any]) -> dict[str, Any]:
    interaction = run.get("interaction_counters") if isinstance(run.get("interaction_counters"), dict) else {}
    calls = interaction.get("goal_harness_cli_calls") if isinstance(interaction.get("goal_harness_cli_calls"), dict) else {}
    worker_cli_total = run.get("worker_goal_harness_cli_call_total")
    if not isinstance(worker_cli_total, int) or isinstance(worker_cli_total, bool):
        worker_cli_total = calls.get("total", 0)
    if not isinstance(worker_cli_total, int) or isinstance(worker_cli_total, bool):
        worker_cli_total = 0
    observation = run.get("active_user_observation") if isinstance(run.get("active_user_observation"), dict) else {}
    worker_file_count = run.get("worker_benchmark_run_schema_ok_count")
    if not isinstance(worker_file_count, int) or isinstance(worker_file_count, bool):
        worker_file_count = 0
    present = bool(
        worker_cli_total > 0
        or worker_file_count > 0
        or observation.get("observed_after_worker_start")
        or observation.get("worker_observation_proof")
    )
    return {
        "worker_goal_harness_cli_call_total": worker_cli_total,
        "worker_benchmark_run_schema_ok_count": worker_file_count,
        "active_user_observed_after_worker_start": bool(
            observation.get("observed_after_worker_start")
            or observation.get("worker_observation_proof")
        ),
        "present": present,
    }


def _claim_review_failure_labels(run: dict[str, Any]) -> list[str]:
    labels = run.get("failure_attribution_labels")
    if not isinstance(labels, list):
        return []
    return [
        str(label)
        for label in labels
        if isinstance(label, (str, int, float)) and not isinstance(label, bool)
    ][:8]


def _claim_review_score_failure_attribution(run: dict[str, Any]) -> str:
    value = run.get("score_failure_attribution")
    return str(value).strip() if isinstance(value, str) and value.strip() else "none"


def _claim_review_pick_runs(
    runs: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    baseline: dict[str, Any] | None = None
    treatment: dict[str, Any] | None = None
    for run in runs:
        mode = _claim_review_run_mode(run)
        job_name = str(run.get("job_name") or "").lower().replace("_", "-")
        if baseline is None and (
            "hardened-codex" in mode
            or "bare-codex" in mode
            or run.get("hardened_install_baseline") is True
        ):
            baseline = run
        if treatment is None and (
            "codex-goal-harness" in mode
            or "codex-goal-harness" in job_name
            or _claim_review_worker_evidence(run)["present"]
        ):
            treatment = run
    if baseline is None and runs:
        baseline = runs[0]
    if treatment is None and len(runs) > 1:
        treatment = runs[1]
    return baseline, treatment


def build_benchmark_claim_review(
    benchmark_comparison: dict[str, Any],
    *,
    benchmark_runs: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Review compact benchmark evidence without reading raw artifacts."""

    runs = [run for run in benchmark_runs if isinstance(run, dict)]
    baseline, treatment = _claim_review_pick_runs(runs)
    official_delta = _claim_review_numeric(
        benchmark_comparison.get("official_task_score_delta")
    )
    if official_delta is None and baseline and treatment:
        baseline_score = _claim_review_run_score(baseline)
        treatment_score = _claim_review_run_score(treatment)
        if baseline_score is not None and treatment_score is not None:
            official_delta = treatment_score - baseline_score

    treatment_evidence = _claim_review_worker_evidence(treatment) if treatment else {"present": False}
    baseline_labels = _claim_review_failure_labels(baseline or {})
    baseline_attribution = _claim_review_score_failure_attribution(baseline or {})
    attribution_caveat = baseline_attribution in {
        "verifier_platform_probe_failure",
        "verifier_infrastructure_failure",
        "verifier_dependency_install_failure",
    } or any(label.startswith("verifier_") for label in baseline_labels)
    boundary_mismatch_count = sum(
        int(run.get("worker_submit_eligible_mismatch_count") or 0)
        for run in runs
        if isinstance(run.get("worker_submit_eligible_mismatch_count"), int)
        and not isinstance(run.get("worker_submit_eligible_mismatch_count"), bool)
    )

    blockers: list[str] = []
    if official_delta is None:
        blockers.append("missing_official_task_score_delta")
    elif official_delta <= 0:
        blockers.append("no_positive_official_task_score_delta")
    if official_delta is not None and official_delta > 0 and not treatment_evidence.get("present"):
        blockers.append("missing_treatment_worker_goal_harness_evidence")
    if official_delta is not None and official_delta > 0 and attribution_caveat:
        blockers.append("baseline_failure_attribution_caveat")
    if boundary_mismatch_count:
        blockers.append("worker_submit_eligible_boundary_mismatch")

    positive_delta = official_delta is not None and official_delta > 0
    assisted_evidence = bool(treatment_evidence.get("present"))
    clean_validation = positive_delta and assisted_evidence and not blockers
    candidate_validation = positive_delta and assisted_evidence
    if clean_validation:
        claim_strength = "strong_goal_harness_assisted_score_recovery"
    elif candidate_validation:
        claim_strength = "candidate_score_recovery_needs_attribution_review"
    elif positive_delta:
        claim_strength = "score_delta_without_assisted_worker_evidence"
    elif assisted_evidence:
        claim_strength = "loop_validation_no_score_uplift"
    else:
        claim_strength = "no_validation_enhancement"

    if "baseline_failure_attribution_caveat" in blockers:
        next_action = (
            "run a same-protocol reliability repeat or add finer compact "
            "verifier-side attribution before making a clean score-recovery claim"
        )
    elif "missing_treatment_worker_goal_harness_evidence" in blockers:
        next_action = "collect compact worker-visible Goal Harness evidence before claiming assisted recovery"
    elif "worker_submit_eligible_boundary_mismatch" in blockers:
        next_action = "normalize the compact worker submit boundary before public claim review"
    elif clean_validation:
        next_action = "record as clean compact score-recovery evidence while preserving no-leaderboard claim boundary"
    else:
        next_action = "treat as loop/attribution evidence and seek a stronger paired sample"

    claim_boundary = benchmark_comparison.get("claim_boundary") if isinstance(benchmark_comparison.get("claim_boundary"), dict) else {}
    return {
        "schema_version": BENCHMARK_CLAIM_REVIEW_SCHEMA_VERSION,
        "input_schema_versions": {
            "benchmark_comparison": benchmark_comparison.get("schema_version"),
            "benchmark_runs": [
                run.get("schema_version") for run in runs if run.get("schema_version")
            ],
        },
        "task_id": benchmark_comparison.get("task_id"),
        "comparison_id": benchmark_comparison.get("comparison_id"),
        "official_task_score_delta": official_delta,
        "control_plane_score_delta": benchmark_comparison.get("control_plane_score_delta"),
        "treatment_worker_evidence": treatment_evidence,
        "baseline_score_failure_attribution": baseline_attribution,
        "baseline_failure_attribution_labels": baseline_labels,
        "boundary_mismatch_count": boundary_mismatch_count,
        "claim_boundary": {
            "leaderboard_claim_allowed": bool(claim_boundary.get("leaderboard_claim_allowed")),
            "official_score_uplift_claim_allowed": bool(claim_boundary.get("official_score_uplift_claim_allowed")),
            "assisted_collaboration_claim_allowed": bool(claim_boundary.get("assisted_collaboration_claim_allowed")),
            "raw_trace_excluded": claim_boundary.get("raw_trace_excluded") is not False,
        },
        "decision": {
            "claim_strength": claim_strength,
            "validation_enhancement_candidate": candidate_validation,
            "clean_validation_enhancement": clean_validation,
            "blockers": blockers,
            "next_action": next_action,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
    }


def _compact_positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0


def _verifier_attribution_labels(run: dict[str, Any]) -> list[str]:
    labels = set(_claim_review_failure_labels(run))
    outcome = run.get("worker_bridge_outcome")
    if isinstance(outcome, dict):
        labels.update(_claim_review_failure_labels(outcome))
    trials = run.get("trials")
    if isinstance(trials, list):
        for trial in trials[:8]:
            if not isinstance(trial, dict):
                continue
            label_values = trial.get("verifier_failure_attribution_labels")
            if isinstance(label_values, list):
                labels.update(
                    str(label)
                    for label in label_values
                    if isinstance(label, (str, int, float))
                    and not isinstance(label, bool)
                )
            attribution = trial.get("verifier_failure_attribution")
            if isinstance(attribution, str) and attribution.strip():
                labels.add(attribution.strip())
    return sorted(labels)[:12]


def _verifier_attribution_class(
    *,
    score: float | None,
    score_attribution: str,
    labels: list[str],
    verifier_failure_count: int,
    verifier_dependency_failure_count: int,
) -> str:
    if score is not None and score > 0:
        return "no_score_failure"
    if (
        score_attribution == "verifier_dependency_install_failure"
        or verifier_dependency_failure_count > 0
        or "verifier_dependency_install_failure" in labels
    ):
        return "verifier_dependency_install_failure"
    if score_attribution == "verifier_platform_probe_failure" or (
        "verifier_platform_probe_failure" in labels
    ):
        return "verifier_platform_probe_failure"
    if score_attribution in {"verifier_infrastructure_failure", "verifier_failure"}:
        return "verifier_infrastructure_failure"
    if any(label.startswith("verifier_") for label in labels) or (
        verifier_failure_count > 0
    ):
        return "verifier_infrastructure_failure"
    if score_attribution in {
        "model_solution_failure",
        "agent_solution_failure",
        "task_solution_failure",
        "solution_incorrect",
        "official_verifier_solution_failure",
    }:
        return "model_or_solution_failure"
    if score is not None and score == 0:
        return "unattributed_score_failure"
    return "missing_official_score"


def _compact_validation_failed_checks(run: dict[str, Any]) -> list[str]:
    validation = run.get("validation")
    if not isinstance(validation, dict):
        return []
    failed = validation.get("failed_checks")
    if not isinstance(failed, list):
        return []
    return [
        str(item)
        for item in failed
        if isinstance(item, (str, int, float)) and not isinstance(item, bool)
    ][:12]


def _verifier_attribution_run_review(run: dict[str, Any]) -> dict[str, Any]:
    score = _claim_review_run_score(run)
    score_attribution = _claim_review_score_failure_attribution(run)
    labels = _verifier_attribution_labels(run)
    verifier_failure_count = _compact_positive_int(
        run.get("verifier_failure_attribution_count")
    )
    verifier_dependency_failure_count = _compact_positive_int(
        run.get("verifier_dependency_failure_count")
    )
    attribution_class = _verifier_attribution_class(
        score=score,
        score_attribution=score_attribution,
        labels=labels,
        verifier_failure_count=verifier_failure_count,
        verifier_dependency_failure_count=verifier_dependency_failure_count,
    )
    verifier_caveat = attribution_class in {
        "verifier_dependency_install_failure",
        "verifier_platform_probe_failure",
        "verifier_infrastructure_failure",
        "unattributed_score_failure",
        "missing_official_score",
    }
    caveat_resolved = attribution_class == "model_or_solution_failure"
    if attribution_class.startswith("verifier_"):
        next_action = (
            "keep attribution caveat; require same-protocol repeat or finer "
            "compact verifier evidence"
        )
    elif attribution_class == "unattributed_score_failure":
        next_action = (
            "keep attribution caveat; compact score failure is not yet attributed"
        )
    elif attribution_class == "missing_official_score":
        next_action = "wait for compact official score before attribution review"
    elif caveat_resolved:
        next_action = "claim caveat resolved by compact non-verifier failure attribution"
    else:
        next_action = "no score-failure caveat for this run"

    return {
        "mode": run.get("mode"),
        "job_name_present": bool(run.get("job_name")),
        "task_ids": [
            str(trial.get("task_id"))
            for trial in (
                run.get("trials") if isinstance(run.get("trials"), list) else []
            )
            if isinstance(trial, dict) and trial.get("task_id")
        ][:4],
        "official_score": score,
        "official_passed": bool(
            (run.get("official_task_score") or {}).get("passed")
        )
        if isinstance(run.get("official_task_score"), dict)
        else None,
        "score_failure_attribution": score_attribution,
        "failure_attribution_labels": labels,
        "verifier_failure_attribution_count": verifier_failure_count,
        "verifier_dependency_failure_count": verifier_dependency_failure_count,
        "validation_failed_checks": _compact_validation_failed_checks(run),
        "worker_submit_eligible_mismatch_count": _compact_positive_int(
            run.get("worker_submit_eligible_mismatch_count")
        ),
        "attribution_class": attribution_class,
        "verifier_caveat": verifier_caveat,
        "claim_caveat_resolved": caveat_resolved,
        "next_action": next_action,
    }


def build_benchmark_verifier_attribution_review(
    *,
    benchmark_runs: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Classify compact verifier attribution without opening raw verifier logs."""

    runs = [run for run in benchmark_runs if isinstance(run, dict)]
    baseline, _treatment = _claim_review_pick_runs(runs)
    run_reviews = [_verifier_attribution_run_review(run) for run in runs]
    baseline_index = 0
    if baseline is not None:
        for index, run in enumerate(runs):
            if run is baseline:
                baseline_index = index
                break
    baseline_review = run_reviews[baseline_index] if run_reviews else None

    blockers: list[str] = []
    if baseline_review is None:
        blockers.append("missing_compact_baseline_run")
    elif baseline_review["attribution_class"].startswith("verifier_"):
        blockers.append("baseline_verifier_attribution_caveat")
    elif baseline_review["attribution_class"] == "unattributed_score_failure":
        blockers.append("baseline_score_failure_unattributed")
    elif baseline_review["attribution_class"] == "missing_official_score":
        blockers.append("baseline_official_score_missing")
    elif _compact_positive_int(
        baseline_review.get("worker_submit_eligible_mismatch_count")
    ):
        blockers.append("baseline_submit_boundary_mismatch")

    baseline_caveat_resolved = bool(
        baseline_review
        and baseline_review.get("claim_caveat_resolved")
        and not blockers
    )
    if baseline_caveat_resolved:
        next_action = (
            "baseline compact verifier caveat resolved; rerun claim review "
            "before upgrading proof strength"
        )
    elif "baseline_verifier_attribution_caveat" in blockers:
        next_action = (
            "do not upgrade claim; run same-protocol repeat or collect finer "
            "compact verifier-side attribution"
        )
    elif "baseline_score_failure_unattributed" in blockers:
        next_action = (
            "do not upgrade claim; compact baseline score failure is unattributed"
        )
    elif "missing_compact_baseline_run" in blockers:
        next_action = "provide a compact benchmark_run_v0 for the baseline arm"
    else:
        next_action = "keep claim blocked until compact attribution blockers are resolved"

    return {
        "schema_version": BENCHMARK_VERIFIER_ATTRIBUTION_REVIEW_SCHEMA_VERSION,
        "input_schema_versions": {
            "benchmark_runs": [
                run.get("schema_version") for run in runs if run.get("schema_version")
            ],
        },
        "reviewed_run_count": len(run_reviews),
        "baseline_run_index": baseline_index if run_reviews else None,
        "run_reviews": run_reviews,
        "decision": {
            "baseline_claim_caveat_resolved": baseline_caveat_resolved,
            "clean_model_failure_attribution": baseline_caveat_resolved,
            "blockers": blockers,
            "next_action": next_action,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
    }


def build_terminal_bench_active_user_injection_channel_probe(
    *,
    active_cli_bridge_preflight: bool,
) -> dict[str, Any]:
    """Describe active-user treatment channels and remaining run blocker."""

    external_update_loop_available = bool(active_cli_bridge_preflight)
    checked_channels = [
        {
            "channel": "initial_prompt_instruction_append",
            "available": True,
            "verdict": "rejected_for_active_intervention",
            "reason": "initial prompt changes start state but cannot inject user messages during the worker run",
        },
        {
            "channel": "worker_goal_harness_cli_pull",
            "available": bool(active_cli_bridge_preflight),
            "verdict": "partial_worker_pull_not_user_push",
            "reason": "worker can query Goal Harness state, but the simulator cannot push a fresh user turn into the active Codex run",
        },
        {
            "channel": "audited_external_update_loop",
            "available": external_update_loop_available,
            "verdict": (
                "available_worker_pull_channel"
                if external_update_loop_available
                else "requires_active_worker_cli_bridge"
            ),
            "reason": "simulator can append a public-safe intervention feed and the worker can poll active-user-observe after start",
            "channel_surface": ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
            "contract_schema_version": ACTIVE_USER_INTERVENTION_CHANNEL_CONTRACT_VERSION,
        },
        {
            "channel": "interactive_worker_session_bridge",
            "available": False,
            "verdict": "optional_direct_chat_missing",
            "reason": "current Harbor custom agent surface invokes one Codex worker run through a single super-run instruction",
        },
    ]
    first_blocker = (
        TERMINAL_BENCH_ACTIVE_USER_REAL_WORKER_OBSERVATION_FIRST_BLOCKER
        if external_update_loop_available
        else TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_FIRST_BLOCKER
    )
    return {
        "schema_version": TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_CHANNEL_SCHEMA,
        "channel_available": external_update_loop_available,
        "first_blocker": first_blocker,
        "required_capability": "worker_observes_simulator_message_after_start",
        "current_agent_surface": (
            ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE
            if external_update_loop_available
            else "single_super_run_instruction_call"
        ),
        "direct_codex_chat_injection_available": False,
        "audited_external_update_loop_available": external_update_loop_available,
        "active_user_feed_jsonl": TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
        "active_user_observation_json": TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
        "initial_prompt_only_is_not_active_intervention": True,
        "no_user_message_injected": True,
        "model_api_invoked": False,
        "raw_transcript_recorded": False,
        "checked_channel_count": len(checked_channels),
        "checked_channels": checked_channels,
        "next_channel_requirement": "wire_worker_prompt_to_poll_active_user_observe_during_assisted_treatment",
        "minimum_next_implementation": "run a worker sample that observes a post-start active-user intervention",
    }


def build_terminal_bench_active_user_observation_fixture() -> dict[str, Any]:
    """Build the deterministic worker-observed active-user intervention fixture."""

    latest = build_active_user_intervention(
        seq=2,
        message="Run the focused public validation before broader edits.",
        trigger="public_progress_or_stall_signal",
        created_after_worker_start=True,
    )
    latest_summary = {
        "seq": latest["seq"],
        "channel": latest["channel"],
        "type": latest["type"],
        "trigger": latest["trigger"],
        "message": latest["message"],
        "oracle_free": latest["oracle_free"] is True,
        "hidden_tests_visible": latest["hidden_tests_visible"] is True,
        "expected_solution_visible": latest["expected_solution_visible"] is True,
        "credential_values_visible": latest["credential_values_visible"] is True,
        "private_material_visible": latest["private_material_visible"] is True,
    }
    return {
        "ok": True,
        "schema_version": ACTIVE_USER_INTERVENTION_OBSERVATION_VERSION,
        "bridge_surface": WORKER_BRIDGE_SURFACE,
        "channel_surface": ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
        "feed_present": True,
        "feed_path_recorded": False,
        "worker_start_seq": 1,
        "valid_intervention_count": 2,
        "invalid_line_count": 0,
        "observed_after_worker_start": True,
        "observed_intervention_count": 1,
        "latest_intervention": latest_summary,
        "worker_observation_proof": True,
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "leaderboard_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "direct_codex_chat_injection": False,
            "worker_pull_channel": True,
        },
        "public_boundary": {
            "raw_paths_recorded": False,
            "raw_transcript_recorded": False,
            "credential_values_recorded": False,
        },
        "next_action": "run a real assisted worker sample or append a compact blocker",
    }


TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES = (
    "CODEX_FORCE_AUTH_JSON",
    "OPENAI_API_KEY",
)
TERMINAL_BENCH_BOOL_AGENT_ENV_NAMES = frozenset({"CODEX_FORCE_AUTH_JSON"})
TERMINAL_BENCH_BOOL_AGENT_ENV_VALUES = frozenset(
    {"true", "false", "1", "0", "yes", "no"}
)
TERMINAL_BENCH_REDACTED_ENV_VALUE_MARKERS = frozenset(
    {"****", "<redacted>", "redacted", "[redacted]", "__redacted__"}
)
TERMINAL_BENCH_EXTRA_PROBE_PATHS = (
    "~/.local/bin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
)
TERMINAL_BENCH_COUNTER_TRACE_FILE = "goal-harness-counter-trace.jsonl"
TERMINAL_BENCH_WORKER_BENCHMARK_RUN_FILE = "goal-harness-worker-benchmark-run.json"
TERMINAL_BENCH_DEFAULT_AGENT_TIMEOUT_SECONDS = 900.0
TERMINAL_BENCH_TRUE_LONG_TASK_BAR_SECONDS = 1800.0
TERMINAL_BENCH_PREFERRED_HOURS_SCALE_BAR_SECONDS = 3600.0
TERMINAL_BENCH_OFFICIAL_TIMEOUT_MULTIPLIER = 1.0
TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_TIMEOUT_MULTIPLIER = 4.0
TERMINAL_BENCH_EPISODE_POLICY_VERSION = (
    "terminal_bench_single_agent_resumable_episode_policy_v0"
)
TERMINAL_BENCH_EPISODE_POLICY_MODE = (
    "single_codex_agent_goal_harness_assisted_checkpoints"
)
TERMINAL_BENCH_DEFAULT_EPISODE_CHECKPOINT_INTERVAL_SECONDS = 600
TERMINAL_BENCH_TIMEOUT_MULTIPLIER_KEYS = (
    "timeout_multiplier",
    "agent_timeout_multiplier",
    "verifier_timeout_multiplier",
    "agent_setup_timeout_multiplier",
    "environment_build_timeout_multiplier",
)
TERMINAL_BENCH_VERIFIER_FAILURE_LOG_FILES = (
    "test-stdout.txt",
    "test-stderr.txt",
    "test-output.txt",
    "stdout.txt",
    "stderr.txt",
    "output.txt",
)
TERMINAL_BENCH_VERIFIER_FAILURE_GLOB_PATTERNS = (
    "test*.txt",
    "*stdout*.txt",
    "*stderr*.txt",
    "*output*.txt",
)
TERMINAL_BENCH_CODEX_RUNTIME_GOAL_TOOL_NAMES = (
    "create_goal",
    "update_goal",
)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for raw_line in raw_lines:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            parsed = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _empty_codex_runtime_goal_tool_calls() -> dict[str, int]:
    return {name: 0 for name in TERMINAL_BENCH_CODEX_RUNTIME_GOAL_TOOL_NAMES}


def _merge_numeric_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        if isinstance(value, int) and not isinstance(value, bool):
            target[key] = target.get(key, 0) + value


def _compact_trace_event_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _trajectory_codex_runtime_goal_tool_calls(path: Path) -> dict[str, int]:
    """Count Codex runtime goal tools from ATIF trajectory without recording trace text."""

    calls = _empty_codex_runtime_goal_tool_calls()
    trajectory = _load_json_object(path)
    steps = trajectory.get("steps")
    if not isinstance(steps, list):
        return calls

    for step in steps:
        if not isinstance(step, dict):
            continue
        tool_calls = step.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function_name = tool_call.get("function_name") or tool_call.get("name")
            function = tool_call.get("function")
            if not isinstance(function_name, str) and isinstance(function, dict):
                function_name = function.get("name")
            if function_name in calls:
                calls[function_name] += 1

    return calls


def _terminal_bench_verifier_failure_attribution(trial_dir: Path) -> dict[str, Any] | None:
    """Classify verifier-side infrastructure failures without recording raw logs."""

    verifier_dir = trial_dir / "verifier"
    if not verifier_dir.exists():
        return None

    log_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for file_name in TERMINAL_BENCH_VERIFIER_FAILURE_LOG_FILES:
        path = verifier_dir / file_name
        if path.exists() and path not in seen_paths:
            log_paths.append(path)
            seen_paths.add(path)
    for pattern in TERMINAL_BENCH_VERIFIER_FAILURE_GLOB_PATTERNS:
        for path in sorted(verifier_dir.glob(pattern)):
            if path.is_file() and path not in seen_paths:
                log_paths.append(path)
                seen_paths.add(path)

    snippets: list[str] = []
    for path in log_paths[:8]:
        try:
            snippets.append(path.read_text(encoding="utf-8", errors="replace")[:12000])
        except OSError:
            continue
    text = "\n".join(snippets).lower()
    if not text:
        return None

    labels: set[str] = set()
    if "failed to download" in text:
        labels.add("verifier_dependency_download_failure")
    if "curl:" in text or "http/2 stream" in text:
        labels.add("verifier_network_transfer_failure")
    if "uv: command not found" in text or "uv-x86_64" in text:
        labels.add("verifier_uv_install_or_download_failure")
    if "command not found" in text or "no such file or directory" in text:
        labels.add("verifier_dependency_command_missing")
    if "unknown platform bitness" in text:
        labels.add("verifier_platform_probe_failure")
    if labels & {
        "verifier_dependency_download_failure",
        "verifier_uv_install_or_download_failure",
        "verifier_dependency_command_missing",
    }:
        labels.add("verifier_dependency_install_failure")
    if not labels:
        return None

    return {
        "schema_version": "terminal_bench_verifier_failure_attribution_v0",
        "classification": "verifier_dependency_install_failure"
        if "verifier_dependency_install_failure" in labels
        else "verifier_infrastructure_failure",
        "labels": sorted(labels),
        "log_probe_file_count": len(log_paths),
        "raw_log_recorded": False,
    }


def _terminal_bench_score_failure_attribution(
    *,
    official_score: Any,
    verifier_dependency_failure_count: int,
    failure_attribution_labels: set[str],
) -> str:
    """Summarize score-failure cause without collapsing verifier probes to none."""

    if official_score != 0:
        return "none"
    if verifier_dependency_failure_count:
        return "verifier_dependency_install_failure"
    if "verifier_platform_probe_failure" in failure_attribution_labels:
        return "verifier_platform_probe_failure"
    if any(label.startswith("verifier_") for label in failure_attribution_labels):
        return "verifier_infrastructure_failure"
    return "none"


def _is_pre_worker_agent_setup_failure(
    *,
    trial_dir: Path,
    exception_type: Any,
    trial_agent_result: dict[str, Any],
    trace_path: Path,
    worker_benchmark_run_path: Path,
) -> bool:
    """Detect failures that happen before the custom worker agent starts."""

    if exception_type != "NonZeroAgentExitCodeError":
        return False
    if trial_agent_result:
        return False
    agent_dir = trial_dir / "agent"
    return (
        (agent_dir / "setup").exists()
        and not (agent_dir / "trajectory.json").exists()
        and not trace_path.exists()
        and not worker_benchmark_run_path.exists()
    )


def _is_compactable_benchmark_run_v0(payload: dict[str, Any]) -> bool:
    """Return true for payload shapes accepted by history append-benchmark-run."""

    if payload.get("schema_version") == "benchmark_run_v0":
        return True
    nested = payload.get("benchmark_run")
    return (
        isinstance(nested, dict)
        and nested.get("schema_version") == "benchmark_run_v0"
    )


def _invocation_arg_value(invocation: list[Any], flag: str) -> str | None:
    for index, value in enumerate(invocation):
        if value == flag and index + 1 < len(invocation):
            next_value = invocation[index + 1]
            if isinstance(next_value, str):
                return next_value
    return None


def _redacted_agent_kwargs(agent_config: dict[str, Any]) -> dict[str, Any]:
    kwargs = agent_config.get("kwargs") if isinstance(agent_config.get("kwargs"), dict) else {}
    return {
        "name": agent_config.get("name"),
        "import_path": agent_config.get("import_path"),
        "model": agent_config.get("model_name"),
        "kwargs_keys": sorted(str(key) for key in kwargs.keys()),
    }


def _numeric_metric_totals(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_tokens": source.get("n_input_tokens"),
        "cache_tokens": source.get("n_cache_tokens"),
        "output_tokens": source.get("n_output_tokens"),
        "cost_usd": source.get("cost_usd"),
    }


def _reward_from_trial_result(trial: dict[str, Any], trial_dir: Path) -> dict[str, Any]:
    rewards = ((trial.get("verifier_result") or {}).get("rewards")) or {}
    if isinstance(rewards, dict) and rewards:
        return rewards
    reward_json = _load_json_object(trial_dir / "verifier" / "reward.json")
    if reward_json:
        return reward_json
    reward_text = trial_dir / "verifier" / "reward.txt"
    try:
        raw_reward = reward_text.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    try:
        return {"reward": float(raw_reward)}
    except ValueError:
        return {}


def _first_numeric_reward(trials: list[dict[str, Any]]) -> float | int | None:
    for trial in trials:
        reward = trial.get("reward") if isinstance(trial.get("reward"), dict) else {}
        for value in reward.values():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
    return None


def _official_score_from_harbor_stats(stats: dict[str, Any]) -> float | int | None:
    evals = stats.get("evals") if isinstance(stats.get("evals"), dict) else {}
    for eval_result in evals.values():
        if not isinstance(eval_result, dict):
            continue
        metrics = eval_result.get("metrics")
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            mean = metric.get("mean")
            if isinstance(mean, (int, float)) and not isinstance(mean, bool):
                return mean
    for key in ("mean_reward", "reward_mean", "mean"):
        value = stats.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def _numeric_reward_value(rewards: dict[str, Any]) -> float | int | None:
    for value in rewards.values():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def _iso_duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if finish.tzinfo is None:
        finish = finish.replace(tzinfo=timezone.utc)
    return max(0.0, (finish - start).total_seconds())


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _first_timeout_multiplier(
    sources: list[dict[str, Any]],
    key: str,
) -> float | None:
    for source in sources:
        if not isinstance(source, dict) or key not in source:
            continue
        parsed = _optional_float(source.get(key))
        if parsed is not None:
            return parsed
    return None


def _is_default_timeout_multiplier(value: float | None) -> bool:
    return value is None or abs(value - TERMINAL_BENCH_OFFICIAL_TIMEOUT_MULTIPLIER) < 1e-9


def _format_harbor_multiplier(value: float) -> str:
    return f"{value:g}"


def _terminal_bench_dataset_args(dataset: str) -> list[str]:
    if dataset.startswith(("/", "./", "../", "~")) or Path(dataset).exists():
        return ["--path", dataset]
    return ["--dataset", dataset]


def _public_safe_benchmark_label(value: Any, *, limit: int = 120) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.strip().split())
    if not text or "/" in text or "\\" in text:
        return None
    return text[:limit]


def _agents_last_exam_public_id(value: Any, *, limit: int = 140) -> str | None:
    """Return a public-safe ALE id without preserving host paths or task bodies."""

    if not isinstance(value, str):
        return None
    text = value.strip().replace("\\", "/")
    if not text or text.startswith("/") or text.startswith("~"):
        return None
    parts = [part for part in text.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    cleaned = []
    for char in "__".join(parts):
        cleaned.append(char.lower() if char.isalnum() or char in {"-", "_", "."} else "-")
    label = "".join(cleaned).strip("-_.")
    while "--" in label:
        label = label.replace("--", "-")
    return (label or None)[:limit]


def _agents_last_exam_first_public_id(*values: Any, default: str) -> str:
    for value in values:
        label = _agents_last_exam_public_id(value)
        if label:
            return label
    return default


def _agents_last_exam_event_type_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        event_type = _agents_last_exam_public_id(
            row.get("type") or row.get("event_type") or row.get("event"),
            limit=80,
        )
        if not event_type:
            continue
        counts[event_type] = counts.get(event_type, 0) + 1
    return dict(sorted(counts.items())[:10])


def _agents_last_exam_nested(source: dict[str, Any], field: str) -> Any:
    value = source.get(field)
    if value is not None:
        return value
    unit = source.get("unit") if isinstance(source.get("unit"), dict) else {}
    value = unit.get(field)
    if value is not None:
        return value
    meta = source.get("meta") if isinstance(source.get("meta"), dict) else {}
    return meta.get(field)


def build_agents_last_exam_result_benchmark_report(
    run_dir: str | Path,
    *,
    report_id: str | None = None,
    harness_identity: str = "goal-harness-meta",
    runner_source: str = "ale_run_run_writer_v2",
    harness_policy_version: str = AGENTS_LAST_EXAM_RESULT_INGEST_POLICY_VERSION,
    trace_publicness: str = AGENTS_LAST_EXAM_TRACE_PUBLICNESS,
) -> dict[str, Any]:
    """Compact an ALE run directory into benchmark_experiment_report_v0.

    The compactor reads only ALE's compact top-level files: ``run.json``,
    ``eval_result.json``, and ``events.jsonl``. It deliberately does not read or
    record ``trajectory.json``, ``origin_log/``, ``output/``, task bodies,
    screenshots, credential values, or local absolute paths.
    """

    path = Path(run_dir)
    run_json = _load_json_object(path / "run.json")
    eval_result = _load_json_object(path / "eval_result.json")
    events = _load_jsonl_objects(path / "events.jsonl")
    score = _optional_float(eval_result.get("score"))
    eval_status = _agents_last_exam_public_id(eval_result.get("eval_status"), limit=80)
    run_status = _agents_last_exam_public_id(
        _agents_last_exam_nested(run_json, "status"),
        limit=80,
    )
    task_label = _agents_last_exam_first_public_id(
        _agents_last_exam_nested(run_json, "task_path"),
        _agents_last_exam_nested(run_json, "task_id"),
        _agents_last_exam_nested(run_json, "task"),
        default="unknown_task",
    )
    agent_label = _agents_last_exam_first_public_id(
        _agents_last_exam_nested(run_json, "agent_id"),
        _agents_last_exam_nested(run_json, "agent"),
        default="unknown_agent",
    )
    model_label = _agents_last_exam_first_public_id(
        _agents_last_exam_nested(run_json, "model"),
        default="unknown_model",
    )
    run_id = _agents_last_exam_public_id(
        run_json.get("run_id") or path.name,
        limit=160,
    ) or "unknown_run"
    report_label = (
        _agents_last_exam_public_id(report_id, limit=160)
        if report_id
        else f"{AGENTS_LAST_EXAM_BENCHMARK_ID}-{run_id}"
    )
    event_counts = _agents_last_exam_event_type_counts(events)
    error = eval_result.get("error") if isinstance(eval_result.get("error"), dict) else {}
    error_type = _agents_last_exam_public_id(
        error.get("type") or error.get("exception_type") or error.get("class"),
        limit=80,
    )
    duration_s = _optional_float(
        run_json.get("duration_s")
        or run_json.get("elapsed_s")
        or _agents_last_exam_nested(run_json, "duration_s")
    )
    eval_duration_s = _optional_float(eval_result.get("eval_duration_s"))
    raw_surface_presence = {
        "trajectory_json_present": (path / "trajectory.json").exists(),
        "origin_log_dir_present": (path / "origin_log").exists(),
        "output_dir_present": (path / "output").exists(),
    }
    run_json_present = bool(run_json)
    eval_result_present = bool(eval_result)
    events_jsonl_present = (path / "events.jsonl").exists()
    completed = eval_status in {"passed", "completed", "success", "ok"} or (
        score is not None and not error_type
    )
    source_events = [
        "ale run.json parsed" if run_json_present else "ale run.json missing",
        "ale eval_result.json parsed" if eval_result_present else "ale eval_result.json missing",
        "ale events.jsonl counted" if events_jsonl_present else "ale events.jsonl missing",
        "raw ALE trajectory/origin_log/output excluded",
    ]
    negative_layers = ["single_arm_no_delta", "raw_surfaces_excluded"]
    if not run_json_present:
        negative_layers.append("run_json_missing")
    if not eval_result_present:
        negative_layers.append("eval_result_missing")
    if error_type:
        negative_layers.append("eval_error_present")

    return {
        "schema_version": "benchmark_experiment_report_v0",
        "experiment_identity": {
            "report_id": report_label,
            "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
            "task_slice": task_label,
            "worker_surface": "ale_run_compact_result_ingest",
            "harness_identity": harness_identity,
            "harness_policy_version": harness_policy_version,
            "trace_publicness": trace_publicness,
        },
        "official_score": {
            "kind": "ale_eval_result" if score is not None else "ale_eval_result_missing",
            "task_id_or_split": task_label,
            "runner_source": runner_source,
            "native_score": score if score is not None else 0.0,
            "wrapped_score": score if score is not None else 0.0,
            "delta": 0.0,
            "repetitions": 1 if eval_result_present else 0,
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
        "passive_control_plane_score": {
            "restartability": 1.0 if run_json_present and events_jsonl_present else 0.5,
            "stale_state_avoidance": 1.0,
            "evidence_discipline": 1.0,
            "writeback_quality": 1.0 if eval_result_present else 0.5,
            "failure_attribution": 1.0 if error_type or completed else 0.5,
            "overhead_bounded": True,
            "regression_avoidance_passed": True,
            "source_events": source_events,
        },
        "operator_simulator_ablation": {
            "enabled": False,
            "leaderboard_evidence": False,
            "intervention_count": 0,
            "reason": "ALE compact result ingest is passive; simulator evidence must be a separate treatment layer.",
        },
        "cost_latency_overhead": {
            "duration_s": duration_s,
            "eval_duration_s": eval_duration_s,
            "event_count": len(events),
            "event_type_counts": event_counts,
            "raw_trace_recorded": False,
            "raw_output_recorded": False,
        },
        "failure_taxonomy": {
            "run_status": run_status or "unknown",
            "eval_status": eval_status or "unknown",
            "error_type": error_type or "none",
            "score_missing": score is None,
            "single_arm_no_delta": True,
        },
        "reproducibility_artifacts": {
            "run_json_present": run_json_present,
            "eval_result_json_present": eval_result_present,
            "events_jsonl_present": events_jsonl_present,
            "event_count": len(events),
            "event_type_counts": event_counts,
            "agent_id": agent_label,
            "model": model_label,
            "task_id": task_label,
            "raw_surfaces_excluded": list(AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED),
            "raw_surface_presence_checked": raw_surface_presence,
            "raw_surface_content_recorded": False,
            "local_paths_recorded": False,
            "credential_values_recorded": False,
        },
        "claim_boundary": {
            "may_claim": [
                "ALE compact run/eval/events artifacts can be reduced to benchmark_experiment_report_v0",
                "Raw trajectory, origin logs, outputs, task bodies, screenshots, credentials, and local paths are excluded",
                "The report is a single-arm compact ingest artifact, not a paired treatment comparison",
            ],
            "must_not_claim": [
                "ALE leaderboard evidence",
                "Goal Harness treatment advantage",
                "baseline-versus-treatment score delta",
                "task solution quality from raw trajectory or outputs",
            ],
            "source_decision_note_schema": "agents_last_exam_result_ingest_contract_v0",
            "source_evidence_layer": "compact_run_eval_events_only",
        },
        "negative_results": {
            "null_official_delta": True,
            "failed_hypothesis_count": 0,
            "negative_evidence_layers": negative_layers,
            "overhead_regression_count": 0,
        },
        "next_decision": {
            "decision": "wire_ale_report_append_or_authorize_no_upload_dry_run",
            "minimum_next_evidence": "Append a synthetic ALE compact report through history, or run an operator-approved no-upload ALE dry-run without reading task bodies.",
            "stop_condition": "Stop before GCP setup, VM launch, model API use, paid compute, output upload, leaderboard submission, hidden refs, task solutions, task body copying, raw trajectories, screenshots, local absolute paths, credential values, or production actions.",
            "source_decision_note_schema": "benchmark_experiment_report_v0",
            "readiness_decision": "compact_ingest_ready",
            "failure_decision": "do_not_infer_pairwise_uplift_from_single_arm_ingest",
        },
        "section_count": 10,
    }


def build_terminal_bench_single_agent_episode_policy(
    *,
    active_cli_bridge: bool = False,
    checkpoint_interval_seconds: int = (
        TERMINAL_BENCH_DEFAULT_EPISODE_CHECKPOINT_INTERVAL_SECONDS
    ),
    runner_side_guaranteed_writeback: bool = True,
) -> dict[str, Any]:
    """Describe the long-run policy without turning the task into multi-agent work."""

    return {
        "schema_version": TERMINAL_BENCH_EPISODE_POLICY_VERSION,
        "mode": TERMINAL_BENCH_EPISODE_POLICY_MODE,
        "worker_topology": "single_codex_agent",
        "goal_harness_role": "assist_checkpoint_context_quota_and_compact_evidence",
        "runner_role": "schedule_same_agent_episode_and_archive_final_outcome",
        "checkpoint_surface": (
            "worker_goal_harness_cli_bridge_compact_jsonl"
            if active_cli_bridge
            else "runner_side_compact_benchmark_run"
        ),
        "checkpoint_interval_seconds": int(checkpoint_interval_seconds),
        "resumable_episode_style": "codex_automation_like_same_agent_checkpoints",
        "runner_side_guaranteed_writeback": bool(runner_side_guaranteed_writeback),
        "does_not_spawn_additional_agents": True,
        "does_not_split_task_prompt": True,
        "does_not_change_task_solution_actor": True,
        "raw_trace_recorded": False,
    }


def _terminal_bench_timeout_policy(
    *,
    timeout_sources: list[dict[str, Any]],
    wall_time_seconds: float | None,
    agent_timeout_observed: bool,
) -> dict[str, Any]:
    timeout_multiplier = (
        _first_timeout_multiplier(timeout_sources, "timeout_multiplier")
        or TERMINAL_BENCH_OFFICIAL_TIMEOUT_MULTIPLIER
    )
    agent_timeout_multiplier = _first_timeout_multiplier(
        timeout_sources,
        "agent_timeout_multiplier",
    )
    verifier_timeout_multiplier = _first_timeout_multiplier(
        timeout_sources,
        "verifier_timeout_multiplier",
    )
    agent_setup_timeout_multiplier = _first_timeout_multiplier(
        timeout_sources,
        "agent_setup_timeout_multiplier",
    )
    environment_build_timeout_multiplier = _first_timeout_multiplier(
        timeout_sources,
        "environment_build_timeout_multiplier",
    )
    effective_agent_multiplier = agent_timeout_multiplier or timeout_multiplier
    changes_official_benchmark_timeout = any(
        not _is_default_timeout_multiplier(value)
        for value in (
            timeout_multiplier,
            agent_timeout_multiplier,
            verifier_timeout_multiplier,
            agent_setup_timeout_multiplier,
            environment_build_timeout_multiplier,
        )
    )
    if not changes_official_benchmark_timeout:
        timeout_tier = "official_default_agent_timeout_900s"
    elif not _is_default_timeout_multiplier(agent_timeout_multiplier):
        timeout_tier = "private_extended_timeout_agent_multiplier"
    elif not _is_default_timeout_multiplier(timeout_multiplier):
        timeout_tier = "private_extended_timeout_global_multiplier"
    else:
        timeout_tier = "private_extended_timeout_component_multiplier"

    wall_time_limit_seconds = (
        TERMINAL_BENCH_DEFAULT_AGENT_TIMEOUT_SECONDS * effective_agent_multiplier
    )
    observed_true_long_task_bar_met = (
        wall_time_seconds is not None
        and wall_time_seconds >= TERMINAL_BENCH_TRUE_LONG_TASK_BAR_SECONDS
    )
    expected_true_long_task_bar_met = (
        wall_time_limit_seconds >= TERMINAL_BENCH_TRUE_LONG_TASK_BAR_SECONDS
    )
    expected_hours_scale_bar_met = (
        wall_time_limit_seconds >= TERMINAL_BENCH_PREFERRED_HOURS_SCALE_BAR_SECONDS
    )

    return {
        "schema_version": "benchmark_runner_wall_time_policy_v0",
        "kind": "harbor_agent_phase_timeout_observed"
        if agent_timeout_observed
        else "harbor_runner_completed",
        "timeout_tier": timeout_tier,
        "interrupt_reason": "AgentTimeoutError" if agent_timeout_observed else "none",
        "interrupted": agent_timeout_observed,
        "changes_official_benchmark_timeout": changes_official_benchmark_timeout,
        "changes_official_task_resources": False,
        "official_timeout_comparable": not changes_official_benchmark_timeout,
        "leaderboard_claim_allowed": False,
        "wall_time_seconds": wall_time_seconds,
        "wall_time_limit_seconds": wall_time_limit_seconds,
        "true_long_task_bar_seconds": TERMINAL_BENCH_TRUE_LONG_TASK_BAR_SECONDS,
        "preferred_hours_scale_bar_seconds": (
            TERMINAL_BENCH_PREFERRED_HOURS_SCALE_BAR_SECONDS
        ),
        "observed_true_long_task_bar_met": observed_true_long_task_bar_met,
        "expected_true_long_task_bar_met": expected_true_long_task_bar_met,
        "true_long_task_bar_met": (
            observed_true_long_task_bar_met or expected_true_long_task_bar_met
        ),
        "expected_hours_scale_bar_met": expected_hours_scale_bar_met,
        "timeout_multipliers": {
            "timeout_multiplier": timeout_multiplier,
            "agent_timeout_multiplier": agent_timeout_multiplier,
            "verifier_timeout_multiplier": verifier_timeout_multiplier,
            "agent_setup_timeout_multiplier": agent_setup_timeout_multiplier,
            "environment_build_timeout_multiplier": environment_build_timeout_multiplier,
        },
    }


def _counter_trace_interaction_counters(
    rows: list[dict[str, Any]],
    *,
    prompt_policy_injected: bool,
    harness_skill_or_packet_injected: bool,
    codex_runtime_goal_tool_calls: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    runtime_calls = _empty_codex_runtime_goal_tool_calls()
    _merge_numeric_counts(runtime_calls, codex_runtime_goal_tool_calls or {})
    if not rows and not any(runtime_calls.values()):
        return None

    observed_calls = {
        command: 0 for command in TERMINAL_BENCH_GOAL_HARNESS_COUNTER_TRACE_COMMANDS
    }
    read_commands = {
        "status",
        "quota_should_run",
        "todo_list",
        "history",
        "check",
        TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND,
    }
    state_reads = 0
    state_writes = 0
    append_attempted = False
    append_dry_run_ok = False
    append_execute_ok = False
    append_schema_rejected = False
    append_success_count = 0
    append_schema_rejected_count = 0

    for row in rows:
        kind = _compact_trace_event_text(
            row.get("kind") or row.get("type") or row.get("event")
        )
        if kind == "codex_runtime_goal_tool_call":
            tool_name = _compact_trace_event_text(row.get("name") or row.get("tool"))
            if tool_name in runtime_calls:
                runtime_calls[tool_name] += 1
            continue
        command = row.get("command") or row.get("call")
        if not isinstance(command, str):
            continue
        if command in observed_calls:
            observed_calls[command] += 1
        if command in read_commands:
            state_reads += 1
        if command == "append_benchmark_run":
            append_attempted = True
            append_schema_rejected = append_schema_rejected or row.get("error_kind") in {
                "schema",
                "schema_rejected",
            }
            if row.get("error_kind") in {"schema", "schema_rejected"}:
                append_schema_rejected_count += 1
            row_succeeded = row.get("ok") is True or row.get("returncode") == 0
            if row_succeeded:
                append_success_count += 1
            if row_succeeded and row.get("dry_run") is not False:
                append_dry_run_ok = True
            elif row_succeeded:
                append_execute_ok = True
                state_writes += 1

    if not rows and any(runtime_calls.values()):
        case_result_writeback = "runner_side_guaranteed_writeback_no_worker_cli_bridge"
    elif append_execute_ok:
        case_result_writeback = "worker_bridge_append_benchmark_run_execute"
    elif append_dry_run_ok:
        case_result_writeback = "worker_bridge_append_benchmark_run_dry_run"
    elif append_schema_rejected:
        case_result_writeback = "worker_bridge_append_benchmark_run_schema_rejected"
    elif append_attempted:
        case_result_writeback = "worker_bridge_append_benchmark_run_failed"
    else:
        case_result_writeback = "not_observed_runner_loaded_worker_trace"

    counters = build_terminal_bench_goal_harness_interaction_counters(
        prompt_policy_injected=prompt_policy_injected,
        harness_skill_or_packet_injected=harness_skill_or_packet_injected,
        codex_runtime_goal_tool_calls=runtime_calls,
        goal_harness_cli_calls=observed_calls,
        goal_harness_state_reads=state_reads,
        goal_harness_state_writes=state_writes,
        case_result_writeback=case_result_writeback,
        counter_trust_level=(
            "runner_loaded_worker_counter_trace_and_codex_trajectory"
            if rows and any(runtime_calls.values())
            else "runner_loaded_worker_counter_trace"
            if rows
            else "runner_loaded_codex_trajectory_no_worker_trace"
        ),
    )
    counters["append_benchmark_run_success_count"] = append_success_count
    counters["append_benchmark_run_schema_rejected_count"] = (
        append_schema_rejected_count
    )
    return counters


def _total_from_counter_map(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = value.get("total")
    if isinstance(total, int) and not isinstance(total, bool):
        return total
    count = 0
    for key, raw in value.items():
        if key == "total":
            continue
        if isinstance(raw, int) and not isinstance(raw, bool):
            count += raw
    return count


def _terminal_bench_overhead_attribution_counters(
    *,
    metrics: dict[str, Any],
    wall_time_policy: dict[str, Any],
    interaction_counters: dict[str, Any] | None,
    trace_rows: list[dict[str, Any]],
    trials: list[dict[str, Any]],
    worker_bridge_required: bool,
    worker_counter_trace_trial_count: int,
    worker_benchmark_run_file_count: int,
    worker_benchmark_run_schema_ok_count: int,
    worker_submit_eligible_mismatch_count: int,
    worker_bridge_writeback_loss_count: int,
    pre_worker_agent_setup_failure_count: int,
    codex_runtime_goal_tool_trial_count: int,
    trace_publicness: str,
) -> dict[str, Any]:
    """Summarize overhead signals from compact artifacts only."""

    interaction_counters = interaction_counters or {}
    cli_calls = interaction_counters.get("goal_harness_cli_calls")
    codex_goal_tool_calls = interaction_counters.get("codex_runtime_goal_tool_calls")
    cli_call_total = _total_from_counter_map(cli_calls)
    codex_goal_tool_call_total = _total_from_counter_map(codex_goal_tool_calls)
    required_cli_call_total = 0
    optional_cli_call_total = 0
    if isinstance(cli_calls, dict):
        required_cli_call_total = sum(
            cli_calls.get(command, 0)
            for command in TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS
            if isinstance(cli_calls.get(command, 0), int)
            and not isinstance(cli_calls.get(command, 0), bool)
        )
        optional_cli_call_total = sum(
            cli_calls.get(command, 0)
            for command in TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS
            if isinstance(cli_calls.get(command, 0), int)
            and not isinstance(cli_calls.get(command, 0), bool)
        )

    if trace_rows:
        attribution_granularity = "coarse_worker_bridge_event_counts"
        worker_step_counter_status = (
            "worker_cli_counter_trace_present_no_phase_breakdown"
        )
    elif codex_goal_tool_call_total:
        attribution_granularity = "codex_runtime_goal_tool_counts_only"
        worker_step_counter_status = "runner_loaded_codex_trajectory_no_worker_trace"
    else:
        attribution_granularity = "runner_usage_and_wall_time_only"
        worker_step_counter_status = "no_worker_step_counters"

    errored_trial_count = sum(
        1 for trial in trials if trial.get("exception_type") not in (None, "none", "")
    )

    return {
        "schema_version": TERMINAL_BENCH_OVERHEAD_ATTRIBUTION_COUNTERS_VERSION,
        "source": "harbor_compact_runner_artifacts",
        "trace_publicness": trace_publicness,
        "attribution_granularity": attribution_granularity,
        "worker_step_counter_status": worker_step_counter_status,
        "attribution_caveat": "coarse_counts_only_no_raw_trace_or_phase_breakdown",
        "raw_logs_read": False,
        "raw_trace_recorded": False,
        "raw_task_prompt_recorded": False,
        "credential_values_recorded": False,
        "goal_harness_worker_cli_bridge_required": worker_bridge_required,
        "timeout_tier": wall_time_policy.get("timeout_tier"),
        "wall_time_seconds": wall_time_policy.get("wall_time_seconds"),
        "wall_time_limit_seconds": wall_time_policy.get("wall_time_limit_seconds"),
        "observed_true_long_task_bar_met": wall_time_policy.get(
            "observed_true_long_task_bar_met"
        ),
        "expected_hours_scale_bar_met": wall_time_policy.get(
            "expected_hours_scale_bar_met"
        ),
        "input_tokens": metrics.get("input_tokens"),
        "cache_tokens": metrics.get("cache_tokens"),
        "output_tokens": metrics.get("output_tokens"),
        "cost_usd": metrics.get("cost_usd"),
        "trial_count": len(trials),
        "errored_trial_count": errored_trial_count,
        "worker_bridge_event_count": len(trace_rows),
        "worker_counter_trace_trial_count": worker_counter_trace_trial_count,
        "worker_benchmark_run_file_count": worker_benchmark_run_file_count,
        "worker_benchmark_run_schema_ok_count": worker_benchmark_run_schema_ok_count,
        "worker_submit_eligible_mismatch_count": worker_submit_eligible_mismatch_count,
        "worker_submit_eligible_mismatch_reason": (
            "worker_file_submit_eligible_true_under_runner_no_upload_boundary"
            if worker_submit_eligible_mismatch_count
            else "none"
        ),
        "worker_bridge_writeback_loss_count": worker_bridge_writeback_loss_count,
        "pre_worker_agent_setup_failure_count": pre_worker_agent_setup_failure_count,
        "codex_runtime_goal_tool_trial_count": codex_runtime_goal_tool_trial_count,
        "goal_harness_cli_call_total": cli_call_total,
        "goal_harness_required_cli_call_total": required_cli_call_total,
        "goal_harness_optional_context_cli_call_total": optional_cli_call_total,
        "goal_harness_state_read_count": interaction_counters.get(
            "goal_harness_state_reads", 0
        ),
        "goal_harness_state_write_count": interaction_counters.get(
            "goal_harness_state_writes", 0
        ),
        "append_benchmark_run_success_count": interaction_counters.get(
            "append_benchmark_run_success_count", 0
        ),
        "append_benchmark_run_schema_rejected_count": interaction_counters.get(
            "append_benchmark_run_schema_rejected_count", 0
        ),
        "codex_runtime_goal_tool_call_total": codex_goal_tool_call_total,
        "goal_harness_cli_calls": cli_calls if isinstance(cli_calls, dict) else {},
        "codex_runtime_goal_tool_calls": (
            codex_goal_tool_calls if isinstance(codex_goal_tool_calls, dict) else {}
        ),
    }


def build_terminal_bench_harbor_result_benchmark_run(
    job_dir: str | Path,
    *,
    mode: str | None = None,
    trace_publicness: str = "compact_counts_only_no_raw_trace",
) -> dict[str, Any]:
    """Build a runner-side benchmark_run_v0 from Harbor job artifacts.

    This is the durable observer path: it reads Harbor's job/trial result files
    and compact worker counter artifacts after the case finishes. It never
    records raw task logs, raw Codex output, local paths, or credential values.
    """

    job_path = Path(job_dir)
    lock = _load_json_object(job_path / "lock.json")
    config = _load_json_object(job_path / "config.json")
    job_result = _load_json_object(job_path / "result.json")
    stats = job_result.get("stats") if isinstance(job_result.get("stats"), dict) else {}
    invocation = lock.get("invocation") if isinstance(lock.get("invocation"), list) else []
    no_upload_requested = "--upload" not in invocation and "upload" not in invocation
    lock_trials = lock.get("trials") if isinstance(lock.get("trials"), list) else []
    first_lock_trial = lock_trials[0] if lock_trials and isinstance(lock_trials[0], dict) else {}
    task_config = first_lock_trial.get("task") if isinstance(first_lock_trial.get("task"), dict) else {}
    agent_config = first_lock_trial.get("agent") if isinstance(first_lock_trial.get("agent"), dict) else {}
    agent_kwargs = agent_config.get("kwargs") if isinstance(agent_config.get("kwargs"), dict) else {}
    benchmark_id = _invocation_arg_value(invocation, "--dataset") or task_config.get("source") or "terminal-bench"
    agent_name = str(agent_config.get("name") or "")
    goal_harness_mode = str(agent_kwargs.get("goal_harness_mode") or "")
    goal_harness_access_packet_mode = str(
        agent_kwargs.get("goal_harness_access_packet_mode")
        or TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL
    )
    access_packet_enabled = (
        goal_harness_mode == "codex_goal_harness"
        and goal_harness_access_packet_mode
        != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    )
    hardened_codex_baseline = (
        goal_harness_mode in TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES
        and goal_harness_access_packet_mode
        == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    )
    worker_bridge_required = bool(
        agent_kwargs.get("goal_harness_cli_bridge_enabled") and access_packet_enabled
    )
    event_mode = (
        mode
        or goal_harness_mode
        or ("bare_codex_cli" if agent_name == "codex" else "harbor_observed")
    )
    if (
        event_mode == "codex_goal_harness"
        and goal_harness_access_packet_mode
        == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    ):
        event_mode = "codex_goal_harness_no_packet"
    if hardened_codex_baseline:
        event_mode = TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE
    timeout_sources = [config, first_lock_trial]
    required_worker_cli_call_min = (
        TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM
        if worker_bridge_required
        else 0
    )

    trials: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    codex_runtime_goal_tool_calls = _empty_codex_runtime_goal_tool_calls()
    codex_runtime_goal_tool_trial_count = 0
    worker_benchmark_run_written = False
    worker_counter_trace_trial_count = 0
    worker_benchmark_run_file_count = 0
    worker_benchmark_run_schema_ok_count = 0
    worker_submit_eligible_mismatch_count = 0
    pre_worker_agent_setup_failure_count = 0
    verifier_failure_attribution_count = 0
    verifier_dependency_failure_count = 0
    failure_attribution_labels: set[str] = set()
    agent_timeout_observed = False
    for trial_dir in sorted(path for path in job_path.iterdir() if path.is_dir()):
        trial_result_path = trial_dir / "result.json"
        if not trial_result_path.exists():
            continue
        trial = _load_json_object(trial_result_path)
        rewards = _reward_from_trial_result(trial, trial_dir)
        trial_config = trial.get("config") if isinstance(trial.get("config"), dict) else {}
        if trial_config:
            timeout_sources.append(trial_config)
        exception_info = trial.get("exception_info") if isinstance(trial.get("exception_info"), dict) else {}
        exception_type = exception_info.get("exception_type")
        if exception_type == "AgentTimeoutError":
            agent_timeout_observed = True
        trial_agent_result = trial.get("agent_result") if isinstance(trial.get("agent_result"), dict) else {}
        agent_dir = trial_dir / "agent"
        trace_path = agent_dir / TERMINAL_BENCH_COUNTER_TRACE_FILE
        trajectory_path = agent_dir / "trajectory.json"
        worker_benchmark_run_path = trial_dir / "agent" / TERMINAL_BENCH_WORKER_BENCHMARK_RUN_FILE
        pre_worker_agent_setup_failure = _is_pre_worker_agent_setup_failure(
            trial_dir=trial_dir,
            exception_type=exception_type,
            trial_agent_result=trial_agent_result,
            trace_path=trace_path,
            worker_benchmark_run_path=worker_benchmark_run_path,
        )
        if pre_worker_agent_setup_failure:
            pre_worker_agent_setup_failure_count += 1
        if trace_path.exists():
            worker_counter_trace_trial_count += 1
            trace_rows.extend(_load_jsonl_objects(trace_path))
        trajectory_goal_calls = _trajectory_codex_runtime_goal_tool_calls(
            trajectory_path
        )
        if any(trajectory_goal_calls.values()):
            codex_runtime_goal_tool_trial_count += 1
            _merge_numeric_counts(
                codex_runtime_goal_tool_calls,
                trajectory_goal_calls,
            )
        if worker_benchmark_run_path.exists():
            worker_benchmark_run_written = True
            worker_benchmark_run_file_count += 1
            worker_benchmark_run = _load_json_object(worker_benchmark_run_path)
            if _is_compactable_benchmark_run_v0(worker_benchmark_run):
                worker_benchmark_run_schema_ok_count += 1
                if (
                    no_upload_requested
                    and worker_benchmark_run.get("submit_eligible") is True
                ):
                    worker_submit_eligible_mismatch_count += 1
        trial_reward_value = _numeric_reward_value(rewards)
        verifier_attribution = (
            _terminal_bench_verifier_failure_attribution(trial_dir)
            if trial_reward_value is None or trial_reward_value == 0
            else None
        )
        if verifier_attribution:
            verifier_failure_attribution_count += 1
            labels = verifier_attribution.get("labels")
            if isinstance(labels, list):
                failure_attribution_labels.update(str(label) for label in labels)
            if verifier_attribution.get("classification") == "verifier_dependency_install_failure":
                verifier_dependency_failure_count += 1
        trial_payload = {
            "task_id": trial.get("task_name") or task_config.get("name") or task_config.get("path"),
            "trial_name": trial.get("trial_name"),
            "source": trial.get("source") or task_config.get("source"),
            "reward": rewards,
            "exception_type": exception_type or "none",
            "worker_start_status": (
                "pre_worker_agent_setup_failed"
                if pre_worker_agent_setup_failure
                else "worker_started_or_not_applicable"
            ),
            "metrics": _numeric_metric_totals(trial_agent_result),
            "trajectory_present": trajectory_path.exists(),
            "verifier_reward_present": bool(rewards)
            or (trial_dir / "verifier" / "reward.txt").exists()
            or (trial_dir / "verifier" / "reward.json").exists(),
            "artifact_manifest_present": (trial_dir / "artifacts" / "manifest.json").exists(),
            "trial_result_present": True,
        }
        if verifier_attribution:
            trial_payload["verifier_failure_attribution"] = verifier_attribution[
                "classification"
            ]
            trial_payload["verifier_failure_attribution_labels"] = (
                verifier_attribution["labels"]
            )
        trials.append(trial_payload)

    interaction_counters = _counter_trace_interaction_counters(
        trace_rows,
        prompt_policy_injected=bool(agent_kwargs) and not hardened_codex_baseline,
        harness_skill_or_packet_injected=bool(
            not hardened_codex_baseline
            and (
                agent_kwargs.get("goal_harness_cli_bridge_enabled")
                or agent_kwargs.get("goal_harness_mode")
            )
        ),
        codex_runtime_goal_tool_calls=codex_runtime_goal_tool_calls,
    )
    worker_cli_total = 0
    if interaction_counters:
        interaction_counters["worker_counter_trace_trial_count"] = (
            worker_counter_trace_trial_count
        )
        interaction_counters["worker_benchmark_run_file_count"] = (
            worker_benchmark_run_file_count
        )
        interaction_counters["worker_benchmark_run_schema_ok_count"] = (
            worker_benchmark_run_schema_ok_count
        )
        interaction_counters["worker_submit_eligible_mismatch_count"] = (
            worker_submit_eligible_mismatch_count
        )
        interaction_counters["pre_worker_agent_setup_failure_count"] = (
            pre_worker_agent_setup_failure_count
        )
        interaction_counters["codex_runtime_goal_tool_trial_count"] = (
            codex_runtime_goal_tool_trial_count
        )
        calls = interaction_counters.get("goal_harness_cli_calls")
        if isinstance(calls, dict) and isinstance(calls.get("total"), int):
            worker_cli_total = calls["total"]

    official_score = _official_score_from_harbor_stats(stats)
    official_score_source = "harbor_stats_eval_mean"
    if official_score is None:
        official_score = _first_numeric_reward(trials)
        official_score_source = "trial_reward_fallback"
    score_failure_attribution = _terminal_bench_score_failure_attribution(
        official_score=official_score,
        verifier_dependency_failure_count=verifier_dependency_failure_count,
        failure_attribution_labels=failure_attribution_labels,
    )
    runner_return_status = (
        "completed_with_agent_timeout"
        if agent_timeout_observed
        else "completed"
        if job_result.get("finished_at")
        else "pending"
    )
    official_score_status = "completed" if official_score is not None else "missing"
    worker_bridge_writeback_loss_count = (
        max(0, worker_counter_trace_trial_count - worker_benchmark_run_file_count)
        if worker_bridge_required
        else 0
    )
    if worker_bridge_writeback_loss_count and agent_timeout_observed:
        worker_bridge_writeback_loss_reason = (
            "agent_timeout_after_worker_trace_before_benchmark_run_writeback"
        )
    elif worker_bridge_writeback_loss_count:
        worker_bridge_writeback_loss_reason = (
            "worker_trace_without_benchmark_run_writeback"
        )
    else:
        worker_bridge_writeback_loss_reason = "none"
    worker_submit_eligible_mismatch_reason = (
        "worker_file_submit_eligible_true_under_runner_no_upload_boundary"
        if worker_submit_eligible_mismatch_count
        else "none"
    )
    if interaction_counters:
        interaction_counters["worker_bridge_writeback_loss_count"] = (
            worker_bridge_writeback_loss_count
        )
        interaction_counters["worker_bridge_writeback_loss_reason"] = (
            worker_bridge_writeback_loss_reason
        )
        interaction_counters["worker_submit_eligible_mismatch_reason"] = (
            worker_submit_eligible_mismatch_reason
        )
    wall_time_seconds = _iso_duration_seconds(
        job_result.get("started_at"),
        job_result.get("finished_at") or job_result.get("updated_at"),
    )
    wall_time_policy = _terminal_bench_timeout_policy(
        timeout_sources=timeout_sources,
        wall_time_seconds=wall_time_seconds,
        agent_timeout_observed=agent_timeout_observed,
    )
    metrics = _numeric_metric_totals(stats)
    overhead_attribution_counters = _terminal_bench_overhead_attribution_counters(
        metrics=metrics,
        wall_time_policy=wall_time_policy,
        interaction_counters=interaction_counters,
        trace_rows=trace_rows,
        trials=trials,
        worker_bridge_required=worker_bridge_required,
        worker_counter_trace_trial_count=worker_counter_trace_trial_count,
        worker_benchmark_run_file_count=worker_benchmark_run_file_count,
        worker_benchmark_run_schema_ok_count=worker_benchmark_run_schema_ok_count,
        worker_submit_eligible_mismatch_count=worker_submit_eligible_mismatch_count,
        worker_bridge_writeback_loss_count=worker_bridge_writeback_loss_count,
        pre_worker_agent_setup_failure_count=pre_worker_agent_setup_failure_count,
        codex_runtime_goal_tool_trial_count=codex_runtime_goal_tool_trial_count,
        trace_publicness=trace_publicness,
    )
    validation = {
        "job_lock_present": (job_path / "lock.json").exists(),
        "job_result_present": (job_path / "result.json").exists(),
        "trial_results_present": bool(trials)
        and len(trials) == (job_result.get("n_total_trials") or len(trials)),
        "verifier_reward_present": official_score is not None,
        "runner_completed_or_exception_recorded": bool(job_result.get("finished_at"))
        or bool(agent_timeout_observed),
        "worker_counter_trace_loaded": (not worker_bridge_required) or bool(trace_rows),
        "worker_benchmark_run_file_present": (
            (not worker_bridge_required) or worker_benchmark_run_written
        ),
        "worker_benchmark_run_schema_ok": (
            (not worker_bridge_required)
            or (
                worker_benchmark_run_file_count > 0
                and worker_benchmark_run_schema_ok_count == worker_benchmark_run_file_count
            )
        ),
        "worker_benchmark_run_present_for_traced_trials": (
            worker_benchmark_run_file_count >= worker_counter_trace_trial_count
        ),
        "worker_submit_eligible_matches_runner_boundary": (
            worker_submit_eligible_mismatch_count == 0
        ),
        "pre_worker_agent_setup_failures_classified": True,
        "verifier_failure_attribution_public_safe": True,
        "verifier_dependency_failures_classified": True,
        "worker_checkpoint_not_expected_before_agent_setup": True,
        "agent_timeout_recorded_if_present": not agent_timeout_observed
        or any(trial.get("exception_type") == "AgentTimeoutError" for trial in trials),
        "no_leaderboard_upload_requested": no_upload_requested,
        "paths_redacted": True,
        "raw_trace_excluded": True,
        "credential_values_not_recorded": True,
    }
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": benchmark_id,
        "job_name": config.get("job_name") or job_path.name,
        "mode": event_mode,
        "worker_mode": TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE
        if hardened_codex_baseline
        else "goal_harness_managed_codex"
        if agent_config.get("import_path") == TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH
        else agent_config.get("name")
        or "codex",
        "trace_publicness": trace_publicness,
        "real_run": True,
        "submit_eligible": False,
        "case_semantics_changed_by_harness": bool(goal_harness_mode)
        and not hardened_codex_baseline,
        "goal_harness_inside_case": bool(goal_harness_mode)
        and not hardened_codex_baseline,
        "official_score_comparable_to_native_codex": (
            not bool(goal_harness_mode) and not hardened_codex_baseline
        ),
        "official_score_comparable_to_goal_harness_treatment": hardened_codex_baseline,
        "model_plus_harness_pair": bool(goal_harness_mode)
        and not hardened_codex_baseline,
        "control_plane_score_applicable": bool(goal_harness_mode)
        and not hardened_codex_baseline,
        "startup_surface_calibration": False,
        "hardened_install_surface": hardened_codex_baseline,
        "hardened_install_baseline": hardened_codex_baseline,
        "leaderboard_evidence": False,
        "goal_harness_worker_cli_bridge_available": bool(
            worker_bridge_required
        ),
        "goal_harness_worker_cli_bridge_trace_observed": bool(trace_rows),
        "worker_goal_harness_cli_call_total": worker_cli_total,
        "worker_counter_trace_trial_count": worker_counter_trace_trial_count,
        "worker_benchmark_run_file_count": worker_benchmark_run_file_count,
        "worker_benchmark_run_schema_ok_count": worker_benchmark_run_schema_ok_count,
        "worker_submit_eligible_mismatch_count": worker_submit_eligible_mismatch_count,
        "worker_submit_eligible_mismatch_reason": worker_submit_eligible_mismatch_reason,
        "worker_bridge_writeback_loss_count": worker_bridge_writeback_loss_count,
        "worker_bridge_writeback_loss_reason": worker_bridge_writeback_loss_reason,
        "pre_worker_agent_setup_failure_count": pre_worker_agent_setup_failure_count,
        "verifier_failure_attribution_count": verifier_failure_attribution_count,
        "verifier_dependency_failure_count": verifier_dependency_failure_count,
        "failure_attribution_labels": sorted(failure_attribution_labels),
        "score_failure_attribution": score_failure_attribution,
        "required_worker_goal_harness_cli_call_total_min": required_worker_cli_call_min,
        "official_task_score": {
            "kind": "harbor_verifier_reward",
            "value": official_score,
            "passed": bool(
                isinstance(official_score, (int, float))
                and not isinstance(official_score, bool)
                and official_score >= 1.0
            ),
            "source": official_score_source,
        }
        if official_score is not None
        else {"kind": "harbor_verifier_reward_missing"},
        "agent": _redacted_agent_kwargs(agent_config),
        "progress": {
            "n_total_trials": job_result.get("n_total_trials"),
            "n_completed_trials": stats.get("n_completed_trials"),
            "n_errored_trials": stats.get("n_errored_trials"),
            "n_running_trials": stats.get("n_running_trials"),
            "n_pending_trials": stats.get("n_pending_trials"),
            "n_cancelled_trials": stats.get("n_cancelled_trials"),
            "n_retries": stats.get("n_retries"),
        },
        "metrics": metrics,
        "interaction_counters": interaction_counters,
        "overhead_attribution_counters": overhead_attribution_counters,
        "episode_policy": build_terminal_bench_single_agent_episode_policy(
            active_cli_bridge=worker_bridge_required,
            runner_side_guaranteed_writeback=True,
        ),
        "worker_bridge_outcome": {
            "schema_version": "worker_bridge_outcome_v0",
            "bridge_surface": (
                TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
                if worker_bridge_required
                else TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE
                if hardened_codex_baseline
                else "runner_only_no_worker_bridge"
                if goal_harness_mode == "codex_goal_harness"
                else "not_applicable_native_codex_baseline"
            ),
            "runner_return_status": runner_return_status,
            "official_score_status": official_score_status,
            "trace_publicness": trace_publicness,
            "next_action": (
                "prefer runner-side guaranteed append; optimize worker graceful closure before repeat"
                if worker_bridge_required
                else "compare hardened Codex baseline against Goal Harness treatment under the same no-upload boundary"
                if hardened_codex_baseline
                else "compare observed runner result against Goal Harness treatment under the same no-upload boundary"
            ),
            "worker_bridge_verified": bool(
                trace_rows
                and worker_cli_total >= required_worker_cli_call_min
            ),
            "counter_trace_present": bool(trace_rows),
            "runner_return_completed": bool(job_result.get("finished_at")),
            "official_score_completed": official_score is not None,
            "side_effect_audit_passed": True,
            "raw_paths_recorded": False,
            "raw_trace_recorded": False,
            "credential_values_recorded": False,
            "runner_side_writeback_guaranteed": True,
            "worker_bridge_writeback_loss_observed": bool(
                worker_bridge_writeback_loss_count
            ),
            "worker_submit_eligible_mismatch_observed": bool(
                worker_submit_eligible_mismatch_count
            ),
            "worker_submit_eligible_mismatch_count": worker_submit_eligible_mismatch_count,
            "worker_submit_eligible_mismatch_reason": worker_submit_eligible_mismatch_reason,
            "worker_bridge_writeback_loss_count": worker_bridge_writeback_loss_count,
            "worker_bridge_writeback_loss_reason": worker_bridge_writeback_loss_reason,
            "worker_goal_harness_cli_call_total": worker_cli_total,
            "required_worker_goal_harness_cli_call_total_min": required_worker_cli_call_min,
            "pre_worker_agent_setup_failure_count": pre_worker_agent_setup_failure_count,
            "verifier_failure_attribution_count": verifier_failure_attribution_count,
            "verifier_dependency_failure_count": verifier_dependency_failure_count,
            "failure_attribution_labels": sorted(failure_attribution_labels),
            "score_failure_attribution": score_failure_attribution,
            "official_score_value": official_score,
            "wall_time_policy": wall_time_policy,
        },
        "validation": validation,
        "trials": trials,
        "evidence_files": [
            "job:lock.json",
            "job:result.json",
            "trial:result.json",
            "trial:agent/trajectory.json",
            "trial:agent/goal-harness-counter-trace.jsonl",
            "trial:agent/goal-harness-worker-benchmark-run.json",
            "trial:verifier/reward.txt",
            "trial:artifacts/manifest.json",
        ],
        "resume_or_inspect_commands": [
            "harbor view <jobs-dir>",
            "goal-harness history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>",
        ],
        "stop_conditions": [
            "do_not_upload_or_submit_leaderboard",
            "do_not_record_raw_trace_or_paths",
            "do_not_claim_worker_clean_exit_when_runner_records_agent_timeout",
        ],
    }


def _probe_path() -> str:
    entries = [os.environ.get("PATH", "")]
    entries.extend(os.path.expanduser(path) for path in TERMINAL_BENCH_EXTRA_PROBE_PATHS)
    return os.pathsep.join(entry for entry in entries if entry)


def _probe_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = _probe_path()
    return env


def _looks_like_redacted_env_value(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in TERMINAL_BENCH_REDACTED_ENV_VALUE_MARKERS or (
        len(normalized) >= 3 and set(normalized) == {"*"}
    )


def _split_env_assignment(value: str) -> tuple[str, str] | None:
    if "=" not in value:
        return None
    name, raw_value = value.split("=", 1)
    if not name:
        return None
    return name, raw_value


def sanitize_terminal_bench_private_runner_env(
    env: dict[str, str],
) -> dict[str, str]:
    """Remove redacted auth placeholders before launching Harbor/Codex."""

    sanitized = dict(env)
    for name in TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES:
        value = sanitized.get(name)
        if isinstance(value, str) and _looks_like_redacted_env_value(value):
            sanitized.pop(name, None)
    return sanitized


def build_terminal_bench_private_runner_env() -> dict[str, str]:
    """Build the private local environment for a real Harbor runner launch."""

    return sanitize_terminal_bench_private_runner_env(_probe_env())


def _private_runner_goal_harness_project_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _private_runner_goal_harness_runtime_root() -> str:
    return str(Path("~/.codex/goal-harness").expanduser())


def _private_runner_active_user_host_dir() -> str:
    return str(Path("~/.codex/goal-harness/active-user-feeds").expanduser())


def _private_runner_command_kwargs(command_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Resolve worker-bridge placeholders only for a real private launch."""

    resolved = dict(command_kwargs)
    if not resolved.get("goal_harness_cli_bridge_enabled"):
        return resolved
    project_root = resolved.get("goal_harness_project_root")
    if not project_root or project_root == TERMINAL_BENCH_WORKER_BRIDGE_PROJECT_ROOT_PLACEHOLDER:
        resolved["goal_harness_project_root"] = _private_runner_goal_harness_project_root()
    runtime_root = resolved.get("goal_harness_runtime_root")
    if not runtime_root or runtime_root == TERMINAL_BENCH_WORKER_BRIDGE_RUNTIME_ROOT_PLACEHOLDER:
        resolved["goal_harness_runtime_root"] = _private_runner_goal_harness_runtime_root()
    active_user_host_dir = resolved.get("goal_harness_active_user_host_dir")
    if resolved.get("goal_harness_active_user_intervention_enabled") and (
        not active_user_host_dir
        or active_user_host_dir
        == TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_HOST_DIR_PLACEHOLDER
    ):
        resolved["goal_harness_active_user_host_dir"] = (
            _private_runner_active_user_host_dir()
        )
    return resolved


def build_terminal_bench_task_material_readiness(
    *,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str | None = TERMINAL_BENCH_DEFAULT_TASK,
    harbor_task_cache_root: str | Path | None = None,
) -> dict[str, Any]:
    """Return a public-safe readiness summary for selected task material.

    This deliberately checks only file presence, not task prompt contents. It is
    scoped to Terminal-Bench/Harbor launch safety: unknown or not-yet-cached
    material is reported as non-blocking, while cached material that is missing
    core files can block a private launch before spending a worker trial.
    """

    task_label = str(task_id or "")
    dataset_label = str(dataset or "")
    if not task_label:
        return {
            "schema_version": TERMINAL_BENCH_TASK_MATERIAL_READINESS_SCHEMA,
            "dataset": dataset_label,
            "task_id": "",
            "checked": False,
            "ready": None,
            "status": "not_checked_batch_or_no_task_selected",
            "first_blocker": "",
            "candidate_count": 0,
            "instruction_md_present_count": 0,
            "task_toml_present_count": 0,
            "raw_paths_recorded": False,
        }

    candidates: list[Path] = []
    dataset_path = Path(dataset_label).expanduser()
    if dataset_path.exists() and dataset_path.is_dir():
        local_candidate = dataset_path / task_label
        if local_candidate.exists() and local_candidate.is_dir():
            candidates.append(local_candidate)
    else:
        cache_root = Path(
            harbor_task_cache_root
            or os.environ.get("GOAL_HARNESS_HARBOR_TASK_CACHE_ROOT", "")
            or Path("~/.cache/harbor/tasks").expanduser()
        )
        if cache_root.exists() and cache_root.is_dir():
            candidates.extend(
                sorted(
                    path
                    for path in cache_root.glob(f"*/{task_label}")
                    if path.exists() and path.is_dir()
                )
            )

    instruction_count = sum(1 for path in candidates if (path / "instruction.md").exists())
    task_toml_count = sum(1 for path in candidates if (path / "task.toml").exists())
    if not candidates:
        status = "not_cached_or_not_locally_resolved"
        first_blocker = ""
        ready: bool | None = None
    elif instruction_count > 0 and task_toml_count > 0:
        status = "ready"
        first_blocker = ""
        ready = True
    elif instruction_count == 0:
        status = "missing_instruction_md"
        first_blocker = "task_material_missing_instruction_md"
        ready = False
    else:
        status = "missing_task_toml"
        first_blocker = "task_material_missing_task_toml"
        ready = False

    return {
        "schema_version": TERMINAL_BENCH_TASK_MATERIAL_READINESS_SCHEMA,
        "dataset": dataset_label,
        "task_id": task_label,
        "checked": bool(candidates),
        "ready": ready,
        "status": status,
        "first_blocker": first_blocker,
        "candidate_count": len(candidates),
        "instruction_md_present_count": instruction_count,
        "task_toml_present_count": task_toml_count,
        "raw_paths_recorded": False,
    }


def build_terminal_bench_private_runner_launch(**command_kwargs: Any) -> dict[str, Any]:
    """Build the real private Harbor launch argv together with its env.

    `build_terminal_bench_managed_harbor_command` returns only argv so docs and
    fixtures can show a safe command template. Real launches also need the
    Goal Harness probe PATH; otherwise non-interactive shells can miss Docker or
    uvx even when the preflight surface is ready.
    """

    env = build_terminal_bench_private_runner_env()
    resolved_command_kwargs = _private_runner_command_kwargs(command_kwargs)
    task_material_ready_required = bool(
        resolved_command_kwargs.pop("require_task_material_ready", False)
    )
    mode = str(
        resolved_command_kwargs.pop("mode", None)
        or resolved_command_kwargs.pop("runner_mode", None)
        or ""
    )
    if mode == "hardened-codex":
        resolved_command_kwargs.pop("goal_harness_mode", None)
        resolved_command_kwargs.pop("goal_harness_ablation_mode", None)
        resolved_command_kwargs.pop("goal_harness_access_packet_mode", None)
        resolved_command_kwargs.pop("goal_harness_cli_bridge_enabled", None)
        resolved_command_kwargs.setdefault(
            "job_name",
            "terminal_bench_hardened_codex_baseline",
        )
        argv = build_terminal_bench_managed_harbor_command(
            resolve_cli_paths=True,
            goal_harness_mode=TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE,
            goal_harness_ablation_mode="hardened_codex_baseline",
            goal_harness_access_packet_mode=TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE,
            goal_harness_cli_bridge_enabled=False,
            **resolved_command_kwargs,
        )
    elif mode in ("", "codex-goal-harness", "goal-harness-managed-codex"):
        if mode == "codex-goal-harness":
            resolved_command_kwargs.setdefault("goal_harness_mode", "codex_goal_harness")
            resolved_command_kwargs.setdefault(
                "job_name",
                "terminal_bench_codex_goal_harness_pilot",
            )
        elif mode == "goal-harness-managed-codex":
            resolved_command_kwargs.setdefault(
                "goal_harness_mode",
                "goal_harness_managed_codex",
            )
        argv = build_terminal_bench_managed_harbor_command(
            resolve_cli_paths=True,
            **resolved_command_kwargs,
        )
    else:
        raise ValueError(f"unsupported private runner launch mode: {mode}")
    surface = collect_terminal_bench_managed_preflight_surface(env=env)
    material_readiness = build_terminal_bench_task_material_readiness(
        dataset=str(resolved_command_kwargs.get("dataset", TERMINAL_BENCH_DEFAULT_DATASET)),
        task_id=resolved_command_kwargs.get("task_id", TERMINAL_BENCH_DEFAULT_TASK),
    )
    first_blocker = _managed_preflight_first_blocker(surface)
    if (
        first_blocker == "ready_for_private_managed_no_upload_pilot_review"
        and material_readiness.get("checked") is True
        and material_readiness.get("ready") is False
    ):
        first_blocker = str(material_readiness.get("first_blocker") or "task_material_not_ready")
    elif (
        first_blocker == "ready_for_private_managed_no_upload_pilot_review"
        and task_material_ready_required
        and material_readiness.get("ready") is not True
    ):
        status = str(material_readiness.get("status") or "not_ready")
        first_blocker = str(
            material_readiness.get("first_blocker") or f"task_material_{status}"
        )
    return {
        "schema_version": "terminal_bench_private_runner_launch_v0",
        "argv": argv,
        "env": env,
        "uses_private_runner_env": True,
        "preflight_surface": surface,
        "task_material_readiness": material_readiness,
        "task_material_ready_required": task_material_ready_required,
        "first_blocker": first_blocker,
        "ready": first_blocker == "ready_for_private_managed_no_upload_pilot_review",
    }


def summarize_terminal_bench_post_launch_materialization(
    jobs_dir: str | Path,
    *,
    job_name: str | None = None,
) -> dict[str, Any]:
    """Summarize whether Harbor produced a pollable job directory after launch.

    The summary intentionally records only booleans, counts, and optional job
    basenames. It does not read logs, task text, trajectories, or file contents,
    and it never echoes local paths.
    """

    jobs_dir_text = str(jobs_dir)
    public_job_name = Path(str(job_name)).name if job_name else ""
    placeholder = "<" in jobs_dir_text or ">" in jobs_dir_text
    summary: dict[str, Any] = {
        "schema_version": TERMINAL_BENCH_POST_LAUNCH_MATERIALIZATION_SCHEMA,
        "checked": not placeholder,
        "ready_for_launch_state": False,
        "ready_for_compact_result_ingest": False,
        "first_blocker": "jobs_dir_placeholder" if placeholder else "",
        "job_name": public_job_name,
        "jobs_dir_present": False,
        "job_root_present": False,
        "job_lock_present": False,
        "job_result_present": False,
        "trial_result_present_count": 0,
        "candidate_job_root_count": 0,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
    }
    if placeholder:
        return summary

    root = Path(jobs_dir).expanduser()
    jobs_dir_present = root.is_dir()
    summary["jobs_dir_present"] = jobs_dir_present
    if not jobs_dir_present:
        summary["first_blocker"] = "jobs_dir_missing"
        return summary

    if public_job_name:
        candidates = [root / public_job_name]
    else:
        candidates = [path for path in sorted(root.iterdir()) if path.is_dir()]
    existing_candidates = [path for path in candidates if path.is_dir()]
    summary["candidate_job_root_count"] = len(existing_candidates)
    if not existing_candidates:
        summary["first_blocker"] = "job_root_missing"
        return summary

    job_root = existing_candidates[0]
    lock_present = (job_root / "lock.json").is_file()
    result_present = (job_root / "result.json").is_file()
    trial_result_count = sum(
        1
        for child in job_root.iterdir()
        if child.is_dir() and (child / "result.json").is_file()
    )
    summary.update(
        {
            "job_root_present": True,
            "job_lock_present": lock_present,
            "job_result_present": result_present,
            "trial_result_present_count": trial_result_count,
            "ready_for_launch_state": lock_present,
            "ready_for_compact_result_ingest": (
                result_present and trial_result_count > 0
            ),
        }
    )
    if not lock_present:
        summary["first_blocker"] = "job_lock_missing"
    elif not result_present or trial_result_count <= 0:
        summary["first_blocker"] = "ready_for_compact_polling"
    else:
        summary["first_blocker"] = "ready_for_compact_result_ingest"
    return summary


def summarize_terminal_bench_private_runner_launch(
    launch: dict[str, Any],
    *,
    post_launch_materialization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a public-safe summary of a private Harbor launch contract."""

    env = launch.get("env") if isinstance(launch.get("env"), dict) else {}
    argv = launch.get("argv") if isinstance(launch.get("argv"), list) else []
    preflight_surface = (
        launch.get("preflight_surface")
        if isinstance(launch.get("preflight_surface"), dict)
        else {}
    )
    boundary = (
        preflight_surface.get("boundary")
        if isinstance(preflight_surface.get("boundary"), dict)
        else {}
    )
    task_material = (
        launch.get("task_material_readiness")
        if isinstance(launch.get("task_material_readiness"), dict)
        else {}
    )
    path_value = env.get("PATH") if isinstance(env.get("PATH"), str) else ""
    agent_name = _invocation_arg_value(argv, "--agent") or ""
    agent_import_path = _invocation_arg_value(argv, "--agent-import-path") or ""
    goal_harness_agent_kwargs_present = any(
        str(value).startswith("goal_harness_") for value in argv
    )
    mounts: list[Any] = []
    mounts_text = _invocation_arg_value(argv, "--mounts")
    if mounts_text:
        try:
            raw_mounts = json.loads(mounts_text)
        except json.JSONDecodeError:
            raw_mounts = []
        if isinstance(raw_mounts, list):
            mounts = raw_mounts
    active_user_mounts = [
        mount
        for mount in mounts
        if isinstance(mount, dict)
        and mount.get("target") == TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET
        and mount.get("read_only") is False
    ]
    probe_coverage = {
        "local_bin": str(Path("~/.local/bin").expanduser()) in path_value,
        "homebrew_bin": "/opt/homebrew/bin" in path_value,
        "usr_local_bin": "/usr/local/bin" in path_value,
    }
    auth_names_present = [
        name for name in TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES if name in env
    ]
    summary = {
        "schema_version": "terminal_bench_private_runner_launch_summary_v0",
        "launch_schema_version": str(launch.get("schema_version") or ""),
        "uses_private_runner_env": launch.get("uses_private_runner_env") is True,
        "ready": launch.get("ready") is True,
        "first_blocker": str(launch.get("first_blocker") or ""),
        "argv_present": bool(argv),
        "argv_binary_name": Path(str(argv[0])).name if argv else "",
        "argv_binary_resolved_for_private_launch": bool(argv and str(argv[0]) != "uvx"),
        "agent_name": agent_name,
        "agent_import_path_present": bool(agent_import_path),
        "goal_harness_agent_kwargs_present": goal_harness_agent_kwargs_present,
        "goal_harness_worker_bridge_requested": "goal_harness_cli_bridge_enabled=true"
        in argv,
        "active_user_writable_mount_requested": bool(active_user_mounts),
        "active_user_writable_mount_count": len(active_user_mounts),
        "active_user_writable_mount_target_present": bool(active_user_mounts),
        "no_upload_boundary": bool(boundary.get("no_upload")),
        "submit_eligible": bool(boundary.get("submit_eligible")),
        "env_path_present": bool(path_value),
        "env_probe_path_coverage": probe_coverage,
        "env_probe_path_coverage_count": sum(1 for ready in probe_coverage.values() if ready),
        "task_material_readiness_status": str(task_material.get("status") or ""),
        "task_material_first_blocker": str(task_material.get("first_blocker") or ""),
        "task_material_readiness_checked": task_material.get("checked") is True,
        "task_material_ready_required": launch.get("task_material_ready_required") is True,
        "task_material_ready": (
            task_material.get("ready") is True
            if task_material.get("checked") is True
            else None
        ),
        "task_material_candidate_count": int(task_material.get("candidate_count") or 0),
        "task_material_instruction_md_present_count": int(
            task_material.get("instruction_md_present_count") or 0
        ),
        "task_material_task_toml_present_count": int(
            task_material.get("task_toml_present_count") or 0
        ),
        "auth_surface_names_present": auth_names_present,
        "auth_values_recorded": False,
        "raw_env_recorded": False,
        "raw_paths_recorded": False,
    }
    materialization = (
        post_launch_materialization
        if isinstance(post_launch_materialization, dict)
        else launch.get("post_launch_materialization")
        if isinstance(launch.get("post_launch_materialization"), dict)
        else None
    )
    if materialization:
        summary["post_launch_materialization"] = materialization
    return summary


def normalize_terminal_bench_private_runner_invocation(
    invocation: list[Any],
) -> list[str]:
    """Normalize safe redacted replay cases and reject unsafe auth placeholders."""

    normalized = [str(value) for value in invocation]
    for index, value in enumerate(normalized[:-1]):
        if value != "--agent-env":
            continue
        assignment = _split_env_assignment(normalized[index + 1])
        if assignment is None:
            continue
        name, raw_value = assignment
        if name not in TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES:
            continue
        if _looks_like_redacted_env_value(raw_value):
            if name in TERMINAL_BENCH_BOOL_AGENT_ENV_NAMES:
                normalized[index + 1] = f"{name}=true"
                continue
            raise ValueError(
                f"redacted auth surface cannot be replayed via --agent-env: {name}"
            )
        if (
            name in TERMINAL_BENCH_BOOL_AGENT_ENV_NAMES
            and raw_value.strip().lower() not in TERMINAL_BENCH_BOOL_AGENT_ENV_VALUES
        ):
            raise ValueError(f"invalid boolean --agent-env value: {name}")
    return normalized


def _command_present(command: str) -> bool:
    return shutil.which(command, path=_probe_path()) is not None


def resolve_terminal_bench_runner_binary(command: str = "uvx") -> str:
    """Resolve a private runner binary through the Goal Harness probe PATH."""

    return shutil.which(command, path=_probe_path()) or command


def _probe_command(args: list[str], *, timeout_seconds: float = 4.0) -> bool:
    try:
        completed = subprocess.run(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout_seconds,
            env=_probe_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def collect_terminal_bench_managed_preflight_surface(
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Collect a public-safe, value-redacted managed-run surface probe.

    This probe intentionally records booleans and environment variable names
    only. It does not run Harbor, Terminal-Bench, Codex workers, containers, or
    model APIs, and it never records credential values or local paths.
    """

    env_map = os.environ if env is None else env
    auth_names_present = [
        name for name in TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES if name in env_map
    ]
    return {
        "schema_version": "terminal_bench_managed_real_run_preflight_surface_v0",
        "runner_surface": {
            "runner": "harbor",
            "benchmark": "terminal-bench",
            "uvx_cli_present": _command_present("uvx"),
            "uvx_version_probe_ok": _probe_command(["uvx", "--version"]),
            "runner_binary_resolution_policy": (
                "prepend_probe_path_or_use_resolved_runner_binary_for_private_runs"
            ),
            "runner_help_invoked": False,
        },
        "execution_surface": {
            "docker_cli_present": _command_present("docker"),
            "docker_version_probe_ok": _probe_command(["docker", "--version"]),
            "docker_server_available": _probe_command(
                ["docker", "version", "--format", "{{.Server.Version}}"]
            ),
            "colima_cli_present": _command_present("colima"),
            "colima_status_probe_ok": _probe_command(["colima", "status"]),
        },
        "codex_surface": {
            "codex_cli_present": _command_present("codex"),
            "codex_version_probe_ok": _probe_command(["codex", "--version"]),
            "auth_surface_names_checked": list(TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES),
            "auth_surface_names_present": auth_names_present,
            "auth_values_read": False,
        },
        "boundary": {
            "real_run": False,
            "submit_eligible": False,
            "no_upload": True,
            "artifact_redaction_required": True,
            "leaderboard_evidence": False,
            "paths_redacted": True,
        },
    }


def _managed_preflight_first_blocker(surface: dict[str, Any]) -> str:
    runner_surface = surface.get("runner_surface") if isinstance(surface.get("runner_surface"), dict) else {}
    execution_surface = (
        surface.get("execution_surface") if isinstance(surface.get("execution_surface"), dict) else {}
    )
    codex_surface = surface.get("codex_surface") if isinstance(surface.get("codex_surface"), dict) else {}
    boundary = surface.get("boundary") if isinstance(surface.get("boundary"), dict) else {}

    if not runner_surface.get("uvx_cli_present"):
        return "missing_uvx_runner_surface"
    if not runner_surface.get("uvx_version_probe_ok"):
        return "uvx_runner_surface_unverified"
    if not execution_surface.get("docker_cli_present"):
        return "missing_docker_cli_surface"
    if not execution_surface.get("docker_server_available"):
        return "missing_docker_server_surface"
    if not codex_surface.get("codex_cli_present"):
        return "missing_codex_cli_surface"
    if codex_surface.get("auth_values_read") is not False:
        return "codex_auth_value_boundary_violation"
    if not boundary.get("no_upload") or boundary.get("submit_eligible"):
        return "no_upload_boundary_not_ready"
    return "ready_for_private_managed_no_upload_pilot_review"


def build_terminal_bench_goal_harness_interaction_counters(
    *,
    prompt_policy_injected: bool,
    harness_skill_or_packet_injected: bool,
    codex_runtime_goal_tool_calls: dict[str, int] | None = None,
    goal_harness_cli_calls: dict[str, int] | None = None,
    goal_harness_state_reads: int = 0,
    goal_harness_state_writes: int = 0,
    case_result_writeback: str = "runner_only",
    counter_trust_level: str = "fixture_declared_zero",
) -> dict[str, Any]:
    """Build compact interaction counters without conflating goal-tool surfaces."""

    runtime_calls = {
        "create_goal": 0,
        "update_goal": 0,
        **(codex_runtime_goal_tool_calls or {}),
    }
    cli_calls = {
        command: 0 for command in TERMINAL_BENCH_GOAL_HARNESS_COUNTER_TRACE_COMMANDS
    }
    cli_calls.update(goal_harness_cli_calls or {})
    return {
        "schema_version": TERMINAL_BENCH_GOAL_HARNESS_INTERACTION_COUNTERS_VERSION,
        "prompt_policy_injected": bool(prompt_policy_injected),
        "harness_skill_or_packet_injected": bool(harness_skill_or_packet_injected),
        "codex_runtime_goal_tool_calls": {
            **runtime_calls,
            "total": sum(runtime_calls.values()),
        },
        "goal_harness_cli_calls": {
            **cli_calls,
            "total": sum(cli_calls.values()),
        },
        "goal_harness_state_reads": int(goal_harness_state_reads),
        "goal_harness_state_writes": int(goal_harness_state_writes),
        "case_result_writeback": case_result_writeback,
        "counter_trust_level": counter_trust_level,
        "raw_trace_recorded": False,
        "raw_task_prompt_recorded": False,
    }


def build_terminal_bench_goal_harness_cli_bridge_contract(
    *,
    goal_id: str = "<goal-id>",
    registry: str = "<registry>",
    runtime_root: str = "<runtime-root>",
    command_prefix: list[str] | tuple[str, ...] | None = None,
    scan_path: str = "<public-scan-path>",
    benchmark_run_json: str = "<benchmark-run-v0.json>",
    classification: str = "<classification>",
    bridge_available: bool = TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE,
) -> dict[str, Any]:
    """Build the host-side Goal Harness CLI bridge contract for Terminal-Bench."""

    prefix = list(command_prefix or ["goal-harness"])
    base = [
        *prefix,
        "--format",
        "json",
        "--registry",
        registry,
        "--runtime-root",
        runtime_root,
    ]
    command_templates = {
        "status": [
            *base,
            "status",
            "--limit",
            "5",
        ],
        "quota_should_run": [
            *base,
            "quota",
            "should-run",
            "--goal-id",
            goal_id,
        ],
        "todo_list": [
            *base,
            "quota",
            "should-run",
            "--goal-id",
            goal_id,
        ],
        "history": [
            *base,
            "history",
            "--goal-id",
            goal_id,
            "--limit",
            "5",
        ],
        "check": [
            *base,
            "check",
            "--scan-path",
            scan_path,
        ],
        "append_benchmark_run": [
            *base,
            "history",
            "append-benchmark-run",
            "--goal-id",
            goal_id,
            "--benchmark-run-json",
            benchmark_run_json,
            "--classification",
            classification,
            "--dry-run",
        ],
    }
    return {
        "schema_version": TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION,
        "bridge_surface": TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_SURFACE,
        "bridge_available": bool(bridge_available),
        "goal_id": goal_id,
        "registry_arg": registry,
        "runtime_root_arg": runtime_root,
        "command_prefix": prefix,
        "command_templates": command_templates,
        "logical_commands": list(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS),
        "read_commands": [
            "status",
            "quota_should_run",
            "todo_list",
            "history",
            "check",
        ],
        "write_commands": [
            "append_benchmark_run",
        ],
        "command_semantics": {
            "todo_list": (
                "Derived from quota should-run todo summaries until a dedicated "
                "todo-list CLI read surface exists."
            ),
            "append_benchmark_run": (
                "Template is dry-run by default; a real bridge may add --execute "
                "only after validation and no-upload/public-boundary checks."
            ),
        },
        "enable_conditions": [
            "goal-harness CLI importable or present on the agent host PATH",
            "project/global registry path mounted read-only for read commands",
            "runtime root mounted for history/status reads",
            "append_benchmark_run write mode gated by validation and no-upload boundary",
            "compact trace rows emitted for every logical bridge call",
        ],
        "boundary": {
            "real_run": False,
            "submit_eligible": False,
            "runs_harbor": False,
            "runs_terminal_bench": False,
            "runs_codex_worker": False,
            "model_api_invoked": False,
            "raw_registry_recorded": False,
            "raw_paths_required_in_public_artifacts": False,
        },
    }


def collect_terminal_bench_goal_harness_cli_bridge_trace(
    *,
    goal_id: str,
    registry: str,
    runtime_root: str,
    command_prefix: list[str] | tuple[str, ...] | None = None,
    scan_path: str = "goal_harness/benchmark.py",
    classification: str = "terminal_bench_goal_harness_cli_bridge_contract_runner_fixture_v0",
) -> dict[str, Any]:
    """Execute the host-agent bridge commands and return a redacted trace.

    The bridge probe is intentionally fixture-only: `append_benchmark_run` is
    dry-run, and the returned trace omits argv, registry paths, runtime paths,
    temp paths, and command payload bodies.
    """

    probe_benchmark_run = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "goal_harness_terminal_bench_cli_bridge_probe",
        "benchmark_id": TERMINAL_BENCH_DEFAULT_DATASET,
        "job_name": "terminal_bench_cli_bridge_probe",
        "mode": "codex_goal_harness_cli_bridge_contract_probe",
        "real_run": False,
        "submit_eligible": False,
    }
    with tempfile.TemporaryDirectory(prefix="goal-harness-terminal-bench-cli-bridge-") as root:
        benchmark_run_json = Path(root) / "benchmark-run.json"
        benchmark_run_json.write_text(
            json.dumps(probe_benchmark_run, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        contract = build_terminal_bench_goal_harness_cli_bridge_contract(
            goal_id=goal_id,
            registry=registry,
            runtime_root=runtime_root,
            command_prefix=command_prefix,
            scan_path=scan_path,
            benchmark_run_json=str(benchmark_run_json),
            classification=classification,
            bridge_available=True,
        )
        command_results: list[dict[str, Any]] = []
        observed_calls: dict[str, int] = {}
        for command in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS:
            completed = subprocess.run(
                contract["command_templates"][command],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=12,
                check=False,
            )
            ok = completed.returncode == 0
            payload: dict[str, Any] = {}
            if completed.stdout.strip():
                try:
                    parsed = json.loads(completed.stdout)
                    if isinstance(parsed, dict):
                        payload = parsed
                except json.JSONDecodeError:
                    payload = {}
            if payload.get("ok") is False:
                ok = False
            if command == "append_benchmark_run":
                ok = ok and payload.get("appended") is False and payload.get("dry_run") is True
            command_results.append(
                {
                    "command": command,
                    "ok": ok,
                    "dry_run_write": command == "append_benchmark_run",
                }
            )
            observed_calls[command] = 1 if ok else 0
            if not ok:
                raise RuntimeError(
                    f"Goal Harness CLI bridge command failed in fixture: {command}"
                )

    return {
        "schema_version": "terminal_bench_goal_harness_cli_bridge_trace_v0",
        "bridge_surface": TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_SURFACE,
        "bridge_available": True,
        "logical_command_count": len(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS),
        "command_results": command_results,
        "goal_harness_cli_calls": observed_calls,
        "goal_harness_state_reads": 5,
        "goal_harness_state_writes": 0,
        "case_result_writeback": "bridge_append_benchmark_run_dry_run",
        "counter_trust_level": "runner_bridge_contract_fixture_observed",
        "boundary": {
            "real_run": False,
            "submit_eligible": False,
            "runs_harbor": False,
            "runs_terminal_bench": False,
            "runs_codex_worker": False,
            "model_api_invoked": False,
            "raw_paths_recorded": False,
        },
    }


def build_terminal_bench_active_user_private_launcher_plan(
    *,
    active_cli_bridge_preflight: bool,
) -> dict[str, Any]:
    """Describe the non-executing plan for a real private assisted sample."""

    channel = build_terminal_bench_active_user_injection_channel_probe(
        active_cli_bridge_preflight=active_cli_bridge_preflight,
    )
    codex_simulator_contract = build_active_user_codex_simulator_contract(
        feed_jsonl=TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    )
    channel_available = bool(channel.get("channel_available"))
    first_blocker = (
        "ready_for_private_no_upload_assisted_worker_sample"
        if channel_available
        else TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_FIRST_BLOCKER
    )
    return {
        "schema_version": TERMINAL_BENCH_ACTIVE_USER_PRIVATE_LAUNCHER_PLAN_SCHEMA,
        "launch_surface": "private_no_upload_terminal_bench_single_worker",
        "ready": channel_available,
        "first_blocker": first_blocker,
        "required_capability": "worker_observes_simulator_message_after_start",
        "worker_start_marker": "worker_start_seq",
        "active_user_feed_jsonl": TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
        "active_user_observation_json": (
            TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON
        ),
        "simulator_setting": TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_SETTING,
        "codex_simulator_contract": {
            "schema_version": codex_simulator_contract.get("schema_version"),
            "simulator_kind": codex_simulator_contract.get("simulator_kind"),
            "manual_controller_feed_allowed": codex_simulator_contract.get(
                "manual_controller_feed_allowed"
            ),
            "formal_treatment_requires_model_backed_simulator": (
                codex_simulator_contract.get(
                    "formal_treatment_requires_model_backed_simulator"
                )
            ),
            "codex_exec_command": (
                (codex_simulator_contract.get("codex_cli") or {}).get(
                    "exec_command"
                )
            ),
            "append_validated_output_command": codex_simulator_contract.get(
                "append_validated_output_command"
            ),
            "simulator_output_schema_version": (
                codex_simulator_contract.get("simulator_output_contract") or {}
            ).get("schema_version"),
            "controller_authored_feed_allowed": (
                (codex_simulator_contract.get("claim_boundary") or {}).get(
                    "controller_authored_feed_allowed"
                )
            ),
        },
        "sequence_steps": [
            "launch_single_codex_goal_harness_worker_with_no_upload",
            "record_worker_start_seq_before_first_poll",
            "build_public_simulator_context_without_hidden_tests_or_solutions",
            "run_codex_cli_user_simulator_with_output_schema",
            "validate_codex_simulator_output_with_no_oracle_audit",
            "append_validated_simulator_intervention_with_seq_gt_worker_start_seq",
            "worker_polls_active_user_observe_after_start",
            "ingest_worker_observation_as_non_official_collaboration_evidence",
        ],
        "required_evidence": [
            "worker_start_seq_recorded",
            "codex_cli_simulator_contract_recorded",
            "codex_cli_simulator_output_validated",
            "post_start_intervention_seq_recorded",
            "active_user_observe_worker_cli_call_recorded",
            "worker_observation_proof_true",
            "official_score_kind_not_run_or_separate",
        ],
        "stop_conditions": [
            "hidden_tests_or_expected_solution_visible",
            "credential_value_needed",
            "controller_authored_feed_needed",
            "codex_simulator_output_schema_rejected",
            "leaderboard_or_upload_requested",
            "raw_transcript_required",
            "worker_observation_missing",
        ],
        "claim_boundary": {
            "assisted_collaboration_claim_allowed": True,
            "official_score_claim_allowed": False,
            "leaderboard_claim_allowed": False,
            "official_score_must_remain_separate": True,
        },
        "public_boundary": {
            "no_upload": True,
            "raw_paths_recorded": False,
            "raw_transcript_recorded": False,
            "credential_values_recorded": False,
        },
    }


def build_terminal_bench_goal_harness_access_packet(
    *,
    mode: str = "codex_goal_harness",
    packet_mode: str = TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL,
    goal_id: str = "<goal-id>",
    cli_bridge_available: bool = TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE,
    command_prefix: str = "goal-harness",
    registry_arg: str = "<registry>",
    runtime_root_arg: str = "<runtime-root>",
    scan_path: str = "<public-scan-path>",
    benchmark_run_json: str = "<benchmark-run-v0.json>",
    counter_trace_json: str = "<counter-trace-jsonl>",
    classification: str = "<classification>",
    append_execute_enabled: bool = False,
    active_user_intervention_enabled: bool = False,
    active_user_feed_jsonl: str = TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    active_user_observation_json: str = TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    active_user_observe_command: str = "<active-user-observe-command>",
    active_user_channel_surface: str = ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
) -> str:
    """Build the public-safe worker access packet for the Goal Harness arm.

    By default V0 is prompt-only. When `cli_bridge_available=True`, the packet
    carries command templates for a Codex worker-side Goal Harness CLI bridge.
    """

    if packet_mode not in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES:
        raise ValueError(f"unsupported Goal Harness access packet mode: {packet_mode}")

    compact_mode = packet_mode == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_COMPACT
    none_mode = packet_mode == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    if none_mode:
        return "\n".join(
            [
                "Goal Harness Access Packet V0",
                f"packet_mode: {packet_mode}",
                f"mode: {mode}",
                f"goal_id: {goal_id}",
                "goal_harness_access_packet_disabled: true",
                "goal_harness_interface_surface: none_runner_archive_only",
                "goal_harness_cli_bridge_available: false",
                "goal_harness_cli_bridge_contract: none",
                "declared_goal_harness_interface_commands: ",
                "runner_side_guaranteed_writeback_for_final_outcome: true",
                "worker_receives_no_goal_harness_cli_templates: true",
                "worker_receives_no_goal_harness_access_packet: true",
                "runner_side_archive_remains_authoritative_for_final_outcome: true",
                "do_not_claim_goal_harness_cli_calls_without_bridge_or_trace: true",
                "do_not_record_private_paths_credentials_raw_sessions_or_raw_task_logs: true",
            ]
        )
    commands = ", ".join(
        TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS
        if compact_mode
        else TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS
    )
    interface_surface = (
        TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
        if cli_bridge_available
        else TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE
    )
    bridge_lines: list[str] = []
    if cli_bridge_available:
        registry_arg_quoted = shlex.quote(registry_arg)
        runtime_root_arg_quoted = shlex.quote(runtime_root_arg)
        goal_id_quoted = shlex.quote(goal_id)
        scan_path_quoted = shlex.quote(scan_path)
        benchmark_run_json_quoted = shlex.quote(benchmark_run_json)
        classification_quoted = shlex.quote(classification)
        active_user_observe_command_text = _public_safe_benchmark_label(
            active_user_observe_command,
            limit=500,
        )
        if active_user_observe_command_text is None:
            active_user_observe_command_text = "<active-user-observe-command-redacted>"
        base = (
            f"{command_prefix} --format json --registry {registry_arg_quoted} "
            f"--runtime-root {runtime_root_arg_quoted}"
        )
        append_suffix = "--execute" if append_execute_enabled else "--dry-run"
        bridge_lines = [
            "goal_harness_cli_bridge_surface: "
            + TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE,
            "goal_harness_cli_bridge_command_check: "
            + f"{base} check --scan-path {scan_path_quoted}",
            "goal_harness_cli_bridge_command_append_benchmark_run: "
            + (
                f"{base} history append-benchmark-run --goal-id {goal_id_quoted} "
                f"--benchmark-run-json {benchmark_run_json_quoted} "
                f"--classification {classification_quoted} {append_suffix}"
            ),
            "goal_harness_cli_bridge_call_policy_version: "
            + TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_VERSION,
            "goal_harness_cli_bridge_call_policy_mode: "
            + TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_MODE,
            "goal_harness_cli_bridge_default_required_calls: "
            + ",".join(TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS),
            "goal_harness_cli_bridge_minimum_required_worker_calls: "
            + str(TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM),
            "goal_harness_cli_bridge_placeholder_policy_version: "
            + TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_PLACEHOLDER_POLICY_VERSION,
            "goal_harness_cli_bridge_command_templates_require_placeholder_substitution: true",
            "goal_harness_cli_bridge_quote_or_argv_execute_substituted_values: true",
            "do_not_execute_goal_harness_cli_command_with_unresolved_angle_bracket_placeholders: true",
            "goal_harness_counter_trace_jsonl: " + counter_trace_json,
            "goal_harness_benchmark_run_json: " + benchmark_run_json,
            "goal_harness_benchmark_run_writeback_contract: "
            + WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION,
            "runner_side_guaranteed_writeback_for_final_outcome: true",
            "after_each_goal_harness_cli_call_append_compact_jsonl_to_trace: true",
            "goal_harness_counter_trace_row_required_fields: "
            "event,command,ok,goal_id,mode,classification",
            "goal_harness_counter_trace_context_goal_id: " + goal_id,
            "goal_harness_counter_trace_context_mode: " + mode,
            "goal_harness_counter_trace_context_classification: " + classification,
            "before_long_actions_call_goal_harness_check_once: true",
            "after_validation_write_compact_case_result_through_goal_harness: true",
            "write_compact_case_result_after_final_validation_cleanup_or_terminal_blocker_only: true",
            "do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true",
            "emit_compact_counter_trace_for_each_goal_harness_cli_call: true",
            "worker_benchmark_run_json_schema_version: benchmark_run_v0",
            "worker_benchmark_run_json_top_level_must_be_schema_version: true",
            "do_not_wrap_worker_benchmark_run_json_in_benchmark_run_key: true",
            "worker_benchmark_run_json_minimal_shape: "
            + ",".join(WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_TOP_LEVEL_FIELDS),
            "worker_benchmark_run_json_must_omit: "
            + ",".join(WORKER_BRIDGE_BENCHMARK_RUN_FORBIDDEN_PUBLIC_FIELDS),
            "worker_benchmark_run_json_required_fixed_fields: "
            + ",".join(
                f"{key}={str(value).lower()}"
                for key, value in WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_FIXED_FIELDS.items()
            ),
            "worker_benchmark_run_json_real_run_must_be_true: true",
            "worker_benchmark_run_json_submit_eligible_must_be_false: true",
            "worker_benchmark_run_json_leaderboard_evidence_must_be_false: true",
            "worker_benchmark_run_json_runner_no_upload_boundary_overrides_worker_guess: true",
        ]
        if active_user_intervention_enabled:
            bridge_lines.extend(
                [
                    "active_user_intervention_channel_enabled: true",
                    "active_user_intervention_channel_surface: "
                    + active_user_channel_surface,
                    "active_user_intervention_feed_jsonl: " + active_user_feed_jsonl,
                    "active_user_intervention_observation_json: "
                    + active_user_observation_json,
                    "active_user_intervention_observe_command: "
                    + active_user_observe_command_text,
                    "active_user_worker_start_marker: worker_start_seq",
                    "active_user_worker_must_poll_after_start: true",
                    "active_user_direct_codex_chat_injection: false",
                    "active_user_official_score_claim_allowed: false",
                    "active_user_leaderboard_claim_allowed: false",
                    "active_user_no_hidden_tests_expected_solutions_or_credentials: true",
                    "active_user_frequency_budget_required: true",
                ]
            )
        if compact_mode:
            bridge_lines.extend(
                [
                    "goal_harness_access_packet_compact_mode: true",
                    "optional_status_quota_todo_history_commands_omitted_from_prompt: true",
                    "runner_side_archive_remains_authoritative_for_final_outcome: true",
                ]
            )
        else:
            bridge_lines[2:2] = [
                "goal_harness_cli_bridge_command_status: "
                + f"{base} status --limit 5",
                "goal_harness_cli_bridge_command_quota_should_run: "
                + f"{base} quota should-run --goal-id {goal_id_quoted}",
                "goal_harness_cli_bridge_command_todo_list: "
                + f"{base} quota should-run --goal-id {goal_id_quoted}",
                "goal_harness_cli_bridge_command_history: "
                + f"{base} history --goal-id {goal_id_quoted} --limit 5",
            ]
            bridge_lines.extend(
                [
                    "goal_harness_cli_bridge_optional_blocked_or_resume_calls: "
                    + ",".join(
                        TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS
                    ),
                    "episode_policy: " + TERMINAL_BENCH_EPISODE_POLICY_MODE,
                    "episode_checkpoint_interval_seconds: "
                    + str(TERMINAL_BENCH_DEFAULT_EPISODE_CHECKPOINT_INTERVAL_SECONDS),
                    "episode_checkpoint_scope: same_codex_agent_compact_evidence",
                    "do_not_spawn_additional_agents_for_episodes: true",
                    "do_not_call_status_quota_todo_history_by_default: true",
                    "call_status_quota_todo_history_only_when_blocked_or_resuming_or_schema_retry_needs_context: true",
                    "if_append_benchmark_run_schema_rejected_rewrite_minimal_benchmark_run_v0_and_retry_once: true",
                ]
            )
    return "\n".join(
        [
            "Goal Harness Access Packet V0",
            f"packet_mode: {packet_mode}",
            f"mode: {mode}",
            f"goal_id: {goal_id}",
            "goal_harness_interface_surface: " + interface_surface,
            "goal_harness_cli_bridge_available: "
            + ("true" if cli_bridge_available else "false"),
            "goal_harness_cli_bridge_contract: "
            + TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION,
            "declared_goal_harness_interface_commands: " + commands,
            *bridge_lines,
            "if_cli_bridge_available_use_lean_check_and_final_append_policy: true",
            "status_quota_todo_history_are_optional_blocked_or_resume_calls: true",
            "write_compact_case_result_through_goal_harness_when_bridge_available: true",
            "count_codex_runtime_goal_tools_separately_from_goal_harness_calls: true",
            "do_not_claim_goal_harness_cli_calls_without_bridge_or_trace: true",
            "do_not_record_private_paths_credentials_raw_sessions_or_raw_task_logs: true",
            "do_not_require_a_hardcoded_tool_call_before_reasoning: true",
            "report_interaction_counters_after_the_case: true",
        ]
    )


def build_terminal_bench_goal_harness_access_packet_fixture(
    *,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str = TERMINAL_BENCH_DEFAULT_TASK,
    model: str = TERMINAL_BENCH_DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build a no-run fixture for the true codex_goal_harness treatment arm."""

    counters = build_terminal_bench_goal_harness_interaction_counters(
        prompt_policy_injected=True,
        harness_skill_or_packet_injected=True,
        case_result_writeback="not_observed_no_run_fixture",
    )
    return {
        "schema_version": "terminal_bench_goal_harness_access_packet_fixture_v0",
        "arm": "codex_goal_harness",
        "benchmark_id": dataset,
        "task_id": task_id,
        "agent": "codex",
        "model": model,
        "access_packet": {
            "schema_version": TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION,
            "packet_public_preview": build_terminal_bench_goal_harness_access_packet(),
            "interface_surface": TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE,
            "interfaces_available": [],
            "interfaces_declared": list(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS),
            "goal_harness_interfaces_available": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
            ),
            "goal_harness_cli_bridge_available": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
            ),
            "goal_harness_cli_bridge_contract": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION
            ),
            "prompt_packet_only_until_cli_bridge": True,
            "hardcoded_tool_call_required": False,
            "worker_may_choose_when_to_call": True,
        },
        "interaction_counters": counters,
        "mode_contract": {
            "goal_harness_inside_case": True,
            "case_semantics_changed_by_harness": True,
            "official_score_comparable_to_native_codex": False,
            "model_plus_harness_pair": True,
            "control_plane_score_applicable": True,
            "leaderboard_evidence": False,
            "worker_trace_observed": False,
            "goal_harness_actual_use_observed": False,
            "goal_harness_interface_surface": (
                TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE
            ),
            "goal_harness_cli_bridge_available": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
            ),
        },
        "boundary": {
            "real_run": False,
            "submit_eligible": False,
            "no_upload": True,
            "raw_task_prompt_recorded": False,
            "raw_sessions_recorded": False,
            "host_paths_recorded": False,
            "credential_values_recorded": False,
        },
        "evidence_files": [
            "doc:terminal-bench-goal-harness-access-packet-v0.md",
            "doc:terminal-bench-treatment-arm-taxonomy-v0.md",
            "smoke:terminal-bench-goal-harness-access-packet-smoke.py",
        ],
        "next_runner_step": (
            "wire this packet into a codex_goal_harness worker mode and count actual "
            "Goal Harness CLI/state reads/writes on a fake-worker fixture before any real repeat"
        ),
    }


def _mode_contract(mode: str, *, fake_worker: bool) -> dict[str, Any]:
    if mode == "hardened-codex":
        return {
            "event_mode": "hardened_codex_baseline_cli_dry_run",
            "worker_mode": TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE,
            "goal_harness_inside_case": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": False,
            "official_score_comparable_to_goal_harness_treatment": True,
            "model_plus_harness_pair": False,
            "control_plane_score_applicable": False,
            "trace_publicness": "public_cli_dry_run",
            "goal_harness_interface_surface": (
                TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE
            ),
            "goal_harness_cli_bridge_available": False,
            "goal_harness_actual_use_observed": False,
            "startup_surface_calibration": False,
            "hardened_install_surface": True,
            "hardened_install_baseline": True,
            "first_blocker": "hardened_codex_baseline_cli_skeleton_only_no_real_case",
        }
    if mode == "passive-observed-codex":
        return {
            "event_mode": "passive_observed_codex_cli_dry_run",
            "worker_mode": "passive_observed_codex_cli",
            "goal_harness_inside_case": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": True,
            "model_plus_harness_pair": False,
            "control_plane_score_applicable": True,
            "trace_publicness": "public_cli_dry_run",
            "first_blocker": "passive_cli_skeleton_only_no_real_case",
        }
    if mode == "codex-goal-harness":
        return {
            "event_mode": (
                "codex_goal_harness_fake_worker_wrapper"
                if fake_worker
                else "codex_goal_harness_cli_dry_run"
            ),
            "worker_mode": "codex_goal_harness_cli",
            "goal_harness_inside_case": True,
            "case_semantics_changed_by_harness": True,
            "official_score_comparable_to_native_codex": False,
            "model_plus_harness_pair": True,
            "control_plane_score_applicable": True,
            "trace_publicness": (
                "public_fake_codex_goal_harness_wrapper"
                if fake_worker
                else "public_cli_dry_run"
            ),
            "goal_harness_interface_surface": (
                "fake_worker_synthetic_cli_trace"
                if fake_worker
                else TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE
            ),
            "goal_harness_cli_bridge_available": (
                True if fake_worker else TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
            ),
            "goal_harness_actual_use_observed": bool(fake_worker),
            "first_blocker": (
                "fake_codex_goal_harness_worker_only_no_real_case"
                if fake_worker
                else "codex_goal_harness_cli_skeleton_only_no_real_case"
            ),
        }
    if mode == "goal-harness-managed-codex":
        return {
            "event_mode": (
                "goal_harness_managed_codex_fake_worker_wrapper"
                if fake_worker
                else "goal_harness_managed_codex_cli_dry_run"
            ),
            "worker_mode": "goal_harness_managed_codex_cli",
            "goal_harness_inside_case": True,
            "case_semantics_changed_by_harness": True,
            "official_score_comparable_to_native_codex": False,
            "model_plus_harness_pair": True,
            "control_plane_score_applicable": True,
            "trace_publicness": (
                "public_fake_managed_wrapper" if fake_worker else "public_cli_dry_run"
            ),
            "first_blocker": (
                "fake_managed_worker_only_no_real_case"
                if fake_worker
                else "managed_cli_skeleton_only_no_real_case"
            ),
        }
    raise ValueError(f"unsupported terminal-bench mode: {mode}")


def build_terminal_bench_managed_harbor_command(
    *,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str | None = TERMINAL_BENCH_DEFAULT_TASK,
    model: str = TERMINAL_BENCH_DEFAULT_MODEL,
    jobs_dir: str = "<private-jobs-dir>",
    job_name: str | None = None,
    goal_harness_mode: str = "goal_harness_managed_codex",
    goal_harness_ablation_mode: str = "goal_harness_managed",
    goal_harness_goal_id: str = "<goal-id>",
    goal_harness_cli_bridge_enabled: bool = False,
    goal_harness_active_user_intervention_enabled: bool = False,
    goal_harness_project_root: str = (
        TERMINAL_BENCH_WORKER_BRIDGE_PROJECT_ROOT_PLACEHOLDER
    ),
    goal_harness_runtime_root: str = (
        TERMINAL_BENCH_WORKER_BRIDGE_RUNTIME_ROOT_PLACEHOLDER
    ),
    goal_harness_counter_trace_json: str = (
        TERMINAL_BENCH_WORKER_BRIDGE_COUNTER_TRACE_JSON
    ),
    goal_harness_benchmark_run_json: str = (
        TERMINAL_BENCH_WORKER_BRIDGE_BENCHMARK_RUN_JSON
    ),
    goal_harness_active_user_host_dir: str | None = None,
    goal_harness_active_user_mount_target: str = (
        TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET
    ),
    goal_harness_classification: str = "<classification>",
    goal_harness_access_packet_mode: str = (
        TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL
    ),
    timeout_multiplier: float | None = None,
    agent_timeout_multiplier: float | None = None,
    verifier_timeout_multiplier: float | None = None,
    agent_setup_timeout_multiplier: float | None = None,
    environment_build_timeout_multiplier: float | None = None,
    no_upload: bool = True,
    resolve_cli_paths: bool = False,
) -> list[str]:
    """Build the private single-task Harbor command for managed Codex.

    The returned argv is safe to show as a public command template when
    `jobs_dir` is left as the placeholder. It intentionally omits Harbor upload,
    publish, share, and leaderboard flags.
    """

    if goal_harness_cli_bridge_enabled and goal_harness_mode != "codex_goal_harness":
        raise ValueError(
            "goal_harness_cli_bridge_enabled requires goal_harness_mode=codex_goal_harness"
        )
    if goal_harness_access_packet_mode not in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES:
        raise ValueError(
            "goal_harness_access_packet_mode must be one of: "
            + ", ".join(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES)
        )
    if job_name is None:
        event_mode = (
            "goal_harness_managed_codex_cli_dry_run"
            if goal_harness_mode == "goal_harness_managed_codex"
            else goal_harness_mode
        )
        task_label = str(task_id or "all").replace("-", "_")
        job_name = (
            f"{dataset.replace('@', '_').replace('.', '_')}_"
            f"{task_label}_{event_mode}"
        )

    command = [
        (
            resolve_terminal_bench_runner_binary("uvx")
            if resolve_cli_paths
            else "uvx"
        ),
        "--from",
        TERMINAL_BENCH_HARBOR_REF,
        "harbor",
        "run",
        *_terminal_bench_dataset_args(dataset),
        "--agent-import-path",
        TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH,
        "--model",
        model,
        "--env",
        "docker",
        "--n-attempts",
        "1",
        "--n-concurrent",
        "1",
        "--jobs-dir",
        jobs_dir,
        "--job-name",
        job_name,
        "--agent-env",
        "CODEX_FORCE_AUTH_JSON=true",
        "--agent-kwarg",
        f"goal_harness_policy_version={TERMINAL_BENCH_MANAGED_POLICY_VERSION}",
        "--agent-kwarg",
        f"goal_harness_behavior_spec_id={TERMINAL_BENCH_MANAGED_BEHAVIOR_SPEC_ID}",
        "--agent-kwarg",
        f"goal_harness_mode={goal_harness_mode}",
        "--agent-kwarg",
        f"goal_harness_goal_id={goal_harness_goal_id}",
        "--agent-kwarg",
        f"goal_harness_ablation_mode={goal_harness_ablation_mode}",
    ]
    if task_id:
        command.extend(["--include-task-name", task_id])
    if goal_harness_access_packet_mode != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL:
        command.extend(
            [
                "--agent-kwarg",
                f"goal_harness_access_packet_mode={goal_harness_access_packet_mode}",
            ]
        )
    timeout_flag_values = (
        ("--timeout-multiplier", timeout_multiplier),
        ("--agent-timeout-multiplier", agent_timeout_multiplier),
        ("--verifier-timeout-multiplier", verifier_timeout_multiplier),
        ("--agent-setup-timeout-multiplier", agent_setup_timeout_multiplier),
        (
            "--environment-build-timeout-multiplier",
            environment_build_timeout_multiplier,
        ),
    )
    for flag, value in timeout_flag_values:
        parsed = _optional_float(value)
        if parsed is None:
            continue
        if parsed <= 0:
            raise ValueError(f"{flag} must be greater than zero")
        command.extend([flag, _format_harbor_multiplier(parsed)])
    if goal_harness_cli_bridge_enabled:
        active_user_host_dir = None
        if goal_harness_active_user_intervention_enabled:
            active_user_host_dir = (
                goal_harness_active_user_host_dir
                or TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_HOST_DIR_PLACEHOLDER
            )
        worker_bridge = build_worker_bridge_install_contract(
            project_root=goal_harness_project_root,
            runtime_root=goal_harness_runtime_root,
            benchmark_run_json=goal_harness_benchmark_run_json,
            counter_trace_json=goal_harness_counter_trace_json,
            classification=goal_harness_classification,
            active_user_host_dir=active_user_host_dir,
            active_user_mount_target=goal_harness_active_user_mount_target,
        )
        agent_kwargs = worker_bridge["agent_kwargs"]
        command.extend(
            [
                "--mounts",
                json.dumps(worker_bridge["mounts"], sort_keys=True),
                "--agent-kwarg",
                "goal_harness_cli_bridge_enabled=true",
                "--agent-kwarg",
                f"goal_harness_command_prefix={agent_kwargs['goal_harness_command_prefix']}",
                "--agent-kwarg",
                f"goal_harness_runtime_preflight_command={agent_kwargs['goal_harness_runtime_preflight_command']}",
                "--agent-kwarg",
                f"goal_harness_registry_arg={agent_kwargs['goal_harness_registry_arg']}",
                "--agent-kwarg",
                f"goal_harness_runtime_root_arg={agent_kwargs['goal_harness_runtime_root_arg']}",
                "--agent-kwarg",
                f"goal_harness_scan_path={agent_kwargs['goal_harness_scan_path']}",
                "--agent-kwarg",
                f"goal_harness_benchmark_run_json={agent_kwargs['goal_harness_benchmark_run_json']}",
                "--agent-kwarg",
                "goal_harness_benchmark_run_schema_version="
                + agent_kwargs["goal_harness_benchmark_run_schema_version"],
                "--agent-kwarg",
                "goal_harness_benchmark_run_writeback_contract="
                + agent_kwargs["goal_harness_benchmark_run_writeback_contract"],
                "--agent-kwarg",
                f"goal_harness_counter_trace_json={agent_kwargs['goal_harness_counter_trace_json']}",
                "--agent-kwarg",
                f"goal_harness_classification={agent_kwargs['goal_harness_classification']}",
            ]
        )
        if goal_harness_active_user_intervention_enabled:
            command.extend(
                [
                    "--agent-kwarg",
                    "goal_harness_active_user_intervention_enabled=true",
                    "--agent-kwarg",
                    "goal_harness_active_user_feed_jsonl="
                    + agent_kwargs["goal_harness_active_user_feed_jsonl"],
                    "--agent-kwarg",
                    "goal_harness_active_user_observation_json="
                    + agent_kwargs["goal_harness_active_user_observation_json"],
                    "--agent-kwarg",
                    "goal_harness_active_user_observe_command="
                    + agent_kwargs["goal_harness_active_user_observe_command"],
                    "--agent-kwarg",
                    "goal_harness_active_user_channel_surface="
                    + agent_kwargs["goal_harness_active_user_channel_surface"],
                ]
            )
    if not no_upload:
        raise ValueError("managed Terminal-Bench pilot command is no-upload only")
    return normalize_terminal_bench_private_runner_invocation(command)


def build_terminal_bench_benchmark_run(
    *,
    mode: str,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str = TERMINAL_BENCH_DEFAULT_TASK,
    runner: str = "harbor",
    agent: str = "codex",
    model: str = TERMINAL_BENCH_DEFAULT_MODEL,
    fake_worker: bool = False,
    preflight_guard: bool = False,
    preflight_surface: dict[str, Any] | None = None,
    cli_bridge_contract: bool = False,
    cli_bridge_trace: dict[str, Any] | None = None,
    worker_cli_bridge_fixture: bool = False,
    active_cli_bridge_preflight: bool = False,
    active_user_assisted_treatment_preflight: bool = False,
    active_user_observation_fixture: bool = False,
    require_task_material_ready: bool = False,
    timeout_multiplier: float | None = None,
    agent_timeout_multiplier: float | None = None,
    verifier_timeout_multiplier: float | None = None,
    agent_setup_timeout_multiplier: float | None = None,
    environment_build_timeout_multiplier: float | None = None,
) -> dict[str, Any]:
    """Build a compact fixture-only benchmark_run_v0 for Terminal-Bench.

    This helper intentionally has no real execution path. It is the public CLI
    skeleton used before any Harbor/Codex/Docker runner integration is enabled.
    """

    if runner != "harbor":
        raise ValueError("terminal-bench skeleton currently supports runner=harbor only")
    if agent != "codex":
        raise ValueError("terminal-bench skeleton currently supports agent=codex only")
    if fake_worker and mode not in ("codex-goal-harness", "goal-harness-managed-codex"):
        raise ValueError(
            "--fake-worker is only supported for codex-goal-harness or goal-harness-managed-codex"
        )
    if preflight_guard and fake_worker:
        raise ValueError("--preflight-guard cannot be combined with --fake-worker")
    if preflight_guard and mode not in (
        "hardened-codex",
        "codex-goal-harness",
        "goal-harness-managed-codex",
    ):
        raise ValueError(
            "--preflight-guard is only supported for hardened-codex, codex-goal-harness, or goal-harness-managed-codex"
        )
    if require_task_material_ready and not preflight_guard:
        raise ValueError("--require-task-material-ready requires --preflight-guard")
    if cli_bridge_contract and mode != "codex-goal-harness":
        raise ValueError("--cli-bridge-contract is only supported for codex-goal-harness")
    if cli_bridge_contract and fake_worker:
        raise ValueError("--cli-bridge-contract cannot be combined with --fake-worker")
    if cli_bridge_contract and preflight_guard:
        raise ValueError("--cli-bridge-contract cannot be combined with --preflight-guard")
    if worker_cli_bridge_fixture and mode != "codex-goal-harness":
        raise ValueError("--worker-cli-bridge-fixture is only supported for codex-goal-harness")
    if worker_cli_bridge_fixture and fake_worker:
        raise ValueError("--worker-cli-bridge-fixture cannot be combined with --fake-worker")
    if worker_cli_bridge_fixture and preflight_guard:
        raise ValueError("--worker-cli-bridge-fixture cannot be combined with --preflight-guard")
    if worker_cli_bridge_fixture and cli_bridge_contract:
        raise ValueError("--worker-cli-bridge-fixture cannot be combined with --cli-bridge-contract")
    if active_cli_bridge_preflight and mode != "codex-goal-harness":
        raise ValueError("--active-cli-bridge is only supported for codex-goal-harness")
    if active_cli_bridge_preflight and not preflight_guard:
        raise ValueError("--active-cli-bridge requires --preflight-guard")
    if active_cli_bridge_preflight and cli_bridge_contract:
        raise ValueError("--active-cli-bridge cannot be combined with --cli-bridge-contract")
    if active_cli_bridge_preflight and worker_cli_bridge_fixture:
        raise ValueError("--active-cli-bridge cannot be combined with --worker-cli-bridge-fixture")
    if active_user_assisted_treatment_preflight and mode != "codex-goal-harness":
        raise ValueError("--active-user-assisted-treatment is only supported for codex-goal-harness")
    if active_user_assisted_treatment_preflight and not preflight_guard:
        raise ValueError("--active-user-assisted-treatment requires --preflight-guard")
    if active_user_assisted_treatment_preflight and not active_cli_bridge_preflight:
        raise ValueError("--active-user-assisted-treatment requires --active-cli-bridge")
    if active_user_assisted_treatment_preflight and worker_cli_bridge_fixture:
        raise ValueError("--active-user-assisted-treatment cannot be combined with --worker-cli-bridge-fixture")
    if active_user_assisted_treatment_preflight and cli_bridge_contract:
        raise ValueError("--active-user-assisted-treatment cannot be combined with --cli-bridge-contract")
    if active_user_observation_fixture and not active_user_assisted_treatment_preflight:
        raise ValueError(
            "--active-user-observation-fixture requires --active-user-assisted-treatment"
        )
    if active_cli_bridge_preflight and agent_timeout_multiplier is None:
        agent_timeout_multiplier = (
            TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_TIMEOUT_MULTIPLIER
        )

    contract = _mode_contract(mode, fake_worker=fake_worker)
    bridge_trace_observed = (
        isinstance(cli_bridge_trace, dict)
        and cli_bridge_trace.get("bridge_available") is True
    )
    if cli_bridge_contract:
        contract = {
            **contract,
            "event_mode": "codex_goal_harness_cli_bridge_contract_fixture",
            "trace_publicness": "public_goal_harness_cli_bridge_contract_fixture",
            "first_blocker": "cli_bridge_contract_fixture_only_no_real_case",
            "goal_harness_cli_bridge_contract_available": True,
            "goal_harness_cli_bridge_trace_observed": bridge_trace_observed,
        }
    if worker_cli_bridge_fixture:
        contract = {
            **contract,
            "event_mode": "codex_goal_harness_worker_cli_bridge_fixture",
            "trace_publicness": "public_worker_goal_harness_cli_bridge_fixture",
            "first_blocker": "worker_cli_bridge_fixture_only_no_real_case",
            "goal_harness_interface_surface": (
                "worker_cli_bridge_fixture_compact_trace"
            ),
            "goal_harness_cli_bridge_available": True,
            "goal_harness_actual_use_observed": True,
            "goal_harness_worker_cli_bridge_available": True,
            "goal_harness_worker_cli_bridge_trace_observed": True,
        }
    if preflight_guard:
        surface = preflight_surface or collect_terminal_bench_managed_preflight_surface()
        first_blocker = _managed_preflight_first_blocker(surface)
        event_mode = (
            TERMINAL_BENCH_ACTIVE_USER_ASSISTED_OBSERVATION_FIXTURE_MODE
            if active_user_observation_fixture
            else TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_MODE
            if active_user_assisted_treatment_preflight
            else "codex_goal_harness_active_cli_bridge_preflight"
            if active_cli_bridge_preflight and mode == "codex-goal-harness"
            else TERMINAL_BENCH_CODEX_GOAL_HARNESS_PREFLIGHT_MODE
            if mode == "codex-goal-harness"
            else TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE
            if mode == "hardened-codex"
            else TERMINAL_BENCH_PREFLIGHT_MODE
        )
        trace_publicness = (
            "public_active_user_assisted_observation_fixture"
            if active_user_observation_fixture
            else "public_active_user_assisted_treatment_preflight"
            if active_user_assisted_treatment_preflight
            else "public_codex_goal_harness_active_cli_bridge_preflight"
            if active_cli_bridge_preflight and mode == "codex-goal-harness"
            else "public_codex_goal_harness_no_upload_preflight_guard"
            if mode == "codex-goal-harness"
            else "public_hardened_codex_baseline_preflight_guard"
            if mode == "hardened-codex"
            else "public_managed_real_run_preflight_guard"
        )
        contract = {
            **contract,
            "event_mode": event_mode,
            "trace_publicness": trace_publicness,
            "first_blocker": (
                TERMINAL_BENCH_ACTIVE_USER_OBSERVATION_FIXTURE_FIRST_BLOCKER
                if active_user_observation_fixture
                else TERMINAL_BENCH_ACTIVE_USER_REAL_WORKER_OBSERVATION_FIRST_BLOCKER
                if active_user_assisted_treatment_preflight
                else first_blocker
            ),
        }
    fake_result: dict[str, Any] = {}
    if fake_worker and mode == "codex-goal-harness":
        fake_result = {
            "schema_version": "fake_codex_goal_harness_worker_result_v0",
            "mode": "codex_goal_harness",
            "worker_mode": contract["worker_mode"],
            "access_packet_schema_version": TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION,
            "interface_surface": contract["goal_harness_interface_surface"],
            "cli_bridge_available": contract["goal_harness_cli_bridge_available"],
            "interfaces_declared_count": len(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS),
            "goal_harness_interface_calls_observed": True,
            "result": "fake_worker_completed_no_official_trial",
        }
    elif fake_worker and mode == "goal-harness-managed-codex":
        fake_result = {
            "schema_version": "fake_managed_codex_worker_result_v0",
            "mode": "goal_harness_managed_codex",
            "worker_mode": contract["worker_mode"],
            "state_surface_count": 7,
            "prompt_chars": 512,
            "saw_ephemeral": True,
            "saw_ignore_user_config": True,
            "saw_ignore_rules": True,
            "result": "fake_worker_completed_no_official_trial",
        }
    validation: dict[str, Any] = {
        "cli_skeleton_present": True,
        "no_real_codex_invoked": True,
        "no_harbor_or_terminal_bench_invoked": True,
        "no_model_api_invoked": True,
        "no_leaderboard_upload_requested": True,
        "paths_redacted": True,
    }
    if fake_worker:
        validation["fake_worker_enabled"] = True
    if cli_bridge_contract:
        validation["cli_bridge_contract_checked"] = True
        validation["cli_bridge_contract_trace_observed"] = bridge_trace_observed
        validation["append_benchmark_run_dry_run_only"] = True
        validation["worker_bridge_not_claimed"] = True
    if worker_cli_bridge_fixture:
        validation["worker_cli_bridge_fixture_enabled"] = True
        validation["worker_bridge_trace_observed"] = True
        validation["runner_bridge_calls_not_counted_as_worker_calls"] = True
        validation["no_terminal_bench_task_or_codex_worker_invoked"] = True
    if active_cli_bridge_preflight:
        validation["active_cli_bridge_preflight"] = True
        validation["worker_cli_bridge_command_preview_checked"] = True
        validation["worker_cli_bridge_trace_required_before_claim"] = True
        validation["no_worker_cli_calls_observed_in_preflight"] = True
    if active_user_assisted_treatment_preflight:
        validation_channel_probe = build_terminal_bench_active_user_injection_channel_probe(
            active_cli_bridge_preflight=active_cli_bridge_preflight,
        )
        validation["active_user_assisted_treatment_preflight"] = True
        validation["active_user_simulator_contract_checked"] = True
        validation["simulator_to_worker_injection_channel_checked"] = True
        validation["simulator_to_worker_injection_channel_probe_checked"] = True
        validation["simulator_to_worker_external_update_loop_available"] = bool(
            validation_channel_probe.get("audited_external_update_loop_available")
        )
        if active_user_observation_fixture:
            validation["active_user_observation_fixture"] = True
            validation["worker_observation_proof"] = True
            validation["scripted_active_user_intervention_observed"] = True
        else:
            validation["real_assisted_worker_observation_missing"] = True
        validation["no_real_user_message_injected"] = True
        validation["no_model_backed_simulator_invoked"] = True
        validation["no_oracle_audit_required"] = True
        validation["assisted_score_kept_separate_from_official"] = True
    if preflight_guard:
        validation["preflight_guard"] = True
        validation["auth_values_not_read"] = True
        validation["no_docker_task_or_container_started"] = True
        surface_runner = (
            surface.get("runner_surface")
            if isinstance(surface.get("runner_surface"), dict)
            else {}
        )
        surface_execution = (
            surface.get("execution_surface")
            if isinstance(surface.get("execution_surface"), dict)
            else {}
        )
        surface_codex = (
            surface.get("codex_surface")
            if isinstance(surface.get("codex_surface"), dict)
            else {}
        )
        validation["uvx_runner_surface_ready"] = bool(
            surface_runner.get("uvx_cli_present")
            and surface_runner.get("uvx_version_probe_ok")
        )
        validation["docker_execution_surface_ready"] = bool(
            surface_execution.get("docker_cli_present")
            and surface_execution.get("docker_server_available")
        )
        validation["codex_cli_surface_ready"] = bool(
            surface_codex.get("codex_cli_present")
            and surface_codex.get("codex_version_probe_ok")
        )
        if mode == "codex-goal-harness":
            validation["access_packet_prompt_injection_checked"] = True
            validation["trace_counter_extraction_contract_checked"] = True
            validation["goal_harness_mode_kwarg_checked"] = True
    else:
        validation["no_docker_or_cloud_invoked"] = True

    if mode == "codex-goal-harness":
        preflight_fixture_calls = {
            "status": 0,
            "quota_should_run": 0,
            "todo_list": 0,
            "history": 0,
            "check": 0,
            "append_benchmark_run": 0,
        }
        bridge_trace_calls = (
            cli_bridge_trace.get("goal_harness_cli_calls", {})
            if bridge_trace_observed
            else preflight_fixture_calls
        )
        active_user_observation_calls = {
            **preflight_fixture_calls,
            "active_user_observe": 1,
        }
        interaction_counters = build_terminal_bench_goal_harness_interaction_counters(
            prompt_policy_injected=True,
            harness_skill_or_packet_injected=True,
            goal_harness_cli_calls=(
                {
                    "status": 1,
                    "quota_should_run": 1,
                    "todo_list": 1,
                    "history": 1,
                    "check": 1,
                    "append_benchmark_run": 1,
                }
                if worker_cli_bridge_fixture
                else
                bridge_trace_calls
                if cli_bridge_contract
                else
                {
                    "status": 1,
                    "quota_should_run": 1,
                    "todo_list": 1,
                    "history": 1,
                    "check": 1,
                    "append_benchmark_run": 1,
                }
                if fake_worker
                else active_user_observation_calls
                if active_user_observation_fixture
                else preflight_fixture_calls if preflight_guard else None
            ),
            goal_harness_state_reads=(
                5
                if worker_cli_bridge_fixture
                else
                int(cli_bridge_trace.get("goal_harness_state_reads", 0))
                if bridge_trace_observed
                else 1 if active_user_observation_fixture
                else 4 if fake_worker else 0
            ),
            goal_harness_state_writes=(
                1
                if worker_cli_bridge_fixture
                else
                int(cli_bridge_trace.get("goal_harness_state_writes", 0))
                if bridge_trace_observed
                else 1 if fake_worker else 0
            ),
            case_result_writeback=(
                "worker_goal_harness_append_benchmark_run"
                if worker_cli_bridge_fixture
                else
                str(cli_bridge_trace.get("case_result_writeback"))
                if bridge_trace_observed
                else "bridge_contract_fixture_not_executed"
                if cli_bridge_contract
                else
                "worker_goal_harness_writeback"
                if fake_worker
                else "worker_active_user_observe_fixture_no_official_run"
                if active_user_observation_fixture
                else "not_observed_active_user_assisted_treatment_preflight"
                if active_user_assisted_treatment_preflight
                else "not_observed_active_cli_bridge_preflight"
                if active_cli_bridge_preflight
                else "not_observed_prompt_only_no_cli_bridge"
                if preflight_guard
                else "runner_only_prompt_only_no_cli_bridge"
            ),
            counter_trust_level=(
                "worker_bridge_fixture_compact_trace_audited"
                if worker_cli_bridge_fixture
                else
                str(cli_bridge_trace.get("counter_trust_level"))
                if bridge_trace_observed
                else "runner_bridge_contract_declared_not_executed"
                if cli_bridge_contract
                else
                "fake_worker_fixture_observed"
                if fake_worker
                else "active_user_observation_fixture_audited"
                if active_user_observation_fixture
                else "active_user_assisted_treatment_preflight_external_update_loop_no_worker_observation"
                if active_user_assisted_treatment_preflight
                else "active_bridge_preflight_no_worker_trace"
                if active_cli_bridge_preflight
                else "preflight_prompt_only_no_cli_bridge"
                if preflight_guard
                else "fixture_declared_prompt_only_no_cli_bridge"
            ),
        )
    elif mode == "hardened-codex":
        interaction_counters = build_terminal_bench_goal_harness_interaction_counters(
            prompt_policy_injected=False,
            harness_skill_or_packet_injected=False,
            case_result_writeback="hardened_codex_baseline_runner_only",
            counter_trust_level="hardened_codex_baseline_no_goal_harness_state",
        )
    else:
        interaction_counters = build_terminal_bench_goal_harness_interaction_counters(
            prompt_policy_injected=(mode == "goal-harness-managed-codex"),
            harness_skill_or_packet_injected=False,
            case_result_writeback="runner_only",
        )

    runner_job_name = (
        f"{dataset.replace('@', '_').replace('.', '_')}_"
        f"{str(task_id).replace('-', '_')}_{contract['event_mode']}"
    )
    managed_runner_command_preview = (
        build_terminal_bench_managed_harbor_command(
            dataset=dataset,
            task_id=task_id,
            model=model,
            job_name=runner_job_name,
            goal_harness_mode=(
                "codex_goal_harness"
                if mode == "codex-goal-harness"
                else TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE
                if mode == "hardened-codex"
                else "goal_harness_managed_codex"
            ),
            goal_harness_ablation_mode=(
                "hardened_codex_baseline"
                if mode == "hardened-codex"
                else "goal_harness_managed"
            ),
            goal_harness_access_packet_mode=(
                TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
                if mode == "hardened-codex"
                else TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL
            ),
            goal_harness_cli_bridge_enabled=(
                mode == "codex-goal-harness"
                and (worker_cli_bridge_fixture or active_cli_bridge_preflight)
            ),
            goal_harness_active_user_intervention_enabled=(
                active_user_assisted_treatment_preflight
            ),
            timeout_multiplier=timeout_multiplier,
            agent_timeout_multiplier=agent_timeout_multiplier,
            verifier_timeout_multiplier=verifier_timeout_multiplier,
            agent_setup_timeout_multiplier=agent_setup_timeout_multiplier,
            environment_build_timeout_multiplier=environment_build_timeout_multiplier,
        )
        if mode in (
            "codex-goal-harness",
            "goal-harness-managed-codex",
            "hardened-codex",
        )
        else []
    )
    private_runner_launch_summary: dict[str, Any] = {}
    if mode in (
        "codex-goal-harness",
        "goal-harness-managed-codex",
        "hardened-codex",
    ) and preflight_guard:
        private_runner_launch_summary = summarize_terminal_bench_private_runner_launch(
            build_terminal_bench_private_runner_launch(
                mode=mode,
                dataset=dataset,
                task_id=task_id,
                model=model,
                job_name=runner_job_name,
                goal_harness_cli_bridge_enabled=(
                    mode == "codex-goal-harness"
                    and (worker_cli_bridge_fixture or active_cli_bridge_preflight)
                ),
                goal_harness_active_user_intervention_enabled=(
                    active_user_assisted_treatment_preflight
                ),
                timeout_multiplier=timeout_multiplier,
                agent_timeout_multiplier=agent_timeout_multiplier,
                verifier_timeout_multiplier=verifier_timeout_multiplier,
                agent_setup_timeout_multiplier=agent_setup_timeout_multiplier,
                environment_build_timeout_multiplier=environment_build_timeout_multiplier,
                require_task_material_ready=require_task_material_ready,
            )
        )
        if (
            require_task_material_ready
            and private_runner_launch_summary.get("ready") is not True
            and contract.get("first_blocker")
            == "ready_for_private_managed_no_upload_pilot_review"
        ):
            contract = {
                **contract,
                "first_blocker": str(
                    private_runner_launch_summary.get("first_blocker")
                    or "task_material_not_ready"
                ),
            }

    benchmark_run: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "goal_harness_terminal_bench_cli_skeleton",
        "benchmark_id": dataset,
        "job_name": runner_job_name,
        "mode": contract["event_mode"],
        "worker_mode": contract["worker_mode"],
        "agent": {
            "name": agent,
            "model": model,
            "import_path": (
                TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH
                if mode
                in (
                    "codex-goal-harness",
                    "goal-harness-managed-codex",
                    "hardened-codex",
                )
                else None
            ),
            "kwargs_keys": [
                "goal_harness_mode",
                "goal_harness_access_packet_version",
                "fixture_only",
                "no_upload",
                "single_task_planned",
            ]
            + (
                [
                    "goal_harness_cli_bridge_enabled",
                    "goal_harness_command_prefix",
                    "goal_harness_runtime_preflight_command",
                    "goal_harness_registry_arg",
                    "goal_harness_runtime_root_arg",
                    "goal_harness_benchmark_run_json",
                    "goal_harness_active_user_feed_jsonl",
                    "goal_harness_active_user_observe_command",
                ]
                if active_cli_bridge_preflight or worker_cli_bridge_fixture
                else []
            ),
        },
        "progress": {
            "n_total_trials": 0,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0,
        },
        "interaction_counters": interaction_counters,
        "episode_policy": build_terminal_bench_single_agent_episode_policy(
            active_cli_bridge=active_cli_bridge_preflight or worker_cli_bridge_fixture,
            runner_side_guaranteed_writeback=True,
        ),
        "trials": [
            {
                "task_id": task_id,
                "trial_name": f"{task_id}_{contract['event_mode']}",
                "source": dataset,
                "exception_type": contract["first_blocker"],
                "reward": {
                    "reward": 0,
                },
                "metrics": {
                    "input_tokens": 0,
                    "cache_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0,
                },
                "trajectory_present": False,
                "verifier_reward_present": False,
                "artifact_manifest_present": False,
                "trial_result_present": False,
            }
        ],
        "validation": validation,
        "authorization": {
            "real_case_execution_authorized": False,
            "submit_eligible": False,
        },
        "redaction": {
            "secret_values_recorded": False,
            "raw_sessions_recorded": False,
            "host_paths_recorded": False,
            "raw_prompts_recorded": False,
        },
        "mode_contract": {
            "requested_mode": mode,
            "case_semantics_changed_by_harness": contract["case_semantics_changed_by_harness"],
            "goal_harness_inside_case": contract["goal_harness_inside_case"],
            "official_score_comparable_to_native_codex": contract[
                "official_score_comparable_to_native_codex"
            ],
            "official_score_comparable_to_goal_harness_treatment": contract.get(
                "official_score_comparable_to_goal_harness_treatment", False
            ),
            "model_plus_harness_pair": contract["model_plus_harness_pair"],
            "leaderboard_evidence": False,
            "control_plane_score_applicable": contract["control_plane_score_applicable"],
            "goal_harness_interface_surface": contract.get(
                "goal_harness_interface_surface"
            ),
            "goal_harness_cli_bridge_available": contract.get(
                "goal_harness_cli_bridge_available"
            ),
            "goal_harness_actual_use_observed": contract.get(
                "goal_harness_actual_use_observed", False
            ),
            "startup_surface_calibration": contract.get(
                "startup_surface_calibration", False
            ),
            "hardened_install_surface": contract.get("hardened_install_surface", False),
            "hardened_install_baseline": contract.get(
                "hardened_install_baseline", False
            ),
        },
        "evidence_files": (
            [
                "doc:terminal-bench-goal-harness-access-packet-v0.md",
                "doc:terminal-bench-codex-goal-harness-fake-worker-v0.md",
                "smoke:terminal-bench-codex-goal-harness-fake-worker-smoke.py",
            ]
            if mode == "codex-goal-harness"
            else [
                "doc:terminal-bench-treatment-arm-taxonomy-v0.md",
                "doc:terminal-bench-runner-mode-contract-v0.md",
                "smoke:terminal-bench-treatment-arm-taxonomy-smoke.py",
            ]
            if mode == "hardened-codex"
            else [
                "doc:terminal-bench-runner-mode-contract-v0.md",
                "doc:terminal-bench-cli-dry-run-fake-worker-v0.md",
                "smoke:terminal-bench-cli-dry-run-fake-worker-smoke.py",
            ]
        ),
        "resume_or_inspect_commands": (
            [
                "goal-harness benchmark run terminal-bench --mode codex-goal-harness --fake-worker",
                "goal-harness history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>",
            ]
            if mode == "codex-goal-harness"
            else [
                "goal-harness benchmark run terminal-bench --mode hardened-codex",
                "goal-harness benchmark run terminal-bench --mode hardened-codex --execute",
            ]
            if mode == "hardened-codex"
            else [
                "goal-harness benchmark run terminal-bench --mode goal-harness-managed-codex --fake-worker",
                "goal-harness history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>",
            ]
        ),
        "managed_runner_command_preview": managed_runner_command_preview,
        "private_runner_launch_summary": private_runner_launch_summary,
        "real_run": False,
        "submit_eligible": False,
        "official_task_score": {
            "kind": "not_run",
            "value": None,
        },
        "case_semantics_changed_by_harness": contract["case_semantics_changed_by_harness"],
        "goal_harness_inside_case": contract["goal_harness_inside_case"],
        "official_score_comparable_to_native_codex": contract[
            "official_score_comparable_to_native_codex"
        ],
        "official_score_comparable_to_goal_harness_treatment": contract.get(
            "official_score_comparable_to_goal_harness_treatment", False
        ),
        "model_plus_harness_pair": contract["model_plus_harness_pair"],
        "control_plane_score_applicable": contract["control_plane_score_applicable"],
        "startup_surface_calibration": contract.get("startup_surface_calibration", False),
        "hardened_install_surface": contract.get("hardened_install_surface", False),
        "hardened_install_baseline": contract.get("hardened_install_baseline", False),
        "leaderboard_evidence": False,
        "trace_publicness": contract["trace_publicness"],
        "first_blocker": contract["first_blocker"],
        "stop_conditions": [
            "do_not_run_harbor",
            "do_not_run_terminal_bench",
            "do_not_invoke_real_codex",
            "do_not_start_docker_or_cloud",
            "do_not_call_model_api",
            "do_not_upload_or_submit_leaderboard",
            "do_not_record_secrets_or_raw_sessions",
        ],
    }
    benchmark_run["goal_harness_counter_scope"] = (
        "worker_active_user_observation_fixture"
        if active_user_observation_fixture
        else
        "worker_in_case_cli_bridge_fixture"
        if worker_cli_bridge_fixture
        else "worker_in_case_cli_bridge_preflight"
        if active_cli_bridge_preflight
        else "runner_cli_bridge_contract_fixture"
        if cli_bridge_contract
        else "synthetic_fake_worker"
        if fake_worker and mode == "codex-goal-harness"
        else "prompt_or_runner_fixture"
    )
    benchmark_run["runner_goal_harness_cli_call_total"] = (
        6 if cli_bridge_contract and bridge_trace_observed else 0
    )
    benchmark_run["worker_goal_harness_cli_call_total"] = (
        1
        if active_user_observation_fixture
        else
        6
        if worker_cli_bridge_fixture or (fake_worker and mode == "codex-goal-harness")
        else 0
    )
    benchmark_run["planned_worker_goal_harness_cli_call_total"] = (
        len(TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS)
        if active_cli_bridge_preflight
        else 0
    )
    benchmark_run["required_worker_goal_harness_cli_call_total_min"] = (
        TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM
        if active_cli_bridge_preflight
        else 0
    )
    if active_user_assisted_treatment_preflight:
        injection_channel_probe = build_terminal_bench_active_user_injection_channel_probe(
            active_cli_bridge_preflight=active_cli_bridge_preflight,
        )
        private_launcher_plan = build_terminal_bench_active_user_private_launcher_plan(
            active_cli_bridge_preflight=active_cli_bridge_preflight,
        )
        benchmark_run["active_user_assisted_treatment_preflight"] = {
            "schema_version": TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_SCHEMA,
            "pilot_schema_version": "active_user_assisted_pilot_v0",
            "active_injection_schema_version": "active_user_simulator_injection_v0",
            "operator_simulator_run_schema_version": "operator_simulator_run_v0",
            "simulator_setting": TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_SETTING,
            "proactive_intervention_allowed": True,
            "directive_feedback_allowed": True,
            "artificial_mildness_required": False,
            "frequency_budget_required": True,
            "visibility_policy_required": True,
            "no_oracle_audit_required": True,
            "assisted_collaboration_claim_allowed": True,
            "official_score_claim_allowed": False,
            "leaderboard_claim_allowed": False,
            "simulator_to_worker_injection_channel": injection_channel_probe,
            "private_launcher_plan": private_launcher_plan,
            "next_step": injection_channel_probe["next_channel_requirement"],
        }
        benchmark_run["active_user_private_launcher_plan"] = private_launcher_plan
        benchmark_run["assisted_collaboration_claim_allowed"] = True
        benchmark_run["official_score_claim_allowed"] = False
        benchmark_run["active_user_simulator_injection_channel_available"] = bool(
            injection_channel_probe.get("channel_available")
        )
        if active_user_observation_fixture:
            benchmark_run["active_user_observation"] = (
                build_terminal_bench_active_user_observation_fixture()
            )
    if mode == "codex-goal-harness":
        benchmark_run["goal_harness_access_packet"] = {
            "schema_version": TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION,
            "interface_surface": (
                TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
                if active_cli_bridge_preflight or worker_cli_bridge_fixture
                else TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE
            ),
            "interfaces_available": (
                list(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS)
                if active_cli_bridge_preflight or worker_cli_bridge_fixture
                else []
            ),
            "interfaces_declared": list(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS),
            "worker_default_call_policy": {
                "schema_version": (
                    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_VERSION
                ),
                "mode": TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_MODE,
                "default_required_calls": list(
                    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS
                ),
                "optional_blocked_or_resume_calls": list(
                    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS
                ),
                "required_worker_goal_harness_cli_call_total_min": (
                    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM
                ),
            },
            "goal_harness_cli_bridge_available": (
                True
                if active_cli_bridge_preflight or worker_cli_bridge_fixture
                else TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
            ),
            "goal_harness_cli_bridge_contract": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION
            ),
            "prompt_packet_only_until_cli_bridge": not (
                active_cli_bridge_preflight or worker_cli_bridge_fixture
            ),
            "packet_public_preview": build_terminal_bench_goal_harness_access_packet(
                cli_bridge_available=active_cli_bridge_preflight
                or worker_cli_bridge_fixture,
                active_user_intervention_enabled=active_user_assisted_treatment_preflight,
            ),
            "raw_prompt_recorded": False,
        }
    if cli_bridge_contract:
        benchmark_run["source_runner"] = (
            "goal_harness_terminal_bench_codex_goal_harness_cli_bridge_contract_runner_fixture"
        )
        benchmark_run["goal_harness_cli_bridge_surface"] = (
            TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_SURFACE
        )
        benchmark_run["goal_harness_cli_bridge_contract"] = (
            TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION
        )
        benchmark_run["goal_harness_cli_bridge_contract_available"] = True
        benchmark_run["goal_harness_cli_bridge_trace_observed"] = bridge_trace_observed
        benchmark_run["goal_harness_cli_bridge_scope"] = (
            "host_agent_runner_fixture_no_terminal_bench_worker"
        )
        benchmark_run["goal_harness_cli_bridge_contract_fixture"] = (
            build_terminal_bench_goal_harness_cli_bridge_contract(
                bridge_available=bridge_trace_observed
            )
        )
        if isinstance(cli_bridge_trace, dict):
            benchmark_run["goal_harness_cli_bridge_trace"] = {
                "schema_version": cli_bridge_trace.get("schema_version"),
                "bridge_surface": cli_bridge_trace.get("bridge_surface"),
                "bridge_available": cli_bridge_trace.get("bridge_available"),
                "logical_command_count": cli_bridge_trace.get("logical_command_count"),
                "command_results": cli_bridge_trace.get("command_results"),
            }
        benchmark_run["evidence_files"] = [
            "doc:terminal-bench-goal-harness-cli-bridge-contract-v0.md",
            "doc:terminal-bench-goal-harness-access-packet-v0.md",
            "smoke:terminal-bench-goal-harness-cli-bridge-runner-smoke.py",
        ]
        benchmark_run["resume_or_inspect_commands"] = [
            "goal-harness benchmark run terminal-bench --mode codex-goal-harness --cli-bridge-contract",
            "goal-harness benchmark run terminal-bench --mode codex-goal-harness --cli-bridge-contract --execute",
        ]
    if worker_cli_bridge_fixture:
        benchmark_run["source_runner"] = (
            "goal_harness_terminal_bench_codex_goal_harness_worker_cli_bridge_fixture"
        )
        benchmark_run["goal_harness_cli_bridge_surface"] = (
            TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
        )
        benchmark_run["goal_harness_worker_cli_bridge_available"] = True
        benchmark_run["goal_harness_worker_cli_bridge_trace_observed"] = True
        benchmark_run["goal_harness_cli_bridge_scope"] = (
            "worker_in_case_fixture_no_terminal_bench_task"
        )
        benchmark_run["codex_goal_harness_worker_result"] = {
            "schema_version": "codex_goal_harness_worker_cli_bridge_fixture_v0",
            "mode": "codex_goal_harness",
            "worker_mode": contract["worker_mode"],
            "access_packet_schema_version": (
                TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION
            ),
            "interface_surface": contract["goal_harness_interface_surface"],
            "cli_bridge_available": True,
            "goal_harness_interface_calls_observed": True,
            "runner_goal_harness_cli_call_total": 0,
            "worker_goal_harness_cli_call_total": 6,
            "result": "worker_bridge_fixture_completed_no_official_trial",
        }
        benchmark_run["evidence_files"] = [
            "doc:terminal-bench-codex-goal-harness-active-cli-bridge-v0.md",
            "doc:terminal-bench-goal-harness-cli-bridge-contract-v0.md",
            "smoke:terminal-bench-codex-goal-harness-active-cli-bridge-smoke.py",
        ]
        benchmark_run["resume_or_inspect_commands"] = [
            "goal-harness benchmark run terminal-bench --mode codex-goal-harness --worker-cli-bridge-fixture",
            "goal-harness benchmark run terminal-bench --mode codex-goal-harness --worker-cli-bridge-fixture --execute",
        ]
    if fake_result:
        if mode == "codex-goal-harness":
            benchmark_run["codex_goal_harness_worker_result"] = fake_result
        else:
            benchmark_run["managed_worker_result"] = fake_result
    if preflight_guard:
        if mode == "codex-goal-harness":
            benchmark_run["source_runner"] = (
                "goal_harness_terminal_bench_active_user_assisted_treatment_preflight"
                if active_user_assisted_treatment_preflight
                else "goal_harness_terminal_bench_codex_goal_harness_active_cli_bridge_preflight"
                if active_cli_bridge_preflight
                else "goal_harness_terminal_bench_codex_goal_harness_no_upload_preflight_guard"
            )
            benchmark_run["evidence_files"] = [
                (
                    "doc:active-user-assisted-pilot-v0.md"
                    if active_user_assisted_treatment_preflight
                    else "doc:terminal-bench-codex-goal-harness-active-cli-bridge-v0.md"
                    if active_cli_bridge_preflight
                    else "doc:terminal-bench-codex-goal-harness-preflight-guard-v0.md"
                ),
                "doc:terminal-bench-codex-goal-harness-custom-agent-v0.md",
                (
                    "smoke:terminal-bench-active-user-assisted-treatment-preflight-smoke.py"
                    if active_user_assisted_treatment_preflight
                    else "smoke:terminal-bench-codex-goal-harness-active-cli-bridge-smoke.py"
                    if active_cli_bridge_preflight
                    else "smoke:terminal-bench-codex-goal-harness-preflight-guard-smoke.py"
                ),
            ]
            benchmark_run["resume_or_inspect_commands"] = [
                (
                    "goal-harness benchmark run terminal-bench --mode codex-goal-harness "
                    "--preflight-guard --active-cli-bridge --active-user-assisted-treatment"
                    if active_user_assisted_treatment_preflight
                    else "goal-harness benchmark run terminal-bench --mode codex-goal-harness "
                    "--preflight-guard --active-cli-bridge"
                    if active_cli_bridge_preflight
                    else "goal-harness benchmark run terminal-bench --mode codex-goal-harness --preflight-guard"
                ),
                (
                    "goal-harness benchmark run terminal-bench --mode codex-goal-harness "
                    "--preflight-guard --active-cli-bridge --active-user-assisted-treatment --execute"
                    if active_user_assisted_treatment_preflight
                    else "goal-harness benchmark run terminal-bench --mode codex-goal-harness "
                    "--preflight-guard --active-cli-bridge --execute"
                    if active_cli_bridge_preflight
                    else "goal-harness benchmark run terminal-bench --mode codex-goal-harness --preflight-guard --execute"
                ),
            ]
        elif mode == "hardened-codex":
            benchmark_run["source_runner"] = (
                "goal_harness_terminal_bench_hardened_codex_baseline_preflight_guard"
            )
            benchmark_run["evidence_files"] = [
                "doc:terminal-bench-runner-mode-contract-v0.md",
                "doc:terminal-bench-treatment-arm-taxonomy-v0.md",
                "smoke:terminal-bench-private-runner-env-guard-smoke.py",
            ]
            benchmark_run["resume_or_inspect_commands"] = [
                "goal-harness benchmark run terminal-bench --mode hardened-codex --preflight-guard",
                "goal-harness benchmark run terminal-bench --mode hardened-codex --preflight-guard --execute",
            ]
        else:
            benchmark_run["source_runner"] = "goal_harness_terminal_bench_managed_real_run_preflight_guard"
            benchmark_run["evidence_files"] = [
                "doc:terminal-bench-managed-real-run-preflight-guard-v0.md",
                "doc:terminal-bench-runner-mode-contract-v0.md",
                "smoke:terminal-bench-managed-real-run-preflight-guard-smoke.py",
            ]
            benchmark_run["resume_or_inspect_commands"] = [
                "goal-harness benchmark run terminal-bench --mode goal-harness-managed-codex --preflight-guard",
                "goal-harness benchmark run terminal-bench --mode goal-harness-managed-codex --preflight-guard --execute",
            ]
        benchmark_run["preflight_guard"] = {
            "schema_version": (
                TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_SCHEMA
                if active_user_assisted_treatment_preflight
                else "terminal_bench_codex_goal_harness_active_cli_bridge_preflight_v0"
                if active_cli_bridge_preflight and mode == "codex-goal-harness"
                else
                "terminal_bench_codex_goal_harness_preflight_guard_v0"
                if mode == "codex-goal-harness"
                else "terminal_bench_hardened_codex_baseline_preflight_guard_v0"
                if mode == "hardened-codex"
                else "terminal_bench_managed_real_run_preflight_guard_v0"
            ),
            "runner_surface_checked": True,
            "local_execution_surface_checked": True,
            "codex_cli_surface_checked": True,
            "auth_surface_names_only": True,
            "auth_values_read": False,
            "artifact_redaction_required": True,
            "first_blocker": contract["first_blocker"],
            "task_material_ready_required": require_task_material_ready,
        }
        runner_surface = (
            surface.get("runner_surface")
            if isinstance(surface.get("runner_surface"), dict)
            else {}
        )
        execution_surface = (
            surface.get("execution_surface")
            if isinstance(surface.get("execution_surface"), dict)
            else {}
        )
        codex_surface = (
            surface.get("codex_surface")
            if isinstance(surface.get("codex_surface"), dict)
            else {}
        )
        for source_field, target_field in (
            ("uvx_cli_present", "uvx_cli_present"),
            ("uvx_version_probe_ok", "uvx_version_probe_ok"),
        ):
            if isinstance(runner_surface.get(source_field), bool):
                benchmark_run["preflight_guard"][target_field] = runner_surface[
                    source_field
                ]
        policy = _public_safe_benchmark_label(
            runner_surface.get("runner_binary_resolution_policy"),
            limit=120,
        )
        if policy:
            benchmark_run["preflight_guard"]["runner_binary_resolution_policy"] = policy
        for source_field, target_field in (
            ("docker_cli_present", "docker_cli_present"),
            ("docker_version_probe_ok", "docker_version_probe_ok"),
            ("docker_server_available", "docker_server_available"),
            ("colima_cli_present", "colima_cli_present"),
            ("colima_status_probe_ok", "colima_status_probe_ok"),
        ):
            if isinstance(execution_surface.get(source_field), bool):
                benchmark_run["preflight_guard"][target_field] = execution_surface[
                    source_field
                ]
        for source_field, target_field in (
            ("codex_cli_present", "codex_cli_present"),
            ("codex_version_probe_ok", "codex_version_probe_ok"),
        ):
            if isinstance(codex_surface.get(source_field), bool):
                benchmark_run["preflight_guard"][target_field] = codex_surface[
                    source_field
                ]
        if mode == "codex-goal-harness":
            benchmark_run["preflight_guard"].update(
                {
                    "access_packet_prompt_injection_checked": True,
                    "trace_counter_extraction_contract_checked": True,
                    "goal_harness_mode_kwarg_checked": True,
                    "goal_harness_mode_kwarg": "codex_goal_harness",
                    "active_cli_bridge_enabled": active_cli_bridge_preflight,
                    "worker_cli_bridge_surface": (
                        TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
                        if active_cli_bridge_preflight
                        else None
                    ),
                    "required_worker_goal_harness_cli_call_total_min": (
                        TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM
                        if active_cli_bridge_preflight
                        else 0
                    ),
                    "claim_requires_worker_cli_calls": active_cli_bridge_preflight,
                    "real_interface_use_observed": False,
                    "uplift_claim_allowed": False,
                }
            )
            if active_user_assisted_treatment_preflight:
                injection_channel_probe = build_terminal_bench_active_user_injection_channel_probe(
                    active_cli_bridge_preflight=active_cli_bridge_preflight,
                )
                benchmark_run["preflight_guard"].update(
                    {
                        "active_user_assisted_treatment": True,
                        "simulator_setting": TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_SETTING,
                        "simulator_to_worker_injection_channel_available": bool(
                            injection_channel_probe.get("channel_available")
                        ),
                        "simulator_to_worker_injection_channel": injection_channel_probe,
                        "interactive_user_message_injection_checked": True,
                        "initial_prompt_only_is_not_active_intervention": True,
                        "no_oracle_audit_required": True,
                        "assisted_score_kept_separate_from_official": True,
                    }
                )
        if active_cli_bridge_preflight:
            benchmark_run["goal_harness_cli_bridge_surface"] = (
                TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
            )
            benchmark_run["goal_harness_cli_bridge_scope"] = (
                "planned_worker_in_case_private_no_upload_preflight"
            )
            benchmark_run["goal_harness_worker_cli_bridge_available"] = True
            benchmark_run["goal_harness_worker_cli_bridge_trace_observed"] = False
            benchmark_run["claim_gate"] = {
                "schema_version": "terminal_bench_goal_harness_claim_gate_v0",
                "requires_private_no_upload": True,
                "requires_worker_goal_harness_cli_calls": True,
                "required_worker_goal_harness_cli_call_total_min": (
                    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM
                ),
                "reject_runner_bridge_calls_as_in_case_evidence": True,
                "reject_codex_runtime_goal_tool_calls_as_goal_harness_evidence": True,
                "uplift_claim_allowed": False,
                "leaderboard_claim_allowed": False,
            }
    return benchmark_run


def terminal_bench_recommended_action(
    *,
    fake_worker: bool,
    preflight_guard: bool = False,
    mode: str | None = None,
    cli_bridge_contract: bool = False,
    worker_cli_bridge_fixture: bool = False,
    active_cli_bridge_preflight: bool = False,
    active_user_assisted_treatment_preflight: bool = False,
) -> str:
    if mode == "hardened-codex":
        return "run hardened-codex baseline and codex-goal-harness treatment in parallel on the same hard task; do not launch bare-codex"
    if active_user_assisted_treatment_preflight:
        return "wire the worker prompt to poll active-user-observe, then run a no-upload assisted worker sample that proves after-start simulator observation"
    if active_cli_bridge_preflight:
        return "run the private no-upload codex-goal-harness sample repeat with active worker Goal Harness CLI bridge, then require nonzero worker_goal_harness_cli_calls before any in-case use claim"
    if worker_cli_bridge_fixture:
        return "inspect the codex-goal-harness worker CLI bridge fixture before any private no-upload repeat"
    if cli_bridge_contract:
        return "inspect the codex-goal-harness CLI bridge runner fixture before any private no-upload repeat"
    if preflight_guard and mode == "codex-goal-harness":
        return "review the codex-goal-harness no-upload preflight guard before any real sample repeat"
    if preflight_guard:
        return "review the managed real-run preflight guard before any real managed benchmark execution"
    if fake_worker and mode == "codex-goal-harness":
        return "inspect codex_goal_harness fake-worker counters before any real benchmark repeat"
    if fake_worker:
        return "inspect fake managed wrapper CLI event before any real managed benchmark case"
    return "inspect terminal-bench CLI dry-run event and keep real benchmark execution gated"
