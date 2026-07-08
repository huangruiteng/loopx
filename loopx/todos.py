from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .agent_registry import (
    primary_agent_id_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
)
from .file_lock import exclusive_file_lock
from .history import load_registry
from .control_plane.runtime.local_state_write_correctness import build_todo_write_correctness_dry_run_packet
from .state_refresh import now_local, resolve_goal_state
from .status import (
    MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
    active_state_event_projection_fields,
    compact_todo_group,
    normalize_todo_text,
    parse_active_state_todos,
)
from .control_plane.todos.contract import (
    TODO_MONITOR_METADATA_FIELDS,
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_USER_GATE,
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
    normalize_todo_id_list,
    normalize_todo_no_followup,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_marker_for_status,
)
from .control_plane.todos.active_state_editing import (
    TODO_SECTION_HEADINGS,
    insert_into_existing_section,
    insert_new_section,
    replace_updated_at,
    section_bounds,
    todo_blocks,
)
from .control_plane.todos.completed_archive import archive_completed_todo_lines
from .control_plane.todos.completion_policy import (
    linked_successor_from_todo,
    resolve_completion_policy,
)
from .control_plane.todos.event_writeback import (
    complete_event_projected_goal_todo,
    event_projection_todo_context,
)
from .control_plane.todos.markdown import render_todo_markdown
from .control_plane.todos.monitor_metadata import require_monitor_metadata_scope
from .control_plane.todos.text import (
    inherit_todo_priority,
    normalize_new_todo,
)
from .control_plane.todos.write_policy import require_user_gate_scope, require_user_todo_task_class


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
    "successor_todo_ids",
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
    todo_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    items = list((summary or {}).get("items") or [])
    normalized_status = normalize_todo_status(status)
    if normalized_status:
        items = [item for item in items if todo_item_status(item) == normalized_status]
    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    if normalized_todo_id:
        items = [
            item
            for item in items
            if normalize_todo_id(item.get("todo_id")) == normalized_todo_id
        ]
    normalized_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
    if normalized_agent_id:
        if role == "agent":
            items = [
                item
                for item in items
                if not normalize_todo_claimed_by(item.get("claimed_by"))
                or normalize_todo_claimed_by(item.get("claimed_by")) == normalized_agent_id
            ]
        elif role == "user":
            items = [
                item
                for item in items
                if bool(item.get("global_gate"))
                or not normalize_todo_blocks_agent(item.get("blocks_agent"))
                or normalize_todo_blocks_agent(item.get("blocks_agent")) == normalized_agent_id
            ]
    source_section = str((summary or {}).get("source_section") or TODO_SECTION_HEADINGS[role])
    return (
        compact_todo_group(
            items,
            source_section=source_section,
            role=role,
            item_limit=None,
        )
        or empty_todo_summary(role=role)
    )


def todo_item_relations(item: dict[str, Any]) -> dict[str, Any]:
    relations: dict[str, Any] = {}
    for key in (
        "claimed_by",
        "blocks_agent",
        "global_gate",
        "unblocks_todo_id",
        "successor_todo_ids",
        "superseded_by",
        "resume_when",
        "resume_condition",
        "resume_ready",
        "decision_scope",
        "required_decision_scopes",
        "required_write_scopes",
        "required_capabilities",
        "target_capabilities",
        "task_class",
        "action_kind",
        "target_key",
        "cadence",
        "next_due_at",
        "expires_at",
    ):
        value = item.get(key)
        if value is not None and value != []:
            relations[key] = value
    return relations


def _summary_items(fields: dict[str, Any], role: str) -> list[dict[str, Any]]:
    summary = fields.get(f"{role}_todos") if isinstance(fields, dict) else None
    if not isinstance(summary, dict):
        return []
    return [item for item in summary.get("items") or [] if isinstance(item, dict)]


