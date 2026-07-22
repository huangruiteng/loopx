"""Run one SkillsBench agent prompt through a real LoopX Turn transaction.

The scored workspace and its case-local LoopX registry live behind the existing
command/file bridge.  The agent CLI runs on the host.  This module keeps those
planes separate: it reads a typed Turn plan from the scored workspace, executes
the host callback, validates a task postcondition through the bridge, and lets
the Turn executor own writeback and the single quota spend.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Union

from ..benchmark_case_state import benchmark_case_loopx_command_prefix
from ..control_plane.turn_driver import run_loopx_turn_once
from .skillsbench_acp_failure_policy import (
    RECOVERABLE_CODEX_TURN_FAILURE_PREFIX,
    recoverable_codex_turn_failure_message,
)
from .skillsbench_turn_route import LOOPX_TURN_PROOF_CHECKS


SKILLSBENCH_LOOPX_TURN_TRACE_SCHEMA_VERSION = (
    "skillsbench_loopx_turn_agent_cli_trace_v0"
)
SKILLSBENCH_BRIDGE_OPERATION_SCHEMA_VERSION = (
    "skillsbench_remote_command_file_bridge_operation_response_v0"
)
SKILLSBENCH_TURN_BASELINE_ENV = "LOOPX_TURN_BASELINE_FILE"
SKILLSBENCH_TURN_SEQUENCE_BASELINE_ENV = "LOOPX_TURN_SEQUENCE_BASELINE_FILE"
SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICIES = frozenset(
    {"validator", "fixed-n", "stability"}
)


@dataclass(frozen=True)
class SkillsBenchTurnAgentResult:
    response_text: str
    progress_evidence: Mapping[str, Any]


AgentPromptRunner = Callable[[str], Union[str, SkillsBenchTurnAgentResult]]
PublicTraceWriter = Callable[[dict[str, Any]], None]
TurnObserver = Callable[[dict[str, Any], dict[str, Any]], None]

SKILLSBENCH_LOOPX_TURN_CONTINUATION_PROMPT = """\
Continue the same task in this same Codex session. Inspect the current workspace
state, perform the next bounded task-facing step, and stop. Do not use or request
official verifier, reward, pass/fail, hidden-test, or gold-answer feedback.
"""
SKILLSBENCH_LOOPX_TURN_STABILITY_PROMPT = """\
Review the current solution against the visible task requirements and inspect the
durable workspace state. Repair concrete defects and run bounded task-derived
checks when useful. If no repair is needed, stop without manufacturing a change.
Do not use or request official verifier, reward, pass/fail, hidden-test, or
gold-answer feedback.
"""


@dataclass(frozen=True)
class SkillsBenchTurnRuntimeConfig:
    bridge_command: str
    validation_command: str
    goal_id: str
    agent_id: str
    runtime_root: Path
    bridge_timeout_seconds: float = 30.0
    agent_timeout_seconds: float = 7200.0
    max_turns: int = 1
    progress_exit_code: int = 10
    terminal_policy: str = "validator"
    sequence_baseline_path: str = ""
    case_cli_path: str = "/app/.local/bin/loopx"
    case_registry_path: str = "/app/.loopx/registry.json"
    case_runtime_root: str = "/app/.loopx/runtime"


class SkillsBenchTurnBridgeError(RuntimeError):
    """A compact failure raised at the host/scored-workspace boundary."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "bridge_operation",
        category: str = "bridge_operation_failed",
        exit_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.category = category
        self.exit_code = exit_code


class SkillsBenchTurnAgentFailure(RuntimeError):
    """A recoverable host Agent CLI failure that must not commit a Turn."""


def _loopx_cli_failure_category(stdout: Any, stderr: Any) -> str:
    try:
        payload = json.loads(str(stdout or ""))
    except json.JSONDecodeError:
        payload = {}
    error = " ".join(
        f"{payload.get('error') if isinstance(payload, dict) else ''} {stderr or ''}".lower().split()
    )
    classifiers = (
        (r"/app/\.local/bin/loopx.*not found", "case_loopx_cli_missing"),
        (r"no module named loopx", "case_loopx_source_missing"),
        (r"loopx cli requires python", "case_python_runtime_missing"),
        (r"python 3\.11\+ is required", "unsupported_python_runtime"),
        (r"permission denied", "scored_workspace_permission_denied"),
        (r"no such file|not found", "scored_workspace_path_missing"),
        (r"unknown agent|agent .*not registered", "case_agent_not_registered"),
        (r"goal .*not found|no matching goal", "case_goal_not_found"),
        (r"public boundary|private material", "case_public_boundary_rejected"),
        (r"operator inbox|lark", "case_operator_inbox_projection_failed"),
    )
    for pattern, category in classifiers:
        if re.search(pattern, error):
            return category
    return "loopx_cli_command_failed"


