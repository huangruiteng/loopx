from __future__ import annotations

from typing import Any

from ..todos.contract import TODO_TASK_CLASS_USER_ACTION
from ..todos.todo_semantics import todo_item_task_class


def user_action_owns_empty_agent_lane(payload: dict[str, Any]) -> bool:
    """Return whether a user-action notice is the lane's only remaining work.

    Selected control-plane obligations count as agent work even when they
    intentionally forbid material delivery.
    """

    execution_obligation = payload.get("execution_obligation")
    if (
        isinstance(execution_obligation, dict)
        and execution_obligation.get("must_attempt_work") is True
    ):
        return False
    return user_action_owns_empty_agent_lane_from_summaries(
        payload.get("user_todo_summary"),
        payload.get("agent_todo_summary"),
    )


def user_action_owns_empty_agent_lane_from_summaries(
    user_summary: Any,
    agent_summary: Any,
) -> bool:
    if not isinstance(user_summary, dict) or not isinstance(agent_summary, dict):
        return False
    user_items = user_summary.get("user_action_items")
    if not isinstance(user_items, list):
        user_items = user_summary.get("first_open_items")
    if not isinstance(user_items, list):
        return False
    has_open_user_action = any(
        isinstance(item, dict)
        and not item.get("done")
        and str(item.get("status") or "open").strip().lower()
        in {"", "open", "todo", "active", "pending"}
        and todo_item_task_class(item) == TODO_TASK_CLASS_USER_ACTION
        for item in user_items
    )
    if not has_open_user_action:
        return False
    first_executable = agent_summary.get("first_executable_items")
    return not (isinstance(first_executable, list) and first_executable)
