"""One bounded LoopX Turn host execution with resumable local receipts."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...authority import validate_public_safe_text
from ..goals.goal_vision import normalize_goal_vision_packet
from ..work_items.delivery_batch_scale import require_delivery_batch_scale
from ..work_items.delivery_outcome import require_delivery_outcome
from .driver import selected_turn_todo
from .lease import TurnLeaseController
from .transaction import (
    LOOPX_TURN_EXECUTION_SCHEMA_VERSION,
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    TRANSACTION_PHASES,
    LoopXTurnResultKind,
    TurnEffectEnvelope,
    build_loopx_turn_transaction_plan,
    require_loopx_turn_completion_outcome,
    validate_loopx_turn_receipt,
)

LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION = "loopx_turn_host_request_v0"
LOOPX_TURN_JOURNAL_SCHEMA_VERSION = "loopx_turn_journal_v0"
LOOPX_TURN_TASK_VALIDATION_SCHEMA_VERSION = "loopx_turn_task_validation_v0"
HOST_RESULT_MAX_BYTES = 12_000
HOST_ARG_MAX_COUNT = 32
HOST_ARG_MAX_CHARS = 1_024
HOST_AGENT_VISION_JSON_MAX_CHARS = 3_200
HOST_PATH_DELTA_MODES = {"", "unchanged", "material_replan"}
HOST_RESULT_TEXT_LIMITS = (
    ("classification", 120),
    ("recommended_action", 1_200),
    ("next_action", 1_200),
    ("vision_unchanged_reason", 240),
    ("summary", 400),
)
TURN_KEY_RE = re.compile(r"^sha256:(?P<digest>[0-9a-f]{64})$")

MATERIAL_HOST_RESULT_KINDS = {
    LoopXTurnResultKind.VALIDATED_PROGRESS,
    LoopXTurnResultKind.VALIDATED_COMPLETION,
    LoopXTurnResultKind.REPAIR_REQUIRED,
    LoopXTurnResultKind.REPLAN_REQUIRED,
}
STOP_HOST_RESULT_KINDS = {
    LoopXTurnResultKind.USER_ACTION_REQUIRED,
    LoopXTurnResultKind.WAIT,
}
HOST_RESULT_FIELDS = {
    "schema_version",
    "turn_key",
    "result_kind",
    "completed_phases",
    "classification",
    "recommended_action",
    "next_action",
    "delivery_batch_scale",
    "delivery_outcome",
    "vision_unchanged_reason",
    "path_delta_mode",
    "agent_vision_json",
    "summary",
}

Writeback = Callable[[TurnEffectEnvelope, dict[str, Any]], dict[str, Any]]
CompletionWriteback = Callable[
    [TurnEffectEnvelope, dict[str, Any]],
    dict[str, Any],
]
Spend = Callable[[TurnEffectEnvelope], dict[str, Any]]
Scheduler = Callable[
    [TurnEffectEnvelope, dict[str, Any]],
    dict[str, Any],
]
HostRunner = Callable[[Mapping[str, Any]], dict[str, Any]]
FaultInjector = Callable[[str], None]
TaskValidator = Callable[
    [Mapping[str, Any], Mapping[str, Any]],
    Mapping[str, Any],
]


class BuiltInHostError(RuntimeError):
    """A public-safe built-in host failure classification."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _normalize_argv(value: Sequence[str], *, label: str) -> list[str]:
    argv = [str(item) for item in value]
    if not argv:
        raise ValueError(f"{label} command must contain at least one argv item")
    if len(argv) > HOST_ARG_MAX_COUNT:
        raise ValueError(f"{label} command exceeds {HOST_ARG_MAX_COUNT} argv items")
    for item in argv:
        if not item or "\x00" in item or len(item) > HOST_ARG_MAX_CHARS:
            raise ValueError(
                f"{label} command contains an empty, NUL, or oversized argv item"
            )
    return argv


def normalize_host_argv(value: Sequence[str]) -> list[str]:
    return _normalize_argv(value, label="host")


def _normalize_task_validator_argv(value: Sequence[str]) -> list[str]:
    return _normalize_argv(value, label="task validator")


