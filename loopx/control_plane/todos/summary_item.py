from __future__ import annotations

from typing import Any

from .contract import (
    normalize_required_write_scopes,
    normalize_todo_decision_scope,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
)
from .handoff_gate import handoff_ready_successor_todo_ids
from .projection import todo_item_task_class


TODO_SUMMARY_COMPACT_FIELDS = (
    "schema_version",
    "todo_id",
    "role",
    "status",
    "priority",
    "title",
    "archive_state",
    "source_section",
    "task_class",
    "action_kind",
    "required_write_scopes",
    "required_capabilities",
    "target_capabilities",
    "decision_scope",
    "required_decision_scopes",
    "claimed_by",
    "blocks_agent",
    "unblocks_todo_id",
    "resume_when",
    "resume_condition",
    "resume_ready",
    "no_followup",
    "successor_todo_ids",
    "target_key",
    "cadence",
    "next_due_at",
    "expires_at",
    "last_checked_at",
    "result_hash",
    "consecutive_no_change",
    "material_change",
    "max_no_change_before_replan",
    "route_continuation_replan_required",
    "route_continuation_reason",
    "route_id",
    "route_key",
    "completed_at",
    "updated_at",
    "superseded_by",
)

TODO_SUMMARY_SOURCE_KEYS = (
    "active_next_action_items",
    "active_next_action_executable_items",
    "first_open_items",
    "backlog_items",
    "unclaimed_priority_open_items",
    "claimed_open_items",
    "claimed_advancement_open_items",
    "claimed_monitor_open_items",
    "current_agent_claimed_open_items",
    "current_agent_claimed_advancement_items",
    "current_agent_claimed_monitor_items",
    "resume_blocked_items",
    "monitor_blocked_resume_candidates",
    "current_agent_monitor_blocked_resume_candidates",
    "unclaimed_monitor_blocked_resume_candidates",
    "items",
)


def compact_todo_summary_item(
    item: dict[str, Any],
    *,
    text: str | None = None,
) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "index": item.get("index"),
        "text": text if text is not None else item.get("text"),
    }
    for key in TODO_SUMMARY_COMPACT_FIELDS:
        if item.get(key) is not None:
            compact[key] = item.get(key)
    required_write_scopes = normalize_required_write_scopes(
        compact.get("required_write_scopes")
    )
    if required_write_scopes:
        compact["required_write_scopes"] = required_write_scopes
    else:
        compact.pop("required_write_scopes", None)
    decision_scope = normalize_todo_decision_scope(compact.get("decision_scope"))
    if decision_scope:
        compact["decision_scope"] = decision_scope
    else:
        compact.pop("decision_scope", None)
    required_decision_scopes = normalize_todo_required_decision_scopes(
        compact.get("required_decision_scopes")
    )
    if required_decision_scopes:
        compact["required_decision_scopes"] = required_decision_scopes
    else:
        compact.pop("required_decision_scopes", None)
    compact["task_class"] = todo_item_task_class(compact)
    return compact


def todo_summary_source_items(value: dict[str, Any]) -> list[dict[str, Any]]:
    ready_successor_todo_ids = handoff_ready_successor_todo_ids(value)
    open_items: list[dict[str, Any]] = []
    for key in TODO_SUMMARY_SOURCE_KEYS:
        source_items = value.get(key) if isinstance(value.get(key), list) else []
        for item in source_items:
            if not isinstance(item, dict) or item.get("done") is True:
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            duplicate = any(
                existing.get("todo_id") == item.get("todo_id")
                if item.get("todo_id") and existing.get("todo_id")
                else existing.get("index") == item.get("index")
                and str(existing.get("text") or "").strip() == text
                for existing in open_items
            )
            if duplicate:
                continue
            compact = compact_todo_summary_item(item, text=text)
            todo_id = normalize_todo_id(compact.get("todo_id"))
            if (
                todo_id
                and todo_id in ready_successor_todo_ids
                and normalize_todo_resume_when(compact.get("resume_when"))
                and "resume_ready" not in compact
            ):
                compact["resume_ready"] = True
                compact["resume_condition"] = {
                    "schema_version": "todo_resume_condition_v0",
                    "resume_when": compact.get("resume_when"),
                    "satisfied": True,
                    "source": "handoff_gate_cleared_with_successor",
                }
            open_items.append(compact)
    return open_items
