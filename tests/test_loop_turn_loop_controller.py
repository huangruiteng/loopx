"""Decision-table tests for the pure Turn Loop Controller transition.

Each row pairs one validated Turn receipt with one fresh quota/scheduler
decision and asserts exactly one typed disposition. The controller must never
launch a host, write state, or spend quota; every row also asserts those
markers.

Receipts are produced through the real
``build_loopx_turn_transaction_plan -> validate_loopx_turn_receipt`` path so
the controller consumes only proven ``loopx_turn_receipt_validation_v0``
output, never a caller-forged ``result_kind + lineage`` mapping.
"""

from __future__ import annotations

import pytest

from loopx.control_plane.turn_driver import (
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    LoopXTurnResultKind,
    build_loopx_turn_transaction_plan,
    validate_loopx_turn_receipt,
)
from loopx.control_plane.turn_driver.loop_controller import (
    BOUNDED_TURN_BUDGET_SCHEMA_VERSION,
    LOOP_CONTROLLER_DISPOSITION_SCHEMA_VERSION,
    VALIDATED_TURN_RECEIPT_SCHEMA_VERSION,
    BoundedTurnBudget,
    ValidatedTurnReceipt,
    decide_loop_disposition,
)


def _lineage(
    *,
    goal_id: str = "goal-1",
    agent_id: str = "agent-1",
    todo_id: str = "todo-1",
) -> dict[str, str]:
    return {"goal_id": goal_id, "agent_id": agent_id, "todo_id": todo_id}


def _plan(lineage: dict[str, str] | None = None) -> dict[str, object]:
    return build_loopx_turn_transaction_plan(
        planned=True,
        lineage=_lineage() if lineage is None else lineage,
        host="codex-cli",
        execution_mode="interactive-visible",
        session_action="resume",
    )


def _result(
    plan: dict[str, object],
    *,
    result_kind: LoopXTurnResultKind = LoopXTurnResultKind.VALIDATED_PROGRESS,
    completed_phases: list[str] | None = None,
    failed_phase: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
        "turn_key": plan["turn_key"],
        "result_kind": result_kind.value,
        "completed_phases": (
            completed_phases
            if completed_phases is not None
            else ["host_execute", "typed_result", "validation"]
        ),
    }
    if failed_phase:
        result["failed_phase"] = failed_phase
    return result


_FAILURE_PHASES = {
    LoopXTurnResultKind.HOST_FAILURE: ([], "host_execute"),
    LoopXTurnResultKind.VALIDATION_FAILED: (
        ["host_execute", "typed_result"],
        "validation",
    ),
    LoopXTurnResultKind.WRITEBACK_FAILED: (
        ["host_execute", "typed_result", "validation"],
        "durable_writeback",
    ),
    LoopXTurnResultKind.QUOTA_SPEND_FAILED: (
        ["host_execute", "typed_result", "validation", "durable_writeback"],
        "quota_spend",
    ),
}
_STOP_KINDS = {LoopXTurnResultKind.WAIT, LoopXTurnResultKind.USER_ACTION_REQUIRED}


def _validated_receipt(
    *,
    result_kind: LoopXTurnResultKind = LoopXTurnResultKind.VALIDATED_PROGRESS,
    lineage: dict[str, str] | None = None,
    completed_phases: list[str] | None = None,
    failed_phase: str | None = None,
) -> ValidatedTurnReceipt:
    plan = _plan(lineage=lineage)
    if completed_phases is None and result_kind in _FAILURE_PHASES:
        completed_phases, failed_phase = _FAILURE_PHASES[result_kind]
    elif completed_phases is None and result_kind in _STOP_KINDS:
        completed_phases = ["host_execute", "typed_result"]
    result = _result(
        plan,
        result_kind=result_kind,
        completed_phases=completed_phases,
        failed_phase=failed_phase,
    )
    validation = validate_loopx_turn_receipt(plan, result)
    assert validation["ok"] is True, validation
    return ValidatedTurnReceipt.from_validation_result(validation)