def _merge_todo_projection_fields(
    *,
    markdown_fields: dict[str, Any],
    event_fields: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged: dict[str, Any] = {}
    overlay: dict[str, Any] = {
        "schema_version": "todo_list_projection_overlay_v0",
        "base": "markdown_active_state",
        "overlay": "event_projection",
        "markdown_only_todo_ids": [],
        "event_only_todo_ids": [],
        "overlaid_todo_ids": [],
    }
    for role in ("user", "agent"):
        markdown_items = _summary_items(markdown_fields, role)
        event_items = _summary_items(event_fields, role)
        if not markdown_items and not event_items:
            continue
        by_id: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in markdown_items:
            todo_id = normalize_todo_id(item.get("todo_id")) or build_todo_id(
                role=role,
                source_section=item.get("source_section"),
                index=item.get("index"),
                text=item.get("text"),
            )
            if todo_id not in by_id:
                order.append(todo_id)
            by_id[todo_id] = dict(item)
        markdown_ids = set(order)
        event_ids: set[str] = set()
        for item in event_items:
            todo_id = normalize_todo_id(item.get("todo_id")) or build_todo_id(
                role=role,
                source_section=item.get("source_section"),
                index=item.get("index"),
                text=item.get("text"),
            )
            event_ids.add(todo_id)
            if todo_id not in by_id:
                order.append(todo_id)
                overlay["event_only_todo_ids"].append(todo_id)
            else:
                overlay["overlaid_todo_ids"].append(todo_id)
            by_id[todo_id] = dict(item)
        overlay["markdown_only_todo_ids"].extend(sorted(markdown_ids - event_ids))
        source_section = str(
            (markdown_fields.get(f"{role}_todos") or {}).get("source_section")
            or (event_fields.get(f"{role}_todos") or {}).get("source_section")
            or TODO_SECTION_HEADINGS[role]
        )
        summary = compact_todo_group(
            [by_id[todo_id] for todo_id in order],
            source_section=source_section,
            role=role,
            item_limit=None,
        )
        if summary:
            merged[f"{role}_todos"] = summary
    return merged, overlay


def list_goal_todos(
    *,
    registry_path: Path,
    goal_id: str,
    role: str | None = None,
    status: str | None = None,
    todo_id: str | None = None,
    agent_id: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
) -> dict[str, Any]:
    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    if todo_id and not normalized_todo_id:
        raise ValueError("todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
    normalized_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
    if agent_id and not normalized_agent_id:
        raise ValueError("agent_id must be a public-safe agent token such as codex-main-control")
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
        item_limit=None,
    )
    projection_has_todos = bool(
        projection_fields.get("user_todos") or projection_fields.get("agent_todos")
    )
    markdown_fields = parse_active_state_todos(
        resolved_state_file.read_text(encoding="utf-8"),
        goal=goal,
        state_path=resolved_state_file,
        item_limit=None,
    )
    markdown_has_todos = bool(
        markdown_fields.get("user_todos") or markdown_fields.get("agent_todos")
    )
    projection_overlay: dict[str, Any] | None = None
    if projection_has_todos and markdown_has_todos:
        fields, projection_overlay = _merge_todo_projection_fields(
            markdown_fields=markdown_fields,
            event_fields=projection_fields,
        )
        source = "event_projection_with_markdown_overlay"
    elif projection_has_todos:
        fields = projection_fields
        source = "event_projection"
    else:
        fields = markdown_fields
        source = "markdown_active_state"

    roles = [role] if role else ["user", "agent"]
    summaries: dict[str, dict[str, Any]] = {}
    todos: list[dict[str, Any]] = []
    unfiltered_count = 0
    for item_role in roles:
        key = f"{item_role}_todos"
        raw_summary = fields.get(key) if isinstance(fields, dict) else None
        unfiltered_count += len((raw_summary or {}).get("items") or [])
        summary = filtered_todo_summary(
            raw_summary,
            role=item_role,
            status=status,
            todo_id=normalized_todo_id,
            agent_id=normalized_agent_id,
        )
        summaries[key] = summary
        todos.extend(summary.get("items") or [])

    matched_todo = todos[0] if len(todos) == 1 else None
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
    if normalized_agent_id:
        payload["agent_id_filter"] = normalized_agent_id
        payload["unfiltered_todo_count"] = unfiltered_count
        payload["filter_semantics"] = (
            "agent todos include unclaimed items plus claimed_by=<agent>; "
            "user todos include global, unscoped legacy, and blocks_agent=<agent> gates"
        )
    if normalized_todo_id:
        payload["todo_id_filter"] = normalized_todo_id
        payload["matched"] = bool(todos)
        payload["todo"] = matched_todo
        payload["relations"] = todo_item_relations(matched_todo) if matched_todo else {}
        if len(todos) > 1:
            payload["ambiguous"] = True
        if not todos:
            payload["not_found"] = True
    payload.update(summaries)
    if source == "event_projection" and projection_fields.get("state_event_projection"):
        payload["state_event_projection"] = projection_fields["state_event_projection"]
    if source == "event_projection_with_markdown_overlay":
        if projection_fields.get("state_event_projection"):
            payload["state_event_projection"] = projection_fields["state_event_projection"]
        payload["projection_overlay"] = projection_overlay
    if projection_fields.get("state_event_projection_warning"):
        payload["state_event_projection_warning"] = projection_fields["state_event_projection_warning"]
    return payload


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
        if todo_done_for_status(todo_item_status(block)):
            continue
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
        elif key == "successor_todo_ids":
            todo_ids = normalize_todo_id_list(value)
            if todo_ids:
                metadata[key] = todo_ids
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
    require_user_todo_task_class(
        role=role,
        task_class=task_class,
        blocks_agent=blocks_agent,
        global_gate=global_gate,
    )
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
    require_user_todo_task_class(
        role=role,
        task_class=task_class,
        blocks_agent=blocks_agent,
        global_gate=True if global_gate else None,
    )
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
    successor_todo_ids: list[str] | None = None,
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
    if successor_todo_ids is not None:
        updates["successor_todo_ids"] = successor_todo_ids
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
        "successor_todo_ids": normalize_todo_id_list(effective_metadata.get("successor_todo_ids")),
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
    successor_todo_ids: list[str] | None = None,
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
            require_user_todo_task_class(
                role=target_role,
                task_class=target_task_class,
                blocks_agent=target_blocks_agent,
                global_gate=target_global_gate,
            )
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
        normalized_successor_todo_ids = normalize_todo_id_list(successor_todo_ids)
        if successor_todo_ids and not normalized_successor_todo_ids:
            raise ValueError("successor_todo_ids must contain public todo_<letters-digits-underscore-hyphen> tokens")
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
            successor_todo_ids=normalized_successor_todo_ids if successor_todo_ids is not None else None,
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
    successor_todo_ids: list[str] | None = None,
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
        normalized_successor_todo_ids = normalize_todo_id_list(successor_todo_ids)
        if successor_todo_ids and not normalized_successor_todo_ids:
            raise ValueError("successor_todo_ids must contain public todo_<letters-digits-underscore-hyphen> tokens")
        linked_successors = []
        for successor_todo_id in normalized_successor_todo_ids:
            successor_match = find_todo_block(lines, todo_id=successor_todo_id)
            if successor_match:
                successor_role, _section, _start, _end, successor_block = successor_match
                successor_item = dict(successor_block)
                successor_item["role"] = successor_role
                linked_successors.append(linked_successor_from_todo(successor_item))
        completion_policy = resolve_completion_policy(
            registry_path=registry_path,
            goal_id=goal_id,
            claimed_by=claimed_by,
            next_claimed_by=next_claimed_by,
            next_agent_todo=next_agent_todo,
            next_action_kind=next_action_kind,
            side_agent_self_merged=side_agent_self_merged,
            evidence=evidence,
            linked_successors=linked_successors,
        )
        effective_claimed_by = completion_policy.effective_claimed_by
        primary_agent = completion_policy.primary_agent
        registered_agents = completion_policy.registered_agents
        effective_next_claimed_by = completion_policy.effective_next_claimed_by
        side_agent_completion = completion_policy.side_agent_completion
        effective_side_agent_self_merged = completion_policy.side_agent_self_merged
        if not find_todo_block(lines, todo_id=todo_id, role=role):
            event_context = event_projection_todo_context(
                registry_path=registry_path,
                goal_id=goal_id,
                state_path=resolved_state_file,
                todo_id=todo_id,
                role=role,
            )
            if event_context:
                event_context["state_file"] = resolved_state_file
                event_context["project"] = resolved_project
                return complete_event_projected_goal_todo(
                    goal_id=goal_id,
                    context=event_context,
                    evidence=evidence,
                    note=note,
                    no_followup=no_followup,
                    successor_todo_ids=normalized_successor_todo_ids,
                    claimed_by=effective_claimed_by,
                    clear_claim=clear_claim,
                    next_agent_todo=next_agent_todo,
                    next_user_todo=next_user_todo,
                    next_claimed_by=effective_next_claimed_by,
                    next_task_class=next_task_class,
                    next_action_kind=next_action_kind,
                    side_agent_completion=side_agent_completion,
                    side_agent_self_merged=effective_side_agent_self_merged,
                    registered_agents=registered_agents,
                    primary_agent=primary_agent,
                    updated_at=updated_at,
                    dry_run=dry_run,
                )
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
            successor_todo_ids=normalized_successor_todo_ids if successor_todo_ids is not None else None,
            updated_at=updated_at,
        )
        if next_agent_todo and not effective_next_claimed_by:
            effective_next_claimed_by = normalize_todo_claimed_by(update_result.get("claimed_by"))
        next_blocks_agent = None
        next_unblocks_todo_id = (
            normalize_todo_id(str(update_result.get("todo_id") or todo_id))
            if next_agent_todo
            else None
        )
        if side_agent_completion and next_agent_todo and not effective_side_agent_self_merged:
            next_blocks_agent = effective_claimed_by
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
        "side_agent_self_merged": effective_side_agent_self_merged,
        "linked_handoff_successor_id": completion_policy.linked_handoff_successor_id,
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
        archive_result = archive_completed_todo_lines(
            lines,
            role=role,
            max_active_done=max_active_done,
        )
        lines = archive_result.pop("lines")

        updated_at = now_local()
        changed = bool(archive_result["changed"])
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if changed:
            new_text = replace_updated_at(new_text, updated_at)
        if changed and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")

    return {
        "ok": True,
        "dry_run": dry_run,
        "goal_id": goal_id,
        **archive_result,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
    }
