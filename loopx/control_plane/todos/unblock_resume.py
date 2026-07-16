from __future__ import annotations

from typing import Any, Callable

from .active_state_editing import section_bounds, todo_blocks
from .contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_USER_GATE,
    normalize_todo_decision_scope,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
    normalize_todo_status,
    todo_done_for_status,
)
from .decision_scope import decision_scope_covers


TODO_UNBLOCK_RESUME_SCHEMA_VERSION = "todo_unblock_resume_v0"
TODO_DECISION_SCOPE_RESOLUTION_SCHEMA_VERSION = (
    "todo_decision_scope_resolution_v0"
)


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


def plan_completed_user_gate_decision_scope_resolution(
    lines: list[str],
    *,
    source_todo_id: str,
    target_todo_id: str,
    decision_scope: Any,
) -> dict[str, Any] | None:
    """Plan consumption of only the target requirements covered by one approval."""

    normalized_scope = normalize_todo_decision_scope(decision_scope)
    if not normalized_scope:
        return None
    target = _find_todo(lines, role="agent", todo_id=target_todo_id)
    if not target:
        return None
    required_scopes = normalize_todo_required_decision_scopes(
        target.get("required_decision_scopes")
    )
    resolved_scopes = [
        scope
        for scope in required_scopes
        if decision_scope_covers(normalized_scope, scope)
    ]
    if not resolved_scopes:
        return None
    remaining_scopes = [
        scope
        for scope in required_scopes
        if not decision_scope_covers(normalized_scope, scope)
    ]
    return {
        "schema_version": TODO_DECISION_SCOPE_RESOLUTION_SCHEMA_VERSION,
        "state": "resolution_ready",
        "source_todo_id": source_todo_id,
        "target_todo_id": target_todo_id,
        "decision_scope": normalized_scope,
        "resolved_required_decision_scopes": resolved_scopes,
        "remaining_required_decision_scopes": remaining_scopes,
        "changed": False,
    }


def apply_completed_user_todo_lifecycle(
    lines: list[str],
    *,
    completion_todo: dict[str, Any] | None,
    update_result: dict[str, Any],
    fallback_todo_id: str,
    updated_at: str,
    apply_update: Callable[..., dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Apply exact unblock and decision-scope effects after user completion."""

    completion_role = str((completion_todo or {}).get("role") or "")
    completion_task_class = str((completion_todo or {}).get("task_class") or "")
    source_todo_id = str(update_result.get("todo_id") or fallback_todo_id)
    target_todo_id = normalize_todo_id(update_result.get("unblocks_todo_id"))
    decision_scope_resolution = None
    if (
        completion_role == "user"
        and completion_task_class == TODO_TASK_CLASS_USER_GATE
        and target_todo_id
    ):
        decision_scope_resolution = plan_completed_user_gate_decision_scope_resolution(
            lines,
            source_todo_id=source_todo_id,
            target_todo_id=target_todo_id,
            decision_scope=(completion_todo or {}).get("decision_scope"),
        )
        if decision_scope_resolution:
            resolved_target = apply_update(
                lines,
                todo_id=target_todo_id,
                role="agent",
                required_decision_scopes=decision_scope_resolution[
                    "remaining_required_decision_scopes"
                ],
                updated_at=updated_at,
            )
            decision_scope_resolution.update(
                state="resolved",
                changed=bool(resolved_target.get("changed")),
                target_status=resolved_target.get("status"),
            )

    unblock_resume = None
    if (
        completion_role == "user"
        and completion_task_class in {"user_action", TODO_TASK_CLASS_USER_GATE}
        and target_todo_id
    ):
        unblock_resume = plan_completed_user_unblock_resume(
            lines,
            source_todo_id=source_todo_id,
            target_todo_id=target_todo_id,
        )
        if unblock_resume.get("state") == "resume_ready":
            resumed = apply_update(
                lines,
                todo_id=target_todo_id,
                role="agent",
                status=TODO_STATUS_OPEN,
                reason=f"authorization satisfied by completed user todo {source_todo_id}",
                updated_at=updated_at,
            )
            unblock_resume.update(
                state="resumed",
                status=resumed.get("status"),
                changed=bool(resumed.get("changed")),
                claimed_by=resumed.get("claimed_by"),
            )
            unblock_resume = {
                key: value
                for key, value in unblock_resume.items()
                if value not in (None, "", [], {})
            }
    return unblock_resume, decision_scope_resolution
