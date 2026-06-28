from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .agent_registry import (
    primary_agent_id_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
    side_agent_handoff_agent_id_from_registry,
)
from .file_lock import exclusive_file_lock
from .history import load_registry
from .local_state_write_correctness import build_todo_write_correctness_dry_run_packet
from .state_refresh import now_local, resolve_goal_state
from .status import (
    MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
    active_state_event_projection_fields,
    compact_todo_group,
    normalize_todo_text,
    parse_active_state_todos,
    parse_timestamp,
    todo_role_for_heading,
)
from .todo_contract import (
    TODO_MONITOR_METADATA_FIELDS,
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_USER_GATE,
    TODO_TASK_PATTERN,
    build_todo_id,
    format_todo_metadata_line,
    normalize_required_capabilities,
    normalize_required_write_scopes,
    normalize_target_capabilities,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_global_gate,
    normalize_todo_id,
    normalize_todo_no_followup,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_marker_for_status,
    todo_status_from_marker,
)


TODO_SECTION_HEADINGS = {
    "user": "User Todo / Owner Review Reading Queue",
    "agent": "Agent Todo",
}
COMPLETED_WORK_ARCHIVE_HEADING = "Completed Work Archive"
TODO_METADATA_FIELDS = (
    "todo_id",
    "status",
    "task_class",
    "action_kind",
    "required_write_scopes",
    "required_capabilities",
    "target_capabilities",
    "decision_scope",
    "required_decision_scopes",
    "claimed_by",
    "blocks_agent",
    "global_gate",
    "unblocks_todo_id",
    "resume_when",
    "no_followup",
    "target_key",
    "cadence",
    "next_due_at",
    "expires_at",
    "last_checked_at",
    "result_hash",
    "consecutive_no_change",
    "material_change",
    "max_no_change_before_replan",
    "note",
    "evidence",
    "reason",
    "completed_at",
    "updated_at",
    "superseded_by",
)


def _attach_todo_write_correctness_dry_run_packet(
    payload: dict[str, Any],
    *,
    goal_id: str,
    write_class: str,
    state_text: str,
) -> dict[str, Any]:
    if not payload.get("dry_run"):
        return payload
    todo_id = normalize_todo_id(str(payload.get("todo_id") or "")) or None
    claimed_by = normalize_todo_claimed_by(payload.get("claimed_by"))
    changed = bool(
        payload.get("changed")
        or payload.get("added")
        or payload.get("metadata_updated")
        or payload.get("completed")
        or payload.get("superseded")
    )
    payload["local_state_write_correctness"] = build_todo_write_correctness_dry_run_packet(
        goal_id=goal_id,
        write_class=write_class,
        state_text=state_text,
        todo_id=todo_id,
        role=str(payload.get("role") or ""),
        section=str(payload.get("section") or ""),
        claimed_by=claimed_by,
        changed=changed,
    )
    return payload
TODO_PRIORITY_PREFIX_PATTERN = re.compile(r"^\[(P[0-4])\]\s+", re.IGNORECASE)
MONITOR_CADENCE_PATTERN = re.compile(
    r"^\s*(?P<count>[1-9][0-9]{0,4})\s*"
    r"(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
    re.IGNORECASE,
)


def normalize_new_todo(text: str) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        raise ValueError("todo text must not be empty")
    return compact


def todo_priority_prefix(text: str | None) -> str | None:
    match = TODO_PRIORITY_PREFIX_PATTERN.match(str(text or "").strip())
    if not match:
        return None
    return match.group(1).upper()


def inherit_todo_priority(next_text: str, source_text: str | None) -> str:
    normalized = normalize_new_todo(next_text)
    if todo_priority_prefix(normalized):
        return normalized
    source_priority = todo_priority_prefix(source_text)
    if not source_priority:
        return normalized
    return f"[{source_priority}] {normalized}"


def normalize_monitor_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        if key not in TODO_MONITOR_METADATA_FIELDS:
            continue
        candidate = str(value or "").strip()
        if candidate:
            normalized[key] = candidate
    if "cadence" in normalized and not MONITOR_CADENCE_PATTERN.match(normalized["cadence"]):
        raise ValueError("--cadence must look like 30m, 2h, or 1d")
    if "next_due_at" in normalized and parse_timestamp(normalized["next_due_at"]) is None:
        raise ValueError("--next-due-at must be an ISO timestamp")
    if "expires_at" in normalized and parse_timestamp(normalized["expires_at"]) is None:
        raise ValueError("--expires-at must be an ISO timestamp")
    if "last_checked_at" in normalized and parse_timestamp(normalized["last_checked_at"]) is None:
        raise ValueError("--last-checked-at must be an ISO timestamp")
    if "consecutive_no_change" in normalized:
        try:
            int(normalized["consecutive_no_change"])
        except ValueError as exc:
            raise ValueError("--consecutive-no-change must be an integer") from exc
    if "material_change" in normalized and normalized["material_change"] not in {"true", "false"}:
        raise ValueError("--material-change metadata must be true or false")
    return normalized


def require_monitor_metadata_scope(
    *,
    monitor_metadata: dict[str, Any] | None,
    role: str,
    task_class: str | None,
) -> dict[str, str]:
    normalized = normalize_monitor_metadata(monitor_metadata)
    if not normalized:
        return {}
    if role != "agent" or task_class != "continuous_monitor":
        raise ValueError(
            "monitor schedule metadata requires --role agent --task-class continuous_monitor"
        )
    return normalized


