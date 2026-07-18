from __future__ import annotations

from pathlib import Path
from typing import Any

from ..todos.contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    normalize_todo_id,
)
from .monitor_todo import (
    monitor_next_due_at,
    monitor_todo_task_class,
    parse_monitor_counter,
)


def resolve_monitor_todo_item(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str | None = None,
    target_key: str | None = None,
) -> dict[str, Any]:
    from ...todos import list_goal_todos

    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    safe_target_key = str(target_key or "").strip()
    if not normalized_todo_id and not safe_target_key:
        raise ValueError("monitor todo writeback requires --todo-id or --target-key")
    payload = list_goal_todos(registry_path=registry_path, goal_id=goal_id, role="agent")
    matches: list[dict[str, Any]] = []
    for item in payload.get("todos") if isinstance(payload.get("todos"), list) else []:
        if not isinstance(item, dict):
            continue
        if normalized_todo_id and normalize_todo_id(item.get("todo_id")) == normalized_todo_id:
            matches.append(item)
            continue
        if safe_target_key and str(item.get("target_key") or "").strip() == safe_target_key:
            matches.append(item)
    if not matches:
        target = normalized_todo_id or safe_target_key
        raise ValueError(f"monitor todo target {target!r} was not found")
    if len(matches) > 1:
        raise ValueError(f"monitor target_key {safe_target_key!r} matched multiple todos; pass --todo-id")
    item = matches[0]
    if monitor_todo_task_class(item) != TODO_TASK_CLASS_MONITOR:
        raise ValueError("monitor-poll todo writeback target must be task_class=continuous_monitor")
    return item


def write_monitor_poll_todo_state(
    *,
    registry_path: Path,
    goal_id: str,
    generated_at: str,
    execute: bool,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
    cadence: str | None = None,
    next_due_at: str | None = None,
    reason_summary: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    from ...todos import add_goal_todo, update_goal_todo

    if not todo_id and not target_key:
        return None
    safe_result_hash = str(result_hash or "").strip()
    if not safe_result_hash:
        raise ValueError("monitor todo writeback requires --result-hash")
    item = resolve_monitor_todo_item(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=todo_id,
        target_key=target_key,
    )
    resolved_todo_id = normalize_todo_id(item.get("todo_id"))
    if not resolved_todo_id:
        raise ValueError("resolved monitor todo has no stable todo_id")
    safe_target_key = str(target_key or item.get("target_key") or "").strip()
    effective_cadence = str(cadence or item.get("cadence") or "").strip()
    effective_next_due_at = monitor_next_due_at(
        generated_at=generated_at,
        cadence=effective_cadence,
        explicit_next_due_at=next_due_at,
    )
    if not material_change and not effective_next_due_at:
        raise ValueError(
            "unchanged monitor todo writeback requires --next-due-at or a parseable cadence such as 30m/2h/1d"
        )
    previous_hash = str(item.get("result_hash") or "").strip()
    previous_no_change = parse_monitor_counter(item.get("consecutive_no_change"))
    consecutive_no_change = (
        0
        if material_change or (previous_hash and previous_hash != safe_result_hash)
        else previous_no_change + 1
    )
    monitor_metadata: dict[str, Any] = {
        "last_checked_at": generated_at,
        "result_hash": safe_result_hash,
        "consecutive_no_change": str(consecutive_no_change),
        "material_change": "true" if material_change else "false",
    }
    if safe_target_key:
        monitor_metadata["target_key"] = safe_target_key
    if effective_cadence:
        monitor_metadata["cadence"] = effective_cadence
    if effective_next_due_at:
        monitor_metadata["next_due_at"] = effective_next_due_at
    update_result = update_goal_todo(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=resolved_todo_id,
        role="agent",
        reason=reason_summary,
        monitor_metadata=monitor_metadata,
        agent_id=agent_id,
        dry_run=not execute,
    )
    next_results: list[dict[str, Any]] = []
    if material_change and next_agent_todo:
        next_results.append(
            add_goal_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                role="agent",
                text=next_agent_todo,
                task_class=TODO_TASK_CLASS_ADVANCEMENT,
                action_kind="advance",
                claimed_by=next_claimed_by,
                unblocks_todo_id=resolved_todo_id,
                dry_run=not execute,
            )
        )
    if material_change and next_user_todo:
        next_results.append(
            add_goal_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                role="user",
                text=next_user_todo,
                task_class=TODO_TASK_CLASS_USER_GATE,
                action_kind="gate",
                agent_id=agent_id,
                unblocks_todo_id=resolved_todo_id,
                dry_run=not execute,
            )
        )
    return {
        "schema_version": "monitor_poll_todo_writeback_v0",
        "dry_run": not execute,
        "goal_id": goal_id,
        "todo_id": resolved_todo_id,
        "target_key": safe_target_key or None,
        "result_hash": safe_result_hash,
        "material_change": material_change,
        "consecutive_no_change": consecutive_no_change,
        "last_checked_at": generated_at,
        "next_due_at": effective_next_due_at,
        "cadence": effective_cadence or None,
        "todo_update": update_result,
        "next_todos": next_results,
    }
