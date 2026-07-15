from __future__ import annotations

from typing import Any

from .active_state_editing import section_bounds, todo_blocks
from .contract import (
    TODO_STATUS_OPEN,
    normalize_todo_id,
    normalize_todo_status,
    todo_done_for_status,
)


TODO_UNBLOCK_RESUME_SCHEMA_VERSION = "todo_unblock_resume_v0"


def _status(todo: dict[str, Any]) -> str:
    return normalize_todo_status(todo.get("status")) or TODO_STATUS_OPEN


def _find_todo(
    lines: list[str],
    *,
    role: str,
    todo_id: str,
) -> dict[str, Any] | None:
    bounds = section_bounds(lines, role)
    if not bounds:
        return None
    start, end, section = bounds
    return next(
        (
            todo
            for todo in todo_blocks(
                lines,
                start,
                end,
                role=role,
                source_section=section,
            )
            if normalize_todo_id(todo.get("todo_id")) == todo_id
        ),
        None,
    )


def plan_completed_user_unblock_resume(
    lines: list[str],
    *,
    source_todo_id: str,
    target_todo_id: str,
) -> dict[str, Any]:
    """Plan a safe resume for one explicitly linked blocked advancement todo."""

    receipt: dict[str, Any] = {
        "schema_version": TODO_UNBLOCK_RESUME_SCHEMA_VERSION,
        "source_todo_id": source_todo_id,
        "target_todo_id": target_todo_id,
        "changed": False,
    }
    target = _find_todo(lines, role="agent", todo_id=target_todo_id)
    if not target:
        return {**receipt, "state": "target_not_found"}
    target_status = _status(target)
    receipt["previous_status"] = target_status
    receipt["status"] = target_status
    if target_status != "blocked":
        return {**receipt, "state": "target_not_blocked"}
    if str(target.get("task_class") or "") == "blocker":
        return {**receipt, "state": "explicit_blocker_repair_required"}

    user_bounds = section_bounds(lines, "user")
    remaining_ids: list[str] = []
    if user_bounds:
        start, end, section = user_bounds
        for candidate in todo_blocks(
            lines,
            start,
            end,
            role="user",
            source_section=section,
        ):
            candidate_id = normalize_todo_id(candidate.get("todo_id"))
            if (
                candidate_id
                and candidate_id != source_todo_id
                and not todo_done_for_status(_status(candidate))
                and normalize_todo_id(candidate.get("unblocks_todo_id")) == target_todo_id
            ):
                remaining_ids.append(candidate_id)
    if remaining_ids:
        return {
            **receipt,
            "state": "other_user_blockers_active",
            "remaining_user_blocker_todo_ids": sorted(set(remaining_ids)),
        }
    return {**receipt, "state": "resume_ready"}
