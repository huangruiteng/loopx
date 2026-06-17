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
    SKILLSBENCH_DEFAULT_DATASET,
    SKILLSBENCH_DEFAULT_MODEL,
    SKILLSBENCH_DEFAULT_ROUTE,
    SKILLSBENCH_DEFAULT_TASK,
    SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH,
    SKILLSBENCH_ROUTES,
    skillsbench_job_name,
    skillsbench_route_contract,
    skillsbench_runner_error_attribution,
    skillsbench_runner_error_fingerprint,
)


TERMINAL_BENCH_MODES = (
    "hardened-codex",
    "passive-observed-codex",
    "codex-goal-mode",
    "codex-goal-harness",
    "goal-harness-managed-codex",
)

TERMINAL_BENCH_DEFAULT_DATASET = "terminal-bench@2.0"
TERMINAL_BENCH_DEFAULT_TASK = "build-cython-ext"
TERMINAL_BENCH_DEFAULT_MODEL = "gpt-5.5"
BENCHMARK_MODEL_CONTROL_SCHEMA_VERSION = "benchmark_model_control_v0"
CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL = "codex_acp_set_model_unsupported"
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
TERMINAL_BENCH_COMPACT_FAILURE_MARKER_SCHEMA = (
    "terminal_bench_compact_failure_marker_v0"
)
TERMINAL_BENCH_RESULT_FINALIZATION_GATE_SCHEMA = (
    "terminal_bench_result_finalization_gate_v0"
)
TERMINAL_BENCH_RUN_LEDGER_CLOSEOUT_SCHEMA = (
    "terminal_bench_run_ledger_closeout_v0"
)
TERMINAL_BENCH_ENVIRONMENT_SETUP_READINESS_SCHEMA = (
    "terminal_bench_environment_setup_readiness_preflight_v0"
)
TERMINAL_BENCH_ENVIRONMENT_SETUP_PROBE_GATE_SCHEMA = (
    "terminal_bench_environment_setup_probe_gate_v0"
)
TERMINAL_BENCH_ENVIRONMENT_SETUP_PROBE_LAUNCH_SCHEMA = (
    "terminal_bench_environment_setup_probe_launch_v0"
)
TERMINAL_BENCH_CASE_RUN_LAUNCH_SCHEMA = (
    "terminal_bench_case_run_launch_v0"
)
TERMINAL_BENCH_LAUNCH_MATERIALIZATION_OBSERVATION_SCHEMA = (
    "terminal_bench_launch_materialization_observation_v0"
)
TERMINAL_BENCH_AGENT_SETUP_READINESS_SCHEMA = (
    "terminal_bench_agent_setup_readiness_v0"
)
TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA = (
    "terminal_bench_worker_setup_diagnostic_v0"
)
TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_PROFILE_SCHEMA = (
    "terminal_bench_setup_timeout_repair_profile_v0"
)
TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING = (
    "runtime_install_if_missing"
)
TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING = "require_existing_codex"
TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES = (
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING,
)
TERMINAL_BENCH_CODEX_RUNTIME_INSTALL_ALLOW_ENVIRONMENT_HOSTS = (
    "registry.npmjs.org",
    "raw.githubusercontent.com",
    "github.com",
    "nodejs.org",
    "deb.debian.org",
    "security.debian.org",
    "archive.ubuntu.com",
    "dl-cdn.alpinelinux.org",
    "download.fedoraproject.org",
    "mirror.stream.centos.org",
)
TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH = (
    "worker_path_preprovisioned"
)
TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED = (
    "runtime_install_extended_setup"
)
TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES = (
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED,
)
TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_AGENT_TIMEOUT_MULTIPLIER = 8.0
TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_AGENT_SETUP_TIMEOUT_MULTIPLIER = 8.0
TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC = 45
TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE = (
    "goal-harness-worker-setup-diagnostic.json"
)
TERMINAL_BENCH_DETACHED_PROCESS_STATES = {"unknown", "running", "ended"}
TERMINAL_BENCH_ACTIVE_JOB_STALE_SECONDS = 10 * 60
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
TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE = "codex_goal_mode_baseline"
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
TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE = (
    "codex_goal_mode_slash_command_no_goal_harness_state"
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
TERMINAL_BENCH_MANAGED_CODEX_GOAL_HARNESS_KWARGS = (
    "goal_harness_policy_version",
    "goal_harness_behavior_spec_id",
    "goal_harness_ablation_mode",
    "goal_harness_mode",
    "goal_harness_goal_id",
    "goal_harness_access_packet_mode",
    "goal_harness_trace_publicness",
    "goal_harness_counter_trace",
    "goal_harness_cli_bridge_enabled",
    "goal_harness_command_prefix",
    "goal_harness_runtime_preflight_command",
    "goal_harness_registry_arg",
    "goal_harness_runtime_root_arg",
    "goal_harness_scan_path",
    "goal_harness_benchmark_run_json",
    "goal_harness_benchmark_run_schema_version",
    "goal_harness_benchmark_run_writeback_contract",
    "goal_harness_counter_trace_json",
    "goal_harness_classification",
    "goal_harness_append_execute_enabled",
    "goal_harness_worker_materialization_probe_only",
    "goal_harness_active_user_intervention_enabled",
    "goal_harness_active_user_feed_jsonl",
    "goal_harness_active_user_observation_json",
    "goal_harness_active_user_observe_command",
    "goal_harness_active_user_channel_surface",
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
AGENTS_LAST_EXAM_LOCAL_PREFLIGHT_SCHEMA_VERSION = (
    "agents_last_exam_local_preflight_v0"
)
AGENTS_LAST_EXAM_LOCAL_DRY_RUN_PLAN_SCHEMA_VERSION = (
    "agents_last_exam_local_dry_run_plan_v0"
)
AGENTS_LAST_EXAM_LOCAL_RUNNER_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_local_runner_readiness_v0"
)
AGENTS_LAST_EXAM_LOCAL_SOURCE_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_local_source_readiness_v0"
)
AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_task_material_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_scan_v0"
)
AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_candidate_task_data_scan_v0"
)
AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION = (
    "agents_last_exam_local_launch_packet_v0"
)
AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION = (
    "agents_last_exam_local_exact_dry_run_result_v0"
)
AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_task_material_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_scan_v0"
)
AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_candidate_task_data_scan_v0"
)
AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION = (
    "agents_last_exam_local_launch_packet_v0"
)
AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION = (
    "agents_last_exam_local_exact_dry_run_result_v0"
)
AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION = (
    "agents_last_exam_host_codex_cli_route_v0"
)
AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION = (
    "agents_last_exam_host_codex_cua_no_task_smoke_v0"
)
AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION = (
    "agents_last_exam_validation_run_gate_v0"
)
AGENTS_LAST_EXAM_TRACE_PUBLICNESS = (
    "compact_public_safe_no_task_body_no_trajectory_no_output"
)
AGENTS_LAST_EXAM_CASE_GOAL_ID = benchmark_case_goal_id(AGENTS_LAST_EXAM_BENCHMARK_ID)
AGENTS_LAST_EXAM_CASE_STATE_PATH = benchmark_case_active_state_path(
    AGENTS_LAST_EXAM_CASE_GOAL_ID
)
AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE = "agentslastexam/ale-kasm:latest"
AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE = "ale-ubuntu22-docker:latest"
AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT = "cpu-free-ubuntu"
AGENTS_LAST_EXAM_DEFAULT_REPO_URL = (
    "https://github.com/rdi-berkeley/agents-last-exam.git"
)
AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED = (
    "trajectory.json",
    "origin_log",
    "output",
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
    calls = interaction.get("goal_harness_cli_calls") if isinstance(interaction.get("goal_harness_cli_calls"), dict) else {}
    worker_cli_total = run.get("worker_goal_harness_cli_call_total")
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
    state_reads = interaction.get("goal_harness_state_reads")
    if not isinstance(state_reads, int) or isinstance(state_reads, bool):
        state_reads = 0
    state_writes = interaction.get("goal_harness_state_writes")
    if not isinstance(state_writes, int) or isinstance(state_writes, bool):
        state_writes = 0
    outer_controller_present = bool(
        interaction.get("goal_harness_automation_loop") is True
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
        "worker_goal_harness_cli_call_total": worker_cli_total,
        "worker_benchmark_run_schema_ok_count": worker_file_count,
        "outer_goal_harness_controller_present": outer_controller_present,
        "outer_goal_harness_controller_action_decisions": controller_action_decisions,
        "outer_goal_harness_heartbeat_count": heartbeat_count,
        "goal_harness_state_reads": state_reads,
        "goal_harness_state_writes": state_writes,
        "active_user_observed_after_worker_start": bool(
            observation.get("observed_after_worker_start")
            or observation.get("worker_observation_proof")
        ),
        "present": present,
    }


def _compact_exception_kind(exception_type: Any) -> str:
    """Classify public-safe compact exception type strings."""

    if not isinstance(exception_type, str) or not exception_type.strip():
        return ""
    lowered = exception_type.strip().lower()
    if "setup" in lowered and "timeout" in lowered:
        return "agent_setup_timeout"
    if "timeout" in lowered:
        return "agent_timeout"
    if "agent" in lowered and "setup" in lowered:
        return "agent_setup_failure"
    if lowered not in {"none", "null", "no_exception"}:
        return "agent_exception"
    return ""


def _terminal_bench_agent_failure_attribution_labels(
    *,
    trial: dict[str, Any],
    exception_type: Any,
) -> set[str]:
    """Classify agent-launch failures without recording raw stderr/traceback."""

    if exception_type in (None, "", "none", "AgentTimeoutError"):
        return set()
    labels: set[str] = set()
    exception_info = (
        trial.get("exception_info")
        if isinstance(trial.get("exception_info"), dict)
        else {}
    )
    text = " ".join(
        str(value)
        for value in (
            exception_info.get("exception_message"),
            exception_info.get("exception_traceback"),
        )
        if isinstance(value, str)
    ).lower()
    if exception_type == "NonZeroAgentExitCodeError":
        labels.add("agent_process_nonzero_exit_before_solution_attempt")
    if "codex exec" in text and "turn.failed" in text:
        labels.add("codex_cli_turn_failed_before_solution_attempt")
    if "invalid_request_error" in text and "model" in text:
        labels.add("codex_model_access_failure_before_solution_attempt")
    if "model is not supported" in text and "chatgpt account" in text:
        labels.add("codex_model_access_unsupported_for_account")
    return labels


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
    if "missing_treatment_worker_goal_harness_evidence" in blockers:
        candidates.append("worker_visible_goal_harness_evidence_gate")
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
        blocked_reason = "compact_result_has_no_goal_harness_learning_signal"
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
        or benchmark_comparison.get("with_goal_harness_overhead_ms")
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
        learning_status = "generic_goal_harness_repair_or_attribution_required"
    elif validation_candidate:
        learning_status = "candidate_score_recovery_needs_review"
    elif bool(
        (claim_review.get("treatment_worker_evidence") or {}).get("present")
        if isinstance(claim_review.get("treatment_worker_evidence"), dict)
        else False
    ):
        learning_status = "loop_validation_or_overhead_evidence_only"
    else:
        learning_status = "no_goal_harness_validation_gain"
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


def agent_kwargs_from_invocation(invocation: Iterable[Any]) -> dict[str, str]:
    """Extract --agent-kwarg key/value pairs without interpreting values."""

    argv = [str(item) for item in invocation if isinstance(item, (str, int, float))]
    kwargs: dict[str, str] = {}
    for index, value in enumerate(argv):
        if value != "--agent-kwarg" or index + 1 >= len(argv):
            continue
        raw = argv[index + 1]
        key, separator, val = raw.partition("=")
        key = key.strip()
        if not separator or not key:
            continue
        kwargs[key] = val
    return kwargs


def _compact_truthy_flag(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _terminal_bench_lock_first_agent_kwargs(lock: dict[str, Any]) -> dict[str, Any]:
    trials = lock.get("trials") if isinstance(lock.get("trials"), list) else []
    for trial in trials:
        if not isinstance(trial, dict):
            continue
        agent = trial.get("agent") if isinstance(trial.get("agent"), dict) else {}
        kwargs = agent.get("kwargs") if isinstance(agent.get("kwargs"), dict) else {}
        if kwargs:
            return kwargs
    return {}


def _terminal_bench_lock_worker_materialization_probe_only(
    lock: dict[str, Any],
) -> bool:
    kwargs = _terminal_bench_lock_first_agent_kwargs(lock)
    return _compact_truthy_flag(
        kwargs.get("goal_harness_worker_materialization_probe_only")
    )


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
        if key.startswith("goal_harness_") and key not in keys:
            keys.append(key)
    return sorted(keys)[:80]


def build_benchmark_adapter_kwarg_absorption_review(
    *,
    adapter_label: str,
    agent_kwargs: dict[str, Any],
    accepted_goal_harness_kwargs: Iterable[Any],
    allowed_base_passthrough: Iterable[Any] = (),
) -> dict[str, Any]:
    """Review whether generated goal_harness_* kwargs are adapter-absorbed."""

    generated_keys = _public_safe_kwarg_key_list(agent_kwargs.keys())
    accepted_keys = set(_public_safe_kwarg_key_list(accepted_goal_harness_kwargs))
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
            "consume_or_reject_generated_goal_harness_kwargs_before_worker_start"
        )
    elif generated_keys:
        classification = "adapter_kwargs_absorbed"
        next_required_action = "adapter_kwarg_absorption_guard_passed"
    else:
        classification = "adapter_goal_harness_kwargs_missing"
        next_required_action = "record_generated_goal_harness_kwargs_before_run"

    return {
        "schema_version": BENCHMARK_ADAPTER_KWARG_ABSORPTION_REVIEW_SCHEMA_VERSION,
        "adapter_label": adapter_label,
        "classification": classification,
        "clean": bool(generated_keys) and not leaked_keys,
        "generated_goal_harness_kwarg_count": len(generated_keys),
        "absorbed_goal_harness_kwarg_count": len(absorbed_keys),
        "leaked_goal_harness_kwarg_count": len(leaked_keys),
        "generated_goal_harness_kwarg_keys": generated_keys,
        "absorbed_goal_harness_kwarg_keys": absorbed_keys,
        "leaked_goal_harness_kwarg_keys": leaked_keys,
        "accepted_goal_harness_kwarg_keys": sorted(accepted_keys)[:80],
        "allowed_base_passthrough_keys": sorted(passthrough_keys)[:40],
        "next_required_action": next_required_action,
        "claim_boundary": {
            "kwarg_values_recorded": False,
            "local_paths_recorded": False,
            "adapter_absorption_required_before_worker_start": True,
            "base_constructor_may_receive_generated_goal_harness_kwargs": False,
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


def _benchmark_lifecycle_ready_preflight(value: dict[str, Any] | None) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    nested_run = value.get("benchmark_run")
    if isinstance(nested_run, dict) and _benchmark_lifecycle_ready_preflight(nested_run):
        return True
    nested_guard = value.get("preflight_guard")
    if isinstance(nested_guard, dict) and _benchmark_lifecycle_ready_preflight(nested_guard):
        return True
    launch_summary = value.get("private_runner_launch_summary")
    if isinstance(launch_summary, dict) and launch_summary.get("ready") is True:
        return True
    if value.get("ready") is True:
        return True
    if value.get("ok") is True and str(value.get("first_blocker") or "").startswith("ready"):
        return True
    return str(value.get("first_blocker") or "") in {
        "ready_for_private_managed_no_upload_pilot_review",
        "ready_for_operator_triggered_no_upload_ale_dry_run",
    }


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


def _benchmark_run_environment_setup_failure_context(
    benchmark_run: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(benchmark_run, dict):
        return {}

    candidates: list[Any] = [
        benchmark_run.get("environment_setup_failure_context"),
    ]
    worker_bridge = (
        benchmark_run.get("worker_bridge_outcome")
        if isinstance(benchmark_run.get("worker_bridge_outcome"), dict)
        else {}
    )
    candidates.append(worker_bridge.get("environment_setup_failure_context"))
    for trial in benchmark_run.get("trials") or []:
        if isinstance(trial, dict):
            candidates.append(trial.get("environment_setup_failure_context"))

    for item in candidates:
        if not isinstance(item, dict):
            continue
        schema = _public_safe_benchmark_label(item.get("schema_version"))
        if not schema:
            continue
        compact: dict[str, Any] = {"schema_version": schema}
        for field in (
            "surface",
            "failure_kind",
            "diagnostic_granularity",
            "exception_type",
            "timeout_signal",
            "resource_signal",
            "environment_setup_duration_tier",
            "next_probe",
        ):
            text = _public_safe_benchmark_label(item.get(field), limit=140)
            if text:
                compact[field] = text
        for field in (
            "environment_setup_present",
            "environment_setup_started",
            "environment_setup_finished",
            "agent_setup_started",
            "agent_execution_started",
            "worker_trace_present",
            "worker_benchmark_run_present",
        ):
            if isinstance(item.get(field), bool):
                compact[field] = item[field]
        seconds = item.get("environment_setup_duration_seconds")
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
            compact["environment_setup_duration_seconds"] = seconds
        return compact

    count = benchmark_run.get("environment_setup_failure_before_worker_count")
    repeat_blocked = str(benchmark_run.get("repeat_blocked_by") or "")
    first_blocker = str(benchmark_run.get("first_blocker") or "")
    worker_status = str(benchmark_run.get("worker_bridge_materialization_status") or "")
    if (
        (isinstance(count, int) and not isinstance(count, bool) and count > 0)
        or repeat_blocked == "environment_setup_failed_before_worker"
        or first_blocker == "environment_setup_failed_before_worker"
        or worker_status == "environment_setup_failed_before_worker"
    ):
        return {
            "schema_version": TERMINAL_BENCH_ENVIRONMENT_SETUP_READINESS_SCHEMA,
            "surface": "harbor_environment_setup",
            "failure_kind": "environment_setup_failed_before_worker",
            "diagnostic_granularity": "compact_counts_only_no_raw_logs",
            "next_probe": "environment_setup_readiness_preflight_before_repeat",
        }
    return {}


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


def _terminal_bench_harbor_run_help_capability(
    help_text: str | None,
    *,
    probe_runner_help: bool = False,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    """Return compact Harbor run capability facts without storing raw help."""

    command_exit_code: int | None = None
    command_timed_out = False
    probe_error = ""
    text = help_text or ""
    if help_text is None and probe_runner_help:
        try:
            result = subprocess.run(
                [
                    resolve_terminal_bench_runner_binary("uvx"),
                    "--from",
                    TERMINAL_BENCH_HARBOR_REF,
                    "harbor",
                    "run",
                    "--help",
                ],
                check=False,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                env=_probe_env(),
            )
            command_exit_code = result.returncode
            if result.returncode == 0:
                text = "\n".join([result.stdout or "", result.stderr or ""])
            else:
                probe_error = "harbor_run_help_nonzero"
        except subprocess.TimeoutExpired:
            command_timed_out = True
            probe_error = "harbor_run_help_timeout"
        except OSError:
            probe_error = "harbor_run_help_probe_failed"

    lowered = text.lower()
    setup_only_markers = (
        "--setup-only",
        "--environment-only",
        "--build-environment-only",
        "--prepare-only",
        "--no-agent",
        "--skip-agent",
    )
    setup_only_options = [marker for marker in setup_only_markers if marker in lowered]
    help_available = bool(text)
    first_blocker = ""
    if probe_error:
        first_blocker = probe_error
    elif not help_available:
        first_blocker = "harbor_run_help_not_probed"

    return {
        "schema_version": "terminal_bench_harbor_run_help_capability_v0",
        "probed": bool(help_text is not None or probe_runner_help),
        "probe_runner_help": bool(probe_runner_help),
        "probe_ok": bool(help_available and not probe_error),
        "first_blocker": first_blocker,
        "command_exit_code": command_exit_code,
        "command_timed_out": command_timed_out,
        "runner_binary_name": "uvx",
        "raw_help_recorded": False,
        "command_argv_recorded": False,
        "setup_only_option_present": bool(setup_only_options),
        "setup_only_option_markers": setup_only_options,
        "nop_agent_option_present": "nop" in lowered,
        "disable_verification_option_present": "--disable-verifica" in lowered,
        "upload_option_present": "--upload" in lowered,
        "docker_invoked": False,
        "terminal_bench_invoked": False,
        "codex_invoked": False,
        "model_api_invoked": False,
        "upload_invoked": False,
    }


def _terminal_bench_environment_setup_probe_command_template(
    *,
    dataset: str,
    task_id: str,
    job_name: str,
) -> list[str]:
    return [
        "uvx",
        "--from",
        TERMINAL_BENCH_HARBOR_REF,
        "harbor",
        "run",
        *_terminal_bench_dataset_args(dataset),
        "--include-task-name",
        task_id,
        "--agent",
        "nop",
        "--env",
        "docker",
        "--n-attempts",
        "1",
        "--n-concurrent",
        "1",
        "--disable-verification",
        "--jobs-dir",
        "<private-jobs-dir>",
        "--job-name",
        job_name,
    ]


def build_terminal_bench_environment_setup_probe_gate(
    *,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str = TERMINAL_BENCH_DEFAULT_TASK,
    preflight: dict[str, Any] | None = None,
    previous_benchmark_run: dict[str, Any] | None = None,
    harbor_run_help_text: str | None = None,
    probe_runner_help: bool = False,
) -> dict[str, Any]:
    """Gate a same-task Terminal-Bench environment setup probe."""

    previous = previous_benchmark_run if isinstance(previous_benchmark_run, dict) else {}
    previous_context = _benchmark_run_environment_setup_failure_context(previous)
    preflight_ready = _benchmark_lifecycle_ready_preflight(preflight)
    help_capability = _terminal_bench_harbor_run_help_capability(
        harbor_run_help_text,
        probe_runner_help=probe_runner_help,
    )
    direct_setup_only_allowed = bool(
        preflight_ready
        and previous_context
        and help_capability.get("setup_only_option_present") is True
    )
    nop_disable_verification_allowed = bool(
        preflight_ready
        and previous_context
        and help_capability.get("nop_agent_option_present") is True
        and help_capability.get("disable_verification_option_present") is True
        and help_capability.get("upload_option_present") is True
    )
    environment_setup_probe_allowed = bool(
        direct_setup_only_allowed or nop_disable_verification_allowed
    )

    blockers: list[str] = []
    if not previous_context:
        blockers.append("previous_environment_setup_failure_context_missing")
    if not preflight_ready:
        blockers.append("no_run_preflight_not_ready")
    if help_capability.get("probe_ok") is not True:
        blockers.append(
            str(help_capability.get("first_blocker") or "harbor_run_help_not_ready")
        )
    if (
        preflight_ready
        and previous_context
        and help_capability.get("probe_ok") is True
        and not environment_setup_probe_allowed
    ):
        blockers.append("safe_environment_setup_probe_route_missing")

    if environment_setup_probe_allowed:
        next_action = "run_nop_disable_verification_environment_setup_probe"
    elif previous_context:
        next_action = "select_next_material_ready_candidate"
    else:
        next_action = "provide_compact_previous_environment_setup_failure"

    task_label = str(task_id or TERMINAL_BENCH_DEFAULT_TASK)
    job_task = task_label.replace("-", "_")
    command_template = _terminal_bench_environment_setup_probe_command_template(
        dataset=str(dataset or TERMINAL_BENCH_DEFAULT_DATASET),
        task_id=task_label,
        job_name=f"terminal_bench_{job_task}_environment_setup_probe",
    )
    return {
        "schema_version": TERMINAL_BENCH_ENVIRONMENT_SETUP_PROBE_GATE_SCHEMA,
        "benchmark_id": str(dataset or TERMINAL_BENCH_DEFAULT_DATASET),
        "task_id": task_label,
        "preflight_ready": preflight_ready,
        "previous_environment_setup_failure_present": bool(previous_context),
        "previous_environment_setup_failure_context": previous_context,
        "harbor_run_help_capability": help_capability,
        "direct_setup_only_route_allowed": direct_setup_only_allowed,
        "nop_disable_verification_probe_allowed": nop_disable_verification_allowed,
        "environment_setup_probe_allowed": environment_setup_probe_allowed,
        "same_task_repeat_allowed": False,
        "repeat_blocked_by": "environment_setup_failed_before_worker"
        if previous_context
        else "previous_environment_setup_failure_context_missing",
        "first_blocker": blockers[0] if blockers else "ready_for_environment_setup_probe",
        "blockers": blockers,
        "next_allowed_action": next_action,
        "probe_command_template": command_template,
        "probe_contract": {
            "agent": "nop",
            "codex_invoked": False,
            "verifier_disabled": True,
            "docker_task_may_start": environment_setup_probe_allowed,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_help_recorded": False,
            "raw_artifacts_read": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "credential_values_recorded": False,
            "codex_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }


def launch_terminal_bench_environment_setup_probe(
    *,
    gate: dict[str, Any],
    jobs_dir: str | Path,
    run_root: str | Path,
    wait_seconds: int = 20,
    execute: bool = False,
    command_override: list[str] | None = None,
) -> dict[str, Any]:
    """Launch a gated Terminal-Bench setup probe with compact-only reporting."""

    if not isinstance(gate, dict):
        raise ValueError("gate must be a terminal_bench_environment_setup_probe_gate_v0 object")
    if gate.get("environment_setup_probe_allowed") is not True:
        raise ValueError("environment setup probe gate is not allowed")
    contract = gate.get("probe_contract") if isinstance(gate.get("probe_contract"), dict) else {}
    if contract.get("agent") != "nop":
        raise ValueError("environment setup probe launcher requires probe_contract.agent=nop")
    if contract.get("no_upload") is not True or contract.get("submit_eligible") is not False:
        raise ValueError("environment setup probe launcher requires no-upload/no-submit boundary")
    if contract.get("codex_invoked") is not False:
        raise ValueError("environment setup probe launcher must not invoke Codex")
    if contract.get("verifier_disabled") is not True:
        raise ValueError("environment setup probe launcher requires verifier_disabled=true")

    template = gate.get("probe_command_template")
    if not isinstance(template, list) or not all(isinstance(part, str) for part in template):
        raise ValueError("gate probe_command_template must be a string argv list")
    argv = [str(jobs_dir) if part == "<private-jobs-dir>" else part for part in template]
    if command_override is not None:
        argv = list(command_override)
    if "--upload" in argv:
        raise ValueError("environment setup probe command must not include --upload")
    if command_override is None and "--disable-verification" not in argv:
        raise ValueError("environment setup probe command must disable verification")

    job_name = ""
    if "--job-name" in argv:
        index = argv.index("--job-name")
        if index + 1 < len(argv):
            job_name = Path(argv[index + 1]).name
    if not job_name:
        job_name = Path(str(gate.get("task_id") or TERMINAL_BENCH_DEFAULT_TASK)).name

    parsed_wait_seconds = max(0, int(wait_seconds))
    run_root_path = Path(run_root).expanduser()
    jobs_dir_path = Path(jobs_dir).expanduser()
    run_basename = run_root_path.name
    output_log = run_root_path / "probe_stdout_stderr.private.log"
    command_file = run_root_path / "probe_command.private.sh"
    pid_file = run_root_path / "probe.pid.private"

    payload: dict[str, Any] = {
        "schema_version": TERMINAL_BENCH_ENVIRONMENT_SETUP_PROBE_LAUNCH_SCHEMA,
        "ok": True,
        "dry_run": not execute,
        "run_basename": run_basename,
        "job_name": job_name,
        "process_started": False,
        "process_state": "not_started",
        "detached_process_group": False,
        "pid": None,
        "returncode": None,
        "wait_seconds": parsed_wait_seconds,
        "process_timed_out": False,
        "command_ref": argv[2] if len(argv) > 2 and argv[:2] == ["uvx", "--from"] else "override",
        "command_shape": {
            "argv_count": len(argv),
            "uses_uvx": bool(argv and argv[0] == "uvx"),
            "uses_harbor_run": "harbor" in argv and "run" in argv,
            "agent_nop": "--agent" in argv and "nop" in argv,
            "disable_verification": "--disable-verification" in argv,
            "upload_flag_present": "--upload" in argv,
            "jobs_dir_placeholder_present": "<private-jobs-dir>" in argv,
        },
        "contract": dict(contract),
        "boundary": {
            "no_upload": True,
            "submit_eligible": False,
            "codex_invoked": False,
            "model_api_invoked": False,
            "verifier_disabled": True,
            "docker_task_may_start": contract.get("docker_task_may_start") is True,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "private_outputs": {
            "stdout_stderr_log_private": True,
            "pid_file_private": True,
            "command_file_private": True,
        },
    }

    if not execute:
        return payload

    run_root_path.mkdir(parents=True, exist_ok=True)
    jobs_dir_path.mkdir(parents=True, exist_ok=True)
    command_file.write_text(" ".join(shlex.quote(part) for part in argv) + "\n", encoding="utf-8")
    with output_log.open("ab") as stream:
        process = subprocess.Popen(
            argv,
            stdout=stream,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()),
            close_fds=True,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    payload.update(
        {
            "process_started": True,
            "process_state": "running",
            "detached_process_group": True,
            "pid": process.pid,
        }
    )
    try:
        returncode = process.wait(timeout=parsed_wait_seconds)
        payload.update(
            {
                "process_state": "ended",
                "returncode": returncode,
                "process_timed_out": False,
            }
        )
    except subprocess.TimeoutExpired:
        payload["process_timed_out"] = True
        payload["process_state"] = "running"

    post_launch = summarize_terminal_bench_post_launch_materialization(
        jobs_dir_path,
        job_name=job_name,
        detached_process_state=payload["process_state"],
    )
    payload["post_launch_materialization"] = post_launch
    payload["ready_for_launch_state"] = post_launch.get("ready_for_launch_state") is True
    payload["ready_for_compact_result_ingest"] = (
        post_launch.get("ready_for_compact_result_ingest") is True
    )
    payload["ready_for_compact_failure_marker"] = (
        post_launch.get("ready_for_compact_failure_marker") is True
    )
    payload["compact_failure_class"] = post_launch.get("compact_failure_class")
    payload["first_blocker"] = post_launch.get("first_blocker")
    if payload["process_state"] == "ended" and payload["returncode"] not in (0, None):
        payload["exit_code_attribution"] = "probe_process_nonzero_exit"
    elif payload["process_state"] == "ended":
        payload["exit_code_attribution"] = "probe_process_zero_exit"
    else:
        payload["exit_code_attribution"] = "probe_process_still_running"

    public_path = run_root_path / "launch_summary.public.json"
    public_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_root_path / "post_launch_summary.public.json").write_text(
        json.dumps(post_launch, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def launch_terminal_bench_worker_materialization_probe(
    *,
    jobs_dir: str | Path,
    run_root: str | Path,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str = TERMINAL_BENCH_DEFAULT_TASK,
    model: str = TERMINAL_BENCH_DEFAULT_MODEL,
    mode: str = "codex-goal-mode",
    job_name: str | None = None,
    worker_codex_materialization_strategy: str = (
        TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH
    ),
    wait_seconds: int = 20,
    execute: bool = False,
) -> dict[str, Any]:
    """Launch a no-upload worker materialization probe without task solving."""

    if mode not in ("codex-goal-mode", "hardened-codex"):
        raise ValueError(
            "worker materialization probe supports codex-goal-mode or hardened-codex only"
        )
    if (
        worker_codex_materialization_strategy
        not in TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES
    ):
        raise ValueError(
            "worker_codex_materialization_strategy must be one of: "
            + ", ".join(TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES)
        )
    run_root_path = Path(run_root).expanduser()
    jobs_dir_path = Path(jobs_dir).expanduser()
    run_basename = run_root_path.name
    task_label = str(task_id or "all").replace("-", "_")
    public_job_name = (
        Path(job_name).name
        if job_name
        else f"terminal_bench_{task_label}_{mode.replace('-', '_')}_worker_materialization_probe"
    )
    launch = build_terminal_bench_private_runner_launch(
        mode=mode,
        dataset=dataset,
        task_id=task_id,
        model=model,
        jobs_dir=str(jobs_dir_path),
        job_name=public_job_name,
        setup_timeout_repair_profile=True,
        worker_codex_materialization_strategy=worker_codex_materialization_strategy,
        worker_materialization_probe_only=True,
    )
    argv = launch["argv"] if isinstance(launch.get("argv"), list) else []
    if "--upload" in argv:
        raise ValueError("worker materialization probe command must not upload")
    if "goal_harness_worker_materialization_probe_only=true" not in argv:
        raise ValueError("worker materialization probe kwarg missing from command")
    summary = summarize_terminal_bench_private_runner_launch(launch)
    if summary.get("no_upload_boundary") is not True or summary.get("submit_eligible"):
        raise ValueError(
            "worker materialization probe requires no-upload/no-submit boundary"
        )
    if summary.get("worker_materialization_probe_only") is not True:
        raise ValueError("worker materialization probe summary missing probe-only flag")

    parsed_wait_seconds = max(0, int(wait_seconds))
    output_log = run_root_path / "worker_materialization_probe_stdout_stderr.private.log"
    command_file = run_root_path / "worker_materialization_probe_command.private.sh"
    pid_file = run_root_path / "worker_materialization_probe.pid.private"
    payload: dict[str, Any] = {
        "schema_version": "terminal_bench_worker_materialization_probe_launch_v0",
        "ok": True,
        "dry_run": not execute,
        "run_basename": run_basename,
        "job_name": public_job_name,
        "process_started": False,
        "process_state": "not_started",
        "detached_process_group": False,
        "pid": None,
        "returncode": None,
        "wait_seconds": parsed_wait_seconds,
        "process_timed_out": False,
        "launch_summary": summary,
        "command_ref": (
            argv[2]
            if len(argv) > 2 and argv[:2] == ["uvx", "--from"]
            else "private_runner_launch"
        ),
        "command_shape": {
            "argv_count": len(argv),
            "uses_uvx": bool(argv and Path(str(argv[0])).name == "uvx"),
            "uses_harbor_run": "harbor" in argv and "run" in argv,
            "agent_import_path_present": "--agent-import-path" in argv,
            "worker_materialization_probe_only": (
                "goal_harness_worker_materialization_probe_only=true" in argv
            ),
            "upload_flag_present": "--upload" in argv,
            "jobs_dir_placeholder_present": "<private-jobs-dir>" in argv,
        },
        "boundary": {
            "no_upload": True,
            "submit_eligible": False,
            "worker_materialization_probe_only": True,
            "task_solver_invoked_by_probe": False,
            "model_api_expected": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "upload_invoked": False,
        },
        "private_outputs": {
            "stdout_stderr_log_private": True,
            "pid_file_private": True,
            "command_file_private": True,
        },
    }
    if not execute:
        return payload

    run_root_path.mkdir(parents=True, exist_ok=True)
    jobs_dir_path.mkdir(parents=True, exist_ok=True)
    command_file.write_text(
        " ".join(shlex.quote(str(part)) for part in argv) + "\n",
        encoding="utf-8",
    )
    launch_env = os.environ.copy()
    if isinstance(launch.get("env"), dict):
        launch_env.update(
            {
                str(key): str(value)
                for key, value in launch["env"].items()
                if isinstance(key, str)
            }
        )
    with output_log.open("ab") as stream:
        process = subprocess.Popen(
            [str(part) for part in argv],
            stdout=stream,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()),
            env=launch_env,
            close_fds=True,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    payload.update(
        {
            "process_started": True,
            "process_state": "running",
            "detached_process_group": True,
            "pid": process.pid,
        }
    )
    try:
        returncode = process.wait(timeout=parsed_wait_seconds)
        payload.update(
            {
                "process_state": "ended",
                "returncode": returncode,
                "process_timed_out": False,
            }
        )
    except subprocess.TimeoutExpired:
        payload["process_timed_out"] = True
        payload["process_state"] = "running"

    post_launch = summarize_terminal_bench_post_launch_materialization(
        jobs_dir_path,
        job_name=public_job_name,
        detached_process_state=payload["process_state"],
    )
    payload["post_launch_materialization"] = post_launch
    payload["ready_for_launch_state"] = post_launch.get("ready_for_launch_state") is True
    payload["ready_for_compact_result_ingest"] = (
        post_launch.get("ready_for_compact_result_ingest") is True
    )
    payload["ready_for_compact_failure_marker"] = (
        post_launch.get("ready_for_compact_failure_marker") is True
    )
    payload["compact_failure_class"] = post_launch.get("compact_failure_class")
    payload["first_blocker"] = post_launch.get("first_blocker")
    if payload["process_state"] == "ended" and payload["returncode"] not in (0, None):
        payload["exit_code_attribution"] = (
            "worker_materialization_probe_process_nonzero_exit"
        )
    elif payload["process_state"] == "ended":
        payload["exit_code_attribution"] = "worker_materialization_probe_process_zero_exit"
    else:
        payload["exit_code_attribution"] = "worker_materialization_probe_still_running"

    public_path = run_root_path / "worker_materialization_probe_launch.public.json"
    public_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root_path / "post_launch_summary.public.json").write_text(
        json.dumps(post_launch, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _detached_process_state_from_pid_file(pid_file: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "pid_file_present": pid_file.is_file(),
        "pid_parse_ok": False,
        "pid": None,
        "process_state": "unknown",
        "first_blocker": "",
        "raw_pid_file_path_recorded": False,
        "command_line_read": False,
    }
    if not pid_file.is_file():
        payload["first_blocker"] = "pid_file_missing"
        return payload
    text = pid_file.read_text(encoding="utf-8").strip()
    try:
        pid = int(text)
    except ValueError:
        payload["first_blocker"] = "pid_file_unparseable"
        return payload
    if pid <= 0:
        payload["first_blocker"] = "pid_file_invalid"
        return payload
    payload["pid"] = pid
    payload["pid_parse_ok"] = True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        payload["process_state"] = "ended"
    except PermissionError:
        payload["process_state"] = "unknown"
        payload["first_blocker"] = "pid_permission_denied"
    else:
        payload["process_state"] = "running"
    return payload


def _process_state_from_poll(process: subprocess.Popen[Any]) -> tuple[str, int | None]:
    returncode = process.poll()
    if returncode is None:
        return "running", None
    return "ended", int(returncode)


def wait_for_terminal_bench_launch_materialization(
    *,
    process: subprocess.Popen[Any],
    jobs_dir: str | Path,
    job_name: str | None,
    wait_seconds: int,
) -> dict[str, Any]:
    """Wait for compact job materialization without reading private artifacts."""

    deadline = time.monotonic() + max(0, int(wait_seconds))
    observations = 0
    process_state, returncode = _process_state_from_poll(process)
    post_launch = summarize_terminal_bench_post_launch_materialization(
        jobs_dir,
        job_name=job_name,
        detached_process_state=process_state,
    )
    observations += 1
    while (
        time.monotonic() < deadline
        and post_launch.get("ready_for_launch_state") is not True
        and post_launch.get("ready_for_compact_failure_marker") is not True
        and process_state != "ended"
    ):
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
        process_state, returncode = _process_state_from_poll(process)
        post_launch = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name=job_name,
            detached_process_state=process_state,
        )
        observations += 1

    materialized = post_launch.get("ready_for_launch_state") is True
    terminal_failure = post_launch.get("ready_for_compact_failure_marker") is True
    return {
        "schema_version": TERMINAL_BENCH_LAUNCH_MATERIALIZATION_OBSERVATION_SCHEMA,
        "wait_seconds": max(0, int(wait_seconds)),
        "observation_count": observations,
        "process_state": process_state,
        "returncode": returncode,
        "materialized": materialized,
        "terminal_compact_failure": terminal_failure,
        "first_blocker": post_launch.get("first_blocker"),
        "compact_failure_class": post_launch.get("compact_failure_class"),
        "post_launch_materialization": post_launch,
        "read_boundary": {
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "command_line_read": False,
            "raw_external_handle_payload_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }


def observe_terminal_bench_post_materialization_closeout(
    *,
    process: subprocess.Popen[Any],
    jobs_dir: str | Path,
    job_name: str | None,
    wait_seconds: int,
) -> dict[str, Any]:
    """Catch immediate no-trial closeout after a job becomes pollable."""

    deadline = time.monotonic() + max(0, int(wait_seconds))
    observations = 0
    process_state, returncode = _process_state_from_poll(process)
    post_launch = summarize_terminal_bench_post_launch_materialization(
        jobs_dir,
        job_name=job_name,
        detached_process_state=process_state,
        reconcile_stale_active=(process_state == "ended"),
    )
    observations += 1
    while (
        time.monotonic() < deadline
        and process_state == "running"
        and post_launch.get("ready_for_compact_result_ingest") is not True
        and post_launch.get("ready_for_compact_failure_marker") is not True
    ):
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
        process_state, returncode = _process_state_from_poll(process)
        post_launch = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name=job_name,
            detached_process_state=process_state,
            reconcile_stale_active=(process_state == "ended"),
        )
        observations += 1

    return {
        "schema_version": "terminal_bench_post_materialization_closeout_observation_v0",
        "wait_seconds": max(0, int(wait_seconds)),
        "observation_count": observations,
        "process_state": process_state,
        "returncode": returncode,
        "ready_for_compact_result_ingest": (
            post_launch.get("ready_for_compact_result_ingest") is True
        ),
        "terminal_compact_failure": (
            post_launch.get("ready_for_compact_failure_marker") is True
        ),
        "first_blocker": post_launch.get("first_blocker"),
        "compact_failure_class": post_launch.get("compact_failure_class"),
        "post_launch_materialization": post_launch,
        "read_boundary": {
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "command_line_read": False,
            "raw_external_handle_payload_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }


def build_terminal_bench_harbor_resume_command(
    *,
    job_path: str | Path,
    resolve_cli_paths: bool = True,
) -> list[str]:
    """Build a private no-upload Harbor resume command for a materialized job."""

    return [
        (
            resolve_terminal_bench_runner_binary("uvx")
            if resolve_cli_paths
            else "uvx"
        ),
        "--from",
        TERMINAL_BENCH_HARBOR_REF,
        "harbor",
        "job",
        "resume",
        "--job-path",
        str(Path(job_path).expanduser()),
    ]


def _terminal_bench_resume_recommended(
    post_launch: dict[str, Any],
) -> bool:
    """Return true when Harbor materialized a job that needs a no-upload resume."""

    return bool(
        post_launch.get("ready_for_launch_state") is True
        and post_launch.get("ready_for_compact_result_ingest") is not True
        and post_launch.get("job_active_without_trial_result") is True
        and int(post_launch.get("trial_result_present_count") or 0) <= 0
        and post_launch.get("external_handle_terminal") is True
        and (
            int(post_launch.get("job_pending_trial_count") or 0) > 0
            or int(post_launch.get("job_running_trial_count") or 0) > 0
        )
    )


def _terminal_bench_active_job_resume_contract(
    *,
    process_state: str,
    job_stale_active_without_trial_result: bool,
    running_trial_count: int,
    pending_trial_count: int,
    trial_result_count: int,
    result_present: bool,
    job_finished: bool,
) -> dict[str, Any]:
    """Describe whether a compact active/no-result job should be resumed."""

    resume_recommended = bool(
        process_state == "ended"
        and result_present
        and not job_finished
        and trial_result_count <= 0
        and (running_trial_count > 0 or pending_trial_count > 0)
        and not job_stale_active_without_trial_result
    )
    if resume_recommended:
        next_action = (
            "run_no_upload_harbor_job_resume_before_terminal_failure_marker"
        )
    elif job_stale_active_without_trial_result:
        next_action = "emit_stale_active_compact_failure_marker"
    else:
        next_action = "continue_compact_polling"
    return {
        "schema_version": "terminal_bench_active_job_resume_contract_v0",
        "resume_recommended": resume_recommended,
        "next_action": next_action,
        "requires_upload": False,
        "raw_logs_required": False,
        "raw_task_text_required": False,
        "trajectory_required": False,
    }


def resume_terminal_bench_materialized_job(
    *,
    jobs_dir: str | Path,
    run_root: str | Path,
    job_name: str,
    wait_seconds: int = 20,
    execute: bool = False,
    env: dict[str, str] | None = None,
    command_override: list[str] | None = None,
) -> dict[str, Any]:
    """Resume a materialized Harbor job and emit compact process evidence only."""

    jobs_dir_path = Path(jobs_dir).expanduser()
    run_root_path = Path(run_root).expanduser()
    public_job_name = Path(job_name).name
    job_path = jobs_dir_path / public_job_name
    parsed_wait_seconds = max(0, int(wait_seconds))
    argv = (
        list(command_override)
        if command_override is not None
        else build_terminal_bench_harbor_resume_command(job_path=job_path)
    )
    if "--upload" in argv:
        raise ValueError("Terminal-Bench Harbor resume command must not upload")

    output_log = run_root_path / "terminal_bench_resume_stdout_stderr.private.log"
    command_file = run_root_path / "terminal_bench_resume_command.private.sh"
    pid_file = run_root_path / "terminal_bench_resume.pid.private"
    payload: dict[str, Any] = {
        "schema_version": "terminal_bench_harbor_resume_observation_v0",
        "ok": True,
        "dry_run": not execute,
        "run_basename": run_root_path.name,
        "job_name": public_job_name,
        "resume_requested": True,
        "process_started": False,
        "process_state": "not_started",
        "detached_process_group": False,
        "pid": None,
        "returncode": None,
        "wait_seconds": parsed_wait_seconds,
        "process_timed_out": False,
        "job_root_present": job_path.is_dir(),
        "job_config_present": (job_path / "config.json").is_file(),
        "command_shape": {
            "argv_count": len(argv),
            "uses_uvx": bool(argv and Path(str(argv[0])).name == "uvx"),
            "uses_harbor_job_resume": (
                "harbor" in argv and "job" in argv and "resume" in argv
            ),
            "job_path_arg_present": "--job-path" in argv or "-p" in argv,
            "upload_flag_present": "--upload" in argv,
            "job_path_recorded": False,
        },
        "boundary": {
            "no_upload": True,
            "submit_eligible": False,
            "resume_invoked": execute,
            "task_solver_may_run": execute,
            "model_api_expected": execute,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "upload_invoked": False,
        },
        "private_outputs": {
            "stdout_stderr_log_private": True,
            "pid_file_private": True,
            "command_file_private": True,
        },
    }
    if not payload["job_root_present"]:
        post_launch = summarize_terminal_bench_post_launch_materialization(
            jobs_dir_path,
            job_name=public_job_name,
            detached_process_state="ended",
            reconcile_stale_active=True,
        )
        payload.update(
            {
                "process_state": "prelaunch_blocked",
                "first_blocker": "resume_job_root_missing",
                "compact_failure_class": "resume_job_root_missing",
                "ready_for_compact_failure_marker": True,
                "post_launch_materialization": post_launch,
            }
        )
        return payload
    if not payload["job_config_present"]:
        post_launch = summarize_terminal_bench_post_launch_materialization(
            jobs_dir_path,
            job_name=public_job_name,
            detached_process_state="ended",
            reconcile_stale_active=True,
        )
        payload.update(
            {
                "process_state": "prelaunch_blocked",
                "first_blocker": "resume_job_config_missing",
                "compact_failure_class": "resume_job_config_missing",
                "ready_for_compact_failure_marker": True,
                "post_launch_materialization": post_launch,
            }
        )
        return payload
    if not execute:
        return payload

    run_root_path.mkdir(parents=True, exist_ok=True)
    command_file.write_text(
        " ".join(shlex.quote(str(part)) for part in argv) + "\n",
        encoding="utf-8",
    )
    launch_env = os.environ.copy()
    if env:
        launch_env.update({str(key): str(value) for key, value in env.items()})
    with output_log.open("ab") as stream:
        process = subprocess.Popen(
            [str(part) for part in argv],
            stdout=stream,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()),
            env=launch_env,
            close_fds=True,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    payload.update(
        {
            "process_started": True,
            "process_state": "running",
            "detached_process_group": True,
            "pid": process.pid,
        }
    )
    try:
        returncode = process.wait(timeout=parsed_wait_seconds)
        payload.update(
            {
                "process_state": "ended",
                "returncode": returncode,
                "process_timed_out": False,
            }
        )
    except subprocess.TimeoutExpired:
        payload["process_timed_out"] = True
        payload["process_state"] = "running"

    post_launch = summarize_terminal_bench_post_launch_materialization(
        jobs_dir_path,
        job_name=public_job_name,
        detached_process_state=str(payload["process_state"]),
        reconcile_stale_active=payload["process_state"] == "ended",
    )
    payload["post_launch_materialization"] = post_launch
    payload["ready_for_launch_state"] = post_launch.get("ready_for_launch_state") is True
    payload["ready_for_compact_result_ingest"] = (
        post_launch.get("ready_for_compact_result_ingest") is True
    )
    payload["ready_for_compact_failure_marker"] = (
        post_launch.get("ready_for_compact_failure_marker") is True
    )
    payload["compact_failure_class"] = post_launch.get("compact_failure_class")
    payload["first_blocker"] = post_launch.get("first_blocker")
    public_path = run_root_path / "terminal_bench_resume.public.json"
    public_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def summarize_terminal_bench_prelaunch_job_root_guard(
    jobs_dir: str | Path,
    *,
    job_name: str | None,
) -> dict[str, Any]:
    """Block launches that would reuse an existing Harbor job root.

    Harbor materialization is keyed by job basename. Reusing a basename can make
    a fresh launcher observe an old active/no-result job as if the new case had
    materialized, so this guard checks only compact job-root facts before the
    subprocess starts.
    """

    public_job_name = Path(str(job_name)).name if job_name else ""
    current_summary = summarize_terminal_bench_post_launch_materialization(
        jobs_dir,
        job_name=public_job_name or None,
        detached_process_state="unknown",
    )
    checked = current_summary.get("checked") is True
    existing_job_root_present = current_summary.get("job_root_present") is True
    if not checked or not existing_job_root_present:
        return {
            "schema_version": "terminal_bench_prelaunch_job_root_guard_v0",
            "checked": checked,
            "allowed": True,
            "job_name": public_job_name,
            "existing_job_root_present": existing_job_root_present,
            "first_blocker": current_summary.get("first_blocker") or "",
            "compact_failure_class": "",
            "existing_compact_failure_class": "",
            "next_allowed_action": "",
            "post_launch_materialization": current_summary,
            "read_boundary": {
                "raw_paths_recorded": False,
                "raw_logs_read": False,
                "task_text_read": False,
                "trajectory_read": False,
                "docker_invoked": False,
                "model_api_invoked": False,
                "upload_invoked": False,
            },
        }

    reconciled_summary = summarize_terminal_bench_post_launch_materialization(
        jobs_dir,
        job_name=public_job_name or None,
        detached_process_state="ended",
        reconcile_stale_active=True,
    )
    existing_failure_class = str(
        reconciled_summary.get("compact_failure_class") or ""
    )
    existing_result_ready = (
        reconciled_summary.get("ready_for_compact_result_ingest") is True
    )
    if existing_failure_class:
        first_blocker = f"prelaunch_existing_{existing_failure_class}"
        next_allowed_action = str(
            (
                reconciled_summary.get("compact_failure_marker")
                if isinstance(reconciled_summary.get("compact_failure_marker"), dict)
                else {}
            ).get("next_allowed_action")
            or "repair_existing_job_root_before_rerun"
        )
    elif existing_result_ready:
        first_blocker = "prelaunch_existing_result_requires_ingest"
        next_allowed_action = "ingest_existing_trial_result_before_any_rerun"
    else:
        first_blocker = "prelaunch_existing_job_root_before_launch"
        next_allowed_action = "choose_unique_job_name_or_clear_existing_job_root_after_ingest"

    return {
        "schema_version": "terminal_bench_prelaunch_job_root_guard_v0",
        "checked": True,
        "allowed": False,
        "job_name": public_job_name,
        "existing_job_root_present": True,
        "first_blocker": first_blocker,
        "compact_failure_class": "terminal_bench_prelaunch_existing_job_root_blocked",
        "existing_compact_failure_class": existing_failure_class,
        "existing_ready_for_compact_result_ingest": existing_result_ready,
        "existing_ready_for_compact_failure_marker": (
            reconciled_summary.get("ready_for_compact_failure_marker") is True
        ),
        "existing_trial_result_present_count": _compact_positive_int(
            reconciled_summary.get("trial_result_present_count")
        ),
        "existing_job_active_without_trial_result": (
            reconciled_summary.get("job_active_without_trial_result") is True
        ),
        "existing_job_stale_active_without_trial_result": (
            reconciled_summary.get("job_stale_active_without_trial_result") is True
        ),
        "next_allowed_action": next_allowed_action,
        "post_launch_materialization": reconciled_summary,
        "read_boundary": {
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }


def launch_terminal_bench_case_run(
    *,
    jobs_dir: str | Path,
    run_root: str | Path,
    dataset: str = TERMINAL_BENCH_DEFAULT_DATASET,
    task_id: str = TERMINAL_BENCH_DEFAULT_TASK,
    model: str = TERMINAL_BENCH_DEFAULT_MODEL,
    mode: str = "codex-goal-mode",
    job_name: str | None = None,
    wait_seconds: int = 20,
    materialization_wait_seconds: int = 0,
    execute: bool = False,
    timeout_multiplier: float | None = None,
    agent_timeout_multiplier: float | None = None,
    verifier_timeout_multiplier: float | None = None,
    agent_setup_timeout_multiplier: float | None = None,
    environment_build_timeout_multiplier: float | None = None,
    codex_install_strategy: str = (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ),
    codex_preflight_timeout_sec: int | None = None,
    worker_codex_materialization_strategy: str | None = None,
    setup_timeout_repair_profile: bool = False,
    resume_after_materialization: bool = False,
    command_override: list[str] | None = None,
    resume_command_override: list[str] | None = None,
) -> dict[str, Any]:
    """Launch one no-upload Terminal-Bench case run with compact reporting."""

    if mode not in (
        "codex-goal-mode",
        "hardened-codex",
        "codex-goal-harness",
        "goal-harness-managed-codex",
    ):
        raise ValueError(
            "case run launcher supports codex-goal-mode, hardened-codex, "
            "codex-goal-harness, or goal-harness-managed-codex"
        )
    run_root_path = Path(run_root).expanduser()
    jobs_dir_path = Path(jobs_dir).expanduser()
    run_basename = run_root_path.name
    task_label = str(task_id or "all").replace("-", "_")
    public_job_name = (
        Path(job_name).name
        if job_name
        else f"terminal_bench_{task_label}_{mode.replace('-', '_')}_case_run"
    )
    launch = build_terminal_bench_private_runner_launch(
        mode=mode,
        dataset=dataset,
        task_id=task_id,
        model=model,
        jobs_dir=str(jobs_dir_path),
        job_name=public_job_name,
        timeout_multiplier=timeout_multiplier,
        agent_timeout_multiplier=agent_timeout_multiplier,
        verifier_timeout_multiplier=verifier_timeout_multiplier,
        agent_setup_timeout_multiplier=agent_setup_timeout_multiplier,
        environment_build_timeout_multiplier=environment_build_timeout_multiplier,
        codex_install_strategy=codex_install_strategy,
        codex_preflight_timeout_sec=codex_preflight_timeout_sec,
        worker_codex_materialization_strategy=worker_codex_materialization_strategy,
        setup_timeout_repair_profile=setup_timeout_repair_profile,
    )
    argv = launch["argv"] if isinstance(launch.get("argv"), list) else []
    if command_override is not None:
        argv = list(command_override)
    if "--upload" in argv:
        raise ValueError("Terminal-Bench case run command must not upload")
    if "goal_harness_worker_materialization_probe_only=true" in argv:
        raise ValueError("Terminal-Bench case run must not be probe-only")
    summary = summarize_terminal_bench_private_runner_launch(launch)
    if summary.get("no_upload_boundary") is not True or summary.get("submit_eligible"):
        raise ValueError("Terminal-Bench case run requires no-upload/no-submit boundary")
    if summary.get("worker_materialization_probe_only") is True:
        raise ValueError("Terminal-Bench case run summary unexpectedly probe-only")

    parsed_wait_seconds = max(0, int(wait_seconds))
    parsed_materialization_wait_seconds = max(0, int(materialization_wait_seconds))
    output_log = run_root_path / "terminal_bench_run_stdout_stderr.private.log"
    command_file = run_root_path / "terminal_bench_run_command.private.sh"
    pid_file = run_root_path / "terminal_bench_run.pid.private"
    payload: dict[str, Any] = {
        "schema_version": TERMINAL_BENCH_CASE_RUN_LAUNCH_SCHEMA,
        "ok": True,
        "dry_run": not execute,
        "run_basename": run_basename,
        "job_name": public_job_name,
        "process_started": False,
        "process_state": "not_started",
        "detached_process_group": False,
        "pid": None,
        "returncode": None,
        "wait_seconds": parsed_wait_seconds,
        "process_timed_out": False,
        "materialization_wait_seconds": parsed_materialization_wait_seconds,
        "materialization_wait_timed_out": False,
        "resume_after_materialization": bool(resume_after_materialization),
        "resume_after_materialization_attempted": False,
        "launch_summary": summary,
        "command_ref": (
            argv[2]
            if len(argv) > 2 and argv[:2] == ["uvx", "--from"]
            else "private_runner_launch"
        ),
        "command_shape": {
            "argv_count": len(argv),
            "uses_uvx": bool(argv and Path(str(argv[0])).name == "uvx"),
            "uses_harbor_run": "harbor" in argv and "run" in argv,
            "resume_after_materialization": bool(resume_after_materialization),
            "agent_import_path_present": "--agent-import-path" in argv,
            "worker_materialization_probe_only": False,
            "upload_flag_present": "--upload" in argv,
            "jobs_dir_placeholder_present": "<private-jobs-dir>" in argv,
        },
        "boundary": {
            "no_upload": True,
            "submit_eligible": False,
            "worker_materialization_probe_only": False,
            "task_solver_invoked": execute,
            "model_api_expected": execute,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "resume_invoked": False,
            "upload_invoked": False,
        },
        "private_outputs": {
            "stdout_stderr_log_private": True,
            "pid_file_private": True,
            "command_file_private": True,
        },
    }
    prelaunch_ready = summary.get("ready") is True
    prelaunch_blocker = str(summary.get("first_blocker") or "")
    payload["execution_ready"] = prelaunch_ready
    prelaunch_job_root_guard = summarize_terminal_bench_prelaunch_job_root_guard(
        jobs_dir_path,
        job_name=public_job_name,
    )
    payload["prelaunch_job_root_guard"] = prelaunch_job_root_guard
    if not prelaunch_ready:
        payload.update(
            {
                "process_state": "prelaunch_blocked",
                "first_blocker": prelaunch_blocker
                or "terminal_bench_runner_launch_not_ready",
                "compact_failure_class": (
                    "terminal_bench_prelaunch_readiness_blocked"
                ),
                "ready_for_launch_state": False,
                "ready_for_compact_result_ingest": False,
                "ready_for_compact_failure_marker": True,
                "launch_preflight_blocker": prelaunch_blocker,
                "launch_preflight_blocked": True,
                "compact_failure_marker": _terminal_bench_compact_failure_marker(
                    failure_class="terminal_bench_prelaunch_readiness_blocked",
                    evidence_kind="compact_launch_readiness_summary",
                    external_handle_state="unknown",
                    launch_state_countable=False,
                    job_result_present=False,
                    trial_result_present_count=0,
                ),
            }
        )
        payload["boundary"].update(
            {
                "task_solver_invoked": False,
                "model_api_expected": False,
            }
        )
    if execute and not prelaunch_ready:
        run_root_path.mkdir(parents=True, exist_ok=True)
        public_path = run_root_path / "terminal_bench_run_launch.public.json"
        public_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_root_path / "post_launch_summary.public.json").write_text(
            json.dumps(
                {
                    "schema_version": TERMINAL_BENCH_POST_LAUNCH_MATERIALIZATION_SCHEMA,
                    "checked": False,
                    "ready_for_launch_state": False,
                    "ready_for_compact_result_ingest": False,
                    "ready_for_compact_failure_marker": True,
                    "first_blocker": payload["first_blocker"],
                    "job_name": public_job_name,
                    "jobs_dir_present": False,
                    "job_root_present": False,
                    "job_lock_present": False,
                    "job_result_present": False,
                    "trial_result_present_count": 0,
                    "raw_paths_recorded": False,
                    "raw_logs_read": False,
                    "raw_task_text_read": False,
                    "trajectory_read": False,
                    "compact_failure_class": payload["compact_failure_class"],
                    "compact_failure_marker": payload["compact_failure_marker"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return payload
    if execute and prelaunch_job_root_guard.get("allowed") is not True:
        post_launch = (
            prelaunch_job_root_guard.get("post_launch_materialization")
            if isinstance(
                prelaunch_job_root_guard.get("post_launch_materialization"), dict
            )
            else {}
        )
        marker_trial_count = _compact_positive_int(
            post_launch.get("trial_result_present_count")
        )
        payload.update(
            {
                "process_state": "prelaunch_blocked",
                "first_blocker": prelaunch_job_root_guard.get("first_blocker")
                or "prelaunch_existing_job_root_before_launch",
                "compact_failure_class": prelaunch_job_root_guard.get(
                    "compact_failure_class"
                )
                or "terminal_bench_prelaunch_existing_job_root_blocked",
                "ready_for_launch_state": False,
                "ready_for_compact_result_ingest": False,
                "ready_for_compact_failure_marker": True,
                "launch_preflight_blocker": prelaunch_job_root_guard.get(
                    "first_blocker"
                )
                or "prelaunch_existing_job_root_before_launch",
                "launch_preflight_blocked": True,
                "prelaunch_job_root_guard_triggered": True,
                "compact_failure_marker": _terminal_bench_compact_failure_marker(
                    failure_class="terminal_bench_prelaunch_existing_job_root_blocked",
                    evidence_kind="compact_prelaunch_existing_job_root_guard",
                    external_handle_state=str(
                        post_launch.get("external_handle_state") or "unknown"
                    ),
                    launch_state_countable=False,
                    job_result_present=post_launch.get("job_result_present") is True,
                    trial_result_present_count=marker_trial_count,
                    job_result_finished=(
                        post_launch.get("job_result_finished")
                        if isinstance(post_launch.get("job_result_finished"), bool)
                        else None
                    ),
                    job_running_trial_count=_compact_positive_int(
                        post_launch.get("job_running_trial_count")
                    ),
                    job_pending_trial_count=_compact_positive_int(
                        post_launch.get("job_pending_trial_count")
                    ),
                    job_result_updated_at_present=(
                        post_launch.get("job_result_updated_at_present")
                        if isinstance(
                            post_launch.get("job_result_updated_at_present"), bool
                        )
                        else None
                    ),
                    job_updated_age_seconds=(
                        post_launch.get("job_updated_age_seconds")
                        if isinstance(
                            post_launch.get("job_updated_age_seconds"),
                            (int, float),
                        )
                        and not isinstance(
                            post_launch.get("job_updated_age_seconds"), bool
                        )
                        else None
                    ),
                    job_active_stale_seconds_threshold=(
                        int(post_launch.get("job_active_stale_seconds_threshold"))
                        if isinstance(
                            post_launch.get("job_active_stale_seconds_threshold"),
                            int,
                        )
                        and not isinstance(
                            post_launch.get("job_active_stale_seconds_threshold"),
                            bool,
                        )
                        else None
                    ),
                ),
            }
        )
        payload["boundary"].update(
            {
                "task_solver_invoked": False,
                "model_api_expected": False,
            }
        )
        run_root_path.mkdir(parents=True, exist_ok=True)
        public_path = run_root_path / "terminal_bench_run_launch.public.json"
        public_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (run_root_path / "post_launch_summary.public.json").write_text(
            json.dumps(post_launch, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return payload
    if not execute:
        return payload

    run_root_path.mkdir(parents=True, exist_ok=True)
    jobs_dir_path.mkdir(parents=True, exist_ok=True)
    command_file.write_text(
        " ".join(shlex.quote(str(part)) for part in argv) + "\n",
        encoding="utf-8",
    )
    launch_env = os.environ.copy()
    if isinstance(launch.get("env"), dict):
        launch_env.update(
            {
                str(key): str(value)
                for key, value in launch["env"].items()
                if isinstance(key, str)
            }
        )
    with output_log.open("ab") as stream:
        process = subprocess.Popen(
            [str(part) for part in argv],
            stdout=stream,
            stderr=subprocess.STDOUT,
            cwd=str(Path.cwd()),
            env=launch_env,
            close_fds=True,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    payload.update(
        {
            "process_started": True,
            "process_state": "running",
            "detached_process_group": True,
            "pid": process.pid,
        }
    )
    launch_materialization_observation: dict[str, Any] | None = None
    if parsed_materialization_wait_seconds > 0:
        launch_materialization_observation = (
            wait_for_terminal_bench_launch_materialization(
                process=process,
                jobs_dir=jobs_dir_path,
                job_name=public_job_name,
                wait_seconds=parsed_materialization_wait_seconds,
            )
        )
        payload.update(
            {
                "process_state": launch_materialization_observation.get(
                    "process_state",
                    "unknown",
                ),
                "returncode": launch_materialization_observation.get("returncode"),
                "materialization_wait_timed_out": (
                    launch_materialization_observation.get("materialized") is not True
                    and launch_materialization_observation.get(
                        "terminal_compact_failure"
                    )
                    is not True
                    and launch_materialization_observation.get("process_state")
                    == "running"
                ),
            }
        )
        post_launch = (
            launch_materialization_observation.get("post_launch_materialization")
            if isinstance(
                launch_materialization_observation.get(
                    "post_launch_materialization"
                ),
                dict,
            )
            else {}
        )
        payload["launch_materialization_observation"] = (
            launch_materialization_observation
        )
        if (
            launch_materialization_observation.get("materialized") is True
            and launch_materialization_observation.get("terminal_compact_failure")
            is not True
            and parsed_wait_seconds > 0
        ):
            post_materialization_closeout = (
                observe_terminal_bench_post_materialization_closeout(
                    process=process,
                    jobs_dir=jobs_dir_path,
                    job_name=public_job_name,
                    wait_seconds=parsed_wait_seconds,
                )
            )
            payload["post_materialization_closeout_observation"] = (
                post_materialization_closeout
            )
            payload.update(
                {
                    "process_state": post_materialization_closeout.get(
                        "process_state", payload["process_state"]
                    ),
                    "returncode": post_materialization_closeout.get(
                        "returncode", payload.get("returncode")
                    ),
                }
            )
            post_launch = (
                post_materialization_closeout.get("post_launch_materialization")
                if isinstance(
                    post_materialization_closeout.get(
                        "post_launch_materialization"
                    ),
                    dict,
                )
                else post_launch
            )
            if (
                resume_after_materialization
                and _terminal_bench_resume_recommended(post_launch)
            ):
                resume_observation = resume_terminal_bench_materialized_job(
                    jobs_dir=jobs_dir_path,
                    run_root=run_root_path,
                    job_name=public_job_name,
                    wait_seconds=parsed_wait_seconds,
                    execute=True,
                    env=launch.get("env") if isinstance(launch.get("env"), dict) else None,
                    command_override=resume_command_override,
                )
                payload["post_materialization_resume_observation"] = (
                    resume_observation
                )
                payload["resume_after_materialization_attempted"] = True
                payload["boundary"]["resume_invoked"] = True
                payload.update(
                    {
                        "process_state": resume_observation.get(
                            "process_state", payload["process_state"]
                        ),
                        "returncode": resume_observation.get(
                            "returncode", payload.get("returncode")
                        ),
                    }
                )
                if isinstance(
                    resume_observation.get("post_launch_materialization"), dict
                ):
                    post_launch = resume_observation[
                        "post_launch_materialization"
                    ]
    else:
        try:
            returncode = process.wait(timeout=parsed_wait_seconds)
            payload.update(
                {
                    "process_state": "ended",
                    "returncode": returncode,
                    "process_timed_out": False,
                }
            )
        except subprocess.TimeoutExpired:
            payload["process_timed_out"] = True
            payload["process_state"] = "running"

        post_launch = summarize_terminal_bench_post_launch_materialization(
            jobs_dir_path,
            job_name=public_job_name,
            detached_process_state=payload["process_state"],
        )
    payload["post_launch_materialization"] = post_launch
    payload["ready_for_launch_state"] = post_launch.get("ready_for_launch_state") is True
    payload["ready_for_compact_result_ingest"] = (
        post_launch.get("ready_for_compact_result_ingest") is True
    )
    payload["ready_for_compact_failure_marker"] = (
        post_launch.get("ready_for_compact_failure_marker") is True
    )
    payload["compact_failure_class"] = post_launch.get("compact_failure_class")
    payload["first_blocker"] = post_launch.get("first_blocker")
    if payload["compact_failure_class"] == "detached_worker_ended_without_job_root":
        payload["exit_code_attribution"] = (
            "terminal_bench_run_process_ended_before_job_root"
        )
    elif payload["compact_failure_class"] == "detached_worker_ended_without_jobs_dir":
        payload["exit_code_attribution"] = (
            "terminal_bench_run_process_ended_before_jobs_dir"
        )
    elif payload["process_state"] == "ended" and payload["returncode"] not in (0, None):
        payload["exit_code_attribution"] = "terminal_bench_run_process_nonzero_exit"
    elif payload["process_state"] == "ended":
        payload["exit_code_attribution"] = "terminal_bench_run_process_zero_exit"
    else:
        payload["exit_code_attribution"] = "terminal_bench_run_process_still_running"
    if payload.get("resume_after_materialization_attempted"):
        if payload.get("compact_failure_class"):
            payload["exit_code_attribution"] = (
                "terminal_bench_resume_terminal_compact_failure"
            )
        elif payload["process_state"] == "ended" and payload["returncode"] not in (
            0,
            None,
        ):
            payload["exit_code_attribution"] = (
                "terminal_bench_resume_process_nonzero_exit"
            )
        elif payload["process_state"] == "ended":
            payload["exit_code_attribution"] = "terminal_bench_resume_process_zero_exit"
        else:
            payload["exit_code_attribution"] = (
                "terminal_bench_resume_process_still_running"
            )

    public_path = run_root_path / "terminal_bench_run_launch.public.json"
    public_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_root_path / "post_launch_summary.public.json").write_text(
        json.dumps(post_launch, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def poll_terminal_bench_worker_materialization_probe(
    *,
    jobs_dir: str | Path,
    run_root: str | Path,
    job_name: str | None = None,
) -> dict[str, Any]:
    """Poll a no-upload worker materialization probe using compact signals only."""

    run_root_path = Path(run_root).expanduser()
    jobs_dir_path = Path(jobs_dir).expanduser()
    public_job_name = Path(job_name).name if job_name else ""
    pid_state = _detached_process_state_from_pid_file(
        run_root_path / "worker_materialization_probe.pid.private"
    )
    process_state = str(pid_state.get("process_state") or "unknown")
    post_launch = summarize_terminal_bench_post_launch_materialization(
        jobs_dir_path,
        job_name=public_job_name or None,
        detached_process_state=process_state,
    )
    payload: dict[str, Any] = {
        "schema_version": "terminal_bench_worker_materialization_probe_poll_v0",
        "ok": True,
        "run_basename": run_root_path.name,
        "job_name": public_job_name,
        "pid_state": pid_state,
        "process_state": process_state,
        "post_launch_materialization": post_launch,
        "ready_for_launch_state": post_launch.get("ready_for_launch_state") is True,
        "ready_for_compact_result_ingest": (
            post_launch.get("ready_for_compact_result_ingest") is True
        ),
        "ready_for_compact_failure_marker": (
            post_launch.get("ready_for_compact_failure_marker") is True
        ),
        "compact_failure_class": post_launch.get("compact_failure_class"),
        "first_blocker": post_launch.get("first_blocker")
        or pid_state.get("first_blocker"),
        "boundary": {
            "no_upload": True,
            "submit_eligible": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "command_line_read": False,
            "raw_external_handle_payload_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
        "public_poll_written": False,
    }
    if run_root_path.is_dir():
        payload["public_poll_written"] = True
        (run_root_path / "worker_materialization_probe_poll.public.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return payload


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


def build_terminal_bench_result_finalization_gate(
    post_launch_materialization: dict[str, Any] | None,
    *,
    max_repaired_baseline_reruns: int = 1,
) -> dict[str, Any]:
    """Reduce compact Terminal-Bench post-launch evidence into a rerun gate.

    The gate is intentionally downstream of post-launch summarization and
    ledger ingestion: it consumes only compact phase fields, never raw logs,
    task text, trajectories, local paths, Docker state, or model APIs.
    """

    payload = (
        post_launch_materialization
        if isinstance(post_launch_materialization, dict)
        else {}
    )
    schema_ok = (
        payload.get("schema_version")
        == TERMINAL_BENCH_POST_LAUNCH_MATERIALIZATION_SCHEMA
    )
    compact_failure_marker = (
        payload.get("compact_failure_marker")
        if isinstance(payload.get("compact_failure_marker"), dict)
        else {}
    )
    failure_class = str(
        payload.get("compact_failure_class")
        or compact_failure_marker.get("failure_class")
        or ""
    )
    ready_for_result_ingest = (
        payload.get("ready_for_compact_result_ingest") is True
    )
    ready_for_failure_marker = (
        payload.get("ready_for_compact_failure_marker") is True
    )
    launch_state_countable = (
        payload.get("ready_for_launch_state") is True
        or compact_failure_marker.get("launch_state_countable") is True
    )
    trial_result_present_count = _compact_positive_int(
        payload.get("trial_result_present_count")
        if payload.get("trial_result_present_count") is not None
        else compact_failure_marker.get("trial_result_present_count")
    )
    no_trial_result = trial_result_present_count <= 0
    external_handle_terminal = (
        payload.get("external_handle_terminal") is True
        or payload.get("external_handle_state") == "ended"
        or compact_failure_marker.get("external_handle_state") == "ended"
    )
    job_stale_active = (
        payload.get("job_stale_active_without_trial_result") is True
        or failure_class == "stale_active_job_without_trial_result"
    )
    job_active_without_trial_result = (
        payload.get("job_active_without_trial_result") is True
        or job_stale_active
    )
    terminal_closeout = compact_failure_marker.get("terminal_closeout") is True
    marker_next_allowed_action = str(
        compact_failure_marker.get("next_allowed_action") or ""
    )
    ledger_attempt_kind = str(
        compact_failure_marker.get("ledger_attempt_kind") or ""
    )
    case_attempt_countable = (
        compact_failure_marker.get("case_attempt_countable") is True
    )
    benchmark_budget_countable = (
        compact_failure_marker.get("benchmark_budget_countable") is True
    )
    raw_boundary_flags = {
        "raw_paths_recorded": payload.get("raw_paths_recorded")
        or compact_failure_marker.get("raw_paths_recorded"),
        "raw_logs_read": payload.get("raw_logs_read")
        or compact_failure_marker.get("raw_logs_read"),
        "raw_task_text_read": payload.get("raw_task_text_read")
        or payload.get("task_text_read")
        or compact_failure_marker.get("raw_task_text_read"),
        "trajectory_read": payload.get("trajectory_read")
        or payload.get("raw_trajectory_read")
        or compact_failure_marker.get("trajectory_read"),
        "raw_external_handle_payload_recorded": payload.get(
            "raw_external_handle_payload_recorded"
        )
        or compact_failure_marker.get("raw_external_handle_payload_recorded"),
    }
    boundary_public_safe = all(value is not True for value in raw_boundary_flags.values())
    max_repaired_baseline_reruns = max(0, int(max_repaired_baseline_reruns))

    finalization_failure_classes = {
        "stale_active_job_without_trial_result",
        "detached_worker_ended_active_without_trial_result",
        "detached_worker_ended_without_trial_result",
    }
    launch_materialization_failure_classes = {
        "detached_worker_ended_without_jobs_dir",
        "detached_worker_ended_without_job_root",
    }
    finalization_repair_required = (
        schema_ok
        and boundary_public_safe
        and ready_for_failure_marker
        and failure_class in finalization_failure_classes
    )
    launch_materialization_repair_required = (
        schema_ok
        and boundary_public_safe
        and ready_for_failure_marker
        and failure_class in launch_materialization_failure_classes
    )
    # A compact terminal closeout marker is evidence that the runner/result
    # finalization path needs repair, not evidence that another rerun is safe.
    # A future repaired-rerun authorization must come from a separate validated
    # repair artifact instead of this failure marker alone.
    repaired_baseline_rerun_allowed = False
    if failure_class == "stale_active_job_without_trial_result":
        finalization_root_cause = (
            "harbor_job_left_active_after_detached_worker_ended_without_trial_result"
        )
    elif failure_class == "detached_worker_ended_active_without_trial_result":
        finalization_root_cause = (
            "detached_worker_ended_while_harbor_job_remained_active_without_trial_result"
        )
    elif failure_class == "detached_worker_ended_without_trial_result":
        finalization_root_cause = (
            "detached_worker_ended_before_trial_result_materialized"
        )
    else:
        finalization_root_cause = "result_finalization_evidence_incomplete"

    if not schema_ok:
        first_blocker = "post_launch_materialization_required"
        decision = "blocked_missing_compact_post_launch_materialization"
        next_allowed_action = "produce_compact_post_launch_materialization"
        root_cause = "unknown_without_compact_post_launch_materialization"
    elif not boundary_public_safe:
        first_blocker = "post_launch_boundary_not_public_safe"
        decision = "blocked_by_raw_boundary"
        next_allowed_action = "rebuild_post_launch_materialization_from_compact_fields_only"
        root_cause = "raw_boundary_violation_in_post_launch_evidence"
    elif ready_for_result_ingest:
        first_blocker = "compact_result_ingest_required"
        decision = "ingest_compact_result_before_rerun"
        next_allowed_action = "ingest_existing_trial_result_before_any_rerun"
        root_cause = "trial_result_materialized_not_yet_ingested"
    elif finalization_repair_required:
        first_blocker = "result_finalization_repair_required_before_rerun"
        decision = "repair_result_finalization_before_rerun"
        next_allowed_action = (
            marker_next_allowed_action
            or "repair_result_finalization_closeout_contract_before_rerun"
        )
        root_cause = finalization_root_cause
    elif launch_materialization_repair_required:
        first_blocker = "launch_materialization_repair_required_before_rerun"
        decision = "repair_launch_materialization_before_rerun"
        next_allowed_action = (
            marker_next_allowed_action
            or "repair_job_materialization_before_baseline_rerun"
        )
        root_cause = "detached_worker_ended_before_countable_job_materialized"
    elif (
        payload.get("resume_recommended") is True
        or payload.get("first_blocker")
        == "resume_materialized_active_job_without_trial_result"
    ):
        first_blocker = "resume_materialized_active_job_without_trial_result"
        decision = "resume_materialized_job_before_failure_marker"
        next_allowed_action = (
            "run_no_upload_harbor_job_resume_before_terminal_failure_marker"
        )
        root_cause = (
            "harbor_job_active_without_trial_result_after_driver_exit"
        )
    elif payload.get("first_blocker") == "ready_for_compact_polling":
        first_blocker = "continue_compact_polling"
        decision = "polling_not_terminal"
        next_allowed_action = "continue_compact_polling_without_spend_claim"
        root_cause = "worker_or_harbor_state_not_terminal_from_compact_fields"
    else:
        first_blocker = "compact_failure_marker_required"
        decision = "compact_failure_marker_required_before_rerun"
        next_allowed_action = "emit_or_ingest_compact_failure_marker_before_rerun"
        root_cause = "post_launch_failure_not_yet_classified"

    return {
        "schema_version": TERMINAL_BENCH_RESULT_FINALIZATION_GATE_SCHEMA,
        "ok": True,
        "benchmark_id": "terminal-bench@2.0",
        "post_launch_schema_ok": schema_ok,
        "failure_class": failure_class,
        "root_cause": root_cause,
        "decision": decision,
        "first_blocker": first_blocker,
        "repair_class": "runner_result_finalization"
        if finalization_repair_required
        else "runner_launch_materialization"
        if launch_materialization_repair_required
        else "none",
        "result_finalization_repair_required": finalization_repair_required,
        "launch_materialization_repair_required": (
            launch_materialization_repair_required
        ),
        "repaired_baseline_rerun_allowed": repaired_baseline_rerun_allowed,
        "max_repaired_baseline_reruns": max_repaired_baseline_reruns,
        "next_allowed_action": next_allowed_action,
        "gate_conditions": {
            "boundary_public_safe": boundary_public_safe,
            "ready_for_compact_result_ingest": ready_for_result_ingest,
            "ready_for_compact_failure_marker": ready_for_failure_marker,
            "launch_state_countable": launch_state_countable,
            "external_handle_terminal": external_handle_terminal,
            "job_active_without_trial_result": job_active_without_trial_result,
            "job_stale_active_without_trial_result": job_stale_active,
            "resume_recommended": payload.get("resume_recommended") is True,
            "no_trial_result": no_trial_result,
            "terminal_closeout": terminal_closeout,
            "case_attempt_countable": case_attempt_countable,
            "benchmark_budget_countable": benchmark_budget_countable,
        },
        "closeout_contract": {
            "terminal_closeout": terminal_closeout,
            "ledger_attempt_kind": ledger_attempt_kind,
            "case_attempt_countable": case_attempt_countable,
            "benchmark_budget_countable": benchmark_budget_countable,
            "next_allowed_action": marker_next_allowed_action,
        },
        "rerun_constraints": {
            "baseline_only": True,
            "max_reruns": max_repaired_baseline_reruns,
            "require_no_upload": True,
            "require_no_leaderboard_claim": True,
            "require_no_treatment_or_uplift_claim": True,
            "require_compact_post_launch_observer": True,
            "require_compact_result_or_failure_marker_ingest": True,
        },
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "raw_external_handle_payload_recorded": False,
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
TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_TIMEOUT_MULTIPLIER = 8.0
TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_SETUP_TIMEOUT_MULTIPLIER = 8.0
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


def _agents_last_exam_codex_cli_probe(
    codex_binary: str | None,
    *,
    binary_available: bool | None = None,
    version_text: str | None = None,
) -> dict[str, Any]:
    """Probe host Codex CLI readiness without recording paths or argv."""

    runner_probe = _agents_last_exam_runner_binary_probe(codex_binary)
    unsafe_binary_blockers = {
        "runner_binary_must_be_name_not_path",
        "runner_binary_not_public_safe",
    }
    if (
        binary_available is not None
        and runner_probe.get("declared") is True
        and runner_probe.get("first_blocker") not in unsafe_binary_blockers
    ):
        runner_probe = {
            **runner_probe,
            "available": bool(binary_available),
            "first_blocker": None
            if binary_available
            else (runner_probe.get("first_blocker") or "codex_binary_not_available"),
        }

    version_label = _agents_last_exam_public_id(version_text, limit=120)
    version_probe_available = bool(version_label)
    if (
        version_text is None
        and runner_probe.get("available") is True
        and isinstance(codex_binary, str)
        and codex_binary
        and "/" not in codex_binary
        and "\\" not in codex_binary
    ):
        try:
            result = subprocess.run(
                [codex_binary, "--version"],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
            )
        except Exception:
            result = None
        if result is not None and result.returncode == 0:
            version_label = _agents_last_exam_public_id(
                result.stdout.strip() or result.stderr.strip(),
                limit=120,
            )
            version_probe_available = bool(version_label)

    first_blocker = _agents_last_exam_public_id(
        runner_probe.get("first_blocker"),
        limit=80,
    )
    if runner_probe.get("available") is True and not version_probe_available:
        first_blocker = "codex_version_probe_failed"

    return {
        "binary": runner_probe.get("binary"),
        "binary_declared": runner_probe.get("declared") is True,
        "binary_available": runner_probe.get("available") is True,
        "version": version_label,
        "version_probe_available": version_probe_available,
        "binary_path_recorded": False,
        "command_argv_recorded": False,
        "first_blocker": first_blocker,
    }

def _agents_last_exam_cua_mcp_assets_probe(
    assets_root: str | None,
) -> dict[str, Any]:
    """Check local CUA MCP server assets without recording host paths."""

    if not assets_root:
        return {
            "declared": False,
            "available": False,
            "package_json_present": False,
            "server_entry_present": False,
            "package_lock_present": False,
            "path_recorded": False,
            "first_blocker": "cua_mcp_assets_root_missing",
        }
    try:
        root = Path(assets_root).expanduser()
    except (OSError, RuntimeError):
        root = None
    available = bool(root and root.is_dir())
    package_json_present = bool(root and (root / "package.json").is_file())
    package_lock_present = bool(root and (root / "package-lock.json").is_file())
    server_entry_present = bool(root and (root / "src" / "index.js").is_file())
    if not available:
        first_blocker = "cua_mcp_assets_root_not_available"
    elif not package_json_present:
        first_blocker = "cua_mcp_package_json_missing"
    elif not server_entry_present:
        first_blocker = "cua_mcp_server_entry_missing"
    else:
        first_blocker = None
    return {
        "declared": True,
        "available": available,
        "package_json_present": package_json_present,
        "server_entry_present": server_entry_present,
        "package_lock_present": package_lock_present,
        "path_recorded": False,
        "first_blocker": first_blocker,
    }

def build_agents_last_exam_host_codex_cli_route(
    *,
    codex_binary: str | None = "codex",
    codex_binary_available: bool | None = None,
    codex_version_text: str | None = None,
    host_auth_cache_present: bool | None = None,
    host_config_present: bool | None = None,
    require_host_config: bool = False,
    cua_mcp_assets_root: str | None = None,
    ale_sandbox_cua_smoke_ready: bool = False,
    operator_authorized_host_codex_auth: bool = False,
) -> dict[str, Any]:
    """Gate the ALE host-Codex route before any task-level execution.

    The contract intentionally checks only host-side existence/probe facts. It
    must not read, print, copy, or persist Codex auth material or task content.
    """

    codex_probe = _agents_last_exam_codex_cli_probe(
        codex_binary,
        binary_available=codex_binary_available,
        version_text=codex_version_text,
    )
    auth_present = (
        Path.home().joinpath(".codex", "auth.json").is_file()
        if host_auth_cache_present is None
        else bool(host_auth_cache_present)
    )
    config_present = (
        Path.home().joinpath(".codex", "config.toml").is_file()
        if host_config_present is None
        else bool(host_config_present)
    )
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)

    blockers: list[str] = []
    if operator_authorized_host_codex_auth is not True:
        blockers.append("operator_authorization_missing")
    if codex_probe.get("binary_available") is not True:
        blockers.append(
            _agents_last_exam_public_id(codex_probe.get("first_blocker"), limit=80)
            or "host_codex_binary_not_available"
        )
    if codex_probe.get("version_probe_available") is not True:
        blockers.append("host_codex_version_probe_missing")
    if auth_present is not True:
        blockers.append("host_codex_auth_cache_missing")
    if require_host_config and config_present is not True:
        blockers.append("host_codex_config_missing")
    if assets_probe.get("first_blocker"):
        blockers.append(
            _agents_last_exam_public_id(assets_probe.get("first_blocker"), limit=80)
            or "cua_mcp_assets_not_ready"
        )
    if ale_sandbox_cua_smoke_ready is not True:
        blockers.append("ale_sandbox_cua_smoke_not_ready")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_no_task_host_codex_cua_smoke",
        "blockers": blockers,
        "route": {
            "mode": "host_codex_cli_local_executor",
            "uses_host_codex_cli": True,
            "uses_existing_host_codex_auth": True,
            "runs_codex_inside_ale_sandbox": False,
            "drives_ale_sandbox_via_cua_mcp": True,
            "upstream_sandbox_codex_agent_bypassed": True,
            "upstream_provider_key_path_required": False,
            "next_smoke": "no_task_host_codex_cli_cua_mcp_smoke",
        },
        "host_codex_cli": codex_probe,
        "host_auth": {
            "auth_cache_present": auth_present,
            "config_present": config_present,
            "config_required": require_host_config,
            "auth_values_read": False,
            "config_content_read": False,
            "credential_values_recorded": False,
            "auth_material_copied_to_sandbox": False,
            "whole_codex_dir_copied": False,
            "paths_recorded": False,
        },
        "cua_mcp_assets": assets_probe,
        "ale_sandbox": {
            "cua_smoke_ready": ale_sandbox_cua_smoke_ready is True,
            "container_started_by_this_check": False,
            "sandbox_auth_material_present": False,
            "sandbox_auth_values_read": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_no_task_host_codex_cli_cua_smoke"
            if ready
            else "repair_host_codex_cli_route_blocker",
            "minimum_next_evidence": (
                "A no-task host Codex CLI smoke using a project-local temporary "
                "Codex config and the ALE CUA MCP bridge, with no task prompt, "
                "no credential values, no upload, no submit, and compact result "
                "only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "auth_values_read": False,
            "config_content_read": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_codex_exec_surface_probe(
    codex_binary: str | None,
) -> dict[str, Any]:
    codex_probe = _agents_last_exam_codex_cli_probe(codex_binary)
    if codex_probe.get("binary_available") is not True:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": codex_probe.get("first_blocker")
            or "host_codex_binary_not_available",
        }
    if not isinstance(codex_binary, str) or "/" in codex_binary or "\\" in codex_binary:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": "host_codex_binary_not_public_safe",
        }
    try:
        result = subprocess.run(
            [codex_binary, "exec", "--help"],
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": "codex_exec_help_probe_failed",
        }
    ok = result.returncode == 0
    return {
        "available": ok,
        "exit_code": result.returncode,
        "stdout_recorded": False,
        "stderr_recorded": False,
        "command_argv_recorded": False,
        "model_invoked": False,
        "first_blocker": None if ok else "codex_exec_help_nonzero",
    }

def _agents_last_exam_codex_mcp_config_probe(
    codex_binary: str | None,
    *,
    cua_mcp_assets_root: str | None,
    cua_server_url: str,
) -> dict[str, Any]:
    codex_probe = _agents_last_exam_codex_cli_probe(codex_binary)
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)
    if codex_probe.get("binary_available") is not True:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": codex_probe.get("first_blocker")
            or "host_codex_binary_not_available",
        }
    if assets_probe.get("first_blocker"):
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": assets_probe.get("first_blocker")
            or "cua_mcp_assets_not_ready",
        }
    if not isinstance(codex_binary, str) or "/" in codex_binary or "\\" in codex_binary:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": "host_codex_binary_not_public_safe",
        }

    try:
        assets_root = Path(str(cua_mcp_assets_root)).expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix="goal-harness-codex-home-") as tmp:
            codex_home = Path(tmp)
            mcp_entry = assets_root / "src" / "index.js"
            config_text = "\n".join(
                [
                    "[mcp_servers.cua]",
                    'command = "node"',
                    f'args = ["{mcp_entry}"]',
                    f'env = {{ CUA_SERVER_URL = "{cua_server_url}" }}',
                    "",
                ]
            )
            (codex_home / "config.toml").write_text(config_text, encoding="utf-8")
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            result = subprocess.run(
                [codex_binary, "mcp", "list", "--json"],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
                env=env,
            )
    except Exception:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": "codex_mcp_config_probe_failed",
        }

    server_detected = False
    server_enabled = False
    transport_type: str | None = None
    if result.returncode == 0:
        try:
            rows = json.loads(result.stdout)
        except json.JSONDecodeError:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict) or row.get("name") != "cua":
                    continue
                server_detected = True
                server_enabled = row.get("enabled") is True
                transport = row.get("transport")
                if isinstance(transport, dict):
                    transport_type = _agents_last_exam_public_id(
                        transport.get("type"),
                        limit=40,
                    )
                break
    if result.returncode != 0:
        first_blocker = "codex_mcp_list_nonzero"
    elif not server_detected:
        first_blocker = "codex_mcp_cua_server_not_detected"
    elif not server_enabled:
        first_blocker = "codex_mcp_cua_server_not_enabled"
    elif transport_type != "stdio":
        first_blocker = "codex_mcp_cua_transport_not_stdio"
    else:
        first_blocker = None
    return {
        "available": first_blocker is None,
        "server_detected": server_detected,
        "server_enabled": server_enabled,
        "transport": transport_type,
        "raw_output_recorded": False,
        "config_path_recorded": False,
        "mcp_server_path_recorded": False,
        "command_argv_recorded": False,
        "auth_values_read": False,
        "first_blocker": first_blocker,
    }

def _agents_last_exam_fake_cua_server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("content-length") or "0")
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                request = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                request = {}
            command = request.get("command")
            if command == "get_screen_size":
                payload = {"success": True, "size": {"width": 1024, "height": 768}}
            elif command == "screenshot":
                payload = {"success": True, "image_data": "iVBORw0KGgo="}
            elif command == "get_cursor_position":
                payload = {"success": True, "position": {"x": 512, "y": 384}}
            else:
                payload = {"success": True}
            data = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def _agents_last_exam_cua_mcp_test_probe(
    *,
    cua_mcp_assets_root: str | None,
    install_node_deps: bool = False,
) -> dict[str, Any]:
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)
    if assets_probe.get("first_blocker"):
        return {
            "available": False,
            "node_available": shutil.which("node") is not None,
            "npm_install_attempted": False,
            "fake_cua_server_used": False,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": assets_probe.get("first_blocker")
            or "cua_mcp_assets_not_ready",
        }
    if not shutil.which("node"):
        return {
            "available": False,
            "node_available": False,
            "npm_install_attempted": False,
            "fake_cua_server_used": False,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": "node_cli_missing",
        }

    server = None
    try:
        with tempfile.TemporaryDirectory(prefix="goal-harness-cua-mcp-") as tmp:
            work_root = Path(tmp) / "cua_mcp_server"
            shutil.copytree(str(cua_mcp_assets_root), work_root)
            node_modules = work_root / "node_modules"
            npm_install_attempted = False
            if not node_modules.is_dir():
                if not install_node_deps:
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": False,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "cua_mcp_node_modules_missing",
                    }
                if not shutil.which("npm"):
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": False,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "npm_cli_missing",
                    }
                npm_install_attempted = True
                npm_result = subprocess.run(
                    ["npm", "install", "--production", "--silent"],
                    cwd=work_root,
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=120,
                )
                if npm_result.returncode != 0:
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": True,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "cua_mcp_npm_install_failed",
                    }
            server = _agents_last_exam_fake_cua_server()
            port = server.server_address[1]
            env = os.environ.copy()
            env["CUA_SERVER_URL"] = f"http://127.0.0.1:{port}"
            test_result = subprocess.run(
                ["node", "src/index.js", "--test"],
                cwd=work_root,
                check=False,
                text=True,
                capture_output=True,
                timeout=60,
                env=env,
            )
    except Exception:
        return {
            "available": False,
            "node_available": shutil.which("node") is not None,
            "npm_install_attempted": install_node_deps,
            "fake_cua_server_used": server is not None,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": "cua_mcp_test_probe_failed",
        }
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    ok = test_result.returncode == 0
    return {
        "available": ok,
        "node_available": True,
        "npm_install_attempted": npm_install_attempted,
        "fake_cua_server_used": True,
        "raw_output_recorded": False,
        "command_argv_recorded": False,
        "local_paths_recorded": False,
        "first_blocker": None if ok else "cua_mcp_test_nonzero",
    }

def build_agents_last_exam_host_codex_cua_no_task_smoke(
    *,
    route_gate: dict[str, Any],
    codex_exec_probe: dict[str, Any],
    mcp_config_probe: dict[str, Any],
    cua_mcp_test_probe: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if route_gate.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(route_gate.get("first_blocker"), limit=80)
            or "host_codex_route_gate_not_ready"
        )
    for probe_name, probe in (
        ("codex_exec_surface", codex_exec_probe),
        ("codex_mcp_config", mcp_config_probe),
        ("cua_mcp_bridge", cua_mcp_test_probe),
    ):
        if probe.get("available") is not True:
            blockers.append(
                _agents_last_exam_public_id(probe.get("first_blocker"), limit=80)
                or f"{probe_name}_not_ready"
            )
    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_task_level_ale_codex_dry_run_gate",
        "blockers": blockers,
        "route_gate_ready": route_gate.get("ready") is True,
        "route_gate": route_gate,
        "codex_exec_surface": codex_exec_probe,
        "codex_mcp_config": mcp_config_probe,
        "cua_mcp_bridge": cua_mcp_test_probe,
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_operator_authorized_task_level_ale_codex_dry_run"
            if ready
            else "repair_no_task_host_codex_cua_smoke_blocker",
            "minimum_next_evidence": (
                "An operator-authorized task-level ALE dry-run may proceed only "
                "after compact route, Codex exec surface, Codex MCP config, and "
                "CUA MCP bridge probes are ready."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "auth_values_read": False,
            "config_content_read": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
    *,
    codex_binary: str | None = "codex",
    codex_binary_available: bool | None = None,
    codex_version_text: str | None = None,
    host_auth_cache_present: bool | None = None,
    host_config_present: bool | None = None,
    require_host_config: bool = False,
    cua_mcp_assets_root: str | None = None,
    cua_server_url: str = "http://127.0.0.1:8000",
    install_node_deps: bool = False,
    ale_sandbox_cua_smoke_ready: bool = False,
    operator_authorized_host_codex_auth: bool = False,
) -> dict[str, Any]:
    """Build compact no-task host Codex/CUA readiness evidence.

    This is deliberately a pre-task probe: it checks CLI/help, Codex MCP config
    loading, and the local CUA MCP bridge without sending a Codex prompt,
    reading task material, or recording auth/path/raw-output details.
    """

    route_gate = build_agents_last_exam_host_codex_cli_route(
        codex_binary=codex_binary,
        codex_binary_available=codex_binary_available,
        codex_version_text=codex_version_text,
        host_auth_cache_present=host_auth_cache_present,
        host_config_present=host_config_present,
        require_host_config=require_host_config,
        cua_mcp_assets_root=cua_mcp_assets_root,
        ale_sandbox_cua_smoke_ready=ale_sandbox_cua_smoke_ready,
        operator_authorized_host_codex_auth=operator_authorized_host_codex_auth,
    )
    codex_exec_probe = _agents_last_exam_codex_exec_surface_probe(codex_binary)
    mcp_config_probe = _agents_last_exam_codex_mcp_config_probe(
        codex_binary,
        cua_mcp_assets_root=cua_mcp_assets_root,
        cua_server_url=cua_server_url,
    )
    cua_mcp_test_probe = _agents_last_exam_cua_mcp_test_probe(
        cua_mcp_assets_root=cua_mcp_assets_root,
        install_node_deps=install_node_deps,
    )
    return build_agents_last_exam_host_codex_cua_no_task_smoke(
        route_gate=route_gate,
        codex_exec_probe=codex_exec_probe,
        mcp_config_probe=mcp_config_probe,
        cua_mcp_test_probe=cua_mcp_test_probe,
    )

def _agents_last_exam_boundary_flag(
    payload: dict[str, Any],
    key: str,
    *,
    default: bool = False,
) -> bool:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    return bool(boundary.get(key, default))

def _agents_last_exam_ready_input(
    payload: dict[str, Any],
    *,
    schema_version: str,
    blocker_prefix: str,
) -> tuple[bool, str | None]:
    if not isinstance(payload, dict):
        return False, f"{blocker_prefix}_missing"
    if payload.get("schema_version") != schema_version:
        return False, f"{blocker_prefix}_schema_mismatch"
    if payload.get("ready") is not True:
        first_blocker = _agents_last_exam_public_id(
            payload.get("first_blocker"),
            limit=80,
        )
        return False, first_blocker or f"{blocker_prefix}_not_ready"
    return True, None

def _agents_last_exam_bool_requirement(value: bool | str | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "required", "requires_task_data"}:
        return True
    if normalized in {"0", "false", "no", "not_required", "none"}:
        return False
    return None

def _agents_last_exam_source_freshness_input(
    launch_packet: dict[str, Any] | None,
    *,
    required: bool,
) -> tuple[bool | None, str | None]:
    if not required:
        return None, None
    if not isinstance(launch_packet, dict):
        return False, "fresh_source_launch_packet_missing"
    source_lock = launch_packet.get("source_lock")
    if not isinstance(source_lock, dict):
        return False, "ale_source_freshness_not_verified"
    if source_lock.get("fetch_origin_attempted") is not True:
        return False, "ale_source_fetch_origin_not_attempted"
    if source_lock.get("fetch_origin_ok") is not True:
        return False, "ale_source_fetch_origin_failed"
    if source_lock.get("require_upstream_current") is not True:
        return False, "ale_source_upstream_current_not_required"
    if source_lock.get("upstream_declared") is not True:
        return False, "ale_source_upstream_missing"
    if source_lock.get("head_matches_upstream") is not True:
        return False, "ale_source_not_at_upstream_head"
    if source_lock.get("upstream_ahead_count") != 0:
        return False, "ale_source_upstream_ahead_count_nonzero"
    if source_lock.get("upstream_behind_count") != 0:
        return False, "ale_source_upstream_behind_count_nonzero"
    return True, None

def _agents_last_exam_task_data_source_readiness(
    *,
    requires_task_data: bool | str | None,
    task_data_source: str | None,
    baked_task_input_present: bool | None,
    baked_task_input_readiness: dict[str, Any] | None,
    gcs_sa_key: str | None,
    gcs_sa_key_present: bool | None,
    enforce_task_data_source: bool,
) -> dict[str, Any]:
    requirement = _agents_last_exam_bool_requirement(requires_task_data)
    raw_source = task_data_source.strip() if isinstance(task_data_source, str) else ""
    source = _agents_last_exam_public_id(raw_source, limit=120)
    official_gcs_source = raw_source.startswith("gs://ale-data-public")
    gcs_key_declared = bool(gcs_sa_key)
    gcs_key_file_present = False
    if gcs_sa_key:
        try:
            gcs_key_file_present = Path(gcs_sa_key).expanduser().is_file()
        except (OSError, RuntimeError):
            gcs_key_file_present = False
    effective_gcs_key_present = (
        bool(gcs_sa_key_present)
        if gcs_sa_key_present is not None
        else gcs_key_file_present
    )
    baked_probe_declared = isinstance(baked_task_input_readiness, dict)
    baked_probe_ready = (
        baked_task_input_readiness.get("schema_version")
        == AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION
        and baked_task_input_readiness.get("ready") is True
        if baked_probe_declared
        else False
    )
    effective_baked_input_present = (
        bool(baked_task_input_present)
        if baked_task_input_present is not None
        else baked_probe_ready
    )
    checked = enforce_task_data_source or requirement is not None or bool(source)
    blockers: list[str] = []
    if checked and requirement is None:
        blockers.append("task_data_requirement_unknown")
    if requirement is True:
        if not source:
            blockers.append("task_data_source_missing_for_required_task")
        elif raw_source == "baked_in_sandbox":
            if baked_probe_declared and baked_probe_ready is not True:
                blockers.append(
                    _agents_last_exam_public_id(
                        baked_task_input_readiness.get("first_blocker"),
                        limit=80,
                    )
                    or "baked_task_input_not_verified"
                )
            elif effective_baked_input_present is not True:
                blockers.append("baked_task_input_not_verified")
        elif official_gcs_source:
            if effective_gcs_key_present is not True:
                blockers.append("gcs_sa_key_presence_not_verified")
        elif raw_source in {"none", "local"}:
            blockers.append("task_data_source_not_sufficient_for_required_task")
        else:
            blockers.append("task_data_source_unsupported_for_required_task")
    ready = checked and not blockers
    if requirement is False:
        ready = True
    return {
        "checked": checked,
        "ready": ready,
        "first_blocker": blockers[0] if blockers else None,
        "blockers": blockers,
        "requires_task_data": requirement,
        "requires_task_data_declared": requirement is not None,
        "task_data_source": source,
        "task_data_source_declared": bool(source),
        "official_gcs_source": official_gcs_source,
        "baked_input_present": effective_baked_input_present is True,
        "baked_input_presence_declared": baked_task_input_present is not None
        or baked_probe_declared,
        "baked_input_probe_declared": baked_probe_declared,
        "baked_input_probe_ready": baked_probe_ready,
        "gcs_sa_key_declared": gcs_key_declared or gcs_sa_key_present is not None,
        "gcs_sa_key_present": effective_gcs_key_present,
        "gcs_sa_key_path_recorded": False,
        "credential_values_read": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
    }

def build_agents_last_exam_validation_run_gate(
    *,
    selected_task_id: str | None,
    validation_hypothesis: str | None,
    task_material_readiness: dict[str, Any],
    host_codex_no_task_e2e: dict[str, Any],
    exact_dry_run_result: dict[str, Any],
    launch_packet: dict[str, Any] | None = None,
    result_reducer_ready: bool = False,
    no_upload: bool = True,
    submit_enabled: bool = False,
    leaderboard_enabled: bool = False,
    formal_score_candidate: bool = False,
    require_fresh_source: bool = False,
    expected_formal_agent: str = "host_codex_gpt55_xhigh",
) -> dict[str, Any]:
    """Combine compact ALE readiness into a pre-run decision gate."""

    task_label = _agents_last_exam_public_id(selected_task_id, limit=180)
    hypothesis_label = _agents_last_exam_public_id(validation_hypothesis, limit=240)
    fresh_source_required = bool(formal_score_candidate or require_fresh_source)
    blockers: list[str] = []
    for payload, schema_version, prefix in (
        (
            task_material_readiness,
            AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
            "task_material_readiness",
        ),
        (
            host_codex_no_task_e2e,
            AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
            "host_codex_no_task_e2e",
        ),
        (
            exact_dry_run_result,
            AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION,
            "exact_dry_run_result",
        ),
    ):
        ready, blocker = _agents_last_exam_ready_input(
            payload,
            schema_version=schema_version,
            blocker_prefix=prefix,
        )
        if not ready and blocker:
            blockers.append(blocker)

    launch_packet_ready = None
    if launch_packet is not None:
        ready, blocker = _agents_last_exam_ready_input(
            launch_packet,
            schema_version=AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION,
            blocker_prefix="launch_packet",
        )
        launch_packet_ready = ready
        if not ready and blocker:
            blockers.append(blocker)

    fresh_source_ready, fresh_source_blocker = _agents_last_exam_source_freshness_input(
        launch_packet,
        required=fresh_source_required,
    )
    if fresh_source_blocker:
        blockers.append(fresh_source_blocker)

    if not hypothesis_label:
        blockers.append("validation_hypothesis_missing")
    if result_reducer_ready is not True:
        blockers.append("compact_result_reducer_not_ready")
    if no_upload is not True:
        blockers.append("no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("submit_must_remain_disabled")
    if leaderboard_enabled:
        blockers.append("leaderboard_must_remain_disabled")

    boundary_payloads = [
        ("task_material_readiness", task_material_readiness),
        ("host_codex_no_task_e2e", host_codex_no_task_e2e),
        ("exact_dry_run_result", exact_dry_run_result),
    ]
    if launch_packet is not None:
        boundary_payloads.append(("launch_packet", launch_packet))
    for name, payload in boundary_payloads:
        if _agents_last_exam_boundary_flag(payload, "credential_values_recorded"):
            blockers.append(f"{name}_credential_values_recorded")
        if _agents_last_exam_boundary_flag(payload, "local_paths_recorded"):
            blockers.append(f"{name}_local_paths_recorded")
        if _agents_last_exam_boundary_flag(payload, "raw_trajectory_read"):
            blockers.append(f"{name}_raw_trajectory_read")
        if _agents_last_exam_boundary_flag(payload, "task_body_read"):
            blockers.append(f"{name}_task_body_read")
        if _agents_last_exam_boundary_flag(payload, "screenshot_captured"):
            blockers.append(f"{name}_screenshot_captured")
        if _agents_last_exam_boundary_flag(payload, "hidden_references_allowed"):
            blockers.append(f"{name}_hidden_refs_allowed")
        if _agents_last_exam_boundary_flag(payload, "production_actions_allowed"):
            blockers.append(f"{name}_production_actions_allowed")

    expected = (
        exact_dry_run_result.get("expected")
        if isinstance(exact_dry_run_result.get("expected"), dict)
        else {}
    )
    expected_task = expected.get("task") if isinstance(expected, dict) else None
    if task_label and expected_task and task_label != expected_task:
        blockers.append("selected_task_mismatch_exact_dry_run")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_operator_authorized_local_no_upload_ale_validation_run",
        "blockers": blockers,
        "selected_task": {
            "task_id": task_label,
            "source": "compact_readiness_artifacts",
        },
        "validation_hypothesis": hypothesis_label,
        "readiness_inputs": {
            "task_material_ready": task_material_readiness.get("ready") is True,
            "host_codex_no_task_e2e_ready": host_codex_no_task_e2e.get("ready") is True,
            "exact_dry_run_ready": exact_dry_run_result.get("ready") is True,
            "launch_packet_ready": launch_packet_ready,
            "fresh_source_required": fresh_source_required,
            "fresh_source_ready": fresh_source_ready,
            "compact_result_reducer_ready": result_reducer_ready is True,
        },
        "model_policy": {
            "connectivity_e2e_model": "gpt-5.3-codex-spark",
            "formal_score_agent": expected_formal_agent,
            "formal_score_candidate": bool(formal_score_candidate),
        },
        "run_boundary": {
            "local_only": True,
            "no_upload": no_upload is True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "operator_authorization_required_before_task_run": True,
            "task_run_started_by_this_gate": False,
            "container_started_by_this_gate": False,
            "model_api_invoked_by_this_gate": False,
            "codex_prompt_sent_by_this_gate": False,
            "raw_trajectory_read": False,
            "task_body_read_by_goal_harness": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "operator_authorized_local_no_upload_ale_validation_run"
            if ready
            else "repair_ale_validation_run_gate_blocker",
            "minimum_next_evidence": (
                "A task-level ALE run may proceed only as local/no-upload/no-submit "
                "work with compact result reduction through the ALE reducer, and "
                "with a concrete Goal Harness validation hypothesis recorded."
            ),
            "must_not_claim": [
                "ALE task success before compact result ingest",
                "ALE score uplift before paired evidence",
                "Goal Harness treatment advantage before paired evidence",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
        },
    }

def _agents_last_exam_public_task_parts(task_id: str | None) -> tuple[list[str], str | None]:
    label = _agents_last_exam_public_id(task_id, limit=180)
    if not isinstance(task_id, str) or not task_id.strip():
        return [], label
    text = task_id.strip().replace("\\", "/")
    parts = [part for part in text.split("/") if part]
    safe = (
        not text.startswith("/")
        and not text.startswith("~")
        and len(parts) == 2
        and all(part not in {".", ".."} for part in parts)
        and all(_agents_last_exam_public_id(part, limit=120) == part for part in parts)
    )
    return (parts if safe else []), label

def _agents_last_exam_public_task_list_membership(
    source_root: str | None,
    task_id: str | None,
    selected_task_lists: Iterable[str],
) -> dict[str, Any]:
    safe_task_id = str(task_id or "").strip().replace("\\", "/")
    memberships: dict[str, bool] = {}
    checked = 0
    present = 0
    if not source_root:
        return {
            "checked": False,
            "selected_task_lists": [],
            "membership": memberships,
            "present_count": present,
            "path_recorded": False,
        }
    try:
        root = Path(source_root).expanduser()
        selected_root = root / "selected_tasks"
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "selected_task_lists": [],
            "membership": memberships,
            "present_count": present,
            "path_recorded": False,
        }
    safe_lists: list[str] = []
    for raw_name in selected_task_lists:
        label = _agents_last_exam_public_id(raw_name, limit=120)
        if not label:
            continue
        parts = [part for part in str(raw_name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            continue
        candidate = selected_root.joinpath(*parts)
        try:
            resolved_candidate = candidate.resolve()
            inside_root = resolved_candidate == resolved_root or (
                resolved_root in resolved_candidate.parents
            )
        except OSError:
            inside_root = False
        safe_lists.append(label)
        if not inside_root or not candidate.is_file():
            memberships[label] = False
            continue
        checked += 1
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            memberships[label] = False
            continue
        matched = any(line.strip().replace("\\", "/") == safe_task_id for line in lines)
        memberships[label] = matched
        if matched:
            present += 1
    return {
        "checked": checked > 0,
        "selected_task_lists": safe_lists,
        "membership": memberships,
        "present_count": present,
        "path_recorded": False,
    }

_AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE = re.compile(
    r"^\s*(?:self\.)?REQUIRES_TASK_DATA\s*(?::[^=]+)?=\s*(True|False)\b"
)


def _agents_last_exam_requires_task_data_line_scan(
    *,
    source_root: str | None,
    task_id: str,
    max_lines: int = 1200,
) -> dict[str, Any]:
    parts, task_label = _agents_last_exam_public_task_parts(task_id)
    if not parts:
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "selected_task_id_not_public_safe",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    try:
        root = Path(source_root).expanduser() if source_root else None
    except (OSError, RuntimeError):
        root = None
    if root is None or not root.is_dir():
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "source_root_not_available",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    source_file = root / "tasks" / parts[0] / parts[1] / "main.py"
    try:
        resolved_root = root.resolve()
        resolved_source_file = source_file.resolve()
        inside_root = resolved_source_file == resolved_root or (
            resolved_root in resolved_source_file.parents
        )
    except OSError:
        inside_root = False
    if not inside_root or not source_file.is_file():
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "task_config_main_py_missing",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    scanned = 0
    try:
        with source_file.open(encoding="utf-8") as handle:
            for raw_line in handle:
                scanned += 1
                match = _AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE.match(raw_line)
                if match:
                    requires_task_data = match.group(1) == "True"
                    return {
                        "task_id": task_label,
                        "checked": True,
                        "requires_task_data": requires_task_data,
                        "requires_task_data_declared": True,
                        "assignment_found": True,
                        "assignment_kind": "requires_task_data_bool_assignment",
                        "line_count_scanned": scanned,
                        "first_blocker": None,
                        "task_source_path_recorded": False,
                        "task_source_content_recorded": False,
                    }
                if scanned >= max_lines:
                    break
    except OSError:
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": scanned,
            "first_blocker": "task_config_main_py_unreadable",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    return {
        "task_id": task_label,
        "checked": True,
        "requires_task_data": True,
        "requires_task_data_declared": False,
        "assignment_found": False,
        "assignment_kind": "default_true_when_assignment_missing",
        "line_count_scanned": scanned,
        "first_blocker": None,
        "task_source_path_recorded": False,
        "task_source_content_recorded": False,
    }

def _agents_last_exam_public_selected_task_scan(
    source_root: str | None,
    selected_task_lists: Iterable[str],
) -> dict[str, Any]:
    labels: list[str] = []
    task_ids: set[str] = set()
    missing_lists = 0
    checked_lists = 0
    unsafe_lists = 0
    if not source_root:
        return {
            "checked": False,
            "selected_task_lists": labels,
            "selected_task_count": 0,
            "checked_list_count": 0,
            "missing_list_count": 0,
            "unsafe_list_count": 0,
            "path_recorded": False,
            "task_ids": [],
        }
    try:
        root = Path(source_root).expanduser()
        selected_root = root / "selected_tasks"
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "selected_task_lists": labels,
            "selected_task_count": 0,
            "checked_list_count": 0,
            "missing_list_count": 0,
            "unsafe_list_count": 0,
            "path_recorded": False,
            "task_ids": [],
        }
    for raw_name in selected_task_lists:
        label = _agents_last_exam_public_id(raw_name, limit=120)
        if not label:
            unsafe_lists += 1
            continue
        parts = [part for part in str(raw_name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            labels.append(label)
            unsafe_lists += 1
            continue
        candidate = selected_root.joinpath(*parts)
        try:
            resolved_candidate = candidate.resolve()
            inside_root = resolved_candidate == resolved_root or (
                resolved_root in resolved_candidate.parents
            )
        except OSError:
            inside_root = False
        labels.append(label)
        if not inside_root or not candidate.is_file():
            missing_lists += 1
            continue
        checked_lists += 1
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            missing_lists += 1
            continue
        for line in lines:
            raw_task_id = line.strip().replace("\\", "/")
            if not raw_task_id or raw_task_id.startswith("#"):
                continue
            parts, safe_label = _agents_last_exam_public_task_parts(raw_task_id)
            if parts and safe_label:
                task_ids.add("/".join(parts))
    return {
        "checked": checked_lists > 0,
        "selected_task_lists": labels,
        "selected_task_count": len(task_ids),
        "checked_list_count": checked_lists,
        "missing_list_count": missing_lists,
        "unsafe_list_count": unsafe_lists,
        "path_recorded": False,
        "task_ids": sorted(task_ids),
    }

def build_agents_last_exam_candidate_task_data_scan(
    *,
    source_root: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    allow_demo_candidate: bool = False,
) -> dict[str, Any]:
    """Scan selected ALE task configs for local no-task-data candidates.

    This is a bounded config-line scan: it extracts only a
    ``REQUIRES_TASK_DATA`` boolean assignment signal from task ``main.py`` and
    never records source paths or source text.
    """

    selected = _agents_last_exam_public_selected_task_scan(
        source_root,
        selected_task_lists,
    )
    blockers: list[str] = []
    if selected.get("checked") is not True:
        blockers.append("selected_task_lists_not_checked")
    task_ids = [
        task_id
        for task_id in selected.get("task_ids", [])
        if isinstance(task_id, str)
    ]
    if selected.get("checked") is True and not task_ids:
        blockers.append("selected_task_lists_empty")

    scan_results = [
        _agents_last_exam_requires_task_data_line_scan(
            source_root=source_root,
            task_id=task_id,
        )
        for task_id in task_ids
    ]
    checked_results = [item for item in scan_results if item.get("checked") is True]
    no_data_candidates = [
        str(item.get("task_id"))
        for item in checked_results
        if item.get("requires_task_data") is False and item.get("task_id")
    ]
    demo_no_data_candidates = [
        task_id for task_id in no_data_candidates if task_id.startswith("demo__")
    ]
    formal_no_data_candidates = [
        task_id for task_id in no_data_candidates if not task_id.startswith("demo__")
    ]
    eligible_candidates = (
        no_data_candidates if allow_demo_candidate else formal_no_data_candidates
    )
    if task_ids and not no_data_candidates:
        blockers.append("no_no_task_data_candidate_found")
    elif task_ids and not eligible_candidates:
        blockers.append("no_formal_no_task_data_candidate_found")
    ready = not blockers
    explicit_false_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is False
        and item.get("requires_task_data_declared") is True
    )
    explicit_true_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is True
        and item.get("requires_task_data_declared") is True
    )
    default_true_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is True
        and item.get("requires_task_data_declared") is False
    )
    missing_config_count = sum(
        1 for item in scan_results if item.get("checked") is not True
    )
    return {
        "schema_version": AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_no_task_data_ale_candidate_gate",
        "blockers": blockers,
        "selected_task_lists": {
            key: value
            for key, value in selected.items()
            if key != "task_ids"
        },
        "scan_summary": {
            "selected_task_count": len(task_ids),
            "task_config_checked_count": len(checked_results),
            "task_config_missing_or_unreadable_count": missing_config_count,
            "explicit_requires_task_data_false_count": explicit_false_count,
            "explicit_requires_task_data_true_count": explicit_true_count,
            "default_requires_task_data_true_count": default_true_count,
            "no_task_data_candidate_count": len(no_data_candidates),
            "formal_no_task_data_candidate_count": len(formal_no_data_candidates),
            "demo_no_task_data_candidate_count": len(demo_no_data_candidates),
            "allow_demo_candidate": bool(allow_demo_candidate),
        },
        "candidate_tasks": {
            "eligible_no_task_data_candidates": eligible_candidates[:25],
            "formal_no_task_data_candidates": formal_no_data_candidates[:25],
            "demo_no_task_data_candidates": demo_no_data_candidates[:25],
            "candidate_count_truncated": len(eligible_candidates) > 25,
            "task_ids_public_only": True,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "selected_task_list_content_recorded": False,
            "task_config_line_scan": True,
            "task_config_source_content_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_instruction_file_read": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_no_task_data_formal_ale_validation_gate"
            if ready
            else "do_not_launch_formal_ale_until_task_data_substrate_is_ready",
            "minimum_next_evidence": (
                "A formal local/no-upload ALE candidate should either be listed "
                "as not requiring task data or carry a separately verified "
                "task-data source readiness signal before any model task run."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_config_line_scan": True,
            "task_config_source_content_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_instruction_file_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def build_agents_last_exam_baked_task_input_readiness(
    *,
    selected_task_id: str | None,
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    docker_binary: str = "docker",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Probe whether an ALE Docker image contains a task baked input dir.

    This starts a tiny shell in the image to test directory existence/readability.
    It does not run the task, list files, read task data, or record the checked path.
    """

    parts, task_label = _agents_last_exam_public_task_parts(selected_task_id)
    blockers: list[str] = []
    if not parts:
        blockers.append("selected_task_id_not_public_safe")
    docker_label = _agents_last_exam_public_id(docker_binary, limit=80)
    docker_binary_safe = bool(
        docker_label
        and docker_binary == docker_label
        and "/" not in docker_binary
        and "\\" not in docker_binary
    )
    if not docker_binary_safe:
        blockers.append("docker_binary_must_be_name_not_path")
    docker_available = bool(docker_binary_safe and shutil.which(docker_binary))
    if docker_binary_safe and not docker_available:
        blockers.append("docker_cli_missing")

    raw_image_metadata = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    image = _agents_last_exam_public_image_metadata(
        raw_image_metadata,
        fallback_image_ref=image_ref,
    )
    if image.get("present") is not True:
        blockers.append(
            _agents_last_exam_public_id(image.get("first_blocker"), limit=80)
            or "docker_image_missing"
        )

    attempted = False
    container_started = False
    baked_input_present = False
    baked_input_readable = False
    probe_return_code: int | None = None
    probe_error: str | None = None
    if not blockers and parts and docker_binary_safe:
        baked_input_path = (
            f"/media/user/data/agenthle/{parts[0]}/{parts[1]}/base/input"
        )
        attempted = True
        try:
            result = subprocess.run(
                [
                    docker_binary,
                    "run",
                    "--rm",
                    "--entrypoint",
                    "/bin/sh",
                    image_ref,
                    "-c",
                    'test -d "$1" && test -r "$1"',
                    "sh",
                    baked_input_path,
                ],
                check=False,
                text=True,
                capture_output=True,
                timeout=max(1, int(timeout_seconds)),
            )
        except subprocess.TimeoutExpired:
            probe_error = "baked_task_input_probe_timeout"
        except Exception:
            probe_error = "baked_task_input_probe_failed"
        else:
            container_started = True
            probe_return_code = result.returncode
            if result.returncode == 0:
                baked_input_present = True
                baked_input_readable = True
            else:
                probe_error = "baked_task_input_missing"
    if probe_error:
        blockers.append(probe_error)

    ready = not blockers and baked_input_present and baked_input_readable
    return {
        "schema_version": AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_baked_sandbox_task_data_source",
        "blockers": blockers,
        "task": {
            "task_id": task_label,
            "category": parts[0] if parts else None,
            "name": parts[1] if parts else None,
        },
        "image": image,
        "probe": {
            "kind": "docker_shell_test_directory_only",
            "attempted": attempted,
            "container_started": container_started,
            "baked_input_present": baked_input_present,
            "baked_input_readable": baked_input_readable,
            "return_code_zero": probe_return_code == 0
            if probe_return_code is not None
            else None,
            "expected_path_template": "ale_task_base_input",
            "expected_path_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": container_started,
            "task_run_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "directory_listed": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "read_boundary": {
            "compact_only": True,
            "path_existence_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }

def build_agents_last_exam_baked_task_input_scan(
    *,
    source_root: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    docker_binary: str = "docker",
    max_tasks: int = 120,
    timeout_seconds: int = 180,
    probe_results: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Scan selected public ALE tasks for baked input dirs without reading them."""

    selected = _agents_last_exam_public_selected_task_scan(
        source_root,
        selected_task_lists,
    )
    task_ids = [
        task_id
        for task_id in selected.get("task_ids", [])
        if _agents_last_exam_public_task_parts(task_id)[0]
    ]
    max_count = max(0, int(max_tasks))
    if max_count:
        task_ids = task_ids[:max_count]
    else:
        task_ids = []
    blockers: list[str] = []
    if selected.get("checked") is not True:
        blockers.append("selected_task_lists_not_checked")
    if not task_ids:
        blockers.append("no_selected_tasks_to_probe")

    docker_label = _agents_last_exam_public_id(docker_binary, limit=80)
    docker_binary_safe = bool(
        docker_label
        and docker_binary == docker_label
        and "/" not in docker_binary
        and "\\" not in docker_binary
    )
    if not docker_binary_safe:
        blockers.append("docker_binary_must_be_name_not_path")
    docker_available = bool(docker_binary_safe and shutil.which(docker_binary))
    raw_image_metadata = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    image = _agents_last_exam_public_image_metadata(
        raw_image_metadata,
        fallback_image_ref=image_ref,
    )

    fixture_probe_used = isinstance(probe_results, dict)
    if not fixture_probe_used:
        if docker_binary_safe and not docker_available:
            blockers.append("docker_cli_missing")
        if image.get("present") is not True:
            blockers.append(
                _agents_last_exam_public_id(image.get("first_blocker"), limit=80)
                or "docker_image_missing"
            )

    attempted = False
    container_started = False
    candidates: list[str] = []
    probe_error: str | None = None
    if not blockers and task_ids:
        attempted = True
        if fixture_probe_used:
            for task_id in task_ids:
                if probe_results.get(task_id) is True:
                    candidates.append(task_id)
        else:
            script = (
                'while IFS= read -r task; do '
                'category="${task%%/*}"; name="${task#*/}"; '
                'path="/media/user/data/agenthle/${category}/${name}/base/input"; '
                'if test -d "$path" && test -r "$path"; then '
                'printf "%s\\t1\\n" "$task"; else printf "%s\\t0\\n" "$task"; fi; '
                "done"
            )
            try:
                result = subprocess.run(
                    [
                        docker_binary,
                        "run",
                        "--rm",
                        "--entrypoint",
                        "/bin/sh",
                        image_ref,
                        "-c",
                        script,
                    ],
                    input="\n".join(task_ids) + "\n",
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=max(1, int(timeout_seconds)),
                )
            except subprocess.TimeoutExpired:
                probe_error = "baked_task_input_scan_timeout"
            except Exception:
                probe_error = "baked_task_input_scan_failed"
            else:
                container_started = True
                if result.returncode != 0:
                    probe_error = "baked_task_input_scan_nonzero"
                else:
                    safe_task_set = set(task_ids)
                    for line in result.stdout.splitlines():
                        raw_task_id, _, flag = line.partition("\t")
                        if flag != "1" or raw_task_id not in safe_task_set:
                            continue
                        parts, safe_label = _agents_last_exam_public_task_parts(
                            raw_task_id
                        )
                        if parts and safe_label:
                            candidates.append(raw_task_id)
    if probe_error:
        blockers.append(probe_error)
    if attempted and not candidates and not blockers:
        blockers.append("no_baked_input_candidate_found")

    ready = bool(candidates) and not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_baked_input_formal_candidate_selection",
        "blockers": blockers,
        "selected_tasks": {
            "checked": selected.get("checked") is True,
            "selected_task_lists": selected.get("selected_task_lists") or [],
            "selected_task_count": selected.get("selected_task_count"),
            "probed_task_count": len(task_ids),
            "max_tasks": max_count,
            "path_recorded": False,
        },
        "image": image,
        "probe": {
            "kind": "docker_shell_batch_test_directory_only",
            "attempted": attempted,
            "container_started": container_started,
            "fixture_probe_used": fixture_probe_used,
            "baked_input_candidate_count": len(candidates),
            "expected_path_template": "ale_task_base_input",
            "expected_path_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
        },
        "candidates": {
            "eligible_baked_input_candidates": candidates[:25],
            "candidate_count": len(candidates),
            "task_ids_public": True,
            "task_paths_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": container_started,
            "task_run_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "directory_listed": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "read_boundary": {
            "compact_only": True,
            "path_existence_only": True,
            "selected_task_lists_read": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }

def build_agents_last_exam_task_material_readiness(
    *,
    source_root: str | None,
    selected_task_id: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    requires_task_data: bool | str | None = None,
    task_data_source: str | None = None,
    baked_task_input_present: bool | None = None,
    baked_task_input_readiness: dict[str, Any] | None = None,
    gcs_sa_key: str | None = None,
    gcs_sa_key_present: bool | None = None,
    enforce_task_data_source: bool = False,
) -> dict[str, Any]:
    """Check local ALE task material existence without reading task bodies."""

    parts, task_label = _agents_last_exam_public_task_parts(selected_task_id)
    blockers: list[str] = []
    if not parts:
        blockers.append("selected_task_id_not_public_safe")
    try:
        root = Path(source_root).expanduser() if source_root else None
    except (OSError, RuntimeError):
        root = None
    source_root_available = bool(root and root.is_dir())
    if not source_root_available or root is None:
        blockers.append("source_root_not_available")

    task_dir_available = False
    task_card_present = False
    scripts_dir_present = False
    scorer_script_count = 0
    task_dir_entry_count = 0
    if root is not None and source_root_available and parts:
        task_dir = root / "tasks" / parts[0] / parts[1]
        try:
            resolved_root = root.resolve()
            resolved_task_dir = task_dir.resolve()
            inside_root = resolved_task_dir == resolved_root or (
                resolved_root in resolved_task_dir.parents
            )
        except OSError:
            inside_root = False
        task_dir_available = bool(inside_root and task_dir.is_dir())
        if task_dir_available:
            task_card_present = (task_dir / "task_card.json").is_file()
            scripts_dir = task_dir / "scripts"
            scripts_dir_present = scripts_dir.is_dir()
            try:
                task_dir_entry_count = sum(1 for _ in task_dir.iterdir())
            except OSError:
                task_dir_entry_count = 0
            if scripts_dir_present:
                try:
                    scorer_script_count = sum(
                        1
                        for path in scripts_dir.iterdir()
                        if path.is_file()
                        and path.suffix == ".py"
                        and "score" in path.name.lower()
                    )
                except OSError:
                    scorer_script_count = 0
    if not task_dir_available:
        blockers.append("task_directory_missing")
    if not task_card_present:
        blockers.append("task_card_json_missing")
    if not scripts_dir_present:
        blockers.append("task_scripts_directory_missing")
    if scorer_script_count < 1:
        blockers.append("task_scorer_script_missing")

    membership = _agents_last_exam_public_task_list_membership(
        source_root,
        selected_task_id,
        selected_task_lists,
    )
    if membership.get("checked") is not True:
        blockers.append("selected_task_list_membership_not_checked")
    elif int(membership.get("present_count") or 0) < 1:
        blockers.append("selected_task_not_in_public_task_lists")
    task_data = _agents_last_exam_task_data_source_readiness(
        requires_task_data=requires_task_data,
        task_data_source=task_data_source,
        baked_task_input_present=baked_task_input_present,
        baked_task_input_readiness=baked_task_input_readiness,
        gcs_sa_key=gcs_sa_key,
        gcs_sa_key_present=gcs_sa_key_present,
        enforce_task_data_source=enforce_task_data_source,
    )
    if enforce_task_data_source and task_data.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(task_data.get("first_blocker"), limit=80)
            or "task_data_source_not_ready"
        )

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_no_upload_ale_task_gate",
        "blockers": blockers,
        "task": {
            "task_id": task_label,
            "category": parts[0] if parts else None,
            "name": parts[1] if parts else None,
            "task_dir_available": task_dir_available,
            "task_card_json_present": task_card_present,
            "scripts_dir_present": scripts_dir_present,
            "scorer_script_count": scorer_script_count,
            "task_dir_entry_count": task_dir_entry_count,
            "task_dir_path_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
        },
        "task_data": task_data,
        "public_task_lists": membership,
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_local_no_upload_ale_validation_run_gate"
            if ready
            else "repair_ale_task_material_readiness_blocker",
            "minimum_next_evidence": (
                "A local/no-upload ALE task gate should combine this material "
                "readiness signal with host Codex no-task E2E readiness and the "
                "compact result reducer boundary before any task-level run."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

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
    agent_timeout_observed: bool = False,
    agent_setup_timeout_observed: bool = False,
) -> str:
    """Summarize score-failure cause without collapsing verifier probes to none."""

    if official_score != 0:
        return "none"
    if (
        agent_setup_timeout_observed
        or "agent_setup_timeout_before_worker_start" in failure_attribution_labels
    ):
        return "agent_setup_timeout_score_failure"
    if "codex_model_access_unsupported_for_account" in failure_attribution_labels:
        return "codex_model_access_unsupported_score_failure"
    if "codex_model_access_failure_before_solution_attempt" in failure_attribution_labels:
        return "codex_model_access_score_failure"
    if "agent_setup_failed_before_worker_start" in failure_attribution_labels:
        return "agent_setup_score_failure"
    if "environment_setup_failed_before_worker" in failure_attribution_labels:
        return "agent_setup_score_failure"
    if "pre_worker_startup_blocker_recorded" in failure_attribution_labels:
        return "agent_setup_score_failure"
    if "agent_process_nonzero_exit_before_solution_attempt" in failure_attribution_labels:
        return "agent_process_nonzero_exit_score_failure"
    if verifier_dependency_failure_count:
        return "verifier_dependency_install_failure"
    if "verifier_platform_probe_failure" in failure_attribution_labels:
        return "verifier_platform_probe_failure"
    if any(label.startswith("verifier_") for label in failure_attribution_labels):
        return "verifier_infrastructure_failure"
    if "worker_self_validation_official_score_mismatch" in failure_attribution_labels:
        return "worker_self_validation_official_score_mismatch"
    if "worker_validation_scope_ambiguous_official_score_failure" in failure_attribution_labels:
        return "worker_validation_scope_ambiguous_official_score_failure"
    if "worker_bridge_connected_official_score_failure" in failure_attribution_labels:
        return "worker_bridge_connected_official_score_failure"
    if "official_verifier_solution_failure" in failure_attribution_labels:
        return "official_verifier_solution_failure"
    if agent_timeout_observed:
        return "agent_timeout_before_solution_completion"
    return "none"


TERMINAL_BENCH_WORKER_CASE_SUCCESS_VALIDATION_SCOPES = {
    "official_verifier_result",
    "case_success",
    "task_success",
    "worker_case_success",
    "worker_task_success",
    "solution_success",
}

TERMINAL_BENCH_WORKER_CONNECTIVITY_VALIDATION_SCOPES = {
    "worker_bridge_connectivity",
    "bridge_connectivity",
    "environment_connectivity",
    "environment_ready",
    "control_plane_connectivity",
}


def _terminal_bench_worker_validation_claim_kind(
    worker_benchmark_run: dict[str, Any],
) -> str:
    """Classify the worker-side compact validation claim.

    This uses only the worker's compact benchmark_run_v0 writeback. It does not
    inspect raw logs, task text, trajectories, or local paths.
    """

    validation = worker_benchmark_run.get("validation")
    validation_scope = str(worker_benchmark_run.get("validation_scope") or "").strip().lower()
    case_success_claimed = worker_benchmark_run.get("case_success_claimed") is True
    if isinstance(validation, dict):
        validation_scope = str(
            validation.get("validation_scope") or validation_scope
        ).strip().lower()
        case_success_claimed = (
            case_success_claimed or validation.get("case_success_claimed") is True
        )
        if validation.get("bridge_connected") is True and (
            validation_scope in TERMINAL_BENCH_WORKER_CONNECTIVITY_VALIDATION_SCOPES
        ):
            return "bridge_connectivity_only"
        if validation_scope in TERMINAL_BENCH_WORKER_CONNECTIVITY_VALIDATION_SCOPES:
            return "bridge_connectivity_only"
        if case_success_claimed or (
            validation_scope in TERMINAL_BENCH_WORKER_CASE_SUCCESS_VALIDATION_SCOPES
        ):
            return "worker_claimed_case_success"
        status = str(validation.get("status") or "").strip().lower()
        if status in {"passed", "pass", "ok", "success", "succeeded"}:
            return "legacy_ambiguous_validation_scope"
        checks = validation.get("checks")
        if isinstance(checks, list) and checks:
            failed_checks = validation.get("failed_checks")
            if not isinstance(failed_checks, list) or not failed_checks:
                return "legacy_ambiguous_validation_scope"

    progress = worker_benchmark_run.get("progress")
    if isinstance(progress, dict) and progress.get("completed") is True:
        if validation_scope in TERMINAL_BENCH_WORKER_CONNECTIVITY_VALIDATION_SCOPES:
            return "bridge_connectivity_only"
        if case_success_claimed or (
            validation_scope in TERMINAL_BENCH_WORKER_CASE_SUCCESS_VALIDATION_SCOPES
        ):
            return "worker_claimed_case_success"
        return "legacy_ambiguous_validation_scope"

    official_task_score = worker_benchmark_run.get("official_task_score")
    if isinstance(official_task_score, dict):
        value = official_task_score.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 1:
            return "official_case_success"
        if official_task_score.get("passed") is True:
            return "official_case_success"

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

    agent_dir = trial_dir / "agent"
    no_worker_artifacts = (
        not (agent_dir / "trajectory.json").exists()
        and not trace_path.exists()
        and not worker_benchmark_run_path.exists()
    )
    if trial_agent_result or not no_worker_artifacts:
        return False

    exception_kind = _compact_exception_kind(exception_type)
    if exception_kind in {"agent_setup_timeout", "agent_setup_failure"}:
        return True

    return exception_type == "NonZeroAgentExitCodeError" and (agent_dir / "setup").exists()


def _is_environment_setup_failure_before_worker(
    *,
    trial: dict[str, Any],
    exception_type: Any,
    trial_agent_result: dict[str, Any],
) -> bool:
    """Detect Harbor environment/setup failures before the custom agent starts."""

    if exception_type in (None, "", "none", "AgentTimeoutError"):
        return False
    if trial_agent_result:
        return False
    environment_setup = trial.get("environment_setup")
    agent_setup = trial.get("agent_setup")
    agent_execution = trial.get("agent_execution")
    return (
        isinstance(environment_setup, dict)
        and not isinstance(agent_setup, dict)
        and not isinstance(agent_execution, dict)
    )


def _terminal_bench_duration_tier(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        return "unknown"
    if seconds >= 600:
        return "over_10_minutes"
    if seconds >= 180:
        return "three_to_ten_minutes"
    if seconds >= 60:
        return "one_to_three_minutes"
    return "under_one_minute"


def _terminal_bench_environment_setup_failure_context(
    *,
    trial: dict[str, Any],
    exception_type: Any,
    trace_path: Path,
    worker_benchmark_run_path: Path,
) -> dict[str, Any]:
    """Return a compact phase-only diagnosis for environment setup failures."""

    environment_setup = (
        trial.get("environment_setup")
        if isinstance(trial.get("environment_setup"), dict)
        else {}
    )
    duration_seconds = _iso_duration_seconds(
        environment_setup.get("started_at"),
        environment_setup.get("finished_at") or environment_setup.get("updated_at"),
    )
    exception_text = str(exception_type or "none")
    timeout_signal = (
        "exception_type_timeout"
        if "timeout" in exception_text.lower()
        else "no_timeout_exception_type"
    )
    if timeout_signal == "exception_type_timeout":
        failure_kind = "environment_setup_timeout_before_worker"
    elif environment_setup.get("finished_at"):
        failure_kind = "environment_setup_runtime_error_before_worker"
    else:
        failure_kind = "environment_setup_interrupted_before_worker"

    context: dict[str, Any] = {
        "schema_version": "terminal_bench_environment_setup_failure_context_v0",
        "surface": "harbor_environment_setup",
        "failure_kind": failure_kind,
        "diagnostic_granularity": "phase_fields_only_no_raw_logs",
        "exception_type": exception_text,
        "timeout_signal": timeout_signal,
        "resource_signal": "not_observable_from_phase_fields",
        "environment_setup_present": bool(environment_setup),
        "environment_setup_started": bool(environment_setup.get("started_at")),
        "environment_setup_finished": bool(environment_setup.get("finished_at")),
        "agent_setup_started": isinstance(trial.get("agent_setup"), dict),
        "agent_execution_started": isinstance(trial.get("agent_execution"), dict),
        "worker_trace_present": trace_path.exists(),
        "worker_benchmark_run_present": worker_benchmark_run_path.exists(),
        "next_probe": "environment_setup_readiness_preflight_before_repeat",
    }
    if isinstance(duration_seconds, (int, float)) and not isinstance(
        duration_seconds, bool
    ):
        context["environment_setup_duration_seconds"] = duration_seconds
        context["environment_setup_duration_tier"] = _terminal_bench_duration_tier(
            duration_seconds
        )
    return context


def _is_compactable_benchmark_run_v0(payload: dict[str, Any]) -> bool:
    """Return true for payload shapes accepted by history append-benchmark-run."""

    if payload.get("schema_version") == "benchmark_run_v0":
        return True
    nested = payload.get("benchmark_run")
    return (
        isinstance(nested, dict)
        and nested.get("schema_version") == "benchmark_run_v0"
    )


def _compactable_benchmark_run_v0_payload(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if payload.get("schema_version") == "benchmark_run_v0":
        return payload
    nested = payload.get("benchmark_run")
    if isinstance(nested, dict) and nested.get("schema_version") == "benchmark_run_v0":
        return nested
    return None


TERMINAL_BENCH_NON_BLOCKING_WORKER_SETUP_LABELS = {
    "none",
    "ok",
    "success",
    "succeeded",
    "passed",
    "codex_runtime_install_or_preflight_ok",
    "codex_require_existing_preflight_ok",
    "worker_codex_materialization_verified",
}


def _terminal_bench_non_blocking_setup_label(value: Any) -> bool:
    label = _public_safe_benchmark_label(value)
    return bool(label and label in TERMINAL_BENCH_NON_BLOCKING_WORKER_SETUP_LABELS)


def _terminal_bench_worker_materialization_probe_contract(
    worker_benchmark_run: dict[str, Any],
) -> bool:
    """Detect compact worker probe contracts even when Harbor wrote a trial result."""

    compact = _compactable_benchmark_run_v0_payload(worker_benchmark_run)
    if compact is None:
        return False
    outcome = compact.get("worker_bridge_outcome")
    if not isinstance(outcome, dict):
        outcome = {}
    official_task_score = compact.get("official_task_score")
    if not isinstance(official_task_score, dict):
        official_task_score = {}
    mode = str(compact.get("mode") or "")
    return (
        compact.get("worker_materialization_real_probe") is True
        or compact.get("worker_materialization_probe_only") is True
        or compact.get("source_runner") == "terminal_bench_worker_materialization_probe"
        or mode.endswith("_worker_materialization_probe")
        or outcome.get("runner_return_status") == "worker_materialization_probe_completed"
        or official_task_score.get("kind") == "not_run_worker_materialization_probe"
    )


def _terminal_bench_worker_startup_blocker(
    worker_benchmark_run: dict[str, Any],
) -> str | None:
    """Extract a public-safe startup blocker from a compact worker benchmark_run."""

    checkpoint = worker_benchmark_run.get("worker_bridge_checkpoint")
    if not isinstance(checkpoint, dict):
        checkpoint = {}
    outcome = worker_benchmark_run.get("worker_bridge_outcome")
    if not isinstance(outcome, dict):
        outcome = {}
    validation = worker_benchmark_run.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    if _terminal_bench_worker_materialization_probe_contract(worker_benchmark_run):
        outcome_blocker = _public_safe_benchmark_label(
            outcome.get("worker_bridge_materialization_blocker")
            or worker_benchmark_run.get("worker_bridge_materialization_blocker")
        )
        outcome_status = _public_safe_benchmark_label(
            outcome.get("worker_bridge_materialization_status")
            or worker_benchmark_run.get("worker_bridge_materialization_status")
        )
        if (
            outcome_blocker in {None, "", "none"}
            or _terminal_bench_non_blocking_setup_label(outcome_blocker)
        ) and outcome_status in {
            "worker_codex_materialization_verified",
            "probe_contract_verified",
        }:
            return None

    outcome_startup_label = _public_safe_benchmark_label(
        outcome.get("pre_worker_startup_blocker")
    )
    startup_recorded = (
        checkpoint.get("checkpoint_kind") == "pre_worker_startup_blocker"
        or validation.get("worker_startup_blocker_recorded") is True
        or bool(
            outcome_startup_label
            and not _terminal_bench_non_blocking_setup_label(outcome_startup_label)
        )
    )
    if not startup_recorded:
        return None

    saw_non_blocking_setup_label = False
    for value in (
        checkpoint.get("pre_worker_startup_blocker"),
        worker_benchmark_run.get("pre_worker_startup_blocker"),
        outcome.get("pre_worker_startup_blocker"),
        worker_benchmark_run.get("first_blocker"),
        worker_benchmark_run.get("repeat_blocked_by"),
    ):
        label = _public_safe_benchmark_label(value)
        if label and label != "none":
            if _terminal_bench_non_blocking_setup_label(label):
                saw_non_blocking_setup_label = True
                continue
            return label
    if saw_non_blocking_setup_label:
        return None
    return "pre_worker_startup_blocker_recorded"


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


def _terminal_bench_finished_phase(trial: dict[str, Any], key: str) -> bool:
    phase = trial.get(key)
    if not isinstance(phase, dict):
        return False
    return bool(phase.get("started_at") and phase.get("finished_at"))


def _terminal_bench_official_zero_observation(
    *,
    trial: dict[str, Any],
    reward_value: float | int | None,
    exception_type: Any,
) -> dict[str, Any]:
    """Summarize a clean official-zero result from structured runner fields only."""

    phase_status = {
        "environment_setup_completed": _terminal_bench_finished_phase(
            trial, "environment_setup"
        ),
        "agent_setup_completed": _terminal_bench_finished_phase(trial, "agent_setup"),
        "agent_execution_completed": _terminal_bench_finished_phase(
            trial, "agent_execution"
        ),
        "verifier_completed": _terminal_bench_finished_phase(trial, "verifier"),
    }
    exception_present = exception_type not in (None, "", "none")
    detected = (
        reward_value == 0
        and not exception_present
        and phase_status["agent_setup_completed"]
        and phase_status["agent_execution_completed"]
        and phase_status["verifier_completed"]
    )
    return {
        "schema_version": "terminal_bench_official_zero_observation_v0",
        "detected": detected,
        "reward_value": reward_value,
        "exception_present": exception_present,
        **phase_status,
        "raw_logs_read": False,
        "raw_trace_recorded": False,
        "task_text_read": False,
    }


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


def _optional_positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        parsed = int(value)
        return parsed if parsed > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed_float = float(text)
        except ValueError:
            return None
        if not parsed_float.is_integer():
            return None
        parsed = int(parsed_float)
        return parsed if parsed > 0 else None
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


def _agents_last_exam_parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def build_agents_last_exam_local_exact_dry_run_result(
    *,
    stdout_text: str | None,
    exit_code: int | str | None,
    expected_task_id: str | None = None,
    expected_agent_id: str | None = None,
) -> dict[str, Any]:
    """Reduce ALE ``--dry-run`` stdout to a compact public-safe artifact.

    The raw stdout is intentionally not returned. The reducer keeps only
    public labels and matrix counts, so callers can persist the result without
    copying paths, task text, trajectories, screenshots, credentials, or command
    argv into Goal Harness state.
    """

    parsed_exit_code = _agents_last_exam_parse_int(exit_code)
    text = stdout_text if isinstance(stdout_text, str) else ""
    lines = [line.rstrip() for line in text.splitlines()]
    experiment_label: str | None = None
    environment_label: str | None = None
    environment_route_label: str | None = None
    concurrency: int | None = None
    declared_unit_count: int | None = None
    units: list[dict[str, Any]] = []
    in_units = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("experiment:"):
            experiment_label = _agents_last_exam_public_id(
                line.split(":", 1)[1],
                limit=160,
            )
            in_units = False
            continue
        if line.startswith("environment:"):
            value = line.split(":", 1)[1].strip()
            before_route, _, route = value.partition("(")
            environment_label = _agents_last_exam_public_id(
                before_route.strip(),
                limit=80,
            )
            environment_route_label = _agents_last_exam_public_id(
                route.rstrip(")").replace("->", "-to-") if route else value,
                limit=160,
            )
            in_units = False
            continue
        if line.startswith("concurrency:"):
            concurrency = _agents_last_exam_parse_int(line.split(":", 1)[1])
            in_units = False
            continue
        if line.startswith("units (") and line.endswith("):"):
            count_text = line[len("units (") : -len("):")]
            declared_unit_count = _agents_last_exam_parse_int(count_text)
            in_units = True
            continue
        if in_units:
            parts = line.split()
            if len(parts) >= 3:
                agent_label = _agents_last_exam_public_id(parts[0], limit=80)
                task_label = _agents_last_exam_public_id(parts[1], limit=180)
                variant_label = _agents_last_exam_public_id(parts[2], limit=40)
                units.append(
                    {
                        "agent": agent_label,
                        "task": task_label,
                        "variant": variant_label,
                    }
                )

    expected_task_label = _agents_last_exam_public_id(expected_task_id, limit=180)
    expected_agent_label = _agents_last_exam_public_id(expected_agent_id, limit=80)
    blockers: list[str] = []
    if parsed_exit_code != 0:
        blockers.append("ale_dry_run_exit_nonzero")
    if declared_unit_count is None:
        blockers.append("ale_dry_run_unit_count_missing")
    elif declared_unit_count != len(units):
        blockers.append("ale_dry_run_unit_count_mismatch")
    if expected_task_label and expected_task_label not in {
        str(unit.get("task") or "") for unit in units
    }:
        blockers.append("expected_task_not_in_dry_run_matrix")
    if expected_agent_label and expected_agent_label not in {
        str(unit.get("agent") or "") for unit in units
    }:
        blockers.append("expected_agent_not_in_dry_run_matrix")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_compact_ale_dry_run_result_ingest",
        "blockers": blockers,
        "exit_code": parsed_exit_code,
        "experiment": experiment_label,
        "environment": {
            "kind": environment_label,
            "route": environment_route_label,
        },
        "concurrency": concurrency,
        "unit_count_declared": declared_unit_count,
        "unit_count_parsed": len(units),
        "units": units[:50],
        "unit_list_truncated": len(units) > 50,
        "expected": {
            "agent": expected_agent_label,
            "task": expected_task_label,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_stdout_recorded": False,
        },
        "decision": {
            "next_allowed_action": "use_compact_ale_dry_run_result_for_run_gate"
            if ready
            else "repair_ale_dry_run_result_before_run_gate",
            "minimum_next_evidence": (
                "A compact ALE dry-run matrix with exit_code=0, matching expected "
                "agent/task labels, and no raw stdout/path/task-body leakage."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "raw_stdout_recorded": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


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


def _agents_last_exam_docker_image_metadata(image_ref: str) -> dict[str, Any]:
    """Inspect local Docker image metadata without starting a container."""

    if not shutil.which("docker"):
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": False,
            "first_blocker": "docker_cli_missing",
        }
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image_ref, "--format", "{{json .}}"],
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": False,
            "first_blocker": "docker_image_inspect_failed",
        }
    if result.returncode != 0 or not result.stdout.strip():
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_missing",
        }
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_inspect_not_json",
        }
    repo_digests = raw.get("RepoDigests") if isinstance(raw.get("RepoDigests"), list) else []
    metadata = raw.get("Metadata") if isinstance(raw.get("Metadata"), dict) else {}
    return {
        "image_ref": image_ref,
        "present": True,
        "probe_available": True,
        "id": _agents_last_exam_public_id(raw.get("Id"), limit=160),
        "digest": _agents_last_exam_public_id(
            next((item for item in repo_digests if isinstance(item, str)), None),
            limit=180,
        ),
        "architecture": _agents_last_exam_public_id(raw.get("Architecture"), limit=40),
        "os": _agents_last_exam_public_id(raw.get("Os"), limit=40),
        "size_bytes": int(raw.get("Size"))
        if isinstance(raw.get("Size"), int) and not isinstance(raw.get("Size"), bool)
        else None,
        "created": _agents_last_exam_public_id(raw.get("Created"), limit=80),
        "last_tag_time": _agents_last_exam_public_id(
            metadata.get("LastTagTime"),
            limit=80,
        ),
        "first_blocker": None,
    }


def _agents_last_exam_public_image_metadata(
    metadata: dict[str, Any],
    *,
    fallback_image_ref: str,
) -> dict[str, Any]:
    """Reduce Docker image metadata to compact public-safe fields."""

    image_ref = metadata.get("image_ref") or fallback_image_ref
    reduced: dict[str, Any] = {
        "image_ref": _agents_last_exam_public_id(image_ref, limit=180)
        or "image_ref_unavailable",
        "present": metadata.get("present") is True,
        "probe_available": metadata.get("probe_available") is True,
        "first_blocker": _agents_last_exam_public_id(
            metadata.get("first_blocker"),
            limit=80,
        ),
    }
    for field, limit in (
        ("id", 160),
        ("digest", 180),
        ("architecture", 40),
        ("os", 40),
        ("created", 80),
        ("last_tag_time", 80),
    ):
        value = _agents_last_exam_public_id(metadata.get(field), limit=limit)
        if value:
            reduced[field] = value
    size_bytes = metadata.get("size_bytes")
    if isinstance(size_bytes, int) and not isinstance(size_bytes, bool):
        reduced["size_bytes"] = size_bytes
    return reduced


def _agents_last_exam_disk_headroom() -> dict[str, Any]:
    usage = shutil.disk_usage(Path.cwd())
    free_gib = usage.free / (1024**3)
    total_gib = usage.total / (1024**3)
    used_pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
    return {
        "free_gib": round(free_gib, 2),
        "total_gib": round(total_gib, 2),
        "used_percent": round(used_pct, 2),
        "path_recorded": False,
    }


def build_agents_last_exam_local_preflight(
    *,
    selected_task_id: str | None = None,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a local ALE adapter preflight without task/body/run execution."""

    task_label = (
        _agents_last_exam_public_id(selected_task_id, limit=160)
        or "metadata_only_candidate"
    )
    primary_raw = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    alternate_raw = (
        alternate_image_metadata
        if isinstance(alternate_image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(alternate_image_ref)
    )
    primary = _agents_last_exam_public_image_metadata(
        primary_raw,
        fallback_image_ref=image_ref,
    )
    alternate = _agents_last_exam_public_image_metadata(
        alternate_raw,
        fallback_image_ref=alternate_image_ref,
    )
    disk = (
        disk_headroom
        if isinstance(disk_headroom, dict)
        else _agents_last_exam_disk_headroom()
    )
    no_cloud = provider_kind == "docker"
    no_upload = True
    required_image_present = primary.get("present") is True
    ready = bool(no_cloud and no_upload and required_image_present)
    if not no_cloud:
        first_blocker = "provider_is_not_local_docker"
    elif not primary.get("probe_available", True):
        first_blocker = primary.get("first_blocker") or "docker_probe_unavailable"
    elif not required_image_present:
        first_blocker = primary.get("first_blocker") or "required_docker_image_missing"
    else:
        first_blocker = "ready_for_local_no_upload_preflight"

    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_PREFLIGHT_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": task_label,
        "snapshot": _agents_last_exam_public_id(snapshot, limit=80)
        or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "provider": {
            "kind": provider_kind,
            "no_cloud": no_cloud,
            "required_image": primary,
            "alternate_image": alternate,
        },
        "disk_headroom": disk,
        "ready": ready,
        "first_blocker": first_blocker,
        "boundary": {
            "local_only": True,
            "no_cloud": no_cloud,
            "no_upload": no_upload,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "local_paths_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_no_upload_adapter_dry_run"
            if ready
            else "repair_preflight_blocker_before_ale_run",
            "minimum_next_evidence": (
                "A no-cloud/no-upload ALE adapter dry-run that confirms local "
                "Docker provider selection and compact ingest boundaries."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "leaderboard evidence",
                "Goal Harness treatment advantage",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }


def build_agents_last_exam_local_dry_run_plan(
    *,
    selected_task_id: str | None = None,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan an ALE local adapter dry-run without running the adapter."""

    preflight_payload = (
        preflight
        if isinstance(preflight, dict)
        else build_agents_last_exam_local_preflight(
            selected_task_id=selected_task_id,
            snapshot=snapshot,
            provider_kind=provider_kind,
            image_ref=image_ref,
            alternate_image_ref=alternate_image_ref,
            image_metadata=image_metadata,
            alternate_image_metadata=alternate_image_metadata,
            disk_headroom=disk_headroom,
        )
    )
    boundary = (
        preflight_payload.get("boundary")
        if isinstance(preflight_payload.get("boundary"), dict)
        else {}
    )
    read_boundary = (
        preflight_payload.get("read_boundary")
        if isinstance(preflight_payload.get("read_boundary"), dict)
        else {}
    )
    forbidden_side_effects = {
        "container_started": False,
        "task_body_read": False,
        "model_api_invoked": False,
        "raw_trajectory_read": False,
        "screenshot_captured": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
        "submit_eligible": False,
        "leaderboard_evidence": False,
    }
    boundary_preserved = (
        boundary.get("local_only") is True
        and boundary.get("no_cloud") is True
        and boundary.get("no_upload") is True
        and all(
            boundary.get(field) is expected
            for field, expected in forbidden_side_effects.items()
        )
        and read_boundary.get("compact_only") is True
        and read_boundary.get("task_text_read") is False
        and read_boundary.get("raw_artifacts_read") is False
        and read_boundary.get("local_paths_recorded") is False
    )
    preflight_ready = preflight_payload.get("ready") is True
    blockers: list[str] = []
    if not preflight_ready:
        blockers.append(
            _agents_last_exam_public_id(
                preflight_payload.get("first_blocker"),
                limit=80,
            )
            or "ale_local_preflight_not_ready"
        )
    if not boundary_preserved:
        blockers.append("ale_local_boundary_not_preserved")
    ready = preflight_ready and boundary_preserved

    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_DRY_RUN_PLAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": preflight_payload.get("task_id") or "metadata_only_candidate",
        "snapshot": preflight_payload.get("snapshot")
        or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "preflight": preflight_payload,
        "ready": ready,
        "first_blocker": blockers[0] if blockers else "ready_for_contract_only_dry_run_plan",
        "blockers": blockers,
        "adapter_plan": {
            "mode": "contract_only_no_execution",
            "provider": "local_docker",
            "will_start_container": False,
            "will_read_task_body": False,
            "will_invoke_model_api": False,
            "will_upload": False,
            "will_submit": False,
            "will_capture_screenshot": False,
            "will_record_credentials": False,
            "will_record_local_paths": False,
            "allowed_probes": [
                "local_docker_image_inspect",
                "disk_headroom_summary",
                "public_task_id_label",
                "compact_boundary_flags",
            ],
            "required_before_real_dry_run": [
                "selected_public_task_id_label",
                "local_docker_provider_confirmed",
                "submit_eligible_false",
                "compact_result_writer_boundary_declared",
                "stop_before_task_body_or_raw_outputs",
            ],
        },
        "paired_run_requirements": {
            "same_task": True,
            "same_model": True,
            "same_sandbox_provider": True,
            "same_timeout": True,
            "same_attempt_count": True,
            "same_grading_path": True,
            "baseline_arm": "hardened-codex",
            "treatment_arm": "codex-goal-harness",
        },
        "claim_boundary": {
            "may_claim": [
                "ALE local adapter dry-run prerequisites are represented as a compact gate",
                "The gate did not start containers, read task bodies, invoke model APIs, upload, or submit",
                "A future real dry-run must preserve the same no-cloud/no-upload boundary",
            ],
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
                "raw trajectory or screenshot evidence",
            ],
        },
        "decision": {
            "next_allowed_action": "run_operator_authorized_no_upload_ale_adapter_dry_run"
            if ready
            else "repair_ale_local_dry_run_plan_blocker",
            "minimum_next_evidence": (
                "A real no-cloud/no-upload adapter dry-run may only proceed if "
                "it preserves the same boundary flags and produces compact "
                "run/eval/events metadata without raw task or trajectory content."
            ),
            "stop_condition": (
                "Stop before task body, hidden references, raw trajectory, "
                "screenshots, credential values, local absolute paths, model "
                "APIs, uploads, submissions, leaderboard claims, paid compute, "
                "or production actions."
            ),
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


def _agents_last_exam_runner_binary_probe(runner_binary: str | None) -> dict[str, Any]:
    binary = _agents_last_exam_public_id(runner_binary, limit=80)
    if not runner_binary:
        return {
            "binary": None,
            "declared": False,
            "available": False,
            "first_blocker": "runner_binary_missing",
            "path_recorded": False,
        }
    if not binary:
        return {
            "binary": None,
            "declared": True,
            "available": False,
            "first_blocker": "runner_binary_not_public_safe",
            "path_recorded": False,
        }
    if "/" in runner_binary or "\\" in runner_binary:
        return {
            "binary": binary,
            "declared": True,
            "available": False,
            "first_blocker": "runner_binary_must_be_name_not_path",
            "path_recorded": False,
        }
    available = shutil.which(runner_binary) is not None
    return {
        "binary": binary,
        "declared": True,
        "available": available,
        "first_blocker": None if available else "runner_binary_not_found",
        "path_recorded": False,
    }


def _agents_last_exam_python_module_probe(
    module_name: str | None,
    *,
    source_root: str | None = None,
) -> dict[str, Any]:
    module = _agents_last_exam_public_id(module_name, limit=100)
    source_root_declared = bool(source_root)
    source_root_available = False
    source_root_path: Path | None = None
    if source_root:
        try:
            source_root_path = Path(source_root).expanduser()
        except (OSError, RuntimeError):
            source_root_path = None
        source_root_available = bool(source_root_path and source_root_path.is_dir())
    if not module_name:
        return {
            "module": None,
            "declared": False,
            "available": False,
            "first_blocker": "runner_python_module_missing",
            "source_root_declared": source_root_declared,
            "source_root_available": source_root_available,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    if source_root_declared and not source_root_available:
        return {
            "module": module,
            "declared": True,
            "available": False,
            "first_blocker": "runner_source_root_missing",
            "source_root_declared": True,
            "source_root_available": False,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    if not module or "/" in module_name or "\\" in module_name:
        return {
            "module": None,
            "declared": True,
            "available": False,
            "first_blocker": "runner_python_module_not_public_safe",
            "source_root_declared": source_root_declared,
            "source_root_available": source_root_available,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    parts = module_name.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        return {
            "module": module,
            "declared": True,
            "available": False,
            "first_blocker": "runner_python_module_not_public_safe",
            "source_root_declared": source_root_declared,
            "source_root_available": source_root_available,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    if source_root_path is not None:
        source_root_text = str(source_root_path)
        sys.path.insert(0, source_root_text)
        importlib.invalidate_caches()
        try:
            available = importlib.util.find_spec(module_name) is not None
        finally:
            try:
                sys.path.remove(source_root_text)
            except ValueError:
                pass
            importlib.invalidate_caches()
    else:
        available = importlib.util.find_spec(module_name) is not None
    return {
        "module": module,
        "declared": True,
        "available": available,
        "first_blocker": None if available else "runner_python_module_not_found",
        "source_root_declared": source_root_declared,
        "source_root_available": source_root_available,
        "source_root_path_recorded": False,
        "path_recorded": False,
    }


def _agents_last_exam_runner_binary_requires_python_module(
    runner_binary: str | None,
) -> bool:
    if not isinstance(runner_binary, str):
        return False
    binary = Path(runner_binary).name.lower()
    return binary == "python" or binary.startswith("python3")


def _agents_last_exam_codex_cli_probe(
    codex_binary: str | None,
    *,
    binary_available: bool | None = None,
    version_text: str | None = None,
) -> dict[str, Any]:
    """Probe host Codex CLI readiness without recording paths or argv."""

    runner_probe = _agents_last_exam_runner_binary_probe(codex_binary)
    unsafe_binary_blockers = {
        "runner_binary_must_be_name_not_path",
        "runner_binary_not_public_safe",
    }
    if (
        binary_available is not None
        and runner_probe.get("declared") is True
        and runner_probe.get("first_blocker") not in unsafe_binary_blockers
    ):
        runner_probe = {
            **runner_probe,
            "available": bool(binary_available),
            "first_blocker": None
            if binary_available
            else (runner_probe.get("first_blocker") or "codex_binary_not_available"),
        }

    version_label = _agents_last_exam_public_id(version_text, limit=120)
    version_probe_available = bool(version_label)
    if (
        version_text is None
        and runner_probe.get("available") is True
        and isinstance(codex_binary, str)
        and codex_binary
        and "/" not in codex_binary
        and "\\" not in codex_binary
    ):
        try:
            result = subprocess.run(
                [codex_binary, "--version"],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
            )
        except Exception:
            result = None
        if result is not None and result.returncode == 0:
            version_label = _agents_last_exam_public_id(
                result.stdout.strip() or result.stderr.strip(),
                limit=120,
            )
            version_probe_available = bool(version_label)

    first_blocker = _agents_last_exam_public_id(
        runner_probe.get("first_blocker"),
        limit=80,
    )
    if runner_probe.get("available") is True and not version_probe_available:
        first_blocker = "codex_version_probe_failed"

    return {
        "binary": runner_probe.get("binary"),
        "binary_declared": runner_probe.get("declared") is True,
        "binary_available": runner_probe.get("available") is True,
        "version": version_label,
        "version_probe_available": version_probe_available,
        "binary_path_recorded": False,
        "command_argv_recorded": False,
        "first_blocker": first_blocker,
    }


def _agents_last_exam_cua_mcp_assets_probe(
    assets_root: str | None,
) -> dict[str, Any]:
    """Check local CUA MCP server assets without recording host paths."""

    if not assets_root:
        return {
            "declared": False,
            "available": False,
            "package_json_present": False,
            "server_entry_present": False,
            "package_lock_present": False,
            "path_recorded": False,
            "first_blocker": "cua_mcp_assets_root_missing",
        }
    try:
        root = Path(assets_root).expanduser()
    except (OSError, RuntimeError):
        root = None
    available = bool(root and root.is_dir())
    package_json_present = bool(root and (root / "package.json").is_file())
    package_lock_present = bool(root and (root / "package-lock.json").is_file())
    server_entry_present = bool(root and (root / "src" / "index.js").is_file())
    if not available:
        first_blocker = "cua_mcp_assets_root_not_available"
    elif not package_json_present:
        first_blocker = "cua_mcp_package_json_missing"
    elif not server_entry_present:
        first_blocker = "cua_mcp_server_entry_missing"
    else:
        first_blocker = None
    return {
        "declared": True,
        "available": available,
        "package_json_present": package_json_present,
        "server_entry_present": server_entry_present,
        "package_lock_present": package_lock_present,
        "path_recorded": False,
        "first_blocker": first_blocker,
    }


def build_agents_last_exam_host_codex_cli_route(
    *,
    codex_binary: str | None = "codex",
    codex_binary_available: bool | None = None,
    codex_version_text: str | None = None,
    host_auth_cache_present: bool | None = None,
    host_config_present: bool | None = None,
    require_host_config: bool = False,
    cua_mcp_assets_root: str | None = None,
    ale_sandbox_cua_smoke_ready: bool = False,
    operator_authorized_host_codex_auth: bool = False,
) -> dict[str, Any]:
    """Gate the ALE host-Codex route before any task-level execution.

    The contract intentionally checks only host-side existence/probe facts. It
    must not read, print, copy, or persist Codex auth material or task content.
    """

    codex_probe = _agents_last_exam_codex_cli_probe(
        codex_binary,
        binary_available=codex_binary_available,
        version_text=codex_version_text,
    )
    auth_present = (
        Path.home().joinpath(".codex", "auth.json").is_file()
        if host_auth_cache_present is None
        else bool(host_auth_cache_present)
    )
    config_present = (
        Path.home().joinpath(".codex", "config.toml").is_file()
        if host_config_present is None
        else bool(host_config_present)
    )
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)

    blockers: list[str] = []
    if operator_authorized_host_codex_auth is not True:
        blockers.append("operator_authorization_missing")
    if codex_probe.get("binary_available") is not True:
        blockers.append(
            _agents_last_exam_public_id(codex_probe.get("first_blocker"), limit=80)
            or "host_codex_binary_not_available"
        )
    if codex_probe.get("version_probe_available") is not True:
        blockers.append("host_codex_version_probe_missing")
    if auth_present is not True:
        blockers.append("host_codex_auth_cache_missing")
    if require_host_config and config_present is not True:
        blockers.append("host_codex_config_missing")
    if assets_probe.get("first_blocker"):
        blockers.append(
            _agents_last_exam_public_id(assets_probe.get("first_blocker"), limit=80)
            or "cua_mcp_assets_not_ready"
        )
    if ale_sandbox_cua_smoke_ready is not True:
        blockers.append("ale_sandbox_cua_smoke_not_ready")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_no_task_host_codex_cua_smoke",
        "blockers": blockers,
        "route": {
            "mode": "host_codex_cli_local_executor",
            "uses_host_codex_cli": True,
            "uses_existing_host_codex_auth": True,
            "runs_codex_inside_ale_sandbox": False,
            "drives_ale_sandbox_via_cua_mcp": True,
            "upstream_sandbox_codex_agent_bypassed": True,
            "upstream_provider_key_path_required": False,
            "next_smoke": "no_task_host_codex_cli_cua_mcp_smoke",
        },
        "host_codex_cli": codex_probe,
        "host_auth": {
            "auth_cache_present": auth_present,
            "config_present": config_present,
            "config_required": require_host_config,
            "auth_values_read": False,
            "config_content_read": False,
            "credential_values_recorded": False,
            "auth_material_copied_to_sandbox": False,
            "whole_codex_dir_copied": False,
            "paths_recorded": False,
        },
        "cua_mcp_assets": assets_probe,
        "ale_sandbox": {
            "cua_smoke_ready": ale_sandbox_cua_smoke_ready is True,
            "container_started_by_this_check": False,
            "sandbox_auth_material_present": False,
            "sandbox_auth_values_read": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_no_task_host_codex_cli_cua_smoke"
            if ready
            else "repair_host_codex_cli_route_blocker",
            "minimum_next_evidence": (
                "A no-task host Codex CLI smoke using a project-local temporary "
                "Codex config and the ALE CUA MCP bridge, with no task prompt, "
                "no credential values, no upload, no submit, and compact result "
                "only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "auth_values_read": False,
            "config_content_read": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


def _agents_last_exam_codex_exec_surface_probe(
    codex_binary: str | None,
) -> dict[str, Any]:
    codex_probe = _agents_last_exam_codex_cli_probe(codex_binary)
    if codex_probe.get("binary_available") is not True:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": codex_probe.get("first_blocker")
            or "host_codex_binary_not_available",
        }
    if not isinstance(codex_binary, str) or "/" in codex_binary or "\\" in codex_binary:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": "host_codex_binary_not_public_safe",
        }
    try:
        result = subprocess.run(
            [codex_binary, "exec", "--help"],
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": "codex_exec_help_probe_failed",
        }
    ok = result.returncode == 0
    return {
        "available": ok,
        "exit_code": result.returncode,
        "stdout_recorded": False,
        "stderr_recorded": False,
        "command_argv_recorded": False,
        "model_invoked": False,
        "first_blocker": None if ok else "codex_exec_help_nonzero",
    }


def _agents_last_exam_codex_mcp_config_probe(
    codex_binary: str | None,
    *,
    cua_mcp_assets_root: str | None,
    cua_server_url: str,
) -> dict[str, Any]:
    codex_probe = _agents_last_exam_codex_cli_probe(codex_binary)
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)
    if codex_probe.get("binary_available") is not True:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": codex_probe.get("first_blocker")
            or "host_codex_binary_not_available",
        }
    if assets_probe.get("first_blocker"):
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": assets_probe.get("first_blocker")
            or "cua_mcp_assets_not_ready",
        }
    if not isinstance(codex_binary, str) or "/" in codex_binary or "\\" in codex_binary:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": "host_codex_binary_not_public_safe",
        }

    try:
        assets_root = Path(str(cua_mcp_assets_root)).expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix="goal-harness-codex-home-") as tmp:
            codex_home = Path(tmp)
            mcp_entry = assets_root / "src" / "index.js"
            config_text = "\n".join(
                [
                    "[mcp_servers.cua]",
                    'command = "node"',
                    f'args = ["{mcp_entry}"]',
                    f'env = {{ CUA_SERVER_URL = "{cua_server_url}" }}',
                    "",
                ]
            )
            (codex_home / "config.toml").write_text(config_text, encoding="utf-8")
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            result = subprocess.run(
                [codex_binary, "mcp", "list", "--json"],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
                env=env,
            )
    except Exception:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": "codex_mcp_config_probe_failed",
        }

    server_detected = False
    server_enabled = False
    transport_type: str | None = None
    if result.returncode == 0:
        try:
            rows = json.loads(result.stdout)
        except json.JSONDecodeError:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict) or row.get("name") != "cua":
                    continue
                server_detected = True
                server_enabled = row.get("enabled") is True
                transport = row.get("transport")
                if isinstance(transport, dict):
                    transport_type = _agents_last_exam_public_id(
                        transport.get("type"),
                        limit=40,
                    )
                break
    if result.returncode != 0:
        first_blocker = "codex_mcp_list_nonzero"
    elif not server_detected:
        first_blocker = "codex_mcp_cua_server_not_detected"
    elif not server_enabled:
        first_blocker = "codex_mcp_cua_server_not_enabled"
    elif transport_type != "stdio":
        first_blocker = "codex_mcp_cua_transport_not_stdio"
    else:
        first_blocker = None
    return {
        "available": first_blocker is None,
        "server_detected": server_detected,
        "server_enabled": server_enabled,
        "transport": transport_type,
        "raw_output_recorded": False,
        "config_path_recorded": False,
        "mcp_server_path_recorded": False,
        "command_argv_recorded": False,
        "auth_values_read": False,
        "first_blocker": first_blocker,
    }


def _agents_last_exam_fake_cua_server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("content-length") or "0")
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                request = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                request = {}
            command = request.get("command")
            if command == "get_screen_size":
                payload = {"success": True, "size": {"width": 1024, "height": 768}}
            elif command == "screenshot":
                payload = {"success": True, "image_data": "iVBORw0KGgo="}
            elif command == "get_cursor_position":
                payload = {"success": True, "position": {"x": 512, "y": 384}}
            else:
                payload = {"success": True}
            data = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _agents_last_exam_cua_mcp_test_probe(
    *,
    cua_mcp_assets_root: str | None,
    install_node_deps: bool = False,
) -> dict[str, Any]:
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)
    if assets_probe.get("first_blocker"):
        return {
            "available": False,
            "node_available": shutil.which("node") is not None,
            "npm_install_attempted": False,
            "fake_cua_server_used": False,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": assets_probe.get("first_blocker")
            or "cua_mcp_assets_not_ready",
        }
    if not shutil.which("node"):
        return {
            "available": False,
            "node_available": False,
            "npm_install_attempted": False,
            "fake_cua_server_used": False,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": "node_cli_missing",
        }

    server = None
    try:
        with tempfile.TemporaryDirectory(prefix="goal-harness-cua-mcp-") as tmp:
            work_root = Path(tmp) / "cua_mcp_server"
            shutil.copytree(str(cua_mcp_assets_root), work_root)
            node_modules = work_root / "node_modules"
            npm_install_attempted = False
            if not node_modules.is_dir():
                if not install_node_deps:
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": False,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "cua_mcp_node_modules_missing",
                    }
                if not shutil.which("npm"):
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": False,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "npm_cli_missing",
                    }
                npm_install_attempted = True
                npm_result = subprocess.run(
                    ["npm", "install", "--production", "--silent"],
                    cwd=work_root,
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=120,
                )
                if npm_result.returncode != 0:
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": True,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "cua_mcp_npm_install_failed",
                    }
            server = _agents_last_exam_fake_cua_server()
            port = server.server_address[1]
            env = os.environ.copy()
            env["CUA_SERVER_URL"] = f"http://127.0.0.1:{port}"
            test_result = subprocess.run(
                ["node", "src/index.js", "--test"],
                cwd=work_root,
                check=False,
                text=True,
                capture_output=True,
                timeout=60,
                env=env,
            )
    except Exception:
        return {
            "available": False,
            "node_available": shutil.which("node") is not None,
            "npm_install_attempted": install_node_deps,
            "fake_cua_server_used": server is not None,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": "cua_mcp_test_probe_failed",
        }
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    ok = test_result.returncode == 0
    return {
        "available": ok,
        "node_available": True,
        "npm_install_attempted": npm_install_attempted,
        "fake_cua_server_used": True,
        "raw_output_recorded": False,
        "command_argv_recorded": False,
        "local_paths_recorded": False,
        "first_blocker": None if ok else "cua_mcp_test_nonzero",
    }


def build_agents_last_exam_host_codex_cua_no_task_smoke(
    *,
    route_gate: dict[str, Any],
    codex_exec_probe: dict[str, Any],
    mcp_config_probe: dict[str, Any],
    cua_mcp_test_probe: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if route_gate.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(route_gate.get("first_blocker"), limit=80)
            or "host_codex_route_gate_not_ready"
        )
    for probe_name, probe in (
        ("codex_exec_surface", codex_exec_probe),
        ("codex_mcp_config", mcp_config_probe),
        ("cua_mcp_bridge", cua_mcp_test_probe),
    ):
        if probe.get("available") is not True:
            blockers.append(
                _agents_last_exam_public_id(probe.get("first_blocker"), limit=80)
                or f"{probe_name}_not_ready"
            )
    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_task_level_ale_codex_dry_run_gate",
        "blockers": blockers,
        "route_gate_ready": route_gate.get("ready") is True,
        "route_gate": route_gate,
        "codex_exec_surface": codex_exec_probe,
        "codex_mcp_config": mcp_config_probe,
        "cua_mcp_bridge": cua_mcp_test_probe,
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_operator_authorized_task_level_ale_codex_dry_run"
            if ready
            else "repair_no_task_host_codex_cua_smoke_blocker",
            "minimum_next_evidence": (
                "An operator-authorized task-level ALE dry-run may proceed only "
                "after compact route, Codex exec surface, Codex MCP config, and "
                "CUA MCP bridge probes are ready."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "auth_values_read": False,
            "config_content_read": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


def build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
    *,
    codex_binary: str | None = "codex",
    codex_binary_available: bool | None = None,
    codex_version_text: str | None = None,
    host_auth_cache_present: bool | None = None,
    host_config_present: bool | None = None,
    require_host_config: bool = False,
    cua_mcp_assets_root: str | None = None,
    cua_server_url: str = "http://127.0.0.1:8000",
    install_node_deps: bool = False,
    ale_sandbox_cua_smoke_ready: bool = False,
    operator_authorized_host_codex_auth: bool = False,
) -> dict[str, Any]:
    """Build compact no-task host Codex/CUA readiness evidence.

    This is deliberately a pre-task probe: it checks CLI/help, Codex MCP config
    loading, and the local CUA MCP bridge without sending a Codex prompt,
    reading task material, or recording auth/path/raw-output details.
    """

    route_gate = build_agents_last_exam_host_codex_cli_route(
        codex_binary=codex_binary,
        codex_binary_available=codex_binary_available,
        codex_version_text=codex_version_text,
        host_auth_cache_present=host_auth_cache_present,
        host_config_present=host_config_present,
        require_host_config=require_host_config,
        cua_mcp_assets_root=cua_mcp_assets_root,
        ale_sandbox_cua_smoke_ready=ale_sandbox_cua_smoke_ready,
        operator_authorized_host_codex_auth=operator_authorized_host_codex_auth,
    )
    codex_exec_probe = _agents_last_exam_codex_exec_surface_probe(codex_binary)
    mcp_config_probe = _agents_last_exam_codex_mcp_config_probe(
        codex_binary,
        cua_mcp_assets_root=cua_mcp_assets_root,
        cua_server_url=cua_server_url,
    )
    cua_mcp_test_probe = _agents_last_exam_cua_mcp_test_probe(
        cua_mcp_assets_root=cua_mcp_assets_root,
        install_node_deps=install_node_deps,
    )
    return build_agents_last_exam_host_codex_cua_no_task_smoke(
        route_gate=route_gate,
        codex_exec_probe=codex_exec_probe,
        mcp_config_probe=mcp_config_probe,
        cua_mcp_test_probe=cua_mcp_test_probe,
    )


def _agents_last_exam_boundary_flag(
    payload: dict[str, Any],
    key: str,
    *,
    default: bool = False,
) -> bool:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    return bool(boundary.get(key, default))


def _agents_last_exam_ready_input(
    payload: dict[str, Any],
    *,
    schema_version: str,
    blocker_prefix: str,
) -> tuple[bool, str | None]:
    if not isinstance(payload, dict):
        return False, f"{blocker_prefix}_missing"
    if payload.get("schema_version") != schema_version:
        return False, f"{blocker_prefix}_schema_mismatch"
    if payload.get("ready") is not True:
        first_blocker = _agents_last_exam_public_id(
            payload.get("first_blocker"),
            limit=80,
        )
        return False, first_blocker or f"{blocker_prefix}_not_ready"
    return True, None


def _agents_last_exam_source_freshness_input(
    launch_packet: dict[str, Any] | None,
    *,
    required: bool,
) -> tuple[bool | None, str | None]:
    if not required:
        return None, None
    if not isinstance(launch_packet, dict):
        return False, "fresh_source_launch_packet_missing"
    source_lock = launch_packet.get("source_lock")
    if not isinstance(source_lock, dict):
        return False, "ale_source_freshness_not_verified"
    if source_lock.get("fetch_origin_attempted") is not True:
        return False, "ale_source_fetch_origin_not_attempted"
    if source_lock.get("fetch_origin_ok") is not True:
        return False, "ale_source_fetch_origin_failed"
    if source_lock.get("require_upstream_current") is not True:
        return False, "ale_source_upstream_current_not_required"
    if source_lock.get("upstream_declared") is not True:
        return False, "ale_source_upstream_missing"
    if source_lock.get("head_matches_upstream") is not True:
        return False, "ale_source_not_at_upstream_head"
    if source_lock.get("upstream_ahead_count") != 0:
        return False, "ale_source_upstream_ahead_count_nonzero"
    if source_lock.get("upstream_behind_count") != 0:
        return False, "ale_source_upstream_behind_count_nonzero"
    return True, None


def _agents_last_exam_case_state_init_contract_input(
    launch_packet: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if not isinstance(launch_packet, dict):
        return False, "launch_packet_missing_for_case_state_init_contract"
    contract = launch_packet.get("case_state_init_contract")
    if not isinstance(contract, dict):
        return False, "case_state_init_contract_missing"
    if contract.get("schema_version") != BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION:
        return False, "case_state_init_contract_schema_mismatch"
    if contract.get("benchmark_case_goal_id") != AGENTS_LAST_EXAM_CASE_GOAL_ID:
        return False, "case_state_init_contract_goal_id_mismatch"
    if contract.get("case_state_path") != AGENTS_LAST_EXAM_CASE_STATE_PATH:
        return False, "case_state_init_contract_path_mismatch"
    if contract.get("init_required_before_worker") is not True:
        return False, "case_state_init_not_required_before_worker"
    if contract.get("initialized_by_launch_packet") is not False:
        return False, "case_state_initialized_by_no_execution_packet"
    if contract.get("surrogate_state_files_allowed") is not False:
        return False, "case_state_surrogate_files_allowed"
    if contract.get("raw_task_text_required_for_init") is not False:
        return False, "case_state_init_requires_raw_task_text"
    if contract.get("local_paths_recorded") is not False:
        return False, "case_state_init_contract_local_paths_recorded"
    proof_fields = contract.get("proof_fields")
    required_fields = set(BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS)
    if not isinstance(proof_fields, list) or not required_fields.issubset(
        {str(field) for field in proof_fields}
    ):
        return False, "case_state_init_contract_proof_fields_incomplete"
    return True, None


def build_agents_last_exam_validation_run_gate(
    *,
    selected_task_id: str | None,
    validation_hypothesis: str | None,
    task_material_readiness: dict[str, Any],
    host_codex_no_task_e2e: dict[str, Any],
    exact_dry_run_result: dict[str, Any],
    launch_packet: dict[str, Any] | None = None,
    result_reducer_ready: bool = False,
    no_upload: bool = True,
    submit_enabled: bool = False,
    leaderboard_enabled: bool = False,
    formal_score_candidate: bool = False,
    require_fresh_source: bool = False,
    expected_formal_agent: str = "host_codex_gpt55_xhigh",
) -> dict[str, Any]:
    """Combine compact ALE readiness into a pre-run decision gate."""

    task_label = _agents_last_exam_public_id(selected_task_id, limit=180)
    hypothesis_label = _agents_last_exam_public_id(validation_hypothesis, limit=240)
    fresh_source_required = bool(formal_score_candidate or require_fresh_source)
    blockers: list[str] = []
    for payload, schema_version, prefix in (
        (
            task_material_readiness,
            AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
            "task_material_readiness",
        ),
        (
            host_codex_no_task_e2e,
            AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
            "host_codex_no_task_e2e",
        ),
        (
            exact_dry_run_result,
            AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION,
            "exact_dry_run_result",
        ),
    ):
        ready, blocker = _agents_last_exam_ready_input(
            payload,
            schema_version=schema_version,
            blocker_prefix=prefix,
        )
        if not ready and blocker:
            blockers.append(blocker)

    launch_packet_ready = None
    if launch_packet is not None:
        ready, blocker = _agents_last_exam_ready_input(
            launch_packet,
            schema_version=AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION,
            blocker_prefix="launch_packet",
        )
        launch_packet_ready = ready
        if not ready and blocker:
            blockers.append(blocker)

    fresh_source_ready, fresh_source_blocker = _agents_last_exam_source_freshness_input(
        launch_packet,
        required=fresh_source_required,
    )
    if fresh_source_blocker:
        blockers.append(fresh_source_blocker)
    case_state_contract_ready, case_state_contract_blocker = (
        _agents_last_exam_case_state_init_contract_input(launch_packet)
    )
    if case_state_contract_blocker:
        blockers.append(case_state_contract_blocker)

    if not hypothesis_label:
        blockers.append("validation_hypothesis_missing")
    if result_reducer_ready is not True:
        blockers.append("compact_result_reducer_not_ready")
    if no_upload is not True:
        blockers.append("no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("submit_must_remain_disabled")
    if leaderboard_enabled:
        blockers.append("leaderboard_must_remain_disabled")

    boundary_payloads = [
        ("task_material_readiness", task_material_readiness),
        ("host_codex_no_task_e2e", host_codex_no_task_e2e),
        ("exact_dry_run_result", exact_dry_run_result),
    ]
    if launch_packet is not None:
        boundary_payloads.append(("launch_packet", launch_packet))
    for name, payload in boundary_payloads:
        if _agents_last_exam_boundary_flag(payload, "credential_values_recorded"):
            blockers.append(f"{name}_credential_values_recorded")
        if _agents_last_exam_boundary_flag(payload, "local_paths_recorded"):
            blockers.append(f"{name}_local_paths_recorded")
        if _agents_last_exam_boundary_flag(payload, "raw_trajectory_read"):
            blockers.append(f"{name}_raw_trajectory_read")
        if _agents_last_exam_boundary_flag(payload, "task_body_read"):
            blockers.append(f"{name}_task_body_read")
        if _agents_last_exam_boundary_flag(payload, "screenshot_captured"):
            blockers.append(f"{name}_screenshot_captured")
        if _agents_last_exam_boundary_flag(payload, "hidden_references_allowed"):
            blockers.append(f"{name}_hidden_refs_allowed")
        if _agents_last_exam_boundary_flag(payload, "production_actions_allowed"):
            blockers.append(f"{name}_production_actions_allowed")

    expected = (
        exact_dry_run_result.get("expected")
        if isinstance(exact_dry_run_result.get("expected"), dict)
        else {}
    )
    expected_task = expected.get("task") if isinstance(expected, dict) else None
    if task_label and expected_task and task_label != expected_task:
        blockers.append("selected_task_mismatch_exact_dry_run")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_operator_authorized_local_no_upload_ale_validation_run",
        "blockers": blockers,
        "selected_task": {
            "task_id": task_label,
            "source": "compact_readiness_artifacts",
        },
        "validation_hypothesis": hypothesis_label,
        "readiness_inputs": {
            "task_material_ready": task_material_readiness.get("ready") is True,
            "host_codex_no_task_e2e_ready": host_codex_no_task_e2e.get("ready") is True,
            "exact_dry_run_ready": exact_dry_run_result.get("ready") is True,
            "launch_packet_ready": launch_packet_ready,
            "fresh_source_required": fresh_source_required,
            "fresh_source_ready": fresh_source_ready,
            "case_state_init_contract_ready": case_state_contract_ready,
            "compact_result_reducer_ready": result_reducer_ready is True,
        },
        "model_policy": {
            "connectivity_e2e_model": "gpt-5.3-codex-spark",
            "formal_score_agent": expected_formal_agent,
            "formal_score_candidate": bool(formal_score_candidate),
        },
        "run_boundary": {
            "local_only": True,
            "no_upload": no_upload is True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "operator_authorization_required_before_task_run": True,
            "case_state_init_required_before_worker": True,
            "case_state_initialized_by_this_gate": False,
            "case_state_path": AGENTS_LAST_EXAM_CASE_STATE_PATH,
            "case_state_schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
            "task_run_started_by_this_gate": False,
            "container_started_by_this_gate": False,
            "model_api_invoked_by_this_gate": False,
            "codex_prompt_sent_by_this_gate": False,
            "raw_trajectory_read": False,
            "task_body_read_by_goal_harness": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "operator_authorized_local_no_upload_ale_validation_run"
            if ready
            else "repair_ale_validation_run_gate_blocker",
            "minimum_next_evidence": (
                "A task-level ALE run may proceed only as local/no-upload/no-submit "
                "work with compact result reduction through the ALE reducer, and "
                "with a concrete Goal Harness validation hypothesis recorded."
            ),
            "must_not_claim": [
                "ALE task success before compact result ingest",
                "ALE score uplift before paired evidence",
                "Goal Harness treatment advantage before paired evidence",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
        },
    }


def _agents_last_exam_normalized_repo_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith(".git"):
        text = text[:-4]
    text = text.replace("git@github.com:", "https://github.com/")
    text = text.replace("http://github.com/", "https://github.com/")
    return _agents_last_exam_public_id(text, limit=180)


def _agents_last_exam_source_git_metadata(
    source_root: str | None,
    *,
    expected_repo_url: str = AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    fetch_origin: bool = False,
) -> dict[str, Any]:
    expected = _agents_last_exam_normalized_repo_label(expected_repo_url)
    source_root_declared = bool(source_root)
    source_root_path: Path | None = None
    if source_root:
        try:
            source_root_path = Path(source_root).expanduser()
        except (OSError, RuntimeError):
            source_root_path = None
    source_root_available = bool(source_root_path and source_root_path.is_dir())
    base = {
        "source_root_declared": source_root_declared,
        "source_root_available": source_root_available,
        "source_root_path_recorded": False,
        "expected_repo": expected,
        "remote": None,
        "remote_matches_expected": False,
        "head": None,
        "upstream_ref": None,
        "upstream_head": None,
        "upstream_declared": False,
        "head_matches_upstream": False,
        "upstream_ahead_count": None,
        "upstream_behind_count": None,
        "fetch_origin_attempted": False,
        "fetch_origin_ok": False,
        "git_probe_available": shutil.which("git") is not None,
        "is_git_checkout": False,
    }
    if not source_root_declared:
        return {**base, "first_blocker": "source_root_missing"}
    if not source_root_available or source_root_path is None:
        return {**base, "first_blocker": "source_root_not_available"}
    if not shutil.which("git"):
        return {**base, "first_blocker": "git_cli_missing"}

    def git_output(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_root_path), *args],
                check=False,
                text=True,
                capture_output=True,
                timeout=10,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def git_run(*args: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_root_path), *args],
                check=False,
                text=True,
                capture_output=True,
                timeout=30,
            )
        except Exception:
            return False
        return result.returncode == 0

    fetch_origin_attempted = bool(fetch_origin)
    fetch_origin_ok = git_run("fetch", "--prune", "origin") if fetch_origin else False

    top_level = git_output("rev-parse", "--show-toplevel")
    is_git_checkout = bool(top_level)
    remote = _agents_last_exam_normalized_repo_label(
        git_output("remote", "get-url", "origin")
    )
    head = _agents_last_exam_public_id(git_output("rev-parse", "HEAD"), limit=80)
    upstream_ref = _agents_last_exam_public_id(
        git_output("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"),
        limit=120,
    )
    upstream_head = _agents_last_exam_public_id(
        git_output("rev-parse", "@{upstream}"),
        limit=80,
    )
    upstream_ahead_count: int | None = None
    upstream_behind_count: int | None = None
    rev_counts = git_output("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if rev_counts:
        parts = rev_counts.split()
        if len(parts) >= 2:
            try:
                upstream_ahead_count = int(parts[0])
                upstream_behind_count = int(parts[1])
            except ValueError:
                upstream_ahead_count = None
                upstream_behind_count = None
    metadata = {
        **base,
        "remote": remote,
        "remote_matches_expected": bool(remote and expected and remote == expected),
        "head": head,
        "upstream_ref": upstream_ref,
        "upstream_head": upstream_head,
        "upstream_declared": bool(upstream_ref),
        "head_matches_upstream": bool(head and upstream_head and head == upstream_head),
        "upstream_ahead_count": upstream_ahead_count,
        "upstream_behind_count": upstream_behind_count,
        "fetch_origin_attempted": fetch_origin_attempted,
        "fetch_origin_ok": fetch_origin_ok,
        "is_git_checkout": is_git_checkout,
    }
    if not is_git_checkout:
        return {**metadata, "first_blocker": "source_root_not_git_checkout"}
    if not remote:
        return {**metadata, "first_blocker": "source_root_origin_missing"}
    if expected and remote != expected:
        return {**metadata, "first_blocker": "source_root_origin_mismatch"}
    if fetch_origin and not fetch_origin_ok:
        return {**metadata, "first_blocker": "source_root_fetch_origin_failed"}
    if not head:
        return {**metadata, "first_blocker": "source_root_head_missing"}
    return {**metadata, "first_blocker": None}


def build_agents_last_exam_local_source_readiness(
    *,
    source_root: str | None,
    expected_repo_url: str = AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    runner_python_module: str = "ale_run",
    fetch_origin: bool = False,
    require_upstream_current: bool = False,
) -> dict[str, Any]:
    """Verify a redacted public ALE source checkout contract without running ALE."""

    git_metadata = _agents_last_exam_source_git_metadata(
        source_root,
        expected_repo_url=expected_repo_url,
        fetch_origin=fetch_origin,
    )
    module_probe = _agents_last_exam_python_module_probe(
        runner_python_module,
        source_root=source_root,
    )
    blockers: list[str] = []
    if git_metadata.get("first_blocker"):
        blockers.append(str(git_metadata["first_blocker"]))
    if require_upstream_current:
        if git_metadata.get("upstream_declared") is not True:
            blockers.append("source_root_upstream_missing")
        elif git_metadata.get("head_matches_upstream") is not True:
            behind = git_metadata.get("upstream_behind_count")
            ahead = git_metadata.get("upstream_ahead_count")
            if isinstance(behind, int) and behind > 0:
                blockers.append("source_root_behind_upstream")
            elif isinstance(ahead, int) and ahead > 0:
                blockers.append("source_root_ahead_of_upstream")
            else:
                blockers.append("source_root_not_at_upstream_head")
    if module_probe.get("available") is not True:
        blockers.append(
            _agents_last_exam_public_id(module_probe.get("first_blocker"), limit=80)
            or "runner_python_module_not_available"
        )
    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_SOURCE_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_redacted_ale_source_lock",
        "blockers": blockers,
        "source": {
            "kind": "git_source_root",
            "expected_repo": git_metadata.get("expected_repo"),
            "remote": git_metadata.get("remote"),
            "remote_matches_expected": git_metadata.get("remote_matches_expected")
            is True,
            "head": git_metadata.get("head"),
            "upstream_ref": git_metadata.get("upstream_ref"),
            "upstream_head": git_metadata.get("upstream_head"),
            "upstream_declared": git_metadata.get("upstream_declared") is True,
            "head_matches_upstream": git_metadata.get("head_matches_upstream")
            is True,
            "upstream_ahead_count": git_metadata.get("upstream_ahead_count"),
            "upstream_behind_count": git_metadata.get("upstream_behind_count"),
            "fetch_origin_attempted": git_metadata.get("fetch_origin_attempted")
            is True,
            "fetch_origin_ok": git_metadata.get("fetch_origin_ok") is True,
            "require_upstream_current": bool(require_upstream_current),
            "git_probe_available": git_metadata.get("git_probe_available") is True,
            "is_git_checkout": git_metadata.get("is_git_checkout") is True,
            "source_root_declared": git_metadata.get("source_root_declared") is True,
            "source_root_available": git_metadata.get("source_root_available") is True,
            "source_root_path_recorded": False,
        },
        "runner_probe": {
            "python_module": module_probe.get("module"),
            "python_module_declared": module_probe.get("declared") is True,
            "python_module_available": module_probe.get("available") is True,
            "python_module_path_recorded": False,
            "source_root_path_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "use_redacted_source_lock_for_runner_readiness"
            if ready
            else "repair_public_ale_source_lock_before_runner_execution",
            "minimum_next_evidence": (
                "A durable public ALE checkout with matching origin, commit, and "
                "importable runner module, followed by no-upload runner readiness."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


def _agents_last_exam_public_task_parts(task_id: str | None) -> tuple[list[str], str | None]:
    label = _agents_last_exam_public_id(task_id, limit=180)
    if not isinstance(task_id, str) or not task_id.strip():
        return [], label
    text = task_id.strip().replace("\\", "/")
    parts = [part for part in text.split("/") if part]
    safe = (
        not text.startswith("/")
        and not text.startswith("~")
        and len(parts) == 2
        and all(part not in {".", ".."} for part in parts)
        and all(_agents_last_exam_public_id(part, limit=120) == part for part in parts)
    )
    return (parts if safe else []), label


def _agents_last_exam_public_task_list_membership(
    source_root: str | None,
    task_id: str | None,
    selected_task_lists: Iterable[str],
) -> dict[str, Any]:
    safe_task_id = str(task_id or "").strip().replace("\\", "/")
    memberships: dict[str, bool] = {}
    checked = 0
    present = 0
    if not source_root:
        return {
            "checked": False,
            "selected_task_lists": [],
            "membership": memberships,
            "present_count": present,
            "path_recorded": False,
        }
    try:
        root = Path(source_root).expanduser()
        selected_root = root / "selected_tasks"
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "selected_task_lists": [],
            "membership": memberships,
            "present_count": present,
            "path_recorded": False,
        }
    safe_lists: list[str] = []
    for raw_name in selected_task_lists:
        label = _agents_last_exam_public_id(raw_name, limit=120)
        if not label:
            continue
        parts = [part for part in str(raw_name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            continue
        candidate = selected_root.joinpath(*parts)
        try:
            resolved_candidate = candidate.resolve()
            inside_root = resolved_candidate == resolved_root or (
                resolved_root in resolved_candidate.parents
            )
        except OSError:
            inside_root = False
        safe_lists.append(label)
        if not inside_root or not candidate.is_file():
            memberships[label] = False
            continue
        checked += 1
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            memberships[label] = False
            continue
        matched = any(line.strip().replace("\\", "/") == safe_task_id for line in lines)
        memberships[label] = matched
        if matched:
            present += 1
    return {
        "checked": checked > 0,
        "selected_task_lists": safe_lists,
        "membership": memberships,
        "present_count": present,
        "path_recorded": False,
    }


def _agents_last_exam_bool_requirement(value: bool | str | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "required", "requires_task_data"}:
        return True
    if normalized in {"0", "false", "no", "not_required", "none"}:
        return False
    return None


def build_agents_last_exam_baked_task_input_readiness(
    *,
    selected_task_id: str | None,
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    docker_binary: str = "docker",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Probe whether an ALE Docker image contains a task baked input dir.

    This starts a tiny shell in the image to test directory existence/readability.
    It does not run the task, list files, read task data, or record the checked path.
    """

    parts, task_label = _agents_last_exam_public_task_parts(selected_task_id)
    blockers: list[str] = []
    if not parts:
        blockers.append("selected_task_id_not_public_safe")
    docker_label = _agents_last_exam_public_id(docker_binary, limit=80)
    docker_binary_safe = bool(
        docker_label
        and docker_binary == docker_label
        and "/" not in docker_binary
        and "\\" not in docker_binary
    )
    if not docker_binary_safe:
        blockers.append("docker_binary_must_be_name_not_path")
    docker_available = bool(docker_binary_safe and shutil.which(docker_binary))
    if docker_binary_safe and not docker_available:
        blockers.append("docker_cli_missing")

    raw_image_metadata = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    image = _agents_last_exam_public_image_metadata(
        raw_image_metadata,
        fallback_image_ref=image_ref,
    )
    if image.get("present") is not True:
        blockers.append(
            _agents_last_exam_public_id(image.get("first_blocker"), limit=80)
            or "docker_image_missing"
        )

    attempted = False
    container_started = False
    baked_input_present = False
    baked_input_readable = False
    probe_return_code: int | None = None
    probe_error: str | None = None
    if not blockers and parts and docker_binary_safe:
        baked_input_path = (
            f"/media/user/data/agenthle/{parts[0]}/{parts[1]}/base/input"
        )
        attempted = True
        try:
            result = subprocess.run(
                [
                    docker_binary,
                    "run",
                    "--rm",
                    "--entrypoint",
                    "/bin/sh",
                    image_ref,
                    "-c",
                    'test -d "$1" && test -r "$1"',
                    "sh",
                    baked_input_path,
                ],
                check=False,
                text=True,
                capture_output=True,
                timeout=max(1, int(timeout_seconds)),
            )
        except subprocess.TimeoutExpired:
            probe_error = "baked_task_input_probe_timeout"
        except Exception:
            probe_error = "baked_task_input_probe_failed"
        else:
            container_started = True
            probe_return_code = result.returncode
            if result.returncode == 0:
                baked_input_present = True
                baked_input_readable = True
            else:
                probe_error = "baked_task_input_missing"
    if probe_error:
        blockers.append(probe_error)

    ready = not blockers and baked_input_present and baked_input_readable
    return {
        "schema_version": AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_baked_sandbox_task_data_source",
        "blockers": blockers,
        "task": {
            "task_id": task_label,
            "category": parts[0] if parts else None,
            "name": parts[1] if parts else None,
        },
        "image": image,
        "probe": {
            "kind": "docker_shell_test_directory_only",
            "attempted": attempted,
            "container_started": container_started,
            "baked_input_present": baked_input_present,
            "baked_input_readable": baked_input_readable,
            "return_code_zero": probe_return_code == 0
            if probe_return_code is not None
            else None,
            "expected_path_template": "ale_task_base_input",
            "expected_path_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": container_started,
            "task_run_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "directory_listed": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "read_boundary": {
            "compact_only": True,
            "path_existence_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }


def build_agents_last_exam_baked_task_input_scan(
    *,
    source_root: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    docker_binary: str = "docker",
    max_tasks: int = 120,
    timeout_seconds: int = 180,
    probe_results: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Scan selected public ALE tasks for baked input dirs without reading them."""

    selected = _agents_last_exam_public_selected_task_scan(
        source_root,
        selected_task_lists,
    )
    task_ids = [
        task_id
        for task_id in selected.get("task_ids", [])
        if _agents_last_exam_public_task_parts(task_id)[0]
    ]
    max_count = max(0, int(max_tasks))
    if max_count:
        task_ids = task_ids[:max_count]
    else:
        task_ids = []
    blockers: list[str] = []
    if selected.get("checked") is not True:
        blockers.append("selected_task_lists_not_checked")
    if not task_ids:
        blockers.append("no_selected_tasks_to_probe")

    docker_label = _agents_last_exam_public_id(docker_binary, limit=80)
    docker_binary_safe = bool(
        docker_label
        and docker_binary == docker_label
        and "/" not in docker_binary
        and "\\" not in docker_binary
    )
    if not docker_binary_safe:
        blockers.append("docker_binary_must_be_name_not_path")
    docker_available = bool(docker_binary_safe and shutil.which(docker_binary))
    raw_image_metadata = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    image = _agents_last_exam_public_image_metadata(
        raw_image_metadata,
        fallback_image_ref=image_ref,
    )

    fixture_probe_used = isinstance(probe_results, dict)
    if not fixture_probe_used:
        if docker_binary_safe and not docker_available:
            blockers.append("docker_cli_missing")
        if image.get("present") is not True:
            blockers.append(
                _agents_last_exam_public_id(image.get("first_blocker"), limit=80)
                or "docker_image_missing"
            )

    attempted = False
    container_started = False
    candidates: list[str] = []
    probe_error: str | None = None
    if not blockers and task_ids:
        attempted = True
        if fixture_probe_used:
            for task_id in task_ids:
                if probe_results.get(task_id) is True:
                    candidates.append(task_id)
        else:
            script = (
                'while IFS= read -r task; do '
                'category="${task%%/*}"; name="${task#*/}"; '
                'path="/media/user/data/agenthle/${category}/${name}/base/input"; '
                'if test -d "$path" && test -r "$path"; then '
                'printf "%s\\t1\\n" "$task"; else printf "%s\\t0\\n" "$task"; fi; '
                "done"
            )
            try:
                result = subprocess.run(
                    [
                        docker_binary,
                        "run",
                        "--rm",
                        "--entrypoint",
                        "/bin/sh",
                        image_ref,
                        "-c",
                        script,
                    ],
                    input="\n".join(task_ids) + "\n",
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=max(1, int(timeout_seconds)),
                )
            except subprocess.TimeoutExpired:
                probe_error = "baked_task_input_scan_timeout"
            except Exception:
                probe_error = "baked_task_input_scan_failed"
            else:
                container_started = True
                if result.returncode != 0:
                    probe_error = "baked_task_input_scan_nonzero"
                else:
                    safe_task_set = set(task_ids)
                    for line in result.stdout.splitlines():
                        raw_task_id, _, flag = line.partition("\t")
                        if flag != "1" or raw_task_id not in safe_task_set:
                            continue
                        parts, safe_label = _agents_last_exam_public_task_parts(
                            raw_task_id
                        )
                        if parts and safe_label:
                            candidates.append(raw_task_id)
    if probe_error:
        blockers.append(probe_error)
    if attempted and not candidates and not blockers:
        blockers.append("no_baked_input_candidate_found")

    ready = bool(candidates) and not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_baked_input_formal_candidate_selection",
        "blockers": blockers,
        "selected_tasks": {
            "checked": selected.get("checked") is True,
            "selected_task_lists": selected.get("selected_task_lists") or [],
            "selected_task_count": selected.get("selected_task_count"),
            "probed_task_count": len(task_ids),
            "max_tasks": max_count,
            "path_recorded": False,
        },
        "image": image,
        "probe": {
            "kind": "docker_shell_batch_test_directory_only",
            "attempted": attempted,
            "container_started": container_started,
            "fixture_probe_used": fixture_probe_used,
            "baked_input_candidate_count": len(candidates),
            "expected_path_template": "ale_task_base_input",
            "expected_path_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
        },
        "candidates": {
            "eligible_baked_input_candidates": candidates[:25],
            "candidate_count": len(candidates),
            "task_ids_public": True,
            "task_paths_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": container_started,
            "task_run_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "directory_listed": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "read_boundary": {
            "compact_only": True,
            "path_existence_only": True,
            "selected_task_lists_read": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }


def _agents_last_exam_task_data_source_readiness(
    *,
    requires_task_data: bool | str | None,
    task_data_source: str | None,
    baked_task_input_present: bool | None,
    baked_task_input_readiness: dict[str, Any] | None,
    gcs_sa_key: str | None,
    gcs_sa_key_present: bool | None,
    enforce_task_data_source: bool,
) -> dict[str, Any]:
    requirement = _agents_last_exam_bool_requirement(requires_task_data)
    raw_source = task_data_source.strip() if isinstance(task_data_source, str) else ""
    source = _agents_last_exam_public_id(raw_source, limit=120)
    official_gcs_source = raw_source.startswith("gs://ale-data-public")
    gcs_key_declared = bool(gcs_sa_key)
    gcs_key_file_present = False
    if gcs_sa_key:
        try:
            gcs_key_file_present = Path(gcs_sa_key).expanduser().is_file()
        except (OSError, RuntimeError):
            gcs_key_file_present = False
    effective_gcs_key_present = (
        bool(gcs_sa_key_present)
        if gcs_sa_key_present is not None
        else gcs_key_file_present
    )
    baked_probe_declared = isinstance(baked_task_input_readiness, dict)
    baked_probe_ready = (
        baked_task_input_readiness.get("schema_version")
        == AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION
        and baked_task_input_readiness.get("ready") is True
        if baked_probe_declared
        else False
    )
    effective_baked_input_present = (
        bool(baked_task_input_present)
        if baked_task_input_present is not None
        else baked_probe_ready
    )
    checked = enforce_task_data_source or requirement is not None or bool(source)
    blockers: list[str] = []
    if checked and requirement is None:
        blockers.append("task_data_requirement_unknown")
    if requirement is True:
        if not source:
            blockers.append("task_data_source_missing_for_required_task")
        elif raw_source == "baked_in_sandbox":
            if baked_probe_declared and baked_probe_ready is not True:
                blockers.append(
                    _agents_last_exam_public_id(
                        baked_task_input_readiness.get("first_blocker"),
                        limit=80,
                    )
                    or "baked_task_input_not_verified"
                )
            elif effective_baked_input_present is not True:
                blockers.append("baked_task_input_not_verified")
        elif official_gcs_source:
            if effective_gcs_key_present is not True:
                blockers.append("gcs_sa_key_presence_not_verified")
        elif raw_source in {"none", "local"}:
            blockers.append("task_data_source_not_sufficient_for_required_task")
        else:
            blockers.append("task_data_source_unsupported_for_required_task")
    ready = checked and not blockers
    if requirement is False:
        ready = True
    return {
        "checked": checked,
        "ready": ready,
        "first_blocker": blockers[0] if blockers else None,
        "blockers": blockers,
        "requires_task_data": requirement,
        "requires_task_data_declared": requirement is not None,
        "task_data_source": source,
        "task_data_source_declared": bool(source),
        "official_gcs_source": official_gcs_source,
        "baked_input_present": effective_baked_input_present is True,
        "baked_input_presence_declared": baked_task_input_present is not None
        or baked_probe_declared,
        "baked_input_probe_declared": baked_probe_declared,
        "baked_input_probe_ready": baked_probe_ready,
        "gcs_sa_key_declared": gcs_key_declared or gcs_sa_key_present is not None,
        "gcs_sa_key_present": effective_gcs_key_present,
        "gcs_sa_key_path_recorded": False,
        "credential_values_read": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
    }


def build_agents_last_exam_task_material_readiness(
    *,
    source_root: str | None,
    selected_task_id: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    requires_task_data: bool | str | None = None,
    task_data_source: str | None = None,
    baked_task_input_present: bool | None = None,
    baked_task_input_readiness: dict[str, Any] | None = None,
    gcs_sa_key: str | None = None,
    gcs_sa_key_present: bool | None = None,
    enforce_task_data_source: bool = False,
) -> dict[str, Any]:
    """Check local ALE task material existence without reading task bodies."""

    parts, task_label = _agents_last_exam_public_task_parts(selected_task_id)
    blockers: list[str] = []
    if not parts:
        blockers.append("selected_task_id_not_public_safe")
    try:
        root = Path(source_root).expanduser() if source_root else None
    except (OSError, RuntimeError):
        root = None
    source_root_available = bool(root and root.is_dir())
    if not source_root_available or root is None:
        blockers.append("source_root_not_available")

    task_dir_available = False
    task_card_present = False
    scripts_dir_present = False
    scorer_script_count = 0
    task_dir_entry_count = 0
    if root is not None and source_root_available and parts:
        task_dir = root / "tasks" / parts[0] / parts[1]
        try:
            resolved_root = root.resolve()
            resolved_task_dir = task_dir.resolve()
            inside_root = resolved_task_dir == resolved_root or (
                resolved_root in resolved_task_dir.parents
            )
        except OSError:
            inside_root = False
        task_dir_available = bool(inside_root and task_dir.is_dir())
        if task_dir_available:
            task_card_present = (task_dir / "task_card.json").is_file()
            scripts_dir = task_dir / "scripts"
            scripts_dir_present = scripts_dir.is_dir()
            try:
                task_dir_entry_count = sum(1 for _ in task_dir.iterdir())
            except OSError:
                task_dir_entry_count = 0
            if scripts_dir_present:
                try:
                    scorer_script_count = sum(
                        1
                        for path in scripts_dir.iterdir()
                        if path.is_file()
                        and path.suffix == ".py"
                        and "score" in path.name.lower()
                    )
                except OSError:
                    scorer_script_count = 0
    if not task_dir_available:
        blockers.append("task_directory_missing")
    if not task_card_present:
        blockers.append("task_card_json_missing")
    if not scripts_dir_present:
        blockers.append("task_scripts_directory_missing")
    if scorer_script_count < 1:
        blockers.append("task_scorer_script_missing")

    membership = _agents_last_exam_public_task_list_membership(
        source_root,
        selected_task_id,
        selected_task_lists,
    )
    if membership.get("checked") is not True:
        blockers.append("selected_task_list_membership_not_checked")
    elif int(membership.get("present_count") or 0) < 1:
        blockers.append("selected_task_not_in_public_task_lists")
    task_data = _agents_last_exam_task_data_source_readiness(
        requires_task_data=requires_task_data,
        task_data_source=task_data_source,
        baked_task_input_present=baked_task_input_present,
        baked_task_input_readiness=baked_task_input_readiness,
        gcs_sa_key=gcs_sa_key,
        gcs_sa_key_present=gcs_sa_key_present,
        enforce_task_data_source=enforce_task_data_source,
    )
    if enforce_task_data_source and task_data.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(task_data.get("first_blocker"), limit=80)
            or "task_data_source_not_ready"
        )

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_no_upload_ale_task_gate",
        "blockers": blockers,
        "task": {
            "task_id": task_label,
            "category": parts[0] if parts else None,
            "name": parts[1] if parts else None,
            "task_dir_available": task_dir_available,
            "task_card_json_present": task_card_present,
            "scripts_dir_present": scripts_dir_present,
            "scorer_script_count": scorer_script_count,
            "task_dir_entry_count": task_dir_entry_count,
            "task_dir_path_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
        },
        "task_data": task_data,
        "public_task_lists": membership,
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_local_no_upload_ale_validation_run_gate"
            if ready
            else "repair_ale_task_material_readiness_blocker",
            "minimum_next_evidence": (
                "A local/no-upload ALE task gate should combine this material "
                "readiness signal with host Codex no-task E2E readiness and the "
                "compact result reducer boundary before any task-level run."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


_AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE = re.compile(
    r"^\s*(?:self\.)?REQUIRES_TASK_DATA\s*(?::[^=]+)?=\s*(True|False)\b"
)


def _agents_last_exam_public_selected_task_scan(
    source_root: str | None,
    selected_task_lists: Iterable[str],
) -> dict[str, Any]:
    labels: list[str] = []
    task_ids: set[str] = set()
    missing_lists = 0
    checked_lists = 0
    unsafe_lists = 0
    if not source_root:
        return {
            "checked": False,
            "selected_task_lists": labels,
            "selected_task_count": 0,
            "checked_list_count": 0,
            "missing_list_count": 0,
            "unsafe_list_count": 0,
            "path_recorded": False,
            "task_ids": [],
        }
    try:
        root = Path(source_root).expanduser()
        selected_root = root / "selected_tasks"
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "selected_task_lists": labels,
            "selected_task_count": 0,
            "checked_list_count": 0,
            "missing_list_count": 0,
            "unsafe_list_count": 0,
            "path_recorded": False,
            "task_ids": [],
        }
    for raw_name in selected_task_lists:
        label = _agents_last_exam_public_id(raw_name, limit=120)
        if not label:
            unsafe_lists += 1
            continue
        parts = [part for part in str(raw_name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            labels.append(label)
            unsafe_lists += 1
            continue
        candidate = selected_root.joinpath(*parts)
        try:
            resolved_candidate = candidate.resolve()
            inside_root = resolved_candidate == resolved_root or (
                resolved_root in resolved_candidate.parents
            )
        except OSError:
            inside_root = False
        labels.append(label)
        if not inside_root or not candidate.is_file():
            missing_lists += 1
            continue
        checked_lists += 1
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            missing_lists += 1
            continue
        for line in lines:
            raw_task_id = line.strip().replace("\\", "/")
            if not raw_task_id or raw_task_id.startswith("#"):
                continue
            parts, safe_label = _agents_last_exam_public_task_parts(raw_task_id)
            if parts and safe_label:
                task_ids.add("/".join(parts))
    return {
        "checked": checked_lists > 0,
        "selected_task_lists": labels,
        "selected_task_count": len(task_ids),
        "checked_list_count": checked_lists,
        "missing_list_count": missing_lists,
        "unsafe_list_count": unsafe_lists,
        "path_recorded": False,
        "task_ids": sorted(task_ids),
    }


def _agents_last_exam_requires_task_data_line_scan(
    *,
    source_root: str | None,
    task_id: str,
    max_lines: int = 1200,
) -> dict[str, Any]:
    parts, task_label = _agents_last_exam_public_task_parts(task_id)
    if not parts:
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "selected_task_id_not_public_safe",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    try:
        root = Path(source_root).expanduser() if source_root else None
    except (OSError, RuntimeError):
        root = None
    if root is None or not root.is_dir():
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "source_root_not_available",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    source_file = root / "tasks" / parts[0] / parts[1] / "main.py"
    try:
        resolved_root = root.resolve()
        resolved_source_file = source_file.resolve()
        inside_root = resolved_source_file == resolved_root or (
            resolved_root in resolved_source_file.parents
        )
    except OSError:
        inside_root = False
    if not inside_root or not source_file.is_file():
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "task_config_main_py_missing",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    scanned = 0
    try:
        with source_file.open(encoding="utf-8") as handle:
            for raw_line in handle:
                scanned += 1
                match = _AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE.match(raw_line)
                if match:
                    requires_task_data = match.group(1) == "True"
                    return {
                        "task_id": task_label,
                        "checked": True,
                        "requires_task_data": requires_task_data,
                        "requires_task_data_declared": True,
                        "assignment_found": True,
                        "assignment_kind": "requires_task_data_bool_assignment",
                        "line_count_scanned": scanned,
                        "first_blocker": None,
                        "task_source_path_recorded": False,
                        "task_source_content_recorded": False,
                    }
                if scanned >= max_lines:
                    break
    except OSError:
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": scanned,
            "first_blocker": "task_config_main_py_unreadable",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    return {
        "task_id": task_label,
        "checked": True,
        "requires_task_data": True,
        "requires_task_data_declared": False,
        "assignment_found": False,
        "assignment_kind": "default_true_when_assignment_missing",
        "line_count_scanned": scanned,
        "first_blocker": None,
        "task_source_path_recorded": False,
        "task_source_content_recorded": False,
    }


def build_agents_last_exam_candidate_task_data_scan(
    *,
    source_root: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    allow_demo_candidate: bool = False,
) -> dict[str, Any]:
    """Scan selected ALE task configs for local no-task-data candidates.

    This is a bounded config-line scan: it extracts only a
    ``REQUIRES_TASK_DATA`` boolean assignment signal from task ``main.py`` and
    never records source paths or source text.
    """

    selected = _agents_last_exam_public_selected_task_scan(
        source_root,
        selected_task_lists,
    )
    blockers: list[str] = []
    if selected.get("checked") is not True:
        blockers.append("selected_task_lists_not_checked")
    task_ids = [
        task_id
        for task_id in selected.get("task_ids", [])
        if isinstance(task_id, str)
    ]
    if selected.get("checked") is True and not task_ids:
        blockers.append("selected_task_lists_empty")

    scan_results = [
        _agents_last_exam_requires_task_data_line_scan(
            source_root=source_root,
            task_id=task_id,
        )
        for task_id in task_ids
    ]
    checked_results = [item for item in scan_results if item.get("checked") is True]
    no_data_candidates = [
        str(item.get("task_id"))
        for item in checked_results
        if item.get("requires_task_data") is False and item.get("task_id")
    ]
    demo_no_data_candidates = [
        task_id for task_id in no_data_candidates if task_id.startswith("demo__")
    ]
    formal_no_data_candidates = [
        task_id for task_id in no_data_candidates if not task_id.startswith("demo__")
    ]
    eligible_candidates = (
        no_data_candidates if allow_demo_candidate else formal_no_data_candidates
    )
    if task_ids and not no_data_candidates:
        blockers.append("no_no_task_data_candidate_found")
    elif task_ids and not eligible_candidates:
        blockers.append("no_formal_no_task_data_candidate_found")
    ready = not blockers
    explicit_false_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is False
        and item.get("requires_task_data_declared") is True
    )
    explicit_true_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is True
        and item.get("requires_task_data_declared") is True
    )
    default_true_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is True
        and item.get("requires_task_data_declared") is False
    )
    missing_config_count = sum(
        1 for item in scan_results if item.get("checked") is not True
    )
    return {
        "schema_version": AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_no_task_data_ale_candidate_gate",
        "blockers": blockers,
        "selected_task_lists": {
            key: value
            for key, value in selected.items()
            if key != "task_ids"
        },
        "scan_summary": {
            "selected_task_count": len(task_ids),
            "task_config_checked_count": len(checked_results),
            "task_config_missing_or_unreadable_count": missing_config_count,
            "explicit_requires_task_data_false_count": explicit_false_count,
            "explicit_requires_task_data_true_count": explicit_true_count,
            "default_requires_task_data_true_count": default_true_count,
            "no_task_data_candidate_count": len(no_data_candidates),
            "formal_no_task_data_candidate_count": len(formal_no_data_candidates),
            "demo_no_task_data_candidate_count": len(demo_no_data_candidates),
            "allow_demo_candidate": bool(allow_demo_candidate),
        },
        "candidate_tasks": {
            "eligible_no_task_data_candidates": eligible_candidates[:25],
            "formal_no_task_data_candidates": formal_no_data_candidates[:25],
            "demo_no_task_data_candidates": demo_no_data_candidates[:25],
            "candidate_count_truncated": len(eligible_candidates) > 25,
            "task_ids_public_only": True,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "selected_task_list_content_recorded": False,
            "task_config_line_scan": True,
            "task_config_source_content_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_instruction_file_read": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_no_task_data_formal_ale_validation_gate"
            if ready
            else "do_not_launch_formal_ale_until_task_data_substrate_is_ready",
            "minimum_next_evidence": (
                "A formal local/no-upload ALE candidate should either be listed "
                "as not requiring task data or carry a separately verified "
                "task-data source readiness signal before any model task run."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_config_line_scan": True,
            "task_config_source_content_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_instruction_file_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


def _agents_last_exam_relative_file_probe(
    source_root: str | None,
    relative_path: str | None,
) -> dict[str, Any]:
    label = _agents_last_exam_public_id(relative_path, limit=160)
    if not relative_path:
        return {
            "relative_path": None,
            "declared": False,
            "exists": False,
            "first_blocker": "experiment_spec_missing",
            "source_root_path_recorded": False,
        }
    text = relative_path.replace("\\", "/").strip()
    parts = [part for part in text.split("/") if part]
    if text.startswith("/") or text.startswith("~") or any(
        part in {".", ".."} for part in parts
    ):
        return {
            "relative_path": label,
            "declared": True,
            "exists": False,
            "first_blocker": "experiment_spec_relative_path_not_public_safe",
            "source_root_path_recorded": False,
        }
    if not source_root:
        return {
            "relative_path": label,
            "declared": True,
            "exists": False,
            "first_blocker": "source_root_missing",
            "source_root_path_recorded": False,
        }
    try:
        source_path = Path(source_root).expanduser()
    except (OSError, RuntimeError):
        source_path = None
    if source_path is None or not source_path.is_dir():
        return {
            "relative_path": label,
            "declared": True,
            "exists": False,
            "first_blocker": "source_root_not_available",
            "source_root_path_recorded": False,
        }
    candidate = source_path.joinpath(*parts)
    try:
        resolved_source = source_path.resolve()
        resolved_candidate = candidate.resolve()
        inside_root = resolved_candidate == resolved_source or (
            resolved_source in resolved_candidate.parents
        )
    except OSError:
        inside_root = False
    exists = bool(inside_root and candidate.is_file())
    return {
        "relative_path": label,
        "declared": True,
        "exists": exists,
        "first_blocker": None if exists else "experiment_spec_file_missing",
        "source_root_path_recorded": False,
    }


def build_agents_last_exam_local_launch_packet(
    *,
    source_root: str | None,
    experiment_spec_relative_path: str | None,
    selected_task_id: str | None = None,
    expected_repo_url: str = AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    runner_binary: str | None = "python3",
    runner_python_module: str | None = "ale_run",
    runner_command_label: str | None = "python-m-ale-run",
    operator_authorized: bool = False,
    allow_public_task_material: bool = False,
    fetch_origin: bool = False,
    require_upstream_current: bool = False,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a redacted no-execution packet for a future ALE dry-run."""

    source_readiness = build_agents_last_exam_local_source_readiness(
        source_root=source_root,
        expected_repo_url=expected_repo_url,
        runner_python_module=runner_python_module or "ale_run",
        fetch_origin=fetch_origin,
        require_upstream_current=require_upstream_current,
    )
    runner_readiness = build_agents_last_exam_local_runner_readiness(
        selected_task_id=selected_task_id,
        snapshot=snapshot,
        provider_kind=provider_kind,
        image_ref=image_ref,
        alternate_image_ref=alternate_image_ref,
        runner_binary=runner_binary,
        runner_python_module=runner_python_module,
        runner_source_root=source_root,
        runner_command_label=runner_command_label,
        operator_authorized=operator_authorized,
        allow_public_task_material=allow_public_task_material,
        image_metadata=image_metadata,
        alternate_image_metadata=alternate_image_metadata,
        disk_headroom=disk_headroom,
    )
    spec_probe = _agents_last_exam_relative_file_probe(
        source_root,
        experiment_spec_relative_path,
    )
    blockers: list[str] = []
    if source_readiness.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(source_readiness.get("first_blocker"), limit=80)
            or "ale_source_not_ready"
        )
    if runner_readiness.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(runner_readiness.get("first_blocker"), limit=80)
            or "ale_runner_not_ready"
        )
    if spec_probe.get("exists") is not True:
        blockers.append(
            _agents_last_exam_public_id(spec_probe.get("first_blocker"), limit=80)
            or "experiment_spec_not_ready"
        )
    ready = not blockers
    source = (
        source_readiness.get("source")
        if isinstance(source_readiness.get("source"), dict)
        else {}
    )
    runner_probe = (
        runner_readiness.get("runner_probe")
        if isinstance(runner_readiness.get("runner_probe"), dict)
        else {}
    )
    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": _agents_last_exam_public_id(selected_task_id, limit=160)
        or "metadata_only_candidate",
        "snapshot": _agents_last_exam_public_id(snapshot, limit=80)
        or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_operator_triggered_no_upload_ale_dry_run",
        "blockers": blockers,
        "source_lock": {
            "expected_repo": source.get("expected_repo"),
            "remote": source.get("remote"),
            "remote_matches_expected": source.get("remote_matches_expected") is True,
            "head": source.get("head"),
            "upstream_ref": source.get("upstream_ref"),
            "upstream_head": source.get("upstream_head"),
            "upstream_declared": source.get("upstream_declared") is True,
            "head_matches_upstream": source.get("head_matches_upstream") is True,
            "upstream_ahead_count": source.get("upstream_ahead_count"),
            "upstream_behind_count": source.get("upstream_behind_count"),
            "fetch_origin_attempted": source.get("fetch_origin_attempted") is True,
            "fetch_origin_ok": source.get("fetch_origin_ok") is True,
            "require_upstream_current": source.get("require_upstream_current") is True,
            "source_root_path_recorded": False,
        },
        "runner": {
            "command_label": runner_probe.get("command_label"),
            "binary": runner_probe.get("binary"),
            "python_module": runner_probe.get("python_module"),
            "binary_available": runner_probe.get("binary_available") is True,
            "python_module_available": runner_probe.get("python_module_available")
            is True,
            "source_root_path_recorded": False,
            "command_argv_recorded": False,
        },
        "experiment_spec": {
            "relative_path": spec_probe.get("relative_path"),
            "declared": spec_probe.get("declared") is True,
            "exists": spec_probe.get("exists") is True,
            "content_read": False,
            "source_root_path_recorded": False,
        },
        "launch_packet": {
            "mode": "no_execution_launch_packet",
            "command_shape": "python-m-ale-run-dry-run",
            "will_execute": False,
            "will_start_container": False,
            "will_read_task_body": False,
            "will_invoke_model_api": False,
            "will_upload": False,
            "will_submit": False,
            "will_capture_screenshot": False,
            "will_record_credentials": False,
            "will_record_local_paths": False,
        },
        "case_state_init_contract": benchmark_case_active_state_init_contract(
            benchmark_id=AGENTS_LAST_EXAM_BENCHMARK_ID,
            goal_id=AGENTS_LAST_EXAM_CASE_GOAL_ID,
            case_state_path=AGENTS_LAST_EXAM_CASE_STATE_PATH,
            initialized_by_launch_packet=False,
        ),
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "operator_trigger_exact_no_upload_ale_dry_run"
            if ready
            else "repair_ale_launch_packet_blocker_before_execution",
            "minimum_next_evidence": (
                "A human/operator-triggered ALE dry-run using the redacted source "
                "lock, runner label, and experiment spec, followed by compact "
                "run/eval/events ingest only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "experiment_spec_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


def build_agents_last_exam_local_runner_readiness(
    *,
    selected_task_id: str | None = None,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    runner_binary: str | None = None,
    runner_python_module: str | None = None,
    runner_source_root: str | None = None,
    runner_command_label: str | None = None,
    operator_authorized: bool = False,
    allow_public_task_material: bool = False,
    fetch_origin: bool = False,
    require_upstream_current: bool = False,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    dry_run_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check whether a real local ALE dry-run runner is configured.

    This is still a no-execution gate: it may inspect Docker image metadata and
    the local PATH for a runner binary, but it does not start containers, read
    task bodies, invoke model APIs, upload, submit, or record command argv.
    """

    preflight_payload = (
        preflight
        if isinstance(preflight, dict)
        else build_agents_last_exam_local_preflight(
            selected_task_id=selected_task_id,
            snapshot=snapshot,
            provider_kind=provider_kind,
            image_ref=image_ref,
            alternate_image_ref=alternate_image_ref,
            image_metadata=image_metadata,
            alternate_image_metadata=alternate_image_metadata,
            disk_headroom=disk_headroom,
        )
    )
    plan_payload = (
        dry_run_plan
        if isinstance(dry_run_plan, dict)
        else build_agents_last_exam_local_dry_run_plan(
            selected_task_id=selected_task_id,
            snapshot=snapshot,
            provider_kind=provider_kind,
            image_ref=image_ref,
            alternate_image_ref=alternate_image_ref,
            image_metadata=image_metadata,
            alternate_image_metadata=alternate_image_metadata,
            disk_headroom=disk_headroom,
            preflight=preflight_payload,
        )
    )
    runner_probe = _agents_last_exam_runner_binary_probe(runner_binary)
    module_probe = _agents_last_exam_python_module_probe(
        runner_python_module,
        source_root=runner_source_root,
    )
    source_lock = None
    if fetch_origin or require_upstream_current:
        source_lock = build_agents_last_exam_local_source_readiness(
            source_root=runner_source_root,
            runner_python_module=runner_python_module or "ale_run",
            fetch_origin=fetch_origin,
            require_upstream_current=require_upstream_current,
        )
    command_label = _agents_last_exam_public_id(
        runner_command_label
        or (
            f"{runner_probe.get('binary')}-m-{module_probe.get('module')}"
            if runner_probe.get("binary") and module_probe.get("module")
            else runner_probe.get("binary")
        ),
        limit=120,
    )
    module_required = _agents_last_exam_runner_binary_requires_python_module(
        runner_binary
    )
    blockers: list[str] = []
    if operator_authorized is not True:
        blockers.append("operator_authorization_missing")
    if allow_public_task_material is not True:
        blockers.append("public_task_material_authorization_missing")
    if plan_payload.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(plan_payload.get("first_blocker"), limit=80)
            or "ale_local_dry_run_plan_not_ready"
        )
    if not command_label:
        blockers.append("runner_command_missing")
    if runner_probe.get("available") is not True:
        blockers.append(
            _agents_last_exam_public_id(runner_probe.get("first_blocker"), limit=80)
            or "runner_binary_not_available"
        )
    if module_required and module_probe.get("declared") is not True:
        blockers.append("runner_python_module_missing")
    if module_probe.get("declared") is True and module_probe.get("available") is not True:
        blockers.append(
            _agents_last_exam_public_id(module_probe.get("first_blocker"), limit=80)
            or "runner_python_module_not_available"
        )
    if source_lock is not None and source_lock.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(source_lock.get("first_blocker"), limit=80)
            or "ale_source_lock_not_ready"
        )
    ready = not blockers

    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_RUNNER_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": plan_payload.get("task_id") or "metadata_only_candidate",
        "snapshot": plan_payload.get("snapshot") or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "preflight_ready": preflight_payload.get("ready") is True,
        "dry_run_plan_ready": plan_payload.get("ready") is True,
        "runner_ready": ready,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_ale_dry_run_runner",
        "blockers": blockers,
        "runner_probe": {
            "command_label": command_label,
            "binary": runner_probe.get("binary"),
            "binary_declared": runner_probe.get("declared") is True,
            "binary_available": runner_probe.get("available") is True,
            "python_module": module_probe.get("module"),
            "python_module_declared": module_probe.get("declared") is True,
            "python_module_available": module_probe.get("available") is True,
            "source_root_declared": module_probe.get("source_root_declared") is True,
            "source_root_available": module_probe.get("source_root_available") is True,
            "source_root_path_recorded": False,
            "python_module_path_recorded": False,
            "binary_path_recorded": False,
            "command_argv_recorded": False,
            "first_blocker": _agents_last_exam_public_id(
                runner_probe.get("first_blocker"),
                limit=80,
            ),
        },
        "source_lock": source_lock,
        "boundary": {
            "local_only": True,
            "no_cloud": provider_kind == "docker",
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "operator_authorized_local_container_start": operator_authorized is True,
            "operator_authorized_public_task_material": (
                allow_public_task_material is True
            ),
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "model_api_allowed": False,
            "upload_allowed": False,
            "submit_allowed": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_configured_no_upload_ale_local_dry_run"
            if ready
            else "configure_verified_ale_local_runner_before_execution",
            "minimum_next_evidence": (
                "A configured local runner command label and PATH-visible runner "
                "binary, followed by one no-upload dry-run that produces compact "
                "run/eval/events metadata only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "Goal Harness treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }


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
    worker_self_validation_official_score_mismatch_count: int,
    worker_validation_scope_ambiguous_official_score_failure_count: int,
    worker_bridge_connected_official_score_failure_count: int,
    worker_startup_blocker_count: int,
    worker_startup_blockers: list[str],
    worker_setup_diagnostic_file_count: int,
    worker_setup_diagnostic_schema_ok_count: int,
    worker_setup_diagnostic_blockers: list[str],
    worker_submit_eligible_mismatch_count: int,
    worker_bridge_writeback_loss_count: int,
    environment_setup_failure_before_worker_count: int,
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
        "worker_self_validation_official_score_mismatch_count": (
            worker_self_validation_official_score_mismatch_count
        ),
        "worker_validation_scope_ambiguous_official_score_failure_count": (
            worker_validation_scope_ambiguous_official_score_failure_count
        ),
        "worker_bridge_connected_official_score_failure_count": (
            worker_bridge_connected_official_score_failure_count
        ),
        "worker_startup_blocker_count": worker_startup_blocker_count,
        "worker_startup_blockers": worker_startup_blockers,
        "worker_setup_diagnostic_file_count": worker_setup_diagnostic_file_count,
        "worker_setup_diagnostic_schema_ok_count": (
            worker_setup_diagnostic_schema_ok_count
        ),
        "worker_setup_diagnostic_blockers": worker_setup_diagnostic_blockers,
        "worker_submit_eligible_mismatch_count": worker_submit_eligible_mismatch_count,
        "worker_submit_eligible_mismatch_reason": (
            "worker_file_submit_eligible_true_under_runner_no_upload_boundary"
            if worker_submit_eligible_mismatch_count
            else "none"
        ),
        "worker_bridge_writeback_loss_count": worker_bridge_writeback_loss_count,
        "environment_setup_failure_before_worker_count": (
            environment_setup_failure_before_worker_count
        ),
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
    include_codex_trajectory_counts: bool = False,
    include_verifier_log_attribution: bool = False,
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
    job_name = str(config.get("job_name") or job_path.name)
    environment_setup_probe_run = (
        "environment_setup_probe" in job_name
        and _invocation_arg_value(invocation, "--agent") == "nop"
        and "--disable-verification" in invocation
    )
    lock_trials = lock.get("trials") if isinstance(lock.get("trials"), list) else []
    first_lock_trial = lock_trials[0] if lock_trials and isinstance(lock_trials[0], dict) else {}
    task_config = first_lock_trial.get("task") if isinstance(first_lock_trial.get("task"), dict) else {}
    agent_config = first_lock_trial.get("agent") if isinstance(first_lock_trial.get("agent"), dict) else {}
    agent_kwargs = agent_config.get("kwargs") if isinstance(agent_config.get("kwargs"), dict) else {}
    worker_materialization_probe_only = (
        _terminal_bench_lock_worker_materialization_probe_only(lock)
    )
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
    codex_goal_mode_baseline = (
        goal_harness_mode == TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
        and goal_harness_access_packet_mode
        == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    )
    baseline_without_goal_harness = (
        hardened_codex_baseline or codex_goal_mode_baseline or not bool(goal_harness_mode)
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
    elif codex_goal_mode_baseline:
        event_mode = TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
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
    worker_materialization_probe_contract_count = 0
    worker_materialization_probe_contract_payload: dict[str, Any] | None = None
    worker_self_validation_official_score_mismatch_count = 0
    worker_validation_scope_ambiguous_official_score_failure_count = 0
    worker_bridge_connected_official_score_failure_count = 0
    worker_startup_blocker_count = 0
    worker_startup_blockers: list[str] = []
    worker_setup_diagnostic_file_count = 0
    worker_setup_diagnostic_schema_ok_count = 0
    worker_setup_diagnostic_blockers: list[str] = []
    worker_submit_eligible_mismatch_count = 0
    pre_worker_agent_setup_failure_count = 0
    environment_setup_failure_before_worker_count = 0
    environment_setup_failure_contexts: list[dict[str, Any]] = []
    worker_runtime_exception_before_checkpoint_count = 0
    verifier_failure_attribution_count = 0
    verifier_dependency_failure_count = 0
    official_zero_observation_count = 0
    failure_attribution_labels: set[str] = set()
    agent_timeout_observed = False
    agent_setup_timeout_observed = False
    for trial_dir in sorted(path for path in job_path.iterdir() if path.is_dir()):
        trial_result_path = trial_dir / "result.json"
        if not trial_result_path.exists():
            continue
        trial = _load_json_object(trial_result_path)
        rewards = _reward_from_trial_result(trial, trial_dir)
        trial_reward_value = _numeric_reward_value(rewards)
        trial_config = trial.get("config") if isinstance(trial.get("config"), dict) else {}
        if trial_config:
            timeout_sources.append(trial_config)
        exception_info = trial.get("exception_info") if isinstance(trial.get("exception_info"), dict) else {}
        exception_type = exception_info.get("exception_type")
        agent_dir = trial_dir / "agent"
        trace_path = agent_dir / TERMINAL_BENCH_COUNTER_TRACE_FILE
        trajectory_path = agent_dir / "trajectory.json"
        worker_benchmark_run_path = (
            trial_dir / "agent" / TERMINAL_BENCH_WORKER_BENCHMARK_RUN_FILE
        )
        worker_setup_diagnostic_path = (
            trial_dir / "agent" / TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
        )
        worker_benchmark_run: dict[str, Any] = {}
        worker_benchmark_run_compact: dict[str, Any] | None = None
        trial_worker_materialization_probe_contract = False
        if worker_benchmark_run_path.exists():
            worker_benchmark_run = _load_json_object(worker_benchmark_run_path)
            worker_benchmark_run_compact = _compactable_benchmark_run_v0_payload(
                worker_benchmark_run
            )
            trial_worker_materialization_probe_contract = (
                _terminal_bench_worker_materialization_probe_contract(
                    worker_benchmark_run
                )
            )
            if trial_worker_materialization_probe_contract:
                worker_materialization_probe_contract_count += 1
                if worker_materialization_probe_contract_payload is None:
                    worker_materialization_probe_contract_payload = (
                        worker_benchmark_run_compact or worker_benchmark_run
                    )
        official_zero_observation = {"detected": False}
        if (
            not environment_setup_probe_run
            and not trial_worker_materialization_probe_contract
        ):
            official_zero_observation = _terminal_bench_official_zero_observation(
                trial=trial,
                reward_value=trial_reward_value,
                exception_type=exception_type,
            )
            if official_zero_observation["detected"]:
                official_zero_observation_count += 1
                failure_attribution_labels.add("official_verifier_solution_failure")
        if exception_type == "AgentTimeoutError" and not environment_setup_probe_run:
            agent_timeout_observed = True
        agent_failure_labels = (
            set()
            if environment_setup_probe_run
            else _terminal_bench_agent_failure_attribution_labels(
                trial=trial,
                exception_type=exception_type,
            )
        )
        failure_attribution_labels.update(agent_failure_labels)
        exception_kind = _compact_exception_kind(exception_type)
        if exception_kind == "agent_setup_timeout" and not environment_setup_probe_run:
            agent_setup_timeout_observed = True
            failure_attribution_labels.add("agent_setup_timeout_before_worker_start")
        elif exception_kind == "agent_setup_failure" and not environment_setup_probe_run:
            failure_attribution_labels.add("agent_setup_failed_before_worker_start")
        trial_agent_result = trial.get("agent_result") if isinstance(trial.get("agent_result"), dict) else {}
        environment_setup_failure_before_worker = (
            False
            if environment_setup_probe_run
            else _is_environment_setup_failure_before_worker(
                trial=trial,
                exception_type=exception_type,
                trial_agent_result=trial_agent_result,
            )
        )
        worker_setup_diagnostic_blocker = ""
        if worker_setup_diagnostic_path.exists():
            worker_setup_diagnostic_file_count += 1
            worker_setup_diagnostic = _load_json_object(worker_setup_diagnostic_path)
            if (
                worker_setup_diagnostic.get("schema_version")
                == TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA
            ):
                worker_setup_diagnostic_schema_ok_count += 1
                raw_blocker = (
                    worker_setup_diagnostic.get("pre_worker_startup_blocker")
                    or worker_setup_diagnostic.get("first_blocker")
                )
                worker_setup_diagnostic_blocker = str(raw_blocker or "").strip()
                if worker_setup_diagnostic_blocker in {"", "none"}:
                    worker_setup_diagnostic_blocker = ""
                if _terminal_bench_non_blocking_setup_label(
                    worker_setup_diagnostic_blocker
                ):
                    worker_setup_diagnostic_blocker = ""
                if worker_setup_diagnostic_blocker:
                    failure_attribution_labels.add(
                        "pre_worker_startup_blocker_recorded"
                    )
                    failure_attribution_labels.add(worker_setup_diagnostic_blocker)
                    if (
                        worker_setup_diagnostic_blocker
                        not in worker_setup_diagnostic_blockers
                    ):
                        worker_setup_diagnostic_blockers.append(
                            worker_setup_diagnostic_blocker
                        )
        pre_worker_agent_setup_failure = (
            _is_pre_worker_agent_setup_failure(
                trial_dir=trial_dir,
                exception_type=exception_type,
                trial_agent_result=trial_agent_result,
                trace_path=trace_path,
                worker_benchmark_run_path=worker_benchmark_run_path,
            )
            if not environment_setup_probe_run
            else False
        )
        if environment_setup_failure_before_worker:
            environment_setup_failure_before_worker_count += 1
            failure_attribution_labels.add("environment_setup_failed_before_worker")
            environment_setup_failure_contexts.append(
                _terminal_bench_environment_setup_failure_context(
                    trial=trial,
                    exception_type=exception_type,
                    trace_path=trace_path,
                    worker_benchmark_run_path=worker_benchmark_run_path,
                )
            )
        if pre_worker_agent_setup_failure:
            pre_worker_agent_setup_failure_count += 1
            failure_attribution_labels.add("agent_setup_failed_before_worker_start")
            if (
                worker_setup_diagnostic_blocker
                and not worker_benchmark_run_path.exists()
                and not worker_bridge_required
            ):
                worker_startup_blocker_count += 1
                if worker_setup_diagnostic_blocker not in worker_startup_blockers:
                    worker_startup_blockers.append(worker_setup_diagnostic_blocker)
        if (
            worker_bridge_required
            and exception_type not in (None, "", "none", "AgentTimeoutError")
            and not environment_setup_failure_before_worker
            and not pre_worker_agent_setup_failure
            and not trace_path.exists()
            and not worker_benchmark_run_path.exists()
        ):
            worker_runtime_exception_before_checkpoint_count += 1
        if trace_path.exists():
            worker_counter_trace_trial_count += 1
            trace_rows.extend(_load_jsonl_objects(trace_path))
        trajectory_goal_calls = (
            _trajectory_codex_runtime_goal_tool_calls(trajectory_path)
            if include_codex_trajectory_counts
            else _empty_codex_runtime_goal_tool_calls()
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
            if worker_benchmark_run_compact is not None:
                worker_benchmark_run_schema_ok_count += 1
                worker_validation_claim_kind = (
                    _terminal_bench_worker_validation_claim_kind(
                        worker_benchmark_run_compact
                    )
                )
                if (
                    not trial_worker_materialization_probe_contract
                    and
                    worker_validation_claim_kind
                    in {"official_case_success", "worker_claimed_case_success"}
                    and trial_reward_value is not None
                    and trial_reward_value == 0
                ):
                    worker_self_validation_official_score_mismatch_count += 1
                    failure_attribution_labels.add(
                        "worker_self_validation_official_score_mismatch"
                    )
                elif (
                    not trial_worker_materialization_probe_contract
                    and
                    worker_validation_claim_kind == "legacy_ambiguous_validation_scope"
                    and trial_reward_value is not None
                    and trial_reward_value == 0
                ):
                    worker_validation_scope_ambiguous_official_score_failure_count += 1
                    failure_attribution_labels.add(
                        "worker_validation_scope_ambiguous_official_score_failure"
                    )
                elif (
                    not trial_worker_materialization_probe_contract
                    and
                    worker_validation_claim_kind == "bridge_connectivity_only"
                    and trial_reward_value is not None
                    and trial_reward_value == 0
                ):
                    worker_bridge_connected_official_score_failure_count += 1
                    failure_attribution_labels.add(
                        "worker_bridge_connected_official_score_failure"
                    )
                worker_startup_blocker = _terminal_bench_worker_startup_blocker(
                    worker_benchmark_run_compact
                )
                if worker_startup_blocker:
                    worker_startup_blocker_count += 1
                    failure_attribution_labels.add("pre_worker_startup_blocker_recorded")
                    failure_attribution_labels.add(worker_startup_blocker)
                    if worker_startup_blocker not in worker_startup_blockers:
                        worker_startup_blockers.append(worker_startup_blocker)
                if (
                    no_upload_requested
                    and worker_benchmark_run_compact.get("submit_eligible") is True
                ):
                    worker_submit_eligible_mismatch_count += 1
        verifier_attribution = (
            _terminal_bench_verifier_failure_attribution(trial_dir)
            if include_verifier_log_attribution
            and (trial_reward_value is None or trial_reward_value == 0)
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
                "environment_setup_probe_materialized"
                if environment_setup_probe_run
                else "environment_setup_failed_before_worker"
                if environment_setup_failure_before_worker
                else
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
        if agent_failure_labels:
            trial_payload["agent_failure_attribution_labels"] = sorted(
                agent_failure_labels
            )
        if worker_setup_diagnostic_blocker:
            trial_payload["worker_setup_diagnostic_blocker"] = (
                worker_setup_diagnostic_blocker
            )
        if environment_setup_failure_before_worker and environment_setup_failure_contexts:
            trial_payload["environment_setup_failure_context"] = (
                environment_setup_failure_contexts[-1]
            )
        if official_zero_observation["detected"] or trial_reward_value == 0:
            trial_payload["official_zero_observation"] = official_zero_observation
        trials.append(trial_payload)

    worker_materialization_probe_no_trial_result = (
        worker_materialization_probe_only
        and not trials
        and (job_path / "lock.json").exists()
        and (job_path / "result.json").exists()
    )
    worker_materialization_probe_contract_present = (
        worker_materialization_probe_no_trial_result
        or worker_materialization_probe_contract_count > 0
    )
    worker_materialization_probe_status = (
        "not_applicable_worker_materialization_probe_no_trial_result"
        if worker_materialization_probe_no_trial_result
        else "not_run_worker_materialization_probe"
    )
    if worker_materialization_probe_no_trial_result:
        failure_attribution_labels.add("worker_materialization_probe_no_trial_result")
        failure_attribution_labels.add("detached_worker_ended_without_trial_result")

    interaction_counters = _counter_trace_interaction_counters(
        trace_rows,
        prompt_policy_injected=not baseline_without_goal_harness,
        harness_skill_or_packet_injected=bool(
            not baseline_without_goal_harness
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
        interaction_counters[
            "worker_self_validation_official_score_mismatch_count"
        ] = worker_self_validation_official_score_mismatch_count
        interaction_counters[
            "worker_validation_scope_ambiguous_official_score_failure_count"
        ] = worker_validation_scope_ambiguous_official_score_failure_count
        interaction_counters[
            "worker_bridge_connected_official_score_failure_count"
        ] = worker_bridge_connected_official_score_failure_count
        interaction_counters["worker_startup_blocker_count"] = (
            worker_startup_blocker_count
        )
        interaction_counters["worker_setup_diagnostic_file_count"] = (
            worker_setup_diagnostic_file_count
        )
        interaction_counters["worker_setup_diagnostic_schema_ok_count"] = (
            worker_setup_diagnostic_schema_ok_count
        )
        interaction_counters["worker_submit_eligible_mismatch_count"] = (
            worker_submit_eligible_mismatch_count
        )
        interaction_counters["pre_worker_agent_setup_failure_count"] = (
            pre_worker_agent_setup_failure_count
        )
        interaction_counters["environment_setup_failure_before_worker_count"] = (
            environment_setup_failure_before_worker_count
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
    if worker_materialization_probe_contract_present:
        official_score = None
        official_score_source = "worker_materialization_probe_contract"
    if official_score == 0 and agent_timeout_observed:
        failure_attribution_labels.add("agent_timeout_before_solution_completion")
    score_failure_attribution = _terminal_bench_score_failure_attribution(
        official_score=official_score,
        verifier_dependency_failure_count=verifier_dependency_failure_count,
        failure_attribution_labels=failure_attribution_labels,
        agent_timeout_observed=agent_timeout_observed,
        agent_setup_timeout_observed=agent_setup_timeout_observed,
    )
    if environment_setup_probe_run:
        score_failure_attribution = "not_applicable_environment_setup_probe"
    elif worker_materialization_probe_contract_present:
        score_failure_attribution = "not_applicable_worker_materialization_probe"
    runner_return_status = (
        "completed_with_agent_timeout"
        if agent_timeout_observed
        else "completed_with_agent_setup_timeout"
        if agent_setup_timeout_observed
        else "completed"
        if job_result.get("finished_at")
        else "pending"
    )
    official_score_status = (
        worker_materialization_probe_status
        if worker_materialization_probe_contract_present
        else "completed"
        if official_score is not None
        else "missing"
    )
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
    worker_bridge_verified = bool(
        trace_rows and worker_cli_total >= required_worker_cli_call_min
    )
    worker_bridge_failure_attribution = "none"
    if not worker_bridge_required:
        worker_bridge_materialization_status = "not_required"
        worker_bridge_materialization_blocker = "none"
    elif not trace_rows and worker_benchmark_run_file_count == 0:
        if environment_setup_failure_before_worker_count:
            worker_bridge_materialization_status = (
                "environment_setup_failed_before_worker"
            )
            worker_bridge_materialization_blocker = (
                "environment_setup_failed_before_worker"
            )
        elif pre_worker_agent_setup_failure_count:
            worker_bridge_materialization_status = "pre_worker_setup_failed"
            worker_bridge_materialization_blocker = (
                "pre_worker_agent_setup_failed_before_bridge_checkpoint"
            )
        elif worker_runtime_exception_before_checkpoint_count:
            worker_bridge_materialization_status = "runtime_exception_before_checkpoint"
            worker_bridge_materialization_blocker = (
                "worker_runtime_exception_before_bridge_checkpoint"
            )
        elif agent_timeout_observed:
            worker_bridge_materialization_status = "agent_timeout_before_checkpoint"
            worker_bridge_materialization_blocker = (
                "agent_timeout_before_bridge_checkpoint"
            )
        else:
            worker_bridge_materialization_status = "not_materialized"
            worker_bridge_materialization_blocker = "worker_bridge_not_materialized"
        worker_bridge_failure_attribution = worker_bridge_materialization_blocker
    elif trace_rows and worker_benchmark_run_file_count == 0:
        worker_bridge_materialization_status = "trace_without_writeback"
        worker_bridge_materialization_blocker = "worker_bridge_writeback_missing"
        worker_bridge_failure_attribution = worker_bridge_writeback_loss_reason
    elif worker_benchmark_run_file_count != worker_benchmark_run_schema_ok_count:
        worker_bridge_materialization_status = "writeback_schema_invalid"
        worker_bridge_materialization_blocker = "worker_bridge_writeback_schema_invalid"
        worker_bridge_failure_attribution = worker_bridge_materialization_blocker
    elif worker_startup_blocker_count:
        worker_bridge_materialization_status = "pre_worker_startup_blocker_recorded"
        worker_bridge_materialization_blocker = (
            worker_startup_blockers[0]
            if worker_startup_blockers
            else "pre_worker_startup_blocker_recorded"
        )
        worker_bridge_failure_attribution = worker_bridge_materialization_blocker
    elif worker_cli_total < required_worker_cli_call_min:
        worker_bridge_materialization_status = "insufficient_cli_calls"
        worker_bridge_materialization_blocker = "worker_bridge_cli_call_minimum_not_met"
        worker_bridge_failure_attribution = worker_bridge_materialization_blocker
    elif worker_bridge_verified:
        worker_bridge_materialization_status = "verified"
        worker_bridge_materialization_blocker = "none"
    else:
        worker_bridge_materialization_status = "incomplete"
        worker_bridge_materialization_blocker = "worker_bridge_incomplete"
        worker_bridge_failure_attribution = worker_bridge_materialization_blocker
    if worker_materialization_probe_no_trial_result:
        worker_bridge_materialization_status = "probe_contract_no_trial_result"
        worker_bridge_materialization_blocker = (
            "detached_worker_ended_without_trial_result"
        )
        worker_bridge_failure_attribution = (
            "worker_materialization_probe_no_trial_result"
        )
    elif worker_materialization_probe_contract_present:
        probe_outcome = (
            worker_materialization_probe_contract_payload.get("worker_bridge_outcome")
            if isinstance(worker_materialization_probe_contract_payload, dict)
            else None
        )
        if not isinstance(probe_outcome, dict):
            probe_outcome = {}
        probe_status = (
            probe_outcome.get("worker_bridge_materialization_status")
            or (
                worker_materialization_probe_contract_payload.get(
                    "worker_bridge_materialization_status"
                )
                if isinstance(worker_materialization_probe_contract_payload, dict)
                else None
            )
            or "probe_contract_verified"
        )
        probe_blocker = (
            probe_outcome.get("worker_bridge_materialization_blocker")
            or (
                worker_materialization_probe_contract_payload.get(
                    "worker_bridge_materialization_blocker"
                )
                if isinstance(worker_materialization_probe_contract_payload, dict)
                else None
            )
            or "none"
        )
        if _terminal_bench_non_blocking_setup_label(probe_blocker):
            probe_blocker = "none"
        worker_bridge_materialization_status = _public_safe_benchmark_label(
            probe_status
        ) or "probe_contract_verified"
        worker_bridge_materialization_blocker = (
            _public_safe_benchmark_label(probe_blocker) or "none"
        )
        worker_bridge_failure_attribution = (
            "none"
            if worker_bridge_materialization_blocker == "none"
            else worker_bridge_materialization_blocker
        )
    repeat_blocked_by = (
        worker_bridge_materialization_blocker
        if (
            worker_bridge_required or worker_materialization_probe_contract_present
        )
        and worker_bridge_materialization_blocker != "none"
        else "none"
    )
    worker_bridge_materialized = worker_bridge_materialization_status in {
        "trace_without_writeback",
        "writeback_schema_invalid",
        "pre_worker_startup_blocker_recorded",
        "insufficient_cli_calls",
        "verified",
        "incomplete",
        "worker_codex_materialization_verified",
        "probe_contract_verified",
    }
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
        worker_startup_blocker_count=worker_startup_blocker_count,
        worker_startup_blockers=worker_startup_blockers,
        worker_setup_diagnostic_file_count=worker_setup_diagnostic_file_count,
        worker_setup_diagnostic_schema_ok_count=(
            worker_setup_diagnostic_schema_ok_count
        ),
        worker_setup_diagnostic_blockers=worker_setup_diagnostic_blockers,
        worker_submit_eligible_mismatch_count=worker_submit_eligible_mismatch_count,
        worker_bridge_writeback_loss_count=worker_bridge_writeback_loss_count,
        worker_self_validation_official_score_mismatch_count=(
            worker_self_validation_official_score_mismatch_count
        ),
        worker_validation_scope_ambiguous_official_score_failure_count=(
            worker_validation_scope_ambiguous_official_score_failure_count
        ),
        worker_bridge_connected_official_score_failure_count=(
            worker_bridge_connected_official_score_failure_count
        ),
        environment_setup_failure_before_worker_count=(
            environment_setup_failure_before_worker_count
        ),
        pre_worker_agent_setup_failure_count=pre_worker_agent_setup_failure_count,
        codex_runtime_goal_tool_trial_count=codex_runtime_goal_tool_trial_count,
        trace_publicness=trace_publicness,
    )
    environment_setup_failure_context = (
        environment_setup_failure_contexts[0]
        if environment_setup_failure_contexts
        else None
    )
    validation = {
        "job_lock_present": (job_path / "lock.json").exists(),
        "job_result_present": (job_path / "result.json").exists(),
        "trial_results_present": bool(trials)
        and len(trials) == (job_result.get("n_total_trials") or len(trials)),
        "probe_contract_result_present": worker_materialization_probe_contract_present,
        "case_solution_attempted_or_not_required": True,
        "case_solution_not_required_for_probe": (
            worker_materialization_probe_contract_present
        ),
        "verifier_reward_present": (
            worker_materialization_probe_contract_present
            or official_score is not None
        ),
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
        "worker_startup_blockers_classified": True,
        "worker_benchmark_run_present_for_traced_trials": (
            worker_benchmark_run_file_count >= worker_counter_trace_trial_count
        ),
        "worker_bridge_materialized_when_required": (
            (not worker_bridge_required)
            or worker_bridge_materialized
        ),
        "worker_bridge_repeat_ready": repeat_blocked_by == "none",
        "worker_submit_eligible_matches_runner_boundary": (
            worker_submit_eligible_mismatch_count == 0
        ),
        "pre_worker_agent_setup_failures_classified": True,
        "environment_setup_failures_before_worker_classified": True,
        "verifier_failure_attribution_public_safe": True,
        "verifier_dependency_failures_classified": True,
        "worker_checkpoint_not_expected_before_agent_setup": True,
        "agent_timeout_recorded_if_present": not agent_timeout_observed
        or any(trial.get("exception_type") == "AgentTimeoutError" for trial in trials),
        "no_leaderboard_upload_requested": no_upload_requested,
        "paths_redacted": True,
        "raw_trace_excluded": True,
        "raw_trajectory_excluded": not bool(include_codex_trajectory_counts),
        "verifier_logs_excluded": not bool(include_verifier_log_attribution),
        "credential_values_not_recorded": True,
    }
    environment_setup_probe_status = "not_applicable"
    environment_setup_probe_cleared = False
    if environment_setup_probe_run:
        environment_setup_probe_cleared = (
            (job_path / "lock.json").exists()
            and (job_path / "result.json").exists()
            and bool(trials)
            and bool(job_result.get("finished_at"))
        )
        environment_setup_probe_status = (
            "materialized" if environment_setup_probe_cleared else "not_materialized"
        )
    evidence_files = [
        "job:lock.json",
        "job:result.json",
        "trial:result.json",
        "trial:agent/goal-harness-counter-trace.jsonl",
        "trial:agent/goal-harness-worker-benchmark-run.json",
        "trial:agent/goal-harness-worker-setup-diagnostic.json",
        "trial:verifier/reward.txt",
        "trial:artifacts/manifest.json",
    ]
    if include_codex_trajectory_counts:
        evidence_files.insert(3, "trial:agent/trajectory.json")
    raw_artifacts_read = bool(
        include_codex_trajectory_counts or include_verifier_log_attribution
    )
    probe_payload = (
        worker_materialization_probe_contract_payload
        if isinstance(worker_materialization_probe_contract_payload, dict)
        else {}
    )
    payload_source_runner = (
        "terminal_bench_worker_materialization_probe"
        if worker_materialization_probe_contract_present
        else "harbor"
    )
    payload_benchmark_id = (
        str(probe_payload.get("benchmark_id") or benchmark_id)
        if worker_materialization_probe_contract_present
        else benchmark_id
    )
    payload_mode = (
        str(probe_payload.get("mode") or f"{event_mode}_worker_materialization_probe")
        if worker_materialization_probe_contract_present
        else event_mode
    )
    official_task_score_payload = (
        {
            "kind": worker_materialization_probe_status,
            "value": None,
            "passed": False,
            "source": "worker_materialization_probe_contract",
        }
        if worker_materialization_probe_contract_present
        else {
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
        else {"kind": "harbor_verifier_reward_missing"}
    )
    payload = {
        "schema_version": "benchmark_run_v0",
        "source_runner": payload_source_runner,
        "benchmark_id": payload_benchmark_id,
        "job_name": config.get("job_name") or job_path.name,
        "mode": payload_mode,
        "environment_setup_probe_run": environment_setup_probe_run,
        "environment_setup_probe_status": environment_setup_probe_status,
        "environment_setup_probe_cleared": environment_setup_probe_cleared,
        "worker_materialization_probe_only": worker_materialization_probe_only,
        "worker_materialization_probe_contract_present": (
            worker_materialization_probe_contract_present
        ),
        "worker_materialization_probe_contract_count": (
            worker_materialization_probe_contract_count
        ),
        "worker_materialization_probe_no_trial_result": (
            worker_materialization_probe_no_trial_result
        ),
        "case_solution_attempted": not worker_materialization_probe_contract_present,
        "worker_mode": TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE
        if hardened_codex_baseline
        else TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
        if codex_goal_mode_baseline
        else "goal_harness_managed_codex"
        if agent_config.get("import_path") == TERMINAL_BENCH_MANAGED_AGENT_IMPORT_PATH
        else agent_config.get("name")
        or "codex",
        "trace_publicness": trace_publicness,
        "real_run": not worker_materialization_probe_contract_present,
        "submit_eligible": False,
        "case_semantics_changed_by_harness": not baseline_without_goal_harness,
        "goal_harness_inside_case": not baseline_without_goal_harness,
        "official_score_comparable_to_native_codex": (
            not worker_materialization_probe_contract_present
            and not bool(goal_harness_mode)
            and not hardened_codex_baseline
        ),
        "official_score_comparable_to_goal_harness_treatment": (
            not worker_materialization_probe_contract_present
            and (hardened_codex_baseline or codex_goal_mode_baseline)
        ),
        "model_plus_harness_pair": not baseline_without_goal_harness,
        "control_plane_score_applicable": (
            not worker_materialization_probe_contract_present
            and not baseline_without_goal_harness
        ),
        "codex_goal_mode_baseline": codex_goal_mode_baseline,
        "startup_surface_calibration": worker_materialization_probe_contract_present,
        "hardened_install_surface": hardened_codex_baseline,
        "hardened_install_baseline": hardened_codex_baseline,
        "leaderboard_evidence": False,
        "read_boundary": {
            "compact_only": not raw_artifacts_read,
            "raw_artifacts_read": raw_artifacts_read,
            "task_text_read": False,
            "trajectory_read": bool(include_codex_trajectory_counts),
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
        "goal_harness_worker_cli_bridge_available": bool(
            worker_bridge_required
        ),
        "goal_harness_worker_cli_bridge_trace_observed": bool(trace_rows),
        "worker_goal_harness_cli_call_total": worker_cli_total,
        "worker_counter_trace_trial_count": worker_counter_trace_trial_count,
        "worker_benchmark_run_file_count": worker_benchmark_run_file_count,
        "worker_benchmark_run_schema_ok_count": worker_benchmark_run_schema_ok_count,
        "worker_materialization_probe_contract_file_count": (
            worker_materialization_probe_contract_count
        ),
        "worker_self_validation_official_score_mismatch_count": (
            worker_self_validation_official_score_mismatch_count
        ),
        "worker_validation_scope_ambiguous_official_score_failure_count": (
            worker_validation_scope_ambiguous_official_score_failure_count
        ),
        "worker_bridge_connected_official_score_failure_count": (
            worker_bridge_connected_official_score_failure_count
        ),
        "worker_startup_blocker_count": worker_startup_blocker_count,
        "worker_startup_blockers": worker_startup_blockers,
        "worker_setup_diagnostic_file_count": worker_setup_diagnostic_file_count,
        "worker_setup_diagnostic_schema_ok_count": (
            worker_setup_diagnostic_schema_ok_count
        ),
        "worker_setup_diagnostic_blockers": worker_setup_diagnostic_blockers,
        "worker_submit_eligible_mismatch_count": worker_submit_eligible_mismatch_count,
        "worker_submit_eligible_mismatch_reason": worker_submit_eligible_mismatch_reason,
        "worker_bridge_writeback_loss_count": worker_bridge_writeback_loss_count,
        "worker_bridge_writeback_loss_reason": worker_bridge_writeback_loss_reason,
        "worker_bridge_materialization_status": worker_bridge_materialization_status,
        "worker_bridge_materialization_blocker": worker_bridge_materialization_blocker,
        "worker_bridge_failure_attribution": worker_bridge_failure_attribution,
        "first_blocker": worker_bridge_materialization_blocker
        if worker_bridge_materialization_blocker != "none"
        else None,
        "repeat_blocked_by": repeat_blocked_by,
        "pre_worker_startup_blocker": (
            worker_bridge_materialization_blocker
            if worker_bridge_materialization_status
            == "pre_worker_startup_blocker_recorded"
            else None
        ),
        "pre_worker_agent_setup_failure_count": pre_worker_agent_setup_failure_count,
        "environment_setup_failure_before_worker_count": (
            environment_setup_failure_before_worker_count
        ),
        "worker_runtime_exception_before_checkpoint_count": (
            worker_runtime_exception_before_checkpoint_count
        ),
        "verifier_failure_attribution_count": verifier_failure_attribution_count,
        "verifier_dependency_failure_count": verifier_dependency_failure_count,
        "official_zero_observation_count": official_zero_observation_count,
        "failure_attribution_labels": sorted(failure_attribution_labels),
        "score_failure_attribution": score_failure_attribution,
        "runner_return_status": runner_return_status,
        "official_score": official_score,
        "official_score_source": official_score_source,
        "official_score_status": official_score_status,
        "required_worker_goal_harness_cli_call_total_min": required_worker_cli_call_min,
        "official_task_score": official_task_score_payload,
        "agent": _redacted_agent_kwargs(agent_config),
        "progress": {
            "n_total_trials": job_result.get("n_total_trials"),
            "n_completed_trials": stats.get("n_completed_trials"),
            "n_errored_trials": stats.get("n_errored_trials"),
            "n_running_trials": stats.get("n_running_trials"),
            "n_pending_trials": stats.get("n_pending_trials"),
            "n_cancelled_trials": stats.get("n_cancelled_trials"),
            "n_retries": stats.get("n_retries"),
            "probe_contract_result_present": (
                worker_materialization_probe_contract_present
            ),
            "case_solution_attempted": (
                not worker_materialization_probe_contract_present
            ),
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
                else TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE
                if codex_goal_mode_baseline
                else "runner_only_no_worker_bridge"
                if goal_harness_mode == "codex_goal_harness"
                else "not_applicable_native_codex_baseline"
            ),
            "runner_return_status": runner_return_status,
            "official_score_status": official_score_status,
            "trace_publicness": trace_publicness,
            "next_action": (
                "run the paired baseline or treatment slice"
                if worker_materialization_probe_contract_present
                and not worker_materialization_probe_no_trial_result
                else "ingest compact worker materialization probe contract, then repair runner materialization before case baseline/test"
                if worker_materialization_probe_no_trial_result
                else
                "diagnose benchmark environment setup before worker startup"
                if worker_bridge_required
                and worker_bridge_materialization_status
                == "environment_setup_failed_before_worker"
                else "repair Codex agent setup/launcher before another same-task repeat"
                if worker_bridge_required
                and worker_bridge_materialization_status == "pre_worker_setup_failed"
                else "repair recorded worker startup blocker before another same-task repeat"
                if worker_bridge_required
                and worker_bridge_materialization_status
                == "pre_worker_startup_blocker_recorded"
                else "diagnose compact worker runtime failure before another repeat"
                if worker_bridge_required
                and worker_bridge_materialization_status
                == "runtime_exception_before_checkpoint"
                else "repair launcher or worker startup bridge materialization before repeat"
                if worker_bridge_required
                and worker_bridge_materialization_status == "not_materialized"
                else "repair worker bridge compact evidence before repeat"
                if worker_bridge_required
                and worker_bridge_materialization_status != "verified"
                else "prefer runner-side guaranteed append; optimize worker graceful closure before repeat"
                if worker_bridge_required
                else "compare hardened Codex baseline against Goal Harness treatment under the same no-upload boundary"
                if hardened_codex_baseline
                else "compare observed runner result against Goal Harness treatment under the same no-upload boundary"
            ),
            "worker_bridge_verified": worker_bridge_verified,
            "worker_materialization_probe_only": worker_materialization_probe_only,
            "worker_materialization_probe_contract_present": (
                worker_materialization_probe_contract_present
            ),
            "worker_materialization_probe_contract_count": (
                worker_materialization_probe_contract_count
            ),
            "worker_materialization_probe_no_trial_result": (
                worker_materialization_probe_no_trial_result
            ),
            "case_solution_attempted": (
                not worker_materialization_probe_contract_present
            ),
            "worker_bridge_materialization_status": worker_bridge_materialization_status,
            "worker_bridge_materialization_blocker": worker_bridge_materialization_blocker,
            "worker_bridge_failure_attribution": worker_bridge_failure_attribution,
            "repeat_blocked_by": repeat_blocked_by,
            "pre_worker_startup_blocker": (
                worker_bridge_materialization_blocker
                if worker_bridge_materialization_status
                == "pre_worker_startup_blocker_recorded"
                else None
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
            "worker_startup_blocker_count": worker_startup_blocker_count,
            "worker_setup_diagnostic_file_count": worker_setup_diagnostic_file_count,
            "worker_setup_diagnostic_schema_ok_count": (
                worker_setup_diagnostic_schema_ok_count
            ),
            "worker_setup_diagnostic_blockers": worker_setup_diagnostic_blockers,
            "worker_self_validation_official_score_mismatch_count": (
                worker_self_validation_official_score_mismatch_count
            ),
            "worker_validation_scope_ambiguous_official_score_failure_count": (
                worker_validation_scope_ambiguous_official_score_failure_count
            ),
            "worker_bridge_connected_official_score_failure_count": (
                worker_bridge_connected_official_score_failure_count
            ),
            "pre_worker_agent_setup_failure_count": pre_worker_agent_setup_failure_count,
            "environment_setup_failure_before_worker_count": (
                environment_setup_failure_before_worker_count
            ),
            "worker_runtime_exception_before_checkpoint_count": (
                worker_runtime_exception_before_checkpoint_count
            ),
            "verifier_failure_attribution_count": verifier_failure_attribution_count,
            "verifier_dependency_failure_count": verifier_dependency_failure_count,
            "official_zero_observation_count": official_zero_observation_count,
            "failure_attribution_labels": sorted(failure_attribution_labels),
            "score_failure_attribution": score_failure_attribution,
            "official_score_value": official_score,
            "wall_time_policy": wall_time_policy,
        },
        "validation": validation,
        "trials": trials,
        "evidence_files": evidence_files,
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
    if environment_setup_failure_context:
        payload["environment_setup_failure_context"] = (
            environment_setup_failure_context
        )
        payload["worker_bridge_outcome"][
            "environment_setup_failure_context"
        ] = environment_setup_failure_context
    return payload


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


def _prepend_env_path_entry(value: str | None, entry: str) -> str:
    parts = [part for part in str(value or "").split(os.pathsep) if part]
    deduped = [part for part in parts if part != entry]
    return os.pathsep.join([entry, *deduped])


def build_terminal_bench_private_runner_env() -> dict[str, str]:
    """Build the private local environment for a real Harbor runner launch."""

    env = sanitize_terminal_bench_private_runner_env(_probe_env())
    env["PYTHONPATH"] = _prepend_env_path_entry(
        env.get("PYTHONPATH"),
        _private_runner_goal_harness_project_root(),
    )
    return env


def _apply_terminal_bench_private_default_timeout_policy(
    command_kwargs: dict[str, Any],
) -> None:
    """Default private no-upload Terminal-Bench cases to a two-hour setup/agent budget."""

    if _optional_float(command_kwargs.get("agent_timeout_multiplier")) is None:
        command_kwargs["agent_timeout_multiplier"] = (
            TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_TIMEOUT_MULTIPLIER
        )
    if _optional_float(command_kwargs.get("agent_setup_timeout_multiplier")) is None:
        command_kwargs["agent_setup_timeout_multiplier"] = (
            TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_SETUP_TIMEOUT_MULTIPLIER
        )


def _private_runner_goal_harness_project_root() -> str:
    return str(Path(__file__).resolve().parents[1])


def _private_runner_goal_harness_runtime_root() -> str:
    return str(Path("~/.codex/goal-harness").expanduser())


def _private_runner_active_user_host_dir() -> str:
    return str(Path("~/.codex/goal-harness/active-user-feeds").expanduser())


def _private_runner_absolute_jobs_dir(value: Any) -> Any:
    text = str(value or "")
    if not text or "<" in text or ">" in text:
        return value
    return str(Path(text).expanduser().resolve())


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


def _terminal_bench_setup_timeout_repair_profile(
    command_kwargs: dict[str, Any],
    *,
    reject_runtime_install: bool = False,
) -> dict[str, Any]:
    """Apply the generic repair profile for pre-worker setup timeouts."""

    materialization_strategy = str(
        command_kwargs.get("worker_codex_materialization_strategy") or ""
    ).strip()
    if (
        materialization_strategy
        and materialization_strategy
        not in TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES
    ):
        raise ValueError(
            "setup_timeout_repair_profile requires worker_codex_materialization_strategy "
            "to be one of: "
            + ", ".join(TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES)
        )
    current_strategy = command_kwargs.get("codex_install_strategy")
    if (
        reject_runtime_install
        and current_strategy
        == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ):
        raise ValueError(
            "setup_timeout_repair_profile disallows "
            "codex_install_strategy=runtime_install_if_missing"
        )
    if current_strategy not in (
        None,
        "",
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING,
    ):
        raise ValueError(
            "setup_timeout_repair_profile requires a known codex install strategy"
        )

    if (
        materialization_strategy
        == TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
    ):
        command_kwargs[
            "codex_install_strategy"
        ] = TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
        command_kwargs["worker_codex_materialization_strategy"] = (
            TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
        )
    else:
        command_kwargs[
            "codex_install_strategy"
        ] = TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING

    required_multipliers = {
        "agent_timeout_multiplier": (
            TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_AGENT_TIMEOUT_MULTIPLIER
        ),
        "agent_setup_timeout_multiplier": (
            TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_AGENT_SETUP_TIMEOUT_MULTIPLIER
        ),
    }
    applied_multipliers: dict[str, float] = {}
    for key, required in required_multipliers.items():
        current = _optional_float(command_kwargs.get(key))
        if current is None:
            command_kwargs[key] = required
            applied_multipliers[key] = required
            continue
        if current != required:
            raise ValueError(
                f"setup_timeout_repair_profile requires {key}="
                f"{_format_harbor_multiplier(required)}"
            )
        applied_multipliers[key] = current

    fail_fast_materialization = (
        command_kwargs["codex_install_strategy"]
        == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    )
    codex_preflight_timeout = _optional_positive_int(
        command_kwargs.get("codex_preflight_timeout_sec")
    )
    if (
        codex_preflight_timeout is None
        and command_kwargs.get("codex_preflight_timeout_sec") is not None
    ):
        raise ValueError(
            "setup_timeout_repair_profile requires a positive integer "
            "codex_preflight_timeout_sec"
        )
    if fail_fast_materialization:
        if codex_preflight_timeout is None:
            codex_preflight_timeout = (
                TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC
            )
            command_kwargs["codex_preflight_timeout_sec"] = codex_preflight_timeout
        elif (
            codex_preflight_timeout
            != TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC
        ):
            raise ValueError(
                "setup_timeout_repair_profile requires codex_preflight_timeout_sec="
                f"{TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_CODEX_PREFLIGHT_TIMEOUT_SEC}"
            )

    required_launch_overrides: dict[str, Any] = {
        "codex_install_strategy": command_kwargs["codex_install_strategy"],
        **applied_multipliers,
    }
    if fail_fast_materialization:
        required_launch_overrides["codex_preflight_timeout_sec"] = (
            codex_preflight_timeout
        )
    if materialization_strategy:
        required_launch_overrides["worker_codex_materialization_strategy"] = (
            materialization_strategy
        )
    disallowed_launch_overrides: dict[str, Any] = {}
    if fail_fast_materialization:
        disallowed_launch_overrides["codex_install_strategy"] = (
            TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
        )

    return {
        "schema_version": TERMINAL_BENCH_SETUP_TIMEOUT_REPAIR_PROFILE_SCHEMA,
        "enabled": True,
        "materialization_strategy": materialization_strategy,
        "required_launch_overrides": required_launch_overrides,
        "disallowed_launch_overrides": disallowed_launch_overrides,
        "raw_logs_required": False,
        "raw_task_text_required": False,
        "credential_values_recorded": False,
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
    _apply_terminal_bench_private_default_timeout_policy(resolved_command_kwargs)
    setup_timeout_repair_profile = bool(
        resolved_command_kwargs.pop("setup_timeout_repair_profile", False)
    )
    repair_profile: dict[str, Any] | None = None
    if setup_timeout_repair_profile:
        repair_profile = _terminal_bench_setup_timeout_repair_profile(
            resolved_command_kwargs
        )
    if "jobs_dir" in resolved_command_kwargs:
        resolved_command_kwargs["jobs_dir"] = _private_runner_absolute_jobs_dir(
            resolved_command_kwargs["jobs_dir"]
        )
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
    elif mode == "codex-goal-mode":
        resolved_command_kwargs.pop("goal_harness_mode", None)
        resolved_command_kwargs.pop("goal_harness_ablation_mode", None)
        resolved_command_kwargs.pop("goal_harness_access_packet_mode", None)
        resolved_command_kwargs.pop("goal_harness_cli_bridge_enabled", None)
        resolved_command_kwargs.pop("goal_harness_active_user_intervention_enabled", None)
        resolved_command_kwargs.setdefault(
            "job_name",
            "terminal_bench_codex_goal_mode_baseline",
        )
        argv = build_terminal_bench_managed_harbor_command(
            resolve_cli_paths=True,
            goal_harness_mode=TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE,
            goal_harness_ablation_mode="codex_goal_mode_baseline",
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
    timeout_policy = _terminal_bench_launch_timeout_multiplier_policy(argv)
    setup_readiness = _terminal_bench_agent_setup_readiness(
        argv,
        timeout_policy,
        setup_timeout_repair_profile=setup_timeout_repair_profile,
    )
    if (
        first_blocker == "ready_for_private_managed_no_upload_pilot_review"
        and (
            setup_timeout_repair_profile
            or setup_readiness.get("fail_fast_install_strategy") is True
        )
        and setup_readiness.get("setup_materialization_blocks_launch") is True
    ):
        first_blocker = str(
            setup_readiness.get("first_blocker")
            or "codex_worker_materialization_not_ready"
        )
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
        "setup_timeout_repair_profile": setup_timeout_repair_profile,
        "repair_profile": repair_profile or {},
        "first_blocker": first_blocker,
        "ready": first_blocker == "ready_for_private_managed_no_upload_pilot_review",
    }


def _terminal_bench_run_ledger_closeout_templates() -> dict[str, Any]:
    """Return public-safe closeout templates for result ingest plus ledger upsert."""

    argv_template = [
        "python3",
        "-m",
        "goal_harness.cli",
        "--format",
        "json",
        "--registry",
        "<goal-harness-runtime-root>/registry.global.json",
        "--runtime-root",
        "<goal-harness-runtime-root>",
        "benchmark",
        "run",
        "terminal-bench",
        "--goal-id",
        "<goal-id>",
        "--harbor-job-dir",
        "<private-job-dir>",
        "--update-run-ledger",
        "--run-group-id",
        "<run-group-id>",
        "--run-ledger-note",
        "<compact-note>",
        "--execute",
        "--no-global-sync",
    ]
    return {
        "schema_version": TERMINAL_BENCH_RUN_LEDGER_CLOSEOUT_SCHEMA,
        "history_append": True,
        "run_ledger_update": True,
        "atomic_ledger_upsert": True,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "argv_template": argv_template,
        "display_command": (
            "PYTHONPATH=<goal-harness-project-root> "
            + " ".join(argv_template)
        ),
        "post_run_rule": (
            "after each completed no-upload case, ingest the Harbor job directory "
            "through benchmark run with --update-run-ledger"
        ),
    }


def _terminal_bench_compact_failure_marker(
    *,
    failure_class: str,
    evidence_kind: str,
    external_handle_state: str,
    launch_state_countable: bool,
    job_result_present: bool,
    trial_result_present_count: int,
    job_result_finished: bool | None = None,
    job_running_trial_count: int | None = None,
    job_pending_trial_count: int | None = None,
    job_result_updated_at_present: bool | None = None,
    job_updated_age_seconds: float | None = None,
    job_active_stale_seconds_threshold: int | None = None,
    worker_materialization_probe_only: bool | None = None,
    probe_contract_result_present: bool | None = None,
) -> dict[str, Any]:
    """Build a compact terminal marker without leaking runner artifacts."""

    finalization_failures = {
        "stale_active_job_without_trial_result",
        "detached_worker_ended_active_without_trial_result",
        "detached_worker_ended_without_trial_result",
    }
    launch_failures = {
        "detached_worker_ended_without_jobs_dir",
        "detached_worker_ended_without_job_root",
        "terminal_bench_prelaunch_readiness_blocked",
        "terminal_bench_prelaunch_existing_job_root_blocked",
    }
    if failure_class in finalization_failures:
        lifecycle_stage = "result_finalization"
        ledger_attempt_kind = "runner_closeout_attempt"
        next_allowed_action = "repair_result_finalization_closeout_contract_before_rerun"
    elif failure_class in launch_failures:
        lifecycle_stage = "job_materialization"
        ledger_attempt_kind = "launcher_attempt"
        next_allowed_action = "repair_job_materialization_before_baseline_rerun"
    else:
        lifecycle_stage = "runner_startup"
        ledger_attempt_kind = "runner_attempt"
        next_allowed_action = "classify_compact_runner_failure_before_rerun"

    marker: dict[str, Any] = {
        "schema_version": TERMINAL_BENCH_COMPACT_FAILURE_MARKER_SCHEMA,
        "failure_class": failure_class,
        "evidence_kind": evidence_kind,
        "external_handle_kind": "detached_worker_process",
        "external_handle_state": external_handle_state,
        "external_handle_terminal": external_handle_state == "ended",
        "terminal_closeout": True,
        "terminal_state": "terminal_compact_failure",
        "lifecycle_stage": lifecycle_stage,
        "ledger_attempt_kind": ledger_attempt_kind,
        "runner_attempt_countable": True,
        "launch_state_countable": launch_state_countable,
        "case_attempt_countable": False,
        "benchmark_budget_countable": False,
        "next_allowed_action": next_allowed_action,
        "job_result_present": job_result_present,
        "trial_result_present_count": trial_result_present_count,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
        "raw_external_handle_payload_recorded": False,
    }
    optional_fields: dict[str, Any] = {
        "job_result_finished": job_result_finished,
        "job_running_trial_count": job_running_trial_count,
        "job_pending_trial_count": job_pending_trial_count,
        "job_result_updated_at_present": job_result_updated_at_present,
        "job_updated_age_seconds": (
            round(job_updated_age_seconds, 3)
            if job_updated_age_seconds is not None
            else None
        ),
        "job_active_stale_seconds_threshold": job_active_stale_seconds_threshold,
        "worker_materialization_probe_only": worker_materialization_probe_only,
        "probe_contract_result_present": probe_contract_result_present,
    }
    marker.update(
        {
            key: value
            for key, value in optional_fields.items()
            if value is not None
        }
    )
    return marker


def summarize_terminal_bench_post_launch_materialization(
    jobs_dir: str | Path,
    *,
    job_name: str | None = None,
    detached_process_state: str | None = None,
    reconcile_stale_active: bool = False,
) -> dict[str, Any]:
    """Summarize whether Harbor produced a pollable job directory after launch.

    The summary intentionally records only booleans, counts, and optional job
    basenames. It does not read logs, task text, trajectories, or file contents,
    and it never echoes local paths.
    """

    jobs_dir_text = str(jobs_dir)
    public_job_name = Path(str(job_name)).name if job_name else ""
    placeholder = "<" in jobs_dir_text or ">" in jobs_dir_text
    process_state = str(detached_process_state or "unknown").strip().lower()
    if process_state not in TERMINAL_BENCH_DETACHED_PROCESS_STATES:
        raise ValueError(
            "detached_process_state must be one of: "
            + ", ".join(sorted(TERMINAL_BENCH_DETACHED_PROCESS_STATES))
        )
    external_handle_observed = process_state != "unknown"
    summary: dict[str, Any] = {
        "schema_version": TERMINAL_BENCH_POST_LAUNCH_MATERIALIZATION_SCHEMA,
        "checked": not placeholder,
        "ready_for_launch_state": False,
        "ready_for_compact_result_ingest": False,
        "ready_for_compact_failure_marker": False,
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
        "external_handle_kind": "detached_worker_process",
        "external_handle_state": process_state,
        "external_handle_observed": external_handle_observed,
        "external_handle_terminal": process_state == "ended",
        "raw_external_handle_payload_recorded": False,
        "stale_active_reconcile_requested": bool(reconcile_stale_active),
    }
    if placeholder:
        return summary

    root = Path(jobs_dir).expanduser()
    jobs_dir_present = root.is_dir()
    summary["jobs_dir_present"] = jobs_dir_present
    if not jobs_dir_present:
        summary["first_blocker"] = "jobs_dir_missing"
        if process_state == "ended":
            summary.update(
                {
                    "first_blocker": "detached_worker_ended_without_jobs_dir",
                    "ready_for_compact_failure_marker": True,
                    "compact_failure_class": (
                        "detached_worker_ended_without_jobs_dir"
                    ),
                    "compact_failure_marker": _terminal_bench_compact_failure_marker(
                        failure_class="detached_worker_ended_without_jobs_dir",
                        evidence_kind="detached_worker_process_state",
                        external_handle_state=process_state,
                        launch_state_countable=False,
                        job_result_present=False,
                        trial_result_present_count=0,
                    ),
                }
            )
        return summary

    if public_job_name:
        candidates = [root / public_job_name]
    else:
        candidates = [path for path in sorted(root.iterdir()) if path.is_dir()]
    existing_candidates = [path for path in candidates if path.is_dir()]
    summary["candidate_job_root_count"] = len(existing_candidates)
    if not existing_candidates:
        summary["first_blocker"] = "job_root_missing"
        if process_state == "ended":
            summary.update(
                {
                    "first_blocker": "detached_worker_ended_without_job_root",
                    "ready_for_compact_failure_marker": True,
                    "compact_failure_class": (
                        "detached_worker_ended_without_job_root"
                    ),
                    "compact_failure_marker": _terminal_bench_compact_failure_marker(
                        failure_class="detached_worker_ended_without_job_root",
                        evidence_kind="detached_worker_process_state",
                        external_handle_state=process_state,
                        launch_state_countable=False,
                        job_result_present=False,
                        trial_result_present_count=0,
                    ),
                }
            )
        return summary

    job_root = existing_candidates[0]
    lock_present = (job_root / "lock.json").is_file()
    result_present = (job_root / "result.json").is_file()
    lock_payload = _load_json_object(job_root / "lock.json") if lock_present else {}
    job_result_payload = (
        _load_json_object(job_root / "result.json") if result_present else {}
    )
    job_result_stats = (
        job_result_payload.get("stats")
        if isinstance(job_result_payload.get("stats"), dict)
        else {}
    )
    job_updated_at = job_result_payload.get("updated_at")
    job_updated_age_seconds = None
    if isinstance(job_updated_at, str) and job_updated_at.strip():
        try:
            job_updated_at_dt = datetime.fromisoformat(
                job_updated_at.replace("Z", "+00:00")
            )
        except ValueError:
            job_updated_at_dt = None
        if job_updated_at_dt is not None:
            job_updated_age_seconds = max(
                0.0,
                (
                    datetime.now(timezone.utc)
                    - job_updated_at_dt.astimezone(timezone.utc)
                ).total_seconds(),
            )
    running_trial_count = _compact_positive_int(
        job_result_stats.get("n_running_trials")
    )
    pending_trial_count = _compact_positive_int(
        job_result_stats.get("n_pending_trials")
    )
    job_finished = bool(job_result_payload.get("finished_at"))
    job_active_without_trial_result = (
        result_present
        and not job_finished
        and (running_trial_count > 0 or pending_trial_count > 0)
    )
    worker_materialization_probe_only = (
        _terminal_bench_lock_worker_materialization_probe_only(lock_payload)
    )
    trial_result_count = sum(
        1
        for child in job_root.iterdir()
        if child.is_dir() and (child / "result.json").is_file()
    )
    job_stale_active_without_trial_result = (
        job_active_without_trial_result
        and trial_result_count <= 0
        and process_state == "ended"
        and job_updated_age_seconds is not None
        and job_updated_age_seconds >= TERMINAL_BENCH_ACTIVE_JOB_STALE_SECONDS
    )
    probe_contract_no_trial_result = (
        worker_materialization_probe_only
        and result_present
        and trial_result_count <= 0
        and process_state == "ended"
    )
    summary.update(
        {
            "job_root_present": True,
            "job_lock_present": lock_present,
            "job_result_present": result_present,
            "job_result_finished": job_finished,
            "job_result_updated_at_present": bool(job_updated_at),
            "job_updated_age_seconds": (
                round(job_updated_age_seconds, 3)
                if job_updated_age_seconds is not None
                else None
            ),
            "job_active_stale_seconds_threshold": (
                TERMINAL_BENCH_ACTIVE_JOB_STALE_SECONDS
            ),
            "job_running_trial_count": running_trial_count,
            "job_pending_trial_count": pending_trial_count,
            "job_active_without_trial_result": job_active_without_trial_result,
            "job_stale_active_without_trial_result": (
                job_stale_active_without_trial_result
            ),
            "trial_result_present_count": trial_result_count,
            "worker_materialization_probe_only": worker_materialization_probe_only,
            "probe_contract_result_present": probe_contract_no_trial_result,
            "ready_for_launch_state": lock_present,
            "ready_for_compact_result_ingest": (
                result_present
                and (trial_result_count > 0 or probe_contract_no_trial_result)
            ),
        }
    )
    if not lock_present:
        summary["first_blocker"] = "job_lock_missing"
    elif job_active_without_trial_result and trial_result_count <= 0:
        summary["first_blocker"] = "ready_for_compact_polling"
        resume_contract = _terminal_bench_active_job_resume_contract(
            process_state=process_state,
            job_stale_active_without_trial_result=(
                job_stale_active_without_trial_result
            ),
            running_trial_count=running_trial_count,
            pending_trial_count=pending_trial_count,
            trial_result_count=trial_result_count,
            result_present=result_present,
            job_finished=job_finished,
        )
        summary["active_job_resume_contract"] = resume_contract
        summary["resume_recommended"] = resume_contract["resume_recommended"]
        if resume_contract["resume_recommended"]:
            summary["first_blocker"] = (
                "resume_materialized_active_job_without_trial_result"
            )
        if process_state == "ended":
            if job_stale_active_without_trial_result:
                active_failure_class = "stale_active_job_without_trial_result"
                active_evidence_kind = "compact_stale_active_job_reconciliation"
            else:
                active_failure_class = (
                    "detached_worker_ended_active_without_trial_result"
                )
                active_evidence_kind = (
                    "detached_worker_active_job_without_trial_result"
                )
            summary["compact_monitor_class"] = active_failure_class
            summary["next_observation_action"] = (
                resume_contract["next_action"]
            )
            if reconcile_stale_active and job_stale_active_without_trial_result:
                summary.update(
                    {
                        "first_blocker": active_failure_class,
                        "ready_for_compact_failure_marker": True,
                        "compact_failure_class": active_failure_class,
                        "compact_failure_marker": _terminal_bench_compact_failure_marker(
                            failure_class=active_failure_class,
                            evidence_kind=active_evidence_kind,
                            external_handle_state=process_state,
                            launch_state_countable=lock_present,
                            job_result_present=result_present,
                            job_result_finished=job_finished,
                            job_running_trial_count=running_trial_count,
                            job_pending_trial_count=pending_trial_count,
                            job_result_updated_at_present=bool(job_updated_at),
                            job_updated_age_seconds=job_updated_age_seconds,
                            job_active_stale_seconds_threshold=(
                                TERMINAL_BENCH_ACTIVE_JOB_STALE_SECONDS
                            ),
                            trial_result_present_count=trial_result_count,
                        ),
                    }
                )
    elif probe_contract_no_trial_result:
        summary.update(
            {
                "first_blocker": "detached_worker_ended_without_trial_result",
                "ready_for_compact_failure_marker": True,
                "compact_failure_class": (
                    "detached_worker_ended_without_trial_result"
                ),
                "compact_failure_marker": _terminal_bench_compact_failure_marker(
                    failure_class="detached_worker_ended_without_trial_result",
                    evidence_kind="worker_materialization_probe_contract",
                    external_handle_state=process_state,
                    launch_state_countable=lock_present,
                    job_result_present=result_present,
                    trial_result_present_count=trial_result_count,
                    worker_materialization_probe_only=True,
                    probe_contract_result_present=True,
                ),
            }
        )
    elif not result_present or trial_result_count <= 0:
        if process_state == "ended":
            summary.update(
                {
                    "first_blocker": "detached_worker_ended_without_trial_result",
                    "ready_for_compact_failure_marker": True,
                    "compact_failure_class": (
                        "detached_worker_ended_without_trial_result"
                    ),
                    "compact_failure_marker": _terminal_bench_compact_failure_marker(
                        failure_class="detached_worker_ended_without_trial_result",
                        evidence_kind="detached_worker_process_state",
                        external_handle_state=process_state,
                        launch_state_countable=lock_present,
                        job_result_present=result_present,
                        trial_result_present_count=trial_result_count,
                    ),
                }
            )
        else:
            summary["first_blocker"] = "ready_for_compact_polling"
    else:
        summary["first_blocker"] = "ready_for_compact_result_ingest"
    return summary


def _terminal_bench_launch_timeout_multiplier_policy(
    argv: list[Any],
) -> dict[str, Any]:
    """Return public-safe timeout multiplier facts from a launch argv."""

    fields = {
        "--timeout-multiplier": "timeout_multiplier",
        "--agent-timeout-multiplier": "agent_timeout_multiplier",
        "--verifier-timeout-multiplier": "verifier_timeout_multiplier",
        "--agent-setup-timeout-multiplier": "agent_setup_timeout_multiplier",
        "--environment-build-timeout-multiplier": (
            "environment_build_timeout_multiplier"
        ),
    }
    argv_text = [str(item) for item in argv]
    multipliers: dict[str, float] = {}
    for flag, key in fields.items():
        parsed = _optional_float(_invocation_arg_value(argv_text, flag))
        if parsed is not None:
            multipliers[key] = parsed

    non_default = any(
        not _is_default_timeout_multiplier(value)
        for value in multipliers.values()
    )
    return {
        "schema_version": "terminal_bench_launch_timeout_multiplier_policy_v0",
        "any_timeout_multiplier_present": bool(multipliers),
        "non_default_timeout_multiplier_present": non_default,
        "agent_setup_timeout_multiplier_present": (
            "agent_setup_timeout_multiplier" in multipliers
        ),
        "changes_official_benchmark_timeout": non_default,
        "leaderboard_claim_allowed": not non_default,
        "raw_argv_recorded": False,
        "multipliers": multipliers,
    }


def _terminal_bench_agent_setup_readiness(
    argv: list[Any],
    timeout_policy: dict[str, Any],
    *,
    setup_timeout_repair_profile: bool = False,
) -> dict[str, Any]:
    """Return compact setup-readiness facts for managed Codex launches.

    This is intentionally launch-contract level only. It records whether the
    worker setup path may install Codex during Harbor setup, without reading
    private logs, credential values, task text, or trajectories.
    """

    kwargs = agent_kwargs_from_invocation(argv)
    strategy = (
        kwargs.get("goal_harness_codex_install_strategy")
        or TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    )
    if strategy not in TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES:
        strategy = "unknown"
    worker_codex_materialization_strategy = str(
        kwargs.get("goal_harness_worker_codex_materialization_strategy") or ""
    ).strip()
    if (
        worker_codex_materialization_strategy
        and worker_codex_materialization_strategy
        not in TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES
    ):
        worker_codex_materialization_strategy = "unknown"
    worker_path_preprovisioned = (
        worker_codex_materialization_strategy
        == TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_WORKER_PATH
    )
    runtime_install_extended = (
        worker_codex_materialization_strategy
        == TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGY_RUNTIME_EXTENDED
    )

    multipliers = timeout_policy.get("multipliers")
    setup_multiplier = None
    if isinstance(multipliers, dict):
        raw_multiplier = multipliers.get("agent_setup_timeout_multiplier")
        if isinstance(raw_multiplier, (int, float)) and not isinstance(
            raw_multiplier, bool
        ):
            setup_multiplier = raw_multiplier

    managed_agent = bool(_invocation_arg_value(argv, "--agent-import-path"))
    worker_bridge_requested = kwargs.get("goal_harness_cli_bridge_enabled") == "true"
    worker_materialization_probe_only = (
        kwargs.get("goal_harness_worker_materialization_probe_only") == "true"
    )
    setup_timeout_budget_explicit = setup_multiplier is not None
    codex_preflight_timeout = _optional_positive_int(
        kwargs.get("goal_harness_codex_preflight_timeout_sec")
    )
    codex_preflight_timeout_explicit = codex_preflight_timeout is not None
    fail_fast_install_strategy = (
        strategy == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
    )
    runtime_install_strategy = (
        strategy
        == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    )
    if (
        setup_timeout_repair_profile
        and runtime_install_strategy
        and not runtime_install_extended
    ):
        first_blocker = "setup_timeout_repair_profile_runtime_install_disallowed"
        next_action = (
            "repair launch profile to use require_existing_codex before "
            "same-task repeat, or declare runtime_install_extended_setup"
        )
    elif not managed_agent:
        first_blocker = "managed_codex_agent_import_path_missing"
        next_action = "repair managed Codex agent launch command"
    elif not setup_timeout_budget_explicit:
        first_blocker = "agent_setup_timeout_budget_missing"
        next_action = "declare an explicit agent setup timeout budget before private repeat"
    elif fail_fast_install_strategy and not codex_preflight_timeout_explicit:
        first_blocker = "codex_preflight_timeout_missing"
        next_action = (
            "declare a bounded Codex CLI preflight timeout before same-task "
            "repeat after setup timeout"
        )
    elif fail_fast_install_strategy and not worker_path_preprovisioned:
        first_blocker = "codex_worker_materialization_strategy_missing"
        next_action = (
            "materialize Codex on the worker PATH, or use a separate extended "
            "runtime-install materialization profile, before rerunning the same "
            "Terminal-Bench case"
        )
    elif runtime_install_strategy:
        if runtime_install_extended and setup_timeout_budget_explicit:
            first_blocker = "ready_for_runtime_codex_materialization_probe"
            next_action = (
                "run exactly one compact no-upload baseline with extended setup "
                "budget and ingest the setup diagnostic before any treatment"
            )
        else:
            first_blocker = "runtime_codex_install_can_exceed_setup_budget"
            next_action = (
                "use require_existing_codex with worker-path materialization, or "
                "declare runtime_install_extended_setup with an explicit setup "
                "budget before same-task repeat after setup timeout"
            )
    elif fail_fast_install_strategy:
        first_blocker = "ready_for_fail_fast_codex_setup_probe"
        next_action = (
            "run private setup readiness probe or same-task repeat with fail-fast "
            "Codex install strategy"
        )
    else:
        first_blocker = "codex_install_strategy_unknown"
        next_action = "select a known Codex setup strategy before private repeat"

    return {
        "schema_version": TERMINAL_BENCH_AGENT_SETUP_READINESS_SCHEMA,
        "managed_codex_agent": managed_agent,
        "worker_bridge_requested": worker_bridge_requested,
        "worker_materialization_probe_only": worker_materialization_probe_only,
        "setup_timeout_repair_profile": setup_timeout_repair_profile,
        "codex_install_strategy": strategy,
        "runtime_codex_install_allowed": runtime_install_strategy,
        "fail_fast_install_strategy": fail_fast_install_strategy,
        "setup_timeout_budget_explicit": setup_timeout_budget_explicit,
        "agent_setup_timeout_multiplier": setup_multiplier,
        "codex_preflight_timeout_explicit": codex_preflight_timeout_explicit,
        "codex_preflight_timeout_sec": codex_preflight_timeout,
        "worker_codex_materialization_strategy": (
            worker_codex_materialization_strategy
        ),
        "worker_codex_materialization_strategy_declared": bool(
            worker_codex_materialization_strategy
        ),
        "worker_path_preprovisioned_declared": worker_path_preprovisioned,
        "runtime_install_extended_setup_declared": runtime_install_extended,
        "same_task_repeat_after_setup_timeout_allowed": (
            (
                fail_fast_install_strategy
                and setup_timeout_budget_explicit
                and codex_preflight_timeout_explicit
                and worker_path_preprovisioned
            )
            or (
                runtime_install_strategy
                and setup_timeout_budget_explicit
                and runtime_install_extended
            )
        ),
        "setup_materialization_blocks_launch": first_blocker not in {
            "ready_for_fail_fast_codex_setup_probe",
            "ready_for_runtime_codex_materialization_probe",
        },
        "first_blocker": first_blocker,
        "next_action_after_setup_timeout": next_action,
        "setup_failure_before_worker_counts_as_case_progress": False,
        "raw_argv_recorded": False,
        "raw_env_recorded": False,
        "raw_logs_read": False,
        "task_text_read": False,
        "trajectory_read": False,
        "credential_values_recorded": False,
    }


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
    environment_host_allowlist_count = sum(
        1 for value in argv if value == "--allow-environment-host"
    )
    pythonpath_value = env.get("PYTHONPATH") if isinstance(env.get("PYTHONPATH"), str) else ""
    project_root = _private_runner_goal_harness_project_root()
    timeout_policy = _terminal_bench_launch_timeout_multiplier_policy(argv)
    setup_timeout_repair_profile = launch.get("setup_timeout_repair_profile") is True
    repair_profile = (
        launch.get("repair_profile")
        if isinstance(launch.get("repair_profile"), dict)
        else {}
    )
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
        "goal_harness_managed_codex_requested": (
            "goal_harness_mode=goal_harness_managed_codex" in argv
        ),
        "codex_goal_mode_baseline_requested": (
            "goal_harness_mode=" + TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
        )
        in argv,
        "codex_goal_mode_invocation_surface": (
            "slash_command"
            if (
                "goal_harness_mode="
                + TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
            )
            in argv
            else ""
        ),
        "goal_harness_access_packet_absent": (
            "goal_harness_access_packet_mode="
            + TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        )
        in argv,
        "goal_harness_worker_bridge_requested": "goal_harness_cli_bridge_enabled=true"
        in argv,
        "worker_materialization_probe_only": (
            "goal_harness_worker_materialization_probe_only=true" in argv
        ),
        "active_user_writable_mount_requested": bool(active_user_mounts),
        "active_user_writable_mount_count": len(active_user_mounts),
        "active_user_writable_mount_target_present": bool(active_user_mounts),
        "no_upload_boundary": bool(boundary.get("no_upload")),
        "submit_eligible": bool(boundary.get("submit_eligible")),
        "env_path_present": bool(path_value),
        "env_probe_path_coverage": probe_coverage,
        "env_probe_path_coverage_count": sum(1 for ready in probe_coverage.values() if ready),
        "env_pythonpath_present": bool(pythonpath_value),
        "goal_harness_project_root_pythonpath_present": project_root
        in pythonpath_value.split(os.pathsep),
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
        "environment_host_allowlist_count": environment_host_allowlist_count,
        "codex_runtime_install_network_allowlist_present": (
            environment_host_allowlist_count > 0
        ),
        "setup_timeout_repair_profile": setup_timeout_repair_profile,
        "repair_profile": repair_profile,
        "timeout_multiplier_policy": timeout_policy,
        "agent_setup_readiness": _terminal_bench_agent_setup_readiness(
            argv,
            timeout_policy,
            setup_timeout_repair_profile=setup_timeout_repair_profile,
        ),
        "closeout_command_templates": _terminal_bench_run_ledger_closeout_templates(),
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
            "worker_benchmark_run_json_validation_scope_required: true",
            "worker_benchmark_run_json_validation_scope_values: "
            "worker_bridge_connectivity,environment_ready,worker_case_success,"
            "official_verifier_result",
            "worker_benchmark_run_json_bridge_connectivity_is_not_case_success: true",
            "worker_benchmark_run_json_claim_boundary_required: true",
            "worker_benchmark_run_json_claim_boundary_required_fields: "
            "bridge_connectivity_claim_allowed,case_success_claim_allowed,"
            "official_score_claim_allowed,leaderboard_claim_allowed,"
            "forbidden_claims",
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
    if mode == "codex-goal-mode":
        return {
            "event_mode": "codex_goal_mode_baseline_cli_dry_run",
            "worker_mode": "codex_goal_mode_baseline",
            "goal_harness_inside_case": False,
            "case_semantics_changed_by_harness": False,
            "official_score_comparable_to_native_codex": False,
            "official_score_comparable_to_goal_harness_treatment": True,
            "model_plus_harness_pair": False,
            "control_plane_score_applicable": False,
            "trace_publicness": "public_cli_dry_run",
            "goal_harness_interface_surface": "none",
            "goal_harness_cli_bridge_available": False,
            "goal_harness_actual_use_observed": False,
            "startup_surface_calibration": False,
            "hardened_install_surface": False,
            "hardened_install_baseline": False,
            "codex_goal_mode_baseline": True,
            "first_blocker": "codex_goal_mode_baseline_cli_skeleton_only_no_real_case",
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
    treatment_scenario_id: str = "codex_goal_harness",
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
            "run the Goal Harness treatment arm on the same compactly verified task"
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
    codex_install_strategy: str = (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ),
    codex_preflight_timeout_sec: int | None = None,
    worker_codex_materialization_strategy: str | None = None,
    worker_materialization_probe_only: bool = False,
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
    if codex_install_strategy not in TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES:
        raise ValueError(
            "codex_install_strategy must be one of: "
            + ", ".join(TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES)
        )
    if (
        worker_codex_materialization_strategy is not None
        and worker_codex_materialization_strategy
        not in TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES
    ):
        raise ValueError(
            "worker_codex_materialization_strategy must be one of: "
            + ", ".join(TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES)
        )
    parsed_codex_preflight_timeout = _optional_positive_int(
        codex_preflight_timeout_sec
    )
    if codex_preflight_timeout_sec is not None and parsed_codex_preflight_timeout is None:
        raise ValueError("codex_preflight_timeout_sec must be a positive integer")
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
        "--agent-kwarg",
        f"goal_harness_codex_install_strategy={codex_install_strategy}",
    ]
    if (
        codex_install_strategy
        == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ):
        for host in TERMINAL_BENCH_CODEX_RUNTIME_INSTALL_ALLOW_ENVIRONMENT_HOSTS:
            command.extend(["--allow-environment-host", host])
    if parsed_codex_preflight_timeout is not None:
        command.extend(
            [
                "--agent-kwarg",
                "goal_harness_codex_preflight_timeout_sec="
                f"{parsed_codex_preflight_timeout}",
            ]
        )
    if worker_codex_materialization_strategy:
        command.extend(
            [
                "--agent-kwarg",
                "goal_harness_worker_codex_materialization_strategy="
                f"{worker_codex_materialization_strategy}",
            ]
        )
    if worker_materialization_probe_only:
        command.extend(
            [
                "--agent-kwarg",
                "goal_harness_worker_materialization_probe_only=true",
            ]
        )
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

def build_skillsbench_benchmark_run(
    *,
    route: str = SKILLSBENCH_DEFAULT_ROUTE,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    task_id: str = SKILLSBENCH_DEFAULT_TASK,
    agent: str = "codex",
    model: str = SKILLSBENCH_DEFAULT_MODEL,
) -> dict[str, Any]:
    """Build a compact no-run SkillsBench benchmark_run_v0 skeleton."""

    if agent != "codex":
        raise ValueError("SkillsBench skeleton currently supports agent=codex only")
    if route not in SKILLSBENCH_ROUTES:
        raise ValueError(f"unsupported SkillsBench route: {route}")
    contract = skillsbench_route_contract(route)
    job_name = skillsbench_job_name(dataset, task_id, route)
    validation: dict[str, Any] = {
        "cli_skeleton_present": True,
        "skillsbench_route_declared": True,
        "compact_ingest_route_declared": True,
        "no_real_codex_invoked": True,
        "no_benchflow_invoked": True,
        "no_docker_or_cloud_invoked": True,
        "no_model_api_invoked": True,
        "no_leaderboard_upload_requested": True,
        "paths_redacted": True,
    }
    benchmark_run: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": contract["source_runner"],
        "benchmark_id": dataset,
        "job_name": job_name,
        "mode": contract["mode"],
        "route": route,
        "agent": {
            "name": agent,
            "model": model,
            "kwargs_keys": (
                [
                    "codex_goal_mode_invocation_surface",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "codex-goal-mode-baseline"
                else [
                    "ordinary_codex_cli_actor",
                    "fixed_blind_loop_budget",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "codex-acp-blind-loop-baseline"
                else [
                    "ordinary_codex_cli_actor",
                    "raw_codex_autonomous_max5",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "raw-codex-autonomous-max5"
                else [
                    "ordinary_codex_cli_actor",
                    "goal_harness_product_mode",
                    "goal_state_todos_replan_cli",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "goal-harness-product-mode"
                else [
                    "ordinary_codex_cli_actor",
                    "goal_harness_blind_loop",
                    "official_feedback_withheld",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "goal-harness-blind-loop-treatment"
                else [
                    "ordinary_codex_cli_actor",
                    "goal_harness_automation_loop",
                    "reward_feedback_ablation",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if route == "automation-loop-treatment"
                else [
                    "skillsbench_curated_skills_visible",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
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
        "interaction_counters": {
            "schema_version": "skillsbench_interaction_counters_v0",
            "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
            "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
            "native_goal_mode_requested": contract["native_goal_mode_requested"],
            "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
            "native_goal_mode_confirmation_status": contract[
                "native_goal_mode_confirmation_status"
            ],
            "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
            "curated_skills_visible": contract["curated_skills_visible"],
            "product_mode": contract.get("product_mode") is True,
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "goal_harness_state_reads": 0,
            "goal_harness_state_writes": 0,
            "goal_harness_case_state_reads": 0,
            "goal_harness_case_state_writes": 0,
            "heartbeat_count": 0,
            "case_goal_state_packet_present": route == "goal-harness-product-mode",
            "case_goal_state_init_required": route == "goal-harness-product-mode",
            "case_goal_state_initialized_before_agent": False,
            "case_goal_state_init_status": (
                "not_run_adapter_skeleton"
                if route == "goal-harness-product-mode"
                else ""
            ),
            "case_goal_state_schema_version": (
                BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
                if route == "goal-harness-product-mode"
                else ""
            ),
            "case_goal_state_path": (
                SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH
                if route == "goal-harness-product-mode"
                else ""
            ),
            "declared_done_requires_no_remaining_goals": route
            == "goal-harness-product-mode",
            "case_result_writeback": "not_run_adapter_skeleton",
            "counter_trust_level": "adapter_contract_fixture",
        },
        "episode_policy": {
            "schema_version": "skillsbench_episode_policy_v0",
            "route": route,
            "outer_controller": (
                "goal_harness_blind_automation_loop"
                if route == "goal-harness-blind-loop-treatment"
                else "goal_harness_product_mode"
                if route == "goal-harness-product-mode"
                else "reward_feedback_automation_loop_ablation"
                if route == "automation-loop-treatment"
                else "raw_codex_autonomous_max5"
                if route == "raw-codex-autonomous-max5"
                else "fixed_blind_loop_runner"
                if route == "codex-acp-blind-loop-baseline"
                else "runner_only"
            ),
            "inner_case_actor": (
                "ordinary_codex_acp_agent"
                if route
                in {
                    "automation-loop-treatment",
                    "goal-harness-blind-loop-treatment",
                    "codex-acp-blind-loop-baseline",
                    "raw-codex-autonomous-max5",
                    "goal-harness-product-mode",
                }
                else "codex_acp_goal_prompt_request_unconfirmed_native_goal_mode"
                if route == "codex-goal-mode-baseline"
                else "codex_acp_with_curated_skills"
            ),
            "blind_loop": contract["blind_loop"],
            "product_mode": contract.get("product_mode") is True,
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "verifier_output_tail_forwarded_by_default": False,
            "raw_trace_recorded": False,
            "raw_task_text_recorded": False,
            "does_not_upload_or_submit": True,
        },
        "trials": [
            {
                "task_id": task_id,
                "trial_name": f"{task_id}_{route}",
                "source": dataset,
                "exception_type": contract["first_blocker"],
                "reward": {"reward": 0},
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
            "raw_solutions_recorded": False,
        },
        "mode_contract": {
            "requested_route": route,
            "arm_id": contract["arm_id"],
            "case_semantics_changed_by_harness": contract[
                "case_semantics_changed_by_harness"
            ],
            "goal_harness_inside_case": contract["goal_harness_inside_case"],
            "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
            "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
            "native_goal_mode_requested": contract["native_goal_mode_requested"],
            "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
            "native_goal_mode_confirmation_status": contract[
                "native_goal_mode_confirmation_status"
            ],
            "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
            "skillsbench_route_semantics": contract["skillsbench_route_semantics"],
            "curated_skills_visible": contract["curated_skills_visible"],
            "product_mode": contract.get("product_mode") is True,
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "official_score_comparable_to_native_codex": contract[
                "official_score_comparable_to_native_codex"
            ],
            "official_score_comparable_to_goal_harness_treatment": contract[
                "official_score_comparable_to_goal_harness_treatment"
            ],
            "leaderboard_evidence": False,
        },
        "evidence_files": [
            "doc:automation-loop-treatment-case-selection-20260614.md",
            "doc:benchmark-run-ledger-v0.md",
            "smoke:skillsbench-benchmark-run-smoke.py",
        ],
        "resume_or_inspect_commands": [
            (
                "goal-harness benchmark run skillsbench "
                f"--skillsbench-route {route} --include-task-name {task_id}"
            ),
            (
                "goal-harness benchmark run-ledger-upsert "
                "--benchmark-run-json <skillsbench-compact-benchmark-run-v0.json>"
            ),
        ],
        "real_run": False,
        "submit_eligible": False,
        "official_task_score": {
            "kind": "not_run",
            "value": None,
        },
        "case_semantics_changed_by_harness": contract[
            "case_semantics_changed_by_harness"
        ],
        "goal_harness_inside_case": contract["goal_harness_inside_case"],
        "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
        "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
        "native_goal_mode_requested": contract["native_goal_mode_requested"],
        "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
        "native_goal_mode_confirmation_status": contract[
            "native_goal_mode_confirmation_status"
        ],
        "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
        "skillsbench_route_semantics": contract["skillsbench_route_semantics"],
        "curated_skills_visible": contract["curated_skills_visible"],
        "product_mode": contract.get("product_mode") is True,
        "blind_loop": contract["blind_loop"],
        "official_feedback_blinded": contract["official_feedback_blinded"],
        "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
        "official_score_comparable_to_native_codex": contract[
            "official_score_comparable_to_native_codex"
        ],
        "official_score_comparable_to_goal_harness_treatment": contract[
            "official_score_comparable_to_goal_harness_treatment"
        ],
        "leaderboard_evidence": False,
        "trace_publicness": "public_skillsbench_adapter_skeleton",
        "first_blocker": contract["first_blocker"],
        "stop_conditions": [
            "do_not_run_benchflow_from_skeleton",
            "do_not_invoke_real_codex_from_skeleton",
            "do_not_start_docker_or_cloud_from_skeleton",
            "do_not_call_model_api_from_skeleton",
            "do_not_read_raw_task_prompt_solution_or_trajectory",
            "do_not_upload_or_submit_leaderboard",
            "do_not_record_secrets_or_raw_sessions",
        ],
    }
    return benchmark_run


def _skillsbench_controller_trace_counters(
    controller_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(controller_trace, dict):
        return {}
    schema_version = str(controller_trace.get("schema_version") or "")
    if schema_version != "skillsbench_goal_harness_controller_trace_v0":
        return {}

    def count(key: str) -> int:
        value = controller_trace.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return 0

    def positive_int(key: str) -> int | None:
        value = controller_trace.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return None

    def round_reward_records() -> list[dict[str, Any]]:
        raw_records = controller_trace.get("round_rewards")
        if not isinstance(raw_records, list):
            return []
        records: list[dict[str, Any]] = []
        seen_rounds: set[int] = set()
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            agent_round = item.get("agent_round")
            if (
                not isinstance(agent_round, int)
                or isinstance(agent_round, bool)
                or agent_round <= 0
                or agent_round in seen_rounds
            ):
                continue
            seen_rounds.add(agent_round)
            record: dict[str, Any] = {"agent_round": agent_round}
            for field in ("reward_present", "passed"):
                if isinstance(item.get(field), bool):
                    record[field] = item[field]
            reward = item.get("reward")
            if isinstance(reward, (int, float)) and not isinstance(reward, bool):
                record["reward"] = float(reward)
            tool_calls = item.get("tool_calls")
            if (
                isinstance(tool_calls, int)
                and not isinstance(tool_calls, bool)
                and tool_calls >= 0
            ):
                record["tool_calls"] = tool_calls
            records.append(record)
        return sorted(records, key=lambda record: record["agent_round"])

    reward_records = round_reward_records()
    first_success_round = positive_int("first_success_round")
    if first_success_round is None:
        for record in reward_records:
            if record.get("passed") is True:
                first_success_round = int(record["agent_round"])
                break

    counters: dict[str, Any] = {
        "controller_trace_present": True,
        "controller_trace_schema_version": schema_version,
        "controller_trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
        "controller_action_decisions": count("controller_action_decisions"),
        "initial_prompt_count": count("initial_prompt_count"),
        "followup_prompt_count": count("followup_prompt_count"),
        "stop_decision_count": count("stop_decision_count"),
        "reward_observation_count": count("reward_observation_count"),
        "round_reward_count": len(reward_records),
        "official_success_observed": controller_trace.get("official_success_observed")
        is True
        or first_success_round is not None,
        "official_success_observation_count": count(
            "official_success_observation_count"
        ),
        "first_success_round": first_success_round,
        "verifier_feedback_observation_count": count(
            "verifier_feedback_observation_count"
        ),
        "official_feedback_blinded_count": count("official_feedback_blinded_count"),
        "official_feedback_forwarded": controller_trace.get(
            "official_feedback_forwarded"
        )
        is True,
        "blind_loop": controller_trace.get("blind_loop") is True,
        "product_mode": controller_trace.get("product_mode") is True,
        "case_goal_state_packet_present": controller_trace.get(
            "case_goal_state_packet_present"
        )
        is True,
        "case_goal_state_init_required": controller_trace.get(
            "case_goal_state_init_required"
        )
        is True,
        "case_goal_state_initialized_before_agent": controller_trace.get(
            "case_goal_state_initialized_before_agent"
        )
        is True,
        "declared_done_requires_no_remaining_goals": controller_trace.get(
            "declared_done_requires_no_remaining_goals"
        )
        is True,
        "agent_declared_done": controller_trace.get("agent_declared_done") is True,
        "agent_declared_no_remaining_goals": controller_trace.get(
            "agent_declared_no_remaining_goals"
        )
        is True,
        "max_rounds_budget": count("max_rounds_budget"),
        "goal_harness_state_reads": count("goal_harness_state_reads"),
        "goal_harness_state_writes": count("goal_harness_state_writes"),
        "goal_harness_case_state_reads": count("goal_harness_case_state_reads"),
        "goal_harness_case_state_writes": count("goal_harness_case_state_writes"),
        "heartbeat_count": count("heartbeat_count"),
        "raw_task_text_recorded": controller_trace.get("raw_task_text_recorded")
        is True,
        "raw_verifier_output_recorded": controller_trace.get(
            "raw_verifier_output_recorded"
        )
        is True,
        "raw_agent_trajectory_recorded": controller_trace.get(
            "raw_agent_trajectory_recorded"
        )
        is True,
    }
    last_decision = _public_safe_benchmark_label(
        controller_trace.get("last_decision") or ""
    )
    if last_decision:
        counters["last_decision"] = last_decision
    init_status = _public_safe_benchmark_label(
        controller_trace.get("case_goal_state_init_status") or ""
    )
    if init_status:
        counters["case_goal_state_init_status"] = init_status
    case_state_schema = _public_safe_benchmark_label(
        controller_trace.get("case_goal_state_schema_version") or ""
    )
    if case_state_schema:
        counters["case_goal_state_schema_version"] = case_state_schema
    case_state_path = str(controller_trace.get("case_goal_state_path") or "")
    if (
        "/.codex/goals/" in case_state_path
        and case_state_path.endswith("/ACTIVE_GOAL_STATE.md")
        and not re.search(r"^/(Users|private|var/folders)/", case_state_path)
    ):
        counters["case_goal_state_path"] = case_state_path
    declared_done_round = positive_int("declared_done_round")
    if declared_done_round is not None:
        counters["declared_done_round"] = declared_done_round
    declared_done_score = controller_trace.get("declared_done_score")
    if (
        isinstance(declared_done_score, (int, float))
        and not isinstance(declared_done_score, bool)
    ):
        counters["declared_done_score"] = float(declared_done_score)
    if reward_records:
        counters["round_rewards"] = reward_records
    trajectory_summary = (
        controller_trace.get("acp_trajectory_summary")
        if isinstance(controller_trace.get("acp_trajectory_summary"), dict)
        else {}
    )
    if trajectory_summary:
        counters["acp_trajectory_summary"] = {
            key: trajectory_summary.get(key)
            for key in (
                "schema_version",
                "private_trajectory_present",
                "raw_text_copied_to_public",
                "event_count",
                "round_count",
                "user_message_count",
                "agent_message_count",
                "tool_call_count",
                "action_category_counts",
                "round_action_category_counts",
                "goal_harness_cli_call_count",
                "goal_harness_cli_calls",
                "goal_harness_cli_state_usage_counts",
                "goal_harness_cli_state_read_count",
                "goal_harness_cli_state_write_count",
                "goal_harness_case_state_path_count",
                "goal_harness_case_state_read_count",
                "goal_harness_case_state_write_count",
                "protected_path_mention_count",
                "protected_path_edit_signal_count",
                "codex_acp_text_present",
                "codex_acp_text_bytes",
            )
            if trajectory_summary.get(key) is not None
        }
    return counters


def _round_reward_trace_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_records: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        agent_round = item.get("agent_round")
        reward = item.get("reward")
        if (
            not isinstance(agent_round, int)
            or isinstance(agent_round, bool)
            or agent_round <= 0
            or not isinstance(reward, (int, float))
            or isinstance(reward, bool)
        ):
            continue
        numeric_records.append(
            {
                "agent_round": agent_round,
                "reward": float(reward),
                "passed": item.get("passed") if isinstance(item.get("passed"), bool) else reward >= 1,
            }
        )
    if not numeric_records:
        return {}
    by_round = sorted(numeric_records, key=lambda item: item["agent_round"])
    best = max(by_round, key=lambda item: (item["reward"], -item["agent_round"]))
    final = by_round[-1]
    return {
        "final_round": final["agent_round"],
        "final_round_reward": final["reward"],
        "final_round_passed": final["passed"],
        "best_reward_round": best["agent_round"],
        "best_round_reward": best["reward"],
        "best_round_passed": best["passed"],
        "best_round_is_final": final["reward"] == best["reward"],
        "loop_score_policy": "best_round_for_offline_controller_analysis",
        "official_score_policy": "final_workspace_official_result",
    }


def _post_success_controller_trace_score(
    round_reward_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(round_reward_trace, dict):
        return {}
    if round_reward_trace.get("success_observed") is not True:
        return {}
    reward = round_reward_trace.get("best_round_reward")
    if not isinstance(reward, (int, float)) or isinstance(reward, bool):
        return {}
    round_index = round_reward_trace.get("best_reward_round")
    return {
        "value": float(reward),
        "passed": reward >= 1.0,
        "round": round_index
        if isinstance(round_index, int) and not isinstance(round_index, bool)
        else None,
        "policy": "best_round_for_post_success_acp_closeout_recovery",
    }


def build_skillsbench_benchflow_result_benchmark_run(
    result_json_path: str | Path,
    *,
    route: str = SKILLSBENCH_DEFAULT_ROUTE,
    dataset: str = SKILLSBENCH_DEFAULT_DATASET,
    agent: str = "codex",
    model: str | None = None,
    runner_warning_labels: Iterable[str] | None = None,
    controller_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a public-safe benchmark_run_v0 from an official SkillsBench result.

    The official BenchFlow result.json already contains the compact fields we
    need for ledgering: task name, agent/model, reward, error, tool-call count,
    and timing. This reducer deliberately reads only result.json and sibling
    timing.json; it does not read prompts, trajectories, verifier stdout, task
    text, screenshots, or credential material.
    """

    result_path = Path(result_json_path).expanduser()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("SkillsBench result.json must contain a JSON object")

    task_id = str(result.get("task_name") or "").strip()
    if not task_id:
        raise ValueError("SkillsBench result.json is missing task_name")

    contract = skillsbench_route_contract(route)
    observed_agent = str(result.get("agent") or result.get("agent_name") or agent)
    if observed_agent not in {"codex", "codex-acp"}:
        raise ValueError(
            "SkillsBench BenchFlow ingest currently supports codex/codex-acp only"
        )
    requested_model = str(model or result.get("model") or SKILLSBENCH_DEFAULT_MODEL)
    observed_model = str(result.get("model") or requested_model)
    warning_labels = [
        label
        for label in (
            _public_safe_benchmark_label(item)
            for item in (runner_warning_labels or [])
        )
        if label
    ]
    model_control_status = "reported_model_from_result_metadata"
    actual_model_verified = False
    actual_model_source = "official_skillsbench_result_model_field"
    if CODEX_ACP_SET_MODEL_UNSUPPORTED_LABEL in warning_labels:
        model_control_status = "requested_model_not_enforced_by_acp"
        actual_model_verified = False
        actual_model_source = "codex_acp_default_or_launch_config"
    rollout_name = str(result.get("rollout_name") or f"{task_id}_{route}")

    rewards = result.get("rewards") if isinstance(result.get("rewards"), dict) else {}
    reward_value = rewards.get("reward")
    if not isinstance(reward_value, (int, float)) or isinstance(reward_value, bool):
        reward_value = None
    official_passed = bool(reward_value is not None and reward_value >= 1)

    timing_path = result_path.with_name("timing.json")
    timing: dict[str, Any] = {}
    if timing_path.exists():
        raw_timing = json.loads(timing_path.read_text(encoding="utf-8"))
        if isinstance(raw_timing, dict):
            timing = raw_timing
    timing_summary = {
        key: value
        for key, value in timing.items()
        if key
        in {
            "environment_setup",
            "agent_setup",
            "agent_execution",
            "verifier",
            "total",
        }
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    }

    error = result.get("error")
    verifier_error = result.get("verifier_error")
    error_text = str(error).strip() if error else ""
    verifier_error_text = str(verifier_error).strip() if verifier_error else ""
    failure_labels: list[str] = []
    exception_type = "none"
    score_failure_attribution = "none"
    runner_score_failure_attribution = "none"
    if error_text:
        exception_type, score_failure_attribution, failure_labels = (
            skillsbench_runner_error_attribution(error_text)
        )
        runner_score_failure_attribution = score_failure_attribution
    if verifier_error_text:
        exception_type = "skillsbench_verifier_error"
        failure_labels.append("verifier_infrastructure_failure")
        score_failure_attribution = "verifier_infrastructure_failure"

    n_tool_calls = result.get("n_tool_calls")
    tool_calls = n_tool_calls if isinstance(n_tool_calls, int) else 0
    partial_trajectory = bool(result.get("partial_trajectory") is True)
    if reward_value == 0 and not failure_labels and not partial_trajectory:
        failure_labels.append("official_verifier_solution_failure")
        score_failure_attribution = "official_verifier_solution_failure"
    elif reward_value == 0 and not failure_labels:
        failure_labels.append("official_score_zero_case_failure")
    real_run_completed = not error_text and not verifier_error_text
    job_name = skillsbench_job_name(dataset, task_id, route)
    controller_counters = _skillsbench_controller_trace_counters(controller_trace)
    controller_trace_present = bool(controller_counters.get("controller_trace_present"))
    controller_raw_material_recorded = bool(
        controller_counters.get("raw_task_text_recorded")
        or controller_counters.get("raw_verifier_output_recorded")
        or controller_counters.get("raw_agent_trajectory_recorded")
    )
    counter_trust_level = "official_benchflow_compact_result"
    if controller_trace_present:
        counter_trust_level = (
            "official_benchflow_compact_result_plus_goal_harness_controller_trace"
        )
    evidence_files = [
        "official_skillsbench:result.json",
        "official_skillsbench:timing.json" if timing else "official_skillsbench:timing_missing",
    ]
    if controller_trace_present:
        evidence_files.append("goal_harness:controller_trace.public.json")
    trajectory_summary = (
        controller_counters.get("acp_trajectory_summary")
        if isinstance(controller_counters.get("acp_trajectory_summary"), dict)
        else {}
    )
    if trajectory_summary:
        evidence_files.append("goal_harness:acp_trajectory_summary")
    runner_failure: dict[str, Any] | None = None
    if error_text:
        runner_failure = {
            "schema_version": "skillsbench_runner_failure_v0",
            "exception_type": exception_type,
            "failure_class": runner_score_failure_attribution,
            "raw_error_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        }
        runner_failure_fingerprint = skillsbench_runner_error_fingerprint(
            error_text
        )
    round_reward_records = controller_counters.get("round_rewards")
    if not isinstance(round_reward_records, list):
        round_reward_records = []
    first_success_round = controller_counters.get("first_success_round")
    first_success_round_value = (
        first_success_round
        if isinstance(first_success_round, int)
        and not isinstance(first_success_round, bool)
        and first_success_round > 0
        else None
    )
    round_reward_trace: dict[str, Any] | None = None
    if controller_trace_present:
        round_stats = _round_reward_trace_stats(round_reward_records)
        round_reward_trace = {
            "schema_version": "benchmark_round_reward_trace_v0",
            "source": "goal_harness_controller_trace",
            "round_index_origin": "agent_round_1_is_first_completed_agent_attempt",
            "records": round_reward_records,
            "first_success_round": first_success_round_value,
            "success_observed": controller_counters.get(
                "official_success_observed",
                False,
            ),
            "max_rounds_budget": controller_counters.get("max_rounds_budget", 0),
            "official_feedback_returned_to_agent": contract[
                "reward_feedback_forwarded"
            ],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "agent_declared_done": controller_counters.get("agent_declared_done")
            is True,
            "declared_done_requires_no_remaining_goals": controller_counters.get(
                "declared_done_requires_no_remaining_goals"
            )
            is True,
            "agent_declared_no_remaining_goals": controller_counters.get(
                "agent_declared_no_remaining_goals"
            )
            is True,
        }
        declared_done_round = controller_counters.get("declared_done_round")
        if (
            isinstance(declared_done_round, int)
            and not isinstance(declared_done_round, bool)
            and declared_done_round > 0
        ):
            round_reward_trace["declared_done_round"] = declared_done_round
        declared_done_score = controller_counters.get("declared_done_score")
        if (
            isinstance(declared_done_score, (int, float))
            and not isinstance(declared_done_score, bool)
        ):
            round_reward_trace["declared_done_score"] = float(declared_done_score)
        round_reward_trace.update(round_stats)

    post_success_score = {}
    if (
        reward_value is None
        and score_failure_attribution == "skillsbench_codex_acp_jsonrpc_internal_error"
        and controller_trace_present
    ):
        post_success_score = _post_success_controller_trace_score(round_reward_trace)
        if post_success_score:
            reward_value = post_success_score["value"]
            official_passed = post_success_score["passed"]
            score_failure_attribution = "none"
            counter_trust_level = (
                "goal_harness_controller_trace_post_success_official_reward_recovery"
            )
            if round_reward_trace is not None:
                round_reward_trace["official_score_policy"] = post_success_score["policy"]
                round_reward_trace["official_score_recovered_from_controller_trace"] = True
                if post_success_score.get("round") is not None:
                    round_reward_trace["official_score_recovered_round"] = post_success_score[
                        "round"
                    ]

    official_score_kind = "skillsbench_verifier_reward"
    official_score_source = "official_skillsbench_benchflow_result_json"
    official_score_status = "completed" if reward_value is not None else "missing"
    validation_scope = "official_benchflow_result_json_only"
    if post_success_score:
        official_score_kind = (
            "skillsbench_verifier_reward_recovered_from_controller_trace"
        )
        official_score_source = (
            "goal_harness_controller_trace_best_round_reward_post_success_acp_closeout"
        )
        validation_scope = (
            "official_benchflow_result_json_plus_goal_harness_controller_trace"
        )

    benchmark_run: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "official_skillsbench_benchflow_result",
        "benchmark_id": dataset,
        "job_name": job_name,
        "mode": contract["mode"],
        "route": route,
        "agent": {
            "name": "codex",
            "model": observed_model,
            "kwargs_keys": [
                "benchflow_agent=codex-acp",
                "sandbox=docker",
                "no_upload",
                "single_task",
            ],
        },
        "model_control": {
            "schema_version": BENCHMARK_MODEL_CONTROL_SCHEMA_VERSION,
            "requested_model": requested_model,
            "reported_model": observed_model,
            "control_method": "benchflow_acp_session_set_model",
            "control_status": model_control_status,
            "actual_model_verified": actual_model_verified,
            "actual_model_source": actual_model_source,
            "warning_labels": warning_labels,
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 1 if real_run_completed else 0,
            "n_errored_trials": 0 if real_run_completed else 1,
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
        "interaction_counters": {
            "schema_version": "skillsbench_interaction_counters_v0",
            "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
            "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
            "native_goal_mode_requested": contract["native_goal_mode_requested"],
            "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
            "native_goal_mode_confirmation_status": contract[
                "native_goal_mode_confirmation_status"
            ],
            "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
            "curated_skills_visible": contract["curated_skills_visible"],
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "goal_harness_state_reads": controller_counters.get(
                "goal_harness_state_reads", 0
            ),
            "goal_harness_state_writes": controller_counters.get(
                "goal_harness_state_writes", 0
            ),
            "goal_harness_case_state_reads": controller_counters.get(
                "goal_harness_case_state_reads", 0
            ),
            "goal_harness_case_state_writes": controller_counters.get(
                "goal_harness_case_state_writes", 0
            ),
            "heartbeat_count": controller_counters.get("heartbeat_count", 0),
            "controller_trace_present": controller_trace_present,
            "controller_action_decisions": controller_counters.get(
                "controller_action_decisions", 0
            ),
            "controller_initial_prompt_count": controller_counters.get(
                "initial_prompt_count", 0
            ),
            "controller_followup_prompt_count": controller_counters.get(
                "followup_prompt_count", 0
            ),
            "controller_stop_decision_count": controller_counters.get(
                "stop_decision_count", 0
            ),
            "controller_reward_observation_count": controller_counters.get(
                "reward_observation_count", 0
            ),
            "controller_round_reward_count": controller_counters.get(
                "round_reward_count", 0
            ),
            "controller_official_success_observed": controller_counters.get(
                "official_success_observed", False
            ),
            "controller_official_success_observation_count": controller_counters.get(
                "official_success_observation_count", 0
            ),
            "controller_first_success_round": first_success_round_value or 0,
            "controller_verifier_feedback_observation_count": controller_counters.get(
                "verifier_feedback_observation_count", 0
            ),
            "controller_official_feedback_blinded_count": controller_counters.get(
                "official_feedback_blinded_count", 0
            ),
            "controller_official_feedback_forwarded": controller_counters.get(
                "official_feedback_forwarded", False
            ),
            "controller_blind_loop": controller_counters.get("blind_loop", False),
            "product_mode": controller_counters.get("product_mode", False),
            "case_goal_state_packet_present": controller_counters.get(
                "case_goal_state_packet_present", False
            ),
            "case_goal_state_init_required": controller_counters.get(
                "case_goal_state_init_required", False
            ),
            "case_goal_state_initialized_before_agent": controller_counters.get(
                "case_goal_state_initialized_before_agent", False
            ),
            "case_goal_state_init_status": controller_counters.get(
                "case_goal_state_init_status", ""
            ),
            "case_goal_state_schema_version": controller_counters.get(
                "case_goal_state_schema_version", ""
            ),
            "case_goal_state_path": controller_counters.get(
                "case_goal_state_path", ""
            ),
            "declared_done_requires_no_remaining_goals": controller_counters.get(
                "declared_done_requires_no_remaining_goals", False
            ),
            "agent_declared_done": controller_counters.get(
                "agent_declared_done", False
            ),
            "agent_declared_no_remaining_goals": controller_counters.get(
                "agent_declared_no_remaining_goals", False
            ),
            "declared_done_round": controller_counters.get("declared_done_round", 0),
            "controller_max_rounds_budget": controller_counters.get(
                "max_rounds_budget", 0
            ),
            "controller_trace_schema_version": controller_counters.get(
                "controller_trace_schema_version", ""
            ),
            "controller_trace_publicness": controller_counters.get(
                "controller_trace_publicness", ""
            ),
            "private_trajectory_summary_present": bool(trajectory_summary),
            "private_trajectory_event_count": trajectory_summary.get("event_count", 0),
            "private_trajectory_round_count": trajectory_summary.get("round_count", 0),
            "private_trajectory_tool_call_count": trajectory_summary.get(
                "tool_call_count", 0
            ),
            "goal_harness_cli_call_count": trajectory_summary.get(
                "goal_harness_cli_call_count", 0
            ),
            "goal_harness_cli_calls": trajectory_summary.get(
                "goal_harness_cli_calls", []
            ),
            "trajectory_action_category_counts": trajectory_summary.get(
                "action_category_counts", {}
            ),
            "goal_harness_cli_state_usage_counts": trajectory_summary.get(
                "goal_harness_cli_state_usage_counts", {}
            ),
            "goal_harness_cli_state_read_count": trajectory_summary.get(
                "goal_harness_cli_state_read_count", 0
            ),
            "goal_harness_cli_state_write_count": trajectory_summary.get(
                "goal_harness_cli_state_write_count", 0
            ),
            "goal_harness_case_state_path_count": trajectory_summary.get(
                "goal_harness_case_state_path_count", 0
            ),
            "goal_harness_case_state_read_count": trajectory_summary.get(
                "goal_harness_case_state_read_count", 0
            ),
            "goal_harness_case_state_write_count": trajectory_summary.get(
                "goal_harness_case_state_write_count", 0
            ),
            "protected_path_mention_count": trajectory_summary.get(
                "protected_path_mention_count", 0
            ),
            "protected_path_edit_signal_count": trajectory_summary.get(
                "protected_path_edit_signal_count", 0
            ),
            "codex_acp_text_bytes": trajectory_summary.get("codex_acp_text_bytes", 0),
            "last_decision": controller_counters.get("last_decision", ""),
            "case_result_writeback": official_score_source,
            "counter_trust_level": counter_trust_level,
        },
        "episode_policy": {
            "schema_version": "skillsbench_episode_policy_v0",
            "route": route,
            "outer_controller": (
                "goal_harness_blind_automation_loop"
                if route == "goal-harness-blind-loop-treatment"
                else "goal_harness_product_mode"
                if route == "goal-harness-product-mode"
                else "reward_feedback_automation_loop_ablation"
                if route == "automation-loop-treatment"
                else "raw_codex_autonomous_max5"
                if route == "raw-codex-autonomous-max5"
                else "fixed_blind_loop_runner"
                if route == "codex-acp-blind-loop-baseline"
                else "runner_only"
            ),
            "inner_case_actor": (
                "ordinary_codex_acp_agent"
                if route
                in {
                    "automation-loop-treatment",
                    "goal-harness-blind-loop-treatment",
                    "codex-acp-blind-loop-baseline",
                    "raw-codex-autonomous-max5",
                    "goal-harness-product-mode",
                }
                else "codex_acp_goal_prompt_request_unconfirmed_native_goal_mode"
                if route == "codex-goal-mode-baseline"
                else "codex_acp_with_curated_skills"
            ),
            "product_mode": contract.get("product_mode") is True,
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "verifier_output_tail_forwarded_by_default": False,
            "raw_trace_recorded": False,
            "raw_task_text_recorded": False,
            "controller_trace_recorded": controller_trace_present,
            "does_not_upload_or_submit": True,
        },
        "trials": [
            {
                "task_id": task_id,
                "trial_name": rollout_name,
                "source": dataset,
                "exception_type": exception_type,
                "reward": {"reward": reward_value if reward_value is not None else 0},
                "metrics": {
                    "input_tokens": 0,
                    "cache_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0,
                },
                "trajectory_present": bool(result.get("trajectory_source")),
                "verifier_reward_present": reward_value is not None,
                "artifact_manifest_present": True,
                "trial_result_present": True,
            }
        ],
        "validation": {
            "official_verifier_validation_present": reward_value is not None,
            "official_case_success": official_passed,
            "no_upload": True,
            "no_submit": True,
            "no_raw_logs_public": True,
            "no_credential_values_recorded": True,
            "validation_scope": validation_scope,
            "official_verifier_status": official_score_status,
            "goal_harness_controller_trace_present": controller_trace_present,
            "goal_harness_controller_trace_public_safe": not controller_raw_material_recorded,
        },
        "authorization": {
            "real_case_execution_authorized": True,
            "submit_eligible": False,
        },
        "redaction": {
            "secret_values_recorded": False,
            "raw_sessions_recorded": False,
            "host_paths_recorded": False,
            "raw_prompts_recorded": False,
            "raw_solutions_recorded": False,
        },
        "mode_contract": {
            "requested_route": route,
            "arm_id": contract["arm_id"],
            "case_semantics_changed_by_harness": contract[
                "case_semantics_changed_by_harness"
            ],
            "goal_harness_inside_case": contract["goal_harness_inside_case"],
            "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
            "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
            "native_goal_mode_requested": contract["native_goal_mode_requested"],
            "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
            "native_goal_mode_confirmation_status": contract[
                "native_goal_mode_confirmation_status"
            ],
            "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
            "skillsbench_route_semantics": contract["skillsbench_route_semantics"],
            "curated_skills_visible": contract["curated_skills_visible"],
            "product_mode": contract.get("product_mode") is True,
            "blind_loop": contract["blind_loop"],
            "official_feedback_blinded": contract["official_feedback_blinded"],
            "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
            "official_score_comparable_to_native_codex": contract[
                "official_score_comparable_to_native_codex"
            ],
            "official_score_comparable_to_goal_harness_treatment": contract[
                "official_score_comparable_to_goal_harness_treatment"
            ],
            "leaderboard_evidence": False,
        },
        "evidence_files": evidence_files,
        "resume_or_inspect_commands": [
            (
                "goal-harness benchmark run skillsbench "
                "--skillsbench-result-json <official-skillsbench-result.json>"
            ),
            (
                "goal-harness benchmark run-ledger-upsert "
                "--benchmark-run-json <skillsbench-compact-benchmark-run-v0.json>"
            ),
        ],
        "real_run": True,
        "submit_eligible": False,
        "official_task_score": {
            "kind": official_score_kind,
            "value": reward_value,
            "passed": official_passed,
        },
        "official_score": reward_value,
        "official_score_status": official_score_status,
        "official_score_source": official_score_source,
        "score_failure_attribution": score_failure_attribution,
        "case_semantics_changed_by_harness": contract[
            "case_semantics_changed_by_harness"
        ],
        "goal_harness_inside_case": contract["goal_harness_inside_case"],
        "goal_harness_automation_loop": contract["goal_harness_automation_loop"],
        "product_mode": contract.get("product_mode") is True,
        "inner_codex_goal_mode": contract["inner_codex_goal_mode"],
        "native_goal_mode_requested": contract["native_goal_mode_requested"],
        "native_goal_mode_invoked": contract["native_goal_mode_invoked"],
        "native_goal_mode_confirmation_status": contract[
            "native_goal_mode_confirmation_status"
        ],
        "codex_acp_protocol_used": contract["codex_acp_protocol_used"],
        "skillsbench_route_semantics": contract["skillsbench_route_semantics"],
        "curated_skills_visible": contract["curated_skills_visible"],
        "blind_loop": contract["blind_loop"],
        "official_feedback_blinded": contract["official_feedback_blinded"],
        "reward_feedback_forwarded": contract["reward_feedback_forwarded"],
        "official_score_comparable_to_native_codex": contract[
            "official_score_comparable_to_native_codex"
        ],
        "official_score_comparable_to_goal_harness_treatment": contract[
            "official_score_comparable_to_goal_harness_treatment"
        ],
        "leaderboard_evidence": False,
        "trace_publicness": "public_skillsbench_official_compact_result_only",
        "failure_attribution_labels": failure_labels,
        "runner_warning_labels": warning_labels,
        "stop_conditions": [
            "do_not_read_raw_task_prompt_solution_or_trajectory",
            "do_not_record_absolute_job_paths_in_public_ledger",
            "do_not_upload_or_submit_leaderboard",
            "do_not_record_secrets_or_raw_sessions",
        ],
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "trajectory_read": False,
            "controller_trace_read": controller_trace_present,
            "local_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
        },
    }
    if timing_summary:
        benchmark_run["timing"] = timing_summary
    if round_reward_trace is not None:
        benchmark_run["round_reward_trace"] = round_reward_trace
    if runner_failure is not None:
        benchmark_run["runner_failure"] = runner_failure
        benchmark_run["runner_failure_fingerprint"] = runner_failure_fingerprint
    if partial_trajectory:
        benchmark_run["failure_attribution_labels"].append("partial_trajectory")
    return benchmark_run


def skillsbench_recommended_action(*, route: str) -> str:
    contract = skillsbench_route_contract(route)
    return str(contract["next_action"])


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
    codex_install_strategy: str = (
        TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
    ),
    codex_preflight_timeout_sec: int | None = None,
    worker_codex_materialization_strategy: str | None = None,
    worker_materialization_probe_only: bool = False,
    setup_timeout_repair_profile: bool = False,
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
        "codex-goal-mode",
        "codex-goal-harness",
        "goal-harness-managed-codex",
    ):
        raise ValueError(
            "--preflight-guard is only supported for hardened-codex, codex-goal-mode, codex-goal-harness, or goal-harness-managed-codex"
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
    if (
        preflight_guard
        and mode
        in (
            "codex-goal-harness",
            "goal-harness-managed-codex",
            "hardened-codex",
            "codex-goal-mode",
        )
        and agent_timeout_multiplier is None
    ):
        agent_timeout_multiplier = (
            TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_TIMEOUT_MULTIPLIER
        )
    if (
        preflight_guard
        and mode
        in (
            "codex-goal-harness",
            "goal-harness-managed-codex",
            "hardened-codex",
            "codex-goal-mode",
        )
        and agent_setup_timeout_multiplier is None
    ):
        agent_setup_timeout_multiplier = (
            TERMINAL_BENCH_PRIVATE_EXTENDED_AGENT_SETUP_TIMEOUT_MULTIPLIER
        )
    setup_repair_profile: dict[str, Any] | None = None
    if setup_timeout_repair_profile:
        profile_kwargs: dict[str, Any] = {
            "codex_install_strategy": codex_install_strategy,
            "agent_timeout_multiplier": agent_timeout_multiplier,
            "agent_setup_timeout_multiplier": agent_setup_timeout_multiplier,
        }
        if codex_preflight_timeout_sec is not None:
            profile_kwargs["codex_preflight_timeout_sec"] = (
                codex_preflight_timeout_sec
            )
        if worker_codex_materialization_strategy is not None:
            profile_kwargs["worker_codex_materialization_strategy"] = (
                worker_codex_materialization_strategy
            )
        setup_repair_profile = _terminal_bench_setup_timeout_repair_profile(
            profile_kwargs
        )
        codex_install_strategy = str(profile_kwargs["codex_install_strategy"])
        agent_timeout_multiplier = _optional_float(
            profile_kwargs["agent_timeout_multiplier"]
        )
        agent_setup_timeout_multiplier = _optional_float(
            profile_kwargs["agent_setup_timeout_multiplier"]
        )
        codex_preflight_timeout_sec = _optional_positive_int(
            profile_kwargs.get("codex_preflight_timeout_sec")
        )
        worker_codex_materialization_strategy = (
            str(profile_kwargs.get("worker_codex_materialization_strategy") or "")
            or None
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
            else "codex_goal_mode_baseline_preflight_guard"
            if mode == "codex-goal-mode"
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
            else "public_codex_goal_mode_baseline_preflight_guard"
            if mode == "codex-goal-mode"
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
        if mode == "codex-goal-mode":
            validation["codex_goal_mode_invocation_surface_checked"] = True
            validation["goal_harness_access_packet_absent"] = True
            validation["goal_harness_cli_bridge_absent"] = True
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
    elif mode == "codex-goal-mode":
        interaction_counters = build_terminal_bench_goal_harness_interaction_counters(
            prompt_policy_injected=False,
            harness_skill_or_packet_injected=False,
            case_result_writeback="codex_goal_mode_baseline_runner_only",
            counter_trust_level="codex_goal_mode_baseline_no_goal_harness_state",
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
    runner_goal_harness_mode = (
        "codex_goal_harness"
        if mode == "codex-goal-harness"
        else TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
        if mode == "codex-goal-mode"
        else TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE
        if mode == "hardened-codex"
        else "goal_harness_managed_codex"
    )
    runner_goal_harness_ablation_mode = (
        "codex_goal_mode_baseline"
        if mode == "codex-goal-mode"
        else "hardened_codex_baseline"
        if mode == "hardened-codex"
        else "goal_harness_managed"
    )
    runner_access_packet_mode = (
        TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        if mode in ("codex-goal-mode", "hardened-codex")
        else TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL
    )
    managed_runner_command_preview = (
        build_terminal_bench_managed_harbor_command(
            dataset=dataset,
            task_id=task_id,
            model=model,
            job_name=runner_job_name,
            goal_harness_mode=runner_goal_harness_mode,
            goal_harness_ablation_mode=runner_goal_harness_ablation_mode,
            goal_harness_access_packet_mode=runner_access_packet_mode,
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
            codex_install_strategy=codex_install_strategy,
            codex_preflight_timeout_sec=codex_preflight_timeout_sec,
            worker_codex_materialization_strategy=worker_codex_materialization_strategy,
            worker_materialization_probe_only=worker_materialization_probe_only,
        )
        if mode in (
            "codex-goal-harness",
            "goal-harness-managed-codex",
            "hardened-codex",
            "codex-goal-mode",
        )
        else []
    )
    private_runner_launch_summary: dict[str, Any] = {}
    if mode in (
        "codex-goal-harness",
        "goal-harness-managed-codex",
        "hardened-codex",
        "codex-goal-mode",
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
                codex_install_strategy=codex_install_strategy,
                codex_preflight_timeout_sec=codex_preflight_timeout_sec,
                worker_codex_materialization_strategy=worker_codex_materialization_strategy,
                worker_materialization_probe_only=worker_materialization_probe_only,
                setup_timeout_repair_profile=setup_timeout_repair_profile,
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
                    "codex-goal-mode",
                )
                else None
            ),
            "kwargs_keys": (
                [
                    "codex_goal_mode_invocation_surface",
                    "fixture_only",
                    "no_upload",
                    "single_task_planned",
                ]
                if mode == "codex-goal-mode"
                else [
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
                )
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
        "episode_policy": (
            {
                "schema_version": "terminal_bench_codex_goal_mode_baseline_episode_policy_v0",
                "mode": "single_codex_goal_mode_baseline",
                "worker_topology": "single_codex_agent",
                "goal_harness_role": "parent_runner_only_compact_ingest",
                "runner_role": "schedule_same_agent_episode_and_archive_final_outcome",
                "checkpoint_surface": "runner_side_compact_benchmark_result_after_completion",
                "does_not_spawn_additional_agents": True,
                "does_not_split_task_prompt": True,
                "does_not_change_task_solution_actor": True,
                "does_not_inject_goal_harness_state": True,
                "raw_trace_recorded": False,
            }
            if mode == "codex-goal-mode"
            else build_terminal_bench_single_agent_episode_policy(
                active_cli_bridge=active_cli_bridge_preflight or worker_cli_bridge_fixture,
                runner_side_guaranteed_writeback=True,
            )
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
                "doc:terminal-bench-official-hard-case-selection-v0.md",
                "smoke:terminal-bench-runner-mode-contract-smoke.py",
            ]
            if mode == "codex-goal-mode"
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
                "goal-harness benchmark run terminal-bench --mode codex-goal-mode",
                "goal-harness benchmark baseline-failure-gate --baseline-result-json <benchmark-result-v0.json>",
            ]
            if mode == "codex-goal-mode"
            else [
                "goal-harness benchmark run terminal-bench --mode goal-harness-managed-codex --fake-worker",
                "goal-harness history append-benchmark-run --benchmark-run-json <benchmark-run-v0.json>",
            ]
        ),
        "managed_runner_command_preview": managed_runner_command_preview,
        "private_runner_launch_summary": private_runner_launch_summary,
        "worker_materialization_probe_only": worker_materialization_probe_only,
        "setup_timeout_repair_profile": setup_repair_profile or {},
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
        elif mode == "codex-goal-mode":
            benchmark_run["source_runner"] = (
                "goal_harness_terminal_bench_codex_goal_mode_baseline_preflight_guard"
            )
            benchmark_run["evidence_files"] = [
                "doc:terminal-bench-runner-mode-contract-v0.md",
                "doc:terminal-bench-official-hard-case-selection-v0.md",
                "smoke:terminal-bench-runner-mode-contract-smoke.py",
            ]
            benchmark_run["resume_or_inspect_commands"] = [
                "goal-harness benchmark run terminal-bench --mode codex-goal-mode --preflight-guard",
                "goal-harness benchmark run terminal-bench --mode codex-goal-mode --preflight-guard --execute",
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
                else "terminal_bench_codex_goal_mode_baseline_preflight_guard_v0"
                if mode == "codex-goal-mode"
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
        if mode == "codex-goal-mode":
            benchmark_run["preflight_guard"].update(
                {
                    "codex_goal_mode_invocation_surface_checked": True,
                    "codex_goal_mode_invocation_surface": "slash_command",
                    "goal_harness_access_packet_absent": True,
                    "goal_harness_cli_bridge_absent": True,
                    "real_interface_use_observed": False,
                    "uplift_claim_allowed": False,
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
        return "use hardened-codex only as startup calibration; primary baseline is codex-goal-mode"
    if mode == "codex-goal-mode":
        return "run or ingest the codex-goal-mode baseline, reduce it through baseline-failure-gate, and only run codex-goal-harness if the failure is control-plane-addressable"
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
