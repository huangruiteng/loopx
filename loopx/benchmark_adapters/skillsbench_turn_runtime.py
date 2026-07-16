"""Run one SkillsBench agent prompt through a real LoopX Turn transaction.

The scored workspace and its case-local LoopX registry live behind the existing
command/file bridge.  The agent CLI runs on the host.  This module keeps those
planes separate: it reads a typed Turn plan from the scored workspace, executes
the host callback, validates a task postcondition through the bridge, and lets
the Turn executor own writeback and the single quota spend.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..benchmark_case_state import benchmark_case_loopx_command_prefix
from ..control_plane.turn_driver import run_loopx_turn_once
from .skillsbench_acp_failure_policy import (
    RECOVERABLE_CODEX_TURN_FAILURE_PREFIX,
    recoverable_codex_turn_failure_message,
)


SKILLSBENCH_LOOPX_TURN_TRACE_SCHEMA_VERSION = (
    "skillsbench_loopx_turn_agent_cli_trace_v0"
)
SKILLSBENCH_BRIDGE_OPERATION_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_operation_response_v0"
)

AgentPromptRunner = Callable[[str], str]
PublicTraceWriter = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class SkillsBenchTurnRuntimeConfig:
    bridge_command: str
    validation_command: str
    goal_id: str
    agent_id: str
    runtime_root: Path
    bridge_timeout_seconds: float = 30.0
    agent_timeout_seconds: float = 7200.0
    case_cli_path: str = "/app/.local/bin/loopx"
    case_registry_path: str = "/app/.loopx/registry.json"
    case_runtime_root: str = "/app/.loopx/runtime"


class SkillsBenchTurnBridgeError(RuntimeError):
    """A compact failure raised at the host/scored-workspace boundary."""


class SkillsBenchTurnAgentFailure(RuntimeError):
    """A recoverable host Agent CLI failure that must not commit a Turn."""


class SkillsBenchTurnBridge:
    def __init__(self, config: SkillsBenchTurnRuntimeConfig):
        self._config = config
        self.meaningful_operation_count = 0

    def exec(self, command: str, *, meaningful: bool = False) -> dict[str, Any]:
        request = {
            "operation": "exec",
            "cwd": "/app",
            "command": command,
            "timeout_sec": max(1.0, self._config.bridge_timeout_seconds),
        }
        started = time.monotonic()
        try:
            proc = subprocess.run(
                self._config.bridge_command,
                input=json.dumps(request, separators=(",", ":")),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                timeout=max(2.0, self._config.bridge_timeout_seconds + 5.0),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SkillsBenchTurnBridgeError(
                "bridge operation did not complete"
            ) from exc
        if proc.returncode != 0:
            raise SkillsBenchTurnBridgeError("bridge command returned non-zero")
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise SkillsBenchTurnBridgeError("bridge response was not JSON") from exc
        if not isinstance(payload, dict):
            raise SkillsBenchTurnBridgeError("bridge response was not an object")
        if payload.get("schema_version") != SKILLSBENCH_BRIDGE_OPERATION_SCHEMA_VERSION:
            raise SkillsBenchTurnBridgeError("bridge operation schema was unsupported")
        if payload.get("ok") is not True or payload.get("exit_code") != 0:
            raise SkillsBenchTurnBridgeError("scored-workspace command failed")
        if payload.get("stdout_truncated") is True:
            raise SkillsBenchTurnBridgeError("scored-workspace stdout was truncated")
        if meaningful:
            self.meaningful_operation_count += 1
        return {
            "ok": True,
            "stdout": str(payload.get("stdout") or ""),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }

    def loopx_json(self, command: str) -> dict[str, Any]:
        result = self.exec(command)
        try:
            payload = json.loads(result["stdout"])
        except json.JSONDecodeError as exc:
            raise SkillsBenchTurnBridgeError("LoopX CLI output was not JSON") from exc
        if not isinstance(payload, dict):
            raise SkillsBenchTurnBridgeError("LoopX CLI output was not an object")
        return payload


def _case_cli_prefix(config: SkillsBenchTurnRuntimeConfig) -> str:
    return benchmark_case_loopx_command_prefix(
        case_cli_path=config.case_cli_path,
        case_registry_path=config.case_registry_path,
        case_runtime_root=config.case_runtime_root,
    )


def _turn_plan(
    bridge: SkillsBenchTurnBridge,
    config: SkillsBenchTurnRuntimeConfig,
) -> dict[str, Any]:
    prefix = _case_cli_prefix(config)
    command = (
        f"{prefix} turn plan "
        f"--goal-id {shlex.quote(config.goal_id)} "
        f"--agent-id {shlex.quote(config.agent_id)} "
        "--host generic-cli --execution-mode isolated-headless "
        "--include-transaction-detail --scan-root /app --limit 5"
    )
    payload = bridge.loopx_json(command)
    if payload.get("ok") is not True:
        raise SkillsBenchTurnBridgeError("LoopX Turn plan was not executable")
    return payload


def _host_result(request: Mapping[str, Any], response: str) -> dict[str, Any]:
    turn_key = str(request.get("turn_key") or "")
    recoverable_failure = response.startswith(RECOVERABLE_CODEX_TURN_FAILURE_PREFIX)
    if recoverable_failure:
        raise SkillsBenchTurnAgentFailure("agent CLI execution requires repair")
    return {
        "schema_version": "loopx_turn_result_v0",
        "turn_key": turn_key,
        "result_kind": "validated_progress",
        "completed_phases": ["host_execute", "typed_result"],
        "classification": "skillsbench_loopx_turn_agent_cli_progress",
        "recommended_action": "continue from the case-local LoopX frontier if work remains",
        "next_action": "use the next typed Turn rather than an ungoverned prompt poll",
        "delivery_batch_scale": "single_surface",
        "delivery_outcome": "outcome_progress",
        "vision_unchanged_reason": "the benchmark case objective is unchanged",
        "summary": "agent CLI completed one bounded scored-workspace turn",
    }


def _callback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok") is True,
        "appended": payload.get("appended") is True,
        "classification": payload.get("classification"),
        "generated_at": payload.get("generated_at"),
        "slots": payload.get("slots"),
        "reason": payload.get("reason") or payload.get("error"),
    }


def run_skillsbench_loopx_turn(
    *,
    prompt: str,
    agent_runner: AgentPromptRunner,
    config: SkillsBenchTurnRuntimeConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute one real Turn and return its receipt plus compact validation."""

    if not config.bridge_command:
        raise ValueError("SkillsBench LoopX Turn requires a scored-workspace bridge")
    if not config.validation_command:
        raise ValueError(
            "SkillsBench LoopX Turn requires an independent validation command"
        )
    bridge = SkillsBenchTurnBridge(config)
    plan = _turn_plan(bridge, config)
    prefix = _case_cli_prefix(config)

    def host_runner(request: Mapping[str, Any]) -> dict[str, Any]:
        return _host_result(request, agent_runner(prompt))

    def validator(
        _plan: Mapping[str, Any],
        _result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            bridge.exec(config.validation_command, meaningful=True)
        except SkillsBenchTurnBridgeError:
            return {
                "status": "failed",
                "validator_kind": "skillsbench_scored_workspace_command",
                "summary": "independent scored-workspace validation returned non-zero",
                "recovery_kind": "repair_required",
                "exit_code": 1,
            }
        return {
            "status": "passed",
            "validator_kind": "skillsbench_scored_workspace_command",
            "summary": "independent scored-workspace validation passed",
            "exit_code": 0,
        }

    def writeback(result: dict[str, Any]) -> dict[str, Any]:
        command = (
            f"{prefix} refresh-state "
            f"--goal-id {shlex.quote(config.goal_id)} "
            f"--classification {shlex.quote(str(result['classification']))} "
            f"--recommended-action {shlex.quote(str(result['recommended_action']))} "
            f"--next-action {shlex.quote(str(result['next_action']))} "
            f"--delivery-batch-scale {shlex.quote(str(result['delivery_batch_scale']))} "
            f"--delivery-outcome {shlex.quote(str(result['delivery_outcome']))} "
            f"--agent-id {shlex.quote(config.agent_id)} "
            "--progress-scope goal "
            f"--vision-unchanged-reason {shlex.quote(str(result['vision_unchanged_reason']))} "
            "--no-global-sync"
        )
        return _callback_payload(bridge.loopx_json(command))

    def spend() -> dict[str, Any]:
        command = (
            f"{prefix} quota spend-slot "
            f"--goal-id {shlex.quote(config.goal_id)} --slots 1 "
            "--source adapter --execute "
            f"--agent-id {shlex.quote(config.agent_id)}"
        )
        return _callback_payload(bridge.loopx_json(command))

    def scheduler(_spend_payload: dict[str, Any]) -> dict[str, Any]:
        command = (
            f"{prefix} quota should-run "
            f"--goal-id {shlex.quote(config.goal_id)} "
            f"--agent-id {shlex.quote(config.agent_id)} "
            "--host-surface generic_cli "
            "--scheduler-owner outer_controller "
            "--execution-mode isolated_headless"
        )
        payload = bridge.loopx_json(command)
        hint = payload.get("scheduler_hint")
        hint = hint if isinstance(hint, dict) else {}
        phase = hint.get("execution_phase")
        if not isinstance(phase, dict):
            return {
                "disposition": "contract_error",
                "completed": False,
                "acknowledged": False,
                "apply_needed": False,
            }
        return dict(phase)

    execution = run_loopx_turn_once(
        plan,
        host_runner=host_runner,
        project=Path("/app"),
        runtime_root=config.runtime_root,
        goal_id=config.goal_id,
        timeout_seconds=config.agent_timeout_seconds,
        execute=True,
        retry_failed=True,
        task_validator=validator,
        writeback=writeback,
        spend=spend,
        scheduler=scheduler,
    )
    scored_validation = {
        "schema_version": "skillsbench_scored_workspace_validation_v0",
        "status": (
            "passed"
            if isinstance(execution.get("validation"), dict)
            and execution["validation"].get("status") == "passed"
            else "failed"
        ),
        "independent": True,
        "validator_kind": "skillsbench_scored_workspace_command",
        "oracle_feedback_used": False,
        "meaningful_operation_count": bridge.meaningful_operation_count,
        "raw_validator_output_recorded": False,
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
    }
    return execution, scored_validation


def build_skillsbench_loopx_turn_trace(
    *,
    route: str,
    benchmark_id: str,
    task_id: str,
    execution: Mapping[str, Any],
    scored_workspace_validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the only public trace emitted by the Turn runtime."""

    return {
        "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
        "ok": execution.get("status") == "committed",
        "route": route,
        "trace_kind": "loopx_turn_execution",
        "benchmark_id": benchmark_id,
        "task_id": task_id,
        "loopx_turn_execution": dict(execution),
        "scored_workspace_validation": dict(scored_workspace_validation),
        "official_feedback_blinded": True,
        "reward_feedback_forwarded": False,
        "boundary": {
            "raw_command_recorded": False,
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "credential_values_recorded": False,
            "host_paths_recorded": False,
            "remote_paths_recorded": False,
            "upload_performed": False,
            "submit_performed": False,
        },
    }


def run_skillsbench_loopx_turn_relay(
    *,
    prompt: str,
    session_id: str,
    relay_config: Any,
    agent_runner: AgentPromptRunner,
    trace_writer: PublicTraceWriter,
) -> str:
    """Adapt one relay prompt to the case-local Turn runtime."""

    bridge_command = str(relay_config.remote_command_file_bridge_command or "")
    validation_command = str(relay_config.loopx_turn_validation_command or "")
    trace_root = str(relay_config.worker_public_trace_dir or "")
    if not bridge_command:
        raise RuntimeError("LoopX Turn requires the scored-workspace bridge")
    if not validation_command:
        raise RuntimeError("LoopX Turn requires an independent validation command")
    if not trace_root:
        raise RuntimeError("LoopX Turn requires a compact public trace directory")
    runtime_session = (
        "".join(
            char if char.isalnum() or char in "_.:-" else "_" for char in session_id
        )[:120]
        or "session"
    )
    execution, scored_validation = run_skillsbench_loopx_turn(
        prompt=prompt,
        agent_runner=agent_runner,
        config=SkillsBenchTurnRuntimeConfig(
            bridge_command=bridge_command,
            validation_command=validation_command,
            goal_id=relay_config.loopx_case_goal_id,
            agent_id=relay_config.loopx_case_agent_id,
            runtime_root=Path(trace_root).parent
            / ".loopx-turn-runtime"
            / runtime_session,
            bridge_timeout_seconds=max(
                1.0, relay_config.remote_command_file_bridge_timeout_sec
            ),
            agent_timeout_seconds=max(1.0, float(relay_config.timeout_sec)),
            case_cli_path=relay_config.loopx_case_cli_path,
            case_registry_path=relay_config.loopx_case_registry_path,
            case_runtime_root=relay_config.loopx_case_runtime_root,
        ),
    )
    trace_writer(
        build_skillsbench_loopx_turn_trace(
            route=relay_config.route,
            benchmark_id=relay_config.dataset,
            task_id=relay_config.task_id,
            execution=execution,
            scored_workspace_validation=scored_validation,
        )
    )
    if execution.get("status") != "committed":
        return recoverable_codex_turn_failure_message(
            "loopx_turn_" + str(execution.get("status") or "failed")
        )
    return "loopx turn committed after independent scored-workspace validation"
