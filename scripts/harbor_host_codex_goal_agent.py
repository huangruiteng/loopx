"""Harbor custom agent that drives host Codex TUI goal mode.

Pass this module to Harbor with:

    --agent-import-path harbor_host_codex_goal_agent:HarborHostCodexGoalAgent

Codex runs on the benchmark host.  A tiny host-side command bridge forwards
commands into Harbor's environment through ``environment.exec()``, so the task
container does not need Codex auth or agent runtime downloads.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
for _path in (SCRIPT_DIR, REPO_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from codex_app_server_goal_driver import (
    CodexAppServerGoalDriverError,
    compact_turn_metadata,
    observe_codex_app_server_goal_turn,
    start_codex_app_server_goal_followup_turn,
    start_codex_app_server_goal_turn,
)
from harbor_host_bridge import BRIDGE_SCRIPT_TEMPLATE
from loopx.benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LOOPX_CLI_PATH,
    BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS,
    BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE,
    BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE,
    BENCHMARK_CASE_LOOPX_REGISTRY_PATH,
    BENCHMARK_CASE_LOOPX_RUNTIME_ROOT,
    BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE,
    BENCHMARK_CASE_LOOPX_TODO_ID,
    build_benchmark_case_lifecycle_packet,
    benchmark_case_loopx_install_payload,
    benchmark_case_lifecycle_contract,
)
from loopx.benchmark_core.loop_protocol import (
    BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    LOOPX_PACKET_ONLY_OBSERVATION_ROUTE,
    LOOPX_PROMPT_POLLING_TEST_ROUTE,
    MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID,
    PACKET_ONLY_OBSERVATION_PROTOCOL_ID,
    build_benchmark_loop_contract,
    build_benchmark_loop_controller_trace,
    build_blind_loop_continuation_prompt,
    classify_loopx_treatment_claim,
    render_loop_contract_packet_lines,
)
from loopx.control_plane.todos.contract import todo_terminal_for_status
from loopx.codex_cli_goal_tui import build_codex_cli_goal_tui_input

LONG_RUN_DEFAULT_GOAL_TIMEOUT_SEC = 21600.0


try:  # pragma: no cover - exercised on the benchmark host.
    from harbor.agents.base import BaseAgent
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext
except Exception:  # pragma: no cover - keeps local smoke import dependency-free.

    class BaseAgent:  # type: ignore[no-redef]
        def __init__(
            self,
            logs_dir: Path,
            model_name: str | None = None,
            **kwargs: Any,
        ) -> None:
            del kwargs
            self.logs_dir = Path(logs_dir)
            self.model_name = model_name

    class BaseEnvironment:  # type: ignore[no-redef]
        pass

    class AgentContext:  # type: ignore[no-redef]
        metadata: dict[str, Any] | None = None


def build_codex_tui_command(
    *,
    codex_bin: str = "codex",
    model_name: str | None = None,
) -> list[str]:
    command = [
        codex_bin,
        "--no-alt-screen",
        "--ask-for-approval",
        "never",
        "--sandbox",
        "danger-full-access",
    ]
    if model_name:
        command.extend(["--model", model_name])
    return command


def _coerce_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() not in {"0", "false", "no", "off"}


LEGACY_PRE_RENAME_KWARG_PREFIX = "goal_" + "harness_"


def _reject_pre_rename_kwargs(kwargs: dict[str, Any]) -> None:
    """Fail closed when a launcher still sends pre-rename benchmark kwargs."""

    legacy_keys = sorted(
        key for key in kwargs if key.startswith(LEGACY_PRE_RENAME_KWARG_PREFIX)
    )
    if not legacy_keys:
        return
    first_key = legacy_keys[0]
    raise ValueError(
        "legacy_pre_rename_kwargs_unsupported: "
        f"use loopx_* kwargs before worker start; first_key={first_key}; "
        f"count={len(legacy_keys)}"
    )


def _compact_todo_summary(value: Any, *, todo_id: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for key in ("schema_version", "open_count", "done_count", "completed_count"):
        if key in value:
            summary[key] = value[key]
    items: list[Any] = []
    for key in ("items", "first_open_items", "first_executable_items"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            items.extend(candidate)
    if todo_id:
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("todo_id") or "") != todo_id:
                continue
            summary["case_todo"] = {
                key: item.get(key)
                for key in (
                    "todo_id",
                    "status",
                    "claimed_by",
                    "priority",
                    "task_class",
                )
                if item.get(key) not in (None, "")
            }
            break
    return summary


def _compact_interaction_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    user_channel = value.get("user_channel")
    agent_channel = value.get("agent_channel")
    cli_channel = value.get("cli_channel")
    return {
        key: compact
        for key, compact in {
            "schema_version": value.get("schema_version"),
            "mode": value.get("mode"),
            "user_action_required": (
                user_channel.get("action_required")
                if isinstance(user_channel, dict)
                else None
            ),
            "agent_must_attempt": (
                agent_channel.get("must_attempt")
                if isinstance(agent_channel, dict)
                else None
            ),
            "delivery_allowed": (
                agent_channel.get("delivery_allowed")
                if isinstance(agent_channel, dict)
                else None
            ),
            "spend_after_validation": (
                cli_channel.get("spend_after_validation")
                if isinstance(cli_channel, dict)
                else None
            ),
        }.items()
        if compact not in (None, "")
    }


def _compact_json_keys(text: str, *, case_todo_id: str = "") -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except Exception:
        return {"json_parse_ok": False}
    if not isinstance(payload, dict):
        return {"json_parse_ok": True, "json_type": type(payload).__name__}
    allowed = {
        "ok",
        "goal_id",
        "agent_id",
        "todo_id",
        "decision",
        "should_run",
        "status",
        "claimed_by",
        "spent",
        "refreshed",
        "raw_logs_recorded",
        "raw_task_text_recorded",
        "raw_verifier_output_recorded",
        "raw_agent_trajectory_recorded",
        "local_paths_recorded",
    }
    compact = {
        "json_parse_ok": True,
        **{key: payload[key] for key in sorted(allowed & set(payload))},
    }
    agent_summary = _compact_todo_summary(
        payload.get("agent_todo_summary"),
        todo_id=case_todo_id,
    )
    if agent_summary:
        compact["agent_todo_summary"] = agent_summary
    user_summary = _compact_todo_summary(payload.get("user_todo_summary"))
    if user_summary:
        compact["user_todo_summary"] = user_summary
    interaction = _compact_interaction_contract(payload.get("interaction_contract"))
    if interaction:
        compact["interaction_contract"] = interaction
    return compact


def _case_scheduler_closeout_summary(
    trace: dict[str, Any],
    *,
    result_kind: str,
) -> dict[str, Any]:
    status_summary = _case_scheduler_latest_status_summary(trace)
    commands = trace.get("commands") if isinstance(trace.get("commands"), list) else []
    refresh_observed = False
    spend_observed = False
    for command in commands:
        if not isinstance(command, dict):
            continue
        action = str(command.get("action") or "")
        if action.endswith("_refresh_state") and command.get("ok"):
            refresh_observed = True
        if action.endswith("_quota_spend") and command.get("ok"):
            spend_observed = True
    agent_summary = (
        status_summary.get("agent_todo_summary")
        if isinstance(status_summary.get("agent_todo_summary"), dict)
        else {}
    )
    user_summary = (
        status_summary.get("user_todo_summary")
        if isinstance(status_summary.get("user_todo_summary"), dict)
        else {}
    )
    case_todo = (
        agent_summary.get("case_todo")
        if isinstance(agent_summary.get("case_todo"), dict)
        else {}
    )
    closeout = {
        "schema_version": "harbor_case_loopx_closeout_summary_v0",
        "result_kind": result_kind,
        "status_observed": bool(status_summary),
        "refresh_state_observed": refresh_observed,
        "quota_spend_observed": spend_observed,
        "agent_open_count": agent_summary.get("open_count"),
        "user_open_count": user_summary.get("open_count"),
        "case_todo_id": case_todo.get("todo_id") or trace.get("case_todo_id") or "",
        "case_todo_status": case_todo.get("status") or "",
        "case_todo_claimed_by": case_todo.get("claimed_by") or "",
        "timeout_preserves_open_todo": False,
        "raw_logs_recorded": False,
        "raw_output_recorded": False,
    }
    if result_kind == "timeout_blocker":
        closeout["timeout_preserves_open_todo"] = (
            not case_todo or not todo_terminal_for_status(case_todo.get("status"))
        )
    return closeout


def _case_scheduler_latest_status_summary(trace: dict[str, Any]) -> dict[str, Any]:
    commands = trace.get("commands") if isinstance(trace.get("commands"), list) else []
    status_summary: dict[str, Any] = {}
    for command in commands:
        if not isinstance(command, dict):
            continue
        action = str(command.get("action") or "")
        if action.endswith("_status") and isinstance(command.get("stdout_summary"), dict):
            status_summary = command["stdout_summary"]
    return status_summary


def _todo_open_count(summary: Any) -> int | None:
    if not isinstance(summary, dict):
        return None
    for key in ("open_count", "open"):
        value = summary.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(0, value)
    return None


def _case_scheduler_active_todo_exit_state(trace: dict[str, Any]) -> dict[str, Any]:
    """Summarize whether case-local LoopX still has active todo work."""

    status_summary = _case_scheduler_latest_status_summary(trace)
    agent_summary = (
        status_summary.get("agent_todo_summary")
        if isinstance(status_summary.get("agent_todo_summary"), dict)
        else {}
    )
    user_summary = (
        status_summary.get("user_todo_summary")
        if isinstance(status_summary.get("user_todo_summary"), dict)
        else {}
    )
    case_todo = (
        agent_summary.get("case_todo")
        if isinstance(agent_summary.get("case_todo"), dict)
        else {}
    )
    case_status = str(case_todo.get("status") or "").strip().lower()
    case_todo_active = bool(case_status and not todo_terminal_for_status(case_status))
    agent_open_count = _todo_open_count(agent_summary)
    user_open_count = _todo_open_count(user_summary)
    agent_has_active = case_todo_active or (
        agent_open_count is not None and agent_open_count > 0
    )
    user_has_active = user_open_count is not None and user_open_count > 0
    status_observed = bool(status_summary)
    unknown = not status_observed or (
        agent_open_count is None and user_open_count is None and not case_todo
    )
    no_active_todo = bool(
        status_observed and not unknown and not agent_has_active and not user_has_active
    )
    return {
        "schema_version": "harbor_case_loopx_active_todo_exit_state_v0",
        "status_observed": status_observed,
        "no_active_todo": no_active_todo,
        "exit_condition": (
            "no_active_loopx_todo"
            if no_active_todo
            else "active_loopx_todo_present"
            if not unknown
            else "unknown_loopx_todo_state"
        ),
        "agent_open_count": agent_open_count,
        "user_open_count": user_open_count,
        "case_todo_id": case_todo.get("todo_id") or trace.get("case_todo_id") or "",
        "case_todo_status": case_todo.get("status") or "",
        "case_todo_claimed_by": case_todo.get("claimed_by") or "",
        "raw_logs_recorded": False,
        "raw_output_recorded": False,
    }


def _case_loopx_action_from_command(
    command: str,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Classify a task-environment command without recording the raw command."""

    cli = str(payload.get("case_cli_path") or BENCHMARK_CASE_LOOPX_CLI_PATH)
    try:
        parts = shlex.split(command)
    except ValueError:
        return {
            "case_loopx_cli_call": False,
            "parse_error": True,
            "raw_command_recorded": False,
        }
    if not parts or parts[0] != cli:
        return {
            "case_loopx_cli_call": False,
            "raw_command_recorded": False,
        }
    args = parts[1:]
    while len(args) >= 2 and args[0] in {
        "--format",
        "--registry",
        "--runtime-root",
    }:
        args = args[2:]
    command_name = args[0] if args else ""
    subcommand = args[1] if len(args) > 1 else ""
    action = command_name or "unknown"
    if command_name == "quota":
        action = (
            "quota_should_run"
            if subcommand == "should-run"
            else "quota_spend"
            if subcommand in {"spend", "spend-slot"}
            else f"quota_{subcommand or 'unknown'}"
        )
    elif command_name == "todo":
        action = (
            "todo_claim"
            if subcommand == "claim"
            else "todo_update"
            if subcommand == "update"
            else f"todo_{subcommand or 'unknown'}"
        )
    elif command_name == "refresh-state":
        action = "refresh_state"
    return {
        "case_loopx_cli_call": True,
        "action": action,
        "command_group": command_name or "unknown",
        "subcommand": subcommand,
        "raw_command_recorded": False,
    }


