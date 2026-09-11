"""Render the bounded Goal acceptance observations owned by status collection."""

from __future__ import annotations

from typing import Any

from ..markdown import as_dict, as_list, markdown_scalar


def append_goal_acceptance_markdown(lines: list[str], goal: dict[str, Any]) -> None:
    lifecycle = as_dict(goal.get("artifact_lifecycle"))
    if lifecycle:
        lines.append(
            "  - acceptance observations (partial; not completion proof): "
            f"milestones={len(as_list(lifecycle.get('milestones')))} "
            f"gaps={len(as_list(lifecycle.get('acceptance_gaps')))} "
            f"gates={len(as_list(lifecycle.get('guards')))}"
        )
        for gap in as_list(lifecycle.get("acceptance_gaps")):
            if isinstance(gap, dict):
                lines.append(
                    f"    - owner={markdown_scalar(gap.get('owner') or 'unknown')}: "
                    f"{markdown_scalar(gap.get('evidence_required') or gap.get('reason') or 'unknown')}"
                )