def build_loopx_turn_host_request(plan: Mapping[str, Any]) -> dict[str, Any]:
    transaction = plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    turn_key = str(transaction.get("turn_key") or "")
    if not TURN_KEY_RE.fullmatch(turn_key):
        raise ValueError("LoopX Turn plan has no valid transaction turn_key")
    route = plan.get("route") if isinstance(plan.get("route"), dict) else {}
    if route.get("would_invoke_host") is not True:
        raise ValueError("LoopX Turn route is not host executable")
    request = {
        "schema_version": LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION,
        "turn_key": turn_key,
        "route": route.get("kind"),
        "session": plan.get("session"),
        "turn_envelope": plan.get("turn_envelope"),
        "result_contract": {
            "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
            "completed_phases": list(TRANSACTION_PHASES[:2]),
            "stdout": "one public-safe JSON object",
        },
    }
    child_operations = plan.get("child_operations")
    if isinstance(child_operations, list) and child_operations:
        request["child_operations"] = child_operations
    return request


def _bounded_public_text(
    result: Mapping[str, Any],
    field: str,
    *,
    limit: int,
    required: bool,
    errors: list[str],
) -> str | None:
    text = str(result.get(field) or "").strip()
    if required and not text:
        errors.append(f"{field} is required")
        return None
    if not text:
        return None
    if len(text) > limit:
        errors.append(f"{field} exceeds {limit} characters")
        return None
    try:
        validate_public_safe_text(f"host_result.{field}", text)
    except ValueError as exc:
        errors.append(str(exc))
        return None
    return text


def _normalize_host_path_delta(
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    unchanged_reason: str,
    errors: list[str],
) -> tuple[str, dict[str, Any] | None]:
    path_delta_mode = str(result.get("path_delta_mode") or "").strip()
    raw_agent_vision = result.get("agent_vision_json")
    if raw_agent_vision is None:
        agent_vision_json = ""
    elif isinstance(raw_agent_vision, str):
        agent_vision_json = raw_agent_vision.strip()
    else:
        agent_vision_json = ""
        errors.append("agent_vision_json must be a JSON string")

    # Older generic hosts only supplied an unchanged reason. Keep that
    # contract valid while making new hosts classify material path changes.
    if not path_delta_mode:
        path_delta_mode = "material_replan" if agent_vision_json else "unchanged"
    if path_delta_mode not in HOST_PATH_DELTA_MODES - {""}:
        errors.append("path_delta_mode must be unchanged or material_replan")

    agent_vision: dict[str, Any] | None = None
    if agent_vision_json:
        if len(agent_vision_json) > HOST_AGENT_VISION_JSON_MAX_CHARS:
            errors.append(
                "agent_vision_json exceeds "
                f"{HOST_AGENT_VISION_JSON_MAX_CHARS} characters"
            )
        else:
            try:
                packet = json.loads(agent_vision_json)
                if not isinstance(packet, dict):
                    raise TypeError("agent_vision_json must decode to a JSON object")
                envelope = (
                    plan.get("turn_envelope")
                    if isinstance(plan.get("turn_envelope"), dict)
                    else {}
                )
                agent_vision = normalize_goal_vision_packet(
                    packet,
                    goal_id=str(envelope.get("goal_id") or ""),
                    agent_id=str(envelope.get("agent_id") or "") or None,
                )
            except (json.JSONDecodeError, ValueError) as exc:
                errors.append(f"invalid agent_vision_json: {exc}")

    if path_delta_mode == "material_replan":
        if agent_vision is None:
            errors.append(
                "material_replan requires agent_vision_json with goal_path_delta_v0"
            )
        elif not isinstance(agent_vision.get("path_delta"), dict):
            errors.append(
                "material_replan agent_vision_json requires goal_path_delta_v0"
            )
        elif agent_vision["path_delta"].get("outcome") != "replan":
            errors.append(
                "material_replan goal_path_delta_v0 outcome must be replan"
            )
        if unchanged_reason:
            errors.append(
                "material_replan cannot also declare vision_unchanged_reason"
            )
    elif path_delta_mode == "unchanged":
        if agent_vision is not None:
            errors.append("unchanged path_delta_mode cannot include agent_vision_json")
        if not unchanged_reason:
            errors.append("unchanged path_delta_mode requires vision_unchanged_reason")

    return path_delta_mode, agent_vision


