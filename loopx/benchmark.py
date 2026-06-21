from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .worker_bridge import (
    ACTIVE_USER_INTERVENTION_CHANNEL_CONTRACT_VERSION,
    ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
    ACTIVE_USER_INTERVENTION_OBSERVATION_VERSION,
    WORKER_BRIDGE_BENCHMARK_RUN_FORBIDDEN_PUBLIC_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_FIXED_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_TOP_LEVEL_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION,
    WORKER_BRIDGE_SURFACE,
    build_active_user_codex_simulator_contract,
    build_active_user_intervention,
    build_worker_bridge_install_contract,
)
from .benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS,
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_init_contract,
    benchmark_case_active_state_path,
    benchmark_case_goal_id,
)
from .benchmark_core import (
    BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION,
    build_benchmark_candidate_source_boundary,
    classify_benchmark_artifact_path,
    classify_benchmark_candidate_source_path,
    canonical_lifecycle,
    filter_public_benchmark_artifact_paths,
)
from .benchmark_core.io import (
    load_json_object as _load_json_object,
    load_jsonl_objects as _load_jsonl_objects,
    optional_float as _optional_float,
    optional_positive_int as _optional_positive_int,
)
from .benchmark_adapters.agentissue import (
    AGENTISSUE_BENCHMARK_ID,
    AGENTISSUE_CODEX_CLI_RUNNER_EXECUTION_GATE_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_FIRST_RUN_HANDOFF_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_PRIVATE_SCRIPT_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_REAL_RESULT_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_RUN_GATE_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_SYNTHETIC_STAGING_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_TARGET_HANDOFF_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_WORKFLOW_CHECK_SCHEMA_VERSION,
    AGENTISSUE_CODEX_CLI_RUNNER_WRAPPER_SCHEMA_VERSION,
    AGENTISSUE_DEFAULT_TAG,
    build_agentissue_codex_cli_runner_wrapper,
    materialize_agentissue_codex_cli_runner_execution_gate,
    materialize_agentissue_codex_cli_runner_first_run_handoff,
    materialize_agentissue_codex_cli_runner_private_script,
    materialize_agentissue_codex_cli_runner_real_result,
    materialize_agentissue_codex_cli_runner_run_gate,
    materialize_agentissue_codex_cli_runner_synthetic_staging,
    materialize_agentissue_codex_cli_runner_target_handoff,
    materialize_agentissue_codex_cli_runner_workflow_check,
)
from .benchmark_adapters.skillsbench import (
    BENCHMARK_MODEL_CONTROL_SCHEMA_VERSION,
    CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL,
    SKILLSBENCH_DEFAULT_DATASET,
    SKILLSBENCH_DEFAULT_MODEL,
    SKILLSBENCH_DEFAULT_ROUTE,
    SKILLSBENCH_DEFAULT_TASK,
    SKILLSBENCH_LOCAL_DRIVER_A2A_CONTRACT_SCHEMA_VERSION,
    SKILLSBENCH_LOCAL_DRIVER_A2A_PAIR_ROUTES,
    SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION,
    SKILLSBENCH_WORKER_HANDSHAKE_PREFLIGHT_SCHEMA_VERSION,
    SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID,
    SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH,
    SKILLSBENCH_ROUTES,
    build_skillsbench_benchmark_run,
    build_skillsbench_app_server_goal_worker_contract,
    build_skillsbench_benchflow_result_benchmark_run,
    build_skillsbench_local_driver_a2a_contract,
    build_skillsbench_worker_handshake_preflight,
    skillsbench_recommended_action,
    skillsbench_job_name,
    skillsbench_route_contract,
    skillsbench_runner_error_attribution,
    skillsbench_runner_error_fingerprint,
)
from .benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET,
    TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    TERMINAL_BENCH_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    TERMINAL_BENCH_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_HOST_DIR_PLACEHOLDER,
    TERMINAL_BENCH_WORKER_BRIDGE_PROJECT_ROOT_PLACEHOLDER,
    TERMINAL_BENCH_WORKER_BRIDGE_RUNTIME_ROOT_PLACEHOLDER,
    TERMINAL_BENCH_MODES,
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_TASK,
    TERMINAL_BENCH_DEFAULT_MODEL,
    TERMINAL_BENCH_CASE_GOAL_ID,
    TERMINAL_BENCH_CASE_STATE_PATH,
    TERMINAL_BENCH_HARBOR_REF,
    TERMINAL_BENCH_PREFLIGHT_MODE,
    TERMINAL_BENCH_CODEX_LOOPX_PREFLIGHT_MODE,
    TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_MODE,
    TERMINAL_BENCH_ACTIVE_USER_ASSISTED_TREATMENT_PREFLIGHT_SCHEMA,
    TERMINAL_BENCH_ACTIVE_USER_ASSISTED_OBSERVATION_FIXTURE_MODE,
    TERMINAL_BENCH_ACTIVE_USER_ASSISTED_OBSERVATION_FIXTURE_SCHEMA,
    TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_CHANNEL_SCHEMA,
    TERMINAL_BENCH_ACTIVE_USER_PRIVATE_LAUNCHER_PLAN_SCHEMA,
    TERMINAL_BENCH_TASK_MATERIAL_READINESS_SCHEMA,
    TERMINAL_BENCH_POST_LAUNCH_MATERIALIZATION_SCHEMA,
    TERMINAL_BENCH_COMPACT_FAILURE_MARKER_SCHEMA,
    TERMINAL_BENCH_RESULT_FINALIZATION_GATE_SCHEMA,
    TERMINAL_BENCH_RUN_LEDGER_CLOSEOUT_SCHEMA,
    TERMINAL_BENCH_ENVIRONMENT_SETUP_READINESS_SCHEMA,
    TERMINAL_BENCH_ENVIRONMENT_SETUP_PROBE_GATE_SCHEMA,
    TERMINAL_BENCH_ENVIRONMENT_SETUP_PROBE_LAUNCH_SCHEMA,
    TERMINAL_BENCH_CASE_RUN_LAUNCH_SCHEMA,
    TERMINAL_BENCH_LAUNCH_MATERIALIZATION_OBSERVATION_SCHEMA,
    TERMINAL_BENCH_AGENT_SETUP_READINESS_SCHEMA,
    TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA,
    TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_PROFILE_SCHEMA,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
    TERMINAL_BENCH_CODEX_RUNTIME_INSTALL_ALLOW_ENVIRONMENT_HOSTS,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
    TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_AGENT_TIMEOUT_MULTIPLIER,
    TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_AGENT_SETUP_TIMEOUT_MULTIPLIER,
    TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC,
    TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE,
    TERMINAL_BENCH_DETACHED_PROCESS_STATES,
    TERMINAL_BENCH_ACTIVE_JOB_STALE_SECONDS,
    TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_SETTING,
    TERMINAL_BENCH_ACTIVE_USER_SIMULATOR_INJECTION_FIRST_BLOCKER,
    TERMINAL_BENCH_ACTIVE_USER_REAL_WORKER_OBSERVATION_FIRST_BLOCKER,
    TERMINAL_BENCH_ACTIVE_USER_OBSERVATION_FIXTURE_FIRST_BLOCKER,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_PREFLIGHT_MODE,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE,
    TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE,
    TERMINAL_BENCH_HARDENED_CODEX_LEGACY_CALIBRATION_MODE,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE,
    TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE,
    TERMINAL_BENCH_HARDENED_CODEX_CALIBRATION_MODE,
    TERMINAL_BENCH_HARDENED_CODEX_CALIBRATION_SURFACE,
    TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH,
    TERMINAL_BENCH_MANAGED_POLICY_VERSION,
    TERMINAL_BENCH_MANAGED_BEHAVIOR_SPEC_ID,
    TERMINAL_BENCH_MANAGED_CODEX_LOOPX_KWARGS,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_VERSION,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_FULL,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODES,
    TERMINAL_BENCH_LOOPX_INTERACTION_COUNTERS_VERSION,
    TERMINAL_BENCH_OVERHEAD_ATTRIBUTION_COUNTERS_VERSION,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS,
    TERMINAL_BENCH_LOOPX_ACTIVE_USER_OBSERVE_COMMAND,
    TERMINAL_BENCH_LOOPX_COUNTER_TRACE_COMMANDS,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CALL_POLICY_VERSION,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CALL_POLICY_MODE,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_REQUIRED_CALL_MINIMUM,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_PLACEHOLDER_POLICY_VERSION,
    TERMINAL_BENCH_LOOPX_INTERFACE_SURFACE,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_AVAILABLE,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_SURFACE,
    TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE,
    TERMINAL_BENCH_CODEX_AUTH_SURFACE_NAMES,
    TERMINAL_BENCH_BOOL_AGENT_ENV_NAMES,
    TERMINAL_BENCH_BOOL_AGENT_ENV_VALUES,
    TERMINAL_BENCH_REDACTED_ENV_VALUE_MARKERS,
    TERMINAL_BENCH_EXTRA_PROBE_PATHS,
    TERMINAL_BENCH_COUNTER_TRACE_FILE,
    TERMINAL_BENCH_WORKER_BENCHMARK_RUN_FILE,
    TERMINAL_BENCH_DEFAULT_AGENT_TIMEOUT_SECONDS,
    TERMINAL_BENCH_TRUE_LONG_TASK_BAR_SECONDS,
    TERMINAL_BENCH_PREFERRED_HOURS_SCALE_BAR_SECONDS,
    TERMINAL_BENCH_OFFICIAL_TIMEOUT_MULTIPLIER,
    TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_TIMEOUT_MULTIPLIER,
    TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_SETUP_TIMEOUT_MULTIPLIER,
    TERMINAL_BENCH_EPISODE_POLICY_VERSION,
    TERMINAL_BENCH_EPISODE_POLICY_MODE,
    TERMINAL_BENCH_DEFAULT_EPISODE_CHECKPOINT_INTERVAL_SECONDS,
    TERMINAL_BENCH_TIMEOUT_MULTIPLIER_KEYS,
    TERMINAL_BENCH_VERIFIER_FAILURE_LOG_FILES,
    TERMINAL_BENCH_VERIFIER_FAILURE_GLOB_PATTERNS,
    TERMINAL_BENCH_CODEX_RUNTIME_GOAL_TOOL_NAMES,
    TERMINAL_BENCH_WORKER_CASE_SUCCESS_VALIDATION_SCOPES,
    TERMINAL_BENCH_WORKER_CONNECTIVITY_VALIDATION_SCOPES,
    TERMINAL_BENCH_NON_BLOCKING_WORKER_SETUP_LABELS,
    _compact_exception_kind,
    _terminal_bench_agent_failure_attribution_labels,
    agent_kwargs_from_invocation,
    _compact_truthy_flag,
    _terminal_bench_lock_first_agent_kwargs,
    _terminal_bench_lock_worker_materialization_probe_only,
    _compact_positive_int,
    _benchmark_lifecycle_ready_preflight,
    _benchmark_run_environment_setup_failure_context,
    _terminal_bench_harbor_run_help_capability,
    _terminal_bench_environment_setup_probe_command_template,
    build_terminal_bench_environment_setup_probe_gate,
    launch_terminal_bench_environment_setup_probe,
    launch_terminal_bench_worker_materialization_probe,
    _detached_process_state_from_pid_file,
    _process_state_from_poll,
    wait_for_terminal_bench_launch_materialization,
    observe_terminal_bench_post_materialization_closeout,
    build_terminal_bench_harbor_resume_command,
    _terminal_bench_resume_recommended,
    _terminal_bench_active_job_resume_contract,
    resume_terminal_bench_materialized_job,
    summarize_terminal_bench_prelaunch_job_root_guard,
    launch_terminal_bench_case_run,
    poll_terminal_bench_worker_materialization_probe,
    build_terminal_bench_result_finalization_gate,
    build_terminal_bench_active_user_injection_channel_probe,
    build_terminal_bench_active_user_observation_fixture,
    _empty_codex_runtime_goal_tool_calls,
    _merge_numeric_counts,
    _compact_trace_event_text,
    _trajectory_codex_runtime_goal_tool_calls,
    _terminal_bench_verifier_failure_attribution,
    _terminal_bench_score_failure_attribution,
    _terminal_bench_worker_validation_claim_kind,
    _is_pre_worker_agent_setup_failure,
    _is_environment_setup_failure_before_worker,
    _terminal_bench_duration_tier,
    _terminal_bench_environment_setup_failure_context,
    _compactable_benchmark_run_v0_payload,
    _terminal_bench_non_blocking_setup_label,
    _terminal_bench_worker_materialization_probe_contract,
    _terminal_bench_worker_startup_blocker,
    _invocation_arg_value,
    _redacted_agent_kwargs,
    _numeric_metric_totals,
    _reward_from_trial_result,
    _first_numeric_reward,
    _terminal_bench_finished_phase,
    _terminal_bench_official_zero_observation,
    _official_score_from_harbor_stats,
    _numeric_reward_value,
    _iso_duration_seconds,
    _first_timeout_multiplier,
    _is_default_timeout_multiplier,
    _format_harbor_multiplier,
    _terminal_bench_dataset_args,
    _public_safe_benchmark_label,
    build_terminal_bench_single_agent_episode_policy,
    _terminal_bench_timeout_policy,
    _counter_trace_interaction_counters,
    _total_from_counter_map,
    _terminal_bench_overhead_attribution_counters,
    build_terminal_bench_harbor_result_benchmark_run,
    _probe_path,
    _probe_env,
    _looks_like_redacted_env_value,
    _split_env_assignment,
    sanitize_terminal_bench_private_runner_env,
    _prepend_env_path_entry,
    build_terminal_bench_private_runner_env,
    _apply_terminal_bench_private_default_timeout_policy,
    _private_runner_loopx_project_root,
    _private_runner_loopx_runtime_root,
    _private_runner_active_user_host_dir,
    _private_runner_absolute_jobs_dir,
    _private_runner_command_kwargs,
    build_terminal_bench_task_material_readiness,
    _terminal_bench_setup_timeout_repair_profile,
    build_terminal_bench_private_runner_launch,
    _terminal_bench_run_ledger_closeout_templates,
    _terminal_bench_compact_failure_marker,
    summarize_terminal_bench_post_launch_materialization,
    _terminal_bench_launch_timeout_multiplier_policy,
    _terminal_bench_agent_setup_readiness,
    summarize_terminal_bench_private_runner_launch,
    normalize_terminal_bench_private_runner_invocation,
    _command_present,
    resolve_terminal_bench_runner_binary,
    _probe_command,
    collect_terminal_bench_managed_preflight_surface,
    _managed_preflight_first_blocker,
    build_terminal_bench_loopx_interaction_counters,
    build_terminal_bench_loopx_cli_bridge_contract,
    build_terminal_bench_case_state_init_contract,
    collect_terminal_bench_loopx_cli_bridge_trace,
    build_terminal_bench_active_user_private_launcher_plan,
    build_terminal_bench_loopx_access_packet,
    build_terminal_bench_loopx_access_packet_fixture,
    _mode_contract,
    build_terminal_bench_managed_harbor_command,
    build_terminal_bench_benchmark_run,
    terminal_bench_recommended_action,

)
from .benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_BENCHMARK_ID,
    AGENTS_LAST_EXAM_RESULT_INGEST_POLICY_VERSION,
    AGENTS_LAST_EXAM_LOCAL_PREFLIGHT_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_LOCAL_DRY_RUN_PLAN_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_LOCAL_RUNNER_READINESS_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_LOCAL_SOURCE_READINESS_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION,
    AGENTS_LAST_EXAM_TRACE_PUBLICNESS,
    AGENTS_LAST_EXAM_CASE_GOAL_ID,
    AGENTS_LAST_EXAM_CASE_STATE_PATH,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED,
    _AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE,
    _agents_last_exam_public_id,
    _agents_last_exam_first_public_id,
    _agents_last_exam_parse_int,
    build_agents_last_exam_local_exact_dry_run_result,
    _agents_last_exam_event_type_counts,
    _agents_last_exam_nested,
    _agents_last_exam_docker_image_metadata,
    _agents_last_exam_public_image_metadata,
    _agents_last_exam_disk_headroom,
    build_agents_last_exam_local_preflight,
    build_agents_last_exam_local_dry_run_plan,
    _agents_last_exam_runner_binary_probe,
    _agents_last_exam_python_module_probe,
    _agents_last_exam_runner_binary_requires_python_module,
    _agents_last_exam_codex_cli_probe,
    _agents_last_exam_cua_mcp_assets_probe,
    build_agents_last_exam_host_codex_cli_route,
    _agents_last_exam_codex_exec_surface_probe,
    _agents_last_exam_codex_mcp_config_probe,
    _agents_last_exam_fake_cua_server,
    _agents_last_exam_cua_mcp_test_probe,
    build_agents_last_exam_host_codex_cua_no_task_smoke,
    build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment,
    _agents_last_exam_boundary_flag,
    _agents_last_exam_ready_input,
    _agents_last_exam_source_freshness_input,
    _agents_last_exam_case_state_init_contract_input,
    build_agents_last_exam_validation_run_gate,
    _agents_last_exam_normalized_repo_label,
    _agents_last_exam_source_git_metadata,
    build_agents_last_exam_local_source_readiness,
    _agents_last_exam_public_task_parts,
    _agents_last_exam_public_task_list_membership,
    _agents_last_exam_bool_requirement,
    build_agents_last_exam_baked_task_input_readiness,
    build_agents_last_exam_baked_task_input_scan,
    _agents_last_exam_task_data_source_readiness,
    build_agents_last_exam_task_material_readiness,
    _agents_last_exam_public_selected_task_scan,
    _agents_last_exam_requires_task_data_line_scan,
    build_agents_last_exam_candidate_task_data_scan,
    _agents_last_exam_relative_file_probe,
    build_agents_last_exam_local_launch_packet,
    build_agents_last_exam_local_runner_readiness,
    build_agents_last_exam_result_benchmark_report,
)


