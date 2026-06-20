from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..benchmark_core.io import (
    load_json_object as _load_json_object,
    load_jsonl_objects as _load_jsonl_objects,
    optional_float as _optional_float,
    optional_positive_int as _optional_positive_int,
)
from ..benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS,
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_init_contract,
    benchmark_case_active_state_path,
    benchmark_case_goal_id,
)
from ..codex_goal_baseline import (
    CODEX_APP_SERVER_GOAL_WORKER_SCHEMA_VERSION,
    CODEX_APP_SERVER_GOAL_WORKER_METHODS,
    build_codex_app_server_goal_worker_plan,
)
from ..worker_bridge import (
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
    "codex-goal-mode",
    "codex-app-server-goal",
    "codex-goal-harness",
    "goal-harness-managed-codex",
)

TERMINAL_BENCH_DEFAULT_DATASET = "terminal-bench@2.0"
TERMINAL_BENCH_DEFAULT_TASK = "build-cython-ext"
TERMINAL_BENCH_DEFAULT_MODEL = "gpt-5.5"
TERMINAL_BENCH_CASE_STATE_BENCHMARK_ID = "terminal-bench"
TERMINAL_BENCH_CASE_GOAL_ID = benchmark_case_goal_id(
    TERMINAL_BENCH_CASE_STATE_BENCHMARK_ID
)
TERMINAL_BENCH_CASE_STATE_PATH = benchmark_case_active_state_path(
    TERMINAL_BENCH_CASE_GOAL_ID
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
TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA = (
    "terminal_bench_remote_executor_command_adapter_v1"
)
TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA = (
    "terminal_bench_remote_executor_materializer_v0"
)
TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA = (
    "terminal_bench_remote_executor_launch_adapter_v0"
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
TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_BASELINE_MODE = (
    "codex_app_server_goal_baseline"
)
TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_WORKER_SEAM_BLOCKER = (
    "terminal_bench_app_server_goal_worker_seam_not_implemented"
)
TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_TURN_PROOF_BLOCKER = (
    "terminal_bench_app_server_goal_turn_start_proof_missing"
)
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
TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_BASELINE_SURFACE = (
    "codex_app_server_thread_goal_set_get_no_goal_harness_state"
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
    "goal_harness_codex_install_strategy",
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

# Terminal-Bench helper surfaces extracted from the legacy benchmark facade.

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

def _compact_positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    return 0

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
        "codex-app-server-goal",
        "hardened-codex",
        "codex-goal-harness",
        "goal-harness-managed-codex",
    ):
        raise ValueError(
            "case run launcher supports codex-goal-mode, codex-app-server-goal, "
            "hardened-codex, codex-goal-harness, or goal-harness-managed-codex"
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

def _compactable_benchmark_run_v0_payload(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    if payload.get("schema_version") == "benchmark_run_v0":
        return payload
    nested = payload.get("benchmark_run")
    if isinstance(nested, dict) and nested.get("schema_version") == "benchmark_run_v0":
        return nested
    return None

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

TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS = (
    "benchmark_id",
    "runner_handle",
    "readiness_rechecked",
    "run_root_handle",
    "jobs_dir_handle",
    "job_name",
    "poll_label",
    "cleanup_label",
    "compact_artifact_ref",
)
TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS = (
    "benchmark_id",
    "case_handle",
    "execution_mode",
    "no_upload",
    "compact_artifact_ref",
)

def _present_fields_from_sources(
    *,
    manifest: Mapping[str, Any] | None,
    present_fields: Sequence[str],
    allowed_fields: Sequence[str],
) -> set[str]:
    allowed = set(allowed_fields)
    present = {str(field) for field in present_fields if str(field) in allowed}
    present.update(
        key
        for key, value in dict(manifest or {}).items()
        if key in allowed and value not in (None, "", [], {})
    )
    return present

def build_terminal_bench_remote_executor_command_adapter(
    *,
    benchmark_id: str = TERMINAL_BENCH_DEFAULT_DATASET,
    launch_surface_ready: bool = True,
    poll_surface_ready: bool = True,
    resume_surface_ready: bool = True,
    compact_ingest_ready: bool = True,
    result_reducer_ready: bool = True,
    remote_materializer_ready: bool = False,
    local_codex_driver_ready: bool = False,
    remote_sandbox_ready: bool = False,
    no_upload: bool = True,
    submit_enabled: bool = False,
    known_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    """Return Terminal-Bench adapter facts for the split-control seam.

    This is not a launcher and it deliberately avoids shell commands, argv,
    host paths, task text, logs, trajectories, uploads, and submit surfaces.
    Private runners may use the labels to find their own local implementation,
    but public Goal Harness state stores only the adapter contract.
    """

    safe_benchmark_id = _public_safe_benchmark_label(benchmark_id, limit=80)
    surface_blockers = [str(item) for item in known_blockers if str(item)]
    blockers: list[str] = []
    if not safe_benchmark_id:
        safe_benchmark_id = TERMINAL_BENCH_DEFAULT_DATASET
        surface_blockers.append("terminal_bench_benchmark_id_not_public_safe")
    if safe_benchmark_id != TERMINAL_BENCH_DEFAULT_DATASET:
        surface_blockers.append("terminal_bench_benchmark_id_unsupported")
    if not launch_surface_ready:
        surface_blockers.append("terminal_bench_launch_surface_not_ready")
    if not poll_surface_ready:
        surface_blockers.append("terminal_bench_poll_surface_not_ready")
    if not resume_surface_ready:
        surface_blockers.append("terminal_bench_resume_surface_not_ready")
    if not compact_ingest_ready:
        surface_blockers.append("terminal_bench_compact_ingest_surface_not_ready")
    if not no_upload:
        surface_blockers.append("terminal_bench_no_upload_boundary_not_enabled")
    if submit_enabled:
        surface_blockers.append("terminal_bench_submit_must_remain_disabled")
    blockers.extend(surface_blockers)
    if not remote_materializer_ready:
        blockers.append("terminal_bench_remote_executor_materializer_missing")
    elif not local_codex_driver_ready:
        blockers.append("terminal_bench_local_codex_driver_missing")
    elif not remote_sandbox_ready:
        blockers.append("terminal_bench_remote_sandbox_contract_missing")

    reducer_ready = (
        result_reducer_ready is True
        and compact_ingest_ready is True
        and no_upload is True
        and submit_enabled is False
    )
    if not reducer_ready:
        blockers.append("terminal_bench_compact_result_reducer_not_ready")

    adapter_ready = not surface_blockers
    adapter = {
        "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
        "benchmark_id": safe_benchmark_id,
        "command_adapter_ready": adapter_ready,
        "result_reducer_ready": reducer_ready,
        "command_adapter_status": "ready" if adapter_ready else "blocked",
        "entrypoint_label": "terminal_bench_no_upload_case_run_surface",
        "poll_label": "terminal_bench_compact_materialization_poll_surface",
        "cleanup_label": "terminal_bench_private_runner_cleanup_surface",
        "result_reducer_label": "terminal_bench_compact_harbor_result_reducer",
        "handle_fields": list(TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS),
        "known_blockers": blockers,
        "surface_contract": {
            "launch_surface_ready": launch_surface_ready is True,
            "poll_surface_ready": poll_surface_ready is True,
            "resume_surface_ready": resume_surface_ready is True,
            "compact_ingest_ready": compact_ingest_ready is True,
            "remote_materializer_ready": remote_materializer_ready is True,
            "private_handle_values_required": True,
            "public_handle_shape_only": True,
            "local_codex_owns_auth_model_state": True,
            "remote_executor_owns_docker_runner_data": True,
        },
        "local_driver_contract": {
            "ready": remote_materializer_ready is True
            and local_codex_driver_ready is True,
            "driver_label": "terminal_bench_local_codex_driver",
            "owns": [
                "codex_cli",
                "codex_auth",
                "goal_harness_state",
                "model_invocation",
                "planning_and_patch_generation",
            ],
            "remote_request_fields": [
                "benchmark_id",
                "case_handle",
                "execution_mode",
                "no_upload",
                "compact_artifact_ref",
            ],
            "keeps_local": [
                "codex_auth",
                "model_invocation",
                "goal_harness_state",
                "raw_reasoning_trace",
            ],
        },
        "remote_sandbox_contract": {
            "ready": remote_materializer_ready is True and remote_sandbox_ready is True,
            "sandbox_label": "terminal_bench_remote_sandbox",
            "owns": [
                "docker",
                "runner_dependencies",
                "task_data_staging",
                "bounded_command_execution",
                "compact_result_reduction",
            ],
            "allowed_actions": [
                "runner_dependency_check",
                "bounded_command_execution",
                "compact_result_reduction",
            ],
            "disallowed_actions": [
                "codex_auth_sync",
                "credential_sync",
                "remote_agent_runtime",
                "remote_codex_runtime",
                "remote_model_api_invocation",
                "raw_task_text_publication",
                "raw_log_publication",
                "upload",
                "submit",
            ],
            "returns": [
                "readiness_state",
                "job_handle",
                "compact_result_or_blocker",
                "cleanup_state",
            ],
        },
        "boundary": {
            "shell_command_embedded": False,
            "argv_embedded": False,
            "host_path_embedded": False,
            "remote_path_embedded": False,
            "raw_task_text_public": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
            "credential_values_recorded": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
    }
    return {
        "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
        "benchmark_id": safe_benchmark_id,
        "ready": adapter_ready
        and reducer_ready
        and remote_materializer_ready
        and local_codex_driver_ready
        and remote_sandbox_ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_split_control_execution_seam",
        "blockers": blockers,
        "command_adapters": {safe_benchmark_id: adapter},
        "command_adapter": adapter,
        "next_action": (
            "feed_terminal_bench_adapter_facts_to_split_control_execution_seam"
            if adapter_ready and reducer_ready and remote_materializer_ready
            else "repair_terminal_bench_adapter_surface_before_execution_seam"
        ),
        "read_boundary": {
            "compact_only": True,
            "shell_commands_read": False,
            "argv_read": False,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "remote_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "submit_invoked": False,
        },
    }

def build_terminal_bench_remote_executor_materializer(
    *,
    benchmark_id: str = TERMINAL_BENCH_DEFAULT_DATASET,
    handle_manifest: Mapping[str, Any] | None = None,
    present_handle_fields: Sequence[str] = (),
    no_upload: bool = True,
    submit_enabled: bool = False,
    local_codex_driver_ready: bool = False,
    remote_agent_runtime_required: bool = False,
    remote_codex_runtime_required: bool = False,
    local_codex_credential_sync: bool = False,
    remote_model_invocation: bool = False,
    raw_material_allowed: bool = False,
) -> dict[str, Any]:
    """Materialize public-safe Terminal-Bench remote-executor handle shape.

    The private manifest may contain real handles, paths, or process ids, but
    this reducer records only which required fields are present. It does not
    launch Harbor, Docker, Codex, or a model API.
    """

    safe_benchmark_id = _public_safe_benchmark_label(benchmark_id, limit=80)
    blockers: list[str] = []
    if not safe_benchmark_id:
        safe_benchmark_id = TERMINAL_BENCH_DEFAULT_DATASET
        blockers.append("terminal_bench_benchmark_id_not_public_safe")
    if safe_benchmark_id != TERMINAL_BENCH_DEFAULT_DATASET:
        blockers.append("terminal_bench_benchmark_id_unsupported")

    manifest = dict(handle_manifest or {})
    present = {
        str(field)
        for field in present_handle_fields
        if str(field) in TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
    }
    present.update(
        key
        for key, value in manifest.items()
        if key in TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
        and value not in (None, "", [], {})
    )
    present.add("benchmark_id")
    missing_fields = [
        field
        for field in TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
        if field not in present
    ]
    if missing_fields:
        blockers.append("terminal_bench_remote_executor_handle_manifest_incomplete")
    if not local_codex_driver_ready:
        blockers.append("terminal_bench_local_codex_driver_missing")
    if remote_agent_runtime_required:
        blockers.append("terminal_bench_remote_agent_runtime_forbidden")
    if remote_codex_runtime_required:
        blockers.append("terminal_bench_remote_codex_runtime_forbidden")
    if not no_upload:
        blockers.append("terminal_bench_no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("terminal_bench_submit_must_remain_disabled")
    if local_codex_credential_sync:
        blockers.append("terminal_bench_codex_credential_sync_forbidden")
    if remote_model_invocation:
        blockers.append("terminal_bench_remote_model_invocation_forbidden")
    if raw_material_allowed:
        blockers.append("terminal_bench_raw_material_boundary_not_enabled")

    ready = not blockers
    adapter_payload = build_terminal_bench_remote_executor_command_adapter(
        benchmark_id=safe_benchmark_id,
        remote_materializer_ready=ready,
        local_codex_driver_ready=local_codex_driver_ready,
        remote_sandbox_ready=ready,
        no_upload=no_upload,
        submit_enabled=submit_enabled,
    )
    return {
        "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA,
        "benchmark_id": safe_benchmark_id,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_terminal_bench_remote_executor_dry_run",
        "blockers": blockers,
        "materializer": {
            "entrypoint_label": "terminal_bench_no_upload_case_run_surface",
            "ready": ready,
            "handle_manifest_read": bool(handle_manifest),
            "required_handle_fields": list(
                TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
            ),
            "present_handle_fields": [
                field
                for field in TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
                if field in present
            ],
            "missing_handle_fields": missing_fields,
            "local_codex_driver_ready": local_codex_driver_ready is True,
            "remote_agent_runtime_required": remote_agent_runtime_required is True,
            "remote_codex_runtime_required": remote_codex_runtime_required is True,
            "private_handle_values_required": True,
            "public_handle_values_recorded": False,
        },
        "boundary": {
            "compact_only": True,
            "local_codex_driver_required": True,
            "remote_agent_runtime_allowed": False,
            "remote_codex_runtime_allowed": False,
            "shell_command_embedded": False,
            "argv_embedded": False,
            "host_path_embedded": False,
            "remote_path_embedded": False,
            "raw_task_text_public": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
            "credential_values_recorded": False,
            "codex_credentials_synced_to_remote": False,
            "remote_model_api_invocation_allowed": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
        "command_adapters": adapter_payload["command_adapters"],
        "command_adapter": adapter_payload["command_adapter"],
        "next_action": (
            "feed_materialized_terminal_bench_adapter_to_execution_seam"
            if ready
            else "provide_private_remote_executor_handle_manifest_before_launch"
            if missing_fields
            else "implement_terminal_bench_local_codex_driver_before_launch"
            if not local_codex_driver_ready
            else "remove_remote_agent_runtime_from_terminal_bench_execution_path"
            if remote_agent_runtime_required or remote_codex_runtime_required
            else "repair_terminal_bench_materializer_boundary_before_launch"
        ),
        "read_boundary": {
            "compact_only": True,
            "handle_manifest_values_recorded": False,
            "shell_commands_read": False,
            "argv_read": False,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "remote_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "submit_invoked": False,
        },
    }

def build_terminal_bench_remote_executor_launch_adapter(
    *,
    benchmark_id: str = TERMINAL_BENCH_DEFAULT_DATASET,
    request_manifest: Mapping[str, Any] | None = None,
    present_request_fields: Sequence[str] = (),
    launch_result_manifest: Mapping[str, Any] | None = None,
    present_launch_result_fields: Sequence[str] = (),
    local_codex_driver_ready: bool = False,
    remote_sandbox_ready: bool = False,
    no_upload: bool = True,
    submit_enabled: bool = False,
    local_codex_credential_sync: bool = False,
    remote_agent_runtime_required: bool = False,
    remote_codex_runtime_required: bool = False,
    remote_model_invocation: bool = False,
    raw_material_allowed: bool = False,
) -> dict[str, Any]:
    """Bridge a local-driver request to private remote-sandbox launch handles.

    This is the public-safe launch adapter surface. It never executes SSH,
    Docker, Codex, or model calls, and it never records private handle values.
    A private runner may feed field presence from its local-driver request and
    remote launch result manifest so Goal Harness can decide whether the
    command adapter can be materialized for the split-control execution seam.
    """

    safe_benchmark_id = _public_safe_benchmark_label(benchmark_id, limit=80)
    blockers: list[str] = []
    if not safe_benchmark_id:
        safe_benchmark_id = TERMINAL_BENCH_DEFAULT_DATASET
        blockers.append("terminal_bench_benchmark_id_not_public_safe")
    if safe_benchmark_id != TERMINAL_BENCH_DEFAULT_DATASET:
        blockers.append("terminal_bench_benchmark_id_unsupported")

    request_present = _present_fields_from_sources(
        manifest=request_manifest,
        present_fields=present_request_fields,
        allowed_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS,
    )
    request_present.add("benchmark_id")
    request_missing = [
        field
        for field in TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS
        if field not in request_present
    ]

    launch_result_present = _present_fields_from_sources(
        manifest=launch_result_manifest,
        present_fields=present_launch_result_fields,
        allowed_fields=TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS,
    )
    launch_result_present.add("benchmark_id")
    launch_result_missing = [
        field
        for field in TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
        if field not in launch_result_present
    ]

    if not local_codex_driver_ready:
        blockers.append("terminal_bench_local_codex_driver_missing")
    if request_missing:
        blockers.append("terminal_bench_local_driver_request_incomplete")
    if not remote_sandbox_ready:
        blockers.append("terminal_bench_remote_sandbox_contract_missing")
    if not no_upload:
        blockers.append("terminal_bench_no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("terminal_bench_submit_must_remain_disabled")
    if local_codex_credential_sync:
        blockers.append("terminal_bench_codex_credential_sync_forbidden")
    if remote_agent_runtime_required:
        blockers.append("terminal_bench_remote_agent_runtime_forbidden")
    if remote_codex_runtime_required:
        blockers.append("terminal_bench_remote_codex_runtime_forbidden")
    if remote_model_invocation:
        blockers.append("terminal_bench_remote_model_invocation_forbidden")
    if raw_material_allowed:
        blockers.append("terminal_bench_raw_material_boundary_not_enabled")
    if not launch_result_manifest and not present_launch_result_fields:
        blockers.append("terminal_bench_remote_launch_result_missing")
    elif launch_result_missing:
        blockers.append("terminal_bench_remote_launch_result_incomplete")

    launch_request_ready = (
        local_codex_driver_ready is True
        and not request_missing
        and remote_sandbox_ready is True
        and no_upload is True
        and submit_enabled is False
        and local_codex_credential_sync is False
        and remote_agent_runtime_required is False
        and remote_codex_runtime_required is False
        and remote_model_invocation is False
        and raw_material_allowed is False
    )
    materializer_payload = build_terminal_bench_remote_executor_materializer(
        benchmark_id=safe_benchmark_id,
        handle_manifest=launch_result_manifest,
        present_handle_fields=tuple(launch_result_present),
        no_upload=no_upload,
        submit_enabled=submit_enabled,
        local_codex_driver_ready=local_codex_driver_ready,
        remote_agent_runtime_required=remote_agent_runtime_required,
        remote_codex_runtime_required=remote_codex_runtime_required,
        local_codex_credential_sync=local_codex_credential_sync,
        remote_model_invocation=remote_model_invocation,
        raw_material_allowed=raw_material_allowed,
    )
    ready = launch_request_ready and materializer_payload.get("ready") is True
    materializer_blockers = [
        str(item)
        for item in materializer_payload.get("blockers", [])
        if str(item) and str(item) not in blockers
    ]
    all_blockers = blockers + materializer_blockers
    if not local_codex_driver_ready:
        next_action = "implement_terminal_bench_local_driver_before_remote_launch"
    elif request_missing:
        next_action = "complete_terminal_bench_local_driver_request_before_remote_launch"
    elif not remote_sandbox_ready:
        next_action = "implement_terminal_bench_remote_sandbox_launch_adapter"
    elif "terminal_bench_remote_launch_result_missing" in blockers:
        next_action = "execute_private_remote_sandbox_and_feed_compact_launch_result_manifest"
    elif launch_result_missing or materializer_blockers:
        next_action = "repair_terminal_bench_remote_launch_result_before_materialization"
    else:
        next_action = "feed_launch_adapter_materialized_handles_to_execution_seam"

    return {
        "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA,
        "benchmark_id": safe_benchmark_id,
        "ready": ready,
        "first_blocker": all_blockers[0]
        if all_blockers
        else "ready_for_terminal_bench_execution_seam",
        "blockers": all_blockers,
        "launch_adapter": {
            "request_label": "terminal_bench_local_driver_remote_sandbox_request",
            "ready_to_request_remote_sandbox": launch_request_ready,
            "remote_launch_result_read": bool(
                launch_result_manifest or present_launch_result_fields
            ),
            "required_request_fields": list(
                TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS
            ),
            "present_request_fields": [
                field
                for field in TERMINAL_BENCH_REMOTE_EXECUTOR_REQUEST_FIELDS
                if field in request_present
            ],
            "missing_request_fields": request_missing,
            "required_launch_result_fields": list(
                TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
            ),
            "present_launch_result_fields": [
                field
                for field in TERMINAL_BENCH_REMOTE_EXECUTOR_HANDLE_FIELDS
                if field in launch_result_present
            ],
            "missing_launch_result_fields": launch_result_missing,
            "local_codex_driver_ready": local_codex_driver_ready is True,
            "remote_sandbox_ready": remote_sandbox_ready is True,
            "private_request_values_recorded": False,
            "private_launch_result_values_recorded": False,
        },
        "materializer": materializer_payload.get("materializer"),
        "command_adapters": materializer_payload.get("command_adapters"),
        "command_adapter": materializer_payload.get("command_adapter"),
        "boundary": {
            "compact_only": True,
            "local_codex_driver_required": True,
            "remote_sandbox_required": True,
            "remote_agent_runtime_allowed": False,
            "remote_codex_runtime_allowed": False,
            "shell_command_embedded": False,
            "argv_embedded": False,
            "host_path_embedded": False,
            "remote_path_embedded": False,
            "raw_task_text_public": False,
            "raw_logs_public": False,
            "raw_trajectory_public": False,
            "credential_values_recorded": False,
            "codex_credentials_synced_to_remote": False,
            "remote_model_api_invocation_allowed": False,
            "upload_allowed": False,
            "submit_allowed": False,
        },
        "next_action": next_action,
        "read_boundary": {
            "compact_only": True,
            "request_manifest_values_recorded": False,
            "launch_result_values_recorded": False,
            "shell_commands_read": False,
            "argv_read": False,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "remote_paths_recorded": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "submit_invoked": False,
        },
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
    return str(Path(__file__).resolve().parents[2])

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
    codex_app_server_goal_mode = mode == "codex-app-server-goal"
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
    elif codex_app_server_goal_mode:
        resolved_command_kwargs.pop("goal_harness_mode", None)
        resolved_command_kwargs.pop("goal_harness_ablation_mode", None)
        resolved_command_kwargs.pop("goal_harness_access_packet_mode", None)
        resolved_command_kwargs.pop("goal_harness_cli_bridge_enabled", None)
        resolved_command_kwargs.pop("goal_harness_active_user_intervention_enabled", None)
        resolved_command_kwargs.setdefault(
            "job_name",
            "terminal_bench_codex_app_server_goal_baseline",
        )
        argv = []
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
    codex_app_server_goal_worker_plan: dict[str, Any] = {}
    if codex_app_server_goal_mode:
        task_name = str(
            resolved_command_kwargs.get("task_id")
            or resolved_command_kwargs.get("include_task_name")
            or TERMINAL_BENCH_DEFAULT_TASK
        )
        codex_app_server_goal_worker_plan = build_codex_app_server_goal_worker_plan(
            objective=f"Complete Terminal-Bench task {task_name} under no-upload baseline.",
            task_instruction="<terminal-bench-task-instruction-from-runner>",
            cwd="<terminal-bench-case-workspace>",
            model=str(resolved_command_kwargs.get("model") or TERMINAL_BENCH_DEFAULT_MODEL),
        )
        first_blocker = TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_TURN_PROOF_BLOCKER
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
        "codex_app_server_goal_baseline_requested": codex_app_server_goal_mode,
        "codex_app_server_goal_worker_adapter_present": codex_app_server_goal_mode,
        "codex_app_server_goal_worker_plan_schema": (
            str(
                codex_app_server_goal_worker_plan.get("schema_version")
                or CODEX_APP_SERVER_GOAL_WORKER_SCHEMA_VERSION
            )
            if codex_app_server_goal_mode
            else ""
        ),
        "codex_app_server_goal_worker_required_methods": (
            list(
                codex_app_server_goal_worker_plan.get("methods")
                or CODEX_APP_SERVER_GOAL_WORKER_METHODS
            )
            if codex_app_server_goal_mode
            else []
        ),
        "codex_app_server_goal_worker_turn_start_required": codex_app_server_goal_mode,
        "codex_app_server_goal_proof_present": False,
        "codex_app_server_goal_required_surface": (
            "codex_app_server_thread_goal_set_get"
            if codex_app_server_goal_mode
            else ""
        ),
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
    codex_goal_mode_requested = (
        "goal_harness_mode=" + TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
    ) in argv
    codex_app_server_goal_requested = (
        launch.get("codex_app_server_goal_baseline_requested") is True
    )
    codex_app_server_goal_adapter_present = (
        launch.get("codex_app_server_goal_worker_adapter_present") is True
    )
    codex_app_server_goal_proof_present = (
        launch.get("codex_app_server_goal_proof_present") is True
    )
    codex_goal_mode_invocation_surface = ""
    if codex_app_server_goal_requested:
        codex_goal_mode_invocation_surface = "codex_app_server_thread_goal_set_get"
    elif codex_goal_mode_requested:
        codex_goal_mode_invocation_surface = "slash_command"
    codex_goal_mode_baseline_claim_allowed = bool(
        codex_app_server_goal_requested
        and codex_app_server_goal_adapter_present
        and codex_app_server_goal_proof_present
    )
    if codex_goal_mode_baseline_claim_allowed:
        codex_goal_mode_baseline_claim_blocker = ""
    elif codex_app_server_goal_requested and not codex_app_server_goal_adapter_present:
        codex_goal_mode_baseline_claim_blocker = (
            TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_WORKER_SEAM_BLOCKER
        )
    elif codex_app_server_goal_requested:
        codex_goal_mode_baseline_claim_blocker = (
            TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_TURN_PROOF_BLOCKER
        )
    elif codex_goal_mode_requested:
        codex_goal_mode_baseline_claim_blocker = "missing_codex_app_server_goal_proof"
    else:
        codex_goal_mode_baseline_claim_blocker = ""
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
            codex_goal_mode_requested or codex_app_server_goal_requested
        ),
        "codex_app_server_goal_baseline_requested": codex_app_server_goal_requested,
        "codex_app_server_goal_worker_adapter_present": (
            codex_app_server_goal_adapter_present
        ),
        "codex_app_server_goal_worker_plan_schema": str(
            launch.get("codex_app_server_goal_worker_plan_schema") or ""
        )[:100],
        "codex_app_server_goal_worker_required_methods": [
            str(method or "")[:80]
            for method in (
                launch.get("codex_app_server_goal_worker_required_methods")
                if isinstance(
                    launch.get("codex_app_server_goal_worker_required_methods"), list
                )
                else []
            )
        ],
        "codex_app_server_goal_worker_turn_start_required": (
            launch.get("codex_app_server_goal_worker_turn_start_required") is True
        ),
        "codex_app_server_goal_proof_present": codex_app_server_goal_proof_present,
        "codex_goal_mode_invocation_surface": codex_goal_mode_invocation_surface,
        "codex_goal_mode_required_invocation_surface": (
            "codex_app_server_thread_goal_set_get"
            if (codex_goal_mode_requested or codex_app_server_goal_requested)
            else ""
        ),
        "codex_goal_mode_baseline_claim_allowed": (
            codex_goal_mode_baseline_claim_allowed
        ),
        "codex_goal_mode_baseline_claim_blocker": (
            codex_goal_mode_baseline_claim_blocker
        ),
        "goal_harness_access_packet_absent": (
            codex_app_server_goal_requested
            or (
            "goal_harness_access_packet_mode="
            + TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
            )
            in argv
        ),
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
    case_goal_state_init_required: bool = False,
    case_goal_state_initialized_before_agent: bool = False,
    case_goal_state_init_status: str | None = None,
    case_goal_state_path: str | None = None,
    case_goal_state_schema_version: str | None = None,
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
    counters = {
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
    if case_goal_state_init_required or case_goal_state_path:
        counters.update(
            {
                "case_goal_state_init_required": bool(
                    case_goal_state_init_required
                ),
                "case_goal_state_initialized_before_agent": bool(
                    case_goal_state_initialized_before_agent
                ),
                "case_goal_state_init_status": (
                    case_goal_state_init_status
                    or (
                        "passed"
                        if case_goal_state_initialized_before_agent
                        else "not_started"
                    )
                ),
                "case_goal_state_schema_version": (
                    case_goal_state_schema_version
                    or BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
                ),
                "case_goal_state_path": (
                    case_goal_state_path or TERMINAL_BENCH_CASE_STATE_PATH
                ),
                "goal_harness_case_state_reads": 0,
                "goal_harness_case_state_writes": (
                    1 if case_goal_state_initialized_before_agent else 0
                ),
                "goal_harness_case_state_path_count": 1,
            }
        )
    return counters

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

def build_terminal_bench_case_state_init_contract(
    *,
    initialized_by_launch_packet: bool = False,
) -> dict[str, object]:
    """Return the shared Goal Harness case active-state contract."""

    return benchmark_case_active_state_init_contract(
        benchmark_id=TERMINAL_BENCH_CASE_STATE_BENCHMARK_ID,
        goal_id=TERMINAL_BENCH_CASE_GOAL_ID,
        case_state_path=TERMINAL_BENCH_CASE_STATE_PATH,
        initialized_by_launch_packet=initialized_by_launch_packet,
    )

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
                cwd=Path(__file__).resolve().parents[2],
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
    case_state_contract = build_terminal_bench_case_state_init_contract()
    case_state_lines = [
        "case_goal_state_init_flow: "
        + str(case_state_contract.get("init_flow") or ""),
        "case_goal_state_init_stage: "
        + str(case_state_contract.get("init_stage") or ""),
        "case_goal_state_init_required_before_worker: "
        + str(case_state_contract.get("init_required_before_worker")).lower(),
        "case_goal_state_path: "
        + str(case_state_contract.get("case_state_path") or ""),
        "case_goal_state_schema_version: "
        + str(case_state_contract.get("schema_version") or ""),
        "case_goal_state_proof_fields: "
        + ",".join(str(field) for field in BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS),
        "case_goal_state_surrogate_state_files_allowed: "
        + str(case_state_contract.get("surrogate_state_files_allowed")).lower(),
    ]
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
            *case_state_lines,
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
        case_goal_state_init_required=True,
        case_goal_state_initialized_before_agent=False,
        case_goal_state_init_status="fixture_contract_only",
        case_goal_state_path=TERMINAL_BENCH_CASE_STATE_PATH,
    )
    case_state_contract = build_terminal_bench_case_state_init_contract()
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
            "case_state_init_contract": case_state_contract,
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
        "codex-app-server-goal",
        "codex-goal-harness",
        "goal-harness-managed-codex",
    ):
        raise ValueError(
            "--preflight-guard is only supported for hardened-codex, codex-goal-mode, "
            "codex-app-server-goal, codex-goal-harness, or goal-harness-managed-codex"
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
            else "codex_app_server_goal_baseline_preflight_guard"
            if mode == "codex-app-server-goal"
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
            else "public_codex_app_server_goal_baseline_preflight_guard"
            if mode == "codex-app-server-goal"
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
        if mode == "codex-app-server-goal":
            validation["codex_goal_mode_invocation_surface_checked"] = True
            validation["codex_app_server_goal_worker_adapter_absent"] = True
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
    elif mode == "codex-app-server-goal":
        interaction_counters = build_terminal_bench_goal_harness_interaction_counters(
            prompt_policy_injected=False,
            harness_skill_or_packet_injected=False,
            case_result_writeback="codex_app_server_goal_baseline_prelaunch_only",
            counter_trust_level="codex_app_server_goal_worker_adapter_absent",
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
        else TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_BASELINE_MODE
        if mode == "codex-app-server-goal"
        else TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODE
        if mode == "hardened-codex"
        else "goal_harness_managed_codex"
    )
    runner_goal_harness_ablation_mode = (
        "codex_goal_mode_baseline"
        if mode == "codex-goal-mode"
        else "codex_app_server_goal_baseline"
        if mode == "codex-app-server-goal"
        else "hardened_codex_baseline"
        if mode == "hardened-codex"
        else "goal_harness_managed"
    )
    runner_access_packet_mode = (
        TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        if mode in ("codex-goal-mode", "codex-app-server-goal", "hardened-codex")
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
            "codex-app-server-goal",
        )
        else []
    )
    private_runner_launch_summary: dict[str, Any] = {}
    if mode in (
        "codex-goal-harness",
        "goal-harness-managed-codex",
        "hardened-codex",
        "codex-goal-mode",
        "codex-app-server-goal",
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
                    "codex_goal_mode_required_invocation_surface": (
                        "codex_app_server_thread_goal_set_get"
                    ),
                    "codex_app_server_goal_proof_present": False,
                    "codex_goal_mode_baseline_claim_allowed": False,
                    "codex_goal_mode_baseline_claim_blocker": (
                        "missing_codex_app_server_goal_proof"
                    ),
                    "goal_harness_access_packet_absent": True,
                    "goal_harness_cli_bridge_absent": True,
                    "real_interface_use_observed": False,
                    "uplift_claim_allowed": False,
                }
            )
            benchmark_run["claim_gate"] = {
                "schema_version": "terminal_bench_codex_goal_baseline_claim_gate_v0",
                "requires_private_no_upload": True,
                "requires_codex_app_server_goal_proof": True,
                "slash_command_is_unverified_fallback": True,
                "baseline_claim_allowed": False,
                "first_blocker": "missing_codex_app_server_goal_proof",
            }
        if mode == "codex-app-server-goal":
            benchmark_run["preflight_guard"].update(
                {
                    "codex_goal_mode_invocation_surface_checked": True,
                    "codex_goal_mode_invocation_surface": (
                        "codex_app_server_thread_goal_set_get"
                    ),
                    "codex_goal_mode_required_invocation_surface": (
                        "codex_app_server_thread_goal_set_get"
                    ),
                    "codex_app_server_goal_baseline_requested": True,
                    "codex_app_server_goal_worker_adapter_present": True,
                    "codex_app_server_goal_worker_plan_schema": (
                        CODEX_APP_SERVER_GOAL_WORKER_SCHEMA_VERSION
                    ),
                    "codex_app_server_goal_worker_turn_start_required": True,
                    "codex_app_server_goal_proof_present": False,
                    "codex_goal_mode_baseline_claim_allowed": False,
                    "codex_goal_mode_baseline_claim_blocker": (
                        TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_TURN_PROOF_BLOCKER
                    ),
                    "goal_harness_access_packet_absent": True,
                    "goal_harness_cli_bridge_absent": True,
                    "real_interface_use_observed": False,
                    "uplift_claim_allowed": False,
                }
            )
            benchmark_run["claim_gate"] = {
                "schema_version": "terminal_bench_codex_goal_baseline_claim_gate_v0",
                "requires_private_no_upload": True,
                "requires_codex_app_server_goal_proof": True,
                "requires_codex_app_server_worker_adapter": True,
                "slash_command_is_unverified_fallback": False,
                "baseline_claim_allowed": False,
                "first_blocker": (
                    TERMINAL_BENCH_CODEX_APP_SERVER_GOAL_TURN_PROOF_BLOCKER
                ),
            }
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
