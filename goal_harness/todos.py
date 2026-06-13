from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .history import load_registry
from .state_refresh import now_local, resolve_goal_state
from .status import (
    MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
    normalize_todo_text,
    todo_role_for_heading,
)
from .todo_contract import TODO_TASK_PATTERN, format_todo_metadata_line, parse_todo_metadata_line


TODO_SECTION_HEADINGS = {
    "user": "User Todo / Owner Review Reading Queue",
    "agent": "Agent Todo",
}
COMPLETED_WORK_ARCHIVE_HEADING = "Completed Work Archive"


def normalize_new_todo(text: str) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        raise ValueError("todo text must not be empty")
    return compact


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


def section_has_todo(lines: list[str], start: int, end: int, text: str) -> bool:
    expected = normalize_todo_text(text)
    for line in lines[start + 1 : end]:
        match = TODO_TASK_PATTERN.match(line)
        if not match:
            continue
        if normalize_todo_text(match.group(2)) == expected:
            return True
    return False


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


def todo_blocks(lines: list[str], start: int, end: int) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index in range(start + 1, end):
        match = TODO_TASK_PATTERN.match(lines[index])
        if match:
            if current is not None:
                current["end"] = index
                blocks.append(current)
            marker, text = match.groups()
            current = {
                "start": index,
                "end": end,
                "done": marker.lower() == "x",
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
        frontmatter = re.sub(r"(?m)^updated_at:\s*.+$", f"updated_at: {updated_at}", frontmatter, count=1)
    else:
        frontmatter = frontmatter.rstrip("\n") + f"\nupdated_at: {updated_at}\n"
    return "---" + frontmatter + "---" + body


def matching_todo_block(lines: list[str], start: int, end: int, text: str) -> dict[str, Any] | None:
    expected = normalize_todo_text(text)
    for block in todo_blocks(lines, start, end):
        if normalize_todo_text(str(block.get("text") or "")) == expected:
            return block
    return None


def upsert_todo_metadata(lines: list[str], block: dict[str, Any], metadata_line: str | None) -> bool:
    if not metadata_line:
        return False
    start = int(block["start"])
    end = int(block["end"])
    for index in range(start + 1, end):
        if parse_todo_metadata_line(lines[index]) is not None:
            if lines[index] == metadata_line:
                return False
            lines[index] = metadata_line
            return True
    lines.insert(start + 1, metadata_line)
    return True


def add_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    role: str,
    text: str,
    task_class: str | None = None,
    action_kind: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if role not in TODO_SECTION_HEADINGS:
        raise ValueError("todo role must be one of: user, agent")
    todo_text = normalize_new_todo(text)
    registry = load_registry(registry_path)
    goal, resolved_project, resolved_state_file = resolve_goal_state(
        registry=registry,
        goal_id=goal_id,
        project_override=project,
        state_file_override=state_file,
    )
    if goal is None:
        raise ValueError(f"goal {goal_id!r} is not present in the registry")
    if not resolved_state_file.exists():
        raise ValueError(f"active state file does not exist: {resolved_state_file}")

    original = resolved_state_file.read_text(encoding="utf-8")
    lines = original.splitlines()
    bounds = section_bounds(lines, role)
    section = bounds[2] if bounds else TODO_SECTION_HEADINGS[role]
    metadata_line = format_todo_metadata_line(task_class=task_class, action_kind=action_kind)
    metadata = parse_todo_metadata_line(metadata_line) if metadata_line else {}
    todo_lines = [f"- [ ] {todo_text}"]
    if metadata_line:
        todo_lines.append(metadata_line)
    todo_line = "\n".join(todo_lines)
    already_exists = bool(bounds and section_has_todo(lines, bounds[0], bounds[1], todo_text))
    added = not already_exists
    metadata_updated = False

    if added:
        if bounds:
            insert_into_existing_section(lines, bounds[0], bounds[1], todo_line)
        else:
            insert_new_section(lines, role, todo_line)
    elif bounds and metadata_line:
        block = matching_todo_block(lines, bounds[0], bounds[1], todo_text)
        if block:
            metadata_updated = upsert_todo_metadata(lines, block, metadata_line)

    updated_at = now_local()
    new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
    if added or metadata_updated:
        new_text = replace_updated_at(new_text, updated_at)
    if (added or metadata_updated) and not dry_run:
        resolved_state_file.write_text(new_text, encoding="utf-8")

    return {
        "ok": True,
        "dry_run": dry_run,
        "added": added,
        "already_exists": already_exists,
        "metadata_updated": metadata_updated,
        "goal_id": goal_id,
        "role": role,
        "section": section,
        "todo": todo_text,
        "task_class": metadata.get("task_class") if metadata else None,
        "action_kind": metadata.get("action_kind") if metadata else None,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if added or metadata_updated else None,
    }


def archive_completed_todos(
    *,
    registry_path: Path,
    goal_id: str,
    role: str = "agent",
    max_active_done: int = MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    if role not in TODO_SECTION_HEADINGS:
        raise ValueError("todo role must be one of: user, agent")
    if max_active_done < 0:
        raise ValueError("max_active_done must be non-negative")
    registry = load_registry(registry_path)
    goal, resolved_project, resolved_state_file = resolve_goal_state(
        registry=registry,
        goal_id=goal_id,
        project_override=project,
        state_file_override=state_file,
    )
    if goal is None:
        raise ValueError(f"goal {goal_id!r} is not present in the registry")
    if not resolved_state_file.exists():
        raise ValueError(f"active state file does not exist: {resolved_state_file}")

    original = resolved_state_file.read_text(encoding="utf-8")
    lines = original.splitlines()
    bounds = section_bounds(lines, role)
    section = bounds[2] if bounds else TODO_SECTION_HEADINGS[role]
    moved_blocks: list[list[str]] = []
    active_done_count = 0
    moved_count = 0
    kept_done_count = 0

    if bounds:
        blocks = todo_blocks(lines, bounds[0], bounds[1])
        done_blocks = [block for block in blocks if block.get("done") is True]
        active_done_count = len(done_blocks)
        move_count = max(0, active_done_count - max_active_done)
        move_starts = {int(block["start"]) for block in done_blocks[:move_count]}
        kept_done_count = active_done_count - move_count
        for block in done_blocks[:move_count]:
            moved_blocks.append(lines[int(block["start"]) : int(block["end"])])
        if move_starts:
            new_lines: list[str] = []
            index = 0
            while index < len(lines):
                if index in move_starts:
                    matching = next(
                        block
                        for block in done_blocks[:move_count]
                        if int(block["start"]) == index
                    )
                    index = int(matching["end"])
                    while (
                        new_lines
                        and not new_lines[-1].strip()
                        and index < len(lines)
                        and not lines[index].strip()
                    ):
                        index += 1
                    continue
                new_lines.append(lines[index])
                index += 1
            lines = new_lines
            insert_archive_blocks(lines, moved_blocks)
            moved_count = move_count

    updated_at = now_local()
    changed = moved_count > 0
    new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
    if changed:
        new_text = replace_updated_at(new_text, updated_at)
    if changed and not dry_run:
        resolved_state_file.write_text(new_text, encoding="utf-8")

    return {
        "ok": True,
        "dry_run": dry_run,
        "changed": changed,
        "goal_id": goal_id,
        "role": role,
        "section": section,
        "archive_section": COMPLETED_WORK_ARCHIVE_HEADING,
        "active_done_before": active_done_count,
        "active_done_after": kept_done_count,
        "max_active_done": max_active_done,
        "moved_count": moved_count,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
    }


def render_todo_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Todo",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- role: `{payload.get('role')}`",
        f"- section: `{payload.get('section')}`",
        f"- state_file: `{payload.get('state_file')}`",
    ]
    if "moved_count" in payload:
        lines.extend(
            [
                f"- changed: `{payload.get('changed')}`",
                f"- archive_section: `{payload.get('archive_section')}`",
                f"- active_done_before: `{payload.get('active_done_before')}`",
                f"- active_done_after: `{payload.get('active_done_after')}`",
                f"- max_active_done: `{payload.get('max_active_done')}`",
                f"- moved_count: `{payload.get('moved_count')}`",
            ]
        )
    else:
        lines.extend(
            [
                f"- added: `{payload.get('added')}`",
                f"- already_exists: `{payload.get('already_exists')}`",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    elif "todo" in payload:
        lines.extend(["", "## Todo", "", f"- [ ] {payload.get('todo')}"])
    return "\n".join(lines)