def _bridge_task_phase_from_command(command: str, *, payload: dict[str, Any]) -> str:
    case_command = _case_loopx_action_from_command(command, payload=payload)
    if case_command.get("case_loopx_cli_call"):
        return "loopx_cli"

    text = " ".join(command.strip().lower().split())
    if not text:
        return "unknown"

    test_markers = (
        "pytest",
        "python -m pytest",
        "go test",
        "cargo test",
        "npm test",
        "npm run test",
        "yarn test",
        "pnpm test",
        "make test",
        "ctest",
        "tox",
        "nox",
        "unittest",
        "rspec",
    )
    verify_markers = (
        "cargo check",
        "go vet",
        "npm run lint",
        "yarn lint",
        "pnpm lint",
        "ruff",
        "flake8",
        "mypy",
        "eslint",
        "lint",
        "verify",
    )
    build_markers = (
        "cargo build",
        "go build",
        "npm run build",
        "yarn build",
        "pnpm build",
        "python -m build",
        "cmake",
        "ninja",
        "make",
        "gcc",
        "g++",
        "clang",
        "javac",
        "mvn package",
        "gradle build",
    )
    edit_markers = (
        "apply_patch",
        "sed -i",
        "perl -pi",
        "cat >",
        "cat <<",
        "tee ",
        "touch ",
        "mv ",
        "cp ",
        "rm ",
        "mkdir ",
        "chmod ",
        "python - <<",
        "python3 - <<",
        ".write_text",
        "open(",
    )
    if any(marker in text for marker in test_markers):
        return "test"
    if any(marker in text for marker in verify_markers):
        return "verify"
    if any(marker in text for marker in build_markers):
        return "build"
    if any(marker in text for marker in edit_markers) or ">" in text:
        return "edit"
    return "unknown"


def _build_solution_phase_counters(
    *,
    bridge_phase_counts: dict[str, int],
    bridge_request_count: int,
    turn_completed_observed: bool,
    case_scheduler_trace: dict[str, Any],
    result_kind: str,
    first_blocker: str,
) -> dict[str, Any]:
    active_todo = (
        case_scheduler_trace.get("active_todo_exit_state")
        if isinstance(case_scheduler_trace.get("active_todo_exit_state"), dict)
        else {}
    )
    closeout = (
        case_scheduler_trace.get("closeout_summary")
        if isinstance(case_scheduler_trace.get("closeout_summary"), dict)
        else {}
    )
    agent_open_count = active_todo.get("agent_open_count")
    if agent_open_count is None:
        agent_open_count = closeout.get("agent_open_count")
    user_open_count = active_todo.get("user_open_count")
    if user_open_count is None:
        user_open_count = closeout.get("user_open_count")
    final_active_todo_count = None
    if isinstance(agent_open_count, int) and isinstance(user_open_count, int):
        final_active_todo_count = max(0, agent_open_count) + max(0, user_open_count)

    case_todo_status = str(
        active_todo.get("case_todo_status")
        or closeout.get("case_todo_status")
        or ""
    )
    self_declared_done_count = 1 if todo_terminal_for_status(case_todo_status) else 0
    loopx_cli_count = bridge_phase_counts.get("loopx_cli", 0)
    task_command_count = sum(
        count
        for phase, count in bridge_phase_counts.items()
        if phase != "loopx_cli" and isinstance(count, int)
    )
    return {
        "schema_version": "harbor_public_safe_solution_phase_counters_v0",
        "source": "host_bridge_command_phase_counts_and_case_loopx_status",
        "counter_granularity": "coarse_command_phase_counts_no_raw_commands",
        "bridge_request_count": bridge_request_count,
        "task_bridge_command_count": task_command_count,
        "loopx_cli_command_count": loopx_cli_count,
        "edit_command_count": bridge_phase_counts.get("edit", 0),
        "build_command_count": bridge_phase_counts.get("build", 0),
        "test_command_count": bridge_phase_counts.get("test", 0),
        "verify_command_count": bridge_phase_counts.get("verify", 0),
        "unknown_task_command_count": bridge_phase_counts.get("unknown", 0),
        "self_declared_done_count": self_declared_done_count,
        "final_agent_open_count": agent_open_count,
        "final_user_open_count": user_open_count,
        "final_active_todo_count": final_active_todo_count,
        "final_no_active_todo": active_todo.get("no_active_todo"),
        "final_case_todo_status": case_todo_status,
        "turn_completed_observed": turn_completed_observed,
        "result_kind": result_kind,
        "first_blocker_present": bool(first_blocker),
        "raw_commands_recorded": False,
        "raw_diffs_recorded": False,
        "raw_logs_recorded": False,
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
    }