class SkillsBenchTurnBridge:
    def __init__(self, config: SkillsBenchTurnRuntimeConfig):
        self._config = config
        self.meaningful_operation_count = 0

    def exec(
        self,
        command: str,
        *,
        meaningful: bool = False,
        allow_nonzero: bool = False,
    ) -> dict[str, Any]:
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
            raise SkillsBenchTurnBridgeError(
                "bridge command returned non-zero",
                exit_code=proc.returncode,
            )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise SkillsBenchTurnBridgeError("bridge response was not JSON") from exc
        if not isinstance(payload, dict):
            raise SkillsBenchTurnBridgeError("bridge response was not an object")
        if payload.get("schema_version") != SKILLSBENCH_BRIDGE_OPERATION_SCHEMA_VERSION:
            raise SkillsBenchTurnBridgeError("bridge operation schema was unsupported")
        exit_code = payload.get("exit_code")
        if payload.get("ok") is not True or exit_code != 0:
            if (
                allow_nonzero
                and isinstance(exit_code, int)
                and not isinstance(exit_code, bool)
                and exit_code != 0
            ):
                if meaningful:
                    self.meaningful_operation_count += 1
                return {
                    "ok": False,
                    "exit_code": exit_code,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                }
            raise SkillsBenchTurnBridgeError(
                "scored-workspace command failed",
                category=_loopx_cli_failure_category(
                    payload.get("stdout"), payload.get("stderr")
                ),
                exit_code=(
                    exit_code
                    if isinstance(exit_code, int) and not isinstance(exit_code, bool)
                    else None
                ),
            )
        if payload.get("stdout_truncated") is True:
            raise SkillsBenchTurnBridgeError("scored-workspace stdout was truncated")
        if meaningful:
            self.meaningful_operation_count += 1
        return {
            "ok": True,
            "exit_code": 0,
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
    *,
    turn_instance_id: str | None = None,
) -> dict[str, Any]:
    prefix = _case_cli_prefix(config)
    command = (
        f"{prefix} turn plan "
        f"--goal-id {shlex.quote(config.goal_id)} "
        f"--agent-id {shlex.quote(config.agent_id)} "
        "--host generic-cli --execution-mode isolated-headless "
        "--include-transaction-detail --scan-root /app --limit 5"
    )
    if turn_instance_id:
        command += f" --turn-instance-id {shlex.quote(turn_instance_id)}"
    try:
        payload = bridge.loopx_json(command)
    except SkillsBenchTurnBridgeError as exc:
        raise SkillsBenchTurnBridgeError(
            str(exc),
            stage="turn_plan",
            category=exc.category,
            exit_code=exc.exit_code,
        ) from exc
    if payload.get("ok") is not True:
        raise SkillsBenchTurnBridgeError(
            "LoopX Turn plan was not executable",
            stage="turn_plan",
            category="loopx_turn_plan_not_executable",
        )
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


def _agent_result(value: str | SkillsBenchTurnAgentResult) -> tuple[str, dict[str, Any]]:
    if isinstance(value, SkillsBenchTurnAgentResult):
        return value.response_text, dict(value.progress_evidence)
    return str(value), {}


def _verified_bridge_content_progress(value: Mapping[str, Any]) -> bool:
    count = value.get("successful_task_file_change_count")
    return bool(
        value.get("schema_version")
        == "skillsbench_bridge_task_progress_receipt_v0"
        and value.get("status") == "verified_task_content_change"
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count > 0
        and value.get("raw_material_recorded") is False
    )


def _turn_baseline_path(request: Mapping[str, Any]) -> str:
    turn_key = str(request.get("turn_key") or "")
    digest = hashlib.sha256(turn_key.encode("utf-8")).hexdigest()[:24]
    return f"/tmp/loopx-turn-agent-baseline-{digest}"