def validate_loopx_turn_host_result(
    plan: Mapping[str, Any],
    value: Mapping[str, Any],
    *,
    completion_writeback_configured: bool = False,
) -> dict[str, Any]:
    result = dict(value)
    errors: list[str] = []
    unknown = sorted(set(result) - HOST_RESULT_FIELDS)
    if unknown:
        errors.append("unsupported host result fields: " + ", ".join(unknown))
    if result.get("schema_version") != LOOPX_TURN_RESULT_SCHEMA_VERSION:
        errors.append("unsupported host result schema_version")

    transaction = plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    turn_key = str(transaction.get("turn_key") or "")
    if not turn_key or str(result.get("turn_key") or "") != turn_key:
        errors.append("host result turn_key does not match the transaction plan")

    try:
        kind = LoopXTurnResultKind(str(result.get("result_kind") or ""))
    except ValueError:
        kind = None
        errors.append("unsupported host result kind")
    if (
        kind is LoopXTurnResultKind.VALIDATED_COMPLETION
        and not completion_writeback_configured
    ):
        errors.append("validated_completion requires a todo lifecycle adapter")
    if (
        kind not in MATERIAL_HOST_RESULT_KINDS | STOP_HOST_RESULT_KINDS
        and kind is not LoopXTurnResultKind.VALIDATED_COMPLETION
    ):
        errors.append("host result kind is not accepted by run-once")

    phases = result.get("completed_phases")
    if phases != list(TRANSACTION_PHASES[:2]):
        errors.append("host result completed_phases must be host_execute, typed_result")

    material = kind in MATERIAL_HOST_RESULT_KINDS
    normalized = {
        "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
        "turn_key": turn_key,
        "result_kind": kind.value if kind else None,
        "completed_phases": list(TRANSACTION_PHASES[:2]),
    }
    for field, limit in HOST_RESULT_TEXT_LIMITS:
        text = _bounded_public_text(
            result,
            field,
            limit=limit,
            required=material and field not in {"summary", "vision_unchanged_reason"},
            errors=errors,
        )
        if text:
            normalized[field] = text
    if material:
        try:
            normalized["delivery_batch_scale"] = require_delivery_batch_scale(
                result.get("delivery_batch_scale")
            ).value
        except ValueError as exc:
            errors.append(str(exc))
        try:
            normalized["delivery_outcome"] = require_delivery_outcome(
                result.get("delivery_outcome")
            ).value
        except ValueError as exc:
            errors.append(str(exc))

        unchanged_reason = str(normalized.get("vision_unchanged_reason") or "")
        path_delta_mode, agent_vision = _normalize_host_path_delta(
            plan,
            result,
            unchanged_reason=unchanged_reason,
            errors=errors,
        )
        if (
            path_delta_mode == "material_replan"
            and kind is not LoopXTurnResultKind.REPLAN_REQUIRED
        ):
            errors.append(
                "material_replan path_delta_mode requires result_kind replan_required"
            )

        normalized["path_delta_mode"] = path_delta_mode
        if agent_vision is not None:
            normalized["agent_vision"] = agent_vision
    elif str(result.get("path_delta_mode") or "").strip() or str(
        result.get("agent_vision_json") or ""
    ).strip():
        errors.append(
            "wait and user_action_required results cannot declare a path delta"
        )
    return {
        "ok": not errors,
        "result": normalized,
        "errors": errors,
    }


