from __future__ import annotations

from typing import Any

from .active_state_editing import (
    COMPLETED_WORK_ARCHIVE_HEADING,
    TODO_SECTION_HEADINGS,
    insert_archive_blocks,
    section_bounds,
    todo_blocks,
)


DEFAULT_MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE = 12


def completed_todo_archive_warning(
    agent_todos: dict[str, Any] | None,
    *,
    max_active_done_todos: int = DEFAULT_MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
) -> dict[str, Any] | None:
    if not isinstance(agent_todos, dict):
        return None
    try:
        done_count = int(agent_todos.get("done_count") or 0)
    except (TypeError, ValueError):
        done_count = 0
    if done_count <= max_active_done_todos:
        return None
    try:
        open_count = int(agent_todos.get("open_count") or 0)
    except (TypeError, ValueError):
        open_count = 0
    return {
        "kind": "completed_agent_todo_archive_required",
        "requires_archive": True,
        "archive_section": COMPLETED_WORK_ARCHIVE_HEADING,
        "active_done_count": done_count,
        "active_open_count": open_count,
        "max_active_done_count": max_active_done_todos,
        "recommended_action": (
            "move older completed Agent Todo entries into a dedicated Completed Work Archive "
            "until the active Agent Todo section keeps only current open work and a small recent-done tail"
        ),
    }


def archive_completed_todo_lines(
    lines: list[str],
    *,
    role: str = "agent",
    max_active_done: int = DEFAULT_MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
) -> dict[str, Any]:
    if role not in TODO_SECTION_HEADINGS:
        raise ValueError("todo role must be one of: user, agent")
    if max_active_done < 0:
        raise ValueError("max_active_done must be non-negative")

    updated_lines = list(lines)
    bounds = section_bounds(updated_lines, role)
    section = bounds[2] if bounds else TODO_SECTION_HEADINGS[role]
    moved_blocks: list[list[str]] = []
    active_done_count = 0
    moved_count = 0
    kept_done_count = 0

    if bounds:
        blocks = todo_blocks(updated_lines, bounds[0], bounds[1], role=role, source_section=section)
        done_blocks = [block for block in blocks if block.get("done") is True]
        active_done_count = len(done_blocks)
        move_count = max(0, active_done_count - max_active_done)
        move_starts = {int(block["start"]) for block in done_blocks[:move_count]}
        kept_done_count = active_done_count - move_count
        for block in done_blocks[:move_count]:
            moved_blocks.append(updated_lines[int(block["start"]) : int(block["end"])])
        if move_starts:
            new_lines: list[str] = []
            index = 0
            while index < len(updated_lines):
                if index in move_starts:
                    matching = next(
                        block for block in done_blocks[:move_count] if int(block["start"]) == index
                    )
                    index = int(matching["end"])
                    while (
                        new_lines
                        and not new_lines[-1].strip()
                        and index < len(updated_lines)
                        and not updated_lines[index].strip()
                    ):
                        index += 1
                    continue
                new_lines.append(updated_lines[index])
                index += 1
            updated_lines = new_lines
            insert_archive_blocks(updated_lines, moved_blocks)
            moved_count = move_count

    return {
        "lines": updated_lines,
        "changed": moved_count > 0,
        "role": role,
        "section": section,
        "archive_section": COMPLETED_WORK_ARCHIVE_HEADING,
        "active_done_before": active_done_count,
        "active_done_after": kept_done_count,
        "max_active_done": max_active_done,
        "moved_count": moved_count,
    }