def _callback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok") is True,
        "appended": payload.get("appended") is True,
        "classification": payload.get("classification"),
        "generated_at": payload.get("generated_at"),
        "slots": payload.get("slots"),
        "reason": payload.get("reason") or payload.get("error"),
    }


def _validation_baseline(
    bridge: SkillsBenchTurnBridge,
    config: SkillsBenchTurnRuntimeConfig,
) -> dict[str, Any]:
    """Observe whether the task postcondition is satisfied before agent work."""

    try:
        result = bridge.exec(
            _completion_validation_command(config), allow_nonzero=True
        )
    except SkillsBenchTurnBridgeError as exc:
        raise SkillsBenchTurnBridgeError(
            str(exc),
            stage="validation_baseline",
            category=exc.category,
            exit_code=exc.exit_code,
        ) from exc
    exit_code = result.get("exit_code")
    if result.get("ok") is True:
        status = "already_satisfied"
    elif exit_code == config.progress_exit_code:
        status = "progress_validated"
    else:
        status = "unsatisfied"
    return {
        "schema_version": "skillsbench_validation_baseline_v0",
        "status": status,
        "postcondition_kind": "task_declared_independent_command",
        "exit_code": exit_code,
        "raw_command_recorded": False,
        "raw_output_recorded": False,
    }


def _completion_validation_command(config: SkillsBenchTurnRuntimeConfig) -> str:
    if not config.sequence_baseline_path:
        return config.validation_command
    return (
        f"env {SKILLSBENCH_TURN_SEQUENCE_BASELINE_ENV}="
        f"{shlex.quote(config.sequence_baseline_path)} sh -c "
        f"{shlex.quote(config.validation_command)}"
    )


