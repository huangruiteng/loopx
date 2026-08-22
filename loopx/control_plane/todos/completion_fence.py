from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result


TODO_COMPLETION_FENCE_REQUEST_SCHEMA = "loopx_todo_completion_fence_request_v0"
TODO_COMPLETION_FENCE_RESULT_SCHEMA = "loopx_todo_completion_fence_result_v0"
TODO_COMPLETION_IDENTITY_REQUEST_SCHEMA = "loopx_todo_completion_identity_request_v0"
TODO_COMPLETION_IDENTITY_RESULT_SCHEMA = "loopx_todo_completion_identity_v0"


def local_todo_completion_identity(*, goal_id: str, todo_id: str) -> str:
    """Return the TS-owned stable identity for an unscoped completion."""

    try:
        result = effect_runtime_result(
            "todo.completion_identity.project",
            {
                "schema_version": TODO_COMPLETION_IDENTITY_REQUEST_SCHEMA,
                "goal_id": goal_id,
                "todo_id": todo_id,
            },
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not (
        isinstance(result, Mapping)
        and result.get("schema_version") == TODO_COMPLETION_IDENTITY_RESULT_SCHEMA
        and result.get("identity_source") == "unscoped_completion"
        and isinstance(result.get("completion_identity_key"), str)
        and str(result["completion_identity_key"]).startswith("local_completion_")
    ):
        raise RuntimeError("TypeScript Todo completion identity result shape mismatch")
    return str(result["completion_identity_key"])


def resolve_todo_completion_identity(
    *,
    todo: Mapping[str, Any],
    goal_id: str,
    todo_id: str,
    completion_turn_key: str | None,
    completion_identity_source: str | None,
) -> tuple[str | None, str | None]:
    """Bind an unscoped open completion to its stable local identity."""

    if completion_turn_key is not None or str(todo.get("status") or "") == "done":
        return completion_turn_key, completion_identity_source
    return (
        local_todo_completion_identity(goal_id=goal_id, todo_id=todo_id),
        "unscoped_completion",
    )


def _json_successor_value(value: Any) -> Any:
    if isinstance(value, (tuple, set)):
        return list(value)
    return value


def evaluate_todo_completion_fence(
    *,
    todo: Mapping[str, Any],
    projection_source: str,
    completion_turn_key: str | None,
    no_followup: bool,
    goal_id: str | None = None,
    todo_id: str | None = None,
    completion_identity_source: str | None = None,
) -> dict[str, Any]:
    """Ask the TypeScript Todo owner for the canonical replay-fence decision."""

    raw_no_followup = todo.get("no_followup")
    if raw_no_followup is not None and not isinstance(raw_no_followup, (bool, str)):
        raw_no_followup = str(raw_no_followup)
    raw_continuation = todo.get("completion_continuation")
    if raw_continuation is not None and not isinstance(raw_continuation, str):
        raw_continuation = str(raw_continuation)
    raw_turn_key = todo.get("completion_turn_key")
    if raw_turn_key is not None and not isinstance(raw_turn_key, str):
        raw_turn_key = str(raw_turn_key)
    try:
        result = effect_runtime_result(
            "todo.completion_fence.evaluate",
            {
                "schema_version": TODO_COMPLETION_FENCE_REQUEST_SCHEMA,
                "projection_source": projection_source,
                "todo": {
                    "status": str(todo.get("status") or "open"),
                    "no_followup": raw_no_followup,
                    "completion_continuation": raw_continuation,
                    "completion_turn_key": raw_turn_key,
                    "successor_todo_ids": _json_successor_value(
                        todo.get("successor_todo_ids")
                    ),
                },
                "requested_no_followup": no_followup,
                "requested_completion_turn_key": completion_turn_key,
                "requested_completion_identity_source": completion_identity_source,
                "goal_id": goal_id,
                "todo_id": todo_id,
            },
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, Mapping):
        raise RuntimeError("TypeScript Todo completion fence result must be an object")
    if (
        result.get("schema_version") != TODO_COMPLETION_FENCE_RESULT_SCHEMA
        or result.get("outcome") not in {"continue", "replay"}
        or not isinstance(result.get("reason"), str)
        or not isinstance(result.get("status"), str)
        or not isinstance(result.get("terminal_before_request"), bool)
        or not (
            result.get("completion_continuation") is None
            or isinstance(result.get("completion_continuation"), str)
        )
    ):
        raise RuntimeError("TypeScript Todo completion fence result shape mismatch")
    return dict(result)


def completed_todo_replay(
    *,
    todo: Mapping[str, Any],
    goal_id: str,
    todo_id: str,
    completion_turn_key: str | None,
    completion_identity_source: str | None,
    no_followup: bool,
    handoff_mode: str,
    mutation_authority: dict[str, Any],
    state_file: str,
    project: str | None,
    dry_run: bool,
) -> dict[str, Any] | None:
    """Project a typed TS replay decision into the legacy Python response.

    ``handoff_mode`` is the currently resolved goal mode, not a persisted copy
    of the original completion result. This local replay therefore is not a
    durable operation receipt and must not be presented as Stage 2 proof.
    Original effect markers such as a lease fence or handoff-gate override are
    intentionally absent because this branch performs neither effect. A
    same-turn request may return ``None`` only to append the missing terminal
    no-follow-up state; it cannot replace a successor or cross a turn fence.
    """

    # This fast path runs before the caller selects the event writer. Treat it
    # as a materialized projection; an event-only deferred Todo falls through
    # and is evaluated with ``projection_source=event_log`` by that writer.
    fence = evaluate_todo_completion_fence(
        todo=todo,
        projection_source="materialized",
        completion_turn_key=completion_turn_key,
        no_followup=no_followup,
        goal_id=goal_id,
        todo_id=todo_id,
        completion_identity_source=completion_identity_source,
    )

    # Event-projected deferred rows must pass through the event writer so the
    # existing lease-fence receipt remains visible. Done rows preserve the
    # earlier fast replay path for both projection sources.
    if fence.get("outcome") != "replay" or fence.get("status") != "done":
        return None
    return {
        "ok": True,
        "dry_run": dry_run,
        "completed": True,
        "idempotent_replay": True,
        "changed": False,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "status": "done",
        "completion_continuation": fence.get("completion_continuation"),
        "completion_recovery": todo.get("completion_recovery"),
        "handoff_mode": handoff_mode,
        "mutation_authority": mutation_authority,
        "state_file": state_file,
        "project": project,
    }
