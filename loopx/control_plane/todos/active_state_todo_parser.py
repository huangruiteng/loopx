from __future__ import annotations

from pathlib import Path
from typing import Any

from ...materials import extract_review_materials
from ...todo_contract import (
    TODO_TASK_PATTERN,
    normalize_todo_id,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_status_from_marker,
)
from ..goals.active_state_metadata import TODO_ARCHIVE_HEADER_MARKERS, todo_role_for_heading
from .todo_summary import MAX_STATUS_TODOS_PER_ROLE, compact_todo_group, normalize_todo_text


def parse_active_state_todos(
    state_text: str,
    *,
    goal: dict[str, Any] | None = None,
    state_path: Path | None = None,
    preferred_todo_ids: set[str] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
    item_limit: int | None = MAX_STATUS_TODOS_PER_ROLE,
) -> dict[str, Any]:
    role: str | None = None
    source_sections: dict[str, str | None] = {"user": None, "agent": None}
    items: dict[str, list[dict[str, Any]]] = {"user": [], "agent": []}
    archive_items: list[dict[str, Any]] = []
    archive_mode = False
    archive_source_section: str | None = None
    current_todo: dict[str, Any] | None = None

    for line in state_text.splitlines():
        if line.startswith("## "):
            heading = line.lstrip("#").strip()
            normalized_heading = heading.strip().lower()
            archive_mode = any(
                marker in normalized_heading for marker in TODO_ARCHIVE_HEADER_MARKERS
            )
            archive_source_section = heading if archive_mode else None
            role = todo_role_for_heading(heading)
            current_todo = None
            if role and source_sections[role] is None:
                source_sections[role] = heading
            continue
        if role is None and not archive_mode:
            continue
        match = TODO_TASK_PATTERN.match(line)
        if match:
            marker, text = match.groups()
            status = todo_status_from_marker(marker)
            target_items = archive_items if archive_mode else items[str(role)]
            todo: dict[str, Any] = {
                "index": len(target_items) + 1,
                "done": todo_done_for_status(status),
                "status": status,
                "text": normalize_todo_text(text),
            }
            if archive_mode:
                todo["archive_state"] = "archive"
                todo["source_section"] = archive_source_section
            else:
                todo["archive_state"] = "active"
                todo["source_section"] = source_sections[str(role)]
                todo["role"] = role
            if goal is not None:
                materials = extract_review_materials(text, goal=goal, state_path=state_path)
                if materials:
                    todo["review_materials"] = materials
            target_items.append(todo)
            current_todo = todo
            continue
        if current_todo is None or not line.startswith((" ", "\t")):
            continue
        metadata = parse_todo_metadata_line(line)
        if metadata:
            current_todo.update(metadata)
            continue
        continuation = line.strip()
        if continuation:
            current_todo["text"] = normalize_todo_text(
                f"{current_todo.get('text', '')} {continuation}"
            )

    result: dict[str, Any] = {}
    archived_resume_source_items = [
        item for item in archive_items if normalize_todo_id(item.get("todo_id"))
    ]
    resume_source_items = [*items["user"], *items["agent"], *archived_resume_source_items]
    user = compact_todo_group(
        items["user"],
        source_section=source_sections["user"],
        role="user",
        preferred_todo_ids=preferred_todo_ids,
        resume_source_items=resume_source_items,
        rollout_events=rollout_events,
        item_limit=item_limit,
    )
    agent = compact_todo_group(
        items["agent"],
        source_section=source_sections["agent"],
        role="agent",
        preferred_todo_ids=preferred_todo_ids,
        resume_source_items=resume_source_items,
        rollout_events=rollout_events,
        item_limit=item_limit,
    )
    if user:
        result["user_todos"] = user
    if agent:
        result["agent_todos"] = agent
    return result
