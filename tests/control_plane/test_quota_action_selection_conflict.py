"""An unreconcilable `--todo-id` guard names its own cause and next read."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from loopx.cli_commands.quota import _apply_requested_quota_action_selection_preflight
from loopx.cli_commands.quota_failure_report import quota_failure_payload
from loopx.control_plane.quota.error_codes import (
    QuotaActionSelectionConflictError,
    QuotaActionSelectionConflictKind,
    quota_error_code,
)


REQUESTED_TODO_ID = "todo_requested_selection"
SELECTED_TODO_ID = "todo_projected_selection"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": True,
        "should_run": True,
        "effective_action": "normal_run",
        "selected_todo": None,
        "execution_obligation": {"must_attempt_work": True},
        "interaction_contract": {"agent_channel": {"must_attempt": True}},
    }
    payload.update(overrides)
    return payload


def _raise(payload: dict[str, object]) -> QuotaActionSelectionConflictError:
    with pytest.raises(QuotaActionSelectionConflictError) as raised:
        _apply_requested_quota_action_selection_preflight(
            payload,
            requested_todo_id=REQUESTED_TODO_ID,
            receipt_bound_todo_id=None,
            receipt_bound_replan_obligation_id=None,
        )
    return raised.value


def _qualified_for(todo_id: str) -> dict[str, object]:
    return {
        "schema_version": "action_selection_qualification_v0",
        "state": "qualified",
        "requested_todo_id": REQUESTED_TODO_ID,
        "selected_todo": {"todo_id": todo_id},
    }


def test_conflicting_qualification_names_requested_and_selected_todo() -> None:
    error = _raise(
        _payload(action_selection_qualification=_qualified_for(SELECTED_TODO_ID))
    )

    assert error.kind is QuotaActionSelectionConflictKind.CONFLICT
    assert error.error_code == "quota_action_selection_conflict"
    assert REQUESTED_TODO_ID in str(error)
    assert SELECTED_TODO_ID in str(error)
    assert "qualified" in str(error)
    assert quota_error_code(error) == "quota_action_selection_conflict"


def test_missing_qualification_is_typed_rather_than_unexplained() -> None:
    error = _raise(_payload(selected_todo={"todo_id": SELECTED_TODO_ID}))

    assert error.kind is QuotaActionSelectionConflictKind.UNQUALIFIED
    assert REQUESTED_TODO_ID in str(error)
    assert "no typed action-selection qualification" in str(error)


def test_a_qualified_selection_for_the_requested_todo_is_not_a_conflict() -> None:
    is_conflict = _apply_requested_quota_action_selection_preflight(
        _payload(action_selection_qualification=_qualified_for(REQUESTED_TODO_ID)),
        requested_todo_id=REQUESTED_TODO_ID,
        receipt_bound_todo_id=None,
        receipt_bound_replan_obligation_id=None,
    )

    assert is_conflict is False


def test_failure_payload_reports_the_conflict_instead_of_collection_failure() -> None:
    error = _raise(
        _payload(action_selection_qualification=_qualified_for(SELECTED_TODO_ID))
    )
    args = argparse.Namespace(
        quota_command="should-run",
        goal_id="quota-conflict-fixture",
        agent_id="agent-fixture",
        runtime_root=None,
        verbose=False,
    )

    payload = quota_failure_payload(
        args,
        registry_path=Path("/tmp/quota-conflict-registry.json"),
        runtime_root_arg=None,
        error=error,
    )

    assert payload["error_code"] == "quota_action_selection_conflict"
    assert payload["status"] == "quota_action_selection_conflict"
    assert payload["reason"] != "quota collection failed"
    assert payload["reason"] == str(error)
    assert "heartbeat receipt writeback" not in str(payload["recommended_action"])
    assert payload["action_selection_conflict"] == {
        "kind": "conflict",
        "requested_todo_id": REQUESTED_TODO_ID,
        "selected_todo_id": SELECTED_TODO_ID,
        "qualification_state": "qualified",
    }
