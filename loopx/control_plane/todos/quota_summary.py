from __future__ import annotations

from typing import Any

from ..agents.agent_scope import (
    _agent_scope_filter_user_gate_items,
    _agent_scope_selectable_todo_item,
)
from .claim_visibility import (
    build_agent_claim_scoped_open_items,
    build_todo_claim_visibility_lanes,
)
from .contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
)
from .deferred_resume import (
    build_todo_deferred_visibility_lanes,
    build_todo_resume_blocked_visibility_lanes,
)
from .handoff_gate import build_todo_handoff_gate_lanes
from .projection import (
    todo_item_is_actionable_open,
    todo_item_is_due_monitor,
    todo_item_task_class,
    todo_projection_sort_key,
    todo_summary_monitor_schedule_gap_items,
    todo_summary_monitor_writeback_contract,
    todo_summary_monitor_writeback_supported,
)
from .route_continuation import build_todo_route_continuation_lanes
from .succession_warning import build_todo_succession_warning_lanes
from .summary_item import compact_todo_summary_item, todo_summary_source_items


MONITOR_DUE_ITEM_LIMIT = 1
TODO_BACKLOG_ITEM_LIMIT = 8
TODO_DEFERRED_VISIBILITY_LIMIT = 8
TODO_VISIBILITY_LANE_LIMIT = 16

USER_GATE_ACTION_KIND_HINTS = (
    "approval",
    "approve",
    "boundary",
    "gate",
    "blocker",
    "credential",
    "private",
    "production",
    "leaderboard",
    "submission",
    "public_claim",
)


def is_user_gate_todo_item(item: dict[str, Any]) -> bool:
    if todo_item_task_class(item) == TODO_TASK_CLASS_USER_GATE:
        return True
    action_kind = str(item.get("action_kind") or "").strip().lower()
    if not action_kind:
        return False
    return any(hint in action_kind for hint in USER_GATE_ACTION_KIND_HINTS)


