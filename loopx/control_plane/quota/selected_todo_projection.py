from __future__ import annotations

from typing import Any

from ..todos.contract import normalize_todo_id
from ..work_items.primary_action import protocol_action_text


SELECTED_TODO_COMPACT_FIELDS = (
    "todo_id",
    "index",
    "role",
    "priority",
    "status",
    "task_class",
    "action_kind",
    "task_repository",
    "required_write_scopes",
    "claimed_by",
    "bound_agent",
    "goal_bound",
    "blocks_agent",
    "excluded_agents",
    "unblocks_todo_id",
    "next_due_at",
    "expires_at",
)
SELECTED_TODO_AGENT_FIELDS = (
    "agent_id",
    "selected_by",
    "confidence",
    "claim_required_before_work",
)
WORK_LANE_SELECTED_TODO_ITEM_FIELDS = (
    "monitor_due_items",
    "monitor_schedule_gap_items",
    "resume_blocked_by_monitor_items",
)


def selected_todo_projection(
    *,
    agent_lane_next_action: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    agent_scope_frontier: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if (
        isinstance(agent_scope_frontier, dict)
        and agent_scope_frontier.get("action") == "successor_replan_required"
    ):
        candidates = agent_scope_frontier.get("deferred_resume_candidates")
        if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict):
            selected = _compact_selected_todo(
                candidates[0],
                source="agent_scope_frontier.deferred_resume_candidates",
            )
            if selected:
                return selected

    if isinstance(agent_lane_next_action, dict):
        source = str(agent_lane_next_action.get("source") or "agent_lane_next_action")
        selected = _compact_selected_todo(agent_lane_next_action, source=source)
        if selected:
            return selected

    if not isinstance(work_lane_contract, dict):
        return None
    selected_todo_id = normalize_todo_id(work_lane_contract.get("selected_todo_id"))
    if not selected_todo_id:
        return None
    for key in WORK_LANE_SELECTED_TODO_ITEM_FIELDS:
        items = work_lane_contract.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_todo_id = normalize_todo_id(item.get("todo_id") or item.get("id"))
            if item_todo_id != selected_todo_id:
                continue
            selected = _compact_selected_todo(item, source=f"work_lane_contract.{key}")
            if selected:
                return selected
    return {
        "schema_version": "quota_selected_todo_v0",
        "source": "work_lane_contract.selected_todo_id",
        "todo_id": selected_todo_id,
    }


def first_todo_id_from_items(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict):
            continue
        todo_id = normalize_todo_id(item.get("todo_id") or item.get("id"))
        if todo_id:
            return todo_id
    return None


def _compact_selected_todo(
    item: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any] | None:
    todo_id = normalize_todo_id(item.get("todo_id") or item.get("id"))
    text = protocol_action_text(item.get("text"), limit=320)
    if not todo_id and not text:
        return None
    selected: dict[str, Any] = {
        "schema_version": "quota_selected_todo_v0",
        "source": source,
    }
    for key in SELECTED_TODO_COMPACT_FIELDS:
        value = item.get(key)
        if value is not None:
            selected[key] = value
    if todo_id:
        selected["todo_id"] = todo_id
    if text:
        selected["text"] = text
    for key in SELECTED_TODO_AGENT_FIELDS:
        if item.get(key) is not None:
            selected[key] = item.get(key)
    return selected
