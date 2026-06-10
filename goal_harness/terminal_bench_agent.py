from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from goal_harness.benchmark import (
    TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_AVAILABLE,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_FULL,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODES,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS,
    TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_VERSION,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_MODE,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CALL_POLICY_VERSION,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_CONTRACT_VERSION,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_DEFAULT_REQUIRED_CALLS,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_OPTIONAL_CONTEXT_CALLS,
    TERMINAL_BENCH_GOAL_HARNESS_CLI_BRIDGE_REQUIRED_CALL_MINIMUM,
    TERMINAL_BENCH_GOAL_HARNESS_INTERFACE_SURFACE,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES,
    TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE,
    build_terminal_bench_goal_harness_access_packet,
    build_terminal_bench_goal_harness_interaction_counters,
    build_terminal_bench_single_agent_episode_policy,
)
from goal_harness.worker_bridge import (
    ACTIVE_USER_INTERVENTION_CHANNEL_SURFACE,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_FEED_JSONL,
    DEFAULT_WORKER_BRIDGE_ACTIVE_USER_OBSERVATION_JSON,
    DEFAULT_WORKER_BRIDGE_BENCHMARK_RUN_JSON,
    DEFAULT_WORKER_BRIDGE_COUNTER_TRACE_JSON,
    GOAL_HARNESS_PROJECT_ROOT_PLACEHOLDER,
    GOAL_HARNESS_RUNTIME_ROOT_PLACEHOLDER,
    build_worker_bridge_benchmark_run_from_counters,
    build_worker_bridge_command_prefix,
    build_worker_bridge_python_runtime_preflight_command,
    worker_bridge_cli_call_total_from_interaction_counters,
    write_worker_bridge_benchmark_run_file,
)