BENCHMARK_CLAIM_REVIEW_SCHEMA_VERSION = "benchmark_claim_review_v0"
BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION = "benchmark_learning_ledger_v0"
BENCHMARK_ATTEMPT_LEARNING_GATE_SCHEMA_VERSION = (
    "benchmark_attempt_learning_gate_v0"
)
BENCHMARK_ADAPTER_KWARG_ABSORPTION_REVIEW_SCHEMA_VERSION = (
    "benchmark_adapter_kwarg_absorption_review_v0"
)
BENCHMARK_VERIFIER_ATTRIBUTION_REVIEW_SCHEMA_VERSION = (
    "benchmark_verifier_attribution_review_v0"
)
BENCHMARK_RUNNER_INVARIANT_REVIEW_SCHEMA_VERSION = (
    "benchmark_runner_invariant_review_v0"
)
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
    calls = interaction.get("loopx_cli_calls") if isinstance(interaction.get("loopx_cli_calls"), dict) else {}
    worker_cli_total = run.get("worker_loopx_cli_call_total")
    if not isinstance(worker_cli_total, int) or isinstance(worker_cli_total, bool):
        worker_cli_total = calls.get("total", 0)
    if not isinstance(worker_cli_total, int) or isinstance(worker_cli_total, bool):
        worker_cli_total = 0
    controller_action_decisions = interaction.get("controller_action_decisions")
    if not isinstance(controller_action_decisions, int) or isinstance(
        controller_action_decisions, bool
    ):
        controller_action_decisions = 0
    heartbeat_count = interaction.get("heartbeat_count")
    if not isinstance(heartbeat_count, int) or isinstance(heartbeat_count, bool):
        heartbeat_count = 0
    state_reads = interaction.get("loopx_state_reads")
    if not isinstance(state_reads, int) or isinstance(state_reads, bool):
        state_reads = 0
    state_writes = interaction.get("loopx_state_writes")
    if not isinstance(state_writes, int) or isinstance(state_writes, bool):
        state_writes = 0
    outer_controller_present = bool(
        interaction.get("loopx_automation_loop") is True
        and (
            interaction.get("controller_trace_present") is True
            or controller_action_decisions > 0
            or heartbeat_count > 0
            or state_reads > 0
            or state_writes > 0
        )
    )
    observation = run.get("active_user_observation") if isinstance(run.get("active_user_observation"), dict) else {}
    worker_file_count = run.get("worker_benchmark_run_schema_ok_count")
    if not isinstance(worker_file_count, int) or isinstance(worker_file_count, bool):
        worker_file_count = 0
    present = bool(
        worker_cli_total > 0
        or worker_file_count > 0
        or outer_controller_present
        or observation.get("observed_after_worker_start")
        or observation.get("worker_observation_proof")
    )
    return {
        "worker_loopx_cli_call_total": worker_cli_total,
        "worker_benchmark_run_schema_ok_count": worker_file_count,
        "outer_loopx_controller_present": outer_controller_present,
        "outer_loopx_controller_action_decisions": controller_action_decisions,
        "outer_loopx_heartbeat_count": heartbeat_count,
        "loopx_state_reads": state_reads,
        "loopx_state_writes": state_writes,
        "active_user_observed_after_worker_start": bool(
            observation.get("observed_after_worker_start")
            or observation.get("worker_observation_proof")
        ),
        "present": present,
    }


def _compact_worker_start_status_kind(worker_start_status: Any) -> str:
    """Classify compact worker-start state emitted by runner reducers."""

    if not isinstance(worker_start_status, str) or not worker_start_status.strip():
        return ""
    status = worker_start_status.strip()
    if status == "pre_worker_agent_setup_failed":
        return "agent_setup_failure"
    if status == "environment_setup_failed_before_worker":
        return "environment_setup_failure"
    return ""


def _claim_review_exception_kind_count(run: dict[str, Any], kind: str) -> int:
    trials = run.get("trials")
    if not isinstance(trials, list):
        return 0
    return sum(
        1
        for trial in trials
        if isinstance(trial, dict)
        and _compact_exception_kind(trial.get("exception_type")) == kind
    )


def _claim_review_worker_start_status_kind_count(
    run: dict[str, Any],
    kind: str,
) -> int:
    trials = run.get("trials")
    count = 0
    if isinstance(run.get("worker_start_status"), str):
        count += int(_compact_worker_start_status_kind(run.get("worker_start_status")) == kind)
    if not isinstance(trials, list):
        return count
    return count + sum(
        1
        for trial in trials
        if isinstance(trial, dict)
        and _compact_worker_start_status_kind(trial.get("worker_start_status")) == kind
    )


def _claim_review_worker_startup_blocker_observed(run: dict[str, Any]) -> bool:
    if _compact_positive_int(run.get("worker_startup_blocker_count")):
        return True
    for field in (
        "worker_bridge_materialization_status",
        "worker_bridge_materialization_blocker",
        "pre_worker_startup_blocker",
        "first_blocker",
        "repeat_blocked_by",
    ):
        value = run.get(field)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            if text == "pre_worker_startup_blocker_recorded":
                return True
            if field == "pre_worker_startup_blocker" and text != "none":
                return True
    outcome = run.get("worker_bridge_outcome")
    if isinstance(outcome, dict):
        return _claim_review_worker_startup_blocker_observed(outcome)
    return False


def _claim_review_failure_labels(run: dict[str, Any]) -> list[str]:
    labels = run.get("failure_attribution_labels")
    compact_labels = [
        str(label)
        for label in labels or []
        if isinstance(label, (str, int, float)) and not isinstance(label, bool)
    ] if isinstance(labels, list) else []
    if _claim_review_exception_kind_count(run, "agent_setup_timeout"):
        compact_labels.append("agent_setup_timeout_before_worker_start")
    if _claim_review_exception_kind_count(run, "agent_setup_failure"):
        compact_labels.append("agent_setup_failed_before_worker_start")
    if _claim_review_agent_timeout_count(run):
        compact_labels.append("agent_timeout_before_solution_completion")
    if _claim_review_worker_start_status_kind_count(run, "agent_setup_failure"):
        compact_labels.append("agent_setup_failed_before_worker_start")
    if _claim_review_worker_start_status_kind_count(run, "environment_setup_failure"):
        compact_labels.append("environment_setup_failed_before_worker")
    if _claim_review_worker_startup_blocker_observed(run):
        compact_labels.append("pre_worker_startup_blocker_recorded")
    return list(dict.fromkeys(compact_labels))[:8]


