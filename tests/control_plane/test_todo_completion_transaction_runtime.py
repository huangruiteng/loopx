from __future__ import annotations

import pytest

from loopx.control_plane import effect_runtime
from loopx.control_plane.todos import completion_transaction


def _commit_result(**overrides: object) -> dict[str, object]:
    return {
        "schema_version": completion_transaction.TODO_COMPLETION_TRANSACTION_RESULT_SCHEMA,
        "decision": "commit",
        "completion_identity_key": "local_completion_0123456789abcdef0123456789abcdef",
        "completion_identity_source": "unscoped_completion",
        "fence": {
            "schema_version": "loopx_todo_completion_fence_result_v0",
            "outcome": "continue",
            "reason": "not_terminal",
            "status": "open",
            "terminal_before_request": False,
            "completion_continuation": None,
        },
        "completion_state": {
            "continuation": "active_goal",
            "recovery": None,
        },
        "metadata_updates": {"completion_continuation": "active_goal"},
        "validation_receipt": None,
        **overrides,
    }


def _completion_policy_result(**overrides: object) -> dict[str, object]:
    return {
        "schema_version": "loopx_todo_completion_policy_result_v0",
        "effective_claimed_by": "agent-a",
        "registered_agents": ["agent-a"],
        "effective_next_claimed_by": "agent-a",
        "effective_next_excluded_agents": [],
        "self_merged": False,
        "linked_successor_id": None,
        **overrides,
    }


def test_python_adapter_sends_one_coarse_transaction(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def call(method: str, params: dict[str, object]) -> dict[str, object]:
        captured["method"] = method
        captured["params"] = params
        return _commit_result()

    monkeypatch.setattr(completion_transaction, "effect_runtime_result", call)
    todo = {
        "status": "open",
        "no_followup": False,
        "completion_continuation": None,
        "completion_turn_key": None,
        "successor_todo_ids": (),
        "validation_command": None,
        "validation_command_argv": None,
        "validation_label": None,
        "validation_timeout_seconds": None,
    }

    result = completion_transaction.reduce_todo_completion_transaction(
        todo=todo,
        projection_source="materialized",
        goal_id="goal-example",
        todo_id="todo_example001",
        completion_turn_key=None,
        completion_identity_source=None,
        no_followup=False,
        requested_has_successor=False,
        dry_run=False,
    )

    assert result == _commit_result()
    assert captured == {
        "method": "todo.completion.reduce",
        "params": {
            "schema_version": completion_transaction.TODO_COMPLETION_TRANSACTION_REQUEST_SCHEMA,
            "goal_id": "goal-example",
            "todo_id": "todo_example001",
            "projection_source": "materialized",
            "todo": completion_transaction.todo_completion_source_snapshot(todo),
            "requested_no_followup": False,
            "requested_completion_turn_key": None,
            "requested_completion_identity_source": None,
            "requested_has_successor": False,
            "dry_run": False,
            "validation_receipt": None,
        },
    }


def test_source_snapshot_detects_completion_authority_drift() -> None:
    todo = {
        "status": "open",
        "validation_command": "python -m pytest",
        "successor_todo_ids": [],
    }
    snapshot = completion_transaction.todo_completion_source_snapshot(todo)

    assert completion_transaction.todo_completion_source_matches(snapshot, todo)
    assert not completion_transaction.todo_completion_source_matches(
        snapshot,
        {**todo, "validation_command": "python -m pytest -q"},
    )


def test_python_adapter_requires_requested_completion_policy_projection(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    policy_request = {
        "schema_version": "loopx_todo_completion_policy_request_v0",
        "goal_id": "goal-example",
    }

    def call(method: str, params: dict[str, object]) -> dict[str, object]:
        captured["method"] = method
        captured["params"] = params
        return _commit_result(completion_policy=_completion_policy_result())

    monkeypatch.setattr(completion_transaction, "effect_runtime_result", call)
    result = completion_transaction.reduce_todo_completion_transaction(
        todo={"status": "open"},
        projection_source="materialized",
        goal_id="goal-example",
        todo_id="todo_example001",
        completion_turn_key=None,
        completion_identity_source=None,
        no_followup=False,
        requested_has_successor=True,
        dry_run=False,
        completion_policy_request=policy_request,
    )

    assert result["completion_policy"] == _completion_policy_result()
    assert captured["params"]["completion_policy_request"] == policy_request

    monkeypatch.setattr(
        completion_transaction,
        "effect_runtime_result",
        lambda _method, _params: _commit_result(),
    )
    with pytest.raises(RuntimeError, match="result shape mismatch"):
        completion_transaction.reduce_todo_completion_transaction(
            todo={"status": "open"},
            projection_source="materialized",
            goal_id="goal-example",
            todo_id="todo_example001",
            completion_turn_key=None,
            completion_identity_source=None,
            no_followup=False,
            requested_has_successor=True,
            dry_run=False,
            completion_policy_request=policy_request,
        )


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        _commit_result(decision="continue"),
        _commit_result(completion_identity_key=[]),
        _commit_result(completion_state={"continuation": "implicit", "recovery": None}),
        _commit_result(metadata_updates={"completion_continuation": 3}),
    ],
)
def test_python_adapter_rejects_malformed_runtime_results(
    monkeypatch, malformed: object
) -> None:
    monkeypatch.setattr(
        completion_transaction,
        "effect_runtime_result",
        lambda _method, _params: malformed,
    )

    with pytest.raises(RuntimeError, match="result (must be|shape mismatch)"):
        completion_transaction.reduce_todo_completion_transaction(
            todo={"status": "open"},
            projection_source="materialized",
            goal_id="goal-example",
            todo_id="todo_example001",
            completion_turn_key=None,
            completion_identity_source=None,
            no_followup=False,
            requested_has_successor=False,
            dry_run=False,
        )


def test_python_adapter_preserves_typed_rejection(monkeypatch) -> None:
    def reject(_method: str, _params: dict[str, object]) -> object:
        raise effect_runtime.EffectRuntimeRejected("typed transaction rejected")

    monkeypatch.setattr(completion_transaction, "effect_runtime_result", reject)

    with pytest.raises(ValueError, match="typed transaction rejected"):
        completion_transaction.reduce_todo_completion_transaction(
            todo={"status": "open"},
            projection_source="materialized",
            goal_id="goal-example",
            todo_id="todo_example001",
            completion_turn_key=None,
            completion_identity_source=None,
            no_followup=False,
            requested_has_successor=False,
            dry_run=False,
        )
