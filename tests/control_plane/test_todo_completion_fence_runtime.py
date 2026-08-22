from __future__ import annotations

import pytest

from loopx.control_plane import effect_runtime
from loopx.control_plane.todos import completion_fence


def _runtime_result(**overrides: object) -> dict[str, object]:
    return {
        "schema_version": completion_fence.TODO_COMPLETION_FENCE_RESULT_SCHEMA,
        "outcome": "replay",
        "reason": "already_terminal",
        "status": "done",
        "terminal_before_request": True,
        "completion_continuation": "no_followup",
        **overrides,
    }


def test_python_facade_sends_one_coarse_typed_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def call(method: str, params: dict[str, object]) -> dict[str, object]:
        captured["method"] = method
        captured["params"] = params
        return _runtime_result()

    monkeypatch.setattr(completion_fence, "effect_runtime_result", call)

    result = completion_fence.evaluate_todo_completion_fence(
        todo={
            "status": "done",
            "no_followup": "true",
            "completion_continuation": "no_followup",
            "completion_turn_key": "turn-a",
            "successor_todo_ids": (),
        },
        projection_source="materialized",
        completion_turn_key="turn-a",
        no_followup=True,
    )

    assert result == _runtime_result()
    assert captured["method"] == "todo.completion_fence.evaluate"
    assert captured["params"] == {
        "schema_version": completion_fence.TODO_COMPLETION_FENCE_REQUEST_SCHEMA,
        "projection_source": "materialized",
        "todo": {
            "status": "done",
            "no_followup": "true",
            "completion_continuation": "no_followup",
            "completion_turn_key": "turn-a",
            "successor_todo_ids": [],
        },
        "requested_no_followup": True,
        "requested_completion_turn_key": "turn-a",
        "requested_completion_identity_source": None,
        "goal_id": None,
        "todo_id": None,
    }


def test_python_facade_projects_stable_unscoped_completion_identity() -> None:
    first = completion_fence.local_todo_completion_identity(
        goal_id="goal-example",
        todo_id="todo_local001",
    )
    second = completion_fence.local_todo_completion_identity(
        goal_id="goal-example",
        todo_id="todo_local001",
    )

    assert first == second
    assert first.startswith("local_completion_")


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        _runtime_result(schema_version="loopx_todo_completion_fence_result_v1"),
        _runtime_result(terminal_before_request="true"),
        _runtime_result(completion_continuation=[]),
    ],
)
def test_python_facade_rejects_malformed_runtime_results(
    monkeypatch, malformed: object
) -> None:
    monkeypatch.setattr(
        completion_fence,
        "effect_runtime_result",
        lambda _method, _params: malformed,
    )

    with pytest.raises(RuntimeError, match="result (must be|shape mismatch)"):
        completion_fence.evaluate_todo_completion_fence(
            todo={"status": "open"},
            projection_source="materialized",
            completion_turn_key=None,
            no_followup=False,
        )


def test_python_facade_preserves_typed_rejection_as_value_error(monkeypatch) -> None:
    def reject(_method: str, _params: dict[str, object]) -> object:
        raise effect_runtime.EffectRuntimeRejected("typed fence rejected")

    monkeypatch.setattr(completion_fence, "effect_runtime_result", reject)

    with pytest.raises(ValueError, match="typed fence rejected"):
        completion_fence.evaluate_todo_completion_fence(
            todo={"status": "done"},
            projection_source="materialized",
            completion_turn_key="turn-b",
            no_followup=True,
        )