def _claim_review_agent_timeout_count(run: dict[str, Any]) -> int:
    return _claim_review_exception_kind_count(run, "agent_timeout")


def _claim_review_score_failure_attribution(run: dict[str, Any]) -> str:
    value = run.get("score_failure_attribution")
    text = str(value).strip() if isinstance(value, str) and value.strip() else "none"
    if text == "none" and _claim_review_exception_kind_count(run, "agent_setup_timeout"):
        return "agent_setup_timeout_score_failure"
    if text == "none" and _claim_review_exception_kind_count(run, "agent_setup_failure"):
        return "agent_setup_score_failure"
    if text == "none" and (
        _claim_review_worker_start_status_kind_count(run, "agent_setup_failure")
        or _claim_review_worker_start_status_kind_count(
            run,
            "environment_setup_failure",
        )
        or _claim_review_worker_startup_blocker_observed(run)
    ):
        return "agent_setup_score_failure"
    if text == "none" and _claim_review_agent_timeout_count(run):
        return "agent_timeout_score_failure"
    return text


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
            "codex-loopx" in mode
            or "codex-loopx" in job_name
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
        blockers.append("missing_treatment_worker_loopx_evidence")
    if official_delta is not None and official_delta > 0 and attribution_caveat:
        blockers.append("baseline_failure_attribution_caveat")
    if boundary_mismatch_count:
        blockers.append("worker_submit_eligible_boundary_mismatch")

    positive_delta = official_delta is not None and official_delta > 0
    assisted_evidence = bool(treatment_evidence.get("present"))
    clean_validation = positive_delta and assisted_evidence and not blockers
    candidate_validation = positive_delta and assisted_evidence
    if clean_validation:
        claim_strength = "strong_loopx_assisted_score_recovery"
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
    elif "missing_treatment_worker_loopx_evidence" in blockers:
        next_action = "collect compact worker-visible LoopX evidence before claiming assisted recovery"
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


def _learning_ledger_failure_labels(
    benchmark_comparison: dict[str, Any],
    runs: Iterable[dict[str, Any]],
) -> set[str]:
    labels = set(
        item
        for item in benchmark_comparison.get("failure_attribution_labels") or []
        if isinstance(item, str)
    )
    for run in runs:
        labels.update(_claim_review_failure_labels(run))
        first_blocker = run.get("first_blocker")
        if isinstance(first_blocker, str) and first_blocker:
            labels.add(first_blocker)
        worker_start_status = run.get("worker_start_status")
        if isinstance(worker_start_status, str) and worker_start_status:
            labels.add(worker_start_status)
    return labels


def _learning_ledger_repair_candidates(
    claim_review: dict[str, Any],
    benchmark_comparison: dict[str, Any],
    runs: Iterable[dict[str, Any]],
) -> list[str]:
    labels = _learning_ledger_failure_labels(benchmark_comparison, runs)
    blockers = set(
        item
        for item in (
            (claim_review.get("decision") or {}).get("blockers")
            if isinstance(claim_review.get("decision"), dict)
            else []
        )
        if isinstance(item, str)
    )
    candidates: list[str] = []

    environment_setup_failed = "environment_setup_failed_before_worker" in labels
    if environment_setup_failed:
        candidates.append("benchmark_environment_setup_contract")
    if not environment_setup_failed and any(
        label in labels
        for label in (
            "pre_worker_agent_setup_failed",
            "treatment_pre_worker_agent_setup_failed",
            "agent_setup_timeout_before_worker_start",
            "agent_setup_failed_before_worker_start",
            "pre_worker_startup_blocker_recorded",
            "agent_setup_timeout_score_failure",
            "agent_setup_score_failure",
        )
    ):
        candidates.append("adapter_startup_argument_contract")
    if any(
        label in labels
        for label in (
            "runner_compact_result_missing",
            "harbor_job_root_missing",
            "post_launch_job_dir_materialization_missing",
            "reducer_validation_failed",
        )
    ):
        candidates.append("benchmark_lifecycle_materialization_gate")
    if "worker_submit_eligible_boundary_mismatch" in blockers:
        candidates.append("runner_owned_submit_boundary_invariant")
    if "missing_treatment_worker_loopx_evidence" in blockers:
        candidates.append("worker_visible_loopx_evidence_gate")
    if "baseline_failure_attribution_caveat" in blockers:
        candidates.append("compact_verifier_attribution_review")
    if not candidates and bool(
        (claim_review.get("treatment_worker_evidence") or {}).get("present")
        if isinstance(claim_review.get("treatment_worker_evidence"), dict)
        else False
    ):
        candidates.append("claim_cost_overhead_guard")
    return candidates


def _learning_ledger_overhead_label(
    official_delta: float | None,
    cost_delta: float | None,
    wall_time_delta: float | None,
) -> str:
    extra_cost = cost_delta is not None and cost_delta > 0
    extra_time = wall_time_delta is not None and wall_time_delta > 0
    positive_delta = official_delta is not None and official_delta > 0
    if extra_cost and not positive_delta:
        return "extra_cost_without_official_gain"
    if extra_time and not positive_delta:
        return "extra_wall_time_without_official_gain"
    if (extra_cost or extra_time) and positive_delta:
        return "positive_delta_with_overhead"
    if cost_delta is not None and cost_delta < 0:
        return "treatment_cheaper"
    return "overhead_not_material_or_unknown"


def _learning_ledger_only_claim_cost_overhead_guard(
    repair_candidates: list[str],
) -> bool:
    return repair_candidates == ["claim_cost_overhead_guard"]


def _learning_ledger_lifecycle_gate(
    benchmark_comparison: dict[str, Any],
) -> dict[str, Any]:
    official_delta = benchmark_comparison.get("official_task_score_delta")
    labels = benchmark_comparison.get("failure_attribution_labels")
    compact_blocker = isinstance(labels, list) and bool(labels)
    compact_score = _claim_review_numeric(official_delta) is not None
    budget_count_allowed = compact_score or compact_blocker
    return {
        "schema_version": "benchmark_lifecycle_gate_v0",
        "paired_comparison_present": True,
        "compact_score_or_blocker_present": budget_count_allowed,
        "budget_count_allowed": budget_count_allowed,
        "blocked_reason": None
        if budget_count_allowed
        else "missing_compact_score_or_blocker_evidence",
    }


def _learning_ledger_learning_quota_gate(
    *,
    lifecycle_gate: dict[str, Any],
    repair_candidates: list[str],
    clean_validation: bool,
    validation_candidate: bool,
) -> dict[str, Any]:
    actionable_reasons: list[str] = []
    if repair_candidates:
        actionable_reasons.append("generic_repair_candidate")
    if clean_validation:
        actionable_reasons.append("clean_score_recovery_evidence")
    elif validation_candidate:
        actionable_reasons.append("candidate_score_recovery_needs_review")

    lifecycle_ready = bool(lifecycle_gate.get("budget_count_allowed"))
    actionable = bool(actionable_reasons)
    if not lifecycle_ready:
        blocked_reason = "missing_compact_score_or_blocker_evidence"
    elif not actionable:
        blocked_reason = "compact_result_has_no_loopx_learning_signal"
    else:
        blocked_reason = None

    return {
        "schema_version": "benchmark_learning_quota_gate_v0",
        "actionable_learning_present": actionable,
        "spend_allowed": lifecycle_ready and actionable,
        "actionable_reasons": actionable_reasons,
        "blocked_reason": blocked_reason,
    }