CODEX_GOAL_HARNESS_MODE = "codex_goal_harness"
GOAL_HARNESS_MANAGED_CODEX_MODE = "goal_harness_managed_codex"
GOAL_HARNESS_MANAGED_CODEX_POLICY_VERSION = "goal_harness_terminal_bench_policy_v0"
GOAL_HARNESS_MANAGED_CODEX_BEHAVIOR_SPEC_ID = (
    "terminal_bench_goal_harness_managed_codex_v0"
)
CODEX_SESSION_TOKEN_COUNT_USAGE_SOURCE = "codex_cli_session_token_count_event"
GOAL_HARNESS_COUNTER_TRACE_SCHEMA_VERSION = (
    "terminal_bench_goal_harness_counter_trace_v0"
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
) -> str:
    """Wrap a benchmark task with the minimal Goal Harness managed policy."""

    if (
        goal_harness_mode in TERMINAL_BENCH_HARDENED_CODEX_BASELINE_MODES
        and goal_harness_access_packet_mode
        == TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
    ):
        return task_instruction

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
        command: 0 for command in TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_COMMANDS
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

    async def install(self, environment: BaseEnvironment) -> None:
        """Install Codex with dependencies needed by minimal benchmark images."""

        version = getattr(self, "_version", None)
        version_spec = f"@{version}" if version else "@latest"
        await self.exec_as_root(
            environment,
            command=(
                "if [ -f /etc/alpine-release ] || "
                "(command -v ldd >/dev/null 2>&1 && ldd --version 2>&1 | grep -qi musl); then"
                "  apk add --no-cache bash curl nodejs npm ripgrep;"
                " elif command -v apt-get >/dev/null 2>&1; then"
                "  apt-get update && apt-get install -y "
                "bash ca-certificates curl git xz-utils tar gzip ripgrep;"
                " elif command -v dnf >/dev/null 2>&1; then"
                "  dnf install -y bash ca-certificates curl git xz tar gzip ripgrep;"
                " elif command -v yum >/dev/null 2>&1; then"
                "  yum install -y bash ca-certificates curl git xz tar gzip ripgrep;"
                " else"
                '  echo "Warning: No known package manager found, assuming Codex install prerequisites are available" >&2;'
                " fi"
            ),
            env={"DEBIAN_FRONTEND": "noninteractive"},
        )
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "codex_is_usable() {"
                "  command -v codex >/dev/null 2>&1 && codex --version >/dev/null 2>&1;"
                "}; "
                "if codex_is_usable; then"
                "  codex --version;"
                " else"
                '  echo "Codex CLI missing or version check failed; installing Codex CLI" >&2;'
                "  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then"
                f"    npm install -g @openai/codex{version_spec};"
                "  else"
                "    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash &&"
                '    export NVM_DIR="$HOME/.nvm" &&'
                '    [ -s "$NVM_DIR/nvm.sh" ] || { echo "Error: NVM failed to install" >&2; exit 1; } &&'
                '    . "$NVM_DIR/nvm.sh" &&'
                "    command -v nvm >/dev/null 2>&1 || { echo 'Error: NVM failed to load' >&2; exit 1; } &&"
                "    nvm install 22 && nvm alias default 22 && npm -v &&"
                f"    npm install -g @openai/codex{version_spec};"
                "  fi &&"
                "  hash -r &&"
                "  codex --version;"
                " fi"
            ),
        )
        await self.exec_as_root(
            environment,
            command=(
                "for bin in node npm codex; do"
                '  BIN_PATH="$(which "$bin" 2>/dev/null || true)";'
                '  if [ -n "$BIN_PATH" ] && [ "$BIN_PATH" != "/usr/local/bin/$bin" ]; then'
                '    ln -sf "$BIN_PATH" "/usr/local/bin/$bin";'
                "  fi;"
                " done"
            ),
        )

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

    def _load_goal_harness_trace_rows(self) -> list[dict[str, Any]]:
        return (
            load_goal_harness_counter_trace_file(self.goal_harness_counter_trace_json)
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
        return extract_goal_harness_interaction_counters_from_trace(
            trace_rows,
            prompt_policy_injected=not hardened_baseline,
            harness_skill_or_packet_injected=bool(
                self._goal_harness_context_metadata.get(
                    "goal_harness_access_packet_injected"
                )
            ),
            case_result_writeback=(
                no_trace_case_result_writeback
                if active_cli_bridge and not trace_rows
                else "hardened_codex_baseline_runner_only"
                if hardened_baseline
                else "not_observed_prompt_only_no_cli_bridge"
                if no_trace_prompt_only
                else "not_observed_custom_agent_metadata"
            ),
            no_trace_counter_trust_level=(
                no_trace_counter_trust_level
                if active_cli_bridge and not trace_rows
                else "hardened_codex_baseline_no_goal_harness_state"
                if hardened_baseline
                else "runtime_metadata_prompt_only_no_cli_bridge"
                if no_trace_prompt_only
                else "runtime_metadata_no_trace_observed"
            ),
        )

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
        written = write_worker_bridge_benchmark_run_file(
            self.goal_harness_benchmark_run_json,
            payload,
        )
        status = (
            "worker_bridge_benchmark_run_written"
            if written
            else "worker_bridge_benchmark_run_write_failed"
        )
        return payload, written, status

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

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        hardened_baseline = self._hardened_codex_baseline()
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
        )
        access_packet_injected = (
            self.goal_harness_mode == CODEX_GOAL_HARNESS_MODE
            and self.goal_harness_access_packet_mode
            != TERMINAL_BENCH_GOAL_HARNESS_ACCESS_PACKET_MODE_NONE
        )
        interface_surface = (
            TERMINAL_BENCH_HARDENED_CODEX_BASELINE_SURFACE
            if hardened_baseline
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
            "case_semantics_changed_by_harness": not hardened_baseline,
            "goal_harness_inside_case": not hardened_baseline,
            "official_score_comparable_to_native_codex": False,
            "official_score_comparable_to_goal_harness_treatment": hardened_baseline,
            "model_plus_harness_pair": not hardened_baseline,
            "control_plane_score_applicable": not hardened_baseline,
            "startup_surface_calibration": False,
            "hardened_install_surface": hardened_baseline,
            "hardened_install_baseline": hardened_baseline,
            "task_prompt_changed_by_goal_harness_policy": not hardened_baseline,
            "raw_task_instruction_recorded": False,
            "raw_managed_prompt_recorded": False,
            "raw_interaction_trace_recorded": False,
            "task_instruction_sha256_16": _task_hash(instruction),
            "managed_prompt_chars": len(managed_instruction),
            "context_metadata_deferred_until_post_run": True,
        }
        self._goal_harness_context_metadata[
            "goal_harness_runtime_preflight_status"
        ] = await self._ensure_goal_harness_worker_bridge_runtime(environment)
        run_completed = False
        try:
            await super().run(managed_instruction, environment, context)
            run_completed = True
        finally:
            self._goal_harness_context_metadata.update(
                {
                    "run_completed_or_interrupted": True,
                    "agent_run_completed": run_completed,
                    "agent_run_interrupted": not run_completed,
                    "credential_values_recorded": False,
                    "auth_files_recorded": False,
                    "leaderboard_evidence": False,
                    "submit_eligible": False,
                }
            )
            _, benchmark_run_written, benchmark_run_status = (
                self._write_goal_harness_worker_benchmark_run_checkpoint(
                    interrupted=not run_completed,
                    interrupt_reason=(
                        "agent_run_exception_or_nonzero_exit"
                        if not run_completed
                        else ""
                    ),
                    checkpoint_kind="run_finally",
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
            self._write_goal_harness_worker_benchmark_run_checkpoint(
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