def _new_prompt_driven_case_trace(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "harbor_prompt_driven_loopx_trace_v0",
        "route": BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE,
        "case_goal_id": payload.get("benchmark_case_goal_id") or "",
        "case_agent_id": payload.get("case_agent_id") or "",
        "case_todo_id": payload.get("case_todo_id") or "",
        "trace_publicness": "public_action_counts_only_no_raw_commands_no_raw_output",
        "raw_commands_recorded": False,
        "raw_output_recorded": False,
        "commands": [],
        "event_kind_counts": {},
        "command_count": 0,
        "lifecycle_observed": False,
    }


def _summarize_prompt_driven_case_trace(
    payload: dict[str, Any],
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    trace = _new_prompt_driven_case_trace(payload)
    public_commands = [
        {
            key: command[key]
            for key in (
                "action",
                "command_group",
                "subcommand",
                "return_code",
                "ok",
                "stdout_summary",
                "stderr_present",
                "raw_command_recorded",
                "raw_output_recorded",
            )
            if key in command
        }
        for command in commands
        if command.get("case_loopx_cli_call")
    ]
    counts: dict[str, int] = {}
    for command in public_commands:
        action = str(command.get("action") or "unknown")
        counts[action] = counts.get(action, 0) + 1
    lifecycle_observed = counts.get("quota_should_run", 0) > 0 and (
        counts.get("todo_claim", 0) > 0 or counts.get("todo_update", 0) > 0
    )
    trace.update(
        {
            "commands": public_commands,
            "event_kind_counts": dict(sorted(counts.items())),
            "command_count": len(public_commands),
            "lifecycle_observed": lifecycle_observed,
            "required_event_kinds_observed": {
                "quota_should_run": counts.get("quota_should_run", 0) > 0,
                "todo_claim_or_update": (
                    counts.get("todo_claim", 0) > 0
                    or counts.get("todo_update", 0) > 0
                ),
            },
        }
    )
    return trace


def _case_cli_command(
    payload: dict[str, Any],
    *args: str,
) -> str:
    cli = str(payload.get("case_cli_path") or BENCHMARK_CASE_LOOPX_CLI_PATH)
    registry = str(
        payload.get("case_registry_path") or BENCHMARK_CASE_LOOPX_REGISTRY_PATH
    )
    runtime_root = str(
        payload.get("case_runtime_root") or BENCHMARK_CASE_LOOPX_RUNTIME_ROOT
    )
    return " ".join(
        [
            shlex.quote(cli),
            "--registry",
            shlex.quote(registry),
            "--runtime-root",
            shlex.quote(runtime_root),
            "--format",
            "json",
            *map(shlex.quote, args),
        ]
    )


def _new_case_scheduler_trace(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "harbor_case_loopx_cli_scheduler_trace_v0",
        "enabled": True,
        "route": BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE,
        "formal_treatment_semantics": payload.get("formal_treatment_semantics")
        or BENCHMARK_CASE_LOOPX_FORMAL_TREATMENT_SEMANTICS,
        "execution_style": payload.get("workflow_orchestrated_route")
        or BENCHMARK_CASE_LOOPX_ORCHESTRATED_EXECUTION_STYLE,
        "host_claims_case_todo_before_agent": False,
        "case_goal_id": payload.get("benchmark_case_goal_id") or "",
        "case_registry_path": payload.get("case_registry_path") or "",
        "case_runtime_root": payload.get("case_runtime_root") or "",
        "case_agent_id": payload.get("case_agent_id") or "",
        "case_todo_id": payload.get("case_todo_id") or "",
        "case_cli_path": payload.get("case_cli_path") or "",
        "case_rollout_event_log_path": (
            payload.get("case_rollout_event_log_path") or ""
        ),
        "raw_logs_recorded": False,
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_agent_trajectory_recorded": False,
        "local_paths_recorded": False,
        "commands": [],
        "event_kind_counts": {},
        "closeout_summary": {},
    }


async def _run_case_loopx_cli(
    environment: BaseEnvironment,
    *,
    payload: dict[str, Any],
    trace: dict[str, Any],
    action: str,
    args: list[str],
    cwd: str,
    timeout_sec: int = 30,
) -> bool:
    try:
        result = await environment.exec(
            command=_case_cli_command(payload, *args),
            cwd=cwd,
            timeout_sec=timeout_sec,
        )
        return_code = int(getattr(result, "return_code", 1) or 0)
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""
        compact = {
            "action": action,
            "return_code": return_code,
            "ok": return_code == 0,
            "stdout_summary": _compact_json_keys(
                stdout.strip(),
                case_todo_id=str(payload.get("case_todo_id") or ""),
            ),
            "stderr_present": bool(stderr.strip()),
            "raw_output_recorded": False,
        }
    except Exception as exc:  # pragma: no cover - benchmark-host failure path.
        compact = {
            "action": action,
            "return_code": 125,
            "ok": False,
            "error_type": type(exc).__name__,
            "raw_output_recorded": False,
        }
    trace.setdefault("commands", []).append(compact)
    return bool(compact.get("ok"))


async def _collect_case_rollout_event_counts(
    environment: BaseEnvironment,
    *,
    payload: dict[str, Any],
    trace: dict[str, Any],
    cwd: str,
) -> None:
    event_log = str(payload.get("case_rollout_event_log_path") or "")
    if not event_log:
        return
    result = await environment.exec(
        command=f"cat {shlex.quote(event_log)} 2>/dev/null || true",
        cwd=cwd,
        timeout_sec=10,
    )
    counts: dict[str, int] = {}
    total = 0
    for line in (getattr(result, "stdout", "") or "").splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        kind = str(event.get("event_kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
        total += 1
    trace["event_kind_counts"] = dict(sorted(counts.items()))
    trace["event_count"] = total
    trace["event_log_read_return_code"] = int(
        getattr(result, "return_code", 0) or 0
    )


def build_host_goal_prompt(
    *,
    instruction: str,
    bridge_command: Path,
    task_workdir: str = "/app",
    loopx_access_packet: str = "",
) -> str:
    bridge = shlex.quote(str(bridge_command))
    task_workdir_arg = shlex.quote(task_workdir)
    access_packet = loopx_access_packet.strip()
    access_packet_section = (
        "\n\nLoopX treatment access packet:\n"
        "After the bridge check and before substantive work, use the "
        "case-local LoopX CLI listed below to run quota should-run and "
        "claim the case todo through the same task-environment bridge. These "
        "calls are part of the treatment proof, so do not replace them with a "
        "mental note or a host-side shortcut. Keep case-local state isolated "
        "to the listed benchmark_case_goal_id.\n"
        f"{access_packet}"
        if access_packet
        else ""
    )
    completion_clause = (
        "LoopX is the completion source of truth for this treatment. When the\n"
        "task is genuinely complete, mark the case-local LoopX todo done using\n"
            "the command in the access packet. The host exits only after it confirms\n"
            "there is no active case-local LoopX todo; do not create a separate\n"
            "completion file."
        if access_packet
        else (
            "When the task is complete, finish the Codex turn. Do not create a\n"
            "separate completion file."
        )
    )
    return f"""
You are solving a Harbor benchmark task using native Codex Goal mode on the host.

Run task-environment commands through this host bridge:
  {bridge} --cwd {task_workdir_arg} -- <command>

Before planning or editing, first verify the bridge with this harmless command:
  {bridge} --cwd {task_workdir_arg} -- pwd

Do not modify tests. Complete the task inside the Harbor environment only.

Task instruction:
{instruction}
{access_packet_section}

{completion_clause}
""".strip()


def build_loopx_access_packet(
    *,
    mode: str,
    packet_mode: str = "compact",
    goal_id: str = "loopx-meta",
    cli_bridge_enabled: str | bool = False,
    command_prefix: str = "loopx",
    registry_arg: str = "",
    runtime_root_arg: str = "",
    scan_path: str = "",
    classification: str = "swe_marathon_codex_loopx_treatment",
    experiment_protocol: str = MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID,
    max_rounds: int = BLIND_LOOP_DEFAULT_MAX_ROUNDS,
    benchmark_id: str = "swe-marathon",
    case_id: str = "current-case",
    arm_id: str = "codex_loopx_treatment",
) -> str:
    """Build a public-safe LoopX access packet for Harbor/SWE tasks."""

    if mode != "codex_loopx" or packet_mode == "none":
        return ""

    cli_enabled = _coerce_bool(cli_bridge_enabled)
    base = command_prefix
    if registry_arg:
        base += f" --registry {shlex.quote(registry_arg)}"
    if runtime_root_arg:
        base += f" --runtime-root {shlex.quote(runtime_root_arg)}"
    base += " --format json"
    goal_id_arg = shlex.quote(goal_id)
    scan_path_arg = shlex.quote(scan_path) if scan_path else "<public-scan-path>"
    route = (
        LOOPX_PROMPT_POLLING_TEST_ROUTE
        if experiment_protocol == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
        else LOOPX_PACKET_ONLY_OBSERVATION_ROUTE
    )
    loop_contract = build_benchmark_loop_contract(
        route=route,
        max_rounds=max_rounds,
        protocol_id=experiment_protocol,
    )
    claim = classify_loopx_treatment_claim(
        {"benchmark_loop_contract": loop_contract}
    )
    case_lifecycle_packet, case_lifecycle = build_benchmark_case_lifecycle_packet(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arm_id=arm_id,
        max_rounds=max_rounds,
        include_case_paths=True,
        include_case_event_log=True,
        include_cli_commands=cli_enabled,
        include_completion_hints=cli_enabled,
    )

    lines = [
        "LoopX Access Packet V0",
        "benchmark_family: harbor",
        f"mode: {mode}",
        f"packet_mode: {packet_mode}",
        f"goal_id: {goal_id}",
        f"classification: {classification}",
        f"loopx_cli_bridge_available: {str(cli_enabled).lower()}",
        "runner_side_official_verifier_remains_authoritative: true",
        "do_not_modify_tests: true",
        "do_not_upload_or_submit_to_leaderboard: true",
        "do_not_record_raw_task_text_logs_trajectories_or_credentials: true",
        "use_loopx_for_planning_checkpoints_and_boundary_awareness_only: false",
        "task_environment_commands_still_must_use_harbor_env_exec_bridge: true",
        "loopx_prompt_driven_loop_required: true",
        "loopx_scheduler_route_supported_for_smoke_or_fallback: true",
        "loopx_case_local_cli_installed_before_agent: true",
        f"loopx_treatment_evidence_tier: {claim['loopx_treatment_evidence_tier']}",
        f"strict_loopx_treatment_claim_allowed: {str(claim['strict_loopx_treatment_claim_allowed']).lower()}",
        f"loopx_treatment_claim_blocker: {claim['loopx_treatment_claim_blocker']}",
    ]
    lines.extend(render_loop_contract_packet_lines(loop_contract))
    lines.extend(case_lifecycle_packet.splitlines())
    if cli_enabled:
        lines.extend(
            [
                "primary_loopx_cli_surface: task_environment_case_local_cli",
                f"loopx_global_command_check_optional_context: {base} check --scan-path {scan_path_arg}",
                f"loopx_global_command_status_optional_context: {base} status --limit 5",
                f"loopx_global_command_history_optional_context: {base} history --goal-id {goal_id_arg} --limit 5",
            ]
        )
    else:
        lines.extend(
            [
                "loopx_interface_surface: prompt_packet_only",
                "worker_receives_no_loopx_cli_templates: true",
            ]
        )
    return "\n".join(lines)


def build_case_goal_state_init_payload(
    *,
    benchmark_id: str,
    case_id: str,
    arm_id: str,
    route: str,
    max_rounds: int,
) -> dict[str, Any]:
    """Build the public-safe case-local LoopX install/state/todo payload."""

    return dict(
        benchmark_case_loopx_install_payload(
            benchmark_id=benchmark_id,
            case_id=case_id,
            arm_id=arm_id,
            route=route,
            max_rounds=max_rounds,
        )
    )


def _case_goal_state_init_compact(
    payload: dict[str, Any] | None,
    *,
    status: str,
    initialized_before_agent: bool,
) -> dict[str, Any]:
    payload = payload or {}
    required = bool(payload)
    return {
        "case_goal_state_init_required": required,
        "case_goal_state_initialized_before_agent": bool(initialized_before_agent),
        "case_goal_state_init_status": status if required else "not_required",
        "case_goal_state_schema_version": (
            payload.get("schema_version") or BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
        ),
        "case_goal_state_path": payload.get("case_state_path") or "",
        "loopx_install_flow_required": bool(
            payload.get("install_flow_required") if required else False
        ),
        "loopx_install_flow_status": status if required else "not_required",
        "loopx_case_cli_installed_before_agent": bool(
            payload.get("case_cli_path") and initialized_before_agent
        ),
        "loopx_case_cli_path": payload.get("case_cli_path") or "",
        "loopx_case_registry_path": payload.get("case_registry_path") or "",
        "loopx_case_runtime_root": payload.get("case_runtime_root") or "",
        "loopx_case_rollout_event_log_path": (
            payload.get("case_rollout_event_log_path") or ""
        ),
        "loopx_case_agent_id": payload.get("case_agent_id") or "",
        "loopx_case_todo_id": payload.get("case_todo_id") or "",
        "loopx_case_todo_seeded": bool(payload.get("case_todo_seeded")),
        "loopx_case_todo_preclaimed": bool(payload.get("case_todo_preclaimed")),
        "loopx_formal_treatment_semantics": (
            payload.get("formal_treatment_semantics") or ""
        ),
        "loopx_lifecycle_driver_schema_version": (
            payload.get("lifecycle_driver_schema_version") or ""
        ),
        "loopx_canonical_product_mode_lifecycle_driver": bool(
            payload.get("canonical_product_mode_lifecycle_driver")
        ),
        "loopx_execution_style": payload.get("execution_style") or "",
        "loopx_host_claims_case_todo_before_agent": bool(
            payload.get("host_claims_case_todo_before_agent")
        ),
        "loopx_agent_must_claim_selected_case_todo": bool(
            payload.get("agent_must_claim_selected_case_todo")
        ),
        "loopx_product_path_primary_route": (
            payload.get("product_path_primary_route") or ""
        ),
        "loopx_prompt_driven_route_required": bool(
            payload.get("prompt_driven_route_required")
        ),
        "loopx_scheduler_route_supported": bool(
            payload.get("scheduler_route_supported")
        ),
        "case_goal_state_raw_output_recorded": False,
    }


class HarborHostCodexGoalAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "harbor-host-codex-goal"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        goal_timeout_sec: str | int | float = LONG_RUN_DEFAULT_GOAL_TIMEOUT_SEC,
        codex_bin: str = "codex",
        task_workdir: str = "/app",
        goal_surface: str = "tui",
        reasoning_effort: str | None = "high",
        app_server_wait_for_completion: str | bool = False,
        app_server_response_timeout_sec: str | int | float = 30,
        loopx_mode: str = "codex_goal_mode_baseline",
        loopx_goal_id: str = "loopx-meta",
        loopx_access_packet_mode: str = "none",
        loopx_cli_bridge_enabled: str | bool = False,
        loopx_command_prefix: str = "loopx",
        loopx_registry_arg: str = "",
        loopx_runtime_root_arg: str = "",
        loopx_scan_path: str = "",
        loopx_classification: str = (
            "swe_marathon_codex_loopx_treatment"
        ),
        loopx_experiment_protocol: str = MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID,
        loopx_max_rounds: str | int = BLIND_LOOP_DEFAULT_MAX_ROUNDS,
        loopx_prompt_polling_rounds: str | int = "auto",
        loopx_prompt_polling_round_timeout_sec: str | int | float = "auto",
        loopx_benchmark_id: str = "swe-marathon",
        loopx_case_id: str = "current-case",
        loopx_arm_id: str = "codex_loopx_treatment",
        startup_delay_sec: str | int | float = 5,
        poll_interval_sec: str | int | float = 5,
        **kwargs: Any,
    ) -> None:
        _reject_pre_rename_kwargs(kwargs)
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.goal_timeout_sec = float(goal_timeout_sec)
        self.codex_bin = codex_bin
        self.task_workdir = task_workdir
        self.goal_surface = goal_surface
        self.reasoning_effort = reasoning_effort
        self.app_server_wait_for_completion = _coerce_bool(app_server_wait_for_completion)
        self.app_server_response_timeout_sec = float(app_server_response_timeout_sec)
        self.loopx_mode = loopx_mode
        self.loopx_goal_id = loopx_goal_id
        self.loopx_access_packet_mode = loopx_access_packet_mode
        self.loopx_cli_bridge_enabled = _coerce_bool(
            loopx_cli_bridge_enabled
        )
        self.loopx_command_prefix = loopx_command_prefix
        self.loopx_registry_arg = loopx_registry_arg
        self.loopx_runtime_root_arg = loopx_runtime_root_arg
        self.loopx_scan_path = loopx_scan_path
        self.loopx_classification = loopx_classification
        self.loopx_experiment_protocol = loopx_experiment_protocol
        self.loopx_max_rounds = int(loopx_max_rounds)
        self.loopx_benchmark_id = loopx_benchmark_id
        self.loopx_case_id = loopx_case_id
        self.loopx_arm_id = loopx_arm_id
        if str(loopx_prompt_polling_rounds).strip().lower() == "auto":
            self.loopx_prompt_polling_rounds = (
                self.loopx_max_rounds
                if loopx_experiment_protocol
                == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
                else 1
            )
        else:
            self.loopx_prompt_polling_rounds = max(
                1,
                int(loopx_prompt_polling_rounds),
            )
        if str(loopx_prompt_polling_round_timeout_sec).strip().lower() == "auto":
            self.loopx_prompt_polling_round_timeout_sec = max(
                30.0,
                self.goal_timeout_sec,
            )
        else:
            self.loopx_prompt_polling_round_timeout_sec = max(
                30.0,
                float(loopx_prompt_polling_round_timeout_sec),
            )
        self.startup_delay_sec = float(startup_delay_sec)
        self.poll_interval_sec = float(poll_interval_sec)
        self._served_request_count = 0
        self._case_state_init_payload: dict[str, Any] = {}
        self._prompt_driven_loopx_commands: list[dict[str, Any]] = []
        self._bridge_phase_counts: dict[str, int] = {}

    def version(self) -> str:
        return "0.5.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        del environment

    def _tmux(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["tmux", *args],
            check=check,
            capture_output=True,
            text=True,
        )

    def _capture(self, session_name: str) -> str:
        result = self._tmux("capture-pane", "-pt", session_name, "-S", "-300", check=False)
        return result.stdout or result.stderr or ""

    @staticmethod
    def _write_bridge_script(path: Path, request_dir: Path) -> None:
        path.write_text(
            BRIDGE_SCRIPT_TEMPLATE.replace(
                "__LOOPX_REQUEST_DIR__",
                str(request_dir),
            ),
            encoding="utf-8",
        )
        path.chmod(0o755)

    async def _serve_bridge_requests(
        self,
        environment: BaseEnvironment,
        request_dir: Path,
    ) -> None:
        for request in sorted(request_dir.glob("*.request.json")):
            request_id = request.name.removesuffix(".request.json")
            running = request_dir / f"{request_id}.running.json"
            response = request_dir / f"{request_id}.response.json"
            try:
                request.rename(running)
            except FileNotFoundError:
                continue
            try:
                payload = json.loads(running.read_text(encoding="utf-8"))
                timeout_sec = int(float(payload.get("timeout_sec") or 600))
                cwd = payload.get("cwd") or None
                phase = _bridge_task_phase_from_command(
                    str(payload["command"]),
                    payload=self._case_state_init_payload,
                )
                self._bridge_phase_counts[phase] = (
                    self._bridge_phase_counts.get(phase, 0) + 1
                )
                result = await environment.exec(
                    command=str(payload["command"]),
                    cwd=cwd,
                    timeout_sec=timeout_sec,
                )
                case_command = _case_loopx_action_from_command(
                    str(payload["command"]),
                    payload=self._case_state_init_payload,
                )
                if case_command.get("case_loopx_cli_call"):
                    case_command.update(
                        {
                            "return_code": int(result.return_code or 0),
                            "ok": int(result.return_code or 0) == 0,
                            "stdout_summary": _compact_json_keys(
                                (result.stdout or "").strip()
                            ),
                            "stderr_present": bool((result.stderr or "").strip()),
                            "raw_output_recorded": False,
                        }
                    )
                    self._prompt_driven_loopx_commands.append(case_command)
                response.write_text(
                    json.dumps(
                        {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "return_code": result.return_code,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            except Exception as exc:  # pragma: no cover - benchmark-host failure path.
                response.write_text(
                    json.dumps(
                        {
                            "stdout": "",
                            "stderr": f"harbor-env-exec bridge failed: {exc}",
                            "return_code": 125,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            finally:
                self._served_request_count += 1
                running.unlink(missing_ok=True)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        run_id = uuid.uuid4().hex[:10]
        work_dir = self.logs_dir / f"host-codex-goal-{run_id}"
        request_dir = work_dir / "requests"
        bin_dir = work_dir / "bin"
        work_dir.mkdir(parents=True, exist_ok=True)
        request_dir.mkdir(parents=True, exist_ok=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        self._case_state_init_payload = {}
        self._prompt_driven_loopx_commands = []
        self._bridge_phase_counts = {}

        bridge = bin_dir / "harbor-env-exec"
        prompt_path = work_dir / "prompt.txt"
        capture_path = work_dir / "tmux_capture.txt"
        tmux_name = f"loopx_harbor_goal_{run_id}"
        self._write_bridge_script(bridge, request_dir)

        loopx_access_packet = build_loopx_access_packet(
            mode=self.loopx_mode,
            packet_mode=self.loopx_access_packet_mode,
            goal_id=self.loopx_goal_id,
            cli_bridge_enabled=self.loopx_cli_bridge_enabled,
            command_prefix=self.loopx_command_prefix,
            registry_arg=self.loopx_registry_arg,
            runtime_root_arg=self.loopx_runtime_root_arg,
            scan_path=self.loopx_scan_path,
            classification=self.loopx_classification,
            experiment_protocol=self.loopx_experiment_protocol,
            max_rounds=self.loopx_max_rounds,
            benchmark_id=self.loopx_benchmark_id,
            case_id=self.loopx_case_id,
            arm_id=self.loopx_arm_id,
        )
        case_state_init_payload: dict[str, Any] = {}
        case_state_init_compact = _case_goal_state_init_compact(
            None,
            status="not_required",
            initialized_before_agent=False,
        )
        case_scheduler_trace: dict[str, Any] = {}
        loop_contract: dict[str, Any] = {}
        treatment_claim: dict[str, Any] = {}
        if loopx_access_packet:
            case_lifecycle_contract = benchmark_case_lifecycle_contract(
                benchmark_id=self.loopx_benchmark_id,
                case_id=self.loopx_case_id,
                arm_id=self.loopx_arm_id,
                max_rounds=self.loopx_max_rounds,
            )
            loop_route = (
                LOOPX_PROMPT_POLLING_TEST_ROUTE
                if self.loopx_experiment_protocol
                == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
                else LOOPX_PACKET_ONLY_OBSERVATION_ROUTE
            )
            loop_contract = build_benchmark_loop_contract(
                route=loop_route,
                max_rounds=self.loopx_max_rounds,
                protocol_id=self.loopx_experiment_protocol,
            )
            case_state_init_payload = build_case_goal_state_init_payload(
                benchmark_id=self.loopx_benchmark_id,
                case_id=self.loopx_case_id,
                arm_id=self.loopx_arm_id,
                route=loop_route,
                max_rounds=self.loopx_max_rounds,
            )
            self._case_state_init_payload = dict(case_state_init_payload)
            init_result = await environment.exec(
                command=str(case_state_init_payload["command"]),
                cwd=self.task_workdir,
                timeout_sec=30,
            )
            init_ok = int(getattr(init_result, "return_code", 1) or 0) == 0
            case_state_init_compact = _case_goal_state_init_compact(
                case_state_init_payload,
                status="initialized" if init_ok else "init_failed",
                initialized_before_agent=init_ok,
            )
            (work_dir / "case_goal_state_init.compact.json").write_text(
                json.dumps(case_state_init_compact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if not init_ok:
                blocker_payload = {
                    "schema_version": "harbor_host_codex_goal_agent_v0",
                    "goal_surface": self.goal_surface,
                    "ok": False,
                    "first_blocker": "harbor_case_goal_state_init_failed",
                    "raw_output_recorded": False,
                    "loopx_mode": self.loopx_mode,
                    "loopx_access_packet_injected": True,
                    "benchmark_loop_contract": loop_contract,
                    "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                    **case_state_init_compact,
                }
                (work_dir / "app_server_goal_turn.compact.json").write_text(
                    json.dumps(blocker_payload, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                context.metadata = {
                    "loopx_agent": self.name(),
                    "first_blocker": "harbor_case_goal_state_init_failed",
                    "loopx_mode": self.loopx_mode,
                    "loopx_access_packet_injected": True,
                    "benchmark_loop_contract": loop_contract,
                    "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                    **case_state_init_compact,
                }
                return
            if self.loopx_cli_bridge_enabled:
                case_scheduler_trace = _new_case_scheduler_trace(
                    case_state_init_payload
                )
                case_goal_id = str(
                    case_state_init_payload.get("benchmark_case_goal_id") or ""
                )
                case_agent_id = str(
                    case_state_init_payload.get("case_agent_id") or ""
                )
                pre_agent_specs = [
                    ("case_cli_doctor", ["doctor"]),
                    (
                        "case_cli_status_before_agent",
                        [
                            "status",
                            "--limit",
                            "5",
                            "--agent-id",
                            case_agent_id,
                        ],
                    ),
                    (
                        "case_quota_should_run_before_agent",
                        [
                            "quota",
                            "should-run",
                            "--goal-id",
                            case_goal_id,
                            "--agent-id",
                            case_agent_id,
                        ],
                    ),
                ]
                pre_agent_ok = True
                for action, args in pre_agent_specs:
                    pre_agent_ok = (
                        await _run_case_loopx_cli(
                            environment,
                            payload=case_state_init_payload,
                            trace=case_scheduler_trace,
                            action=action,
                            args=args,
                            cwd=self.task_workdir,
                        )
                        and pre_agent_ok
                    )
                await _collect_case_rollout_event_counts(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    cwd=self.task_workdir,
                )
                case_scheduler_trace["pre_agent_lifecycle_ok"] = pre_agent_ok
                (work_dir / "loopx_case_rollout_trace.public.json").write_text(
                    json.dumps(case_scheduler_trace, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                if not pre_agent_ok:
                    blocker_payload = {
                        "schema_version": "harbor_host_codex_goal_agent_v0",
                        "goal_surface": self.goal_surface,
                        "ok": False,
                        "first_blocker": (
                            "harbor_case_loopx_scheduler_preflight_failed"
                        ),
                        "raw_output_recorded": False,
                        "loopx_mode": self.loopx_mode,
                        "loopx_access_packet_injected": True,
                        "loopx_case_scheduler_trace_present": True,
                        "loopx_case_scheduler_pre_agent_ok": False,
                        "benchmark_loop_contract": loop_contract,
                        "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                        **case_state_init_compact,
                    }
                    (work_dir / "app_server_goal_turn.compact.json").write_text(
                        json.dumps(blocker_payload, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    context.metadata = {
                        "loopx_agent": self.name(),
                        "first_blocker": (
                            "harbor_case_loopx_scheduler_preflight_failed"
                        ),
                        "loopx_mode": self.loopx_mode,
                        "loopx_access_packet_injected": True,
                        "loopx_case_scheduler_trace_present": True,
                        **case_state_init_compact,
                    }
                    return
            treatment_claim = classify_loopx_treatment_claim(
                {"benchmark_loop_contract": loop_contract}
            )
        else:
            case_lifecycle_contract = {}
        prompt = build_host_goal_prompt(
            instruction=instruction,
            bridge_command=bridge,
            task_workdir=self.task_workdir,
            loopx_access_packet=loopx_access_packet,
        )
        prompt_path.write_text(
            build_codex_cli_goal_tui_input(prompt),
            encoding="utf-8",
        )

        if self.goal_surface == "app_server":
            try:
                turn_task = asyncio.create_task(
                    asyncio.to_thread(
                        start_codex_app_server_goal_turn,
                        codex_bin=self.codex_bin,
                        work_dir=work_dir,
                        objective="Complete the Harbor benchmark task using the task environment bridge.",
                        prompt=prompt,
                        model_name=self.model_name,
                        reasoning_effort=self.reasoning_effort,
                        response_timeout_sec=self.app_server_response_timeout_sec,
                        wait_for_completion=False,
                    )
                )
                while not turn_task.done():
                    await self._serve_bridge_requests(environment, request_dir)
                    await asyncio.sleep(self.poll_interval_sec)
                turn = await turn_task
            except CodexAppServerGoalDriverError as exc:
                (work_dir / "app_server_goal_turn.compact.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "harbor_host_codex_goal_agent_v0",
                            "goal_surface": "app_server",
                            "ok": False,
                            "first_blocker": "codex_app_server_goal_turn_failed",
                            "error_type": type(exc).__name__,
                            "raw_transcript_recorded": False,
                            "loopx_mode": self.loopx_mode,
                            "loopx_access_packet_injected": bool(
                                loopx_access_packet
                            ),
                            "benchmark_loop_contract": loop_contract,
                            "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                            **case_state_init_compact,
                        },
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                context.metadata = {
                    "loopx_agent": self.name(),
                    "bridge_request_count": self._served_request_count,
                    "first_blocker": "codex_app_server_goal_turn_failed",
                    "loopx_mode": self.loopx_mode,
                    "loopx_access_packet_injected": bool(
                        loopx_access_packet
                    ),
                    "benchmark_loop_contract": loop_contract,
                    "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                    **case_state_init_compact,
                }
                return
            await self._serve_bridge_requests(environment, request_dir)

            prompt_polling_enabled = bool(
                loopx_access_packet
                and self.loopx_experiment_protocol
                == MAX5_BLIND_LOOP_NO_FEEDBACK_PROTOCOL_ID
                and self.loopx_prompt_polling_rounds > 1
            )
            controller_trace: dict[str, Any] = {}
            if prompt_polling_enabled:
                controller_trace = build_benchmark_loop_controller_trace(
                    route=LOOPX_PROMPT_POLLING_TEST_ROUTE,
                    max_rounds=self.loopx_max_rounds,
                    schema_version="harbor_host_prompt_polling_controller_trace_v0",
                )
                controller_trace["initial_prompt_count"] = 1
                controller_trace["controller_action_decisions"] = 1
                controller_trace["last_decision"] = "start_initial_app_server_goal_turn"
                treatment_claim = classify_loopx_treatment_claim(
                    {
                        "benchmark_loop_contract": loop_contract,
                        "controller_trace_present": True,
                    }
                )

            def write_compact(
                first_blocker: str = "",
                *,
                result_kind: str = "case_result",
            ) -> dict[str, Any]:
                compact = compact_turn_metadata(turn)
                case_scheduler_command_count = len(
                    case_scheduler_trace.get("commands") or []
                )
                prompt_driven_trace = _summarize_prompt_driven_case_trace(
                    case_state_init_payload,
                    self._prompt_driven_loopx_commands,
                )
                current_treatment_claim = classify_loopx_treatment_claim(
                    {
                        "benchmark_loop_contract": loop_contract,
                        "controller_trace_present": bool(controller_trace),
                        "loopx_product_path_primary_route": (
                            case_state_init_payload.get("product_path_primary_route")
                            or ""
                        ),
                        "loopx_prompt_driven_loop_required": bool(
                            case_state_init_payload.get("prompt_driven_route_required")
                        ),
                        "loopx_prompt_driven_lifecycle_observed": bool(
                            prompt_driven_trace.get("lifecycle_observed")
                        ),
                    }
                )
                compact.update(
                    {
                        "goal_surface": "app_server",
                        "app_server_wait_for_completion_requested": self.app_server_wait_for_completion,
                        "app_server_completion_hard_gate": False,
                        "completion_source_of_truth": (
                            "case_local_active_todo"
                            if case_state_init_payload
                            else "codex_turn_completion"
                        ),
                        "bridge_request_count": self._served_request_count,
                        "first_blocker": first_blocker,
                        "loopx_mode": self.loopx_mode,
                        "loopx_access_packet_injected": bool(
                            loopx_access_packet
                        ),
                        "loopx_cli_bridge_enabled": (
                            self.loopx_cli_bridge_enabled
                        ),
                        "prompt_polling_enabled": prompt_polling_enabled,
                        "prompt_polling_rounds_requested": (
                            self.loopx_prompt_polling_rounds
                        ),
                        "prompt_polling_round_timeout_sec": (
                            self.loopx_prompt_polling_round_timeout_sec
                        ),
                        "benchmark_loop_contract": loop_contract,
                        "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                        "loopx_case_scheduler_trace_present": bool(
                            case_scheduler_trace
                        ),
                        "loopx_case_scheduler_route": (
                            case_scheduler_trace.get("route") or ""
                        ),
                        "loopx_case_scheduler_pre_agent_ok": bool(
                            case_scheduler_trace.get("pre_agent_lifecycle_ok")
                        ),
                        "loopx_case_scheduler_command_count": (
                            case_scheduler_command_count
                        ),
                        "loopx_case_rollout_event_counts": (
                            case_scheduler_trace.get("event_kind_counts") or {}
                        ),
                        "loopx_case_active_todo_exit_state": (
                            case_scheduler_trace.get("active_todo_exit_state") or {}
                        ),
                        "loopx_case_closeout_summary": (
                            case_scheduler_trace.get("closeout_summary") or {}
                        ),
                        "loopx_solution_phase_counters": (
                            _build_solution_phase_counters(
                                bridge_phase_counts=self._bridge_phase_counts,
                                bridge_request_count=self._served_request_count,
                                turn_completed_observed=bool(
                                    turn.turn_completed_observed
                                ),
                                case_scheduler_trace=case_scheduler_trace,
                                result_kind=result_kind,
                                first_blocker=first_blocker,
                            )
                        ),
                        "loopx_prompt_driven_trace_present": bool(
                            prompt_driven_trace.get("command_count")
                        ),
                        "loopx_prompt_driven_case_cli_call_count": (
                            prompt_driven_trace.get("command_count") or 0
                        ),
                        "loopx_prompt_driven_event_counts": (
                            prompt_driven_trace.get("event_kind_counts") or {}
                        ),
                        "loopx_prompt_driven_lifecycle_observed": bool(
                            prompt_driven_trace.get("lifecycle_observed")
                        ),
                        **case_state_init_compact,
                        **current_treatment_claim,
                    }
                )
                if loopx_access_packet:
                    (
                        work_dir / "loopx_prompt_driven_trace.public.json"
                    ).write_text(
                        json.dumps(prompt_driven_trace, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                if controller_trace:
                    compact["loopx_controller_trace_present"] = True
                    compact["loopx_controller_trace"] = controller_trace
                    (work_dir / "loopx_controller_trace.public.json").write_text(
                        json.dumps(controller_trace, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                if case_scheduler_trace:
                    (work_dir / "loopx_case_rollout_trace.public.json").write_text(
                        json.dumps(case_scheduler_trace, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                (work_dir / "app_server_goal_turn.compact.json").write_text(
                    json.dumps(compact, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                return compact

            async def run_case_scheduler_round(
                *,
                round_index: int,
                stage: str,
            ) -> dict[str, Any]:
                if not case_scheduler_trace or not case_state_init_payload:
                    return {}
                case_goal_id = str(
                    case_state_init_payload.get("benchmark_case_goal_id") or ""
                )
                case_agent_id = str(
                    case_state_init_payload.get("case_agent_id") or ""
                )
                case_todo_id = str(case_state_init_payload.get("case_todo_id") or "")
                await _run_case_loopx_cli(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    action=f"{stage}_round_{round_index}_quota_should_run",
                    args=[
                        "quota",
                        "should-run",
                        "--goal-id",
                        case_goal_id,
                        "--agent-id",
                        case_agent_id,
                    ],
                    cwd=self.task_workdir,
                )
                await _run_case_loopx_cli(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    action=f"{stage}_round_{round_index}_todo_update",
                    args=[
                        "todo",
                        "update",
                        "--goal-id",
                        case_goal_id,
                        "--todo-id",
                        case_todo_id,
                        "--claimed-by",
                        case_agent_id,
                    ],
                    cwd=self.task_workdir,
                )
                await _run_case_loopx_cli(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    action=f"{stage}_round_{round_index}_status",
                    args=["status", "--goal-id", case_goal_id, "--limit", "5"],
                    cwd=self.task_workdir,
                )
                exit_state = _case_scheduler_active_todo_exit_state(
                    case_scheduler_trace
                )
                case_scheduler_trace["active_todo_exit_state"] = exit_state
                await _collect_case_rollout_event_counts(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    cwd=self.task_workdir,
                )
                return exit_state

            async def run_case_scheduler_closeout(*, result_kind: str) -> None:
                if not case_scheduler_trace or not case_state_init_payload:
                    return
                case_goal_id = str(
                    case_state_init_payload.get("benchmark_case_goal_id") or ""
                )
                case_agent_id = str(
                    case_state_init_payload.get("case_agent_id") or ""
                )
                closeout_specs = [
                    (
                        f"{result_kind}_status",
                        ["status", "--goal-id", case_goal_id, "--limit", "5"],
                    ),
                    (
                        f"{result_kind}_refresh_state",
                        ["refresh-state", "--goal-id", case_goal_id],
                    ),
                    (
                        f"{result_kind}_quota_spend",
                        [
                            "quota",
                            "spend-slot",
                            "--goal-id",
                            case_goal_id,
                            "--agent-id",
                            case_agent_id,
                        ],
                    ),
                ]
                for action, args in closeout_specs:
                    await _run_case_loopx_cli(
                        environment,
                        payload=case_state_init_payload,
                        trace=case_scheduler_trace,
                        action=action,
                        args=args,
                        cwd=self.task_workdir,
                    )
                case_scheduler_trace["closeout_summary"] = (
                    _case_scheduler_closeout_summary(
                        case_scheduler_trace,
                        result_kind=result_kind,
                    )
                )
                await _collect_case_rollout_event_counts(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    cwd=self.task_workdir,
                )

            if prompt_polling_enabled:
                deadline = time.time() + self.goal_timeout_sec
                current_round = 1
                timeout_blocker = ""
                runtime_blocker = ""
                try:
                    while current_round <= self.loopx_prompt_polling_rounds:
                        active_todo_exit_state: dict[str, Any] = {}
                        round_deadline = min(
                            deadline,
                            time.time() + self.loopx_prompt_polling_round_timeout_sec,
                        )
                        while time.time() < round_deadline:
                            observe_codex_app_server_goal_turn(turn)
                            await self._serve_bridge_requests(environment, request_dir)
                            if turn.turn_completed_observed:
                                break
                            await asyncio.sleep(self.poll_interval_sec)
                        controller_trace["max_round_observed"] = max(
                            int(controller_trace.get("max_round_observed", -1)),
                            current_round,
                        )
                        controller_trace["round_timeout_sec"] = (
                            self.loopx_prompt_polling_round_timeout_sec
                        )
                        active_todo_exit_state = await run_case_scheduler_round(
                            round_index=current_round,
                            stage="post_turn",
                        )
                        if active_todo_exit_state:
                            controller_trace["active_todo_exit_state"] = (
                                active_todo_exit_state
                            )
                        if active_todo_exit_state.get("no_active_todo") is True:
                            await self._serve_bridge_requests(
                                environment,
                                request_dir,
                            )
                            await asyncio.sleep(
                                min(max(self.poll_interval_sec, 0.01), 1.0)
                            )
                            case_goal_id = str(
                                case_state_init_payload.get(
                                    "benchmark_case_goal_id"
                                )
                                or ""
                            )
                            await _run_case_loopx_cli(
                                environment,
                                payload=case_state_init_payload,
                                trace=case_scheduler_trace,
                                action=(
                                    f"post_turn_round_{current_round}"
                                    "_status_confirm"
                                ),
                                args=[
                                    "status",
                                    "--goal-id",
                                    case_goal_id,
                                    "--limit",
                                    "5",
                                ],
                                cwd=self.task_workdir,
                            )
                            active_todo_exit_state = (
                                _case_scheduler_active_todo_exit_state(
                                    case_scheduler_trace
                                )
                            )
                            case_scheduler_trace["active_todo_exit_state"] = (
                                active_todo_exit_state
                            )
                            controller_trace["active_todo_exit_state"] = (
                                active_todo_exit_state
                            )
                            if (
                                active_todo_exit_state.get("no_active_todo")
                                is True
                            ):
                                controller_trace[
                                    "no_active_todo_confirmed_count"
                                ] = (
                                    int(
                                        controller_trace.get(
                                            "no_active_todo_confirmed_count", 0
                                        )
                                    )
                                    + 1
                                )
                                controller_trace["last_decision"] = (
                                    "stop_after_confirmed_no_active_loopx_todo"
                                )
                                break
                        if (
                            time.time() >= round_deadline
                            and not turn.turn_completed_observed
                        ):
                            timeout_blocker = (
                                "harbor_prompt_polling_round_timeout_before_completion"
                            )
                            controller_trace["last_decision"] = timeout_blocker
                            break
                        if current_round >= self.loopx_prompt_polling_rounds:
                            controller_trace["last_decision"] = (
                                "stop_at_prompt_polling_round_budget"
                            )
                            break
                        next_round = current_round + 1
                        continuation_prompt = "\n\n".join(
                            part
                            for part in (
                                loopx_access_packet,
                                build_blind_loop_continuation_prompt(
                                    scheduled_round=next_round,
                                    max_rounds=self.loopx_prompt_polling_rounds,
                                    persistent_constraint_clause=(
                                        " Use harbor-env-exec for task-environment "
                                        "commands; do not upload or submit."
                                    ),
                                ),
                            )
                            if part
                        )
                        (work_dir / f"prompt_round_{next_round}.txt").write_text(
                            continuation_prompt,
                            encoding="utf-8",
                        )
                        controller_trace["followup_prompt_count"] = int(
                            controller_trace.get("followup_prompt_count", 0)
                        ) + 1
                        controller_trace["controller_action_decisions"] = int(
                            controller_trace.get("controller_action_decisions", 0)
                        ) + 1
                        controller_trace["last_decision"] = (
                            "send_prompt_polling_continuation"
                        )
                        try:
                            turn = await asyncio.to_thread(
                                start_codex_app_server_goal_followup_turn,
                                turn,
                                work_dir=work_dir,
                                prompt=continuation_prompt,
                                model_name=self.model_name,
                                reasoning_effort=self.reasoning_effort,
                                response_timeout_sec=(
                                    self.app_server_response_timeout_sec
                                ),
                                wait_for_completion=False,
                            )
                        except CodexAppServerGoalDriverError as exc:
                            runtime_blocker = (
                                "codex_app_server_goal_followup_turn_failed"
                            )
                            controller_trace["last_decision"] = runtime_blocker
                            controller_trace["runtime_error_type"] = type(exc).__name__
                            controller_trace["raw_error_recorded"] = False
                            break
                        current_round = next_round
                    observe_codex_app_server_goal_turn(turn)
                    await self._serve_bridge_requests(environment, request_dir)
                    result_kind = (
                        "runtime_exception_blocker"
                        if runtime_blocker
                        else ("timeout_blocker" if timeout_blocker else "case_result")
                    )
                    await run_case_scheduler_closeout(result_kind=result_kind)
                    first_blocker = runtime_blocker or timeout_blocker
                    written_compact = write_compact(
                        first_blocker,
                        result_kind=result_kind,
                    )
                finally:
                    turn.terminate()
                context.metadata = {
                    "loopx_agent": self.name(),
                    "completion_source_of_truth": "case_local_active_todo",
                    "bridge_request_count": self._served_request_count,
                    "goal_surface": "app_server",
                    "turn_completed_observed": bool(turn.turn_completed_observed),
                    "first_blocker": runtime_blocker or timeout_blocker,
                    "loopx_mode": self.loopx_mode,
                    "loopx_access_packet_injected": bool(
                        loopx_access_packet
                    ),
                    "prompt_polling_enabled": True,
                    "prompt_polling_rounds_completed": current_round,
                    "prompt_polling_round_timeout_sec": (
                        self.loopx_prompt_polling_round_timeout_sec
                    ),
                    "benchmark_loop_contract": loop_contract,
                    "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                    "loopx_solution_phase_counters": written_compact.get(
                        "loopx_solution_phase_counters", {}
                    ),
                    **case_state_init_compact,
                    **treatment_claim,
                }
                return

            deadline = time.time() + self.goal_timeout_sec
            try:
                while time.time() < deadline:
                    observe_codex_app_server_goal_turn(turn)
                    await self._serve_bridge_requests(environment, request_dir)
                    if turn.turn_completed_observed:
                        await run_case_scheduler_closeout(
                            result_kind="turn_completed"
                        )
                        written_compact = write_compact(
                            result_kind="turn_completed"
                        )
                        turn.terminate()
                        context.metadata = {
                            "loopx_agent": self.name(),
                            "completion_source_of_truth": (
                                "case_local_active_todo"
                                if case_state_init_payload
                                else "codex_turn_completion"
                            ),
                            "bridge_request_count": self._served_request_count,
                            "goal_surface": "app_server",
                            "turn_completed_observed": bool(turn.turn_completed_observed),
                            "loopx_mode": self.loopx_mode,
                            "loopx_access_packet_injected": bool(
                                loopx_access_packet
                            ),
                            "benchmark_loop_contract": loop_contract,
                            "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                            "loopx_solution_phase_counters": written_compact.get(
                                "loopx_solution_phase_counters", {}
                            ),
                            **case_state_init_compact,
                            **treatment_claim,
                        }
                        return
                    await asyncio.sleep(self.poll_interval_sec)
                observe_codex_app_server_goal_turn(turn)
                await run_case_scheduler_closeout(result_kind="timeout_blocker")
                written_compact = write_compact(
                    "harbor_app_server_turn_incomplete_before_timeout",
                    result_kind="timeout_blocker",
                )
            finally:
                turn.terminate()
            context.metadata = {
                "loopx_agent": self.name(),
                "completion_source_of_truth": (
                    "case_local_active_todo"
                    if case_state_init_payload
                    else "codex_turn_completion"
                ),
                "bridge_request_count": self._served_request_count,
                "goal_surface": "app_server",
                "turn_completed_observed": bool(turn.turn_completed_observed),
                "first_blocker": "harbor_host_codex_app_server_goal_timeout",
                "loopx_mode": self.loopx_mode,
                "loopx_access_packet_injected": bool(
                    loopx_access_packet
                ),
                "benchmark_loop_contract": loop_contract,
                "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                "loopx_solution_phase_counters": written_compact.get(
                    "loopx_solution_phase_counters", {}
                ),
                **case_state_init_compact,
                **treatment_claim,
            }
            return

        if self.goal_surface != "tui":
            raise ValueError(f"unsupported goal_surface: {self.goal_surface}")

        command = build_codex_tui_command(
            codex_bin=self.codex_bin,
            model_name=self.model_name,
        )
        shell_command = (
            f"PATH={shlex.quote(str(bin_dir))}:$PATH "
            + " ".join(shlex.quote(part) for part in command)
        )
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                tmux_name,
                "-c",
                str(work_dir),
                shell_command,
            ],
            check=True,
        )
        await asyncio.sleep(self.startup_delay_sec)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)
        await asyncio.sleep(self.startup_delay_sec)
        self._tmux("load-buffer", "-b", f"gh_prompt_{run_id}", str(prompt_path), check=True)
        self._tmux("paste-buffer", "-d", "-b", f"gh_prompt_{run_id}", "-t", tmux_name, check=True)
        await asyncio.sleep(1)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)
        await asyncio.sleep(1)
        self._tmux("send-keys", "-t", tmux_name, "C-m", check=False)

        deadline = time.time() + self.goal_timeout_sec
        while time.time() < deadline:
            await self._serve_bridge_requests(environment, request_dir)
            capture_path.write_text(self._capture(tmux_name), encoding="utf-8")
            await asyncio.sleep(self.poll_interval_sec)

        self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
        context.metadata = {
            "loopx_agent": self.name(),
            "completion_source_of_truth": (
                "case_local_active_todo"
                if case_state_init_payload
                else "codex_turn_completion"
            ),
            "bridge_request_count": self._served_request_count,
            "first_blocker": "harbor_host_codex_goal_timeout",
            "loopx_mode": self.loopx_mode,
            "loopx_access_packet_injected": bool(loopx_access_packet),
            "benchmark_loop_contract": loop_contract,
            "benchmark_case_lifecycle_contract": case_lifecycle_contract,
            **case_state_init_compact,
            **treatment_claim,
        }
