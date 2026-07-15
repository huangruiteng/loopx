"""One bounded LoopX Turn host execution with resumable local receipts."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from ...authority import validate_public_safe_text
from ...file_lock import exclusive_file_lock
from ..work_items.delivery_batch_scale import require_delivery_batch_scale
from ..work_items.delivery_outcome import require_delivery_outcome
from .transaction import (
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    TRANSACTION_PHASES,
    LoopXTurnResultKind,
    validate_loopx_turn_receipt,
)


LOOPX_TURN_HOST_REQUEST_SCHEMA_VERSION = "loopx_turn_host_request_v0"
LOOPX_TURN_EXECUTION_SCHEMA_VERSION = "loopx_turn_execution_v0"
LOOPX_TURN_JOURNAL_SCHEMA_VERSION = "loopx_turn_journal_v0"
LOOPX_TURN_TASK_VALIDATION_SCHEMA_VERSION = "loopx_turn_task_validation_v0"
HOST_RESULT_MAX_BYTES = 12_000
HOST_ARG_MAX_COUNT = 32
HOST_ARG_MAX_CHARS = 1_024
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
    "summary",
}

Writeback = Callable[[dict[str, Any]], dict[str, Any]]
Spend = Callable[[], dict[str, Any]]
Scheduler = Callable[[dict[str, Any]], dict[str, Any]]
HostRunner = Callable[[Mapping[str, Any]], dict[str, Any]]
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
    return {
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


def validate_loopx_turn_host_result(
    plan: Mapping[str, Any],
    value: Mapping[str, Any],
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
    if kind is LoopXTurnResultKind.VALIDATED_COMPLETION:
        errors.append("validated_completion requires a todo lifecycle adapter")
    if kind not in MATERIAL_HOST_RESULT_KINDS | STOP_HOST_RESULT_KINDS:
        if kind is not LoopXTurnResultKind.VALIDATED_COMPLETION:
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
            required=material and field != "summary",
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
    if status not in {"passed", "failed", "inconclusive", "unavailable", "not_required"}:
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
    if status in {"passed", "not_required"} and recovery_kind is not None:
        errors.append("successful task validation cannot declare recovery_kind")
    if exit_code is not None and (not isinstance(exit_code, int) or exit_code < 0):
        errors.append("task validation exit_code must be a non-negative integer")
    if status == "passed" and exit_code not in {None, 0}:
        errors.append("passed task validation cannot declare a non-zero exit_code")
    effective_status = status if not errors else "inconclusive"
    effective_recovery_kind = recovery_kind
    if errors and effective_recovery_kind is None:
        effective_recovery_kind = LoopXTurnResultKind.REPAIR_REQUIRED.value
    return {
        "ok": not errors and status in {"passed", "not_required"},
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
    except Exception:
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


def turn_journal_path(runtime_root: Path, *, goal_id: str, turn_key: str) -> Path:
    match = TURN_KEY_RE.fullmatch(turn_key)
    if not match:
        raise ValueError("turn_key must be a sha256 digest")
    return runtime_root / "goals" / goal_id / "turns" / f"{match.group('digest')}.json"


def _write_journal(path: Path, journal: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(journal, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_journal(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != LOOPX_TURN_JOURNAL_SCHEMA_VERSION:
        raise ValueError("LoopX Turn journal has an unsupported schema")
    return value


def load_loopx_turn_plan_from_journal(
    runtime_root: Path,
    *,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any]:
    path = turn_journal_path(runtime_root, goal_id=goal_id, turn_key=turn_key)
    with exclusive_file_lock(path):
        journal = _load_journal(path)
    if journal is None:
        raise ValueError("LoopX Turn resume journal does not exist")
    plan = journal.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("LoopX Turn resume journal does not contain a plan")
    transaction = plan.get("transaction") if isinstance(plan.get("transaction"), dict) else {}
    if transaction.get("turn_key") != turn_key or journal.get("turn_key") != turn_key:
        raise ValueError("LoopX Turn resume journal has mismatched turn lineage")
    envelope = plan.get("turn_envelope") if isinstance(plan.get("turn_envelope"), dict) else {}
    if envelope.get("goal_id") != goal_id or journal.get("goal_id") != goal_id:
        raise ValueError("LoopX Turn resume journal belongs to another goal")
    return dict(plan)


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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
    except Exception as exc:
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
        "host": journal.get("host"),
        "result_kind": journal.get("result_kind"),
        "validation": journal.get("task_validation"),
        "receipt": journal.get("receipt"),
        "scheduler": journal.get("scheduler"),
        "effects": dict(effects),
        **({"reason": journal.get("reason")} if journal.get("reason") else {}),
    }


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
    spend: Spend | None = None,
    scheduler: Scheduler | None = None,
) -> dict[str, Any]:
    if host_runner is not None and host_argv is not None:
        raise ValueError("run-once accepts either host_argv or host_runner, not both")
    if host_runner is None:
        argv = normalize_host_argv(host_argv or [])
        host_projection = {"executable": Path(argv[0]).name, "argv_count": len(argv)}
    else:
        argv = None
        host_projection = {"executable": "built-in", "kind": "codex-cli"}
    request = build_loopx_turn_host_request(plan)
    empty_effects = {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    if not execute:
        preview = {
            "schema_version": LOOPX_TURN_JOURNAL_SCHEMA_VERSION,
            "status": "preview",
            "host": host_projection,
            "result_kind": None,
            "receipt": None,
            "scheduler": {"disposition": "not_evaluated"},
        }
        return _execution_payload(
            plan,
            preview,
            execute=False,
            replayed=False,
            effects=empty_effects,
        )
    if writeback is None or spend is None or scheduler is None:
        raise ValueError("executing run-once requires writeback, spend, and scheduler callbacks")

    turn_key = str(request["turn_key"])
    journal_path = turn_journal_path(runtime_root, goal_id=goal_id, turn_key=turn_key)
    with exclusive_file_lock(journal_path):
        journal = _load_journal(journal_path)
        if journal and (
            journal.get("status") in {"committed", "stopped"}
            or journal.get("status") == "failed" and not retry_failed
        ):
            return _execution_payload(
                plan,
                journal,
                execute=True,
                replayed=True,
                effects=empty_effects,
            )
        if journal and journal.get("status") == "failed":
            receipt = journal.get("receipt") if isinstance(journal.get("receipt"), dict) else {}
            if receipt.get("failed_phase") == "validation":
                if journal.get("validation_stage") != "task_postcondition":
                    journal.pop("host_result", None)
                journal.pop("result_kind", None)
                journal["completed_phases"] = (
                    list(TRANSACTION_PHASES[:2])
                    if isinstance(journal.get("host_result"), dict)
                    else []
                )
                journal.pop("task_validation", None)
                journal.pop("validation_stage", None)
            journal.pop("reason", None)
            journal.pop("receipt", None)
            journal["status"] = "in_progress"
            _write_journal(journal_path, journal)
        if journal is None:
            journal = {
                "schema_version": LOOPX_TURN_JOURNAL_SCHEMA_VERSION,
                "turn_key": turn_key,
                "goal_id": goal_id,
                "status": "in_progress",
                "host": host_projection,
                "completed_phases": [],
                "plan": dict(plan),
            }
            _write_journal(journal_path, journal)

        effects = dict(empty_effects)
        completed_phases = list(journal.get("completed_phases") or [])
        result = journal.get("host_result") if isinstance(journal.get("host_result"), dict) else None
        if "typed_result" not in completed_phases:
            host_observation = (
                _run_host_runner(request, runner=host_runner)
                if host_runner is not None
                else _run_host(
                    request,
                    argv=argv or [],
                    project=project,
                    timeout_seconds=timeout_seconds,
                )
            )
            effects["host_invoked"] = True
            if not host_observation.get("ok"):
                failure = _host_failure(
                    plan,
                    kind=LoopXTurnResultKind.HOST_FAILURE,
                    completed_phases=[],
                    failed_phase="host_execute",
                    reason=str(host_observation.get("reason") or "host execution failed"),
                )
                journal.update(
                    status="failed",
                    reason=failure["reason"],
                    receipt=failure["receipt"],
                    completed_phases=[],
                )
                _write_journal(journal_path, journal)
                return _execution_payload(plan, journal, execute=True, replayed=False, effects=effects)
            result = dict(host_observation["value"])
            completed_phases = list(TRANSACTION_PHASES[:2])

        validation = validate_loopx_turn_host_result(plan, result or {})
        if not validation.get("ok"):
            failure = _host_failure(
                plan,
                kind=LoopXTurnResultKind.VALIDATION_FAILED,
                completed_phases=list(TRANSACTION_PHASES[:2]),
                failed_phase="validation",
                reason="; ".join(validation.get("errors") or ["host result validation failed"]),
            )
            journal.update(
                status="failed",
                reason=failure["reason"],
                receipt=failure["receipt"],
                completed_phases=list(TRANSACTION_PHASES[:2]),
                result_kind=LoopXTurnResultKind.VALIDATION_FAILED.value,
                validation_stage="host_result_contract",
            )
            _write_journal(journal_path, journal)
            return _execution_payload(plan, journal, execute=True, replayed=False, effects=effects)
        result = dict(validation["result"])
        if len(completed_phases) < 2:
            completed_phases = list(TRANSACTION_PHASES[:2])
        journal.update(
            host_result=result,
            result_kind=result.get("result_kind"),
            completed_phases=completed_phases,
        )
        _write_journal(journal_path, journal)

        kind = LoopXTurnResultKind(str(result["result_kind"]))
        if kind in STOP_HOST_RESULT_KINDS:
            completed_phases = list(TRANSACTION_PHASES[:3])
            journal.update(
                status="stopped",
                completed_phases=completed_phases,
                task_validation=_task_validation_receipt(
                    status="not_required",
                    validator_kind="stop_result",
                    summary="task validation is not required for a typed stop result",
                ),
                receipt=_receipt(plan, result, completed_phases=completed_phases),
                scheduler={"disposition": "not_applicable"},
            )
            _write_journal(journal_path, journal)
            return _execution_payload(plan, journal, execute=True, replayed=False, effects=effects)

        stored_task_validation = (
            journal.get("task_validation")
            if isinstance(journal.get("task_validation"), dict)
            else None
        )
        task_validation = (
            stored_task_validation
            if "validation" in completed_phases
            and stored_task_validation is not None
            and stored_task_validation.get("ok") is True
            else _run_task_validator(
                plan,
                result,
                validator=task_validator,
            )
        )
        journal["task_validation"] = task_validation
        if not task_validation.get("ok"):
            reason = str(
                task_validation.get("summary")
                or "independent task validation failed"
            )
            failure = _host_failure(
                plan,
                kind=LoopXTurnResultKind.VALIDATION_FAILED,
                completed_phases=list(TRANSACTION_PHASES[:2]),
                failed_phase="validation",
                reason=reason,
            )
            journal.update(
                status="failed",
                reason=reason,
                receipt=failure["receipt"],
                completed_phases=list(TRANSACTION_PHASES[:2]),
                result_kind=LoopXTurnResultKind.VALIDATION_FAILED.value,
                validation_stage="task_postcondition",
            )
            _write_journal(journal_path, journal)
            return _execution_payload(
                plan,
                journal,
                execute=True,
                replayed=False,
                effects=effects,
            )

        if "validation" not in completed_phases:
            completed_phases = list(TRANSACTION_PHASES[:3])
        journal.update(
            result_kind=result.get("result_kind"),
            completed_phases=completed_phases,
            validation_stage="task_postcondition",
        )
        _write_journal(journal_path, journal)

        if "durable_writeback" not in completed_phases:
            writeback_payload = writeback(result)
            if not writeback_payload.get("ok") or not writeback_payload.get("appended"):
                failure = _host_failure(
                    plan,
                    kind=LoopXTurnResultKind.WRITEBACK_FAILED,
                    completed_phases=completed_phases,
                    failed_phase="durable_writeback",
                    reason=str(
                        writeback_payload.get("error")
                        or writeback_payload.get("reason")
                        or "writeback failed"
                    ),
                )
                journal.update(
                    status="failed",
                    reason=failure["reason"],
                    receipt=failure["receipt"],
                )
                _write_journal(journal_path, journal)
                return _execution_payload(
                    plan,
                    journal,
                    execute=True,
                    replayed=False,
                    effects=effects,
                )
            effects["state_written"] = True
            completed_phases = list(TRANSACTION_PHASES[:4])
            journal.update(
                completed_phases=completed_phases,
                writeback=_compact_callback(writeback_payload),
            )
            _write_journal(journal_path, journal)

        if "quota_spend" not in completed_phases:
            spend_payload = spend()
            if not spend_payload.get("ok") or not spend_payload.get("appended"):
                failure = _host_failure(
                    plan,
                    kind=LoopXTurnResultKind.QUOTA_SPEND_FAILED,
                    completed_phases=completed_phases,
                    failed_phase="quota_spend",
                    reason=str(spend_payload.get("reason") or "quota spend failed"),
                )
                journal.update(
                    status="failed",
                    reason=failure["reason"],
                    receipt=failure["receipt"],
                )
                _write_journal(journal_path, journal)
                return _execution_payload(
                    plan,
                    journal,
                    execute=True,
                    replayed=False,
                    effects=effects,
                )
            effects["quota_spent"] = True
            completed_phases = list(TRANSACTION_PHASES[:5])
            journal.update(
                completed_phases=completed_phases,
                quota_spend=_compact_callback(spend_payload),
            )
            _write_journal(journal_path, journal)
        else:
            spend_payload = (
                dict(journal["quota_spend"])
                if isinstance(journal.get("quota_spend"), dict)
                else {"ok": True, "appended": True}
            )

        scheduler_payload = scheduler(spend_payload)
        journal["scheduler"] = scheduler_payload
        if scheduler_payload.get("completed") is not True:
            journal.update(
                status="scheduler_action_required",
                receipt=_receipt(plan, result, completed_phases=completed_phases),
            )
            _write_journal(journal_path, journal)
            return _execution_payload(plan, journal, execute=True, replayed=False, effects=effects)

        completed_phases = list(TRANSACTION_PHASES)
        effects["scheduler_acknowledged"] = bool(scheduler_payload.get("acknowledged"))
        journal.update(
            status="committed",
            completed_phases=completed_phases,
            receipt=_receipt(plan, result, completed_phases=completed_phases),
        )
        _write_journal(journal_path, journal)
        return _execution_payload(plan, journal, execute=True, replayed=False, effects=effects)
