"""Decision-table tests for the pure Turn Loop Controller transition.

Each row pairs one Turn receipt with one fresh quota/scheduler decision and
asserts exactly one typed disposition. The controller must never launch a
host, write state, or spend quota; every row also asserts those markers.
"""

from __future__ import annotations

import pytest

from loopx.control_plane.turn_driver.loop_controller import (
    LOOP_CONTROLLER_DISPOSITION_SCHEMA_VERSION,
    decide_loop_disposition,
)


def _envelope(
    *,
    should_run: bool,
    effective_action: str = "deliver",
    delivery_allowed: bool = True,
    must_attempt: bool = True,
    user_action_required: bool = False,
    quiet_noop_allowed: bool = False,
    todo_id: str = "todo-1",
    goal_id: str = "goal-1",
    agent_id: str = "agent-1",
    signature_matches: bool = True,
) -> dict[str, object]:
    signature: dict[str, object] = {"matches": signature_matches}
    if signature_matches:
        signature["source_hash"] = "sha256:test"
        signature["envelope_hash"] = "sha256:test"
    return {
        "schema_version": "loopx_turn_envelope_v0",
        "goal_id": goal_id,
        "agent_id": agent_id,
        "should_run": should_run,
        "effective_action": effective_action,
        "action_signature": signature,
        "compaction": {"within_budget": True},
        "action": {
            "delivery_allowed": delivery_allowed,
            "must_attempt": must_attempt,
            "quiet_noop_allowed": quiet_noop_allowed,
            "selected_todo": {"todo_id": todo_id},
        },
        "user": {"action_required": user_action_required},
    }


def _receipt(
    result_kind: str,
    *,
    goal_id: str = "goal-1",
    agent_id: str = "agent-1",
    todo_id: str = "todo-1",
) -> dict[str, object]:
    return {
        "result_kind": result_kind,
        "lineage": {"goal_id": goal_id, "agent_id": agent_id, "todo_id": todo_id},
    }


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
        turn_receipt=_receipt("validated_completion"),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "terminal")


def test_validated_progress_with_budget_runs_now() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_progress"),
        quota_decision=_envelope(should_run=True),
        bounded_turn_budget={"max_turns": 3, "completed_turns": 1},
    )
    _assert_markers(payload, "run_now")


def test_validated_progress_with_exhausted_budget_is_terminal() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_progress"),
        quota_decision=_envelope(should_run=True),
        bounded_turn_budget={"max_turns": 3, "completed_turns": 3},
    )
    _assert_markers(payload, "terminal")
    assert "budget" in str(payload["reason"])


def test_validated_progress_without_delivery_decision_waits() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_progress"),
        quota_decision=_envelope(should_run=False, quiet_noop_allowed=True),
        bounded_turn_budget={"max_turns": 3, "completed_turns": 1},
    )
    _assert_markers(payload, "wait")


def test_validated_progress_without_bounded_budget_fails_closed() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_progress"),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "contract_error")
    assert "bounded turn budget" in str(payload["reason"])


def test_repair_receipt_routes_to_repair() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("repair_required"),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "repair")


def test_replan_receipt_requires_bounded_delta_before_successor() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("replan_required"),
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
        quota_decision=_envelope(should_run=True, effective_action="autonomous_replan_required"),
    )
    _assert_markers(payload, "replan")
    assert payload["replan_continuation"]["stale_todo_rerun_allowed"] is False


def test_user_action_from_receipt_wins() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("user_action_required"),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "user_action_required")


def test_user_action_from_decision_wins_even_with_receipt() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_progress"),
        quota_decision=_envelope(should_run=True, user_action_required=True),
        bounded_turn_budget={"max_turns": 3, "completed_turns": 1},
    )
    _assert_markers(payload, "user_action_required")


def test_validated_completion_wins_over_decision_user_action() -> None:
    # Precedence: a met terminal postcondition is stronger than a decision-only
    # user action, but only after the receipt is proven valid and fresh.
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_completion"),
        quota_decision=_envelope(should_run=True, user_action_required=True),
    )
    _assert_markers(payload, "terminal")
    assert "validated completion" in str(payload["reason"])


def test_wait_receipt_waits() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("wait"),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "wait")


@pytest.mark.parametrize(
    "failure_kind",
    ["host_failure", "validation_failed", "writeback_failed", "quota_spend_failed"],
)
def test_failure_receipts_route_to_repair(failure_kind: str) -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt(failure_kind),
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "repair")
    assert failure_kind in str(payload["reason"])


def test_stale_receipt_lineage_fails_closed_to_contract_error() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_progress", agent_id="agent-2"),
        quota_decision=_envelope(should_run=True, agent_id="agent-1"),
    )
    _assert_markers(payload, "contract_error")
    assert "stale_receipt" in str(payload["reason"])
    assert payload["stale_receipt_lineage"]["agent_id"] == "agent-2"


def test_stale_completion_receipt_fails_closed_not_terminal() -> None:
    payload = decide_loop_disposition(
        turn_receipt=_receipt("validated_completion", agent_id="agent-2"),
        quota_decision=_envelope(should_run=True, agent_id="agent-1"),
    )
    _assert_markers(payload, "contract_error")
    assert "stale_receipt" in str(payload["reason"])


def test_bare_completion_mapping_fails_closed_not_terminal() -> None:
    payload = decide_loop_disposition(
        turn_receipt={"result_kind": "validated_completion"},
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "contract_error")
    assert "lineage" in str(payload["reason"])


def test_malformed_decision_fails_closed_as_contract_error() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision={"schema_version": "not_an_envelope"},
    )
    _assert_markers(payload, "contract_error")


def test_marker_only_signature_fails_closed() -> None:
    envelope = _envelope(should_run=True)
    envelope["action_signature"] = {"matches": True}
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=envelope,
    )
    _assert_markers(payload, "contract_error")


def test_mismatched_signature_hashes_fail_closed() -> None:
    envelope = _envelope(should_run=True)
    envelope["action_signature"] = {
        "matches": True,
        "source_hash": "sha256:a",
        "envelope_hash": "sha256:b",
    }
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=envelope,
    )
    _assert_markers(payload, "contract_error")


def test_over_budget_compaction_fails_closed() -> None:
    envelope = _envelope(should_run=True)
    envelope["compaction"] = {"within_budget": False}
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=envelope,
    )
    _assert_markers(payload, "contract_error")


def test_mismatched_signature_fails_closed() -> None:
    payload = decide_loop_disposition(
        turn_receipt=None,
        quota_decision=_envelope(should_run=True, signature_matches=False),
    )
    _assert_markers(payload, "contract_error")


def test_unknown_receipt_kind_fails_closed() -> None:
    payload = decide_loop_disposition(
        turn_receipt={"result_kind": "made_up_kind"},
        quota_decision=_envelope(should_run=True),
    )
    _assert_markers(payload, "contract_error")


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