def _envelope(
    *,
    should_run: bool,
    effective_action: str = "deliver",
    delivery_allowed: bool = True,
    must_attempt: bool = True,
    user_action_required: bool = False,
    quiet_noop_allowed: bool = False,
    lineage: dict[str, str] | None = None,
    signature_matches: bool = True,
) -> dict[str, object]:
    lin = _lineage() if lineage is None else lineage
    signature: dict[str, object] = {"matches": signature_matches}
    if signature_matches:
        signature["source_hash"] = "sha256:test"
        signature["envelope_hash"] = "sha256:test"
    return {
        "schema_version": "loopx_turn_envelope_v0",
        "goal_id": lin["goal_id"],
        "agent_id": lin["agent_id"],
        "should_run": should_run,
        "effective_action": effective_action,
        "action_signature": signature,
        "compaction": {"within_budget": True},
        "action": {
            "delivery_allowed": delivery_allowed,
            "must_attempt": must_attempt,
            "quiet_noop_allowed": quiet_noop_allowed,
            "selected_todo": {"todo_id": lin["todo_id"]},
        },
        "user": {"action_required": user_action_required},
    }


def _budget(
    *,
    max_turns: int = 3,
    completed_turns: int = 1,
    lineage: dict[str, str] | None = None,
) -> BoundedTurnBudget:
    return BoundedTurnBudget(
        lineage=_lineage() if lineage is None else lineage,
        max_turns=max_turns,
        completed_turns=completed_turns,
    )


def _assert_markers(payload: dict[str, object], disposition: str) -> None:
    assert payload["schema_version"] == LOOP_CONTROLLER_DISPOSITION_SCHEMA_VERSION
    assert payload["disposition"] == disposition
    assert payload["spends_quota"] is False
    assert payload["launches_host"] is False
    assert payload["writes_state"] is False


def test_no_receipt_with_delivery_decision_runs_now() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "run_now")


def test_no_receipt_with_quiet_decision_waits_no_spend() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=_envelope(should_run=False, quiet_noop_allowed=True),
    )
    _assert_markers(payload, "wait")


def test_validated_completion_is_terminal() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(
            result_kind=LoopXTurnResultKind.VALIDATED_COMPLETION
        ),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "terminal")


def test_validated_progress_with_budget_runs_now() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS),
        quota_decision=_envelope(should_run=True),
        bounded_turn_budget=_budget(max_turns=3, completed_turns=1),
    )
    _assert_markers(payload, "run_now")


def test_validated_progress_with_exhausted_budget_is_terminal() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS),
        quota_decision=_envelope(should_run=True),
        bounded_turn_budget=_budget(max_turns=3, completed_turns=3),
    )
    _assert_markers(payload, "terminal")
    assert "budget" in str(payload["reason"])


def test_validated_progress_without_delivery_decision_waits() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS),
        quota_decision=_envelope(should_run=False, quiet_noop_allowed=True),
        bounded_turn_budget=_budget(max_turns=3, completed_turns=1),
    )
    _assert_markers(payload, "wait")


def test_validated_progress_without_bounded_budget_raises() -> None:
    with pytest.raises(ValueError, match="bounded turn budget"):
        decide_loop_disposition(
            turn_receipt=_validated_receipt(
                result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS
            ),
            quota_decision=_envelope(should_run=True),
        )


def test_repair_receipt_routes_to_repair() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.REPAIR_REQUIRED),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "repair")


def test_replan_receipt_requires_bounded_delta_before_successor() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.REPLAN_REQUIRED),
        quota_decision=_envelope(should_run=True, effective_action="autonomous_replan"),
    )
    _assert_markers(payload, "replan")
    continuation = payload["replan_continuation"]
    assert continuation["requires_bounded_delta"] is True
    assert continuation["stale_todo_rerun_allowed"] is False
    assert continuation["fresh_envelope_required"] is True
    assert "todo_delta" in continuation["delta_kinds"]


