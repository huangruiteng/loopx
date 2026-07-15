from __future__ import annotations

from typing import Any

from ..todos.contract import normalize_todo_id
from ..todos.deferred_resume import todo_summary_blocked_successor_items


GOAL_VISION_WAIT_STATE_SCHEMA_VERSION = "goal_vision_wait_state_v0"
VISION_ACCEPTANCE_GAP_KIND = "vision_acceptance_gap"


def _compact_resume_condition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact = {
        key: value.get(key)
        for key in (
            "schema_version",
            "resume_when",
            "satisfied",
            "kind",
            "target",
            "target_todo_id",
            "target_status",
            "target_archive_state",
            "target_source_section",
            "target_task_class",
            "target_claimed_by",
            "capability",
            "provider",
        )
        if value.get(key) is not None
    }
    compact["satisfied"] = False
    return compact


def build_goal_vision_wait_state(
    *,
    agent_todo_summary: dict[str, Any] | None,
    agent_id: str | None,
    acceptance_gaps: list[dict[str, Any]] | None,
    selectable_advancement_count: int,
) -> dict[str, Any] | None:
    """Project a temporary vision wait over an exact blocked successor.

    This is deliberately a read model, not a new todo or vision lifecycle
    state. It may defer only ordinary open-vision acceptance gaps. Missing
    checkpoints and closed-stage successor requirements remain strict.
    """

    gaps = [gap for gap in (acceptance_gaps or []) if isinstance(gap, dict)]
    if not gaps or any(gap.get("kind") != VISION_ACCEPTANCE_GAP_KIND for gap in gaps):
        return None
    if selectable_advancement_count > 0:
        return None
    candidates = todo_summary_blocked_successor_items(
        agent_todo_summary or {},
        agent_id=agent_id,
    )
    if not candidates:
        return None

    selected = candidates[0]
    waiting_todo_ids = [
        todo_id
        for todo_id in (normalize_todo_id(item.get("todo_id")) for item in candidates[:5])
        if todo_id
    ]
    selected_todo_id = normalize_todo_id(selected.get("todo_id"))
    payload: dict[str, Any] = {
        "schema_version": GOAL_VISION_WAIT_STATE_SCHEMA_VERSION,
        "state": "waiting",
        "reason_code": "exact_blocked_successor",
        "agent_id": agent_id,
        "waiting_todo_count": len(candidates),
        "waiting_todo_ids": waiting_todo_ids,
        "selected_todo_id": selected_todo_id,
        "selected_todo_status": selected.get("status"),
        "selected_todo_priority": selected.get("priority"),
        "selected_todo_claimed_by": selected.get("claimed_by"),
        "resume_when": selected.get("resume_when"),
        "resume_condition": _compact_resume_condition(selected.get("resume_condition")),
        "deferred_acceptance_gap_count": len(gaps),
        "deferred_acceptance_gap_kinds": [VISION_ACCEPTANCE_GAP_KIND],
        "automatic_resume": True,
        "resume_behavior": (
            "when resume_ready becomes true, restore ordinary open-todo or "
            "deferred-successor routing without closing the active vision"
        ),
    }
    return {key: value for key, value in payload.items() if value is not None}