def run_skillsbench_loopx_turn(
    *,
    prompt: str,
    agent_runner: AgentPromptRunner,
    config: SkillsBenchTurnRuntimeConfig,
    turn_instance_id: str | None = None,
    sequence_step_kind: str = "validator",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute one real Turn and return its receipt plus compact validation."""

    if not config.bridge_command:
        raise ValueError("SkillsBench LoopX Turn requires a scored-workspace bridge")
    if not config.validation_command:
        raise ValueError(
            "SkillsBench LoopX Turn requires an independent validation command"
        )
    if not 1 <= config.progress_exit_code <= 255:
        raise ValueError("SkillsBench progress exit code must be between 1 and 255")
    if config.terminal_policy not in SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICIES:
        raise ValueError(
            "SkillsBench terminal policy must be validator, fixed-n, or stability"
        )
    if config.terminal_policy == "stability" and not config.sequence_baseline_path:
        raise ValueError("SkillsBench stability policy requires a sequence baseline")
    if sequence_step_kind not in {"validator", "progress", "terminal"}:
        raise ValueError("SkillsBench sequence step kind was unsupported")
    bridge = SkillsBenchTurnBridge(config)
    if config.terminal_policy == "stability":
        sequence_baseline_path = shlex.quote(config.sequence_baseline_path)
        sequence_baseline_dir = shlex.quote(
            str(Path(config.sequence_baseline_path).parent)
        )
        bridge.exec(
            f"umask 077; mkdir -p {sequence_baseline_dir}; "
            f"test -e {sequence_baseline_path} || : > {sequence_baseline_path}"
        )
    plan = (
        _turn_plan(bridge, config, turn_instance_id=turn_instance_id)
        if turn_instance_id is not None
        else _turn_plan(bridge, config)
    )
    validation_baseline = _validation_baseline(bridge, config)
    prefix = _case_cli_prefix(config)
    baseline_path = ""
    agent_progress_evidence: dict[str, Any] = {}
    stability_validation_evidence: dict[str, bool] = {}

    def host_runner(request: Mapping[str, Any]) -> dict[str, Any]:
        nonlocal agent_progress_evidence, baseline_path
        baseline_path = _turn_baseline_path(request)
        bridge.exec(f"umask 077; : > {shlex.quote(baseline_path)}")
        response, agent_progress_evidence = _agent_result(agent_runner(prompt))
        return _host_result(request, response)

    def validator(
        _plan: Mapping[str, Any],
        _result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        nonlocal stability_validation_evidence
        if not baseline_path:
            return {
                "status": "failed",
                "validator_kind": "skillsbench_scored_workspace_command",
                "summary": "independent scored-workspace baseline was unavailable",
                "recovery_kind": "repair_required",
                "exit_code": 1,
            }
        validation_command = (
            f"env {SKILLSBENCH_TURN_BASELINE_ENV}="
            f"{shlex.quote(baseline_path)} sh -c "
            f"{shlex.quote(config.validation_command)}"
        )
        try:
            validation_result = bridge.exec(
                validation_command,
                meaningful=True,
                allow_nonzero=True,
            )
        except SkillsBenchTurnBridgeError:
            return {
                "status": "failed",
                "validator_kind": "skillsbench_scored_workspace_command",
                "summary": "independent scored-workspace validation returned non-zero",
                "recovery_kind": "repair_required",
                "exit_code": 1,
            }
        exit_code = validation_result.get("exit_code")
        if config.terminal_policy == "stability":
            try:
                completion_result = bridge.exec(
                    _completion_validation_command(config),
                    meaningful=True,
                    allow_nonzero=True,
                )
            except SkillsBenchTurnBridgeError:
                completion_result = {"ok": False, "exit_code": 1}
            completion_satisfied = completion_result.get("ok") is True
            progress_detected = bool(
                exit_code == config.progress_exit_code
                or _verified_bridge_content_progress(agent_progress_evidence)
            )
            stability_validation_evidence = {
                "stability_progress_detected": progress_detected,
                "stability_completion_satisfied": completion_satisfied,
                "stability_completion_checked": True,
            }
            if sequence_step_kind == "terminal" and completion_satisfied:
                return {
                    "status": "passed",
                    "validator_kind": "skillsbench_stability_postcondition",
                    "summary": "independent completion postcondition passed at the Turn limit",
                    "exit_code": 0,
                }
            if progress_detected:
                return {
                    "status": "progress",
                    "validator_kind": "skillsbench_stability_postcondition",
                    "summary": "independent task progress requires another review Turn",
                    "exit_code": config.progress_exit_code,
                }
            if completion_satisfied:
                return {
                    "status": "passed",
                    "validator_kind": "skillsbench_stability_postcondition",
                    "summary": "no new repair was needed and the completion postcondition passed",
                    "exit_code": 0,
                }
            return {
                "status": "failed",
                "validator_kind": "skillsbench_stability_postcondition",
                "summary": "neither independent progress nor completion was validated",
                "recovery_kind": "repair_required",
                "exit_code": completion_result.get("exit_code"),
            }
        validation_succeeded = exit_code in {0, config.progress_exit_code}
        if not validation_succeeded:
            if _verified_bridge_content_progress(agent_progress_evidence):
                effective_step_kind = sequence_step_kind
                if effective_step_kind == "validator":
                    effective_step_kind = "progress"
                if effective_step_kind == "terminal":
                    return {
                        "status": "passed",
                        "validator_kind": "skillsbench_bridge_content_progress",
                        "summary": "independent task-facing content change validated progress",
                        "exit_code": 0,
                    }
                return {
                    "status": "progress",
                    "validator_kind": "skillsbench_bridge_content_progress",
                    "summary": "independent task-facing content change validated progress",
                    "exit_code": config.progress_exit_code,
                }
            return {
                "status": "failed",
                "validator_kind": "skillsbench_scored_workspace_command",
                "summary": "independent scored-workspace validation returned non-zero",
                "recovery_kind": "repair_required",
                "exit_code": exit_code,
            }
        effective_step_kind = sequence_step_kind
        if effective_step_kind == "validator":
            effective_step_kind = (
                "progress" if exit_code == config.progress_exit_code else "terminal"
            )
        if effective_step_kind == "progress":
            return {
                "status": "progress",
                "validator_kind": "skillsbench_scored_workspace_command",
                "summary": "independent scored-workspace progress validation passed",
                "exit_code": config.progress_exit_code,
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
            "--runtime-profile outer_controller"
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

    try:
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
    finally:
        if baseline_path:
            try:
                bridge.exec(f"rm -f {shlex.quote(baseline_path)}")
            except SkillsBenchTurnBridgeError:
                pass
    transaction_validation = execution.get("validation")
    transaction_validation = (
        transaction_validation if isinstance(transaction_validation, dict) else {}
    )
    validation_status = transaction_validation.get("status")
    validation_passed = validation_status in {"passed", "progress"}
    terminal_complete = validation_status == "passed"
    validated_progress = validation_status in {"passed", "progress"}
    bridge_content_progress = _verified_bridge_content_progress(agent_progress_evidence)
    write_count = agent_progress_evidence.get("successful_task_file_write_count")
    if not isinstance(write_count, int) or isinstance(write_count, bool):
        write_count = 0
    change_count = agent_progress_evidence.get("successful_task_file_change_count")
    if not isinstance(change_count, int) or isinstance(change_count, bool):
        change_count = 0
    scored_validation = {
        "schema_version": "skillsbench_scored_workspace_validation_v0",
        "status": ("passed" if validation_passed else "failed"),
        "independent": True,
        "validator_kind": str(
            transaction_validation.get("validator_kind")
            or "skillsbench_scored_workspace_command"
        ),
        "pre_agent_postcondition_checked": True,
        "pre_agent_postcondition_status": validation_baseline["status"],
        "post_agent_postcondition_status": (
            "satisfied"
            if terminal_complete
            else "progress_validated"
            if validated_progress
            else "unsatisfied"
        ),
        "validated_progress": validated_progress,
        "terminal_complete": terminal_complete,
        "terminal_policy": config.terminal_policy,
        "sequence_baseline_configured": bool(config.sequence_baseline_path),
        "stability_progress_detected": bool(
            stability_validation_evidence.get("stability_progress_detected") is True
        ),
        "stability_completion_checked": bool(
            stability_validation_evidence.get("stability_completion_checked") is True
        ),
        "stability_completion_satisfied": bool(
            stability_validation_evidence.get("stability_completion_satisfied") is True
        ),
        "baseline_contract": (
            "task_declared_independent_postcondition_or_verified_content_change"
        ),
        "progress_evidence_kind": (
            "verified_task_content_change"
            if bridge_content_progress
            else "scored_workspace_command"
        ),
        "successful_task_file_write_count": max(0, write_count),
        "successful_task_file_change_count": max(0, change_count),
        "oracle_feedback_used": False,
        "meaningful_operation_count": bridge.meaningful_operation_count,
        "raw_validator_output_recorded": False,
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
    }
    return execution, scored_validation


def run_skillsbench_loopx_turn_sequence(
    *,
    prompt: str,
    agent_runner: AgentPromptRunner,
    config: SkillsBenchTurnRuntimeConfig,
    turn_observer: TurnObserver | None = None,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    """Run up to N independently validated Turns within one total time budget."""

    if config.max_turns < 1:
        raise ValueError("SkillsBench LoopX Turn max_turns must be at least 1")
    if config.terminal_policy not in SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICIES:
        raise ValueError(
            "SkillsBench terminal policy must be validator, fixed-n, or stability"
        )
    sequence_id = uuid.uuid4().hex[:16]
    turn_sequence_ref = (
        "sequence:" + hashlib.sha256(sequence_id.encode("utf-8")).hexdigest()[:16]
    )
    sequence_baseline_path = (
        f"{config.case_runtime_root.rstrip('/')}"
        f"/benchmark-turn-sequences/{sequence_id}.baseline"
    )
    sequence_config = replace(
        config,
        sequence_baseline_path=(
            sequence_baseline_path if config.terminal_policy == "stability" else ""
        ),
    )
    deadline = time.monotonic() + max(1.0, config.agent_timeout_seconds)
    records: list[tuple[dict[str, Any], dict[str, Any]]] = []
    stop_reason = "max_turns_reached"
    for turn_index in range(1, config.max_turns + 1):
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            stop_reason = "time_budget_exhausted"
            break
        if turn_index == 1:
            turn_prompt = prompt
        elif config.terminal_policy == "stability":
            turn_prompt = SKILLSBENCH_LOOPX_TURN_STABILITY_PROMPT
        else:
            turn_prompt = SKILLSBENCH_LOOPX_TURN_CONTINUATION_PROMPT
        sequence_step_kind = "validator"
        if config.terminal_policy == "fixed-n":
            sequence_step_kind = (
                "terminal" if turn_index == config.max_turns else "progress"
            )
        elif (
            config.terminal_policy == "stability"
            and turn_index == config.max_turns
        ):
            sequence_step_kind = "terminal"
        execution, validation = run_skillsbench_loopx_turn(
            prompt=turn_prompt,
            agent_runner=agent_runner,
            config=replace(
                sequence_config, agent_timeout_seconds=remaining_seconds
            ),
            turn_instance_id=f"{sequence_id}-turn-{turn_index:03d}",
            sequence_step_kind=sequence_step_kind,
        )
        validation["turn_index"] = turn_index
        validation["turn_sequence_ref"] = turn_sequence_ref
        records.append((execution, validation))
        if execution.get("status") != "committed":
            stop_reason = "turn_not_committed"
        elif validation.get("terminal_complete") is True:
            stop_reason = "terminal_complete"
        elif validation.get("validated_progress") is not True:
            stop_reason = "no_validated_progress"
        elif turn_index < config.max_turns:
            stop_reason = "continue"
        else:
            stop_reason = "max_turns_reached"
        validation["sequence_stop_reason"] = stop_reason
        if turn_observer is not None:
            turn_observer(execution, validation)
        if stop_reason != "continue":
            break
    return records, {
        "schema_version": "skillsbench_loopx_turn_sequence_v0",
        "status": stop_reason,
        "turn_count": len(records),
        "max_turns": config.max_turns,
        "turn_sequence_ref": turn_sequence_ref,
        "terminal_policy": config.terminal_policy,
        "terminal_complete": stop_reason == "terminal_complete",
        "official_feedback_blinded": True,
        "reward_feedback_forwarded": False,
    }


def build_skillsbench_benchmark_runner_readiness(
    *,
    execution: Mapping[str, Any],
    scored_workspace_validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Reduce a Turn outcome to a compact, public-safe runner capability receipt."""

    pre_agent_unsatisfied = scored_workspace_validation.get(
        "pre_agent_postcondition_status"
    ) in {"unsatisfied", "progress_validated"}
    stability_terminal_review = bool(
        scored_workspace_validation.get("terminal_policy") == "stability"
        and scored_workspace_validation.get("terminal_complete") is True
        and scored_workspace_validation.get("stability_completion_checked") is True
        and scored_workspace_validation.get("stability_completion_satisfied") is True
    )
    checks = {
        "turn_transaction_committed": execution.get("status") == "committed",
        "independent_scored_workspace_validation_passed": bool(
            scored_workspace_validation.get("status") == "passed"
            and scored_workspace_validation.get("independent") is True
        ),
        "pre_agent_postcondition_checked": (
            scored_workspace_validation.get("pre_agent_postcondition_checked") is True
        ),
        "pre_agent_postcondition_eligible": (
            pre_agent_unsatisfied or stability_terminal_review
        ),
        "post_agent_postcondition_satisfied": (
            scored_workspace_validation.get("post_agent_postcondition_status")
            == "satisfied"
        ),
        "post_agent_postcondition_validated": (
            scored_workspace_validation.get("post_agent_postcondition_status")
            in {"progress_validated", "satisfied"}
        ),
        "official_feedback_blinded": (
            scored_workspace_validation.get("oracle_feedback_used") is False
        ),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    turn_proven = all(checks[name] for name in LOOPX_TURN_PROOF_CHECKS)
    receipt = {
        "schema_version": "skillsbench_benchmark_runner_readiness_v0",
        "capability": "benchmark_runner",
        "status": "ready" if not blockers else "blocked",
        "ready": not blockers,
        "turn_proven": turn_proven,
        "checks": checks,
        "blocker_codes": blockers,
        "evidence_kind": "committed_turn_with_independent_postcondition",
        "raw_task_text_recorded": False,
        "raw_validator_output_recorded": False,
        "raw_verifier_output_recorded": False,
        "raw_trajectory_recorded": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
    }
    turn_sequence_ref = scored_workspace_validation.get("turn_sequence_ref")
    if isinstance(turn_sequence_ref, str) and re.fullmatch(
        r"sequence:[0-9a-f]{16}", turn_sequence_ref
    ):
        receipt["turn_sequence_ref"] = turn_sequence_ref
    turn_index = scored_workspace_validation.get("turn_index")
    if isinstance(turn_index, int) and not isinstance(turn_index, bool):
        receipt["turn_index"] = max(1, turn_index)
    return receipt


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
        "benchmark_runner_readiness": build_skillsbench_benchmark_runner_readiness(
            execution=execution,
            scored_workspace_validation=scored_workspace_validation,
        ),
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


def build_skillsbench_loopx_turn_failure_trace(
    *,
    route: str,
    benchmark_id: str,
    task_id: str,
    error: SkillsBenchTurnBridgeError,
) -> dict[str, Any]:
    """Build a public-safe receipt when Turn fails before execution exists."""

    failure: dict[str, Any] = {
        "category": error.category,
    }
    if error.exit_code is not None:
        failure["exit_code"] = error.exit_code
    execution = {
        "schema_version": "loopx_turn_execution_v0",
        "mode": "run_once",
        "status": "failed",
        "execution_mode": "isolated-headless",
        "result_kind": "repair_required",
        "quota_slot_spend_count": 0,
        "failure": failure,
        "receipt": {
            "status": "failed",
            "result_kind": "repair_required",
            "failed_phase": error.stage,
            "next_phase": error.stage,
            "completed_phases": [],
        },
        "effects": {
            "host_invoked": False,
            "state_written": False,
            "quota_spent": False,
            "scheduler_acknowledged": False,
        },
    }
    validation = {
        "schema_version": "skillsbench_scored_workspace_validation_v0",
        "status": "not_attempted",
        "independent": True,
        "validator_kind": "skillsbench_scored_workspace_command",
        "pre_agent_postcondition_checked": error.stage == "validation_baseline",
        "pre_agent_postcondition_status": (
            "check_failed" if error.stage == "validation_baseline" else "not_attempted"
        ),
        "post_agent_postcondition_status": "not_attempted",
        "baseline_contract": "task_declared_independent_postcondition",
        "oracle_feedback_used": False,
        "meaningful_operation_count": 0,
        "raw_validator_output_recorded": False,
        "raw_task_text_recorded": False,
        "raw_verifier_output_recorded": False,
    }
    return build_skillsbench_loopx_turn_trace(
        route=route,
        benchmark_id=benchmark_id,
        task_id=task_id,
        execution=execution,
        scored_workspace_validation=validation,
    )


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
    max_turns = int(getattr(relay_config, "loopx_turn_max_turns", 1))
    progress_exit_code = int(getattr(relay_config, "loopx_turn_progress_exit_code", 10))
    terminal_policy = str(
        getattr(relay_config, "loopx_turn_terminal_policy", "validator")
    )
    if max_turns < 1:
        raise RuntimeError("LoopX Turn max Turns must be at least one")
    if not 1 <= progress_exit_code <= 255:
        raise RuntimeError("LoopX Turn progress exit code must be between 1 and 255")
    if terminal_policy not in SKILLSBENCH_LOOPX_TURN_TERMINAL_POLICIES:
        raise RuntimeError(
            "LoopX Turn terminal policy must be validator, fixed-n, or stability"
        )
    runtime_session = (
        "".join(
            char if char.isalnum() or char in "_.:-" else "_" for char in session_id
        )[:120]
        or "session"
    )
    try:
        turn_records, sequence = run_skillsbench_loopx_turn_sequence(
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
                max_turns=max_turns,
                progress_exit_code=progress_exit_code,
                terminal_policy=terminal_policy,
                case_cli_path=relay_config.loopx_case_cli_path,
                case_registry_path=relay_config.loopx_case_registry_path,
                case_runtime_root=relay_config.loopx_case_runtime_root,
            ),
            turn_observer=lambda execution, scored_validation: trace_writer(
                build_skillsbench_loopx_turn_trace(
                    route=relay_config.route,
                    benchmark_id=relay_config.dataset,
                    task_id=relay_config.task_id,
                    execution=execution,
                    scored_workspace_validation=scored_validation,
                )
            ),
        )
    except SkillsBenchTurnBridgeError as exc:
        trace_writer(
            build_skillsbench_loopx_turn_failure_trace(
                route=relay_config.route,
                benchmark_id=relay_config.dataset,
                task_id=relay_config.task_id,
                error=exc,
            )
        )
        return recoverable_codex_turn_failure_message(
            f"loopx_turn_{exc.stage}_{exc.category}"
        )
    if not turn_records:
        return recoverable_codex_turn_failure_message(
            "loopx_turn_" + str(sequence.get("status") or "failed")
        )
    execution, _scored_validation = turn_records[-1]
    if execution.get("status") != "committed":
        return recoverable_codex_turn_failure_message(
            "loopx_turn_" + str(execution.get("status") or "failed")
        )
    return (
        "loopx turn sequence stopped after "
        f"{len(turn_records)} committed turn(s): {sequence['status']}"
    )
