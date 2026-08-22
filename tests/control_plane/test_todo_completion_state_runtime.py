from __future__ import annotations

import pytest

from loopx.control_plane import effect_runtime
from loopx.control_plane.todos import completion_state


def _result(**values: object) -> dict[str, object]:
    return {
        "schema_version": completion_state.TODO_COMPLETION_STATE_RESULT_SCHEMA,
        **values,
    }


def test_python_facade_sends_one_typed_state_request(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def call(method: str, params: dict[str, object]) -> dict[str, object]:
        captured["method"] = method
        captured["params"] = params
        return _result(
            continuation="no_followup",
            recovery="same_turn_terminal_closeout",
        )

    monkeypatch.setattr(completion_state, "effect_runtime_result", call)

    state = completion_state.completion_state_for_todo_write(
        {
            "status": "done",
            "no_followup": "false",
            "completion_continuation": "active_goal",
        },
        requested_no_followup=True,
        has_successor=False,
    )

    assert state == completion_state.TodoCompletionState(
        continuation="no_followup",
        recovery="same_turn_terminal_closeout",
    )
    assert captured == {
        "method": "todo.completion_state.evaluate",
        "params": {
            "schema_version": completion_state.TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "todo": {
                "status": "done",
                "no_followup": "false",
                "completion_continuation": "active_goal",
            },
            "requested_no_followup": True,
            "has_successor": False,
            "completion_identity_source": None,
        },
    }


def test_lifecycle_reentry_has_distinct_recovery_receipt() -> None:
    state = completion_state.completion_state_for_todo_write(
        {
            "status": "done",
            "no_followup": "false",
            "completion_continuation": "active_goal",
        },
        requested_no_followup=True,
        has_successor=False,
        completion_identity_source="lifecycle_reentry",
    )

    assert state == completion_state.TodoCompletionState(
        continuation="no_followup",
        recovery="lifecycle_reentry_terminal_closeout",
    )


def test_scalar_normalization_uses_bounded_process_cache(monkeypatch) -> None:
    calls = 0

    def call(_method: str, params: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return _result(kind=params["kind"], value=True)

    completion_state._normalize_cached.cache_clear()
    monkeypatch.setattr(completion_state, "effect_runtime_result", call)

    assert completion_state.normalize_todo_no_followup("YES") is True
    assert completion_state.normalize_todo_no_followup("YES") is True
    assert calls == 1
    completion_state._normalize_cached.cache_clear()


@pytest.mark.parametrize(
    "malformed",
    [
        None,
        {},
        _result(continuation="implicit", recovery=None),
        _result(continuation="active_goal", recovery="best_effort"),
    ],
)
def test_python_facade_rejects_malformed_state_results(
    monkeypatch, malformed: object
) -> None:
    monkeypatch.setattr(
        completion_state,
        "effect_runtime_result",
        lambda _method, _params: malformed,
    )

    with pytest.raises(RuntimeError, match="result (must be|shape mismatch)"):
        completion_state.completion_state_for_todo_write(
            {"status": "open"},
            requested_no_followup=False,
            has_successor=False,
        )


def test_python_facade_preserves_typed_rejection_as_value_error(monkeypatch) -> None:
    def reject(_method: str, _params: dict[str, object]) -> object:
        raise effect_runtime.EffectRuntimeRejected("typed state rejected")

    monkeypatch.setattr(completion_state, "effect_runtime_result", reject)

    with pytest.raises(ValueError, match="typed state rejected"):
        completion_state.completion_continuation_for_write(
            no_followup=True,
            has_successor=True,
        )
