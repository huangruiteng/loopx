from __future__ import annotations

from typing import Any

from ..agents.agent_scope import agent_scope_item_claimed_by_agent_or_unclaimed
from .compact_projection import compact_todo_projection_item
from .contract import (
    TODO_STATUS_OPEN,
    normalize_todo_id,
    normalize_todo_id_list,
)


TODO_SUCCESSION_WARNING_SCHEMA_VERSION = "todo_succession_warning_v0"
TODO_SUCCESSION_WARNING_REASON_CODE = "completed_advancement_without_successor"
TODO_PARENT_SUCCESSOR_ADVISORY_SCHEMA_VERSION = "todo_parent_successor_advisory_v0"


def build_open_parent_successor_advisory(
    *,
    todo_id: Any,
    status: Any,
    successor_todo_ids: Any,
) -> dict[str, Any]:
    """Warn at authoring time that successor links do not suspend an open parent."""

    normalized_todo_id = normalize_todo_id(todo_id)
    normalized_successor_ids = normalize_todo_id_list(successor_todo_ids)
    if status != TODO_STATUS_OPEN or not normalized_todo_id or not normalized_successor_ids:
        return {}
    return {
        "schema_version": TODO_PARENT_SUCCESSOR_ADVISORY_SCHEMA_VERSION,
        "reason_code": "open_parent_remains_runnable_after_successor_link",
        "todo_id": normalized_todo_id,
        "status": TODO_STATUS_OPEN,
        "successor_todo_ids": normalized_successor_ids,
        "successor_semantics": "lineage_only",
        "parent_remains_quota_runnable": True,
        "automatic_transition_applied": False,
        "authoring_decision_required": True,
        "recommended_action": (
            "If the parent has no independent immediate action, explicitly defer it with "
            "resume_when or complete it; otherwise leave it open intentionally."
        ),
    }


def build_todo_succession_warning_lanes(
    summary: dict[str, Any],
    *,
    item_limit: int,
) -> dict[str, Any]:
    warning = summary.get("todo_succession_warning")
    warning = warning if isinstance(warning, dict) else {}
    source_items = (
        warning.get("items")
        if isinstance(warning.get("items"), list)
        else summary.get("completed_without_successor_items")
    )
    items = [
        compact_todo_projection_item(
            item, text=item.get("text"), task_class_text=str(item.get("text") or ""),
            extra_fields=("completion_continuation", "completion_recovery", "completion_turn_key",
                          "done", "succession_tracked", "recommended_action"),
        )
        for item in (source_items or [])
        if isinstance(item, dict)
    ][:item_limit]
    count = warning.get("count", summary.get("completed_without_successor_count"))
    try:
        count = max(0, int(count)) if count is not None else len(items)
    except (TypeError, ValueError):
        count = len(items)
    if count <= 0 and not items:
        return {}

    payload = {
        "schema_version": warning.get(
            "schema_version",
            TODO_SUCCESSION_WARNING_SCHEMA_VERSION,
        ),
        "reason_code": warning.get(
            "reason_code",
            TODO_SUCCESSION_WARNING_REASON_CODE,
        ),
        "count": count,
        "items": items,
        "recommended_action": warning.get(
            "recommended_action",
            (
                "run loopx todo complete --no-follow-up for the completed Todo, "
                "or add/link a successor Todo; do not invent a user gate"
            ),
        ),
    }
    return {
        "completed_without_successor_count": count,
        "completed_without_successor_items": items,
        "todo_succession_warning": payload,
    }


def todo_succession_gap_items(
    summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    """Return current typed succession gaps owned by this agent lane."""

    if not isinstance(summary, dict):
        return []
    raw_warning = summary.get("todo_succession_warning")
    warning = raw_warning if isinstance(raw_warning, dict) else {}
    if warning and warning.get("reason_code") != TODO_SUCCESSION_WARNING_REASON_CODE:
        return []
    warning_items = warning.get("items")
    completed_items = summary.get("completed_without_successor_items")
    source_items = (
        warning_items
        if isinstance(warning_items, list)
        else completed_items
        if isinstance(completed_items, list)
        else []
    )
    items = [item for item in source_items if isinstance(item, dict)]
    if not agent_id:
        return items
    return [
        item
        for item in items
        if agent_scope_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
    ]