def resolve_todo_state_path(
    *,
    registry_path: Path,
    goal_id: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> tuple[Path | None, Path]:
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
    return resolved_project, resolved_state_file


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


def ensure_block_identity(block: dict[str, Any], *, role: str | None, source_section: str | None) -> dict[str, Any]:
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


def todo_item_status(item: dict[str, Any]) -> str:
    status = normalize_todo_status(item.get("status"))
    if status:
        return status
    return TODO_STATUS_DONE if item.get("done") else TODO_STATUS_OPEN


def empty_todo_summary(*, role: str) -> dict[str, Any]:
    return {
        "schema_version": "todo_summary_v0",
        "role": role,
        "source_section": TODO_SECTION_HEADINGS[role],
        "total_count": 0,
        "open_count": 0,
        "done_count": 0,
        "items": [],
        "first_open_items": [],
    }


def filtered_todo_summary(
    summary: dict[str, Any] | None,
    *,
    role: str,
    status: str | None = None,
) -> dict[str, Any]:
    items = list((summary or {}).get("items") or [])
    normalized_status = normalize_todo_status(status)
    if normalized_status:
        items = [item for item in items if todo_item_status(item) == normalized_status]
    source_section = str((summary or {}).get("source_section") or TODO_SECTION_HEADINGS[role])
    return compact_todo_group(items, source_section=source_section, role=role) or empty_todo_summary(role=role)


def list_goal_todos(
    *,
    registry_path: Path,
    goal_id: str,
    role: str | None = None,
    status: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
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

    projection_fields = active_state_event_projection_fields(
        goal,
        state_path=resolved_state_file,
    )
    projection_has_todos = bool(
        projection_fields.get("user_todos") or projection_fields.get("agent_todos")
    )
    if projection_has_todos:
        fields = projection_fields
        source = "event_projection"
    else:
        fields = parse_active_state_todos(
            resolved_state_file.read_text(encoding="utf-8"),
            goal=goal,
            state_path=resolved_state_file,
        )
        source = "markdown_active_state"

    roles = [role] if role else ["user", "agent"]
    summaries: dict[str, dict[str, Any]] = {}
    todos: list[dict[str, Any]] = []
    for item_role in roles:
        key = f"{item_role}_todos"
        summary = filtered_todo_summary(
            fields.get(key) if isinstance(fields, dict) else None,
            role=item_role,
            status=status,
        )
        summaries[key] = summary
        todos.extend(summary.get("items") or [])

    payload: dict[str, Any] = {
        "ok": True,
        "dry_run": True,
        "read_only": True,
        "command": "list",
        "goal_id": goal_id,
        "role": role or "all",
        "status_filter": normalize_todo_status(status) if status else None,
        "source": source,
        "todo_count": len(todos),
        "todos": todos,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
    }
    payload.update(summaries)
    if source == "event_projection" and projection_fields.get("state_event_projection"):
        payload["state_event_projection"] = projection_fields["state_event_projection"]
    if projection_fields.get("state_event_projection_warning"):
        payload["state_event_projection_warning"] = projection_fields["state_event_projection_warning"]
    return payload


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


def matching_todo_block(
    lines: list[str],
    start: int,
    end: int,
    text: str,
    *,
    role: str | None = None,
    source_section: str | None = None,
) -> dict[str, Any] | None:
    expected = normalize_todo_text(text)
    for block in todo_blocks(lines, start, end, role=role, source_section=source_section):
        if normalize_todo_text(str(block.get("text") or "")) == expected:
            return block
    return None


def block_metadata(block: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in TODO_METADATA_FIELDS:
        value = block.get(key)
        if value is None:
            continue
        if key == "required_write_scopes":
            scopes = normalize_required_write_scopes(value)
            if scopes:
                metadata[key] = scopes
            continue
        if key == "required_capabilities":
            capabilities = normalize_required_capabilities(value)
            if capabilities:
                metadata[key] = capabilities
            continue
        if key == "target_capabilities":
            capabilities = normalize_target_capabilities(value)
            if capabilities:
                metadata[key] = capabilities
            continue
        if key == "decision_scope":
            decision_scope = normalize_todo_decision_scope(value)
            if decision_scope:
                metadata[key] = decision_scope
            continue
        if key == "required_decision_scopes":
            scopes = normalize_todo_required_decision_scopes(value)
            if scopes:
                metadata[key] = scopes
            continue
        if key == "no_followup":
            no_followup = normalize_todo_no_followup(value)
            if no_followup is not None:
                metadata[key] = no_followup
            continue
        if key == "global_gate":
            global_gate = normalize_todo_global_gate(value)
            if global_gate is not None:
                metadata[key] = global_gate
            continue
        if str(value or "").strip():
            metadata[key] = str(value).strip()
    return metadata


def metadata_line_for_block(block: dict[str, Any], updates: dict[str, Any]) -> str | None:
    metadata = block_metadata(block)
    for key, value in updates.items():
        if key not in TODO_METADATA_FIELDS:
            continue
        if value is None:
            metadata.pop(key, None)
        elif key == "required_write_scopes":
            scopes = normalize_required_write_scopes(value)
            if scopes:
                metadata[key] = scopes
            else:
                metadata.pop(key, None)
        elif key == "required_capabilities":
            capabilities = normalize_required_capabilities(value)
            if capabilities:
                metadata[key] = capabilities
            else:
                metadata.pop(key, None)
        elif key == "target_capabilities":
            capabilities = normalize_target_capabilities(value)
            if capabilities:
                metadata[key] = capabilities
            else:
                metadata.pop(key, None)
        elif key == "decision_scope":
            decision_scope = normalize_todo_decision_scope(value)
            if decision_scope:
                metadata[key] = decision_scope
            else:
                metadata.pop(key, None)
        elif key == "required_decision_scopes":
            scopes = normalize_todo_required_decision_scopes(value)
            if scopes:
                metadata[key] = scopes
            else:
                metadata.pop(key, None)
        elif key == "no_followup":
            no_followup = normalize_todo_no_followup(value)
            if no_followup is not None:
                metadata[key] = no_followup
            else:
                metadata.pop(key, None)
        elif key == "global_gate":
            global_gate = normalize_todo_global_gate(value)
            if global_gate is not None:
                metadata[key] = global_gate
            else:
                metadata.pop(key, None)
        elif str(value).strip():
            metadata[key] = str(value).strip()
    if "todo_id" not in metadata and block.get("todo_id"):
        metadata["todo_id"] = str(block["todo_id"])
    if "status" not in metadata:
        metadata["status"] = TODO_STATUS_DONE if block.get("done") else TODO_STATUS_OPEN
    return format_todo_metadata_line(**metadata)


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
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, metadata_line)
    return True


def todo_metadata_would_change(lines: list[str], block: dict[str, Any], metadata_line: str | None) -> bool:
    if not metadata_line:
        return False
    start = int(block["start"])
    end = int(block["end"])
    for index in range(start + 1, end):
        if parse_todo_metadata_line(lines[index]) is not None:
            return lines[index] != metadata_line
    return True


def set_todo_marker(lines: list[str], block: dict[str, Any], status: str) -> bool:
    marker = todo_marker_for_status(status)
    index = int(block["start"])
    updated = re.sub(r"^(\s*[-*]\s+\[)[ xX-](\]\s+)", rf"\1{marker}\2", lines[index], count=1)
    if updated == lines[index]:
        return False
    lines[index] = updated
    return True


def set_todo_text(lines: list[str], block: dict[str, Any], text: str, *, status: str) -> bool:
    normalized = normalize_new_todo(text)
    if normalize_todo_text(str(block.get("text") or "")) == normalized:
        return False

    start = int(block["start"])
    end = int(block["end"])
    marker = todo_marker_for_status(status)
    replacement = f"- [{marker}] {normalized}"
    remove_until = start + 1
    while remove_until < end and lines[remove_until].startswith((" ", "\t")):
        if parse_todo_metadata_line(lines[remove_until]) is not None:
            break
        remove_until += 1
    removed = remove_until - start
    lines[start:remove_until] = [replacement]
    block["text"] = normalized
    block["end"] = end - (removed - 1)
    return True


def find_todo_block(
    lines: list[str],
    *,
    todo_id: str,
    role: str | None = None,
) -> tuple[str, str, int, int, dict[str, Any]] | None:
    roles = [role] if role else list(TODO_SECTION_HEADINGS)
    for candidate_role in roles:
        if candidate_role not in TODO_SECTION_HEADINGS:
            continue
        bounds = section_bounds(lines, candidate_role)
        if not bounds:
            continue
        start, end, section = bounds
        for block in todo_blocks(
            lines,
            start,
            end,
            role=candidate_role,
            source_section=section,
        ):
            if block.get("todo_id") == todo_id:
                return candidate_role, section, start, end, block
    return None


def add_todo_to_lines(
    lines: list[str],
    *,
    role: str,
    text: str,
    task_class: str | None = None,
    action_kind: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
    global_gate: bool | None = None,
    unblocks_todo_id: str | None = None,
    resume_when: str | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    todo_text = normalize_new_todo(text)
    normalized_monitor_metadata = require_monitor_metadata_scope(
        monitor_metadata=monitor_metadata,
        role=role,
        task_class=task_class,
    )
    bounds = section_bounds(lines, role)
    section = bounds[2] if bounds else TODO_SECTION_HEADINGS[role]
    existing_blocks = (
        todo_blocks(lines, bounds[0], bounds[1], role=role, source_section=section)
        if bounds
        else []
    )
    block = matching_todo_block(
        lines,
        bounds[0],
        bounds[1],
        todo_text,
        role=role,
        source_section=section,
    ) if bounds else None
    added = block is None
    metadata_updated = False

    if block is None:
        todo_id = build_todo_id(
            role=role,
            source_section=section,
            index=len(existing_blocks) + 1,
            text=todo_text,
        )
        metadata_line = format_todo_metadata_line(
            todo_id=todo_id,
            status=TODO_STATUS_OPEN,
            task_class=task_class,
            action_kind=action_kind,
            required_write_scopes=required_write_scopes,
            required_capabilities=required_capabilities,
            target_capabilities=target_capabilities,
            decision_scope=decision_scope,
            required_decision_scopes=required_decision_scopes,
            claimed_by=claimed_by,
            blocks_agent=blocks_agent,
            global_gate=global_gate,
            unblocks_todo_id=unblocks_todo_id,
            resume_when=resume_when,
            **normalized_monitor_metadata,
            evidence=evidence,
        )
        todo_line = "\n".join([f"- [ ] {todo_text}", metadata_line] if metadata_line else [f"- [ ] {todo_text}"])
        if bounds:
            insert_into_existing_section(lines, bounds[0], bounds[1], todo_line)
        else:
            insert_new_section(lines, role, todo_line)
        effective_metadata = parse_todo_metadata_line(metadata_line or "") or {}
    else:
        updates: dict[str, Any] = {
            "todo_id": block.get("todo_id"),
            "status": block.get("status") or TODO_STATUS_OPEN,
        }
        if task_class:
            updates["task_class"] = task_class
        if action_kind:
            updates["action_kind"] = action_kind
        if required_write_scopes is not None:
            updates["required_write_scopes"] = required_write_scopes
        if required_capabilities is not None:
            updates["required_capabilities"] = required_capabilities
        if target_capabilities is not None:
            updates["target_capabilities"] = target_capabilities
        if decision_scope is not None:
            updates["decision_scope"] = decision_scope
        if required_decision_scopes is not None:
            updates["required_decision_scopes"] = required_decision_scopes
        if claimed_by:
            updates["claimed_by"] = claimed_by
        if blocks_agent:
            updates["blocks_agent"] = blocks_agent
        if global_gate is not None:
            updates["global_gate"] = global_gate
        if unblocks_todo_id:
            updates["unblocks_todo_id"] = unblocks_todo_id
        if resume_when:
            updates["resume_when"] = resume_when
        updates.update(normalized_monitor_metadata)
        if evidence:
            updates["evidence"] = evidence
        metadata_line = metadata_line_for_block(block, updates)
        metadata_updated = upsert_todo_metadata(lines, block, metadata_line)
        todo_id = str(block.get("todo_id") or "")
        effective_metadata = parse_todo_metadata_line(metadata_line or "") or {}

    return {
        "added": added,
        "already_exists": not added,
        "metadata_updated": metadata_updated,
        "role": role,
        "section": section,
        "todo": todo_text,
        "todo_id": todo_id,
        "task_class": effective_metadata.get("task_class") or task_class,
        "action_kind": effective_metadata.get("action_kind") or action_kind,
        "required_write_scopes": normalize_required_write_scopes(
            effective_metadata.get("required_write_scopes") or required_write_scopes
        ),
        "required_capabilities": normalize_required_capabilities(
            effective_metadata.get("required_capabilities") or required_capabilities
        ),
        "target_capabilities": normalize_target_capabilities(
            effective_metadata.get("target_capabilities") or target_capabilities
        ),
        "decision_scope": normalize_todo_decision_scope(
            effective_metadata.get("decision_scope") or decision_scope
        ),
        "required_decision_scopes": normalize_todo_required_decision_scopes(
            effective_metadata.get("required_decision_scopes") or required_decision_scopes
        ),
        "claimed_by": normalize_todo_claimed_by(effective_metadata.get("claimed_by")),
        "blocks_agent": normalize_todo_blocks_agent(effective_metadata.get("blocks_agent")),
        "global_gate": normalize_todo_global_gate(effective_metadata.get("global_gate")),
        "unblocks_todo_id": normalize_todo_id(effective_metadata.get("unblocks_todo_id")),
        "resume_when": normalize_todo_resume_when(effective_metadata.get("resume_when")),
        "target_key": effective_metadata.get("target_key"),
        "cadence": effective_metadata.get("cadence"),
        "next_due_at": effective_metadata.get("next_due_at"),
        "expires_at": effective_metadata.get("expires_at"),
        "evidence": effective_metadata.get("evidence") or evidence,
    }


def require_user_gate_scope(
    *,
    registry_path: Path,
    goal_id: str,
    role: str,
    task_class: str | None,
    blocks_agent: str | None,
    global_gate: bool | None,
) -> None:
    if role != "user" or task_class != TODO_TASK_CLASS_USER_GATE:
        return
    if global_gate and blocks_agent:
        raise ValueError(
            "user_gate cannot set both blocks_agent and global_gate=true; "
            "use blocks_agent for one registered agent or global_gate=true for a goal-wide gate"
        )
    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    if len(registered_agents) <= 1:
        return
    if blocks_agent or global_gate is True:
        return
    raise ValueError(
        "multi-agent user_gate requires an explicit scope: pass --blocks-agent "
        "<registered-agent> (or --agent-id <registered-agent> for authoring) "
        "when the gate blocks one lane, or pass --global-gate when it genuinely "
        "blocks every registered agent"
    )


def add_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    role: str,
    text: str,
    task_class: str | None = None,
    action_kind: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
    global_gate: bool = False,
    agent_id: str | None = None,
    unblocks_todo_id: str | None = None,
    resume_when: str | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if role not in TODO_SECTION_HEADINGS:
        raise ValueError("todo role must be one of: user, agent")
    if global_gate and not (role == "user" and task_class == TODO_TASK_CLASS_USER_GATE):
        raise ValueError("global_gate is only valid for `--role user --task-class user_gate`")
    todo_text = normalize_new_todo(text)
    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )

    with exclusive_file_lock(resolved_state_file):
        original = resolved_state_file.read_text(encoding="utf-8")
        lines = original.splitlines()
        updated_at = now_local()
        effective_claimed_by = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=claimed_by,
            )
            if claimed_by
            else None
        )
        effective_agent_id = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=agent_id,
                field="agent_id",
            )
            if agent_id
            else None
        )
        inferred_blocks_agent = blocks_agent
        if (
            effective_agent_id
            and not inferred_blocks_agent
            and role == "user"
            and task_class == TODO_TASK_CLASS_USER_GATE
        ):
            inferred_blocks_agent = effective_agent_id
        effective_blocks_agent = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=inferred_blocks_agent,
                field="blocks_agent",
            )
            if inferred_blocks_agent
            else None
        )
        require_user_gate_scope(
            registry_path=registry_path,
            goal_id=goal_id,
            role=role,
            task_class=task_class,
            blocks_agent=effective_blocks_agent,
            global_gate=True if global_gate else None,
        )
        normalized_unblocks_todo_id = normalize_todo_id(unblocks_todo_id) if unblocks_todo_id else None
        if unblocks_todo_id and not normalized_unblocks_todo_id:
            raise ValueError("unblocks_todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
        normalized_resume_when = normalize_todo_resume_when(resume_when) if resume_when else None
        if resume_when and not normalized_resume_when:
            raise ValueError("resume_when must be public-safe, e.g. todo_done:todo_ab12cd34ef56 or pr_merged:#532")
        normalized_monitor_metadata = require_monitor_metadata_scope(
            monitor_metadata=monitor_metadata,
            role=role,
            task_class=task_class,
        )
        add_result = add_todo_to_lines(
            lines,
            role=role,
            text=todo_text,
            task_class=task_class,
            action_kind=action_kind,
            required_write_scopes=required_write_scopes,
            required_capabilities=required_capabilities,
            target_capabilities=target_capabilities,
            decision_scope=decision_scope,
            required_decision_scopes=required_decision_scopes,
            claimed_by=effective_claimed_by,
            blocks_agent=effective_blocks_agent,
            global_gate=True if global_gate else None,
            unblocks_todo_id=normalized_unblocks_todo_id,
            resume_when=normalized_resume_when,
            monitor_metadata=normalized_monitor_metadata,
        )
        added = bool(add_result["added"])
        metadata_updated = bool(add_result["metadata_updated"])

        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if added or metadata_updated:
            new_text = replace_updated_at(new_text, updated_at)
        if (added or metadata_updated) and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")

    payload = {
        "ok": True,
        "dry_run": dry_run,
        "added": added,
        "already_exists": bool(add_result["already_exists"]),
        "metadata_updated": metadata_updated,
        "goal_id": goal_id,
        "role": role,
        "section": add_result.get("section"),
        "todo": todo_text,
        "todo_id": add_result.get("todo_id"),
        "task_class": add_result.get("task_class"),
        "action_kind": add_result.get("action_kind"),
        "required_write_scopes": add_result.get("required_write_scopes"),
        "required_capabilities": add_result.get("required_capabilities"),
        "target_capabilities": add_result.get("target_capabilities"),
        "decision_scope": add_result.get("decision_scope"),
        "required_decision_scopes": add_result.get("required_decision_scopes"),
        "claimed_by": add_result.get("claimed_by"),
        "agent_id": effective_agent_id,
        "blocks_agent": add_result.get("blocks_agent"),
        "global_gate": add_result.get("global_gate"),
        "unblocks_todo_id": add_result.get("unblocks_todo_id"),
        "resume_when": add_result.get("resume_when"),
        "target_key": add_result.get("target_key"),
        "cadence": add_result.get("cadence"),
        "next_due_at": add_result.get("next_due_at"),
        "expires_at": add_result.get("expires_at"),
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if added or metadata_updated else None,
    }
    return _attach_todo_write_correctness_dry_run_packet(
        payload,
        goal_id=goal_id,
        write_class="todo_add",
        state_text=original,
    )


def resolve_todo_state(
    *,
    registry_path: Path,
    goal_id: str,
    project: Path | None = None,
    state_file: Path | None = None,
) -> tuple[Path | None, Path, str, list[str]]:
    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    original = resolved_state_file.read_text(encoding="utf-8")
    return resolved_project, resolved_state_file, original, original.splitlines()


def apply_todo_update_to_lines(
    lines: list[str],
    *,
    todo_id: str,
    text: str | None = None,
    status: str | None = None,
    role: str | None = None,
    note: str | None = None,
    evidence: str | None = None,
    reason: str | None = None,
    task_class: str | None = None,
    action_kind: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
    global_gate: bool | None = None,
    unblocks_todo_id: str | None = None,
    resume_when: str | None = None,
    no_followup: bool | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    clear_claim: bool = False,
    claim_only: bool = False,
    updated_at: str,
) -> dict[str, Any]:
    normalized_todo_id = normalize_todo_id(todo_id)
    if not normalized_todo_id:
        raise ValueError("todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
    if role is not None and role not in TODO_SECTION_HEADINGS:
        raise ValueError("todo role must be one of: user, agent")
    block_match = find_todo_block(lines, todo_id=normalized_todo_id, role=role)
    if not block_match:
        raise ValueError(f"todo_id {normalized_todo_id!r} was not found in active user or agent todos")
    resolved_role, section, _start, _end, block = block_match
    normalized_status = normalize_todo_status(status) if status else None
    if status and not normalized_status:
        raise ValueError("todo status must be one of: open, done, blocked, deferred")
    target_status = normalized_status or str(block.get("status") or TODO_STATUS_OPEN)
    status_changed = False
    if normalized_status:
        status_changed = set_todo_marker(lines, block, normalized_status)
    text_changed = False
    if text is not None:
        text_changed = set_todo_text(lines, block, text, status=target_status)

    updates: dict[str, Any] = {
        "todo_id": normalized_todo_id,
        "status": target_status,
    }
    if normalized_status == TODO_STATUS_DONE and not block.get("completed_at"):
        updates["completed_at"] = updated_at
    elif normalized_status and not todo_done_for_status(normalized_status):
        updates["completed_at"] = None
    if note:
        updates["note"] = note
    if evidence:
        updates["evidence"] = evidence
    if reason:
        updates["reason"] = reason
    if task_class:
        updates["task_class"] = task_class
    if action_kind:
        updates["action_kind"] = action_kind
    if required_write_scopes is not None:
        updates["required_write_scopes"] = required_write_scopes
    if required_capabilities is not None:
        updates["required_capabilities"] = required_capabilities
    if target_capabilities is not None:
        updates["target_capabilities"] = target_capabilities
    if decision_scope is not None:
        updates["decision_scope"] = decision_scope
    if required_decision_scopes is not None:
        updates["required_decision_scopes"] = required_decision_scopes
    if clear_claim:
        updates["claimed_by"] = None
    elif claimed_by:
        existing_claim = normalize_todo_claimed_by(block.get("claimed_by"))
        if claim_only and existing_claim and existing_claim != claimed_by:
            raise ValueError(
                f"todo_id {normalized_todo_id!r} is already claimed_by={existing_claim!r}; "
                "clear or transfer the claim explicitly before claiming it"
            )
        updates["claimed_by"] = claimed_by
    if blocks_agent:
        updates["blocks_agent"] = blocks_agent
    if global_gate is not None:
        updates["global_gate"] = global_gate
    if unblocks_todo_id:
        updates["unblocks_todo_id"] = unblocks_todo_id
    if resume_when:
        updates["resume_when"] = resume_when
    if no_followup is not None:
        updates["no_followup"] = no_followup
    for key, value in (monitor_metadata or {}).items():
        if key in TODO_MONITOR_METADATA_FIELDS:
            updates[key] = value
    metadata_line = metadata_line_for_block(block, updates)
    semantic_metadata_changed = todo_metadata_would_change(lines, block, metadata_line)
    if status_changed or text_changed or semantic_metadata_changed:
        updates["updated_at"] = updated_at
        metadata_line = metadata_line_for_block(block, updates)
    metadata_updated = upsert_todo_metadata(lines, block, metadata_line)
    effective_metadata = parse_todo_metadata_line(metadata_line or "") or {}
    return {
        "role": resolved_role,
        "section": section,
        "todo": block.get("text"),
        "todo_id": normalized_todo_id,
        "status": target_status,
        "status_changed": status_changed,
        "text_changed": text_changed,
        "metadata_updated": metadata_updated,
        "changed": status_changed or text_changed or metadata_updated,
        "claimed_by": normalize_todo_claimed_by(effective_metadata.get("claimed_by")),
        "task_class": effective_metadata.get("task_class"),
        "action_kind": effective_metadata.get("action_kind"),
        "required_capabilities": normalize_required_capabilities(
            effective_metadata.get("required_capabilities")
        ),
        "target_capabilities": normalize_target_capabilities(
            effective_metadata.get("target_capabilities")
        ),
        "decision_scope": normalize_todo_decision_scope(effective_metadata.get("decision_scope")),
        "required_decision_scopes": normalize_todo_required_decision_scopes(
            effective_metadata.get("required_decision_scopes")
        ),
        "blocks_agent": normalize_todo_blocks_agent(effective_metadata.get("blocks_agent")),
        "global_gate": normalize_todo_global_gate(effective_metadata.get("global_gate")),
        "unblocks_todo_id": normalize_todo_id(effective_metadata.get("unblocks_todo_id")),
        "resume_when": normalize_todo_resume_when(effective_metadata.get("resume_when")),
        "no_followup": normalize_todo_no_followup(effective_metadata.get("no_followup")),
        "target_key": effective_metadata.get("target_key"),
        "cadence": effective_metadata.get("cadence"),
        "next_due_at": effective_metadata.get("next_due_at"),
        "expires_at": effective_metadata.get("expires_at"),
    }


def update_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    text: str | None = None,
    status: str | None = None,
    role: str | None = None,
    note: str | None = None,
    evidence: str | None = None,
    reason: str | None = None,
    task_class: str | None = None,
    action_kind: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
    global_gate: bool = False,
    agent_id: str | None = None,
    unblocks_todo_id: str | None = None,
    resume_when: str | None = None,
    no_followup: bool | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    clear_claim: bool = False,
    claim_only: bool = False,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if global_gate and (
        (role is not None and role != "user")
        or (task_class is not None and task_class != TODO_TASK_CLASS_USER_GATE)
    ):
        raise ValueError("global_gate is only valid for user_gate todos")
    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    with exclusive_file_lock(resolved_state_file):
        original = resolved_state_file.read_text(encoding="utf-8")
        lines = original.splitlines()
        updated_at = now_local()
        effective_claimed_by = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=claimed_by,
            )
            if claimed_by
            else None
        )
        effective_agent_id = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=agent_id,
                field="agent_id",
            )
            if agent_id
            else None
        )
        inferred_blocks_agent = blocks_agent
        if (
            effective_agent_id
            and not inferred_blocks_agent
            and role == "user"
            and task_class == TODO_TASK_CLASS_USER_GATE
        ):
            inferred_blocks_agent = effective_agent_id
        effective_blocks_agent = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=inferred_blocks_agent,
                field="blocks_agent",
            )
            if inferred_blocks_agent
            else None
        )
        existing_block_match = find_todo_block(lines, todo_id=todo_id, role=role)
        if not existing_block_match:
            normalized_todo_id = normalize_todo_id(todo_id) or todo_id
            raise ValueError(f"todo_id {normalized_todo_id!r} was not found in active user or agent todos")
        existing_role, _section, _start, _end, existing_block = existing_block_match
        target_role = role or existing_role
        target_task_class = task_class or str(existing_block.get("task_class") or "")
        target_status = (
            normalize_todo_status(status)
            if status
            else str(existing_block.get("status") or TODO_STATUS_OPEN)
        )
        existing_blocks_agent = normalize_todo_blocks_agent(existing_block.get("blocks_agent"))
        existing_global_gate = normalize_todo_global_gate(existing_block.get("global_gate"))
        if global_gate and not (target_role == "user" and target_task_class == TODO_TASK_CLASS_USER_GATE):
            raise ValueError("global_gate is only valid for user_gate todos")
        target_blocks_agent = effective_blocks_agent or existing_blocks_agent
        if (
            effective_agent_id
            and not target_blocks_agent
            and target_role == "user"
            and target_task_class == TODO_TASK_CLASS_USER_GATE
        ):
            target_blocks_agent = effective_agent_id
            effective_blocks_agent = effective_agent_id
        target_global_gate = True if global_gate else existing_global_gate
        if not todo_done_for_status(target_status):
            require_user_gate_scope(
                registry_path=registry_path,
                goal_id=goal_id,
                role=target_role,
                task_class=target_task_class,
                blocks_agent=target_blocks_agent,
                global_gate=target_global_gate,
            )
        normalized_unblocks_todo_id = normalize_todo_id(unblocks_todo_id) if unblocks_todo_id else None
        if unblocks_todo_id and not normalized_unblocks_todo_id:
            raise ValueError("unblocks_todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
        normalized_resume_when = normalize_todo_resume_when(resume_when) if resume_when else None
        if resume_when and not normalized_resume_when:
            raise ValueError("resume_when must be public-safe, e.g. todo_done:todo_ab12cd34ef56 or pr_merged:#532")
        normalized_monitor_metadata = require_monitor_metadata_scope(
            monitor_metadata=monitor_metadata,
            role=target_role,
            task_class=target_task_class,
        )
        update_result = apply_todo_update_to_lines(
            lines,
            todo_id=todo_id,
            text=text,
            status=status,
            role=role,
            note=note,
            evidence=evidence,
            reason=reason,
            task_class=task_class,
            action_kind=action_kind,
            required_write_scopes=required_write_scopes,
            required_capabilities=required_capabilities,
            target_capabilities=target_capabilities,
            decision_scope=decision_scope,
            required_decision_scopes=required_decision_scopes,
            claimed_by=effective_claimed_by,
            blocks_agent=effective_blocks_agent,
            global_gate=True if global_gate else None,
            unblocks_todo_id=normalized_unblocks_todo_id,
            resume_when=normalized_resume_when,
            no_followup=no_followup,
            monitor_metadata=normalized_monitor_metadata,
            clear_claim=clear_claim,
            claim_only=claim_only,
            updated_at=updated_at,
        )
        changed = bool(update_result["changed"])
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if changed:
            new_text = replace_updated_at(new_text, updated_at)
        if changed and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")
    write_class = "todo_claim" if claim_only else "todo_update"
    payload = {
        "ok": True,
        "dry_run": dry_run,
        "changed": changed,
        "goal_id": goal_id,
        "agent_id": effective_agent_id,
        **update_result,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
    }
    return _attach_todo_write_correctness_dry_run_packet(
        payload,
        goal_id=goal_id,
        write_class=write_class,
        state_text=original,
    )


def complete_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    role: str | None = None,
    evidence: str | None = None,
    note: str | None = None,
    no_followup: bool = False,
    claimed_by: str | None = None,
    clear_claim: bool = False,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
    next_task_class: str | None = None,
    next_action_kind: str | None = None,
    side_agent_self_merged: bool = False,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    with exclusive_file_lock(resolved_state_file):
        original = resolved_state_file.read_text(encoding="utf-8")
        lines = original.splitlines()
        updated_at = now_local()
        effective_claimed_by = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=claimed_by,
            )
            if claimed_by
            else None
        )
        primary_agent = primary_agent_id_from_registry(registry_path, goal_id)
        registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
        configured_handoff_agent = side_agent_handoff_agent_id_from_registry(
            registry_path,
            goal_id,
            agent_id=effective_claimed_by,
        )
        handoff_agent = configured_handoff_agent or primary_agent
        if configured_handoff_agent:
            handoff_agent = require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=configured_handoff_agent,
                field="side_agent_handoff_agent",
            )
        effective_next_claimed_by = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=next_claimed_by,
                field="next_claimed_by",
            )
            if next_claimed_by
            else None
        )
        if effective_claimed_by and not primary_agent:
            raise ValueError(
                "todo complete with --claimed-by requires coordination.primary_agent "
                "so LoopX can distinguish the primary agent from side agents"
            )
        side_agent_completion = bool(
            effective_claimed_by and primary_agent and effective_claimed_by != primary_agent
        )
        if side_agent_completion:
            if side_agent_self_merged and not evidence:
                raise ValueError(
                    "--side-agent-self-merged requires --evidence with a public-safe "
                    "self-merge, commit, and validation summary"
                )
            if not side_agent_self_merged and not next_agent_todo:
                raise ValueError(
                    f"side-agent completion by {effective_claimed_by!r} requires "
                    "--next-agent-todo for independent handoff, verification, and merge, "
                    "or --side-agent-self-merged with --evidence for a small validated self-merge"
                )
            if not side_agent_self_merged and handoff_agent == effective_claimed_by:
                raise ValueError(
                    "side-agent handoff todo cannot be claimed by the completing side agent; "
                    "use --side-agent-self-merged with --evidence for same-agent delivery, "
                    "or configure side_agent_handoff_agent to another registered agent"
                )
            if (
                not side_agent_self_merged
                and effective_next_claimed_by
                and effective_next_claimed_by != handoff_agent
            ):
                raise ValueError(
                    f"side-agent completion handoff todo must be claimed_by handoff_agent={handoff_agent!r}"
                )
            if next_agent_todo and not side_agent_self_merged:
                effective_next_claimed_by = handoff_agent
        if effective_next_claimed_by and not next_agent_todo:
            raise ValueError("--next-claimed-by requires --next-agent-todo")
        update_result = apply_todo_update_to_lines(
            lines,
            todo_id=todo_id,
            status=TODO_STATUS_DONE,
            role=role,
            note=note,
            evidence=evidence,
            claimed_by=effective_claimed_by,
            clear_claim=clear_claim,
            no_followup=True if no_followup else None,
            updated_at=updated_at,
        )
        if next_agent_todo and not effective_next_claimed_by:
            effective_next_claimed_by = normalize_todo_claimed_by(update_result.get("claimed_by"))
        next_blocks_agent = None
        next_unblocks_todo_id = None
        if side_agent_completion and next_agent_todo and not side_agent_self_merged:
            next_blocks_agent = effective_claimed_by
            next_unblocks_todo_id = normalize_todo_id(str(update_result.get("todo_id") or todo_id))
        next_user_blocks_agent = None
        if next_user_todo and len(registered_agents) > 1:
            next_user_blocks_agent = effective_claimed_by or primary_agent
            if not next_user_blocks_agent:
                raise ValueError(
                    "multi-agent --next-user-todo requires a completing --claimed-by "
                    "agent or coordination.primary_agent so the user_gate can be scoped"
                )
        next_results: list[dict[str, Any]] = []
        if next_agent_todo:
            next_results.append(
                add_todo_to_lines(
                    lines,
                    role="agent",
                    text=inherit_todo_priority(
                        next_agent_todo,
                        str(update_result.get("todo") or ""),
                    ),
                    task_class=next_task_class or "advancement_task",
                    action_kind=next_action_kind,
                    claimed_by=effective_next_claimed_by,
                    blocks_agent=next_blocks_agent,
                    unblocks_todo_id=next_unblocks_todo_id,
                )
            )
        if next_user_todo:
            next_results.append(
                add_todo_to_lines(
                    lines,
                    role="user",
                    text=inherit_todo_priority(
                        next_user_todo,
                        str(update_result.get("todo") or ""),
                    ),
                    task_class="user_gate",
                    blocks_agent=next_user_blocks_agent,
                )
            )
        next_changed = any(item.get("added") or item.get("metadata_updated") for item in next_results)
        changed = bool(update_result["changed"] or next_changed)
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if changed:
            new_text = replace_updated_at(new_text, updated_at)
        if changed and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")
    return {
        "ok": True,
        "dry_run": dry_run,
        "completed": True,
        "goal_id": goal_id,
        **update_result,
        "changed": changed,
        "next_todos": next_results,
        "side_agent_self_merged": bool(side_agent_completion and side_agent_self_merged),
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
    }