def test_replan_decision_without_receipt_also_requires_delta() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=_envelope(
            should_run=True, effective_action="autonomous_replan_required"
        ),
    )
    _assert_markers(payload, "replan")
    assert payload["replan_continuation"]["stale_todo_rerun_allowed"] is False


def test_user_action_from_receipt_wins() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(
            result_kind=LoopXTurnResultKind.USER_ACTION_REQUIRED
        ),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "user_action_required")


def test_user_action_from_decision_wins_even_with_receipt() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS),
        quota_decision=_envelope(should_run=True, user_action_required=True),
        bounded_turn_budget=_budget(max_turns=3, completed_turns=1),
    )
    _assert_markers(payload, "user_action_required")


def test_validated_completion_wins_over_decision_user_action() -> None:
    # Precedence: a met terminal postcondition is stronger than a decision-only
    # user action, but only after the receipt is proven valid and fresh.
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(
            result_kind=LoopXTurnResultKind.VALIDATED_COMPLETION
        ),
        quota_decision=_envelope(should_run=True, user_action_required=True),
    )
    _assert_markers(payload, "terminal")
    assert "validated completion" in str(payload["reason"])


def test_wait_receipt_waits() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=LoopXTurnResultKind.WAIT),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "wait")


@pytest.mark.parametrize(
    "failure_kind",
    ["host_failure", "validation_failed", "writeback_failed", "quota_spend_failed"],
)
def test_failure_receipts_route_to_repair(failure_kind: str) -> None:
    kind = LoopXTurnResultKind(failure_kind)
    payload = decide_loop_disposition(
        turn_receipt=_validated_receipt(result_kind=kind),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "repair")
    assert failure_kind in str(payload["reason"])


def test_stale_todo_receipt_raises_not_terminal() -> None:
    # A stale todo_id completion must not terminate a newly selected todo.
    receipt = _validated_receipt(
        result_kind=LoopXTurnResultKind.VALIDATED_COMPLETION,
        lineage=_lineage(todo_id="todo-old"),
    )
    with pytest.raises(ValueError, match="stale_receipt"):
        decide_loop_disposition(
            turn_receipt=receipt,
            quota_decision=_envelope(should_run=True, lineage=_lineage(todo_id="todo-new")),
        )


def test_stale_agent_receipt_raises() -> None:
    receipt = _validated_receipt(
        result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS,
        lineage=_lineage(agent_id="agent-2"),
    )
    with pytest.raises(ValueError, match="stale_receipt"):
        decide_loop_disposition(
            turn_receipt=receipt,
            quota_decision=_envelope(should_run=True, lineage=_lineage(agent_id="agent-1")),
        )


def test_forged_completion_mapping_cannot_construct_receipt() -> None:
    # A caller-authored result_kind + lineage mapping must not be enough to
    # prove completion.
    with pytest.raises(ValueError, match="schema_version"):
        ValidatedTurnReceipt.from_validation_result(
            {
                "result_kind": "validated_completion",
                "lineage": _lineage(),
            }
        )


def test_receipt_requires_ok_true() -> None:
    with pytest.raises(ValueError, match="ok=true"):
        ValidatedTurnReceipt.from_validation_result(
            {
                "schema_version": "loopx_turn_receipt_validation_v0",
                "ok": False,
                "result_kind": "validated_progress",
                "lineage": _lineage(),
            }
        )


def test_malformed_decision_raises() -> None:
    with pytest.raises(ValueError, match="envelope contract"):
        decide_loop_disposition(
            turn_receipt=None,
            quota_decision={"schema_version": "not_an_envelope"},
        )