def build_benchmark_learning_ledger(
    benchmark_comparison: dict[str, Any],
    *,
    benchmark_runs: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Build a compact benchmark learning row from public-safe summaries."""

    runs = [run for run in benchmark_runs if isinstance(run, dict)]
    claim_review = build_benchmark_claim_review(
        benchmark_comparison,
        benchmark_runs=runs,
    )
    official_delta = claim_review.get("official_task_score_delta")
    official_delta_num = (
        official_delta if isinstance(official_delta, (int, float)) else None
    )
    cost_delta = _claim_review_numeric(benchmark_comparison.get("cost_delta_usd"))
    wall_time_delta = _claim_review_numeric(
        benchmark_comparison.get("wall_time_delta_seconds")
        or benchmark_comparison.get("with_loopx_overhead_ms")
    )
    repair_candidates = _learning_ledger_repair_candidates(
        claim_review,
        benchmark_comparison,
        runs,
    )
    lifecycle_gate = _learning_ledger_lifecycle_gate(benchmark_comparison)
    decision = (
        claim_review.get("decision")
        if isinstance(claim_review.get("decision"), dict)
        else {}
    )
    clean = bool(decision.get("clean_validation_enhancement"))
    validation_candidate = bool(decision.get("validation_enhancement_candidate"))
    overhead_guard_only = _learning_ledger_only_claim_cost_overhead_guard(
        repair_candidates
    )
    if clean:
        learning_status = "clean_score_recovery_evidence"
    elif overhead_guard_only:
        learning_status = "loop_validation_cost_overhead_guard"
    elif repair_candidates:
        learning_status = "generic_loopx_repair_or_attribution_required"
    elif validation_candidate:
        learning_status = "candidate_score_recovery_needs_review"
    elif bool(
        (claim_review.get("treatment_worker_evidence") or {}).get("present")
        if isinstance(claim_review.get("treatment_worker_evidence"), dict)
        else False
    ):
        learning_status = "loop_validation_or_overhead_evidence_only"
    else:
        learning_status = "no_loopx_validation_gain"
    learning_quota_gate = _learning_ledger_learning_quota_gate(
        lifecycle_gate=lifecycle_gate,
        repair_candidates=repair_candidates,
        clean_validation=clean,
        validation_candidate=validation_candidate,
    )

    if overhead_guard_only:
        next_allowed_action = (
            "select_next_candidate_or_add_named_cost_control_hypothesis_before_repeat"
        )
        repeat_allowed = False
    elif repair_candidates:
        next_allowed_action = f"repair_or_validate_{repair_candidates[0]}"
        repeat_allowed = False
    elif not lifecycle_gate["budget_count_allowed"]:
        next_allowed_action = "write_compact_blocker_before_repeat_or_new_candidate"
        repeat_allowed = False
    elif not learning_quota_gate["spend_allowed"]:
        next_allowed_action = "stop_without_spend_and_record_no_learning_signal"
        repeat_allowed = False
    elif clean:
        next_allowed_action = "record_clean_evidence_then_select_next_benchmark_lane"
        repeat_allowed = True
    else:
        next_allowed_action = "only_repeat_with_named_attribution_or_stability_hypothesis"
        repeat_allowed = True

    return {
        "schema_version": BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION,
        "input_schema_versions": {
            "benchmark_comparison": benchmark_comparison.get("schema_version"),
            "benchmark_runs": [
                run.get("schema_version") for run in runs if run.get("schema_version")
            ],
            "claim_review": claim_review.get("schema_version"),
        },
        "task_id": benchmark_comparison.get("task_id"),
        "comparison_id": benchmark_comparison.get("comparison_id"),
        "official_task_score_delta": official_delta,
        "control_plane_score_delta": benchmark_comparison.get(
            "control_plane_score_delta"
        ),
        "learning_status": learning_status,
        "repair_candidates": repair_candidates,
        "lifecycle_gate": lifecycle_gate,
        "claim_strength": decision.get("claim_strength"),
        "claim_blockers": decision.get("blockers") or [],
        "learning_quota_gate": learning_quota_gate,
        "overhead": {
            "cost_delta_usd": cost_delta,
            "wall_time_delta_seconds_or_ms": wall_time_delta,
            "label": _learning_ledger_overhead_label(
                official_delta_num,
                cost_delta,
                wall_time_delta,
            ),
        },
        "routing": {
            "repeat_allowed": repeat_allowed,
            "new_candidate_allowed": (
                not repair_candidates or overhead_guard_only
            )
            and bool(learning_quota_gate["spend_allowed"]),
            "next_allowed_action": next_allowed_action,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
    }


def _attempt_learning_task_ids(run: dict[str, Any]) -> list[str]:
    task_ids: list[str] = []
    trials = run.get("trials")
    if isinstance(trials, list):
        for trial in trials[:8]:
            if not isinstance(trial, dict):
                continue
            task_id = trial.get("task_id")
            if isinstance(task_id, str) and task_id and task_id not in task_ids:
                task_ids.append(task_id)
    return task_ids[:4]


def _attempt_learning_repair_candidates(run: dict[str, Any]) -> list[str]:
    labels = set(_claim_review_failure_labels(run))
    first_blocker = run.get("first_blocker")
    if isinstance(first_blocker, str) and first_blocker:
        labels.add(first_blocker)
    candidates: list[str] = []
    if "environment_setup_failed_before_worker" in labels:
        candidates.append("benchmark_environment_setup_contract")
    elif any(
        label in labels
        for label in (
            "pre_worker_agent_setup_failed",
            "treatment_pre_worker_agent_setup_failed",
        )
    ):
        candidates.append("adapter_startup_argument_contract")
    if any(
        label in labels
        for label in (
            "runner_compact_result_missing",
            "harbor_job_root_missing",
            "post_launch_job_dir_materialization_missing",
            "reducer_validation_failed",
        )
    ):
        candidates.append("benchmark_lifecycle_materialization_gate")
    if _compact_positive_int(run.get("worker_submit_eligible_mismatch_count")):
        candidates.append("runner_owned_submit_boundary_invariant")
    if not candidates and labels:
        candidates.append("compact_failure_attribution_review")
    return candidates


def _attempt_learning_run_countable(run: dict[str, Any]) -> bool:
    if not run:
        return False
    official = (
        run.get("official_task_score")
        if isinstance(run.get("official_task_score"), dict)
        else {}
    )
    compact_score = any(
        isinstance(official.get(field), (bool, int, float))
        for field in ("value", "passed")
    )
    compact_blocker = bool(run.get("first_blocker")) or bool(
        _claim_review_failure_labels(run)
    )
    return compact_score or compact_blocker


def _attempt_learning_ledger_actionable(
    learning_ledger: dict[str, Any] | None,
) -> bool:
    if not isinstance(learning_ledger, dict):
        return False
    learning_gate = (
        learning_ledger.get("learning_quota_gate")
        if isinstance(learning_ledger.get("learning_quota_gate"), dict)
        else {}
    )
    routing = (
        learning_ledger.get("routing")
        if isinstance(learning_ledger.get("routing"), dict)
        else {}
    )
    return (
        learning_gate.get("spend_allowed") is True
        and isinstance(routing.get("next_allowed_action"), str)
        and bool(str(routing.get("next_allowed_action")).strip())
    )


def build_benchmark_attempt_learning_gate(
    benchmark_run: dict[str, Any],
    *,
    benchmark_learning_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate benchmark budget counting on durable compact learning evidence."""

    countable_attempt = _attempt_learning_run_countable(benchmark_run)
    repair_candidates = _attempt_learning_repair_candidates(benchmark_run)
    ledger_present = (
        isinstance(benchmark_learning_ledger, dict)
        and benchmark_learning_ledger.get("schema_version")
        == BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION
    )
    ledger_actionable = _attempt_learning_ledger_actionable(
        benchmark_learning_ledger
    )

    if not countable_attempt:
        classification = "benchmark_attempt_not_countable"
        next_required_action = "record_compact_score_or_blocker_before_budget_count"
    elif not ledger_present:
        classification = "benchmark_attempt_learning_row_missing"
        next_required_action = "build_compact_benchmark_learning_ledger_before_repeat_or_new_candidate"
    elif not ledger_actionable:
        classification = "benchmark_attempt_learning_row_nonactionable"
        next_required_action = (
            "stop_without_spend_or_add_named_repair_caveat_before_repeat"
        )
    else:
        classification = "benchmark_attempt_learning_ready"
        routing = (
            benchmark_learning_ledger.get("routing")
            if isinstance(benchmark_learning_ledger, dict)
            and isinstance(benchmark_learning_ledger.get("routing"), dict)
            else {}
        )
        next_required_action = str(
            routing.get("next_allowed_action")
            or "record_learning_row_and_continue"
        )

    return {
        "schema_version": BENCHMARK_ATTEMPT_LEARNING_GATE_SCHEMA_VERSION,
        "benchmark_id": benchmark_run.get("benchmark_id"),
        "mode": benchmark_run.get("mode"),
        "task_ids": _attempt_learning_task_ids(benchmark_run),
        "classification": classification,
        "countable_attempt": countable_attempt,
        "learning_row_present": ledger_present,
        "learning_row_actionable": ledger_actionable,
        "budget_count_allowed": countable_attempt and ledger_actionable,
        "repeat_allowed": bool(
            benchmark_learning_ledger
            and isinstance(benchmark_learning_ledger.get("routing"), dict)
            and benchmark_learning_ledger["routing"].get("repeat_allowed") is True
            and ledger_actionable
        ),
        "new_candidate_allowed": bool(
            benchmark_learning_ledger
            and isinstance(benchmark_learning_ledger.get("routing"), dict)
            and benchmark_learning_ledger["routing"].get("new_candidate_allowed")
            is True
            and ledger_actionable
        ),
        "repair_candidates": repair_candidates,
        "next_required_action": next_required_action,
        "claim_boundary": {
            "requires_learning_row_before_budget_count": True,
            "requires_learning_row_before_repeat_or_new_candidate": True,
            "raw_trace_excluded": True,
            "leaderboard_claim_allowed": False,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
    }


def _public_safe_kwarg_key_list(values: Iterable[Any]) -> list[str]:
    keys: list[str] = []
    for value in values:
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            continue
        key = str(value).strip()
        if not key:
            continue
        if "=" in key:
            key = key.split("=", 1)[0].strip()
        if key.startswith("loopx_") and key not in keys:
            keys.append(key)
    return sorted(keys)[:80]


def build_benchmark_adapter_kwarg_absorption_review(
    *,
    adapter_label: str,
    agent_kwargs: dict[str, Any],
    accepted_loopx_kwargs: Iterable[Any],
    allowed_base_passthrough: Iterable[Any] = (),
) -> dict[str, Any]:
    """Review whether generated loopx_* kwargs are adapter-absorbed."""

    generated_keys = _public_safe_kwarg_key_list(agent_kwargs.keys())
    accepted_keys = set(_public_safe_kwarg_key_list(accepted_loopx_kwargs))
    passthrough_keys = set(_public_safe_kwarg_key_list(allowed_base_passthrough))
    absorbed_keys = sorted(
        key for key in generated_keys if key in accepted_keys or key in passthrough_keys
    )
    leaked_keys = sorted(
        key
        for key in generated_keys
        if key not in accepted_keys and key not in passthrough_keys
    )

    if leaked_keys:
        classification = "adapter_kwarg_leak_risk"
        next_required_action = (
            "consume_or_reject_generated_loopx_kwargs_before_worker_start"
        )
    elif generated_keys:
        classification = "adapter_kwargs_absorbed"
        next_required_action = "adapter_kwarg_absorption_guard_passed"
    else:
        classification = "adapter_loopx_kwargs_missing"
        next_required_action = "record_generated_loopx_kwargs_before_run"

    return {
        "schema_version": BENCHMARK_ADAPTER_KWARG_ABSORPTION_REVIEW_SCHEMA_VERSION,
        "adapter_label": adapter_label,
        "classification": classification,
        "clean": bool(generated_keys) and not leaked_keys,
        "generated_loopx_kwarg_count": len(generated_keys),
        "absorbed_loopx_kwarg_count": len(absorbed_keys),
        "leaked_loopx_kwarg_count": len(leaked_keys),
        "generated_loopx_kwarg_keys": generated_keys,
        "absorbed_loopx_kwarg_keys": absorbed_keys,
        "leaked_loopx_kwarg_keys": leaked_keys,
        "accepted_loopx_kwarg_keys": sorted(accepted_keys)[:80],
        "allowed_base_passthrough_keys": sorted(passthrough_keys)[:40],
        "next_required_action": next_required_action,
        "claim_boundary": {
            "kwarg_values_recorded": False,
            "local_paths_recorded": False,
            "adapter_absorption_required_before_worker_start": True,
            "base_constructor_may_receive_generated_loopx_kwargs": False,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }


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
            exception_kind = _compact_exception_kind(trial.get("exception_type"))
            if exception_kind == "agent_setup_timeout":
                labels.add("agent_setup_timeout_before_worker_start")
            elif exception_kind == "agent_setup_failure":
                labels.add("agent_setup_failed_before_worker_start")
            elif exception_kind == "agent_timeout":
                labels.add("agent_timeout_before_solution_completion")
            elif exception_kind == "agent_exception":
                labels.add("agent_exception_before_solution_completion")
            worker_start_kind = _compact_worker_start_status_kind(
                trial.get("worker_start_status")
            )
            if worker_start_kind == "agent_setup_failure":
                labels.add("agent_setup_failed_before_worker_start")
            elif worker_start_kind == "environment_setup_failure":
                labels.add("environment_setup_failed_before_worker")
    return sorted(labels)[:12]


def _compact_trial_exception_summary(run: dict[str, Any]) -> dict[str, Any]:
    trials = run.get("trials")
    if not isinstance(trials, list):
        return {
            "schema_version": "compact_trial_exception_summary_v0",
            "trial_count": 0,
            "agent_timeout_count": 0,
            "agent_setup_timeout_count": 0,
            "agent_setup_failure_count": 0,
            "agent_exception_count": 0,
            "exception_types": [],
        }
    exception_types: list[str] = []
    agent_timeout_count = 0
    agent_setup_timeout_count = 0
    agent_setup_failure_count = 0
    agent_exception_count = 0
    for trial in trials[:8]:
        if not isinstance(trial, dict):
            continue
        exception_type = trial.get("exception_type")
        exception_kind = ""
        if isinstance(exception_type, str) and exception_type.strip():
            exception_type = exception_type.strip()
            if exception_type not in exception_types:
                exception_types.append(exception_type)
            exception_kind = _compact_exception_kind(exception_type)
        if exception_kind == "agent_timeout":
            agent_timeout_count += 1
        elif exception_kind == "agent_setup_timeout":
            agent_setup_timeout_count += 1
        elif exception_kind == "agent_setup_failure":
            agent_setup_failure_count += 1
        elif exception_kind == "agent_exception":
            agent_exception_count += 1
        worker_start_kind = _compact_worker_start_status_kind(
            trial.get("worker_start_status")
        )
        if worker_start_kind in {"agent_setup_failure", "environment_setup_failure"}:
            agent_setup_failure_count += 1
    return {
        "schema_version": "compact_trial_exception_summary_v0",
        "trial_count": len([trial for trial in trials if isinstance(trial, dict)]),
        "agent_timeout_count": agent_timeout_count,
        "agent_setup_timeout_count": agent_setup_timeout_count,
        "agent_setup_failure_count": agent_setup_failure_count,
        "agent_exception_count": agent_exception_count,
        "exception_types": exception_types[:8],
    }


def _compact_runner_completed_score_zero_signal(
    *,
    run: dict[str, Any],
    score: float | None,
    labels: list[str],
    verifier_failure_count: int,
    verifier_dependency_failure_count: int,
    agent_timeout_count: int,
    agent_setup_timeout_count: int,
    agent_setup_failure_count: int,
    agent_exception_count: int,
) -> dict[str, Any]:
    """Detect clean runner completion with an official zero score and no compact cause."""

    progress = run.get("progress")
    if not isinstance(progress, dict):
        progress = {}
    trials = run.get("trials")
    trial_dicts = [trial for trial in trials if isinstance(trial, dict)] if isinstance(trials, list) else []
    exception_types = [
        str(trial.get("exception_type")).strip()
        for trial in trial_dicts[:8]
        if isinstance(trial.get("exception_type"), str)
        and str(trial.get("exception_type")).strip()
    ]
    non_empty_exceptions = [
        exception_type
        for exception_type in exception_types
        if exception_type.lower() not in {"none", "null", "no_exception"}
    ]
    completed_trials = _compact_positive_int(progress.get("n_completed_trials"))
    errored_trials = _compact_positive_int(progress.get("n_errored_trials"))
    running_trials = _compact_positive_int(progress.get("n_running_trials"))
    pending_trials = _compact_positive_int(progress.get("n_pending_trials"))
    verifier_reward_present_count = sum(
        1
        for trial in trial_dicts[:8]
        if trial.get("verifier_reward_present") is True
        or isinstance(trial.get("reward"), dict)
    )
    explicit_compact_cause_present = any(
        [
            labels,
            verifier_failure_count,
            verifier_dependency_failure_count,
            agent_timeout_count,
            agent_setup_timeout_count,
            agent_setup_failure_count,
            agent_exception_count,
            non_empty_exceptions,
        ]
    )
    runner_completed = str(run.get("runner_return_status") or "").strip() == "completed"
    official_score_completed = (
        str(run.get("official_score_status") or "").strip() == "completed"
    )
    completed_cleanly = (
        score == 0
        and runner_completed
        and official_score_completed
        and completed_trials > 0
        and errored_trials == 0
        and running_trials == 0
        and pending_trials == 0
        and verifier_reward_present_count > 0
        and not explicit_compact_cause_present
    )
    return {
        "schema_version": "runner_completed_score_zero_signal_v0",
        "detected": completed_cleanly,
        "runner_return_status": run.get("runner_return_status"),
        "official_score_status": run.get("official_score_status"),
        "completed_trials": completed_trials,
        "errored_trials": errored_trials,
        "running_trials": running_trials,
        "pending_trials": pending_trials,
        "verifier_reward_present_count": verifier_reward_present_count,
        "non_empty_exception_types": non_empty_exceptions[:8],
    }


def _verifier_attribution_class(
    *,
    score: float | None,
    score_attribution: str,
    labels: list[str],
    verifier_failure_count: int,
    verifier_dependency_failure_count: int,
    agent_timeout_count: int,
    agent_setup_timeout_count: int,
    agent_setup_failure_count: int,
    agent_exception_count: int,
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
    if (
        score_attribution == "worker_self_validation_official_score_mismatch"
        or "worker_self_validation_official_score_mismatch" in labels
    ):
        return "worker_self_validation_official_score_mismatch"
    if (
        score_attribution == "worker_validation_scope_ambiguous_official_score_failure"
        or "worker_validation_scope_ambiguous_official_score_failure" in labels
    ):
        return "worker_validation_scope_ambiguous_official_score_failure"
    if (
        score_attribution == "worker_bridge_connected_official_score_failure"
        or "worker_bridge_connected_official_score_failure" in labels
    ):
        return "model_or_solution_failure"
    if score_attribution in {
        "model_solution_failure",
        "agent_solution_failure",
        "agent_timeout_before_solution_completion",
        "task_solution_failure",
        "solution_incorrect",
        "official_verifier_solution_failure",
    }:
        return "model_or_solution_failure"
    if (
        score_attribution == "agent_setup_timeout_score_failure"
        or agent_setup_timeout_count > 0
        or "agent_setup_timeout_before_worker_start" in labels
    ):
        return "agent_setup_timeout_score_failure"
    if (
        score_attribution == "agent_setup_score_failure"
        or agent_setup_failure_count > 0
        or "agent_setup_failed_before_worker_start" in labels
        or "environment_setup_failed_before_worker" in labels
        or "pre_worker_startup_blocker_recorded" in labels
    ):
        return "agent_setup_score_failure"
    if agent_timeout_count > 0 or "agent_timeout_before_solution_completion" in labels:
        return "agent_timeout_score_failure"
    if (
        agent_exception_count > 0
        or "agent_exception_before_solution_completion" in labels
    ):
        return "agent_exception_score_failure"
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
    exception_summary = _compact_trial_exception_summary(run)
    agent_timeout_count = _compact_positive_int(
        exception_summary.get("agent_timeout_count")
    )
    agent_setup_timeout_count = _compact_positive_int(
        exception_summary.get("agent_setup_timeout_count")
    )
    agent_setup_failure_count = _compact_positive_int(
        exception_summary.get("agent_setup_failure_count")
    )
    agent_exception_count = _compact_positive_int(
        exception_summary.get("agent_exception_count")
    )
    attribution_class = _verifier_attribution_class(
        score=score,
        score_attribution=score_attribution,
        labels=labels,
        verifier_failure_count=verifier_failure_count,
        verifier_dependency_failure_count=verifier_dependency_failure_count,
        agent_timeout_count=agent_timeout_count,
        agent_setup_timeout_count=agent_setup_timeout_count,
        agent_setup_failure_count=agent_setup_failure_count,
        agent_exception_count=agent_exception_count,
    )
    runner_completed_score_zero_signal = _compact_runner_completed_score_zero_signal(
        run=run,
        score=score,
        labels=labels,
        verifier_failure_count=verifier_failure_count,
        verifier_dependency_failure_count=verifier_dependency_failure_count,
        agent_timeout_count=agent_timeout_count,
        agent_setup_timeout_count=agent_setup_timeout_count,
        agent_setup_failure_count=agent_setup_failure_count,
        agent_exception_count=agent_exception_count,
    )
    if (
        attribution_class == "unattributed_score_failure"
        and runner_completed_score_zero_signal["detected"]
    ):
        attribution_class = "runner_completed_official_score_zero_unattributed"
    verifier_caveat = attribution_class in {
        "verifier_dependency_install_failure",
        "verifier_platform_probe_failure",
        "verifier_infrastructure_failure",
        "worker_self_validation_official_score_mismatch",
        "worker_validation_scope_ambiguous_official_score_failure",
        "runner_completed_official_score_zero_unattributed",
        "unattributed_score_failure",
        "missing_official_score",
    }
    caveat_resolved = attribution_class in {
        "model_or_solution_failure",
        "agent_setup_timeout_score_failure",
        "agent_setup_score_failure",
        "agent_timeout_score_failure",
        "agent_exception_score_failure",
    }
    if attribution_class.startswith("verifier_"):
        next_action = (
            "keep attribution caveat; require same-protocol repeat or finer "
            "compact verifier evidence"
        )
    elif attribution_class == "worker_self_validation_official_score_mismatch":
        next_action = (
            "keep attribution caveat; align worker self-validation with official "
            "verifier or collect finer compact verifier-facing evidence"
        )
    elif attribution_class == "worker_validation_scope_ambiguous_official_score_failure":
        next_action = (
            "keep attribution caveat; add explicit worker validation_scope and "
            "claim_boundary before same-task repeat"
        )
    elif attribution_class == "runner_completed_official_score_zero_unattributed":
        next_action = (
            "keep attribution caveat; runner and official verifier completed, "
            "but compact score-zero cause still needs finer attribution"
        )
    elif attribution_class == "unattributed_score_failure":
        next_action = (
            "keep attribution caveat; compact score failure is not yet attributed"
        )
    elif attribution_class == "missing_official_score":
        next_action = "wait for compact official score before attribution review"
    elif attribution_class == "agent_timeout_score_failure":
        next_action = (
            "claim caveat resolved by compact agent-timeout attribution; "
            "treat as non-verifier score failure"
        )
    elif attribution_class == "agent_exception_score_failure":
        next_action = (
            "claim caveat resolved by compact agent-exception attribution; "
            "inspect case-level exception context before same-task repeat"
        )
    elif attribution_class == "agent_setup_timeout_score_failure":
        next_action = (
            "claim caveat resolved by compact agent-setup-timeout attribution; "
            "repair startup/setup before same-task repeat"
        )
    elif attribution_class == "agent_setup_score_failure":
        next_action = (
            "claim caveat resolved by compact agent-setup attribution; repair "
            "startup/setup before same-task repeat"
        )
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
        "compact_trial_exception_summary": exception_summary,
        "agent_timeout_count": agent_timeout_count,
        "agent_setup_timeout_count": agent_setup_timeout_count,
        "agent_setup_failure_count": agent_setup_failure_count,
        "agent_exception_count": agent_exception_count,
        "verifier_failure_attribution_count": verifier_failure_count,
        "verifier_dependency_failure_count": verifier_dependency_failure_count,
        "validation_failed_checks": _compact_validation_failed_checks(run),
        "runner_completed_score_zero_signal": runner_completed_score_zero_signal,
        "worker_submit_eligible_mismatch_count": _compact_positive_int(
            run.get("worker_submit_eligible_mismatch_count")
        ),
        "worker_self_validation_official_score_mismatch_count": _compact_positive_int(
            run.get("worker_self_validation_official_score_mismatch_count")
        ),
        "worker_validation_scope_ambiguous_official_score_failure_count": (
            _compact_positive_int(
                run.get(
                    "worker_validation_scope_ambiguous_official_score_failure_count"
                )
            )
        ),
        "worker_bridge_connected_official_score_failure_count": _compact_positive_int(
            run.get("worker_bridge_connected_official_score_failure_count")
        ),
        "attribution_class": attribution_class,
        "verifier_caveat": verifier_caveat,
        "claim_caveat_resolved": caveat_resolved,
        "next_action": next_action,
    }


def _verifier_attribution_review_routing(
    *,
    baseline_review: dict[str, Any] | None,
    blockers: list[str],
    baseline_caveat_resolved: bool,
) -> dict[str, Any]:
    """Project compact attribution into machine-readable routing decisions."""

    attribution_class = (
        str(baseline_review.get("attribution_class") or "")
        if isinstance(baseline_review, dict)
        else ""
    )
    verifier_blocked = "baseline_verifier_attribution_caveat" in blockers
    worker_verifier_alignment_blocked = (
        "baseline_worker_verifier_alignment_caveat" in blockers
    )
    worker_validation_scope_blocked = (
        "baseline_worker_validation_scope_ambiguous_caveat" in blockers
    )
    missing_baseline = "missing_compact_baseline_run" in blockers
    missing_score = "baseline_official_score_missing" in blockers
    unattributed = "baseline_score_failure_unattributed" in blockers
    boundary_mismatch = "baseline_submit_boundary_mismatch" in blockers
    no_score_failure = attribution_class == "no_score_failure" and not blockers
    requires_preflight_repair = attribution_class in {
        "verifier_dependency_install_failure",
        "verifier_platform_probe_failure",
        "verifier_infrastructure_failure",
    }
    requires_agent_setup_repair = attribution_class in {
        "agent_setup_timeout_score_failure",
        "agent_setup_score_failure",
    }
    requires_case_exception_research = (
        attribution_class == "agent_exception_score_failure"
    )

    treatment_eligible = (
        baseline_caveat_resolved
        and not requires_agent_setup_repair
        and not requires_case_exception_research
    )
    repeat_allowed = baseline_caveat_resolved
    new_candidate_allowed = (
        baseline_caveat_resolved
        or verifier_blocked
        or worker_verifier_alignment_blocked
        or worker_validation_scope_blocked
    )

    if missing_baseline:
        next_allowed_action = "provide_compact_baseline_run"
    elif missing_score:
        next_allowed_action = "wait_for_compact_official_score"
    elif boundary_mismatch:
        next_allowed_action = "repair_submit_boundary_mismatch"
    elif requires_preflight_repair:
        next_allowed_action = (
            "repair_verifier_preflight_or_select_new_material_ready_case"
        )
        repeat_allowed = False
    elif attribution_class == "worker_self_validation_official_score_mismatch":
        next_allowed_action = "align_worker_self_validation_with_official_verifier"
        repeat_allowed = False
        new_candidate_allowed = False
    elif attribution_class == "worker_validation_scope_ambiguous_official_score_failure":
        next_allowed_action = "add_worker_validation_scope_and_claim_boundary"
        repeat_allowed = False
        new_candidate_allowed = False
    elif requires_agent_setup_repair:
        next_allowed_action = "repair_agent_setup_timeout_or_select_new_material_ready_case"
        repeat_allowed = False
        new_candidate_allowed = True
    elif requires_case_exception_research:
        next_allowed_action = "inspect_compact_agent_exception_before_same_task_repeat"
        repeat_allowed = False
        new_candidate_allowed = True
    elif unattributed:
        next_allowed_action = "collect_finer_compact_failure_attribution"
        repeat_allowed = False
        new_candidate_allowed = False
    elif no_score_failure:
        next_allowed_action = "select_new_material_ready_case_no_score_failure"
        treatment_eligible = False
        repeat_allowed = False
        new_candidate_allowed = True
    elif baseline_caveat_resolved:
        next_allowed_action = "baseline_failure_is_control_plane_addressable"
    else:
        next_allowed_action = "keep_treatment_blocked_until_attribution_resolves"
        repeat_allowed = False
        new_candidate_allowed = False

    return {
        "treatment_eligible": treatment_eligible,
        "repeat_allowed": repeat_allowed,
        "new_candidate_allowed": new_candidate_allowed,
        "requires_verifier_preflight_repair": requires_preflight_repair,
        "requires_agent_setup_repair": requires_agent_setup_repair,
        "requires_case_exception_research": requires_case_exception_research,
        "requires_compact_official_score": missing_score,
        "requires_compact_baseline_run": missing_baseline,
        "requires_finer_compact_attribution": unattributed,
        "requires_worker_verifier_alignment": (
            attribution_class == "worker_self_validation_official_score_mismatch"
        ),
        "requires_worker_validation_scope": (
            attribution_class
            == "worker_validation_scope_ambiguous_official_score_failure"
        ),
        "next_allowed_action": next_allowed_action,
        "blocked_action_scope": (
            "treatment_and_same_task_repeat"
            if requires_preflight_repair
            else "same_task_repeat_until_worker_verifier_alignment"
            if attribution_class == "worker_self_validation_official_score_mismatch"
            else "same_task_repeat_until_worker_validation_scope"
            if attribution_class
            == "worker_validation_scope_ambiguous_official_score_failure"
            else "same_task_repeat_until_setup_repair"
            if requires_agent_setup_repair
            else "same_task_repeat_until_exception_hypothesis"
            if requires_case_exception_research
            else "same_task_claim"
            if no_score_failure
            else "treatment"
            if blockers and not baseline_caveat_resolved
            else ""
        ),
    }


def _benchmark_lifecycle_schema(value: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("schema_version") or "")


def _benchmark_lifecycle_launched(value: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    for field in ("process_started", "launched", "started", "pid"):
        if value.get(field):
            return True
    return False


def _benchmark_lifecycle_budget_count_allowed(
    learning_ledger: dict[str, Any] | None,
) -> bool:
    if not isinstance(learning_ledger, dict):
        return False
    lifecycle_gate = (
        learning_ledger.get("lifecycle_gate")
        if isinstance(learning_ledger.get("lifecycle_gate"), dict)
        else {}
    )
    return lifecycle_gate.get("budget_count_allowed") is True


def _benchmark_lifecycle_environment_setup_readiness(
    *,
    benchmark_run: dict[str, Any] | None,
    preflight: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _benchmark_run_environment_setup_failure_context(benchmark_run)
    if not context:
        return {}

    preflight_ready = _benchmark_lifecycle_ready_preflight(preflight)
    task_id = "unknown_task"
    if isinstance(benchmark_run, dict):
        for trial in benchmark_run.get("trials") or []:
            if not isinstance(trial, dict):
                continue
            task_label = _public_safe_benchmark_label(trial.get("task_id"))
            if task_label:
                task_id = task_label
                break
    no_run_preflight_status = "ready" if preflight_ready else "not_ready_or_absent"
    first_blocker = "environment_setup_failed_before_worker"
    if not preflight_ready:
        next_allowed_action = "repair_no_run_preflight_before_environment_setup_probe"
    else:
        next_allowed_action = (
            "run_setup_only_environment_preflight_or_select_new_material_ready_case"
        )

    return {
        "schema_version": TERMINAL_BENCH_ENVIRONMENT_SETUP_READINESS_SCHEMA,
        "benchmark_id": (
            _public_safe_benchmark_label(
                benchmark_run.get("benchmark_id") if isinstance(benchmark_run, dict) else None
            )
            or "benchmark"
        ),
        "task_id": task_id,
        "previous_failure_observed": True,
        "previous_failure_context": context,
        "no_run_preflight_ready": preflight_ready,
        "no_run_preflight_status": no_run_preflight_status,
        "same_task_repeat_allowed": False,
        "repeat_blocked_by": first_blocker,
        "first_blocker": first_blocker,
        "diagnostic_limit": "cannot_prove_reproducible_or_cleared_from_no_run_preflight",
        "next_allowed_action": next_allowed_action,
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "docker_logs_read": False,
            "credential_values_recorded": False,
            "local_paths_recorded": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "submit_invoked": False,
        },
    }


def _benchmark_lifecycle_environment_setup_probe_result(
    benchmark_run: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return compact lifecycle facts for a no-upload environment setup probe."""

    if not isinstance(benchmark_run, dict):
        return {}
    trials = [
        trial
        for trial in benchmark_run.get("trials") or []
        if isinstance(trial, dict)
    ]
    materialized_trials: list[dict[str, Any]] = []
    for trial in trials:
        if trial.get("worker_start_status") != "environment_setup_probe_materialized":
            continue
        materialized_trials.append(trial)
    if not materialized_trials:
        return {}

    first_trial = materialized_trials[0]
    task_id = _public_safe_benchmark_label(first_trial.get("task_id")) or "unknown_task"
    exception_type = (
        _public_safe_benchmark_label(first_trial.get("exception_type"), limit=120)
        or "none"
    )
    exception_present = exception_type not in {"", "none", "not_applicable"}
    if exception_present:
        probe_outcome = "materialized_with_exception"
        repeat_blocked_by = "environment_setup_probe_exception_requires_interpretation"
        next_allowed_action = (
            "classify_environment_setup_probe_exception_before_same_task_repeat"
        )
    else:
        probe_outcome = "materialized_without_exception"
        repeat_blocked_by = "environment_setup_probe_result_requires_review"
        next_allowed_action = (
            "review_environment_setup_probe_result_before_same_task_repeat"
        )
    return {
        "schema_version": "terminal_bench_environment_setup_probe_result_v0",
        "benchmark_id": (
            _public_safe_benchmark_label(benchmark_run.get("benchmark_id"))
            or "benchmark"
        ),
        "task_id": task_id,
        "worker_mode": (
            _public_safe_benchmark_label(benchmark_run.get("worker_mode"))
            or "unknown"
        ),
        "probe_materialized": True,
        "materialized_trial_count": len(materialized_trials),
        "trial_result_present_count": sum(
            1 for trial in trials if trial.get("trial_result_present") is True
        ),
        "artifact_manifest_present_count": sum(
            1 for trial in trials if trial.get("artifact_manifest_present") is True
        ),
        "exception_type": exception_type,
        "exception_present": exception_present,
        "probe_outcome": probe_outcome,
        "repeat_blocked_by": repeat_blocked_by,
        "case_attempt_countable": False,
        "benchmark_budget_countable": False,
        "same_task_repeat_allowed": False,
        "next_allowed_action": next_allowed_action,
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "docker_logs_read": False,
            "credential_values_recorded": False,
            "local_paths_recorded": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "submit_invoked": False,
        },
    }


def build_benchmark_lifecycle_state(
    *,
    preflight: dict[str, Any] | None = None,
    launch: dict[str, Any] | None = None,
    post_launch_materialization: dict[str, Any] | None = None,
    benchmark_run: dict[str, Any] | None = None,
    benchmark_comparison: dict[str, Any] | None = None,
    claim_review: dict[str, Any] | None = None,
    learning_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reduce compact benchmark evidence into an explicit lifecycle state."""

    preflight_ready = _benchmark_lifecycle_ready_preflight(preflight)
    process_launched = _benchmark_lifecycle_launched(launch)
    materialized = (
        isinstance(post_launch_materialization, dict)
        and post_launch_materialization.get("ready_for_launch_state") is True
    )
    compact_ready = (
        isinstance(post_launch_materialization, dict)
        and post_launch_materialization.get("ready_for_compact_result_ingest") is True
    ) or _benchmark_lifecycle_schema(benchmark_run) == "benchmark_run_v0"
    compact_failure_marker_ready = (
        isinstance(post_launch_materialization, dict)
        and post_launch_materialization.get("ready_for_compact_failure_marker") is True
    )
    result_ingested = _benchmark_lifecycle_schema(benchmark_run) == "benchmark_run_v0"
    if result_ingested:
        process_launched = True
        materialized = True
        compact_ready = True
    verifier_scored = False
    if isinstance(benchmark_run, dict):
        verifier_scored = any(
            isinstance(benchmark_run.get(field), (int, float))
            and not isinstance(benchmark_run.get(field), bool)
            for field in (
                "official_score",
                "official_task_score",
                "score",
            )
        )
        if not verifier_scored:
            for trial in benchmark_run.get("trials") or []:
                if not isinstance(trial, dict):
                    continue
                if any(
                    isinstance(trial.get(field), (int, float))
                    and not isinstance(trial.get(field), bool)
                    for field in (
                        "official_score",
                        "official_task_score",
                        "score",
                    )
                ):
                    verifier_scored = True
                    break
    paired_compared = (
        _benchmark_lifecycle_schema(benchmark_comparison)
        == "benchmark_comparison_v0"
    )
    claim_reviewed = (
        _benchmark_lifecycle_schema(claim_review)
        == BENCHMARK_CLAIM_REVIEW_SCHEMA_VERSION
    )
    learning_ledgered = (
        _benchmark_lifecycle_schema(learning_ledger)
        == BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION
    )
    budget_count_allowed = _benchmark_lifecycle_budget_count_allowed(learning_ledger)
    environment_setup_readiness = _benchmark_lifecycle_environment_setup_readiness(
        benchmark_run=benchmark_run,
        preflight=preflight,
    )
    environment_setup_probe_result = (
        _benchmark_lifecycle_environment_setup_probe_result(benchmark_run)
    )
    environment_setup_repeat_cleared = (
        not environment_setup_readiness
        or environment_setup_readiness.get("same_task_repeat_allowed") is True
    )
    environment_setup_probe_completed = (
        environment_setup_probe_result.get("probe_materialized") is True
    )

    transitions = [
        ("preflight_ready", preflight_ready),
        ("launched_process", process_launched),
        ("post_launch_materialized", materialized),
        ("compact_result_ready", compact_ready),
        ("result_ingested", result_ingested),
    ]
    if environment_setup_readiness:
        transitions.append(
            (
                "environment_setup_repeat_cleared",
                environment_setup_repeat_cleared,
            )
        )
    if environment_setup_probe_result:
        transitions.append(
            (
                "environment_setup_probe_completed",
                environment_setup_probe_completed,
            )
        )
    transitions.extend(
        [
            ("paired_compared", paired_compared),
            ("claim_reviewed", claim_reviewed),
            ("learning_ledgered", learning_ledgered),
            ("budget_counted", budget_count_allowed),
        ]
    )
    achieved = [name for name, ready in transitions if ready]
    current_phase = achieved[-1] if achieved else "not_started"

    first_blocker = "ready_for_budget_count" if budget_count_allowed else ""
    if not preflight_ready:
        first_blocker = "preflight_not_ready"
    elif process_launched and not materialized:
        first_blocker = "post_launch_materialization_missing"
    elif materialized and not compact_ready:
        first_blocker = "compact_result_not_ready"
    elif compact_ready and not result_ingested:
        first_blocker = "compact_result_not_ingested"
    elif result_ingested and not environment_setup_repeat_cleared:
        first_blocker = "environment_setup_readiness_preflight_required"
    elif result_ingested and environment_setup_probe_completed:
        first_blocker = str(
            environment_setup_probe_result.get("repeat_blocked_by")
            or "inspect_environment_setup_probe_result_before_same_task_repeat"
        )
    elif result_ingested and not paired_compared:
        first_blocker = "paired_comparison_missing"
    elif paired_compared and not claim_reviewed:
        first_blocker = "claim_review_missing"
    elif claim_reviewed and not learning_ledgered:
        first_blocker = "benchmark_learning_ledger_missing"
    elif learning_ledgered and not budget_count_allowed:
        first_blocker = "budget_count_blocked_by_learning_ledger"

    next_required_transition = ""
    for name, ready in transitions:
        if not ready:
            next_required_transition = name
            break
    if (
        materialized
        and compact_failure_marker_ready
        and not result_ingested
    ):
        if "compact_failure_marker_ready" not in achieved:
            achieved.append("compact_failure_marker_ready")
        current_phase = "compact_failure_marker_ready"
        first_blocker = "compact_failure_marker_ledger_ingest_required"
        next_required_transition = "compact_failure_marker_ledger_ingest"
    if result_ingested and environment_setup_probe_completed:
        current_phase = "environment_setup_probe_completed"
        next_required_transition = "case_repeat_decision"
    canonical = canonical_lifecycle(
        process_started=process_launched,
        runner_accepted_args=process_launched,
        job_root_materialized=materialized,
        trial_started=compact_ready or result_ingested,
        worker_started=result_ingested,
        result_written=result_ingested,
        verifier_scored=verifier_scored,
    )

    routing = (
        learning_ledger.get("routing")
        if isinstance(learning_ledger, dict)
        and isinstance(learning_ledger.get("routing"), dict)
        else {}
    )
    learning_gate = (
        learning_ledger.get("learning_quota_gate")
        if isinstance(learning_ledger, dict)
        and isinstance(learning_ledger.get("learning_quota_gate"), dict)
        else {}
    )
    ledger_repeat_allowed = (
        routing.get("repeat_allowed")
        if isinstance(routing.get("repeat_allowed"), bool)
        else False
    )
    post_launch_blocker = (
        str(post_launch_materialization.get("first_blocker") or "")
        if isinstance(post_launch_materialization, dict)
        else ""
    )
    compact_failure_marker = (
        post_launch_materialization.get("compact_failure_marker")
        if isinstance(post_launch_materialization, dict)
        and isinstance(post_launch_materialization.get("compact_failure_marker"), dict)
        else {}
    )
    case_attempt_countable = compact_failure_marker.get("case_attempt_countable") is True
    benchmark_budget_countable = (
        compact_failure_marker.get("benchmark_budget_countable") is True
    )
    terminal_closeout = compact_failure_marker.get("terminal_closeout") is True
    return {
        "schema_version": BENCHMARK_LIFECYCLE_STATE_SCHEMA_VERSION,
        "current_phase": current_phase,
        "canonical_lifecycle": canonical,
        "achieved_transitions": achieved,
        "next_required_transition": next_required_transition,
        "first_blocker": first_blocker,
        "transition_ready": {name: ready for name, ready in transitions},
        "gates": {
            "launch_state_countable": materialized,
            "compact_result_ingest_allowed": compact_ready,
            "compact_failure_marker_ready": compact_failure_marker_ready,
            "terminal_closeout": terminal_closeout,
            "case_attempt_countable": case_attempt_countable,
            "benchmark_budget_countable": bool(
                benchmark_budget_countable or budget_count_allowed
            ),
            "budget_count_allowed": budget_count_allowed,
            "new_candidate_allowed": routing.get("new_candidate_allowed")
            if isinstance(routing.get("new_candidate_allowed"), bool)
            else False,
            "repeat_allowed": bool(
                ledger_repeat_allowed and environment_setup_repeat_cleared
            ),
            "environment_setup_repeat_allowed": (
                environment_setup_readiness.get("same_task_repeat_allowed")
                if environment_setup_readiness
                else None
            ),
            "environment_setup_probe_completed": environment_setup_probe_completed,
            "environment_setup_probe_case_attempt_countable": (
                environment_setup_probe_result.get("case_attempt_countable")
                if environment_setup_probe_result
                else None
            ),
            "learning_spend_allowed": learning_gate.get("spend_allowed")
            if isinstance(learning_gate.get("spend_allowed"), bool)
            else False,
        },
        "environment_setup_readiness_preflight": environment_setup_readiness,
        "environment_setup_probe_result": environment_setup_probe_result,
        "inputs": {
            "preflight_schema": _benchmark_lifecycle_schema(preflight),
            "launch_present": isinstance(launch, dict) and bool(launch),
            "post_launch_schema": _benchmark_lifecycle_schema(
                post_launch_materialization
            ),
            "post_launch_first_blocker": post_launch_blocker,
            "benchmark_run_schema": _benchmark_lifecycle_schema(benchmark_run),
            "benchmark_comparison_schema": _benchmark_lifecycle_schema(
                benchmark_comparison
            ),
            "claim_review_schema": _benchmark_lifecycle_schema(claim_review),
            "learning_ledger_schema": _benchmark_lifecycle_schema(learning_ledger),
        },
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
    elif (
        baseline_review["attribution_class"]
        == "worker_self_validation_official_score_mismatch"
    ):
        blockers.append("baseline_worker_verifier_alignment_caveat")
    elif (
        baseline_review["attribution_class"]
        == "worker_validation_scope_ambiguous_official_score_failure"
    ):
        blockers.append("baseline_worker_validation_scope_ambiguous_caveat")
    elif baseline_review["attribution_class"] in {
        "runner_completed_official_score_zero_unattributed",
        "unattributed_score_failure",
    }:
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
    if (
        baseline_caveat_resolved
        and baseline_review
        and baseline_review.get("attribution_class") == "agent_exception_score_failure"
    ):
        next_action = (
            "baseline compact verifier caveat resolved as agent exception; "
            "inspect case-level exception hypothesis before same-task repeat"
        )
    elif baseline_caveat_resolved:
        next_action = (
            "baseline compact verifier caveat resolved; rerun claim review "
            "before upgrading proof strength"
        )
    elif "baseline_verifier_attribution_caveat" in blockers:
        next_action = (
            "do not upgrade claim; run same-protocol repeat or collect finer "
            "compact verifier-side attribution"
        )
    elif "baseline_worker_verifier_alignment_caveat" in blockers:
        next_action = (
            "do not upgrade claim; align worker self-validation with official "
            "verifier evidence before same-task repeat"
        )
    elif "baseline_worker_validation_scope_ambiguous_caveat" in blockers:
        next_action = (
            "do not repeat same task; add explicit worker validation_scope and "
            "claim_boundary so bridge connectivity cannot be confused with case success"
        )
    elif "baseline_score_failure_unattributed" in blockers:
        next_action = (
            "do not upgrade claim; compact baseline score failure is unattributed"
        )
    elif "missing_compact_baseline_run" in blockers:
        next_action = "provide a compact benchmark_run_v0 for the baseline arm"
    elif (
        baseline_review
        and baseline_review.get("attribution_class") == "no_score_failure"
        and not blockers
    ):
        next_action = (
            "no baseline score-failure caveat; do not claim same-task uplift, "
            "select a new material-ready case"
        )
    else:
        next_action = "keep claim blocked until compact attribution blockers are resolved"
    routing = _verifier_attribution_review_routing(
        baseline_review=baseline_review,
        blockers=blockers,
        baseline_caveat_resolved=baseline_caveat_resolved,
    )

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
        "routing": routing,
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
    }


DEFAULT_BENCHMARK_RUNNER_OWNED_FLAG_INVARIANTS = {
    "submit_eligible": WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_FIXED_FIELDS[
        "submit_eligible"
    ],
    "leaderboard_evidence": WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_FIXED_FIELDS[
        "leaderboard_evidence"
    ],
}
DEFAULT_BENCHMARK_RUNNER_OWNED_READ_BOUNDARY_INVARIANTS = {
    "compact_only": True,
    "raw_artifacts_read": False,
    "task_text_read": False,
    "local_paths_recorded": False,
}


def _runner_invariant_compare_bool(
    *,
    source: dict[str, Any],
    field: str,
    expected: bool,
    namespace: str,
    observed: dict[str, bool],
    mismatches: list[dict[str, Any]],
    missing_fields: list[str],
) -> None:
    actual = source.get(field)
    qualified_field = f"{namespace}.{field}" if namespace else field
    if isinstance(actual, bool):
        observed[qualified_field] = actual
        if actual != expected:
            mismatches.append(
                {
                    "field": qualified_field,
                    "expected": expected,
                    "actual": actual,
                    "owner": "runner",
                    "reason": "worker_writeback_conflicts_with_runner_owned_boundary",
                }
            )
        return
    missing_fields.append(qualified_field)


def build_benchmark_runner_invariant_review(
    benchmark_run: dict[str, Any],
    *,
    expected_flags: dict[str, bool] | None = None,
    expected_read_boundary: dict[str, bool] | None = None,
    runner_label: str | None = None,
) -> dict[str, Any]:
    """Compare compact worker writeback against runner-owned boundary facts."""

    flags = expected_flags or DEFAULT_BENCHMARK_RUNNER_OWNED_FLAG_INVARIANTS
    read_boundary_expectations = (
        expected_read_boundary
        or DEFAULT_BENCHMARK_RUNNER_OWNED_READ_BOUNDARY_INVARIANTS
    )
    read_boundary = (
        benchmark_run.get("read_boundary")
        if isinstance(benchmark_run.get("read_boundary"), dict)
        else {}
    )
    observed: dict[str, bool] = {}
    mismatches: list[dict[str, Any]] = []
    missing_fields: list[str] = []

    for field, expected in flags.items():
        _runner_invariant_compare_bool(
            source=benchmark_run,
            field=field,
            expected=bool(expected),
            namespace="",
            observed=observed,
            mismatches=mismatches,
            missing_fields=missing_fields,
        )
    for field, expected in read_boundary_expectations.items():
        _runner_invariant_compare_bool(
            source=read_boundary,
            field=field,
            expected=bool(expected),
            namespace="read_boundary",
            observed=observed,
            mismatches=mismatches,
            missing_fields=missing_fields,
        )

    if mismatches:
        classification = "runner_owned_boundary_mismatch"
        repair_recommendation = (
            "treat worker writeback as boundary-mismatch evidence; preserve "
            "runner-owned launch/preflight facts and do not widen no-upload, "
            "no-submit, leaderboard, or raw-read claims"
        )
    elif missing_fields:
        classification = "runner_owned_boundary_incomplete"
        repair_recommendation = (
            "require compact runner-owned boundary fields before trusting the "
            "worker writeback for public claim review"
        )
    else:
        classification = "runner_owned_boundary_ok"
        repair_recommendation = (
            "accept compact boundary echo for review while keeping runner-owned "
            "fields authoritative"
        )

    return {
        "schema_version": BENCHMARK_RUNNER_INVARIANT_REVIEW_SCHEMA_VERSION,
        "benchmark_id": benchmark_run.get("benchmark_id"),
        "job_name_present": bool(benchmark_run.get("job_name")),
        "mode": benchmark_run.get("mode"),
        "runner_label": runner_label or benchmark_run.get("source_runner"),
        "classification": classification,
        "clean": not mismatches and not missing_fields,
        "mismatch_count": len(mismatches),
        "missing_field_count": len(missing_fields),
        "mismatches": mismatches,
        "missing_fields": missing_fields[:12],
        "observed_runner_owned_fields": observed,
        "expected_runner_owned_fields": {
            **{field: bool(value) for field, value in flags.items()},
            **{
                f"read_boundary.{field}": bool(value)
                for field, value in read_boundary_expectations.items()
            },
        },
        "claim_boundary": {
            "runner_owned_fields_authoritative": True,
            "worker_may_override_runner_owned_fields": False,
            "submit_eligible": flags.get("submit_eligible") is True,
            "leaderboard_evidence": flags.get("leaderboard_evidence") is True,
            "raw_trace_excluded": True,
        },
        "repair_recommendation": repair_recommendation,
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
    }



def _is_compactable_benchmark_run_v0(payload: dict[str, Any]) -> bool:
    """Return true for payload shapes accepted by history append-benchmark-run."""

    if payload.get("schema_version") == "benchmark_run_v0":
        return True
    nested = payload.get("benchmark_run")
    return (
        isinstance(nested, dict)
        and nested.get("schema_version") == "benchmark_run_v0"
    )


def _benchmark_result_failed(result: dict[str, Any]) -> bool:
    official = (
        result.get("official_task_score")
        if isinstance(result.get("official_task_score"), dict)
        else {}
    )
    if isinstance(official.get("passed"), bool):
        return official.get("passed") is False
    terminal_state = str(result.get("terminal_state") or "").strip().lower()
    if terminal_state in {"success", "succeeded", "passed", "resolved"}:
        return False
    return bool(terminal_state)


def benchmark_result_from_benchmark_run_for_baseline_gate(
    benchmark_run: dict[str, Any],
) -> dict[str, Any]:
    """Project a compact benchmark_run_v0 into baseline-gate result shape.

    Current benchmark runners increasingly write run-level compact artifacts
    because they need to preserve protocol, timing, bridge, and ledger context.
    The baseline-failure gate only needs a result-level public-safe slice:
    task id, scenario id, terminal state, score, and compact attribution labels.
    """

    if benchmark_run.get("schema_version") != "benchmark_run_v0":
        raise ValueError("benchmark_run must be compact benchmark_run_v0")

    safe_mode = _public_safe_benchmark_label(benchmark_run.get("mode")) or "baseline"
    trials = benchmark_run.get("trials") if isinstance(benchmark_run.get("trials"), list) else []
    first_trial = trials[0] if trials and isinstance(trials[0], dict) else {}
    case_ids = benchmark_run.get("case_ids") if isinstance(benchmark_run.get("case_ids"), list) else []
    task_id = (
        _public_safe_benchmark_label(first_trial.get("task_id"))
        or _public_safe_benchmark_label(benchmark_run.get("task_id"))
        or (_public_safe_benchmark_label(case_ids[0]) if case_ids else None)
        or _public_safe_benchmark_label(benchmark_run.get("job_name"))
        or "unknown_task"
    )

    official = (
        benchmark_run.get("official_task_score")
        if isinstance(benchmark_run.get("official_task_score"), dict)
        else {}
    )
    score_value = official.get("value")
    if not isinstance(score_value, (int, float)) or isinstance(score_value, bool):
        score_value = benchmark_run.get("official_score")
    passed = official.get("passed")
    if not isinstance(passed, bool):
        passed = None
    if passed is None and isinstance(score_value, (int, float)) and not isinstance(score_value, bool):
        passed = score_value > 0

    runner_status = _public_safe_benchmark_label(
        benchmark_run.get("runner_return_status")
        or benchmark_run.get("official_score_status")
        or benchmark_run.get("status")
    )
    if passed is True:
        terminal_state = "passed"
    elif passed is False:
        terminal_state = "failed"
    else:
        terminal_state = runner_status or "unknown"

    labels: list[str] = []
    for item in (
        benchmark_run.get("score_failure_attribution"),
        benchmark_run.get("failure_class"),
    ):
        label = _public_safe_benchmark_label(item)
        if label and label not in {"none", "unknown", "missing"} and label not in labels:
            labels.append(label)
    result_labels = benchmark_run.get("failure_attribution_labels")
    if isinstance(result_labels, list):
        for item in result_labels:
            label = _public_safe_benchmark_label(item)
            if label and label not in {"none", "unknown", "missing"} and label not in labels:
                labels.append(label)
    worker_bridge_outcome = (
        benchmark_run.get("worker_bridge_outcome")
        if isinstance(benchmark_run.get("worker_bridge_outcome"), dict)
        else {}
    )
    for item in (
        worker_bridge_outcome.get("score_failure_attribution"),
        worker_bridge_outcome.get("worker_bridge_failure_attribution"),
        worker_bridge_outcome.get("worker_bridge_materialization_blocker"),
        worker_bridge_outcome.get("pre_worker_startup_blocker"),
    ):
        label = _public_safe_benchmark_label(item)
        if label and label not in {"none", "unknown", "missing"} and label not in labels:
            labels.append(label)

    official_score: dict[str, Any] = {
        "kind": (
            _public_safe_benchmark_label(official.get("kind"))
            or _public_safe_benchmark_label(benchmark_run.get("official_score_source"))
            or "benchmark_run_official_score"
        ),
    }
    if isinstance(score_value, (int, float)) and not isinstance(score_value, bool):
        official_score["value"] = score_value
    if isinstance(passed, bool):
        official_score["passed"] = passed

    projected: dict[str, Any] = {
        "schema_version": "benchmark_result_v0",
        "task_id": task_id,
        "scenario_id": safe_mode,
        "worker_mode": (
            _public_safe_benchmark_label(benchmark_run.get("worker_mode"))
            or "benchmark_run_worker"
        ),
        "terminal_state": terminal_state,
        "official_task_score": official_score,
        "trace_publicness": (
            _public_safe_benchmark_label(benchmark_run.get("trace_publicness"))
            or _public_safe_benchmark_label(worker_bridge_outcome.get("trace_publicness"))
            or "compact_counts_only_no_raw_trace"
        ),
        "source_schema_version": "benchmark_run_v0",
    }
    if labels:
        projected["failure_attribution_labels"] = labels[:8]
    return projected


def build_benchmark_baseline_failure_gate_comparison(
    *,
    baseline_result: dict[str, Any],
    benchmark_id: str,
    baseline_mode: str = "codex_cli_goal_mode",
    treatment_scenario_id: str = "codex_loopx",
    comparison_id: str | None = None,
    failure_phase: str | None = None,
    failure_class: str | None = None,
    failure_attribution_labels: Iterable[str] | None = None,
    control_plane_addressable: bool = False,
    same_task_semantics: bool = False,
    same_runner_protocol: bool = False,
    trace_publicness_verified: bool = False,
    baseline_attempt_count: int = 1,
    minimum_next_evidence: str | None = None,
    negative_selection_reason: str | None = None,
    next_action: str | None = None,
    evidence_refs: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a public-safe baseline-failure gate comparison from compact result.

    The reducer is benchmark-generic: callers must explicitly mark whether the
    observed baseline failure is control-plane-addressable. Without that signal
    the comparison is a negative-selection gate and must not route to treatment.
    """

    if baseline_result.get("schema_version") != "benchmark_result_v0":
        raise ValueError("baseline_result must be compact benchmark_result_v0")

    task_id = _public_safe_benchmark_label(baseline_result.get("task_id")) or "unknown_task"
    baseline_scenario_id = (
        _public_safe_benchmark_label(baseline_result.get("scenario_id"))
        or _public_safe_benchmark_label(baseline_mode)
        or "baseline"
    )
    safe_benchmark_id = _public_safe_benchmark_label(benchmark_id) or "benchmark"
    safe_treatment_id = (
        _public_safe_benchmark_label(treatment_scenario_id)
        or "treatment"
    )
    safe_baseline_mode = (
        _public_safe_benchmark_label(baseline_mode)
        or "codex_cli_goal_mode"
    )
    terminal_state = (
        _public_safe_benchmark_label(baseline_result.get("terminal_state"))
        or "unknown"
    )
    baseline_failed = _benchmark_result_failed(baseline_result)
    labels = [
        label
        for label in (
            _public_safe_benchmark_label(item)
            for item in (failure_attribution_labels or [])
        )
        if label
    ]
    result_labels = baseline_result.get("failure_attribution_labels")
    if isinstance(result_labels, list):
        for item in result_labels:
            label = _public_safe_benchmark_label(item)
            if label and label not in labels:
                labels.append(label)
    safe_failure_phase = (
        _public_safe_benchmark_label(failure_phase)
        or ("unknown_failure_phase" if baseline_failed else "not_failed")
    )
    safe_failure_class = (
        _public_safe_benchmark_label(failure_class)
        or (labels[0] if labels else None)
        or ("unclassified_baseline_failure" if baseline_failed else "baseline_not_failed")
    )
    same_task = bool(same_task_semantics)
    same_runner = bool(same_runner_protocol)
    trace_public = bool(trace_publicness_verified)
    addressable = bool(control_plane_addressable)
    treatment_eligible = (
        baseline_failed
        and addressable
        and same_task
        and same_runner
        and trace_public
    )

    if treatment_eligible:
        default_minimum_next = (
            "run the LoopX treatment arm on the same compactly verified task"
        )
        default_negative_reason = ""
    elif not baseline_failed:
        default_minimum_next = "select a failed goal-mode baseline before treatment"
        default_negative_reason = "baseline did not fail"
    elif not addressable:
        default_minimum_next = (
            "attribute a control-plane-addressable goal-mode baseline failure"
        )
        default_negative_reason = "baseline failure is not marked control-plane-addressable"
    elif not same_task:
        default_minimum_next = "verify same task semantics before treatment"
        default_negative_reason = "same task semantics not verified"
    elif not same_runner:
        default_minimum_next = "verify same runner protocol before treatment"
        default_negative_reason = "same runner protocol not verified"
    else:
        default_minimum_next = "verify trace publicness before treatment"
        default_negative_reason = "trace publicness not verified"

    gate: dict[str, Any] = {
        "schema_version": "benchmark_baseline_failure_gate_v0",
        "baseline_mode": safe_baseline_mode,
        "baseline_scenario_id": baseline_scenario_id,
        "baseline_terminal_state": terminal_state,
        "baseline_failed": baseline_failed,
        "failure_phase": safe_failure_phase,
        "failure_class": safe_failure_class,
        "control_plane_addressable": addressable,
        "treatment_eligible": treatment_eligible,
        "same_task_semantics": same_task,
        "same_runner_protocol": same_runner,
        "trace_publicness_verified": trace_public,
        "baseline_attempt_count": max(1, int(baseline_attempt_count)),
        "minimum_next_evidence": (
            _public_safe_benchmark_label(minimum_next_evidence, limit=180)
            or default_minimum_next
        ),
    }
    safe_negative_reason = _public_safe_benchmark_label(
        negative_selection_reason or default_negative_reason,
        limit=180,
    )
    if safe_negative_reason:
        gate["negative_selection_reason"] = safe_negative_reason
    if labels:
        gate["failure_attribution_labels"] = labels[:8]
    safe_evidence_refs = [
        ref
        for ref in (
            _public_safe_benchmark_label(item, limit=180)
            for item in (evidence_refs or [])
        )
        if ref
    ]
    if not safe_evidence_refs:
        safe_evidence_refs = [f"benchmark_result_v0:{baseline_scenario_id}"]
    gate["evidence_refs"] = safe_evidence_refs[:8]
    safe_next_action = _public_safe_benchmark_label(next_action, limit=180)
    if safe_next_action:
        gate["next_action"] = safe_next_action

    safe_comparison_id = (
        _public_safe_benchmark_label(comparison_id)
        or f"{task_id}_{baseline_scenario_id}_baseline_failure_gate"
    )[:180]
    comparison: dict[str, Any] = {
        "schema_version": "benchmark_comparison_v0",
        "task_id": task_id,
        "comparison_id": safe_comparison_id,
        "benchmark_id": safe_benchmark_id,
        "mode_pair": [baseline_scenario_id, safe_treatment_id],
        "baseline_scenario_id": baseline_scenario_id,
        "treatment_scenario_id": safe_treatment_id,
        "baseline_failure_gate": gate,
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": False,
            "raw_trace_excluded": True,
            "credential_values_recorded": False,
        },
        "decision": {
            "score_uplift": False,
            "validation_enhancement_point": treatment_eligible,
            "why": (
                "Baseline failure is gate-eligible for treatment"
                if treatment_eligible
                else "Baseline is negative-selected before treatment"
            ),
        },
    }
    if safe_next_action:
        comparison["next_action"] = safe_next_action
    if labels:
        comparison["failure_attribution_labels"] = labels[:8]
    return comparison
