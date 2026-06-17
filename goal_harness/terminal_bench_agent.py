from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from goal_harness.benchmark import (
    TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING,
    TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING,
    TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE,
    TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION,
    TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_MODE,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_VERSION,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION,
    TERMINAL_BENCH_GOAL_HARNESS_COUNTER_TRACE_COMMANDS,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM,
    TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE,
    TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES,
    TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE,
    TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA,
    build_terminal_bench_goal_harness_access_packet,
    build_terminal_bench_goal_harness_interaction_counters,
    build_terminal_bench_single_agent_episode_policy,
)
from goal_harness.benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_path,
    benchmark_case_active_state_seed_text,
    benchmark_case_active_state_write_command,
    benchmark_case_goal_id,
)
from goal_harness.worker_bridge import (
    ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    DEFAULT_WORKER_BRIDGE_TRACE_DIR,
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
    WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION,
    build_worker_bridge_benchmark_run_from_counters,
    build_worker_bridge_command_prefix,
    build_worker_bridge_python_runtime_preflight_command,
    worker_bridge_cli_call_total_from_interaction_counters,
    write_worker_bridge_benchmark_run_file,
)

CODEX_GOAL_HARNESS_MODE = "codex_goal_harness"
CODEX_GOAL_MODE_BASELINE_MODE = TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_MODE
GOAL_HARNESS_MANAGED_CODEX_MODE = "goal_harness_managed_codex"
GOAL_HARNESS_MANAGED_CODEX_POLICY_VERSION = "goal_harness_terminal_bench_policy_v0"
GOAL_HARNESS_MANAGED_CODEX_BEHAVIOR_SPEC_ID = (
    "terminal_bench_goal_harness_managed_codex_v0"
)
CODEX_SESSION_TOKEN_COUNT_USAGE_SOURCE = "codex_cli_session_token_count_event"
GOAL_HARNESS_COUNTER_TRACE_SCHEMA_VERSION = (
    "terminal_bench_goal_harness_counter_trace_v0"
)
TERMINAL_BENCH_CASE_GOAL_ID = benchmark_case_goal_id("terminal-bench")
TERMINAL_BENCH_CASE_STATE_PATH = benchmark_case_active_state_path(
    TERMINAL_BENCH_CASE_GOAL_ID
)
DEFAULT_GOAL_HARNESS_WORKER_COMMAND_PREFIX = build_worker_bridge_command_prefix()
DEFAULT_GOAL_HARNESS_WORKER_RUNTIME_PREFLIGHT_COMMAND = (
    build_worker_bridge_python_runtime_preflight_command()
)
DEFAULT_GOAL_HARNESS_WORKER_REGISTRY_ARG = (
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER + "/registry.global.json"
)
DEFAULT_GOAL_HARNESS_WORKER_SCAN_PATH = (
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER + "/goal_harness/benchmark.py"
)
CODEX_REQUIRE_EXISTING_BLOCKER_NOT_ON_PATH = "codex_cli_not_on_path"
CODEX_REQUIRE_EXISTING_BLOCKER_VERSION_PROBE_FAILED = (
    "codex_cli_version_probe_failed"
)
CODEX_REQUIRE_EXISTING_BLOCKER_SYMLINK_REPAIR_FAILED = (
    "codex_cli_symlink_repair_failed"
)
DEFAULT_CODEX_PREFLIGHT_TIMEOUT_SEC = 45
UNRESOLVED_ANGLE_PLACEHOLDER_RE = re.compile(r"<[^>\s]+>")


def _concrete_active_user_observe_command(
    command: str,
    *,
    worker_start_seq: int = 0,
) -> str | None:
    """Return a worker-runnable active-user observe command when it is concrete."""

    text = str(command or "").strip()
    if not text or text in {
        "<active-user-observe-command>",
        "<active-user-observe-command-redacted>",
    }:
        return None
    text = text.replace("<worker-start-seq>", str(worker_start_seq))
    if UNRESOLVED_ANGLE_PLACEHOLDER_RE.search(text):
        return None
    return text


def build_private_active_user_observe_instruction(
    *,
    enabled: bool,
    observe_command: str,
    observation_json: str,
    counter_trace_json: str,
    goal_id: str,
    mode: str,
    classification: str,
) -> str:
    """Build the private worker-only active-user observe checkpoint."""

    if not enabled:
        return ""
    concrete_command = _concrete_active_user_observe_command(
        observe_command,
        worker_start_seq=0,
    )
    if concrete_command is None:
        return (
            "\nActive-user observe checkpoint for this case:\n"
            "- The active-user channel is enabled, but no runnable private observe command was provided.\n"
            "- Do not claim active-user observation unless a concrete observe command is available and executed.\n\n"
        )
    trace_example = {
        "kind": "goal_harness_cli_call",
        "command": TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND,
        "ok": True,
        "goal_id": goal_id,
        "mode": mode,
        "classification": classification,
    }
    return (
        "\nActive-user observe checkpoint for this case:\n"
        "- The active-user channel is enabled. This private worker checkpoint supplies the runnable observe command; the public access packet may redact it.\n"
        "- Before broad task work, run this exact command once:\n"
        f"  {concrete_command}\n"
        "- If no post-start intervention is observed, run the same observe command once more before final validation or a terminal blocker decision.\n"
        f"- Read {observation_json} after the command. If observed_after_worker_start is true, apply only the compact latest_intervention.message and boundary fields.\n"
        f"- Append one compact trace row to {counter_trace_json} for each observe attempt; use command={TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND} and public-safe fields like:\n"
        f"  {json.dumps(trace_example, sort_keys=True)}\n"
        "- Do not paste raw feed contents, raw paths, credentials, hidden tests, expected solutions, or transcripts into the final answer.\n\n"
    )


def build_codex_goal_mode_baseline_instruction(task_instruction: str) -> str:
    """Build a /goal-prefixed baseline prompt without Goal Harness state.

    This requests goal-mode-like behavior. Native Codex CLI goal-mode
    confirmation requires separate interactive slash-command or goal-state
    evidence.
    """

    return (
        "/goal Complete the following Terminal-Bench task. Keep working until "
        "the task is done, validated, or blocked by the benchmark environment.\n\n"
        f"{task_instruction}"
    )


def build_managed_terminal_bench_instruction(
    task_instruction: str,
    *,
    policy_version: str = GOAL_HARNESS_MANAGED_CODEX_POLICY_VERSION,
    behavior_spec_id: str = GOAL_HARNESS_MANAGED_CODEX_BEHAVIOR_SPEC_ID,
    ablation_mode: str = "goal_harness_managed",
    goal_harness_mode: str = GOAL_HARNESS_MANAGED_CODEX_MODE,
    goal_id: str = "<goal-id>",
    goal_harness_access_packet_mode: str = (
        TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL
    ),
    goal_harness_cli_bridge_enabled: bool = False,
    goal_harness_command_prefix: str = DEFAULT_GOAL_HARNESS_WORKER_COMMAND_PREFIX,
    goal_harness_registry_arg: str = DEFAULT_GOAL_HARNESS_WORKER_REGISTRY_ARG,
    goal_harness_runtime_root_arg: str = GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
    goal_harness_scan_path: str = DEFAULT_GOAL_HARNESS_WORKER_SCAN_PATH,
    goal_harness_benchmark_run_json: str = DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    goal_harness_counter_trace_json: str = DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    goal_harness_classification: str = "<classification>",
    goal_harness_append_execute_enabled: bool = False,
    goal_harness_active_user_intervention_enabled: bool = False,
    goal_harness_active_user_feed_jsonl: str = DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    goal_harness_active_user_observation_json: str = DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    goal_harness_active_user_observe_command: str = "<active-user-observe-command>",
    goal_harness_active_user_channel_surface: str = ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
    goal_harness_case_state_path: str = TERMINAL_BENCH_CASE_STATE_PATH,
    goal_harness_case_state_schema_version: str = BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    goal_harness_case_state_required: bool = True,
) -> str:
    """Wrap a benchmark task with the minimal Goal Harness managed policy."""

    if (
        goal_harness_mode in TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES
        and goal_harness_access_packet_mode
        == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    ):
        return task_instruction
    if (
        goal_harness_mode == CODEX_GOAL_MODE_BASELINE_MODE
        and goal_harness_access_packet_mode
        == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    ):
        return build_codex_goal_mode_baseline_instruction(task_instruction)

    access_packet = ""
    access_packet_enabled = (
        goal_harness_mode == CODEX_GOAL_HARNESS_MODE
        and goal_harness_access_packet_mode
        != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    )
    if access_packet_enabled:
        access_packet_body = build_terminal_bench_goal_harness_access_packet(
            goal_id=goal_id,
            packet_mode=goal_harness_access_packet_mode,
            cli_bridge_available=goal_harness_cli_bridge_enabled,
            command_prefix=goal_harness_command_prefix,
            registry_arg=goal_harness_registry_arg,
            runtime_root_arg=goal_harness_runtime_root_arg,
            scan_path=goal_harness_scan_path,
            benchmark_run_json=goal_harness_benchmark_run_json,
            counter_trace_json=goal_harness_counter_trace_json,
            classification=goal_harness_classification,
            append_execute_enabled=goal_harness_append_execute_enabled,
            active_user_intervention_enabled=(
                goal_harness_active_user_intervention_enabled
            ),
            active_user_feed_jsonl=goal_harness_active_user_feed_jsonl,
            active_user_observation_json=goal_harness_active_user_observation_json,
            active_user_observe_command=goal_harness_active_user_observe_command,
            active_user_channel_surface=goal_harness_active_user_channel_surface,
        )
        access_packet = (
            "\nGoal Harness access packet for this case:\n\n"
            "----- GOAL-HARNESS ACCESS PACKET -----\n"
            f"{access_packet_body}\n"
            "----- END GOAL-HARNESS ACCESS PACKET -----\n\n"
        )
    active_user_observe_instruction = build_private_active_user_observe_instruction(
        enabled=(
            access_packet_enabled
            and goal_harness_cli_bridge_enabled
            and goal_harness_active_user_intervention_enabled
        ),
        observe_command=goal_harness_active_user_observe_command,
        observation_json=goal_harness_active_user_observation_json,
        counter_trace_json=goal_harness_counter_trace_json,
        goal_id=goal_id,
        mode=goal_harness_mode,
        classification=goal_harness_classification,
    )
    case_state_instruction = ""
    if goal_harness_case_state_required and goal_harness_case_state_path:
        case_state_instruction = (
            "Goal Harness benchmark case-state contract:\n"
            f"- Canonical active state path: `{goal_harness_case_state_path}`.\n"
            f"- Active state schema: `{goal_harness_case_state_schema_version}`.\n"
            "- The runner initializes this file before the Codex worker starts.\n"
            "- Read and maintain this case-local active state as the control surface; "
            "do not use benchmark-specific surrogate state files.\n\n"
        )

    return (
        "You are running one Terminal-Bench task under Goal Harness managed Codex mode.\n"
        f"Policy version: {policy_version}.\n"
        f"Behavior spec: {behavior_spec_id}.\n"
        f"Ablation mode: {ablation_mode}.\n\n"
        "Goal Harness operating rules for this case:\n"
        "- Solve the benchmark task normally inside the provided case environment.\n"
        "- Keep all raw traces, credentials, auth files, host paths, and private logs out of final answers.\n"
        "- Do not upload, publish, share, or claim leaderboard evidence.\n"
        "- Prefer small verifiable edits, recheck the result after meaningful changes, and report a concise blocker if the task cannot be completed.\n"
        "- If a Goal Harness CLI bridge packet is present, treat command lines as templates: replace placeholders before execution, quote paths as single argv values, and do not run commands containing unresolved angle-bracket placeholders.\n"
        "- Write the compact Goal Harness case result only after final validation and cleanup, or after a terminal blocker decision; the runner still performs guaranteed final archive writeback.\n"
        "- Treat this as a model plus harness pair; do not present it as a native Codex baseline.\n\n"
        f"{case_state_instruction}"
        f"{active_user_observe_instruction}"
        f"{access_packet}"
        "Benchmark task instruction follows.\n\n"
        "----- TERMINAL-BENCH TASK -----\n"
        f"{task_instruction}"
    )


