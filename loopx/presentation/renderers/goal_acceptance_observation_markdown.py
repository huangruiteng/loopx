"""Render the bounded Goal acceptance observations owned by status collection."""

from __future__ import annotations

from typing import Any

from ...control_plane.goals.acceptance_observation import (
    GOAL_ACCEPTANCE_OBSERVATION_SCHEMA_VERSION,
)
from ..markdown import as_dict, as_list, markdown_scalar


def append_goal_acceptance_observation_markdown(
    lines: list[str], goal: dict[str, Any]
) -> None:
    observation = as_dict(goal.get("acceptance_observation"))
    if observation.get("schema_version") == GOAL_ACCEPTANCE_OBSERVATION_SCHEMA_VERSION:
        lines.append(
            "  - acceptance observations (partial; not completion proof): "
            f"historical_progress={len(as_list(observation.get('historical_progress')))} "
            f"gaps={len(as_list(observation.get('acceptance_gaps')))} "
            f"gates={len(as_list(observation.get('guards')))}"
        )
        for gap in as_list(observation.get("acceptance_gaps")):
            if isinstance(gap, dict):
                lines.append(
                    f"    - owner={markdown_scalar(gap.get('owner') or 'unknown')}: "
                    f"{markdown_scalar(gap.get('evidence_required') or gap.get('reason') or 'unknown')}"
                )