def summarize_user_todos_for_quota(
    value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    all_open_items = sorted(
        todo_summary_source_items(value),
        key=todo_projection_sort_key,
    )
    blocking_open_items = all_open_items
    other_agent_scoped_items: list[dict[str, Any]] = []
    agent_scope_filter: dict[str, Any] | None = None
    if filter_user_gate_blocks_agent:
        (
            blocking_open_items,
            other_agent_scoped_items,
            agent_scope_filter,
        ) = _agent_scope_filter_user_gate_items(
            all_open_items,
            agent_identity=agent_identity,
        )
    open_items, claim_scope = build_agent_claim_scoped_open_items(
        blocking_open_items,
        agent_identity=agent_identity,
        diagnostic_item_limit=3,
    )
    executable_items = [
        item
        for item in open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    monitor_items = [
        item
        for item in open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_writeback_supported = todo_summary_monitor_writeback_supported(value)
    monitor_due_items = (
        [
            item
            for item in monitor_items
            if todo_item_is_due_monitor(item)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if monitor_writeback_supported
        else []
    )
    monitor_schedule_gap_items = todo_summary_monitor_schedule_gap_items(
        {
            "monitor_open_items": monitor_items,
            "monitor_writeback": value.get("monitor_writeback"),
        }
    )
    claimed_open_items = [item for item in blocking_open_items if item.get("claimed_by")]
    gate_items = [
        item
        for item in open_items
        if is_user_gate_todo_item(item)
    ]
    active_next_action_items = (
        [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in (value.get("active_next_action_items") or [])
            if isinstance(item, dict)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if isinstance(value.get("active_next_action_items"), list)
        else []
    )
    active_next_action_executable_items = (
        [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in (value.get("active_next_action_executable_items") or [])
            if isinstance(item, dict)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if isinstance(value.get("active_next_action_executable_items"), list)
        else []
    )
    open_count = value.get("open_count", len(all_open_items))
    if claim_scope is not None:
        open_count = len(open_items)
    if agent_scope_filter is not None:
        open_count = len(blocking_open_items)
    summary = {
        "schema_version": value.get("schema_version"),
        "source_section": value.get("source_section"),
        "total_count": value.get("total_count"),
        "open_count": open_count,
        "done_count": value.get("done_count"),
        "first_open_items": open_items[:3],
        "first_executable_items": executable_items[:3],
        "gate_open_items": gate_items[:3],
        "monitor_open_items": monitor_items,
        "monitor_due_count": len(monitor_due_items),
        "monitor_due_items": monitor_due_items[:MONITOR_DUE_ITEM_LIMIT],
        "monitor_schedule_gap_count": len(monitor_schedule_gap_items),
        "monitor_schedule_gap_items": monitor_schedule_gap_items[:MONITOR_DUE_ITEM_LIMIT],
        "active_next_action_items": active_next_action_items,
        "active_next_action_executable_items": active_next_action_executable_items,
        "backlog_items": open_items[:TODO_BACKLOG_ITEM_LIMIT],
        "executable_backlog_items": executable_items[:TODO_BACKLOG_ITEM_LIMIT],
    }
    monitor_writeback = todo_summary_monitor_writeback_contract(value)
    if monitor_writeback:
        summary["monitor_writeback"] = monitor_writeback
    summary.update(
        build_todo_claim_visibility_lanes(
            blocking_open_items,
            agent_identity=agent_identity,
            backlog_item_limit=TODO_BACKLOG_ITEM_LIMIT,
            visibility_lane_limit=TODO_VISIBILITY_LANE_LIMIT,
        )
    )
    summary.update(
        build_todo_deferred_visibility_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_DEFERRED_VISIBILITY_LIMIT,
        )
    )
    summary.update(
        build_todo_resume_blocked_visibility_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_DEFERRED_VISIBILITY_LIMIT,
        )
    )
    summary.update(
        build_todo_handoff_gate_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    summary.update(
        build_todo_route_continuation_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    summary.update(
        build_todo_succession_warning_lanes(
            value,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    if claimed_open_items or value.get("claimed_open_count"):
        summary["claimed_open_count"] = value.get("claimed_open_count", len(claimed_open_items))
        summary["unclaimed_open_count"] = value.get(
            "unclaimed_open_count",
            max(0, int(open_count or 0) - len(claimed_open_items)),
        )
    if claim_scope:
        summary["claim_scope"] = claim_scope
    if agent_scope_filter:
        summary["agent_scope_filter"] = agent_scope_filter
        summary["all_open_count"] = value.get("open_count", len(all_open_items))
        summary["other_agent_scoped_open_count"] = len(other_agent_scoped_items)
        summary["other_agent_scoped_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in other_agent_scoped_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    return summary


def summarize_project_asset_todos_for_quota(
    value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("items"), list)
        or isinstance(value.get("first_open_items"), list)
    ) and (
        "total_count" in value or "open_count" in value or "done_count" in value
    ):
        return summarize_user_todos_for_quota(
            value,
            agent_identity=agent_identity,
            filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
        )

    all_open_items = sorted(
        todo_summary_source_items(value),
        key=todo_projection_sort_key,
    )
    if not all_open_items:
        next_text = str(value.get("next") or "").strip()
        next_index = value.get("next_index", 1)
        all_open_items = [{"index": next_index, "text": next_text}] if next_text else []
        next_claimed_by = str(value.get("next_claimed_by") or "").strip()
        if all_open_items and next_claimed_by:
            all_open_items[0]["claimed_by"] = next_claimed_by
    blocking_open_items = all_open_items
    other_agent_scoped_items: list[dict[str, Any]] = []
    agent_scope_filter: dict[str, Any] | None = None
    if filter_user_gate_blocks_agent:
        (
            blocking_open_items,
            other_agent_scoped_items,
            agent_scope_filter,
        ) = _agent_scope_filter_user_gate_items(
            all_open_items,
            agent_identity=agent_identity,
        )
    open_items, claim_scope = build_agent_claim_scoped_open_items(
        blocking_open_items,
        agent_identity=agent_identity,
        diagnostic_item_limit=3,
    )
    executable_items = [
        item
        for item in open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    monitor_items = [
        item
        for item in open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_writeback_supported = todo_summary_monitor_writeback_supported(value)
    monitor_due_items = (
        [
            item
            for item in monitor_items
            if todo_item_is_due_monitor(item)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if monitor_writeback_supported
        else []
    )
    active_next_action_items = (
        [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in (value.get("active_next_action_items") or [])
            if isinstance(item, dict)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if isinstance(value.get("active_next_action_items"), list)
        else []
    )
    active_next_action_executable_items = (
        [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in (value.get("active_next_action_executable_items") or [])
            if isinstance(item, dict)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if isinstance(value.get("active_next_action_executable_items"), list)
        else []
    )
    claimed_open_items = [item for item in blocking_open_items if item.get("claimed_by")]
    open_count = value.get("open", value.get("open_count", len(all_open_items)))
    if claim_scope is not None:
        open_count = len(open_items)
    if agent_scope_filter is not None:
        open_count = len(blocking_open_items)
    summary = {
        "schema_version": value.get("schema_version"),
        "source_section": value.get("source_section") or "project_asset",
        "total_count": value.get("total", value.get("total_count")),
        "open_count": open_count,
        "done_count": value.get("done", value.get("done_count")),
        "first_open_items": open_items[:3],
        "first_executable_items": executable_items[:3],
        "monitor_open_items": monitor_items,
        "monitor_due_count": len(monitor_due_items),
        "monitor_due_items": monitor_due_items[:MONITOR_DUE_ITEM_LIMIT],
        "active_next_action_items": active_next_action_items,
        "active_next_action_executable_items": active_next_action_executable_items,
        "backlog_items": open_items[:TODO_BACKLOG_ITEM_LIMIT],
        "executable_backlog_items": executable_items[:TODO_BACKLOG_ITEM_LIMIT],
    }
    monitor_writeback = todo_summary_monitor_writeback_contract(value)
    if monitor_writeback:
        summary["monitor_writeback"] = monitor_writeback
    summary.update(
        build_todo_claim_visibility_lanes(
            blocking_open_items,
            agent_identity=agent_identity,
            backlog_item_limit=TODO_BACKLOG_ITEM_LIMIT,
            visibility_lane_limit=TODO_VISIBILITY_LANE_LIMIT,
        )
    )
    summary.update(
        build_todo_deferred_visibility_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_DEFERRED_VISIBILITY_LIMIT,
        )
    )
    summary.update(
        build_todo_handoff_gate_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    summary.update(
        build_todo_route_continuation_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    if claimed_open_items or value.get("claimed_open_count"):
        summary["claimed_open_count"] = value.get("claimed_open_count", len(claimed_open_items))
        summary["unclaimed_open_count"] = value.get(
            "unclaimed_open_count",
            max(0, int(open_count or 0) - len(claimed_open_items)),
        )
    if claim_scope:
        summary["claim_scope"] = claim_scope
    if agent_scope_filter:
        summary["agent_scope_filter"] = agent_scope_filter
        summary["all_open_count"] = value.get("open", value.get("open_count", len(all_open_items)))
        summary["other_agent_scoped_open_count"] = len(other_agent_scoped_items)
        summary["other_agent_scoped_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in other_agent_scoped_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    return summary


def is_canonical_attention_todo_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("schema_version") == "todo_summary_v0":
        return True
    source_section = str(value.get("source_section") or "").strip().lower()
    if source_section.startswith("raw "):
        return False
    return source_section in {"agent todo", "user todo"}


def select_quota_todo_summary(
    canonical_value: Any,
    project_asset_value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
) -> dict[str, Any] | None:
    canonical_summary = summarize_user_todos_for_quota(
        canonical_value,
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
    )
    project_asset_summary = summarize_project_asset_todos_for_quota(
        project_asset_value,
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
    )
    if is_canonical_attention_todo_summary(canonical_value):
        return canonical_summary or project_asset_summary
    return project_asset_summary or canonical_summary
