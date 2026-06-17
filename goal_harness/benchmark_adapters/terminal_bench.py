from __future__ import annotations

from ..worker_bridge import (
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_MOUNT_TARGET,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON as TERMINAL_BENCH_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON as TERMINAL_BENCH_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    GOAL_HARNESS_ACTIVE_USER_HOST_DIR_PLACEHOLDER as TERMINAL_BENCH_WORKER_BRIDGE_ACTIVE_USER_HOST_DIR_PLACEHOLDER,
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER as TERMINAL_BENCH_WORKER_BRIDGE_PROJECT_ROOT_PLACEHOLDER,
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER as TERMINAL_BENCH_WORKER_BRIDGE_RUNTIME_ROOT_PLACEHOLDER,
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
