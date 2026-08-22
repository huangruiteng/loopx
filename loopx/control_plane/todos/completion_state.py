"""Python compatibility facade for TypeScript-owned Todo completion state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Any, Mapping

from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result


TODO_COMPLETION_STATE_REQUEST_SCHEMA = "loopx_todo_completion_state_request_v0"
TODO_COMPLETION_STATE_RESULT_SCHEMA = "loopx_todo_completion_state_result_v0"


class TodoCompletionContinuation(str, Enum):
    """Stable Python import compatibility for the persisted wire values."""

    ACTIVE_GOAL = "active_goal"
    SUCCESSOR = "successor"
    NO_FOLLOWUP = "no_followup"


class TodoCompletionRecovery(str, Enum):
    """Stable Python import compatibility for the persisted wire value."""

    SAME_TURN_TERMINAL_CLOSEOUT = "same_turn_terminal_closeout"
    LIFECYCLE_REENTRY_TERMINAL_CLOSEOUT = "lifecycle_reentry_terminal_closeout"


def _string_value(value: Any) -> str:
    return str(value or "")


def _no_followup_value(value: Any) -> bool | str:
    return value if isinstance(value, bool) else _string_value(value)


def _successor_values(value: Any) -> Any:
    if not value:
        return []
    if isinstance(value, (list, tuple, set, str, Mapping)):
        return list(value)
    return value


def _result(method: str, params: dict[str, Any]) -> Mapping[str, Any]:
    try:
        result = effect_runtime_result(method, params)
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, Mapping):
        raise RuntimeError("TypeScript Todo completion state result must be an object")
    if result.get("schema_version") != TODO_COMPLETION_STATE_RESULT_SCHEMA:
        raise RuntimeError("TypeScript Todo completion state result shape mismatch")
    return result


@lru_cache(maxsize=64)
def _normalize_cached(kind: str, value: bool | str) -> bool | str | None:
    result = _result(
        "todo.completion_state.normalize",
        {
            "schema_version": TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "kind": kind,
            "value": value,
        },
    )
    normalized = result.get("value")
    if kind == "no_followup":
        if normalized is not None and not isinstance(normalized, bool):
            raise RuntimeError("TypeScript no_followup normalization shape mismatch")
    elif normalized is not None and not isinstance(normalized, str):
        raise RuntimeError(
            "TypeScript completion metadata normalization shape mismatch"
        )
    return normalized


def normalize_todo_no_followup(value: Any) -> bool | None:
    normalized = _normalize_cached("no_followup", _no_followup_value(value))
    return normalized if isinstance(normalized, bool) else None


def normalize_todo_completion_continuation(value: Any) -> str | None:
    normalized = _normalize_cached("continuation", _string_value(value))
    return normalized if isinstance(normalized, str) else None


def require_todo_completion_continuation(value: Any) -> str:
    result = _result(
        "todo.completion_state.require_metadata",
        {
            "schema_version": TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "key": "completion_continuation",
            "value": _string_value(value),
        },
    )
    normalized = result.get("value")
    if not isinstance(normalized, str):
        raise RuntimeError("TypeScript completion continuation result shape mismatch")
    return normalized


def normalize_todo_completion_recovery(value: Any) -> str | None:
    normalized = _normalize_cached("recovery", _string_value(value))
    return normalized if isinstance(normalized, str) else None


def require_todo_completion_metadata(key: str, value: Any) -> str | None:
    result = _result(
        "todo.completion_state.require_metadata",
        {
            "schema_version": TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "key": key,
            "value": _string_value(value),
        },
    )
    normalized = result.get("value")
    if normalized is not None and not isinstance(normalized, str):
        raise RuntimeError("TypeScript completion metadata result shape mismatch")
    return normalized


def completion_continuation_for_write(*, no_followup: bool, has_successor: bool) -> str:
    result = _result(
        "todo.completion_state.continuation_for_write",
        {
            "schema_version": TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "no_followup": no_followup,
            "has_successor": has_successor,
        },
    )
    continuation = result.get("continuation")
    if continuation not in {item.value for item in TodoCompletionContinuation}:
        raise RuntimeError("TypeScript completion continuation result shape mismatch")
    return str(continuation)


@dataclass(frozen=True, slots=True)
class TodoCompletionState:
    continuation: str
    recovery: str | None = None


def completion_state_for_todo_write(
    todo: Mapping[str, Any],
    *,
    requested_no_followup: bool,
    has_successor: bool,
    completion_identity_source: str | None = None,
) -> TodoCompletionState:
    result = _result(
        "todo.completion_state.evaluate",
        {
            "schema_version": TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "todo": {
                "status": str(todo.get("status") or ""),
                "no_followup": _no_followup_value(todo.get("no_followup")),
                "completion_continuation": _string_value(
                    todo.get("completion_continuation")
                ),
            },
            "requested_no_followup": requested_no_followup,
            "has_successor": has_successor,
            "completion_identity_source": completion_identity_source,
        },
    )
    continuation = result.get("continuation")
    recovery = result.get("recovery")
    if continuation not in {item.value for item in TodoCompletionContinuation} or (
        recovery is not None
        and recovery not in {item.value for item in TodoCompletionRecovery}
    ):
        raise RuntimeError("TypeScript Todo completion state result shape mismatch")
    return TodoCompletionState(
        continuation=str(continuation),
        recovery=str(recovery) if recovery is not None else None,
    )


def completion_metadata_updates(
    block: Mapping[str, Any],
    *,
    target_status: str,
    normalized_status: str | None,
    completion_continuation: str | None,
    completion_recovery: str | None,
    no_followup: bool | None,
    successor_todo_ids: list[str] | None,
) -> dict[str, Any]:
    result = _result(
        "todo.completion_state.metadata_updates",
        {
            "schema_version": TODO_COMPLETION_STATE_REQUEST_SCHEMA,
            "block": {
                "no_followup": _no_followup_value(block.get("no_followup")),
                "completion_continuation": _string_value(
                    block.get("completion_continuation")
                ),
                "successor_todo_ids": _successor_values(
                    block.get("successor_todo_ids")
                ),
            },
            "target_status": target_status,
            "normalized_status": normalized_status,
            "completion_continuation": completion_continuation,
            "completion_recovery": completion_recovery,
            "no_followup": no_followup,
            "successor_todo_ids": successor_todo_ids,
        },
    )
    updates = result.get("updates")
    if not isinstance(updates, Mapping) or any(
        key not in {"completion_continuation", "completion_recovery"}
        or not isinstance(value, str)
        for key, value in updates.items()
    ):
        raise RuntimeError("TypeScript completion metadata updates shape mismatch")
    return dict(updates)