def _task_validation_receipt(
    *,
    status: str,
    validator_kind: str,
    summary: str,
    recovery_kind: str | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if status not in {
        "passed",
        "progress",
        "failed",
        "inconclusive",
        "unavailable",
        "not_required",
    }:
        errors.append("unsupported task validation status")
    if not validator_kind or len(validator_kind) > 80:
        errors.append("task validator kind must contain at most 80 characters")
    if not summary or len(summary) > 240:
        errors.append("task validation summary must contain at most 240 characters")
    for field, text in (("validator_kind", validator_kind), ("summary", summary)):
        if text:
            try:
                validate_public_safe_text(f"task_validation.{field}", text)
            except ValueError as exc:
                errors.append(str(exc))
    if recovery_kind is not None and recovery_kind not in {
        LoopXTurnResultKind.REPAIR_REQUIRED.value,
        LoopXTurnResultKind.REPLAN_REQUIRED.value,
    }:
        errors.append("task validation recovery_kind must be repair_required or replan_required")
    if status in {"failed", "inconclusive", "unavailable"} and recovery_kind is None:
        errors.append("failed task validation requires a typed recovery_kind")
    if status in {"passed", "progress", "not_required"} and recovery_kind is not None:
        errors.append("successful task validation cannot declare recovery_kind")
    if exit_code is not None and (not isinstance(exit_code, int) or exit_code < 0):
        errors.append("task validation exit_code must be a non-negative integer")
    if status == "passed" and exit_code not in {None, 0}:
        errors.append("passed task validation cannot declare a non-zero exit_code")
    if status == "progress" and exit_code in {None, 0}:
        errors.append("progress task validation requires a non-zero exit_code")
    effective_status = status if not errors else "inconclusive"
    effective_recovery_kind = recovery_kind
    if errors and effective_recovery_kind is None:
        effective_recovery_kind = LoopXTurnResultKind.REPAIR_REQUIRED.value
    return {
        "ok": not errors and status in {"passed", "progress", "not_required"},
        "schema_version": LOOPX_TURN_TASK_VALIDATION_SCHEMA_VERSION,
        "status": effective_status,
        "validator_kind": validator_kind or "invalid",
        "summary": summary or "task validation receipt is invalid",
        "recovery_kind": effective_recovery_kind,
        "exit_code": exit_code,
        "errors": errors,
    }


def _run_task_validator(
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    validator: TaskValidator | None,
) -> dict[str, Any]:
    if validator is None:
        return _task_validation_receipt(
            status="unavailable",
            validator_kind="none",
            summary="independent task validator is required for material host results",
            recovery_kind=LoopXTurnResultKind.REPAIR_REQUIRED.value,
        )
    try:
        value = validator(plan, result)
    except Exception:  # noqa: BLE001 - validator plugins fail closed at this boundary
        return _task_validation_receipt(
            status="inconclusive",
            validator_kind="callback",
            summary="independent task validator did not produce a receipt",
            recovery_kind=LoopXTurnResultKind.REPAIR_REQUIRED.value,
        )
    if not isinstance(value, Mapping):
        return _task_validation_receipt(
            status="inconclusive",
            validator_kind="callback",
            summary="independent task validator returned an invalid receipt",
            recovery_kind=LoopXTurnResultKind.REPAIR_REQUIRED.value,
        )
    unknown = sorted(
        set(value)
        - {
            "status",
            "validator_kind",
            "summary",
            "recovery_kind",
            "exit_code",
        }
    )
    if unknown:
        return _task_validation_receipt(
            status="inconclusive",
            validator_kind="callback",
            summary="independent task validator returned unsupported receipt fields",
            recovery_kind=LoopXTurnResultKind.REPAIR_REQUIRED.value,
        )
    status = str(value.get("status") or "")
    if status == "not_required":
        return _task_validation_receipt(
            status="inconclusive",
            validator_kind="callback",
            summary="material host results cannot skip independent task validation",
            recovery_kind=LoopXTurnResultKind.REPAIR_REQUIRED.value,
        )
    exit_code_value = value.get("exit_code")
    if exit_code_value is not None and (
        not isinstance(exit_code_value, int) or isinstance(exit_code_value, bool)
    ):
        return _task_validation_receipt(
            status="inconclusive",
            validator_kind="callback",
            summary="independent task validator returned an invalid exit code",
            recovery_kind=LoopXTurnResultKind.REPAIR_REQUIRED.value,
        )
    return _task_validation_receipt(
        status=status,
        validator_kind=str(value.get("validator_kind") or ""),
        summary=str(value.get("summary") or ""),
        recovery_kind=(
            str(value["recovery_kind"])
            if value.get("recovery_kind") is not None
            else None
        ),
        exit_code=exit_code_value,
    )


def build_loopx_turn_command_validator(
    argv: Sequence[str],
    *,
    project: Path,
    timeout_seconds: float,
    failure_recovery_kind: str = LoopXTurnResultKind.REPAIR_REQUIRED.value,
) -> TaskValidator:
    """Build a trusted argv-only postcondition validator for one Turn host workspace."""

    normalized = _normalize_task_validator_argv(argv)
    if failure_recovery_kind not in {
        LoopXTurnResultKind.REPAIR_REQUIRED.value,
        LoopXTurnResultKind.REPLAN_REQUIRED.value,
    }:
        raise ValueError(
            "task validator failure recovery must be repair_required or replan_required"
        )

    def validate(
        _plan: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            completed = subprocess.run(
                normalized,
                cwd=project,
                input=json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(1.0, timeout_seconds),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {
                "status": "inconclusive",
                "validator_kind": "command",
                "summary": "independent task validation command could not complete",
                "recovery_kind": LoopXTurnResultKind.REPAIR_REQUIRED.value,
            }
        if completed.returncode != 0:
            return {
                "status": "failed",
                "validator_kind": "command",
                "summary": "independent task validation command returned non-zero",
                "recovery_kind": failure_recovery_kind,
                "exit_code": completed.returncode,
            }
        return {
            "status": "passed",
            "validator_kind": "command",
            "summary": "independent task validation command passed",
            "exit_code": 0,
        }

    return validate


def load_loopx_turn_plan_from_journal(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any]:
    from .fenced_runtime import load_loopx_turn_plan_from_fenced_journal

    return load_loopx_turn_plan_from_fenced_journal(
        runtime_root,
        goal_id=goal_id,
        turn_key=turn_key,
    )


def _receipt(
    plan: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    completed_phases: Sequence[str],
    failure_kind: LoopXTurnResultKind | None = None,
    failed_phase: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
        "turn_key": result.get("turn_key"),
        "result_kind": (
            failure_kind.value if failure_kind else result.get("result_kind")
        ),
        "completed_phases": list(completed_phases),
        "failed_phase": failed_phase,
    }
    return validate_loopx_turn_receipt(
        plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {},
        payload,
    )


def _host_failure(
    plan: Mapping[str, Any],
    *,
    kind: LoopXTurnResultKind,
    completed_phases: Sequence[str],
    failed_phase: str,
    reason: str,
) -> dict[str, Any]:
    transaction = plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    result = {"turn_key": transaction.get("turn_key"), "result_kind": kind.value}
    return {
        "ok": False,
        "reason": reason,
        "receipt": _receipt(
            plan,
            result,
            completed_phases=completed_phases,
            failure_kind=kind,
            failed_phase=failed_phase,
        ),
    }


def _run_host(
    request: Mapping[str, Any],
    *,
    argv: Sequence[str],
    project: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(argv),
            cwd=project,
            input=json.dumps(request, ensure_ascii=False, separators=(",", ":")),
            text=True,
            capture_output=True,
            timeout=max(1.0, timeout_seconds),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": type(exc).__name__, "returncode": None}
    if completed.returncode != 0:
        return {
            "ok": False,
            "reason": "host command returned non-zero",
            "returncode": completed.returncode,
            "stderr_chars": len(completed.stderr),
        }
    encoded = completed.stdout.encode("utf-8")
    if len(encoded) > HOST_RESULT_MAX_BYTES:
        return {"ok": False, "reason": "host stdout exceeded the result budget", "returncode": 0}
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "reason": "host stdout is not one JSON value", "returncode": 0}
    if not isinstance(value, dict):
        return {"ok": False, "reason": "host stdout must be one JSON object", "returncode": 0}
    return {"ok": True, "value": value, "returncode": 0}


def _run_host_runner(
    request: Mapping[str, Any],
    *,
    runner: HostRunner,
) -> dict[str, Any]:
    try:
        value = runner(request)
    except BuiltInHostError as exc:
        return {"ok": False, "reason": exc.reason, "returncode": None}
    except Exception as exc:  # noqa: BLE001 - host adapters fail closed at boundary
        return {"ok": False, "reason": type(exc).__name__, "returncode": None}
    if not isinstance(value, dict):
        return {"ok": False, "reason": "built-in host result must be one JSON object"}
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > HOST_RESULT_MAX_BYTES:
        return {"ok": False, "reason": "built-in host result exceeded the result budget"}
    return {"ok": True, "value": value, "returncode": 0}


def _compact_callback(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: payload.get(key)
        for key in ("ok", "appended", "classification", "generated_at", "slots", "reason")
        if key in payload
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _execution_payload(
    plan: Mapping[str, Any],
    journal: Mapping[str, Any],
    *,
    execute: bool,
    replayed: bool,
    effects: Mapping[str, bool],
) -> dict[str, Any]:
    transaction = plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    turn_key = str(transaction.get("turn_key") or "")
    planned_host = plan.get("host") if isinstance(plan.get("host"), dict) else {}
    writeback = _mapping(journal.get("writeback"))
    todo_completion = _mapping(writeback.get("completion"))
    quota_spent = effects.get("quota_spent") is True or "quota_spend" in list(
        journal.get("completed_phases") or []
    )
    return {
        "ok": journal.get("status") in {
            "preview",
            "committed",
            "stopped",
            "scheduler_action_required",
        },
        "schema_version": LOOPX_TURN_EXECUTION_SCHEMA_VERSION,
        "mode": "run_once",
        "dry_run": not execute,
        "replayed": replayed,
        "resume_turn_key": turn_key,
        "journal_ref": f"turn:{turn_key.removeprefix('sha256:')[:16]}",
        "status": journal.get("status"),
        "execution_mode": planned_host.get("execution_mode"),
        "host": journal.get("host"),
        "result_kind": journal.get("result_kind"),
        "validation": journal.get("task_validation"),
        "receipt": journal.get("receipt"),
        "scheduler": journal.get("scheduler"),
        "effects": dict(effects),
        "quota_slot_spend_count": 1 if quota_spent else 0,
        **(
            {"settlement_result": journal["settlement_result"]}
            if isinstance(journal.get("settlement_result"), Mapping)
            else {}
        ),
        **({"todo_completion": todo_completion} if todo_completion else {}),
        **({"reason": journal.get("reason")} if journal.get("reason") else {}),
    }


def _completion_writeback_outcome(
    payload: Mapping[str, Any],
    *,
    plan: Mapping[str, Any],
) -> dict[str, Any] | None:
    completion = payload.get("completion")
    if not isinstance(completion, Mapping):
        return None
    envelope = plan.get("turn_envelope")
    selected_todo = selected_turn_todo(envelope) if isinstance(envelope, Mapping) else {}
    expected_todo_id = str(selected_todo.get("todo_id") or "")
    try:
        return require_loopx_turn_completion_outcome(
            completion,
            expected_todo_id=expected_todo_id,
        )
    except ValueError:
        return None


def _ensure_turn_settlement_plan(
    plan: Mapping[str, Any],
    transaction_plan: dict[str, Any],
) -> None:
    """Upgrade a legacy transaction plan with a typed settlement plan.

    Turn plans produced by older LoopX releases (for example plans read from a
    scored-workspace image) do not carry ``settlement_plan``. Rebuild it from
    the plan's own ``turn_envelope`` lineage so the typed closeout can bind
    validation -> writeback -> spend instead of failing every legacy run.
    """

    if isinstance(transaction_plan.get("settlement_plan"), Mapping):
        return
    envelope = plan.get("turn_envelope")
    if not isinstance(envelope, Mapping):
        return
    selected_todo = selected_turn_todo(envelope)
    lineage = {
        "goal_id": str(envelope.get("goal_id") or ""),
        "agent_id": str(envelope.get("agent_id") or ""),
        "todo_id": str(selected_todo.get("todo_id") or ""),
    }
    if not all(lineage.values()):
        return
    host = plan.get("host")
    host_fields = host if isinstance(host, Mapping) else {}
    built = build_loopx_turn_transaction_plan(
        planned=True,
        lineage=lineage,
        host=str(host_fields.get("kind") or "generic-cli"),
        execution_mode=str(
            host_fields.get("execution_mode") or "isolated-headless"
        ),
        session_action=str(host_fields.get("session_action") or "resume"),
        turn_instance_id=transaction_plan.get("turn_instance_id"),
    )
    settlement_plan = built.get("settlement_plan")
    if isinstance(settlement_plan, Mapping):
        transaction_plan["settlement_plan"] = settlement_plan


def run_loopx_turn_once(
    plan: Mapping[str, Any],
    *,
    host_argv: Sequence[str] | None = None,
    host_runner: HostRunner | None = None,
    project: Path,
    runtime_root: Path,
    goal_id: str,
    timeout_seconds: float,
    execute: bool,
    retry_failed: bool = False,
    task_validator: TaskValidator | None = None,
    writeback: Writeback | None = None,
    completion_writeback: CompletionWriteback | None = None,
    spend: Spend | None = None,
    scheduler: Scheduler | None = None,
    lease_controller: TurnLeaseController | None = None,
    fault_injector: FaultInjector | None = None,
) -> dict[str, Any]:
    from .fenced_runtime import run_fenced_loopx_turn_once

    return run_fenced_loopx_turn_once(
        plan,
        host_argv=host_argv,
        host_runner=host_runner,
        project=project,
        runtime_root=runtime_root,
        goal_id=goal_id,
        timeout_seconds=timeout_seconds,
        execute=execute,
        retry_failed=retry_failed,
        task_validator=task_validator,
        writeback=writeback,
        completion_writeback=completion_writeback,
        spend=spend,
        scheduler=scheduler,
        lease_controller=lease_controller,
        fault_injector=fault_injector,
    )