def test_marker_only_signature_raises() -> None:
    envelope = _envelope(should_run=True)
    envelope["action_signature"] = {"matches": True}
    with pytest.raises(ValueError, match="envelope contract"):
        decide_loop_disposition(turn_receipt=None, quota_decision=envelope)


def test_mismatched_signature_hashes_raise() -> None:
    envelope = _envelope(should_run=True)
    envelope["action_signature"] = {
        "matches": True,
        "source_hash": "sha256:a",
        "envelope_hash": "sha256:b",
    }
    with pytest.raises(ValueError, match="envelope contract"):
        decide_loop_disposition(turn_receipt=None, quota_decision=envelope)


def test_over_budget_compaction_raises() -> None:
    envelope = _envelope(should_run=True)
    envelope["compaction"] = {"within_budget": False}
    with pytest.raises(ValueError, match="envelope contract"):
        decide_loop_disposition(turn_receipt=None, quota_decision=envelope)


def test_mismatched_signature_raises() -> None:
    with pytest.raises(ValueError, match="envelope contract"):
        decide_loop_disposition(
            turn_receipt=None,
            quota_decision=_envelope(should_run=True, signature_matches=False),
        )


def test_repair_decision_routes_to_repair() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=_envelope(should_run=True, effective_action="workspace_repair"),
    )
    _assert_markers(payload, "repair")


def test_delivery_blocked_decision_waits() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=_envelope(should_run=True, delivery_allowed=False),
    )
    _assert_markers(payload, "wait")


def test_disposition_enum_has_exactly_six_values() -> None:
    from loopx.control_plane.turn_driver.loop_controller import LoopDisposition

    assert {d.value for d in LoopDisposition} == {
        "run_now",
        "wait",
        "user_action_required",
        "repair",
        "replan",
        "terminal",
    }


def test_budget_rejects_booleans() -> None:
    with pytest.raises(ValueError, match="max_turns must be an int"):
        BoundedTurnBudget(lineage=_lineage(), max_turns=True, completed_turns=0)
    with pytest.raises(ValueError, match="completed_turns must be an int"):
        BoundedTurnBudget(lineage=_lineage(), max_turns=3, completed_turns=False)


@pytest.mark.parametrize(
    "max_turns,completed_turns",
    [
        (0, 0),
        (-1, 0),
        (3, -1),
        (3, 4),
    ],
)
def test_budget_rejects_invalid_ranges(max_turns: int, completed_turns: int) -> None:
    with pytest.raises(ValueError):
        BoundedTurnBudget(
            lineage=_lineage(),
            max_turns=max_turns,
            completed_turns=completed_turns,
        )


def test_budget_requires_lineage() -> None:
    with pytest.raises(ValueError, match="lineage"):
        BoundedTurnBudget(lineage={}, max_turns=3, completed_turns=0)


def test_stale_budget_lineage_raises() -> None:
    receipt = _validated_receipt(result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS)
    with pytest.raises(ValueError, match="stale_receipt"):
        decide_loop_disposition(
            turn_receipt=receipt,
            quota_decision=_envelope(should_run=True),
            bounded_turn_budget=_budget(lineage=_lineage(agent_id="agent-2")),
        )


def test_validated_receipt_carries_lineage_from_plan() -> None:
    receipt = _validated_receipt(
        result_kind=LoopXTurnResultKind.VALIDATED_PROGRESS,
        lineage=_lineage(goal_id="goal-x", agent_id="agent-y", todo_id="todo-z"),
    )
    assert receipt.lineage == {
        "goal_id": "goal-x",
        "agent_id": "agent-y",
        "todo_id": "todo-z",
    }


def test_budget_schema_version() -> None:
    assert _budget().to_mapping()["schema_version"] == BOUNDED_TURN_BUDGET_SCHEMA_VERSION


def test_validated_receipt_schema_version() -> None:
    assert (
        _validated_receipt().to_mapping()["schema_version"]
        == VALIDATED_TURN_RECEIPT_SCHEMA_VERSION
    )
