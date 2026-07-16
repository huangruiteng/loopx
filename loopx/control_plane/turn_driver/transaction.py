"""Typed LoopX Turn transaction planning and receipt validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from hashlib import sha256
from typing import Any


LOOPX_TURN_TRANSACTION_PLAN_SCHEMA_VERSION = "loopx_turn_transaction_plan_v0"
LOOPX_TURN_RESULT_SCHEMA_VERSION = "loopx_turn_result_v0"
LOOPX_TURN_RECEIPT_SCHEMA_VERSION = "loopx_turn_receipt_v0"
LOOPX_TURN_RECEIPT_VALIDATION_SCHEMA_VERSION = "loopx_turn_receipt_validation_v0"
TRANSACTION_PHASES = (
    "host_execute",
    "typed_result",
    "validation",
    "durable_writeback",
    "quota_spend",
    "scheduler_apply",
    "scheduler_ack",
)


class LoopXTurnResultKind(str, Enum):
    VALIDATED_PROGRESS = "validated_progress"
    VALIDATED_COMPLETION = "validated_completion"
    REPAIR_REQUIRED = "repair_required"
    REPLAN_REQUIRED = "replan_required"
    USER_ACTION_REQUIRED = "user_action_required"
    WAIT = "wait"
    HOST_FAILURE = "host_failure"
    VALIDATION_FAILED = "validation_failed"
    WRITEBACK_FAILED = "writeback_failed"
    QUOTA_SPEND_FAILED = "quota_spend_failed"


MATERIAL_RESULT_KINDS = {
    LoopXTurnResultKind.VALIDATED_PROGRESS,
    LoopXTurnResultKind.VALIDATED_COMPLETION,
    LoopXTurnResultKind.REPAIR_REQUIRED,
    LoopXTurnResultKind.REPLAN_REQUIRED,
}
NO_SPEND_RESULT_KINDS = {
    LoopXTurnResultKind.USER_ACTION_REQUIRED,
    LoopXTurnResultKind.WAIT,
    LoopXTurnResultKind.HOST_FAILURE,
    LoopXTurnResultKind.VALIDATION_FAILED,
    LoopXTurnResultKind.WRITEBACK_FAILED,
    LoopXTurnResultKind.QUOTA_SPEND_FAILED,
}
STOP_RESULT_KINDS = {
    LoopXTurnResultKind.USER_ACTION_REQUIRED,
    LoopXTurnResultKind.WAIT,
}
FAILURE_PHASES = {
    LoopXTurnResultKind.HOST_FAILURE: "host_execute",
    LoopXTurnResultKind.VALIDATION_FAILED: "validation",
    LoopXTurnResultKind.WRITEBACK_FAILED: "durable_writeback",
    LoopXTurnResultKind.QUOTA_SPEND_FAILED: "quota_spend",
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def loopx_turn_execution_committed(execution: Mapping[str, Any]) -> bool:
    """Return whether one public execution completed its durable transaction."""

    validation = _mapping(execution.get("validation"))
    receipt = _mapping(execution.get("receipt"))
    effects = _mapping(execution.get("effects"))
    return bool(
        execution.get("status") == "committed"
        and receipt.get("status") == "committed"
        and validation.get("status") == "passed"
        and effects.get("state_written") is True
        and effects.get("quota_spent") is True
    )


def loopx_turn_execution_recovery_required(
    execution: Mapping[str, Any],
) -> bool:
    """Return whether a failed public execution requests repair or replan."""

    validation = _mapping(execution.get("validation"))
    receipt = _mapping(execution.get("receipt"))
    return bool(
        validation.get("recovery_kind") in {"repair_required", "replan_required"}
        and (
            validation.get("status") == "failed"
            or receipt.get("failed_phase") == "validation"
            or execution.get("status") in {"failed", "validation_failed"}
        )
    )


def loopx_turn_execution_has_durable_effects(
    execution: Mapping[str, Any],
) -> bool:
    """Return whether an execution wrote state or spent quota."""

    effects = _mapping(execution.get("effects"))
    return bool(
        effects.get("state_written") is True or effects.get("quota_spent") is True
    )


def build_loopx_turn_transaction_plan(
    *,
    planned: bool,
    lineage: Mapping[str, str],
    host: str,
    execution_mode: str,
    session_action: str,
    scheduler_owner: str = "none",
) -> dict[str, Any]:
    turn_key = _canonical_hash(
        {
            "lineage": dict(lineage),
            "host": host,
            "execution_mode": execution_mode,
            "scheduler_owner": scheduler_owner,
            "session_action": session_action,
        }
    )
    return {
        "schema_version": LOOPX_TURN_TRANSACTION_PLAN_SCHEMA_VERSION,
        "status": "planned" if planned else "not_applicable",
        "turn_key": turn_key,
        "phases": list(TRANSACTION_PHASES) if planned else [],
        "commit_policy": "result<validate<writeback<spend;apply<ack;cadence:no-spend",
        "receipt_seed": {
            "schema_version": LOOPX_TURN_RECEIPT_SCHEMA_VERSION,
            "status": "not_executed",
            "next_phase": TRANSACTION_PHASES[0] if planned else None,
        },
    }


def _result_kind(value: Any, errors: list[str]) -> LoopXTurnResultKind | None:
    try:
        return LoopXTurnResultKind(str(value or ""))
    except ValueError:
        errors.append("unsupported execution result kind")
        return None


def _completed_phases(value: Any, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append("completed_phases must be a list")
        return []
    phases = [str(item) for item in value]
    expected = list(TRANSACTION_PHASES[: len(phases)])
    if phases != expected:
        errors.append("completed_phases must be an ordered transaction prefix")
    return phases


def validate_loopx_turn_receipt(
    transaction_plan: Mapping[str, Any],
    execution_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one public-safe host result against its transaction plan."""

    plan = _mapping(transaction_plan)
    result = _mapping(execution_result)
    errors: list[str] = []
    if plan.get("schema_version") != LOOPX_TURN_TRANSACTION_PLAN_SCHEMA_VERSION:
        errors.append("unsupported transaction plan schema")
    if plan.get("status") != "planned":
        errors.append("transaction plan is not executable")
    if result.get("schema_version") != LOOPX_TURN_RESULT_SCHEMA_VERSION:
        errors.append("unsupported execution result schema")

    turn_key = str(plan.get("turn_key") or "")
    if not turn_key or str(result.get("turn_key") or "") != turn_key:
        errors.append("execution result turn_key does not match the transaction plan")

    kind = _result_kind(result.get("result_kind"), errors)
    completed = _completed_phases(result.get("completed_phases"), errors)
    failed_phase = str(result.get("failed_phase") or "") or None
    next_index = min(len(completed), len(TRANSACTION_PHASES))
    expected_next = (
        TRANSACTION_PHASES[next_index] if next_index < len(TRANSACTION_PHASES) else None
    )

    if failed_phase and failed_phase != expected_next:
        errors.append("failed_phase must be the next uncompleted transaction phase")
    if failed_phase and kind not in FAILURE_PHASES:
        errors.append("failed_phase is only valid for a typed failure result")
    if kind in FAILURE_PHASES and failed_phase != FAILURE_PHASES[kind]:
        errors.append(f"{kind.value} must declare failed_phase={FAILURE_PHASES[kind]}")
    if kind in MATERIAL_RESULT_KINDS and "validation" not in completed:
        errors.append("material result requires completed validation")
    if kind in NO_SPEND_RESULT_KINDS and "quota_spend" in completed:
        errors.append(f"{kind.value} cannot spend quota")

    ok = not errors
    fully_committed = completed == list(TRANSACTION_PHASES)
    failed = kind in FAILURE_PHASES if kind is not None else False
    stopped = kind in STOP_RESULT_KINDS if kind is not None else False
    status = (
        "invalid"
        if not ok
        else "failed"
        if failed
        else "stopped"
        if stopped
        else "committed"
        if fully_committed
        else "validated"
        if "validation" in completed
        else "in_progress"
    )
    return {
        "ok": ok,
        "schema_version": LOOPX_TURN_RECEIPT_VALIDATION_SCHEMA_VERSION,
        "turn_key": turn_key or None,
        "result_kind": kind.value if kind is not None else None,
        "completed_phases": completed,
        "failed_phase": failed_phase,
        "status": status,
        "next_phase": (
            None
            if fully_committed or (ok and stopped)
            else failed_phase or expected_next
        ),
        "commit_eligibility": {
            "writeback": ok
            and kind in MATERIAL_RESULT_KINDS
            and "validation" in completed,
            "quota_spend": (
                ok
                and kind in MATERIAL_RESULT_KINDS
                and "durable_writeback" in completed
            ),
            "scheduler_ack": ok and "scheduler_apply" in completed,
        },
        "errors": errors,
    }
