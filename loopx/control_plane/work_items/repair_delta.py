from __future__ import annotations

from typing import Iterable


REPAIR_DELTA_KIND_CHOICES = (
    "effective_action",
    "interaction_contract",
    "runnable_todo_set",
    "user_gate",
    "blocker",
    "successor_or_supersede",
    "capability_gate",
    "monitor_target",
    "active_state_next_action",
    "goal_vision_patch",
    "goal_boundary_projection",
    "no_followup",
    "watch_lane_continuation",
)

FRONTIER_REPLAN_ACK_DELTA_KINDS = frozenset(
    {
        "active_state_next_action",
        "blocker",
        "goal_vision_patch",
        "no_followup",
        "runnable_todo_set",
        "successor_or_supersede",
        "watch_lane_continuation",
    }
)


def normalize_repair_delta_kinds(values: Iterable[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    allowed = set(REPAIR_DELTA_KIND_CHOICES)
    for value in values or []:
        item = str(value or "").strip()
        if not item:
            continue
        if item not in allowed:
            raise ValueError(
                "repair_delta_kind must be one of: "
                + ", ".join(REPAIR_DELTA_KIND_CHOICES)
            )
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def repair_delta_kinds_have_frontier_delta(values: Iterable[str] | None) -> bool:
    return bool(
        {
            str(item or "").strip()
            for item in (values or [])
            if str(item or "").strip()
        }
        & FRONTIER_REPLAN_ACK_DELTA_KINDS
    )
