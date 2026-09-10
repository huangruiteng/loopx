"""Complete locked Todo facts for public update planning; no state decisions."""
from typing import Any

from .active_state_editing import archive_section_bounds, section_bounds, todo_blocks
from .resume_condition import compact_todo_resume_items


def todo_update_snapshot(lines: list[str]) -> list[dict[str, Any]]:
    """Collect complete active/archive Todo metadata under the caller's lock."""

    collected: list[dict[str, Any]] = []
    archive_bounds = archive_section_bounds(lines)
    if archive_bounds:
        collected.extend(
            {
                **item,
                "role": "agent",
            }
            for item in todo_blocks(
                lines,
                archive_bounds[0],
                archive_bounds[1],
                role="agent",
                source_section="Completed Work Archive",
            )
        )
    for role in ("user", "agent"):
        bounds = section_bounds(lines, role)
        if bounds:
            collected.extend(
                {
                    **item,
                    "role": role,
                }
                for item in todo_blocks(
                    lines,
                    bounds[0],
                    bounds[1],
                    role=role,
                    source_section=bounds[2],
                )
            )
    return compact_todo_resume_items(collected)
