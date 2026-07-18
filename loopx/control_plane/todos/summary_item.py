from __future__ import annotations

from typing import Any

from .contract import (
    normalize_required_write_scopes,
    normalize_todo_decision_outcome,
    normalize_todo_decision_scope,
    normalize_todo_decision_scope_outcomes,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    normalize_removed_todo_continuation_policy,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_task_repository,
)
from .handoff_gate import handoff_ready_successor_todo_ids
from .handoff_note import attach_todo_handoff_note
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
    "task_repository",
    "continuation_policy",
    "removed_continuation_policy",
    "required_write_scopes",
    "required_capabilities",
    "target_capabilities",
    "decision_scope",
    "required_decision_scopes",
    "decision_outcome",
    "decision_scope_outcomes",
    "claimed_by",
    "bound_agent",
    "goal_bound",
    "blocks_agent",
    "excluded_agents",
    "global_gate",
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
    "handoff_note",
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
    "monitor_open_items",
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
    task_repository = normalize_todo_task_repository(compact.get("task_repository"))
    if task_repository:
        compact["task_repository"] = task_repository
    else:
        compact.pop("task_repository", None)
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
    decision_outcome = normalize_todo_decision_outcome(compact.get("decision_outcome"))
    if decision_outcome:
        compact["decision_outcome"] = decision_outcome
    else:
        compact.pop("decision_outcome", None)
    decision_scope_outcomes = normalize_todo_decision_scope_outcomes(
        compact.get("decision_scope_outcomes")
    )
    if decision_scope_outcomes:
        compact["decision_scope_outcomes"] = decision_scope_outcomes
    else:
        compact.pop("decision_scope_outcomes", None)
    excluded_agents = normalize_todo_excluded_agents(compact.get("excluded_agents"))
    if excluded_agents:
        compact["excluded_agents"] = excluded_agents
    else:
        compact.pop("excluded_agents", None)
    removed_continuation_policy = normalize_removed_todo_continuation_policy(
        compact.get("removed_continuation_policy")
    )
    if removed_continuation_policy:
        compact["removed_continuation_policy"] = removed_continuation_policy
    else:
        compact.pop("removed_continuation_policy", None)
    compact["task_class"] = todo_item_task_class(compact)
    attach_todo_handoff_note(compact)
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
