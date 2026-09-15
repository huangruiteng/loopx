"""Render the derived Goal artifact lifecycle projection owned by status collection."""

from __future__ import annotations

from typing import Any

from ...control_plane.goals.artifact_lifecycle import (
    GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION,
)
from ..markdown import as_dict, as_list, markdown_scalar


def append_goal_artifact_lifecycle_markdown(
    lines: list[str], goal: dict[str, Any]
) -> None:
    projection = as_dict(goal.get("artifact_lifecycle"))
    if (
        projection.get("schema_version")
        != GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION
    ):
        return
    milestones = as_list(projection.get("milestones"))
    reached = [
        milestone
        for milestone in milestones
        if isinstance(milestone, dict) and milestone.get("reached") is True
    ]
    lines.append(
        "  - artifact lifecycle: "
        f"phase={markdown_scalar(projection.get('lifecycle_phase') or 'unknown')} "
        f"milestones={len(reached)}/{len(milestones)} "
        f"guards={len(as_list(projection.get('guards')))}"
    )
    for guard in as_list(projection.get("guards")):
        if not isinstance(guard, dict) or guard.get("blocked") is not True:
            continue
        lines.append(
            f"    - blocked by {markdown_scalar(guard.get('kind') or 'unknown')} "
            f"({markdown_scalar(guard.get('owner') or 'unowned')}): "
            f"{markdown_scalar(guard.get('id') or 'unknown')}"
        )
    for transition in as_list(projection.get("next_transitions")):
        if isinstance(transition, dict):
            lines.append(
                f"    - next: {markdown_scalar(transition.get('target_phase') or 'unknown')} "
                f"({markdown_scalar(transition.get('precondition') or 'unknown')})"
            )
