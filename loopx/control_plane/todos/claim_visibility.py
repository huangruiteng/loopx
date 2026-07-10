from __future__ import annotations

from typing import Any

from .contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_claimed_by,
)
from .projection import (
    todo_claimed_visibility_items,
    todo_item_is_actionable_open,
    todo_item_task_class,
    todo_projection_sort_key,
)
from .summary_item import compact_todo_summary_item


TODO_AGENT_CLAIM_SCOPE_SCHEMA_VERSION = "agent_claim_scope_v0"


def _compact_items(
    items: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    return [
        compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        for item in items[:limit]
    ]


def build_agent_claim_scoped_open_items(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
    diagnostic_item_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(agent_identity, dict):
        return open_items, None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return open_items, None

    def claim_bucket(item: dict[str, Any]) -> int:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claimed_by == agent_id:
            return 0
        if not claimed_by:
            return 1
        return 2

    current_agent_items = [item for item in open_items if claim_bucket(item) == 0]
    unclaimed_items = [item for item in open_items if claim_bucket(item) == 1]
    other_agent_claimed_items = [item for item in open_items if claim_bucket(item) == 2]
    selectable_items = sorted(
        [*current_agent_items, *unclaimed_items],
        key=lambda item: (claim_bucket(item), *todo_projection_sort_key(item)),
    )
    other_agent_visibility = todo_claimed_visibility_items(
        other_agent_claimed_items,
        limit=diagnostic_item_limit,
    )
    claim_scope = {
        "schema_version": TODO_AGENT_CLAIM_SCOPE_SCHEMA_VERSION,
        "agent_id": agent_id,
        "agent_model": "peer_v1",
        "selection_order": "current_agent_claimed_then_unclaimed",
        "selectable_open_count": len(selectable_items),
        "current_agent_claimed_open_count": len(current_agent_items),
        "unclaimed_open_count": len(unclaimed_items),
        "other_agent_claimed_open_count": len(other_agent_claimed_items),
        "other_agent_claimed_weight": "diagnostic_only",
        "other_agent_claimed_items": _compact_items(
            other_agent_visibility,
            limit=diagnostic_item_limit,
        ),
        "blocked_claimed_open_count": len(other_agent_claimed_items),
        "blocked_claimed_items": _compact_items(
            other_agent_visibility,
            limit=diagnostic_item_limit,
        ),
    }
    return selectable_items, claim_scope


def build_todo_claim_visibility_lanes(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
    backlog_item_limit: int,
    visibility_lane_limit: int,
) -> dict[str, Any]:
    claimed_items = [
        item
        for item in open_items
        if normalize_todo_claimed_by(item.get("claimed_by"))
    ]
    unclaimed_items = [
        item
        for item in open_items
        if not normalize_todo_claimed_by(item.get("claimed_by"))
    ]
    claimed_advancement_items = [
        item
        for item in claimed_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    claimed_monitor_items = [
        item
        for item in claimed_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]

    lanes: dict[str, Any] = {
        "unclaimed_priority_open_items": _compact_items(
            unclaimed_items,
            limit=backlog_item_limit,
        ),
        "claimed_open_items": _compact_items(
            todo_claimed_visibility_items(claimed_items, limit=visibility_lane_limit),
            limit=visibility_lane_limit,
        ),
        "claimed_advancement_open_items": _compact_items(
            todo_claimed_visibility_items(
                claimed_advancement_items,
                limit=visibility_lane_limit,
            ),
            limit=visibility_lane_limit,
        ),
        "claimed_monitor_open_items": _compact_items(
            todo_claimed_visibility_items(
                claimed_monitor_items,
                limit=visibility_lane_limit,
            ),
            limit=visibility_lane_limit,
        ),
    }
    if claimed_items:
        lanes["claimed_advancement_open_count"] = len(claimed_advancement_items)
        lanes["claimed_monitor_open_count"] = len(claimed_monitor_items)

    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id:
        current_agent_items = [
            item
            for item in claimed_items
            if normalize_todo_claimed_by(item.get("claimed_by")) == agent_id
        ]
        claimed_by_others_items = [
            item
            for item in claimed_items
            if normalize_todo_claimed_by(item.get("claimed_by")) != agent_id
        ]
        current_agent_advancement_items = [
            item
            for item in current_agent_items
            if todo_item_is_actionable_open(item)
            if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
        ]
        current_agent_monitor_items = [
            item
            for item in current_agent_items
            if todo_item_is_actionable_open(item)
            if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
        ]
        lanes.update(
            {
                "current_agent_claimed_open_items": _compact_items(
                    current_agent_items,
                    limit=visibility_lane_limit,
                ),
                "current_agent_claimed_advancement_items": _compact_items(
                    current_agent_advancement_items,
                    limit=visibility_lane_limit,
                ),
                "current_agent_claimed_monitor_items": _compact_items(
                    current_agent_monitor_items,
                    limit=visibility_lane_limit,
                ),
                "claimed_by_others_items": _compact_items(
                    claimed_by_others_items,
                    limit=backlog_item_limit,
                ),
                "current_agent_claimed_open_count": len(current_agent_items),
                "current_agent_claimed_advancement_count": len(
                    current_agent_advancement_items
                ),
                "current_agent_claimed_monitor_count": len(current_agent_monitor_items),
                "claimed_by_others_count": len(claimed_by_others_items),
            }
        )
    return lanes
