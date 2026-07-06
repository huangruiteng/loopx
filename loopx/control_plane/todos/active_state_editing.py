from __future__ import annotations

import re
from typing import Any

from ..goals.active_state_metadata import todo_role_for_heading
from .contract import (
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_PATTERN,
    build_todo_id,
    normalize_todo_status,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_status_from_marker,
)
from .todo_summary import normalize_todo_text


TODO_SECTION_HEADINGS = {
    "user": "User Todo / Owner Review Reading Queue",
    "agent": "Agent Todo",
}
COMPLETED_WORK_ARCHIVE_HEADING = "Completed Work Archive"


def section_bounds(lines: list[str], role: str) -> tuple[int, int, str] | None:
    for index, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        heading = line.lstrip("#").strip()
        if todo_role_for_heading(heading) != role:
            continue
        end = len(lines)
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("## "):
                end = next_index
                break
        return index, end, heading
    return None


def heading_index(lines: list[str], heading: str) -> int | None:
    needle = f"## {heading}"
    for index, line in enumerate(lines):
        if line.strip() == needle:
            return index
    return None


def insert_into_existing_section(lines: list[str], start: int, end: int, todo_line: str) -> None:
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new_lines = todo_line.splitlines()
    if insert_at == start + 1:
        new_lines.insert(0, "")
    if insert_at == end and end < len(lines) and lines[end].startswith("## "):
        new_lines.append("")
    lines[insert_at:insert_at] = new_lines


def insertion_anchor(lines: list[str], role: str) -> int:
    if role == "user":
        agent_bounds = section_bounds(lines, "agent")
        if agent_bounds:
            return agent_bounds[0]
    next_action = heading_index(lines, "Next Action")
    if next_action is not None:
        return next_action
    return len(lines)


def insert_new_section(lines: list[str], role: str, todo_line: str) -> None:
    anchor = insertion_anchor(lines, role)
    heading = TODO_SECTION_HEADINGS[role]
    section = [f"## {heading}", "", *todo_line.splitlines(), ""]
    if anchor > 0 and lines[anchor - 1].strip():
        section.insert(0, "")
    lines[anchor:anchor] = section


def archive_section_bounds(lines: list[str]) -> tuple[int, int] | None:
    start = heading_index(lines, COMPLETED_WORK_ARCHIVE_HEADING)
    if start is None:
        return None
    end = len(lines)
    for next_index in range(start + 1, len(lines)):
        if lines[next_index].startswith("## "):
            end = next_index
            break
    return start, end


def ensure_archive_section(lines: list[str]) -> tuple[int, int]:
    bounds = archive_section_bounds(lines)
    if bounds:
        return bounds
    if lines and lines[-1].strip():
        lines.append("")
    start = len(lines)
    lines.extend([f"## {COMPLETED_WORK_ARCHIVE_HEADING}", ""])
    return start, len(lines)


def ensure_block_identity(
    block: dict[str, Any],
    *,
    role: str | None,
    source_section: str | None,
) -> dict[str, Any]:
    if block.get("status"):
        status = normalize_todo_status(block.get("status")) or TODO_STATUS_OPEN
    else:
        status = TODO_STATUS_DONE if block.get("done") else TODO_STATUS_OPEN
    block["status"] = status
    block["done"] = todo_done_for_status(status)
    if not block.get("todo_id"):
        block["todo_id"] = build_todo_id(
            role=role,
            source_section=source_section,
            index=block.get("index"),
            text=block.get("text"),
        )
    return block


def todo_blocks(
    lines: list[str],
    start: int,
    end: int,
    *,
    role: str | None = None,
    source_section: str | None = None,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    todo_index = 0
    for index in range(start + 1, end):
        match = TODO_TASK_PATTERN.match(lines[index])
        if match:
            if current is not None:
                current["end"] = index
                ensure_block_identity(current, role=role, source_section=source_section)
                blocks.append(current)
            marker, text = match.groups()
            todo_index += 1
            status = todo_status_from_marker(marker)
            current = {
                "start": index,
                "end": end,
                "index": todo_index,
                "done": todo_done_for_status(status),
                "status": status,
                "text": normalize_todo_text(text),
            }
            continue
        if current is not None and lines[index].startswith((" ", "\t")):
            metadata = parse_todo_metadata_line(lines[index])
            if metadata:
                current.update(metadata)
                continue
            continuation = lines[index].strip()
            if continuation:
                current["text"] = normalize_todo_text(
                    f"{current.get('text', '')} {continuation}"
                )
    if current is not None:
        current["end"] = end
        ensure_block_identity(current, role=role, source_section=source_section)
        blocks.append(current)
    return blocks


def insert_archive_blocks(lines: list[str], blocks: list[list[str]]) -> None:
    if not blocks:
        return
    bounds = ensure_archive_section(lines)
    insert_at = bounds[1]
    while insert_at > bounds[0] + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new_lines: list[str] = []
    if insert_at == bounds[0] + 1:
        new_lines.append("")
    for block in blocks:
        new_lines.extend(block)
    if insert_at < len(lines) and lines[insert_at].startswith("## "):
        new_lines.append("")
    lines[insert_at:insert_at] = new_lines


def replace_updated_at(text: str, updated_at: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    frontmatter = parts[1]
    body = parts[2]
    if re.search(r"(?m)^updated_at:\s*.+$", frontmatter):
        frontmatter = re.sub(
            r"(?m)^updated_at:\s*.+$",
            f"updated_at: {updated_at}",
            frontmatter,
            count=1,
        )
    else:
        frontmatter = frontmatter.rstrip("\n") + f"\nupdated_at: {updated_at}\n"
    return "---" + frontmatter + "---" + body