def _task_hash(task_instruction: str) -> str:
    return hashlib.sha256(task_instruction.encode("utf-8")).hexdigest()[:16]


def _merge_metadata(context: AgentContext, payload: dict[str, Any]) -> None:
    metadata = dict(context.metadata or {})
    goal_harness = dict(metadata.get("goal_harness") or {})
    goal_harness.update(payload)
    metadata["goal_harness"] = goal_harness
    context.metadata = metadata


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _coerce_positive_timeout_sec(value: Any, *, default: int) -> int:
    if value in (None, ""):
        return default
    parsed = _coerce_int(value)
    if parsed is None and isinstance(value, str):
        text = value.strip()
        try:
            parsed_float = float(text)
        except ValueError:
            parsed_float = -1.0
        if parsed_float.is_integer():
            parsed = int(parsed_float)
    if parsed is None or parsed <= 0:
        raise ValueError(
            "goal_harness_codex_preflight_timeout_sec must be a positive integer"
        )
    return parsed


def _compact_trace_event_text(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def extract_goal_harness_interaction_counters_from_trace(
    counter_trace: list[dict[str, Any]] | None,
    *,
    prompt_policy_injected: bool,
    harness_skill_or_packet_injected: bool,
    case_result_writeback: str = "not_observed_custom_agent_metadata",
    no_trace_counter_trust_level: str = "runtime_metadata_no_trace_observed",
) -> dict[str, Any]:
    """Count compact public interaction trace rows into benchmark counters."""

    runtime_goal_calls = {
        "create_goal": 0,
        "update_goal": 0,
    }
    goal_harness_cli_calls = {
        command: 0 for command in TERMINAL_BENCH_GOAL_HARNESS_COUNTER_TRACE_COMMANDS
    }
    state_reads = 0
    state_writes = 0
    writeback = case_result_writeback
    trace_rows = counter_trace or []
    append_attempted = False
    append_dry_run_ok = False
    append_execute_ok = False
    append_schema_rejected = False

    for event in trace_rows:
        if not isinstance(event, dict):
            continue
        kind = _compact_trace_event_text(
            event.get("kind") or event.get("type") or event.get("event")
        )
        if not kind and event.get("command"):
            kind = "goal_harness_cli_call"
        if not kind and event.get("call"):
            kind = "goal_harness_cli_call"
        if kind == "codex_runtime_goal_tool_call":
            tool_name = _compact_trace_event_text(event.get("name") or event.get("tool"))
            if tool_name in runtime_goal_calls:
                runtime_goal_calls[tool_name] += 1
            continue
        if kind == "goal_harness_cli_call":
            command = _compact_trace_event_text(event.get("command") or event.get("call"))
            if command in goal_harness_cli_calls:
                goal_harness_cli_calls[command] += 1
            if command == TERMINAL_BENCH_GOAL_HARNESS_ACTIVE_USER_OBSERVE_COMMAND:
                state_reads += 1
            if command == "append_benchmark_run":
                append_attempted = True
                append_schema_rejected = append_schema_rejected or (
                    _compact_trace_event_text(event.get("error_kind"))
                    in {"schema", "schema_rejected"}
                )
                if event.get("ok") is True and event.get("dry_run") is True:
                    append_dry_run_ok = True
                elif event.get("ok") is True:
                    append_execute_ok = True
            continue
        if kind == "goal_harness_state_read":
            state_reads += 1
            continue
        if kind == "goal_harness_state_write":
            state_writes += 1
            continue
        if kind == "case_result_writeback":
            candidate = _compact_trace_event_text(event.get("target"))
            if candidate:
                writeback = candidate

    if writeback == case_result_writeback:
        if append_execute_ok:
            writeback = "worker_bridge_append_benchmark_run_execute"
            state_writes += 1
        elif append_dry_run_ok:
            writeback = "worker_bridge_append_benchmark_run_dry_run"
        elif append_schema_rejected:
            writeback = "worker_bridge_append_benchmark_run_schema_rejected"
        elif append_attempted:
            writeback = "worker_bridge_append_benchmark_run_failed"

    return build_terminal_bench_goal_harness_interaction_counters(
        prompt_policy_injected=prompt_policy_injected,
        harness_skill_or_packet_injected=harness_skill_or_packet_injected,
        codex_runtime_goal_tool_calls=runtime_goal_calls,
        goal_harness_cli_calls=goal_harness_cli_calls,
        goal_harness_state_reads=state_reads,
        goal_harness_state_writes=state_writes,
        case_result_writeback=writeback,
        counter_trust_level=(
            "compact_trace_audited" if trace_rows else no_trace_counter_trust_level
        ),
    )


def load_goal_harness_counter_trace_file(path: str | Path | None) -> list[dict[str, Any]]:
    """Load compact Goal Harness counter trace JSONL rows from a private path."""

    if not path:
        return []
    trace_path = Path(path)
    try:
        lines = trace_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    rows: list[dict[str, Any]] = []
    allowed_keys = {
        "kind",
        "type",
        "event",
        "command",
        "call",
        "ok",
        "dry_run",
        "error_kind",
        "surface",
        "action",
        "target",
        "name",
        "tool",
        "goal_id",
        "mode",
        "goal_harness_mode",
        "classification",
        "trace_schema_version",
        "benchmark_run_schema_version",
    }
    for line in lines[:200]:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        compact: dict[str, str | int | float | bool] = {}
        for key, value in payload.items():
            if key not in allowed_keys or not isinstance(value, (str, int, float, bool)):
                continue
            compact[key] = value if isinstance(value, (int, float, bool)) else value[:120]
        if compact:
            rows.append(compact)
    return rows


def extract_codex_session_usage(session_dir: Path) -> dict[str, int] | None:
    """Extract the last compact token-count total from Codex session JSONL."""

    latest_usage: dict[str, int] | None = None
    for session_file in sorted(session_dir.glob("*.jsonl")):
        try:
            lines = session_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") != "event_msg":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            total_usage = info.get("total_token_usage")
            if not isinstance(total_usage, dict):
                continue

            input_tokens = _coerce_int(total_usage.get("input_tokens"))
            output_tokens = _coerce_int(total_usage.get("output_tokens"))
            if input_tokens is None or output_tokens is None:
                continue

            usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            cache_tokens = _coerce_int(total_usage.get("cached_input_tokens"))
            if cache_tokens is not None:
                usage["cache_tokens"] = cache_tokens
            reasoning_output_tokens = _coerce_int(
                total_usage.get("reasoning_output_tokens")
            )
            if reasoning_output_tokens is not None:
                usage["reasoning_output_tokens"] = reasoning_output_tokens
            total_tokens = _coerce_int(total_usage.get("total_tokens"))
            if total_tokens is not None:
                usage["total_tokens"] = total_tokens
            latest_usage = usage

    return latest_usage


def _context_has_usage(context: AgentContext) -> bool:
    return any(
        value is not None
        for value in (
            context.n_input_tokens,
            context.n_cache_tokens,
            context.n_output_tokens,
            context.cost_usd,
        )
    )


class GoalHarnessManagedCodex(Codex):
    """Harbor custom agent that runs Codex with a Goal Harness policy envelope."""

    @staticmethod
    def name() -> str:
        return "goal-harness-managed-codex"

    def __init__(
        self,
        *args: Any,
        goal_harness_policy_version: str = GOAL_HARNESS_MANAGED_CODEX_POLICY_VERSION,
        goal_harness_behavior_spec_id: str = GOAL_HARNESS_MANAGED_CODEX_BEHAVIOR_SPEC_ID,
        goal_harness_ablation_mode: str = "goal_harness_managed",
        goal_harness_mode: str = GOAL_HARNESS_MANAGED_CODEX_MODE,
        goal_harness_codex_install_strategy: str = (
            TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_RUNTIME_INSTALL_IF_MISSING
        ),
        goal_harness_codex_preflight_timeout_sec: int | str | None = (
            DEFAULT_CODEX_PREFLIGHT_TIMEOUT_SEC
        ),
        goal_harness_worker_codex_materialization_strategy: str = "",
        goal_harness_worker_materialization_probe_only: bool = False,
        goal_harness_goal_id: str = "<goal-id>",
        goal_harness_access_packet_mode: str = (
            TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL
        ),
        goal_harness_trace_publicness: str = "private_raw_trace_compact_public_summary",
        goal_harness_counter_trace: list[dict[str, Any]] | None = None,
        goal_harness_cli_bridge_enabled: bool = False,
        goal_harness_command_prefix: str = DEFAULT_GOAL_HARNESS_WORKER_COMMAND_PREFIX,
        goal_harness_runtime_preflight_command: str = (
            DEFAULT_GOAL_HARNESS_WORKER_RUNTIME_PREFLIGHT_COMMAND
        ),
        goal_harness_registry_arg: str = DEFAULT_GOAL_HARNESS_WORKER_REGISTRY_ARG,
        goal_harness_runtime_root_arg: str = GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
        goal_harness_scan_path: str = DEFAULT_GOAL_HARNESS_WORKER_SCAN_PATH,
        goal_harness_benchmark_run_json: str = DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
        goal_harness_benchmark_run_schema_version: str = "benchmark_run_v0",
        goal_harness_benchmark_run_writeback_contract: str = (
            WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION
        ),
        goal_harness_counter_trace_json: str = DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
        goal_harness_classification: str = "<classification>",
        goal_harness_append_execute_enabled: bool = False,
        goal_harness_active_user_intervention_enabled: bool = False,
        goal_harness_active_user_feed_jsonl: str = DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
        goal_harness_active_user_observation_json: str = DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
        goal_harness_active_user_observe_command: str = "<active-user-observe-command>",
        goal_harness_active_user_channel_surface: str = ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
        **kwargs: Any,
    ) -> None:
        self.goal_harness_policy_version = goal_harness_policy_version
        self.goal_harness_behavior_spec_id = goal_harness_behavior_spec_id
        self.goal_harness_ablation_mode = goal_harness_ablation_mode
        self.goal_harness_mode = goal_harness_mode
        if goal_harness_codex_install_strategy not in TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES:
            raise ValueError(
                "goal_harness_codex_install_strategy must be one of: "
                + ", ".join(TERMINAL_BENCH_CODEX_INSTALL_STRATEGIES)
            )
        self.goal_harness_codex_install_strategy = goal_harness_codex_install_strategy
        self.goal_harness_codex_preflight_timeout_sec = _coerce_positive_timeout_sec(
            goal_harness_codex_preflight_timeout_sec,
            default=DEFAULT_CODEX_PREFLIGHT_TIMEOUT_SEC,
        )
        if (
            goal_harness_worker_codex_materialization_strategy
            and goal_harness_worker_codex_materialization_strategy
            not in TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES
        ):
            raise ValueError(
                "goal_harness_worker_codex_materialization_strategy must be one of: "
                + ", ".join(TERMINAL_BENCH_WORKER_CODEX_MATERIALIZATION_STRATEGIES)
            )
        self.goal_harness_worker_codex_materialization_strategy = (
            goal_harness_worker_codex_materialization_strategy
        )
        self.goal_harness_worker_materialization_probe_only = bool(
            goal_harness_worker_materialization_probe_only
        )
        self.goal_harness_goal_id = goal_harness_goal_id
        if goal_harness_access_packet_mode not in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES:
            raise ValueError(
                "goal_harness_access_packet_mode must be one of: "
                + ", ".join(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES)
            )
        self.goal_harness_access_packet_mode = goal_harness_access_packet_mode
        self.goal_harness_trace_publicness = goal_harness_trace_publicness
        self.goal_harness_counter_trace = goal_harness_counter_trace or []
        self.goal_harness_cli_bridge_enabled = bool(goal_harness_cli_bridge_enabled)
        self.goal_harness_command_prefix = goal_harness_command_prefix
        self.goal_harness_runtime_preflight_command = goal_harness_runtime_preflight_command
        self.goal_harness_registry_arg = goal_harness_registry_arg
        self.goal_harness_runtime_root_arg = goal_harness_runtime_root_arg
        self.goal_harness_scan_path = goal_harness_scan_path
        self.goal_harness_benchmark_run_json = goal_harness_benchmark_run_json
        self.goal_harness_benchmark_run_schema_version = (
            goal_harness_benchmark_run_schema_version
        )
        self.goal_harness_benchmark_run_writeback_contract = (
            goal_harness_benchmark_run_writeback_contract
        )
        self.goal_harness_counter_trace_json = goal_harness_counter_trace_json
        self.goal_harness_classification = goal_harness_classification
        self.goal_harness_append_execute_enabled = bool(
            goal_harness_append_execute_enabled
        )
        self.goal_harness_active_user_intervention_enabled = bool(
            goal_harness_active_user_intervention_enabled
        )
        self.goal_harness_active_user_feed_jsonl = goal_harness_active_user_feed_jsonl
        self.goal_harness_active_user_observation_json = (
            goal_harness_active_user_observation_json
        )
        self.goal_harness_active_user_observe_command = (
            goal_harness_active_user_observe_command
        )
        self.goal_harness_active_user_channel_surface = (
            goal_harness_active_user_channel_surface
        )
        self._goal_harness_context_metadata: dict[str, Any] = {}
        super().__init__(*args, **kwargs)

    def _write_goal_harness_setup_diagnostic(
        self,
        *,
        interrupted: bool,
        interrupt_reason: str,
        checkpoint_kind: str,
        codex_path_observed: bool | None = None,
    ) -> tuple[dict[str, Any], bool, str]:
        """Write public-safe setup diagnostics for every Terminal-Bench arm."""

        blocker = str(interrupt_reason or "").strip() or "worker_setup_unknown"
        payload: dict[str, Any] = {
            "schema_version": TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA,
            "checkpoint_kind": checkpoint_kind,
            "interrupted": bool(interrupted),
            "first_blocker": blocker,
            "pre_worker_startup_blocker": blocker if interrupted else "none",
            "goal_harness_mode": self.goal_harness_mode,
            "goal_harness_ablation_mode": self.goal_harness_ablation_mode,
            "goal_harness_access_packet_mode": self.goal_harness_access_packet_mode,
            "codex_install_strategy": self.goal_harness_codex_install_strategy,
            "worker_codex_materialization_strategy": (
                self.goal_harness_worker_codex_materialization_strategy
            ),
            "worker_codex_materialization_strategy_declared": bool(
                self.goal_harness_worker_codex_materialization_strategy
            ),
            "codex_preflight_timeout_sec": (
                self.goal_harness_codex_preflight_timeout_sec
            ),
            "codex_path_observed": codex_path_observed,
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_recorded": False,
            "command_output_recorded": False,
            "case_goal_state_init_required": self._benchmark_case_active_state_required(),
            "case_goal_state_path": (
                TERMINAL_BENCH_CASE_STATE_PATH
                if self._benchmark_case_active_state_required()
                else None
            ),
            "case_goal_state_schema_version": (
                BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
                if self._benchmark_case_active_state_required()
                else None
            ),
            "case_goal_state_initialized_before_agent": False,
            "case_goal_state_init_status": "not_started"
            if self._benchmark_case_active_state_required()
            else "not_applicable",
        }
        try:
            target = Path(self.logs_dir) / TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return payload, True, "worker_setup_diagnostic_written"
        except Exception:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.exception("Goal Harness setup diagnostic write failed")
            return payload, False, "worker_setup_diagnostic_write_failed"

    def _best_effort_goal_harness_setup_diagnostic(
        self,
        *,
        interrupted: bool,
        interrupt_reason: str,
        checkpoint_kind: str,
        codex_path_observed: bool | None = None,
    ) -> tuple[dict[str, Any] | None, bool, str]:
        try:
            return self._write_goal_harness_setup_diagnostic(
                interrupted=interrupted,
                interrupt_reason=interrupt_reason,
                checkpoint_kind=checkpoint_kind,
                codex_path_observed=codex_path_observed,
            )
        except Exception:
            return None, False, "worker_setup_diagnostic_write_failed"

    def _load_goal_harness_setup_diagnostic(self) -> dict[str, Any]:
        """Load the compact setup diagnostic written during install/preflight."""

        try:
            target = Path(self.logs_dir) / TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
            if not target.exists():
                return {}
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _read_goal_harness_setup_stage_marker(self) -> str:
        """Read a public-safe setup stage marker written before risky install steps."""

        try:
            target = Path(self.logs_dir) / "goal-harness-worker-setup-stage.txt"
            if not target.exists():
                return ""
            value = target.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
        if not re.fullmatch(r"[a-z0-9_]{1,96}", value):
            return ""
        return value

    def _write_goal_harness_worker_materialization_probe_result(
        self,
        *,
        interface_surface: str,
        runtime_preflight_status: str,
        interrupted: bool = False,
        interrupt_reason: str = "",
    ) -> tuple[dict[str, Any] | None, bool, str]:
        """Write a compact proof that the worker materialized Codex, not task success."""

        if not self.goal_harness_benchmark_run_json:
            return None, False, "worker_materialization_probe_path_missing"

        setup = self._load_goal_harness_setup_diagnostic()
        setup_schema_ok = (
            setup.get("schema_version") == TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA
        )
        setup_file_count = 1 if setup else 0
        setup_schema_ok_count = 1 if setup_schema_ok else 0
        setup_blocker = str(
            setup.get("pre_worker_startup_blocker")
            or setup.get("first_blocker")
            or ""
        ).strip()
        if interrupt_reason:
            setup_blocker = interrupt_reason
        setup_ok_blockers = {
            "",
            "none",
            "codex_runtime_install_or_preflight_ok",
            "codex_require_existing_preflight_ok",
        }
        setup_ok = (
            setup_schema_ok
            and setup.get("interrupted") is False
            and setup_blocker in setup_ok_blockers
            and not interrupted
        )
        materialization_status = (
            "worker_codex_materialization_verified"
            if setup_ok
            else "worker_codex_materialization_blocked"
        )
        materialization_blocker = "none" if setup_ok else setup_blocker or "setup_diagnostic_missing"
        runner_status = (
            "worker_materialization_probe_completed"
            if setup_ok
            else "worker_materialization_probe_blocked"
        )
        official_score_status = "not_run_worker_materialization_probe"
        mode = (
            "codex_goal_mode_baseline_worker_materialization_probe"
            if self._codex_goal_mode_baseline()
            else "hardened_codex_baseline_worker_materialization_probe"
            if self._hardened_codex_baseline()
            else "goal_harness_worker_materialization_probe"
        )
        claim_boundary = {
            "public_claim_allowed": "worker materialization only",
            "bridge_connectivity_claim_allowed": False,
            "case_success_claim_allowed": False,
            "official_score_claim_allowed": False,
            "leaderboard_claim_allowed": False,
            "forbidden_claims": [
                "case_success",
                "official_reward_complete",
                "leaderboard_ready",
                "uplift_over_baseline",
                "raw_trace_public",
            ],
        }
        payload: dict[str, Any] = {
            "ok": setup_ok,
            "schema_version": self.goal_harness_benchmark_run_schema_version
            or "benchmark_run_v0",
            "source_runner": "terminal_bench_worker_materialization_probe",
            "benchmark_id": "terminal-bench-worker-materialization@v0",
            "job_name": "terminal_bench_worker_materialization_probe",
            "mode": mode,
            "worker_mode": self.goal_harness_mode,
            "real_run": False,
            "worker_materialization_real_probe": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "trace_publicness": "compact_setup_diagnostic_only_no_raw_trace",
            "task_prompt_changed_by_goal_harness_policy": False,
            "raw_task_instruction_recorded": False,
            "raw_managed_prompt_recorded": False,
            "raw_interaction_trace_recorded": False,
            "credential_values_recorded": False,
            "auth_files_recorded": False,
            "command_output_recorded": False,
            "official_task_score": {"kind": official_score_status},
            "official_score": None,
            "first_blocker": "none" if setup_ok else materialization_blocker,
            "repeat_blocked_by": "none" if setup_ok else materialization_blocker,
            "progress": {
                "n_total_trials": 0,
                "n_completed_trials": 0,
                "n_errored_trials": 0 if setup_ok else 1,
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
            "worker_setup_diagnostic_file_count": setup_file_count,
            "worker_setup_diagnostic_schema_ok_count": setup_schema_ok_count,
            "worker_setup_diagnostic_blockers": []
            if setup_ok
            else [materialization_blocker],
            "worker_bridge_outcome": {
                "schema_version": "terminal_bench_worker_materialization_probe_outcome_v0",
                "bridge_surface": interface_surface,
                "runner_return_status": runner_status,
                "official_score_status": official_score_status,
                "trace_publicness": "compact_setup_diagnostic_only_no_raw_trace",
                "worker_bridge_verified": False,
                "counter_trace_present": False,
                "runner_return_completed": True,
                "official_score_completed": False,
                "side_effect_audit_passed": True,
                "raw_paths_recorded": False,
                "raw_trace_recorded": False,
                "credential_values_recorded": False,
                "worker_bridge_materialization_status": materialization_status,
                "worker_bridge_materialization_blocker": materialization_blocker,
                "worker_bridge_failure_attribution": (
                    "none" if setup_ok else materialization_blocker
                ),
                "worker_setup_diagnostic_file_count": setup_file_count,
                "worker_setup_diagnostic_schema_ok_count": setup_schema_ok_count,
                "worker_startup_blocker_count": 0 if setup_ok else 1,
                "next_action": (
                    "run the paired baseline or treatment slice"
                    if setup_ok
                    else "repair worker Codex materialization before repeat"
                ),
            },
            "claim_boundary": claim_boundary,
            "validation": {
                "validation_scope": "worker_codex_materialization_probe",
                "worker_bridge_materialized_when_required": setup_ok,
                "worker_bridge_repeat_ready": setup_ok,
                "runner_return_completed_or_blocker_recorded": True,
                "worker_startup_blocker_recorded": True,
                "no_model_task_solution_invoked": True,
                "no_leaderboard_upload_requested": True,
                "paths_redacted": True,
                "raw_trace_excluded": True,
                "side_effect_audit_passed": True,
            },
            "case_semantics_changed_by_harness": False,
            "goal_harness_inside_case": False,
            "official_score_comparable_to_native_codex": False,
            "official_score_comparable_to_goal_harness_treatment": False,
            "model_plus_harness_pair": False,
            "control_plane_score_applicable": False,
            "startup_surface_calibration": True,
            "codex_goal_mode_baseline": self._codex_goal_mode_baseline(),
            "hardened_install_baseline": self._hardened_codex_baseline(),
            "runtime_preflight_status": runtime_preflight_status,
            "stop_conditions": [
                "do_not_run_task_solver_in_materialization_probe",
                "do_not_upload_or_submit_leaderboard",
                "do_not_claim_case_success_from_worker_materialization",
                "do_not_record_raw_trace_or_paths",
            ],
            "trials": [],
        }
        written = write_worker_bridge_benchmark_run_file(
            self._host_worker_bridge_artifact_path(
                self.goal_harness_benchmark_run_json
            ),
            payload,
        )
        status = (
            "worker_materialization_probe_written"
            if written
            else "worker_materialization_probe_write_failed"
        )
        return payload, written, status

    async def _require_existing_codex_cli(self, environment: BaseEnvironment) -> str:
        """Fail fast with a precise setup blocker when Codex is unavailable."""

        try:
            result = await self.exec_as_agent(
                environment,
                command="set -euo pipefail; command -v codex",
                timeout_sec=self.goal_harness_codex_preflight_timeout_sec,
            )
        except Exception:
            self._best_effort_goal_harness_setup_diagnostic(
                interrupted=True,
                interrupt_reason=CODEX_REQUIRE_EXISTING_BLOCKER_NOT_ON_PATH,
                checkpoint_kind="pre_worker_setup_probe",
                codex_path_observed=False,
            )
            self._best_effort_goal_harness_worker_bridge_checkpoint(
                interrupted=True,
                interrupt_reason=CODEX_REQUIRE_EXISTING_BLOCKER_NOT_ON_PATH,
                checkpoint_kind="pre_worker_startup_blocker",
            )
            raise

        codex_path = ""
        stdout = getattr(result, "stdout", "")
        if isinstance(stdout, str):
            codex_path = stdout.strip().splitlines()[0] if stdout.strip() else ""

        try:
            await self.exec_as_agent(
                environment,
                command=(
                    "set -euo pipefail; "
                    "codex --version >/dev/null 2>&1; "
                    "codex --version"
                ),
                timeout_sec=self.goal_harness_codex_preflight_timeout_sec,
            )
        except Exception:
            self._best_effort_goal_harness_setup_diagnostic(
                interrupted=True,
                interrupt_reason=CODEX_REQUIRE_EXISTING_BLOCKER_VERSION_PROBE_FAILED,
                checkpoint_kind="pre_worker_setup_probe",
                codex_path_observed=bool(codex_path),
            )
            self._best_effort_goal_harness_worker_bridge_checkpoint(
                interrupted=True,
                interrupt_reason=CODEX_REQUIRE_EXISTING_BLOCKER_VERSION_PROBE_FAILED,
                checkpoint_kind="pre_worker_startup_blocker",
            )
            raise

        if codex_path.startswith("/"):
            try:
                await self.exec_as_root(
                    environment,
                    command=(
                        "set -euo pipefail; "
                        f"BIN_PATH={shlex.quote(codex_path)}; "
                        'if [ "$BIN_PATH" != "/usr/local/bin/codex" ]; then '
                        'ln -sf "$BIN_PATH" "/usr/local/bin/codex"; '
                        "fi"
                    ),
                    timeout_sec=self.goal_harness_codex_preflight_timeout_sec,
                )
            except Exception:
                self._best_effort_goal_harness_setup_diagnostic(
                    interrupted=True,
                    interrupt_reason=(
                        CODEX_REQUIRE_EXISTING_BLOCKER_SYMLINK_REPAIR_FAILED
                    ),
                    checkpoint_kind="pre_worker_setup_probe",
                    codex_path_observed=True,
                )
                self._best_effort_goal_harness_worker_bridge_checkpoint(
                    interrupted=True,
                    interrupt_reason=CODEX_REQUIRE_EXISTING_BLOCKER_SYMLINK_REPAIR_FAILED,
                    checkpoint_kind="pre_worker_startup_blocker",
                )
                raise

        self._best_effort_goal_harness_setup_diagnostic(
            interrupted=False,
            interrupt_reason="codex_require_existing_preflight_ok",
            checkpoint_kind="pre_worker_setup_probe",
            codex_path_observed=bool(codex_path),
        )
        return codex_path

    async def _repair_agent_node_runtime_path(
        self, environment: BaseEnvironment
    ) -> None:
        """Expose root-installed node/npm binaries on the agent-visible PATH."""

        await self.exec_as_root(
            environment,
            command=(
                "set -euo pipefail; "
                "mkdir -p /usr/local/bin; "
                "for bin in node npm; do "
                '  BIN_PATH="$(command -v "$bin" 2>/dev/null || true)"; '
                '  if [ -z "$BIN_PATH" ]; then '
                "    for candidate in /usr/local/bin/$bin /usr/bin/$bin /bin/$bin; do "
                '      if [ -x "$candidate" ]; then BIN_PATH="$candidate"; break; fi; '
                "    done; "
                "  fi; "
                '  if [ "$bin" = "node" ] && [ -z "$BIN_PATH" ] && [ -x /usr/bin/nodejs ]; then '
                "    BIN_PATH=/usr/bin/nodejs; "
                "  fi; "
                '  if [ -n "$BIN_PATH" ] && [ "$BIN_PATH" != "/usr/local/bin/$bin" ]; then '
                '    ln -sf "$BIN_PATH" "/usr/local/bin/$bin"; '
                "  fi; "
                "done; "
                "printf 'goal_harness_worker_node_runtime_path_repair_attempted\\n'"
            ),
        )

    async def install(self, environment: BaseEnvironment) -> None:
        """Install Codex with dependencies needed by minimal benchmark images."""

        version = getattr(self, "_version", None)
        version_spec = f"@{version}" if version else "@latest"
        if (
            self.goal_harness_codex_install_strategy
            == TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
        ):
            await self._require_existing_codex_cli(environment)
            return
        setup_stage = "package_manager_preinstall"
        try:
            await self.exec_as_root(
                environment,
                command=(
                    "(if [ -f /etc/alpine-release ] || "
                    "(command -v ldd >/dev/null 2>&1 && ldd --version 2>&1 | grep -qi musl); then"
                    "  apk add --no-cache bash curl nodejs npm ripgrep;"
                    " elif command -v apt-get >/dev/null 2>&1; then"
                    "  apt-get update && apt-get install -y "
                    "bash ca-certificates curl git nodejs npm xz-utils tar gzip ripgrep;"
                    " elif command -v dnf >/dev/null 2>&1; then"
                    "  dnf install -y bash ca-certificates curl git nodejs npm xz tar gzip ripgrep;"
                    " elif command -v yum >/dev/null 2>&1; then"
                    "  yum install -y bash ca-certificates curl git nodejs npm xz tar gzip ripgrep;"
                    " else"
                    '  echo "Warning: No known package manager found, assuming Codex install prerequisites are available" >&2;'
                    " fi) || "
                    'echo "Warning: Package-manager prerequisite install failed; continuing with existing worker tools" >&2'
                ),
                env={"DEBIAN_FRONTEND": "noninteractive"},
            )
            setup_stage = "agent_codex_install"
            agent_env_prefix = (
                "set -euo pipefail; "
                'export NPM_CONFIG_PREFIX="${HOME}/.goal-harness-codex"; '
                'export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmjs.org}"; '
                'export PATH="${NPM_CONFIG_PREFIX}/bin:${PATH}"; '
                'if [ -s "${HOME}/.nvm/nvm.sh" ]; then '
                '  export NVM_DIR="${HOME}/.nvm"; . "$NVM_DIR/nvm.sh"; '
                "fi; "
            )
            codex_probe = await self.exec_as_agent(
                environment,
                command=(
                    agent_env_prefix
                    + "if command -v codex >/dev/null 2>&1 && "
                    "codex --version >/dev/null 2>&1; then "
                    "  printf 'goal_harness_codex_usable\\n'; "
                    "else "
                    "  printf 'goal_harness_codex_missing\\n'; "
                    "fi"
                ),
            )
            codex_probe_stdout = str(getattr(codex_probe, "stdout", "") or "")
            if "goal_harness_codex_usable" not in codex_probe_stdout:
                runtime_probe = await self.exec_as_agent(
                    environment,
                    command=(
                        agent_env_prefix
                        + "if command -v node >/dev/null 2>&1 && "
                        "command -v npm >/dev/null 2>&1; then "
                        "  printf 'goal_harness_node_npm_ready\\n'; "
                        "else "
                        "  printf 'goal_harness_node_npm_missing\\n'; "
                        "fi"
                    ),
                )
                runtime_probe_stdout = str(
                    getattr(runtime_probe, "stdout", "") or ""
                )
                if "goal_harness_node_npm_ready" not in runtime_probe_stdout:
                    setup_stage = "agent_codex_install_node_path_repair"
                    await self._repair_agent_node_runtime_path(environment)
                    runtime_probe = await self.exec_as_agent(
                        environment,
                        command=(
                            agent_env_prefix
                            + "hash -r; "
                            + "if command -v node >/dev/null 2>&1 && "
                            "command -v npm >/dev/null 2>&1; then "
                            "  printf 'goal_harness_node_npm_ready\\n'; "
                            "else "
                            "  printf 'goal_harness_node_npm_missing\\n'; "
                            "fi"
                        ),
                    )
                    runtime_probe_stdout = str(
                        getattr(runtime_probe, "stdout", "") or ""
                    )
                if "goal_harness_node_npm_ready" in runtime_probe_stdout:
                    setup_stage = "agent_codex_install_npm_existing"
                    await self.exec_as_agent(
                        environment,
                        command=(
                            agent_env_prefix
                            + 'mkdir -p "$NPM_CONFIG_PREFIX" && '
                            f'npm install -g --registry "$NPM_CONFIG_REGISTRY" @openai/codex{version_spec}'
                        ),
                    )
                else:
                    setup_stage = "agent_codex_install_nvm_bootstrap"
                    await self.exec_as_agent(
                        environment,
                        command=(
                            "set -euo pipefail; "
                            "command -v curl >/dev/null 2>&1 || "
                            "{ echo 'Error: curl unavailable for NVM bootstrap' >&2; exit 1; }; "
                            "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash"
                        ),
                    )
                    nvm_prefix = (
                        agent_env_prefix
                        + 'export NVM_DIR="$HOME/.nvm"; '
                        + '[ -s "$NVM_DIR/nvm.sh" ] || '
                        + '{ echo "Error: NVM failed to install" >&2; exit 1; }; '
                        + '. "$NVM_DIR/nvm.sh"; '
                        + "command -v nvm >/dev/null 2>&1 || "
                        + "{ echo 'Error: NVM failed to load' >&2; exit 1; }; "
                    )
                    setup_stage = "agent_codex_install_nvm_node"
                    await self.exec_as_agent(
                        environment,
                        command=nvm_prefix + "nvm install 22 && nvm alias default 22 && npm -v",
                    )
                    setup_stage = "agent_codex_install_npm_after_nvm"
                    await self.exec_as_agent(
                        environment,
                        command=(
                            nvm_prefix
                            + 'export NPM_CONFIG_PREFIX="${HOME}/.goal-harness-codex"; '
                            + 'export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmjs.org}"; '
                            + 'export PATH="${NPM_CONFIG_PREFIX}/bin:${PATH}"; '
                            + 'mkdir -p "$NPM_CONFIG_PREFIX" && '
                            + f'npm install -g --registry "$NPM_CONFIG_REGISTRY" @openai/codex{version_spec}'
                        ),
                    )
            setup_stage = "agent_codex_install_codex_version_probe"
            await self.exec_as_agent(
                environment,
                command=(
                    agent_env_prefix
                    + "hash -r; codex --version >/dev/null 2>&1; codex --version"
                ),
            )
            setup_stage = "root_codex_link"
            await self.exec_as_root(
                environment,
                command=(
                    "for bin in node npm codex; do"
                    '  BIN_PATH="$(which "$bin" 2>/dev/null || true)";'
                    '  if [ -z "$BIN_PATH" ]; then'
                    "    for dir in "
                    "/home/*/.goal-harness-codex/bin "
                    "/root/.goal-harness-codex/bin "
                    "/home/*/.nvm/versions/node/*/bin "
                    "/root/.nvm/versions/node/*/bin; do"
                    '      if [ -x "$dir/$bin" ]; then BIN_PATH="$dir/$bin"; break; fi;'
                    "    done;"
                    "  fi;"
                    '  if [ -n "$BIN_PATH" ] && [ "$BIN_PATH" != "/usr/local/bin/$bin" ]; then'
                    '    ln -sf "$BIN_PATH" "/usr/local/bin/$bin";'
                    "  fi;"
                    " done"
                ),
            )
            self._best_effort_goal_harness_setup_diagnostic(
                interrupted=False,
                interrupt_reason="codex_runtime_install_or_preflight_ok",
                checkpoint_kind="pre_worker_setup_install",
                codex_path_observed=None,
            )
        except Exception:
            stage_marker = self._read_goal_harness_setup_stage_marker()
            blocker_stage = (
                stage_marker
                if setup_stage == "agent_codex_install" and stage_marker
                else setup_stage
            )
            blocker = f"worker_install_failed_{blocker_stage}"
            self._best_effort_goal_harness_setup_diagnostic(
                interrupted=True,
                interrupt_reason=blocker,
                checkpoint_kind="pre_worker_setup_install",
                codex_path_observed=None,
            )
            self._best_effort_goal_harness_worker_bridge_checkpoint(
                interrupted=True,
                interrupt_reason=blocker,
                checkpoint_kind="pre_worker_startup_blocker",
            )
            raise

    def _active_goal_harness_cli_bridge(self) -> bool:
        return (
            self.goal_harness_mode == CODEX_GOAL_HARNESS_MODE
            and self.goal_harness_cli_bridge_enabled
            and self.goal_harness_access_packet_mode
            != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        )

    def _hardened_codex_baseline(self) -> bool:
        return (
            self.goal_harness_mode in TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES
            and self.goal_harness_access_packet_mode
            == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        )

    def _codex_goal_mode_baseline(self) -> bool:
        return (
            self.goal_harness_mode == CODEX_GOAL_MODE_BASELINE_MODE
            and self.goal_harness_access_packet_mode
            == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        )

    def _benchmark_case_active_state_required(self) -> bool:
        return not (self._hardened_codex_baseline() or self._codex_goal_mode_baseline())

    def _host_worker_bridge_artifact_path(self, path: str | Path | None) -> Path | None:
        """Map default in-container worker artifact paths to Harbor's host log dir."""

        if not path:
            return None
        text = str(path)
        prefix = DEFAULT_WORKER_BRIDGE_TRACE_DIR.rstrip("/") + "/"
        if text.startswith(prefix):
            try:
                return Path(self.logs_dir) / text[len(prefix) :]
            except Exception:
                return Path(text)
        return Path(text)

    def _load_goal_harness_trace_rows(self) -> list[dict[str, Any]]:
        host_trace_path = self._host_worker_bridge_artifact_path(
            self.goal_harness_counter_trace_json
        )
        return (
            load_goal_harness_counter_trace_file(host_trace_path)
            or self.goal_harness_counter_trace
        )

    def _build_goal_harness_interaction_counters(
        self,
        trace_rows: list[dict[str, Any]],
        *,
        active_cli_bridge: bool,
        no_trace_case_result_writeback: str,
        no_trace_counter_trust_level: str,
    ) -> dict[str, Any]:
        no_trace_prompt_only = (
            self.goal_harness_mode == CODEX_GOAL_HARNESS_MODE
            and not active_cli_bridge
            and not self.goal_harness_counter_trace
        )
        hardened_baseline = self._hardened_codex_baseline()
        goal_mode_baseline = self._codex_goal_mode_baseline()
        counters = extract_goal_harness_interaction_counters_from_trace(
            trace_rows,
            prompt_policy_injected=not (hardened_baseline or goal_mode_baseline),
            harness_skill_or_packet_injected=bool(
                self._goal_harness_context_metadata.get(
                    "goal_harness_access_packet_injected"
                )
            ),
            case_result_writeback=(
                no_trace_case_result_writeback
                if active_cli_bridge and not trace_rows
                else "codex_goal_mode_baseline_runner_only"
                if goal_mode_baseline
                else "hardened_codex_baseline_runner_only"
                if hardened_baseline
                else "not_observed_prompt_only_no_cli_bridge"
                if no_trace_prompt_only
                else "not_observed_custom_agent_metadata"
            ),
            no_trace_counter_trust_level=(
                no_trace_counter_trust_level
                if active_cli_bridge and not trace_rows
                else "codex_goal_mode_baseline_no_goal_harness_state"
                if goal_mode_baseline
                else "hardened_codex_baseline_no_goal_harness_state"
                if hardened_baseline
                else "runtime_metadata_prompt_only_no_cli_bridge"
                if no_trace_prompt_only
                else "runtime_metadata_no_trace_observed"
            ),
        )
        if self._benchmark_case_active_state_required():
            initialized = bool(
                self._goal_harness_context_metadata.get(
                    "case_goal_state_initialized_before_agent"
                )
            )
            counters.update(
                {
                    "case_goal_state_packet_present": True,
                    "case_goal_state_init_required": True,
                    "case_goal_state_initialized_before_agent": initialized,
                    "case_goal_state_init_status": str(
                        self._goal_harness_context_metadata.get(
                            "case_goal_state_init_status"
                        )
                        or "not_started"
                    ),
                    "case_goal_state_schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
                    "case_goal_state_path": TERMINAL_BENCH_CASE_STATE_PATH,
                    "goal_harness_case_state_reads": 0,
                    "goal_harness_case_state_writes": 1 if initialized else 0,
                    "goal_harness_case_state_path_count": 1,
                }
            )
        return counters

    def _write_goal_harness_worker_benchmark_run_checkpoint(
        self,
        *,
        interrupted: bool,
        interrupt_reason: str,
        checkpoint_kind: str,
    ) -> tuple[dict[str, Any] | None, bool, str]:
        active_cli_bridge = self._active_goal_harness_cli_bridge()
        benchmark_run_json_declared = bool(self.goal_harness_benchmark_run_json)
        if not active_cli_bridge:
            return None, False, "not_enabled"
        if not benchmark_run_json_declared:
            return None, False, "worker_bridge_benchmark_run_path_missing"

        trace_rows = self._load_goal_harness_trace_rows()
        interaction_counters = self._build_goal_harness_interaction_counters(
            trace_rows,
            active_cli_bridge=active_cli_bridge,
            no_trace_case_result_writeback=(
                "worker_bridge_run_finally_checkpoint_no_trace"
                if checkpoint_kind == "run_finally"
                else "not_observed_active_cli_bridge_no_trace"
            ),
            no_trace_counter_trust_level=(
                "run_finally_active_cli_bridge_no_trace_observed"
                if checkpoint_kind == "run_finally"
                else "runtime_metadata_active_cli_bridge_no_trace_observed"
            ),
        )
        payload = build_worker_bridge_benchmark_run_from_counters(
            interaction_counters,
            counter_trace_present=bool(trace_rows),
            source_runner="terminal_bench_worker_bridge",
            benchmark_id="terminal-bench-worker-bridge@v0",
            job_name="terminal_bench_goal_harness_active_worker",
            task_id="terminal-bench-worker-bridge",
            trial_name=f"terminal-bench-worker-bridge-{checkpoint_kind}",
            interrupted=interrupted,
            interrupt_reason=interrupt_reason,
        )
        payload["episode_policy"] = build_terminal_bench_single_agent_episode_policy(
            active_cli_bridge=True,
            runner_side_guaranteed_writeback=True,
        )
        payload["worker_bridge_checkpoint"] = {
            "schema_version": "goal_harness_worker_bridge_checkpoint_v0",
            "checkpoint_kind": checkpoint_kind,
            "interrupted": bool(interrupted),
            "trace_row_count": len(trace_rows),
            "raw_trace_recorded": False,
            "raw_paths_recorded": False,
        }
        if checkpoint_kind == "pre_worker_startup_blocker":
            blocker = interrupt_reason.strip() or "pre_worker_startup_failure"
            payload["first_blocker"] = blocker
            payload["repeat_blocked_by"] = blocker
            payload["pre_worker_startup_blocker"] = blocker
            payload["worker_bridge_checkpoint"]["pre_worker_startup_blocker"] = blocker
            payload["worker_bridge_outcome"]["pre_worker_startup_blocker"] = blocker
            payload["worker_bridge_outcome"][
                "next_action"
            ] = "repair worker runtime preflight/startup before repeat"
            payload["validation"]["worker_startup_blocker_recorded"] = True
            payload["validation"][
                "runner_return_completed_or_blocker_recorded"
            ] = True
        written = write_worker_bridge_benchmark_run_file(
            self._host_worker_bridge_artifact_path(
                self.goal_harness_benchmark_run_json
            ),
            payload,
        )
        status = (
            "worker_bridge_benchmark_run_written"
            if written
            else "worker_bridge_benchmark_run_write_failed"
        )
        return payload, written, status

    def _best_effort_goal_harness_worker_bridge_checkpoint(
        self,
        *,
        interrupted: bool,
        interrupt_reason: str,
        checkpoint_kind: str,
    ) -> tuple[dict[str, Any] | None, bool, str]:
        try:
            return self._write_goal_harness_worker_benchmark_run_checkpoint(
                interrupted=interrupted,
                interrupt_reason=interrupt_reason,
                checkpoint_kind=checkpoint_kind,
            )
        except Exception:
            logger = getattr(self, "logger", None)
            if logger is not None:
                logger.exception("Goal Harness worker checkpoint write failed")
            return None, False, "worker_bridge_benchmark_run_checkpoint_failed"

    async def _ensure_goal_harness_worker_bridge_runtime(
        self,
        environment: BaseEnvironment,
    ) -> str:
        if not (
            self.goal_harness_mode == CODEX_GOAL_HARNESS_MODE
            and self.goal_harness_cli_bridge_enabled
            and self.goal_harness_access_packet_mode
            != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        ):
            return "not_applicable"
        if not self.goal_harness_runtime_preflight_command:
            return "not_configured"

        exec_as_root = getattr(self, "exec_as_root", None)
        if exec_as_root is None:
            return "not_supported_by_agent_base"

        await exec_as_root(
            environment,
            command=self.goal_harness_runtime_preflight_command,
            timeout_sec=300,
        )
        return "passed"

    async def _initialize_benchmark_case_active_state(
        self,
        environment: BaseEnvironment,
        instruction: str,
    ) -> dict[str, Any]:
        """Initialize the canonical benchmark case active-state before Codex runs."""

        required = self._benchmark_case_active_state_required()
        if not required:
            return {
                "case_goal_state_init_required": False,
                "case_goal_state_initialized_before_agent": False,
                "case_goal_state_init_status": "not_applicable",
            }

        exec_as_root = getattr(self, "exec_as_root", None)
        if exec_as_root is None:
            return {
                "case_goal_state_init_required": True,
                "case_goal_state_initialized_before_agent": False,
                "case_goal_state_init_status": "not_supported_by_agent_base",
                "case_goal_state_path": TERMINAL_BENCH_CASE_STATE_PATH,
                "case_goal_state_schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
            }

        content = benchmark_case_active_state_seed_text(
            benchmark_name="Terminal-Bench",
            goal_id=TERMINAL_BENCH_CASE_GOAL_ID,
            task_id=f"terminal-bench-task-{_task_hash(instruction)}",
            route=self.goal_harness_mode,
            max_rounds=1,
            case_state_path=TERMINAL_BENCH_CASE_STATE_PATH,
        )
        command = benchmark_case_active_state_write_command(
            case_state_path=TERMINAL_BENCH_CASE_STATE_PATH,
            content=content,
        )
        result = await exec_as_root(environment, command=command, timeout_sec=30)
        return_code = int(getattr(result, "return_code", 1))
        if return_code != 0:
            return {
                "case_goal_state_init_required": True,
                "case_goal_state_initialized_before_agent": False,
                "case_goal_state_init_status": "failed",
                "case_goal_state_init_rc": return_code,
                "case_goal_state_path": TERMINAL_BENCH_CASE_STATE_PATH,
                "case_goal_state_schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
            }

        return {
            "case_goal_state_init_required": True,
            "case_goal_state_initialized_before_agent": True,
            "case_goal_state_init_status": "passed",
            "case_goal_state_init_rc": return_code,
            "case_goal_state_path": TERMINAL_BENCH_CASE_STATE_PATH,
            "case_goal_state_schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
        }

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        hardened_baseline = self._hardened_codex_baseline()
        goal_mode_baseline = self._codex_goal_mode_baseline()
        baseline_without_goal_harness = hardened_baseline or goal_mode_baseline
        case_goal_state_required = not baseline_without_goal_harness
        managed_instruction = build_managed_terminal_bench_instruction(
            instruction,
            policy_version=self.goal_harness_policy_version,
            behavior_spec_id=self.goal_harness_behavior_spec_id,
            ablation_mode=self.goal_harness_ablation_mode,
            goal_harness_mode=self.goal_harness_mode,
            goal_id=self.goal_harness_goal_id,
            goal_harness_access_packet_mode=self.goal_harness_access_packet_mode,
            goal_harness_cli_bridge_enabled=self.goal_harness_cli_bridge_enabled,
            goal_harness_command_prefix=self.goal_harness_command_prefix,
            goal_harness_registry_arg=self.goal_harness_registry_arg,
            goal_harness_runtime_root_arg=self.goal_harness_runtime_root_arg,
            goal_harness_scan_path=self.goal_harness_scan_path,
            goal_harness_benchmark_run_json=self.goal_harness_benchmark_run_json,
            goal_harness_counter_trace_json=self.goal_harness_counter_trace_json,
            goal_harness_classification=self.goal_harness_classification,
            goal_harness_append_execute_enabled=self.goal_harness_append_execute_enabled,
            goal_harness_active_user_intervention_enabled=(
                self.goal_harness_active_user_intervention_enabled
            ),
            goal_harness_active_user_feed_jsonl=self.goal_harness_active_user_feed_jsonl,
            goal_harness_active_user_observation_json=(
                self.goal_harness_active_user_observation_json
            ),
            goal_harness_active_user_observe_command=(
                self.goal_harness_active_user_observe_command
            ),
            goal_harness_active_user_channel_surface=(
                self.goal_harness_active_user_channel_surface
            ),
            goal_harness_case_state_path=TERMINAL_BENCH_CASE_STATE_PATH,
            goal_harness_case_state_schema_version=(
                BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
            ),
            goal_harness_case_state_required=case_goal_state_required,
        )
        access_packet_injected = (
            self.goal_harness_mode == CODEX_GOAL_HARNESS_MODE
            and self.goal_harness_access_packet_mode
            != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        )
        interface_surface = (
            TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE
            if hardened_baseline
            else TERMINAL_BENCH_CODEX_GOAL_MODE_BASELINE_SURFACE
            if goal_mode_baseline
            else
            TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE
            if access_packet_injected and self.goal_harness_cli_bridge_enabled
            else TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE
            if access_packet_injected
            else "managed_policy_prompt_only"
        )
        self._goal_harness_context_metadata = {
            "mode": self.goal_harness_mode,
            "policy_version": self.goal_harness_policy_version,
            "behavior_spec_id": self.goal_harness_behavior_spec_id,
            "ablation_mode": self.goal_harness_ablation_mode,
            "goal_harness_access_packet_mode": self.goal_harness_access_packet_mode,
            "trace_publicness": self.goal_harness_trace_publicness,
            "goal_harness_codex_preflight_timeout_sec": (
                self.goal_harness_codex_preflight_timeout_sec
            ),
            "goal_harness_access_packet_injected": access_packet_injected,
            "goal_harness_interface_surface": interface_surface,
            "goal_harness_cli_bridge_available": (
                True
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
                if access_packet_injected
                else False
            ),
            "goal_harness_cli_bridge_contract": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION
                if access_packet_injected
                else None
            ),
            "goal_harness_active_user_intervention_enabled": (
                self.goal_harness_active_user_intervention_enabled
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else False
            ),
            "goal_harness_active_user_channel_surface": (
                self.goal_harness_active_user_channel_surface
                if self.goal_harness_active_user_intervention_enabled
                else None
            ),
            "goal_harness_active_user_feed_declared": (
                bool(self.goal_harness_active_user_feed_jsonl)
                if self.goal_harness_active_user_intervention_enabled
                else False
            ),
            "goal_harness_active_user_observe_command_declared": (
                bool(self.goal_harness_active_user_observe_command)
                if self.goal_harness_active_user_intervention_enabled
                else False
            ),
            "goal_harness_prompt_only_until_cli_bridge": (
                access_packet_injected
                and not self.goal_harness_cli_bridge_enabled
                and not TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE
            ),
            "available_goal_harness_interface_commands": (
                list(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS)
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else []
            ),
            "goal_harness_cli_bridge_call_policy_version": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_VERSION
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else None
            ),
            "goal_harness_cli_bridge_call_policy_mode": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_MODE
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else None
            ),
            "goal_harness_cli_bridge_default_required_calls": (
                list(TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS)
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else []
            ),
            "goal_harness_cli_bridge_optional_context_calls": (
                list(TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS)
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else []
            ),
            "goal_harness_cli_bridge_required_call_minimum": (
                TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else 0
            ),
            "goal_harness_cli_bridge_command_prefix_present": (
                bool(self.goal_harness_command_prefix)
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else False
            ),
            "goal_harness_cli_bridge_append_execute_enabled": (
                self.goal_harness_append_execute_enabled
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else False
            ),
            "goal_harness_counter_trace_jsonl_declared": (
                bool(self.goal_harness_counter_trace_json)
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else False
            ),
            "goal_harness_benchmark_run_schema_version": (
                self.goal_harness_benchmark_run_schema_version
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else None
            ),
            "goal_harness_benchmark_run_writeback_contract": (
                self.goal_harness_benchmark_run_writeback_contract
                if access_packet_injected and self.goal_harness_cli_bridge_enabled
                else None
            ),
            "declared_goal_harness_interface_commands": (
                list(TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS)
                if access_packet_injected
                else []
            ),
            "goal_harness_access_packet_schema_version": (
                TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION
                if access_packet_injected
                else None
            ),
            "goal_harness_episode_policy": build_terminal_bench_single_agent_episode_policy(
                active_cli_bridge=bool(
                    access_packet_injected and self.goal_harness_cli_bridge_enabled
                ),
                runner_side_guaranteed_writeback=True,
            ),
            "case_semantics_changed_by_harness": not baseline_without_goal_harness,
            "goal_harness_inside_case": not baseline_without_goal_harness,
            "official_score_comparable_to_native_codex": False,
            "official_score_comparable_to_goal_harness_treatment": baseline_without_goal_harness,
            "model_plus_harness_pair": not baseline_without_goal_harness,
            "control_plane_score_applicable": not baseline_without_goal_harness,
            "startup_surface_calibration": False,
            "hardened_install_surface": hardened_baseline,
            "hardened_install_baseline": hardened_baseline,
            "codex_goal_mode_baseline": goal_mode_baseline,
            "codex_goal_mode_invocation_surface": (
                "slash_command" if goal_mode_baseline else None
            ),
            "task_prompt_changed_by_goal_harness_policy": not baseline_without_goal_harness,
            "raw_task_instruction_recorded": False,
            "raw_managed_prompt_recorded": False,
            "raw_interaction_trace_recorded": False,
            "task_instruction_sha256_16": _task_hash(instruction),
            "managed_prompt_chars": len(managed_instruction),
            "context_metadata_deferred_until_post_run": True,
            "case_goal_state_init_required": case_goal_state_required,
            "case_goal_state_initialized_before_agent": False,
            "case_goal_state_init_status": (
                "not_started" if case_goal_state_required else "not_applicable"
            ),
            "case_goal_state_path": (
                TERMINAL_BENCH_CASE_STATE_PATH if case_goal_state_required else None
            ),
            "case_goal_state_schema_version": (
                BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
                if case_goal_state_required
                else None
            ),
        }
        self._goal_harness_context_metadata[
            "goal_harness_runtime_preflight_status"
        ] = "not_started"
        if self.goal_harness_worker_materialization_probe_only:
            try:
                runtime_preflight_status = (
                    await self._ensure_goal_harness_worker_bridge_runtime(environment)
                )
            except Exception:
                self._goal_harness_context_metadata.update(
                    {
                        "goal_harness_runtime_preflight_status": "failed",
                        "goal_harness_pre_worker_startup_blocker": (
                            "runtime_preflight_failed"
                        ),
                    }
                )
                _, probe_written, probe_status = (
                    self._write_goal_harness_worker_materialization_probe_result(
                        interface_surface=interface_surface,
                        runtime_preflight_status="failed",
                        interrupted=True,
                        interrupt_reason="runtime_preflight_failed",
                    )
                )
                self._goal_harness_context_metadata.update(
                    {
                        "worker_materialization_probe_only": True,
                        "worker_materialization_probe_written": probe_written,
                        "worker_materialization_probe_writeback_status": probe_status,
                    }
                )
                raise
            self._goal_harness_context_metadata[
                "goal_harness_runtime_preflight_status"
            ] = runtime_preflight_status
            _, probe_written, probe_status = (
                self._write_goal_harness_worker_materialization_probe_result(
                    interface_surface=interface_surface,
                    runtime_preflight_status=runtime_preflight_status,
                )
            )
            case_state_probe_status: dict[str, Any] = {}
            if case_goal_state_required:
                case_state_probe_status = {
                    "case_goal_state_initialized_before_agent": False,
                    "case_goal_state_init_status": "not_applicable_probe_only",
                }
            self._goal_harness_context_metadata.update(
                {
                    **case_state_probe_status,
                    "worker_materialization_probe_only": True,
                    "worker_materialization_probe_written": probe_written,
                    "worker_materialization_probe_writeback_status": probe_status,
                    "run_completed_or_interrupted": True,
                    "agent_run_started": False,
                    "agent_run_completed": False,
                    "agent_run_interrupted": False,
                    "credential_values_recorded": False,
                    "auth_files_recorded": False,
                    "leaderboard_evidence": False,
                    "submit_eligible": False,
                }
            )
            return
        worker_run_started = False
        run_completed = False
        pre_worker_startup_blocker = "runtime_preflight_failed"
        try:
            try:
                runtime_preflight_status = (
                    await self._ensure_goal_harness_worker_bridge_runtime(environment)
                )
            except Exception:
                self._goal_harness_context_metadata.update(
                    {
                        "goal_harness_runtime_preflight_status": "failed",
                        "goal_harness_pre_worker_startup_blocker": (
                            "runtime_preflight_failed"
                        ),
                    }
                )
                raise
            self._goal_harness_context_metadata[
                "goal_harness_runtime_preflight_status"
            ] = runtime_preflight_status
            case_state_init = await self._initialize_benchmark_case_active_state(
                environment,
                instruction,
            )
            self._goal_harness_context_metadata.update(case_state_init)
            if (
                case_goal_state_required
                and case_state_init.get("case_goal_state_init_status") != "passed"
            ):
                pre_worker_startup_blocker = "case_goal_state_init_failed"
                self._goal_harness_context_metadata[
                    "goal_harness_pre_worker_startup_blocker"
                ] = pre_worker_startup_blocker
                raise RuntimeError("Goal Harness case active-state init failed")
            worker_run_started = True
            await super().run(managed_instruction, environment, context)
            run_completed = True
        finally:
            checkpoint_kind = (
                "run_finally" if worker_run_started else "pre_worker_startup_blocker"
            )
            interrupt_reason = (
                ""
                if run_completed
                else "agent_run_exception_or_nonzero_exit"
                if worker_run_started
                else pre_worker_startup_blocker
            )
            self._goal_harness_context_metadata.update(
                {
                    "run_completed_or_interrupted": True,
                    "agent_run_started": worker_run_started,
                    "agent_run_completed": run_completed,
                    "agent_run_interrupted": not run_completed,
                    "goal_harness_run_finally_checkpoint_kind": checkpoint_kind,
                    "goal_harness_run_finally_interrupt_reason": interrupt_reason,
                    "credential_values_recorded": False,
                    "auth_files_recorded": False,
                    "leaderboard_evidence": False,
                    "submit_eligible": False,
                }
            )
            _, benchmark_run_written, benchmark_run_status = (
                self._best_effort_goal_harness_worker_bridge_checkpoint(
                    interrupted=not run_completed,
                    interrupt_reason=interrupt_reason,
                    checkpoint_kind=checkpoint_kind,
                )
            )
            self._goal_harness_context_metadata.update(
                {
                    "goal_harness_run_finally_benchmark_run_json_written": (
                        benchmark_run_written
                    ),
                    "goal_harness_run_finally_benchmark_run_writeback_status": (
                        benchmark_run_status
                    ),
                }
            )

    def _populate_usage_from_session_token_count(self, context: AgentContext) -> bool:
        try:
            session_dir = self._get_session_dir()
        except Exception:
            self.logger.exception("Failed to locate Codex session directory")
            return False
        if not session_dir:
            return False

        usage = extract_codex_session_usage(session_dir)
        if not usage:
            return False

        context.n_input_tokens = usage.get("input_tokens")
        context.n_cache_tokens = usage.get("cache_tokens")
        context.n_output_tokens = usage.get("output_tokens")
        if context.cost_usd is None:
            context.cost_usd = self._compute_cost_from_pricing(
                prompt_tokens=context.n_input_tokens,
                completion_tokens=context.n_output_tokens,
                cached_tokens=context.n_cache_tokens,
            )
        return True

    def populate_context_post_run(self, context: AgentContext) -> None:
        """Let Harbor ingest Codex usage before adding managed metadata."""

        super().populate_context_post_run(context)
        fallback_applied = False
        if not _context_has_usage(context):
            fallback_applied = self._populate_usage_from_session_token_count(context)

        usage_available = _context_has_usage(context)
        active_cli_bridge = self._active_goal_harness_cli_bridge()
        trace_rows = self._load_goal_harness_trace_rows()
        interaction_counters = self._build_goal_harness_interaction_counters(
            trace_rows,
            active_cli_bridge=active_cli_bridge,
            no_trace_case_result_writeback="not_observed_active_cli_bridge_no_trace",
            no_trace_counter_trust_level=(
                "runtime_metadata_active_cli_bridge_no_trace_observed"
            ),
        )
        worker_cli_call_total = worker_bridge_cli_call_total_from_interaction_counters(
            interaction_counters
        )
        benchmark_run_json_declared = bool(self.goal_harness_benchmark_run_json)
        benchmark_run_payload, benchmark_run_written, benchmark_run_writeback_status = (
            self._best_effort_goal_harness_worker_bridge_checkpoint(
                interrupted=False,
                interrupt_reason="",
                checkpoint_kind="post_run",
            )
        )

        payload = {
            **self._goal_harness_context_metadata,
            "goal_harness_interaction_counters": interaction_counters,
            "goal_harness_counter_trace_schema_version": GOAL_HARNESS_COUNTER_TRACE_SCHEMA_VERSION,
            "goal_harness_counter_trace_file_loaded": bool(
                trace_rows and not self.goal_harness_counter_trace
            ),
            "goal_harness_counter_trace_row_count": len(trace_rows),
            "goal_harness_benchmark_run_json_declared": (
                benchmark_run_json_declared if active_cli_bridge else False
            ),
            "goal_harness_benchmark_run_schema_version": (
                self.goal_harness_benchmark_run_schema_version
                if active_cli_bridge
                else None
            ),
            "goal_harness_benchmark_run_writeback_contract": (
                self.goal_harness_benchmark_run_writeback_contract
                if active_cli_bridge
                else None
            ),
            "goal_harness_benchmark_run_json_written": benchmark_run_written,
            "goal_harness_benchmark_run_writeback_status": benchmark_run_writeback_status,
            "goal_harness_worker_cli_call_total": worker_cli_call_total,
            "goal_harness_worker_benchmark_run_schema_version": (
                benchmark_run_payload.get("schema_version")
                if benchmark_run_written and benchmark_run_payload
                else None
            ),
            "context_post_run_ingested": True,
            "usage_source": CODEX_SESSION_TOKEN_COUNT_USAGE_SOURCE
            if usage_available
            else "unavailable",
            "token_cost_fallback_applied": fallback_applied,
            "trajectory_present_after_post_run": (
                self.logs_dir / "trajectory.json"
            ).exists(),
            "raw_codex_output_recorded": False,
            "raw_sessions_recorded": False,
        }
        _merge_metadata(context, payload)
