from __future__ import annotations

from typing import Any

from .public_safety import public_safe_compact_list, public_safe_compact_text


MAX_GOAL_START_TODOS = 8


def compact_goal_start_todo_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    if isinstance(value.get("raw_material_recorded"), bool):
        compact["raw_material_recorded"] = value["raw_material_recorded"]
    for field in (
        "completed_todo_id_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    for field in ("selected_p0_todo_id", "todo_identity_attribution"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    planned_ids = public_safe_compact_list(
        value.get("planned_todo_ids"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_ids:
        compact["planned_todo_ids"] = planned_ids
    completed_ids = public_safe_compact_list(
        value.get("completed_todo_ids"),
        limit=MAX_GOAL_START_TODOS,
    )
    if completed_ids:
        compact["completed_todo_ids"] = completed_ids
    planned_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_texts:
        compact["planned_todo_texts_public_safe"] = planned_texts
    planned_todos: list[dict[str, Any]] = []
    source_todos = value.get("planned_todos")
    if isinstance(source_todos, list):
        for item in source_todos[:MAX_GOAL_START_TODOS]:
            if not isinstance(item, dict):
                continue
            todo: dict[str, Any] = {}
            for field in ("todo_id", "role", "status", "text_public_safe"):
                text = public_safe_compact_text(item.get(field), limit=180)
                if text:
                    todo[field] = text
            for field in ("claim_count", "update_count", "complete_count"):
                raw = item.get(field)
                if isinstance(raw, int) and not isinstance(raw, bool):
                    todo[field] = max(0, raw)
            if todo:
                planned_todos.append(todo)
    if planned_todos:
        compact["planned_todos"] = planned_todos
    return compact


def compact_goal_start_product_mode_control_score(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "satisfied",
        "raw_material_recorded",
        "goal_start_plan_observed",
        "planner_before_todo_write",
        "same_priority_order_preserved",
        "selected_todo_claimed",
        "selected_todo_updated_before_solver",
        "selected_todo_completed_before_spend",
        "selected_todo_completed_observed",
        "selected_todo_spend_observed",
        "non_selected_todos_preserved_open_or_deferred",
        "quota_spend_missing_after_repeated_complete",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "component_count",
        "satisfied_component_count",
        "planned_todo_count",
        "planned_todo_count_expected",
        "planned_p0_count",
        "premature_done_signal_count",
        "agent_todo_claim_count",
        "agent_todo_update_count",
        "agent_todo_complete_count",
        "agent_todo_complete_unique_todo_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
        "agent_quota_spend_slot_count",
        "driver_todo_claim_count",
        "driver_todo_update_count",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    score = value.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        compact["score"] = float(score)
    for field in ("selected_p0_todo_id", "premature_done_stop_reason"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    planned_ids = public_safe_compact_list(
        value.get("planned_todo_ids"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_ids:
        compact["planned_todo_ids"] = planned_ids
    planned_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=MAX_GOAL_START_TODOS,
    )
    if planned_texts:
        compact["planned_todo_texts_public_safe"] = planned_texts
    snapshot = compact_goal_start_todo_snapshot(value.get("goal_start_todo_snapshot"))
    if snapshot:
        compact["goal_start_todo_snapshot"] = snapshot
    return compact
