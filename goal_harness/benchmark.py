from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

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
    WORKER_BRIDGE_BENCHMARK_RUN_REQUIRED_TOP_LEVEL_FIELDS,
    WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION,
    WORKER_BRIDGE_SURFACE,
    build_active_user_intervention,
    build_worker_bridge_install_contract,
)


TERMINAL_BENCH_MODES = (
    "hardened-codex",
    "passive-observed-codex",
    "codex-goal-harness",
    "goal-harness-managed-codex",
)

TERMINAL_BENCH_DEFAULT_DATASET = "terminal-bench-sample@2.0"
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
        command: 0 for command in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS
    }
    read_commands = {"status", "quota_should_run", "todo_list", "history", "check"}
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
    score_failure_attribution = (
        "verifier_dependency_install_failure"
        if official_score == 0 and verifier_dependency_failure_count
        else "none"
    )
    runner_return_status = (
        "completed_with_agent_timeout"
        if agent_timeout_observed
        else "completed"
        if job_result.get("finished_at")
        else "pending"
    )
    official_score_status = "completed" if official_score is not None else "missing"
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
        pre_worker_agent_setup_failure_count=pre_worker_agent_setup_failure_count,
        codex_runtime_goal_tool_trial_count=codex_runtime_goal_tool_trial_count,
        trace_publicness=trace_publicness,
    )
    no_upload_requested = "--upload" not in invocation and "upload" not in invocation

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


def build_terminal_bench_private_runner_launch(**command_kwargs: Any) -> dict[str, Any]:
    """Build the real private Harbor launch argv together with its env.

    `build_terminal_bench_managed_harbor_command` returns only argv so docs and
    fixtures can show a safe command template. Real launches also need the
    Goal Harness probe PATH; otherwise non-interactive shells can miss Docker or
    uvx even when the preflight surface is ready.
    """

    env = build_terminal_bench_private_runner_env()
    resolved_command_kwargs = _private_runner_command_kwargs(command_kwargs)
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
    first_blocker = _managed_preflight_first_blocker(surface)
    return {
        "schema_version": "terminal_bench_private_runner_launch_v0",
        "argv": argv,
        "env": env,
        "uses_private_runner_env": True,
        "preflight_surface": surface,
        "first_blocker": first_blocker,
        "ready": first_blocker == "ready_for_private_managed_no_upload_pilot_review",
    }


def summarize_terminal_bench_private_runner_launch(
    launch: dict[str, Any],
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
    return {
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
        "auth_surface_names_present": auth_names_present,
        "auth_values_recorded": False,
        "raw_env_recorded": False,
        "raw_paths_recorded": False,
    }


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
        command: 0 for command in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS
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
        "sequence_steps": [
            "launch_single_codex_goal_harness_worker_with_no_upload",
            "record_worker_start_seq_before_first_poll",
            "append_public_safe_simulator_intervention_with_seq_gt_worker_start_seq",
            "worker_polls_active_user_observe_after_start",
            "ingest_worker_observation_as_non_official_collaboration_evidence",
        ],
        "required_evidence": [
            "worker_start_seq_recorded",
            "post_start_intervention_seq_recorded",
            "active_user_observe_worker_cli_call_recorded",
            "worker_observation_proof_true",
            "official_score_kind_not_run_or_separate",
        ],
        "stop_conditions": [
            "hidden_tests_or_expected_solution_visible",
            "credential_value_needed",
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
    job_name: str = "terminal_bench_sample_build_cython_ext_goal_harness_managed_codex_pilot",
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

    managed_runner_command_preview = (
        build_terminal_bench_managed_harbor_command(
            job_name=(
                "terminal_bench_sample_build_cython_ext_codex_goal_harness_pilot"
                if mode == "codex-goal-harness"
                else "terminal_bench_hardened_codex_baseline"
                if mode == "hardened-codex"
                else "terminal_bench_sample_build_cython_ext_goal_harness_managed_codex_pilot"
            ),
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
    if mode in ("codex-goal-harness", "goal-harness-managed-codex") and preflight_guard:
        private_runner_launch_summary = summarize_terminal_bench_private_runner_launch(
            {
                "schema_version": "terminal_bench_private_runner_launch_v0",
                "argv": build_terminal_bench_managed_harbor_command(
                    job_name=(
                        "terminal_bench_sample_build_cython_ext_codex_goal_harness_pilot"
                        if mode == "codex-goal-harness"
                        else "terminal_bench_sample_build_cython_ext_goal_harness_managed_codex_pilot"
                    ),
                    goal_harness_mode=(
                        "codex_goal_harness"
                        if mode == "codex-goal-harness"
                        else "goal_harness_managed_codex"
                    ),
                    goal_harness_cli_bridge_enabled=(
                        worker_cli_bridge_fixture or active_cli_bridge_preflight
                    ),
                    goal_harness_active_user_intervention_enabled=(
                        active_user_assisted_treatment_preflight
                    ),
                    timeout_multiplier=timeout_multiplier,
                    agent_timeout_multiplier=agent_timeout_multiplier,
                    verifier_timeout_multiplier=verifier_timeout_multiplier,
                    agent_setup_timeout_multiplier=agent_setup_timeout_multiplier,
                    environment_build_timeout_multiplier=environment_build_timeout_multiplier,
                    resolve_cli_paths=True,
                ),
                "env": build_terminal_bench_private_runner_env(),
                "uses_private_runner_env": True,
                "preflight_surface": surface,
                "first_blocker": first_blocker,
                "ready": first_blocker == "ready_for_private_managed_no_upload_pilot_review"
                and not active_user_assisted_treatment_preflight,
            }
        )

    benchmark_run: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "goal_harness_terminal_bench_cli_skeleton",
        "benchmark_id": dataset,
        "job_name": f"{dataset.replace('@', '_').replace('.', '_')}_{task_id}_{contract['event_mode']}",
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
            "simulator_setting": "deterministic_scripted_user",
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
                        "simulator_setting": "deterministic_scripted_user",
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
