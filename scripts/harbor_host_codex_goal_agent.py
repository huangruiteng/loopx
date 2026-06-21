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
from loopx.benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LOOPX_AGENT_ID,
    BENCHMARK_CASE_LOOPX_CLI_PATH,
    BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE,
    BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE,
    BENCHMARK_CASE_LOOPX_TODO_ID,
    benchmark_case_loopx_event_log_path,
    benchmark_case_loopx_install_payload,
    benchmark_case_lifecycle_contract,
    render_benchmark_case_lifecycle_contract_lines,
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

LONG_RUN_DEFAULT_GOAL_TIMEOUT_SEC = 10800.0


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


BRIDGE_SCRIPT_TEMPLATE = """#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
import time
import uuid

REQUEST_DIR = pathlib.Path("__LOOPX_REQUEST_DIR__")

parser = argparse.ArgumentParser(description="Forward a command into Harbor environment.exec")
parser.add_argument("--cwd", default="")
parser.add_argument("--timeout-sec", type=float, default=600)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()

if not args.command:
    print("missing command", file=sys.stderr)
    raise SystemExit(2)

if args.command[0] == "--":
    args.command = args.command[1:]

command = " ".join(args.command) if len(args.command) > 1 else args.command[0]
request_id = uuid.uuid4().hex
request = REQUEST_DIR / f"{request_id}.request.json"
response = REQUEST_DIR / f"{request_id}.response.json"
tmp = REQUEST_DIR / f"{request_id}.tmp"
tmp.write_text(json.dumps({
    "command": command,
    "cwd": args.cwd,
    "timeout_sec": args.timeout_sec,
}, ensure_ascii=False))
tmp.rename(request)
deadline = time.time() + args.timeout_sec + 30
while time.time() < deadline:
    if response.exists():
        payload = json.loads(response.read_text())
        stdout = payload.get("stdout") or ""
        stderr = payload.get("stderr") or ""
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        raise SystemExit(int(payload.get("return_code") or 0))
    time.sleep(0.5)

print("harbor-env-exec timed out waiting for response", file=sys.stderr)
raise SystemExit(124)
"""


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


