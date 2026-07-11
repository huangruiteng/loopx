from __future__ import annotations

from typing import Any

from .contract import (
    normalize_required_write_scopes,
    normalize_todo_decision_scope,
    normalize_todo_required_decision_scopes,
    normalize_todo_task_class,
)


TODO_SUCCESSION_WARNING_SCHEMA_VERSION = "todo_succession_warning_v0"


def _compact_succession_warning_item(item: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "index": item.get("index"),
        "text": item.get("text"),
    }
    for key in (
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
        "continuation_policy",
        "required_write_scopes",
        "required_capabilities",
        "target_capabilities",
        "decision_scope",
        "required_decision_scopes",
        "claimed_by",
        "blocks_agent",
        "excluded_agents",
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
        "done",
        "succession_tracked",
        "recommended_action",
    ):
        if item.get(key) is not None:
            compact[key] = item.get(key)
    required_write_scopes = normalize_required_write_scopes(compact.get("required_write_scopes"))
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
    compact["task_class"] = normalize_todo_task_class(
        compact.get("task_class"),
        text=str(compact.get("text") or ""),
        action_kind=compact.get("action_kind"),
    )
    return compact


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
        _compact_succession_warning_item(item)
        for item in (source_items or [])
        if isinstance(item, dict)
    ][:item_limit]
    count = warning.get("count", summary.get("completed_without_successor_count"))
    try:
        count = max(0, int(count))
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
            "completed_advancement_without_successor",
        ),
        "count": count,
        "items": items,
        "recommended_action": warning.get(
            "recommended_action",
            "record no_followup=true or add/link a successor todo",
        ),
    }
    return {
        "completed_without_successor_count": count,
        "completed_without_successor_items": items,
        "todo_succession_warning": payload,
    }
