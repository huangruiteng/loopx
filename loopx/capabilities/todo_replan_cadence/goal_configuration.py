from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...control_plane.goals.goal_vision_policy import (
    completed_todo_replan_threshold,
)


def configuration_summary(goal: Mapping[str, Any]) -> dict[str, Any] | None:
    profile = goal.get("execution_profile")
    if not isinstance(profile, Mapping) or (
        "replan_after_completed_todos" not in profile
    ):
        return None
    return {"completed_todos": completed_todo_replan_threshold(dict(profile))}


__all__ = ["configuration_summary"]