def _compact_json_keys(text: str) -> dict[str, Any]:
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
    return {
        "json_parse_ok": True,
        **{key: payload[key] for key in sorted(allowed & set(payload))},
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
    if len(args) >= 2 and args[0] == "--format":
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
    return " ".join([shlex.quote(cli), "--format", "json", *map(shlex.quote, args)])


def _new_case_scheduler_trace(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "harbor_case_loopx_cli_scheduler_trace_v0",
        "enabled": True,
        "route": BENCHMARK_CASE_LOOPX_SCHEDULER_ROUTE,
        "case_goal_id": payload.get("benchmark_case_goal_id") or "",
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
            "stdout_summary": _compact_json_keys(stdout.strip()),
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
    marker_path: Path,
    task_workdir: str = "/app",
    loopx_access_packet: str = "",
) -> str:
    bridge = shlex.quote(str(bridge_command))
    marker_cmd = f"touch {shlex.quote(str(marker_path))}"
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

When and only when the task is complete, run this exact host command so the
harness can observe completion:
{marker_cmd}
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
    experiment_protocol: str = PACKET_ONLY_OBSERVATION_PROTOCOL_ID,
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
    case_lifecycle = benchmark_case_lifecycle_contract(
        benchmark_id=benchmark_id,
        case_id=case_id,
        arm_id=arm_id,
        max_rounds=max_rounds,
    )
    case_goal_id = str(case_lifecycle["benchmark_case_goal_id"])
    case_event_log_path = benchmark_case_loopx_event_log_path(case_goal_id)

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
        f"loopx_product_path_primary_route: {BENCHMARK_CASE_LOOPX_PRODUCT_PATH_PRIMARY_ROUTE}",
        "loopx_prompt_driven_loop_required: true",
        "loopx_scheduler_route_supported_for_smoke_or_fallback: true",
        "loopx_case_local_cli_installed_before_agent: true",
        f"loopx_case_cli_path: {BENCHMARK_CASE_LOOPX_CLI_PATH}",
        f"loopx_case_rollout_event_log_path: {case_event_log_path}",
        f"loopx_case_agent_id: {BENCHMARK_CASE_LOOPX_AGENT_ID}",
        f"loopx_case_todo_id: {BENCHMARK_CASE_LOOPX_TODO_ID}",
        f"loopx_treatment_evidence_tier: {claim['loopx_treatment_evidence_tier']}",
        f"strict_loopx_treatment_claim_allowed: {str(claim['strict_loopx_treatment_claim_allowed']).lower()}",
        f"loopx_treatment_claim_blocker: {claim['loopx_treatment_claim_blocker']}",
    ]
    lines.extend(render_loop_contract_packet_lines(loop_contract))
    lines.extend(render_benchmark_case_lifecycle_contract_lines(case_lifecycle))
    if cli_enabled:
        lines.extend(
            [
                "primary_loopx_cli_surface: task_environment_case_local_cli",
                f"loopx_case_command_quota_should_run: {BENCHMARK_CASE_LOOPX_CLI_PATH} --format json quota should-run --goal-id {shlex.quote(case_goal_id)} --agent-id {BENCHMARK_CASE_LOOPX_AGENT_ID}",
                f"loopx_case_command_claim_todo: {BENCHMARK_CASE_LOOPX_CLI_PATH} --format json todo claim --goal-id {shlex.quote(case_goal_id)} --todo-id {BENCHMARK_CASE_LOOPX_TODO_ID} --claimed-by {BENCHMARK_CASE_LOOPX_AGENT_ID}",
                f"loopx_case_command_status: {BENCHMARK_CASE_LOOPX_CLI_PATH} --format json status --goal-id {shlex.quote(case_goal_id)} --limit 5",
                f"loopx_case_command_refresh_state: {BENCHMARK_CASE_LOOPX_CLI_PATH} --format json refresh-state --goal-id {shlex.quote(case_goal_id)}",
                f"loopx_case_command_spend_quota: {BENCHMARK_CASE_LOOPX_CLI_PATH} --format json quota spend-slot --goal-id {shlex.quote(case_goal_id)}",
                "before_planning_call_loopx_case_quota_should_run_once: true",
                "before_planning_claim_loopx_case_todo_once: true",
                "before_final_marker_review_loopx_case_status_or_history_once: true",
                f"loopx_global_command_check_optional_context: {base} check --scan-path {scan_path_arg}",
                f"loopx_global_command_status_optional_context: {base} status --limit 5",
                f"loopx_global_command_history_optional_context: {base} history --goal-id {goal_id_arg} --limit 5",
                "loopx_case_cli_calls_are_part_of_the_treatment_flow: true",
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
    """Build the public-safe case-local GH install/state/todo payload."""

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
        "loopx_case_rollout_event_log_path": (
            payload.get("case_rollout_event_log_path") or ""
        ),
        "loopx_case_agent_id": payload.get("case_agent_id") or "",
        "loopx_case_todo_id": payload.get("case_todo_id") or "",
        "loopx_case_todo_seeded": bool(payload.get("case_todo_seeded")),
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
        loopx_experiment_protocol: str = PACKET_ONLY_OBSERVATION_PROTOCOL_ID,
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

        bridge = bin_dir / "harbor-env-exec"
        marker = work_dir / "done.marker"
        prompt_path = work_dir / "prompt.txt"
        capture_path = work_dir / "tmux_capture.txt"
        tmux_name = f"gh_harbor_goal_{run_id}"
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
                    "completion_marker_observed": False,
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
                case_todo_id = str(case_state_init_payload.get("case_todo_id") or "")
                pre_agent_specs = [
                    ("case_cli_check", ["check"]),
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
                    (
                        "case_todo_claim_before_agent",
                        [
                            "todo",
                            "claim",
                            "--goal-id",
                            case_goal_id,
                            "--todo-id",
                            case_todo_id,
                            "--claimed-by",
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
                        "completion_marker_observed": False,
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
            marker_path=marker,
            task_workdir=self.task_workdir,
            loopx_access_packet=loopx_access_packet,
        )
        prompt_path.write_text(prompt, encoding="utf-8")

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
                    "completion_marker_observed": False,
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

            def write_compact(first_blocker: str = "") -> None:
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
                        "completion_marker_observed": marker.exists(),
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

            async def run_case_scheduler_round(
                *,
                round_index: int,
                stage: str,
            ) -> None:
                if not case_scheduler_trace or not case_state_init_payload:
                    return
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
                await _collect_case_rollout_event_counts(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    cwd=self.task_workdir,
                )

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
                await _collect_case_rollout_event_counts(
                    environment,
                    payload=case_state_init_payload,
                    trace=case_scheduler_trace,
                    cwd=self.task_workdir,
                )

            if prompt_polling_enabled:
                deadline = time.time() + self.goal_timeout_sec
                current_round = 1
                completion_marker_count = 0
                timeout_blocker = ""
                try:
                    while current_round <= self.loopx_prompt_polling_rounds:
                        marker_seen_this_round = False
                        round_deadline = min(
                            deadline,
                            time.time() + self.loopx_prompt_polling_round_timeout_sec,
                        )
                        while time.time() < round_deadline:
                            observe_codex_app_server_goal_turn(turn)
                            await self._serve_bridge_requests(environment, request_dir)
                            if marker.exists():
                                completion_marker_count += 1
                                marker_seen_this_round = True
                                break
                            if turn.turn_completed_observed:
                                break
                            await asyncio.sleep(self.poll_interval_sec)
                        controller_trace["max_round_observed"] = max(
                            int(controller_trace.get("max_round_observed", -1)),
                            current_round,
                        )
                        controller_trace["completion_marker_observed_count"] = (
                            completion_marker_count
                        )
                        controller_trace["round_timeout_sec"] = (
                            self.loopx_prompt_polling_round_timeout_sec
                        )
                        await run_case_scheduler_round(
                            round_index=current_round,
                            stage="post_turn",
                        )
                        if time.time() >= round_deadline and not (
                            marker_seen_this_round or turn.turn_completed_observed
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
                        if marker.exists():
                            marker.unlink()
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
                        turn = await asyncio.to_thread(
                            start_codex_app_server_goal_followup_turn,
                            turn,
                            work_dir=work_dir,
                            prompt=continuation_prompt,
                            model_name=self.model_name,
                            reasoning_effort=self.reasoning_effort,
                            response_timeout_sec=self.app_server_response_timeout_sec,
                            wait_for_completion=False,
                        )
                        current_round = next_round
                    observe_codex_app_server_goal_turn(turn)
                    await self._serve_bridge_requests(environment, request_dir)
                    await run_case_scheduler_closeout(
                        result_kind=(
                            "timeout_blocker" if timeout_blocker else "case_result"
                        )
                    )
                    first_blocker = timeout_blocker
                    write_compact(first_blocker)
                finally:
                    turn.terminate()
                context.metadata = {
                    "loopx_agent": self.name(),
                    "completion_marker_observed": bool(completion_marker_count),
                    "bridge_request_count": self._served_request_count,
                    "goal_surface": "app_server",
                    "turn_completed_observed": bool(turn.turn_completed_observed),
                    "first_blocker": timeout_blocker,
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
                    **case_state_init_compact,
                    **treatment_claim,
                }
                return

            deadline = time.time() + self.goal_timeout_sec
            try:
                while time.time() < deadline:
                    observe_codex_app_server_goal_turn(turn)
                    await self._serve_bridge_requests(environment, request_dir)
                    if marker.exists():
                        observe_codex_app_server_goal_turn(
                            turn,
                            timeout_sec=min(2.0, self.poll_interval_sec),
                        )
                        await run_case_scheduler_closeout(
                            result_kind="completion_marker"
                        )
                        write_compact()
                        turn.terminate()
                        context.metadata = {
                            "loopx_agent": self.name(),
                            "completion_marker_observed": True,
                            "bridge_request_count": self._served_request_count,
                            "goal_surface": "app_server",
                            "turn_completed_observed": bool(turn.turn_completed_observed),
                            "loopx_mode": self.loopx_mode,
                            "loopx_access_packet_injected": bool(
                                loopx_access_packet
                            ),
                            "benchmark_loop_contract": loop_contract,
                            "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                            **case_state_init_compact,
                            **treatment_claim,
                        }
                        return
                    await asyncio.sleep(self.poll_interval_sec)
                observe_codex_app_server_goal_turn(turn)
                await run_case_scheduler_closeout(result_kind="timeout_blocker")
                write_compact("harbor_completion_marker_missing_before_timeout")
            finally:
                turn.terminate()
            context.metadata = {
                "loopx_agent": self.name(),
                "completion_marker_observed": False,
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
        self._tmux("send-keys", "-t", tmux_name, "/goal", "C-m", check=False)
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
            if marker.exists():
                capture_path.write_text(self._capture(tmux_name), encoding="utf-8")
                self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
                context.metadata = {
                    "loopx_agent": self.name(),
                    "completion_marker_observed": True,
                    "bridge_request_count": self._served_request_count,
                    "loopx_mode": self.loopx_mode,
                    "loopx_access_packet_injected": bool(
                        loopx_access_packet
                    ),
                    "benchmark_loop_contract": loop_contract,
                    "benchmark_case_lifecycle_contract": case_lifecycle_contract,
                    **case_state_init_compact,
                    **treatment_claim,
                }
                return
            capture_path.write_text(self._capture(tmux_name), encoding="utf-8")
            await asyncio.sleep(self.poll_interval_sec)

        self._tmux("send-keys", "-t", tmux_name, "C-c", check=False)
        context.metadata = {
            "loopx_agent": self.name(),
            "completion_marker_observed": False,
            "bridge_request_count": self._served_request_count,
            "first_blocker": "harbor_host_codex_goal_timeout",
            "loopx_mode": self.loopx_mode,
            "loopx_access_packet_injected": bool(loopx_access_packet),
            "benchmark_loop_contract": loop_contract,
            "benchmark_case_lifecycle_contract": case_lifecycle_contract,
            **case_state_init_compact,
            **treatment_claim,
        }
