"""Pure Turn Loop Controller transition contract.

This module decides the next disposition of a governed loop from one validated
Turn receipt plus a fresh quota/scheduler decision. It is a pure function: it
never invokes a model, sleeps, mutates a host scheduler, writes state, or
spends quota. `loopx turn run-once` remains the only delivery transaction;
scheduler process management, host wake APIs, and operator presentation belong
to later adapters (see the Turn Loop Controller plan in CONTRIBUTOR_TASKS).

The transition output space is exactly six dispositions:
``run_now | wait | user_action_required | repair | replan | terminal``.

Input validity is enforced at the typed-input boundary, not encoded as a
seventh disposition. ``decide_loop_disposition`` raises ``ValueError`` when a
receipt, envelope, or budget cannot be proven against the shared Turn
contracts, so the caller is responsible for feeding only validated, fresh
inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from .driver import LoopXTurnRoute, _typed_route
from .transaction import (
    LOOPX_TURN_RECEIPT_VALIDATION_SCHEMA_VERSION,
    LoopXTurnResultKind,
)


LOOP_CONTROLLER_DISPOSITION_SCHEMA_VERSION = "loop_turn_loop_disposition_v0"
BOUNDED_TURN_BUDGET_SCHEMA_VERSION = "loop_bounded_turn_budget_v0"
VALIDATED_TURN_RECEIPT_SCHEMA_VERSION = "loop_validated_turn_receipt_v0"

# Statuses that prove a material result has been independently validated and
# may therefore drive a terminal or progress transition.
_VALIDATED_RECEIPT_STATUSES = {"validated", "committed"}


class LoopDisposition(str, Enum):
    RUN_NOW = "run_now"
    WAIT = "wait"
    USER_ACTION_REQUIRED = "user_action_required"
    REPAIR = "repair"
    REPLAN = "replan"
    TERMINAL = "terminal"


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


def _decision_lineage(decision: Mapping[str, Any]) -> dict[str, str]:
    action = _mapping(decision.get("action"))
    selected_todo = _mapping(action.get("selected_todo"))
    return {
        "goal_id": str(decision.get("goal_id") or ""),
        "agent_id": str(decision.get("agent_id") or ""),
        "todo_id": str(selected_todo.get("todo_id") or ""),
    }


def _envelope_route(decision: Mapping[str, Any]) -> LoopXTurnRoute:
    """Return the shared typed route for a fresh quota/scheduler decision.

    Reuses the Turn plan driver's ``_typed_route`` contract, which requires a
    matching action signature with non-empty equal hashes and an in-budget
    compaction. A projected user action outranks delivery, so it is resolved
    before the typed delivery route. Raises ``ValueError`` when the envelope
    fails the shared contract instead of accepting a forged or truncated
    decision.
    """

    route = _typed_route(decision)
    if route is LoopXTurnRoute.CONTRACT_ERROR:
        raise ValueError(
            "quota decision failed the shared envelope contract "
            "(schema, signature hashes, or compaction budget)"
        )
    user = _mapping(decision.get("user"))
    if user.get("action_required") is True:
        return LoopXTurnRoute.USER_ACTION_REQUIRED
    return route


def _route_to_disposition(route: LoopXTurnRoute) -> LoopDisposition:
    return {
        LoopXTurnRoute.READY_FOR_HOST: LoopDisposition.RUN_NOW,
        LoopXTurnRoute.REPLAN_REQUIRED: LoopDisposition.REPLAN,
        LoopXTurnRoute.REPAIR_REQUIRED: LoopDisposition.REPAIR,
        LoopXTurnRoute.USER_ACTION_REQUIRED: LoopDisposition.USER_ACTION_REQUIRED,
        LoopXTurnRoute.WAIT: LoopDisposition.WAIT,
        LoopXTurnRoute.BLOCKED: LoopDisposition.WAIT,
    }[route]


class ValidatedTurnReceipt:
    """A Turn receipt proven by ``validate_loopx_turn_receipt``.

    Only a successful ``loopx_turn_receipt_validation_v0`` result (``ok=true``)
    with a supported result kind can construct one. The normalized
    ``(goal_id, agent_id, todo_id)`` lineage is taken from the validation
    result, so a caller cannot forge a completion by hand-writing
    ``result_kind + lineage``.
    """

    __slots__ = ("result_kind", "status", "lineage", "turn_key")

    def __init__(
        self,
        *,
        result_kind: LoopXTurnResultKind,
        status: str,
        lineage: Mapping[str, str],
        turn_key: str | None,
    ) -> None:
        self.result_kind = result_kind
        self.status = status
        self.lineage = {
            "goal_id": str(lineage.get("goal_id") or ""),
            "agent_id": str(lineage.get("agent_id") or ""),
            "todo_id": str(lineage.get("todo_id") or ""),
        }
        self.turn_key = turn_key

    @classmethod
    def from_validation_result(
        cls, validation_result: Mapping[str, Any]
    ) -> "ValidatedTurnReceipt":
        result = _mapping(validation_result)
        if result.get("schema_version") != LOOPX_TURN_RECEIPT_VALIDATION_SCHEMA_VERSION:
            raise ValueError(
                "validated turn receipt requires schema_version="
                f"{LOOPX_TURN_RECEIPT_VALIDATION_SCHEMA_VERSION}"
            )
        if result.get("ok") is not True:
            raise ValueError("validated turn receipt requires ok=true")
        raw_kind = result.get("result_kind")
        try:
            result_kind = LoopXTurnResultKind(str(raw_kind or ""))
        except ValueError:
            raise ValueError(
                f"validated turn receipt has unsupported result_kind {raw_kind!r}"
            ) from None
        lineage = _mapping(result.get("lineage"))
        if not all(lineage.get(k) for k in ("goal_id", "agent_id", "todo_id")):
            raise ValueError(
                "validated turn receipt is missing goal/agent/todo lineage"
            )
        return cls(
            result_kind=result_kind,
            status=str(result.get("status") or ""),
            lineage=lineage,
            turn_key=str(result.get("turn_key") or "") or None,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": VALIDATED_TURN_RECEIPT_SCHEMA_VERSION,
            "result_kind": self.result_kind.value,
            "status": self.status,
            "lineage": dict(self.lineage),
            "turn_key": self.turn_key,
        }


class BoundedTurnBudget:
    """A provider-neutral bounded Turn budget tied to one lineage.

    Construction enforces strict integer domains (booleans are rejected) and a
    sane range, so the transition never guesses an unbounded continuation.
    """

    __slots__ = ("lineage", "max_turns", "completed_turns")

    def __init__(
        self,
        *,
        lineage: Mapping[str, str],
        max_turns: int,
        completed_turns: int,
    ) -> None:
        if type(max_turns) is not int:
            raise ValueError("bounded turn budget max_turns must be an int")
        if type(completed_turns) is not int:
            raise ValueError("bounded turn budget completed_turns must be an int")
        if max_turns <= 0:
            raise ValueError("bounded turn budget max_turns must be > 0")
        if completed_turns < 0:
            raise ValueError("bounded turn budget completed_turns must be >= 0")
        if completed_turns > max_turns:
            raise ValueError(
                "bounded turn budget completed_turns must be <= max_turns"
            )
        self.lineage = {
            "goal_id": str(lineage.get("goal_id") or ""),
            "agent_id": str(lineage.get("agent_id") or ""),
            "todo_id": str(lineage.get("todo_id") or ""),
        }
        if not all(self.lineage.values()):
            raise ValueError("bounded turn budget is missing goal/agent/todo lineage")
        self.max_turns = max_turns
        self.completed_turns = completed_turns

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": BOUNDED_TURN_BUDGET_SCHEMA_VERSION,
            "lineage": dict(self.lineage),
            "max_turns": self.max_turns,
            "completed_turns": self.completed_turns,
        }

    @property
    def remaining(self) -> int:
        return self.max_turns - self.completed_turns


def _assert_lineage_match(
    *,
    receipt_lineage: Mapping[str, str],
    decision_lineage: Mapping[str, str],
) -> None:
    for key in ("goal_id", "agent_id", "todo_id"):
        if receipt_lineage.get(key) != decision_lineage.get(key):
            raise ValueError(
                "stale_receipt: receipt lineage does not match the fresh decision "
                f"on {key} (receipt={receipt_lineage.get(key)!r}, "
                f"decision={decision_lineage.get(key)!r})"
            )


def decide_loop_disposition(
    *,
    turn_receipt: ValidatedTurnReceipt | None,
    quota_decision: Mapping[str, Any],
    bounded_turn_budget: BoundedTurnBudget | None = None,
) -> dict[str, Any]:
    """Decide the next loop disposition from one validated receipt and a fresh decision.

    ``turn_receipt`` is a :class:`ValidatedTurnReceipt` (or ``None`` when no
    prior Turn has committed). ``quota_decision`` is a fresh
    ``loopx_turn_envelope_v0``. ``bounded_turn_budget`` is a
    :class:`BoundedTurnBudget` and is required when the receipt is
    ``validated_progress`` so continuation can prove a bound.

    The function is pure: it launches no host, writes no state, and spends no
    quota. Invalid or stale input raises ``ValueError`` at the typed-input
    boundary; the transition output space is always one of the six
    :class:`LoopDisposition` values.
    """

    route = _envelope_route(quota_decision)
    decision_lineage = _decision_lineage(quota_decision)
    if not all(decision_lineage.values()):
        raise ValueError(
            "fresh quota decision is missing goal/agent/todo lineage"
        )

    if turn_receipt is None:
        disposition = _route_to_disposition(route)
        if disposition is LoopDisposition.REPLAN:
            return _replan_disposition(
                reason="fresh decision requires replan",
                decision_lineage=decision_lineage,
            )
        return _disposition(
            disposition,
            reason=_no_receipt_reason(disposition),
            lineage=decision_lineage,
        )

    _assert_lineage_match(
        receipt_lineage=turn_receipt.lineage,
        decision_lineage=decision_lineage,
    )
    result_kind = turn_receipt.result_kind

    # A met terminal postcondition outranks a decision-only user action, but
    # only after the receipt is proven valid and fresh (above).
    if result_kind is LoopXTurnResultKind.VALIDATED_COMPLETION:
        return _disposition(
            LoopDisposition.TERMINAL,
            reason="terminal postcondition met by validated completion",
            lineage=decision_lineage,
        )

    # Decision user action outranks every non-terminal disposition.
    if route is LoopXTurnRoute.USER_ACTION_REQUIRED:
        return _disposition(
            LoopDisposition.USER_ACTION_REQUIRED,
            reason="fresh decision projects a concrete user action",
            lineage=decision_lineage,
        )

    if result_kind is LoopXTurnResultKind.VALIDATED_PROGRESS:
        if bounded_turn_budget is None:
            raise ValueError(
                "validated progress cannot continue without a proven bounded turn budget"
            )
        _assert_lineage_match(
            receipt_lineage=bounded_turn_budget.lineage,
            decision_lineage=decision_lineage,
        )
        if bounded_turn_budget.remaining <= 0:
            return _disposition(
                LoopDisposition.TERMINAL,
                reason="bounded turn budget exhausted after validated progress",
                lineage=decision_lineage,
            )
        disposition = _route_to_disposition(route)
        if disposition is LoopDisposition.REPLAN:
            return _replan_disposition(
                reason="fresh decision requires replan after progress",
                decision_lineage=decision_lineage,
            )
        return _disposition(
            disposition,
            reason=_progress_reason(disposition),
            lineage=decision_lineage,
        )

    if result_kind is LoopXTurnResultKind.REPLAN_REQUIRED:
        return _replan_disposition(
            reason="turn receipt requires replan",
            decision_lineage=decision_lineage,
        )

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
        reason=(
            f"turn receipt ended in {result_kind.value}; "
            "route to repair before any successor turn"
        ),
        lineage=decision_lineage,
    )


def _no_receipt_reason(disposition: LoopDisposition) -> str:
    return {
        LoopDisposition.RUN_NOW: "no prior receipt and fresh decision allows delivery",
        LoopDisposition.WAIT: "fresh decision is a quiet no-spend wait",
        LoopDisposition.REPAIR: "fresh decision requires repair",
        LoopDisposition.USER_ACTION_REQUIRED: "fresh decision projects a concrete user action",
    }[disposition]


def _progress_reason(disposition: LoopDisposition) -> str:
    return {
        LoopDisposition.RUN_NOW: "validated progress with fresh decision allowing the next turn",
        LoopDisposition.WAIT: "validated progress but fresh decision does not allow the next turn yet",
        LoopDisposition.REPAIR: "fresh decision requires repair after progress",
        LoopDisposition.USER_ACTION_REQUIRED: "fresh decision projects a concrete user action",
    }[disposition]


def _replan_disposition(
    *, reason: str, decision_lineage: Mapping[str, str]
) -> dict[str, Any]:
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