def supersede_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    role: str | None = None,
    reason: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
    next_task_class: str | None = None,
    next_action_kind: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )
    with exclusive_file_lock(resolved_state_file):
        original = resolved_state_file.read_text(encoding="utf-8")
        lines = original.splitlines()
        updated_at = now_local()
        effective_next_claimed_by = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=next_claimed_by,
                field="next_claimed_by",
            )
            if next_claimed_by
            else None
        )
        if effective_next_claimed_by and not next_agent_todo:
            raise ValueError("--next-claimed-by requires --next-agent-todo")
        update_result = apply_todo_update_to_lines(
            lines,
            todo_id=todo_id,
            status=TODO_STATUS_DONE,
            role=role,
            reason=reason,
            note="superseded",
            updated_at=updated_at,
        )
        if next_agent_todo and not effective_next_claimed_by:
            effective_next_claimed_by = normalize_todo_claimed_by(update_result.get("claimed_by"))
        next_blocks_agent = normalize_todo_blocks_agent(update_result.get("blocks_agent"))
        next_unblocks_todo_id = normalize_todo_id(update_result.get("unblocks_todo_id"))
        registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
        primary_agent = primary_agent_id_from_registry(registry_path, goal_id)
        next_user_blocks_agent = next_blocks_agent
        if next_user_todo and len(registered_agents) > 1 and not next_user_blocks_agent:
            next_user_blocks_agent = (
                normalize_todo_claimed_by(update_result.get("claimed_by"))
                or effective_next_claimed_by
                or primary_agent
            )
            if not next_user_blocks_agent:
                raise ValueError(
                    "multi-agent supersede --next-user-todo requires inherited "
                    "blocks_agent, next_claimed_by, or coordination.primary_agent "
                    "so the user_gate can be scoped"
                )
        next_results: list[dict[str, Any]] = []
        if next_agent_todo:
            next_results.append(
                add_todo_to_lines(
                    lines,
                    role="agent",
                    text=inherit_todo_priority(
                        next_agent_todo,
                        str(update_result.get("todo") or ""),
                    ),
                    task_class=next_task_class or "advancement_task",
                    action_kind=next_action_kind,
                    claimed_by=effective_next_claimed_by,
                    blocks_agent=next_blocks_agent,
                    unblocks_todo_id=next_unblocks_todo_id,
                )
            )
        if next_user_todo:
            next_results.append(
                add_todo_to_lines(
                    lines,
                    role="user",
                    text=inherit_todo_priority(
                        next_user_todo,
                        str(update_result.get("todo") or ""),
                    ),
                    task_class="user_gate",
                    blocks_agent=next_user_blocks_agent,
                )
            )
        superseded_by = next((item.get("todo_id") for item in next_results if item.get("todo_id")), None)
        if superseded_by:
            block_match = find_todo_block(lines, todo_id=str(update_result["todo_id"]), role=role)
            if block_match:
                _resolved_role, _section, _start, _end, block = block_match
                update_result["metadata_updated"] = upsert_todo_metadata(
                    lines,
                    block,
                    metadata_line_for_block(block, {"superseded_by": superseded_by}),
                ) or update_result["metadata_updated"]
                update_result["superseded_by"] = superseded_by
                update_result["changed"] = True
        next_changed = any(item.get("added") or item.get("metadata_updated") for item in next_results)
        changed = bool(update_result["changed"] or next_changed)
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if changed:
            new_text = replace_updated_at(new_text, updated_at)
        if changed and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")
    return {
        "ok": True,
        "dry_run": dry_run,
        "superseded": True,
        "goal_id": goal_id,
        **update_result,
        "changed": changed,
        "next_todos": next_results,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
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
    resolved_project, resolved_state_file = resolve_todo_state_path(
        registry_path=registry_path,
        goal_id=goal_id,
        project=project,
        state_file=state_file,
    )

    with exclusive_file_lock(resolved_state_file):
        original = resolved_state_file.read_text(encoding="utf-8")
        lines = original.splitlines()
        bounds = section_bounds(lines, role)
        section = bounds[2] if bounds else TODO_SECTION_HEADINGS[role]
        moved_blocks: list[list[str]] = []
        active_done_count = 0
        moved_count = 0
        kept_done_count = 0

        if bounds:
            blocks = todo_blocks(lines, bounds[0], bounds[1], role=role, source_section=section)
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
    if payload.get("command") == "list":
        lines = [
            "# LoopX Todo List",
            "",
            f"- ok: `{payload.get('ok')}`",
            f"- read_only: `{payload.get('read_only')}`",
            f"- goal_id: `{payload.get('goal_id')}`",
            f"- role: `{payload.get('role')}`",
            f"- status_filter: `{payload.get('status_filter')}`",
            f"- source: `{payload.get('source')}`",
            f"- todo_count: `{payload.get('todo_count')}`",
            f"- state_file: `{payload.get('state_file')}`",
        ]
        projection = payload.get("state_event_projection")
        if isinstance(projection, dict):
            lines.extend(
                [
                    f"- event_log: `{projection.get('event_log')}`",
                    f"- source_event_count: `{projection.get('source_event_count')}`",
                    f"- last_event_id: `{projection.get('last_event_id')}`",
                ]
            )
        for key, heading in (
            ("user_todos", "User Todo"),
            ("agent_todos", "Agent Todo"),
        ):
            summary = payload.get(key)
            if not isinstance(summary, dict):
                continue
            lines.extend(["", f"## {heading}", ""])
            items = summary.get("items") or []
            if not items:
                lines.append("- none")
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                marker = todo_marker_for_status(item.get("status") or TODO_STATUS_OPEN)
                text = item.get("text") or item.get("title") or ""
                metadata = []
                for metadata_key in (
                    "todo_id",
                    "status",
                    "task_class",
                    "action_kind",
                    "claimed_by",
                    "target_key",
                    "cadence",
                    "next_due_at",
                    "expires_at",
                ):
                    if item.get(metadata_key):
                        metadata.append(f"{metadata_key}={item.get(metadata_key)}")
                suffix = f" <!-- {' '.join(metadata)} -->" if metadata else ""
                lines.append(f"- [{marker}] {text}{suffix}")
        if payload.get("error"):
            lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)

    lines = [
        "# LoopX Todo",
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
                f"- changed: `{payload.get('changed')}`",
                f"- added: `{payload.get('added')}`",
                f"- already_exists: `{payload.get('already_exists')}`",
                f"- todo_id: `{payload.get('todo_id')}`",
                f"- status: `{payload.get('status')}`",
                f"- required_capabilities: `{payload.get('required_capabilities')}`",
                f"- target_capabilities: `{payload.get('target_capabilities')}`",
                f"- claimed_by: `{payload.get('claimed_by')}`",
                f"- blocks_agent: `{payload.get('blocks_agent')}`",
                f"- global_gate: `{payload.get('global_gate')}`",
                f"- resume_when: `{payload.get('resume_when')}`",
                f"- target_key: `{payload.get('target_key')}`",
                f"- cadence: `{payload.get('cadence')}`",
                f"- next_due_at: `{payload.get('next_due_at')}`",
                f"- expires_at: `{payload.get('expires_at')}`",
            ]
        )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    elif "todo" in payload:
        marker = todo_marker_for_status(payload.get("status") or TODO_STATUS_OPEN)
        lines.extend(["", "## Todo", "", f"- [{marker}] {payload.get('todo')}"])
    correctness = payload.get("local_state_write_correctness")
    if isinstance(correctness, dict):
        intent = correctness.get("write_intent") if isinstance(correctness.get("write_intent"), dict) else {}
        apply_result = (
            correctness.get("apply_result")
            if isinstance(correctness.get("apply_result"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Local State Write Correctness",
                "",
                f"- schema_version: `{correctness.get('schema_version')}`",
                f"- write_id: `{intent.get('write_id')}`",
                f"- write_class: `{intent.get('write_class')}`",
                f"- idempotency_key: `{intent.get('idempotency_key')}`",
                f"- status: `{apply_result.get('status')}`",
            ]
        )
    return "\n".join(lines)
