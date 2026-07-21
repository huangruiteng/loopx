"""Pure Turn Loop Controller transition contract.

This module decides the next disposition of a governed loop from one Turn
receipt plus a fresh quota/scheduler decision. It is a pure function: it never
invokes a model, sleeps, mutates a host scheduler, writes state, or spends
quota. `loopx turn run-once` remains the only delivery transaction; scheduler
process management, host wake APIs, and operator presentation belong to later
adapters (see the Turn Loop Controller plan in CONTRIBUTOR_TASKS).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from ..quota.turn_envelope import TURN_ENVELOPE_SCHEMA_VERSION
from .driver import REPAIR_ACTIONS, REPLAN_ACTIONS
from .transaction import LoopXTurnResultKind


LOOP_CONTROLLER_DISPOSITION_SCHEMA_VERSION = "loop_turn_loop_disposition_v0"


class LoopDisposition(str, Enum):
    RUN_NOW = "run_now"
    WAIT = "wait"
    USER_ACTION_REQUIRED = "user_action_required"
    REPAIR = "repair"
    REPLAN = "replan"
    TERMINAL = "terminal"


_NO_RECEIPT = object()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _disposition(
    disposition: LoopDisposition,
    *,
    reason: str,
    lineage: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": LOOP_CONTROLLER_DISPOSITION_SCHEMA_VERSION,
        "disposition": disposition.value,
        "reason": reason,
        "spends_quota": False,
        "launches_host": False,
        "writes_state": False,
    }
    if lineage:
        payload["lineage"] = dict(lineage)
    if extra:
        payload.update(dict(extra))
    return payload


def _receipt_lineage(receipt: Mapping[str, Any]) -> dict[str, str]:
    lineage = _mapping(receipt.get("lineage"))
    return {
        "goal_id": str(lineage.get("goal_id") or receipt.get("goal_id") or ""),
        "agent_id": str(lineage.get("agent_id") or receipt.get("agent_id") or ""),
        "todo_id": str(lineage.get("todo_id") or receipt.get("todo_id") or ""),
    }


def _decision_lineage(decision: Mapping[str, Any]) -> dict[str, str]:
    action = _mapping(decision.get("action"))
    selected_todo = _mapping(action.get("selected_todo"))
    return {
        "goal_id": str(decision.get("goal_id") or ""),
        "agent_id": str(decision.get("agent_id") or ""),
        "todo_id": str(selected_todo.get("todo_id") or ""),
    }


def _envelope_route(decision: Mapping[str, Any]) -> str | None:
    """Return a coarse route for a fresh quota/scheduler decision.

    Mirrors the typed-route semantics of the Turn plan driver: replan and
    repair actions route to their own dispositions, user action blocks host
    execution, quiet cadence waits, and only an allowed delivery runs now.
    Returns None when the decision envelope itself is malformed.
    """

    if decision.get("schema_version") != TURN_ENVELOPE_SCHEMA_VERSION:
        return None
    signature = _mapping(decision.get("action_signature"))
    if signature.get("matches") is not True:
        return None

    action = _mapping(decision.get("action"))
    user = _mapping(decision.get("user"))
    effective_action = str(decision.get("effective_action") or "")

    if user.get("action_required") is True:
        return LoopDisposition.USER_ACTION_REQUIRED.value
    if decision.get("should_run") is True:
        if not (action.get("delivery_allowed") is True and action.get("must_attempt") is True):
            return LoopDisposition.WAIT.value
        if effective_action in REPLAN_ACTIONS:
            return LoopDisposition.REPLAN.value
        if effective_action in REPAIR_ACTIONS or effective_action.endswith(
            ("_repair", "_repair_required")
        ):
            return LoopDisposition.REPAIR.value
        return LoopDisposition.RUN_NOW.value
    if action.get("quiet_noop_allowed") is True:
        return LoopDisposition.WAIT.value
    return LoopDisposition.WAIT.value


def decide_loop_disposition(
    *,
    turn_receipt: Mapping[str, Any] | None,
    quota_decision: Mapping[str, Any],
    bounded_turn_budget: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide the next loop disposition from one receipt and a fresh decision.

    `turn_receipt` is one `loopx_turn_receipt_v0`-shaped mapping (result kind,
    optional validation status, optional lineage). `quota_decision` is a fresh
    `loopx_turn_envelope_v0`. `bounded_turn_budget` may carry `max_turns` and
    `completed_turns` so validated progress can exhaust a bounded sequence.

    The function is pure: it launches no host, writes no state, and spends no
    quota. Unknown or contradictory input fails closed to a typed wait or
    contract-error disposition instead of guessing.
    """

    route = _envelope_route(quota_decision)
    if route is None:
        return _disposition(
            LoopDisposition.WAIT,
            reason="contract_error: quota decision is not a valid loopx_turn_envelope_v0",
        )
    decision_lineage = _decision_lineage(quota_decision)

    # A validated completion settles the terminal postcondition; it wins over
    # a decision-only user action because a finished loop must not stay
    # non-terminal behind a stale gate projection.
    if turn_receipt is not None:
        completion_kind = str(_mapping(turn_receipt).get("result_kind") or "")
        if completion_kind == LoopXTurnResultKind.VALIDATED_COMPLETION.value:
            return _disposition(
                LoopDisposition.TERMINAL,
                reason="terminal postcondition met by validated completion",
                lineage=decision_lineage,
            )

    if route == LoopDisposition.USER_ACTION_REQUIRED.value:
        return _disposition(
            LoopDisposition.USER_ACTION_REQUIRED,
            reason="fresh decision projects a concrete user action",
            lineage=decision_lineage,
        )

    if turn_receipt is None:
        if route == LoopDisposition.RUN_NOW.value:
            return _disposition(
                LoopDisposition.RUN_NOW,
                reason="no prior receipt and fresh decision allows delivery",
                lineage=decision_lineage,
            )
        if route == LoopDisposition.REPLAN.value:
            return _replan_disposition(reason="fresh decision requires replan", decision_lineage=decision_lineage)
        if route == LoopDisposition.REPAIR.value:
            return _disposition(
                LoopDisposition.REPAIR,
                reason="fresh decision requires repair",
                lineage=decision_lineage,
            )
        return _disposition(
            LoopDisposition.WAIT,
            reason="fresh decision is a quiet no-spend wait",
            lineage=decision_lineage,
        )

    receipt = _mapping(turn_receipt)
    raw_kind = str(receipt.get("result_kind") or "")
    try:
        result_kind = LoopXTurnResultKind(raw_kind)
    except ValueError:
        return _disposition(
            LoopDisposition.WAIT,
            reason=f"contract_error: unsupported turn receipt result_kind {raw_kind!r}",
            lineage=decision_lineage,
        )

    receipt_lineage = _receipt_lineage(receipt)
    if all(receipt_lineage.values()) and all(decision_lineage.values()):
        mismatched = {
            key
            for key in ("goal_id", "agent_id")
            if receipt_lineage[key] != decision_lineage[key]
        }
        if mismatched:
            return _disposition(
                LoopDisposition.WAIT,
                reason="stale_receipt: receipt lineage does not match the fresh decision",
                lineage=decision_lineage,
                extra={"stale_receipt_lineage": receipt_lineage},
            )

    if result_kind is LoopXTurnResultKind.VALIDATED_PROGRESS:
        budget = _mapping(bounded_turn_budget)
        max_turns = budget.get("max_turns")
        completed_turns = budget.get("completed_turns")
        if (
            isinstance(max_turns, int)
            and isinstance(completed_turns, int)
            and completed_turns >= max_turns
        ):
            return _disposition(
                LoopDisposition.TERMINAL,
                reason="bounded turn budget exhausted after validated progress",
                lineage=decision_lineage,
            )
        if route == LoopDisposition.RUN_NOW.value:
            return _disposition(
                LoopDisposition.RUN_NOW,
                reason="validated progress with fresh decision allowing the next turn",
                lineage=decision_lineage,
            )
        if route == LoopDisposition.REPLAN.value:
            return _replan_disposition(reason="fresh decision requires replan after progress", decision_lineage=decision_lineage)
        if route == LoopDisposition.REPAIR.value:
            return _disposition(
                LoopDisposition.REPAIR,
                reason="fresh decision requires repair after progress",
                lineage=decision_lineage,
            )
        return _disposition(
            LoopDisposition.WAIT,
            reason="validated progress but fresh decision does not allow the next turn yet",
            lineage=decision_lineage,
        )

    if result_kind is LoopXTurnResultKind.REPLAN_REQUIRED:
        return _replan_disposition(reason="turn receipt requires replan", decision_lineage=decision_lineage)

    if result_kind is LoopXTurnResultKind.REPAIR_REQUIRED:
        return _disposition(
            LoopDisposition.REPAIR,
            reason="turn receipt requires repair",
            lineage=decision_lineage,
        )

    if result_kind is LoopXTurnResultKind.USER_ACTION_REQUIRED:
        return _disposition(
            LoopDisposition.USER_ACTION_REQUIRED,
            reason="turn receipt projects a concrete user action",
            lineage=decision_lineage,
        )

    if result_kind is LoopXTurnResultKind.WAIT:
        return _disposition(
            LoopDisposition.WAIT,
            reason="turn receipt is a typed no-spend wait",
            lineage=decision_lineage,
        )

    # host_failure, validation_failed, writeback_failed, quota_spend_failed:
    # the loop must not guess recovery on its own; hold for repair routing.
    return _disposition(
        LoopDisposition.REPAIR,
        reason=f"turn receipt ended in {result_kind.value}; route to repair before any successor turn",
        lineage=decision_lineage,
    )


def _replan_disposition(*, reason: str, decision_lineage: Mapping[str, str]) -> dict[str, Any]:
    return _disposition(
        LoopDisposition.REPLAN,
        reason=reason,
        lineage=decision_lineage,
        extra={
            "replan_continuation": {
                "requires_bounded_delta": True,
                "delta_kinds": ["todo_delta", "vision_delta"],
                "stale_todo_rerun_allowed": False,
                "fresh_envelope_required": True,
            }
        },
    )
