from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_registry import registered_agent_ids_from_registry, require_registered_agent_id
from .file_lock import exclusive_file_lock
from .history import load_registry
from .paths import resolve_runtime_root
from .rollout_event_log import load_rollout_events, rollout_event_log_path
from .control_plane.runtime.local_state_write_correctness import build_todo_write_correctness_dry_run_packet
from .state_refresh import now_local, resolve_goal_state
from .status import (
    MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
    active_state_event_projection_fields,
)
from .control_plane.todos.active_state_todo_parser import parse_active_state_todos
from .control_plane.todos.contract import (
    TodoContinuationPolicy,
    TODO_STATUS_DEFERRED,
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_USER_ACTION,
    TODO_TASK_CLASS_USER_GATE,
    build_todo_id,
    format_todo_metadata_line,
    metadata_line_for_todo_block,
    merge_todo_id_lists,
    normalize_required_capabilities,
    normalize_required_write_scopes,
    normalize_explore_result_node_refs,
    normalize_target_capabilities,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_continuation_policy,
    normalize_todo_decision_scope,
    normalize_todo_excluded_agents,
    normalize_todo_global_gate,
    normalize_todo_goal_bound,
    normalize_todo_id,
    normalize_todo_id_list,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_supported_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_repository,
    parse_todo_metadata_line,
    require_todo_excluded_agents,
    resolve_todo_continuation_policy,
    require_supported_todo_resume_when,
    todo_done_for_status,
    todo_marker_for_status,
)
from .control_plane.todos.active_state_editing import (
    TODO_SECTION_HEADINGS,
    find_todo_block,
    insert_into_existing_section,
    insert_new_section,
    replace_updated_at,
    section_bounds,
    set_todo_marker,
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
from .control_plane.todos.line_update import (
    apply_todo_update_to_lines,
    upsert_todo_metadata,
)
from .control_plane.todos.monitor_metadata import require_monitor_metadata_scope
from .control_plane.todos.mutation_authority import authorize_todo_lifecycle_mutation, todo_update_authority_action
from .control_plane.todos.todo_summary import compact_todo_group, normalize_todo_text
from .control_plane.todos.succession_warning import build_open_parent_successor_advisory
from .control_plane.todos.todo_index import MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL
from .control_plane.todos.text import (
    inherit_todo_priority,
    normalize_new_todo,
)
from .control_plane.todos.unblock_resume import (
    apply_completed_user_todo_lifecycle,
    require_completion_decision_outcome,
)
from .control_plane.todos.write_policy import (
    require_user_gate_scope,
    require_user_todo_binding,
    require_user_todo_task_class,
    resolve_user_gate_global_gate_update,
)


ARCHIVE_COMPLETED_DEFAULT_MAX_ACTIVE_DONE = max(0, MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE - 2)


def resolve_next_user_task_class(
    next_user_todo: str | None,
    next_user_task_class: str | None,
) -> str:
    if next_user_task_class and not next_user_todo:
        raise ValueError("--next-user-task-class requires --next-user-todo")
    effective = next_user_task_class or TODO_TASK_CLASS_USER_GATE
    if effective not in {TODO_TASK_CLASS_USER_GATE, TODO_TASK_CLASS_USER_ACTION}:
        raise ValueError(
            "next_user_task_class must be one of: user_action, user_gate"
        )
    return effective


def require_registered_todo_excluded_agents(
    *,
    registry_path: Path,
    goal_id: str,
    excluded_agents: Any,
    field: str = "excluded_agents",
) -> list[str]:
    return sorted(
        require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=agent_id,
            field=field,
        )
        for agent_id in require_todo_excluded_agents(excluded_agents, field=field)
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
    resume_source_items: list[dict[str, Any]] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
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
                if normalized_agent_id
                not in normalize_todo_excluded_agents(item.get("excluded_agents"))
                and (
                    not normalize_todo_claimed_by(item.get("claimed_by"))
                    or normalize_todo_claimed_by(item.get("claimed_by"))
                    == normalized_agent_id
                )
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
            resume_source_items=resume_source_items,
            rollout_events=rollout_events,
            item_limit=None,
        )
        or empty_todo_summary(role=role)
    )


def todo_item_relations(item: dict[str, Any]) -> dict[str, Any]:
    relations: dict[str, Any] = {}
    for key in (
        "claimed_by",
        "bound_agent",
        "goal_bound",
        "blocks_agent",
        "excluded_agents",
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
        "continuation_policy",
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
    merged_items: dict[str, list[dict[str, Any]]] = {"user": [], "agent": []}
    source_sections: dict[str, str] = {}
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
        merged_items[role] = [by_id[todo_id] for todo_id in order]
        source_sections[role] = source_section

    resume_source_items = [*merged_items["user"], *merged_items["agent"]]
    for role in ("user", "agent"):
        if not merged_items[role]:
            continue
        summary = compact_todo_group(
            merged_items[role],
            source_section=source_sections[role],
            role=role,
            resume_source_items=resume_source_items,
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
    runtime_root_arg: str | None = None,
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

    runtime_root = resolve_runtime_root(registry, runtime_root_arg)
    rollout_events = load_rollout_events(
        rollout_event_log_path(runtime_root, goal_id),
        limit=MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL,
    )

    projection_fields = active_state_event_projection_fields(
        goal,
        state_path=resolved_state_file,
        item_limit=None,
        rollout_events=rollout_events,
    )
    projection_has_todos = bool(
        projection_fields.get("user_todos") or projection_fields.get("agent_todos")
    )
    markdown_fields = parse_active_state_todos(
        resolved_state_file.read_text(encoding="utf-8"),
        goal=goal,
        state_path=resolved_state_file,
        item_limit=None,
        rollout_events=rollout_events,
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
    resume_source_items = [
        *_summary_items(fields, "user"),
        *_summary_items(fields, "agent"),
    ]
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
            resume_source_items=resume_source_items,
            rollout_events=rollout_events,
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


def link_generated_successor_todo_ids(
    lines: list[str],
    *,
    update_result: dict[str, Any],
    role: str | None,
    successor_todo_ids: list[str],
) -> bool:
    merged_successor_ids = merge_todo_id_lists(
        update_result.get("successor_todo_ids"),
        successor_todo_ids,
    )
    if merged_successor_ids == normalize_todo_id_list(update_result.get("successor_todo_ids")):
        return False
    block_match = find_todo_block(
        lines,
        todo_id=str(update_result.get("todo_id") or ""),
        role=role,
    )
    if not block_match:
        return False
    _resolved_role, _section, _start, _end, block = block_match
    metadata_updated = upsert_todo_metadata(
        lines,
        block,
        metadata_line_for_todo_block(block, {"successor_todo_ids": merged_successor_ids}),
    )
    update_result["successor_todo_ids"] = merged_successor_ids
    update_result["metadata_updated"] = bool(update_result.get("metadata_updated") or metadata_updated)
    update_result["changed"] = bool(update_result.get("changed") or metadata_updated)
    return metadata_updated


def add_todo_to_lines(
    lines: list[str],
    *,
    role: str,
    text: str,
    status: str | None = None,
    task_class: str | None = None,
    action_kind: str | None = None,
    task_repository: str | None = None,
    continuation_policy: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    explore_result_node_refs: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    bound_agent: str | None = None,
    goal_bound: bool | None = None,
    blocks_agent: str | None = None,
    excluded_agents: list[str] | None = None,
    global_gate: bool | None = None,
    unblocks_todo_id: str | None = None,
    resume_when: str | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    evidence: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    if role == "agent" and blocks_agent:
        raise ValueError(
            "blocks_agent is only valid for user gates; use excluded_agents for "
            "agent executor constraints"
        )
    if role != "agent" and excluded_agents:
        raise ValueError("excluded_agents is only valid for agent todos")
    require_user_todo_task_class(
        role=role,
        task_class=task_class,
        blocks_agent=blocks_agent,
        global_gate=global_gate,
    )
    todo_text = normalize_new_todo(text)
    normalized_status = normalize_todo_status(status) if status else TODO_STATUS_OPEN
    if status and not normalized_status:
        raise ValueError("todo status must be one of: open, done, blocked, deferred")
    normalized_resume_when = require_supported_todo_resume_when(resume_when)
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
    status_changed = False

    if block is None:
        todo_id = build_todo_id(
            role=role,
            source_section=section,
            index=len(existing_blocks) + 1,
            text=todo_text,
        )
        metadata_line = format_todo_metadata_line(
            todo_id=todo_id,
            status=normalized_status,
            task_class=task_class,
            action_kind=action_kind,
            task_repository=task_repository,
            continuation_policy=continuation_policy,
            required_write_scopes=required_write_scopes,
            required_capabilities=required_capabilities,
            target_capabilities=target_capabilities,
            explore_result_node_refs=explore_result_node_refs,
            decision_scope=decision_scope,
            required_decision_scopes=required_decision_scopes,
            claimed_by=claimed_by,
            bound_agent=bound_agent,
            goal_bound=goal_bound,
            blocks_agent=blocks_agent,
            excluded_agents=excluded_agents,
            global_gate=global_gate,
            unblocks_todo_id=unblocks_todo_id,
            resume_when=normalized_resume_when,
            **normalized_monitor_metadata,
            evidence=evidence,
            updated_at=updated_at,
        )
        marker = todo_marker_for_status(normalized_status)
        todo_line = "\n".join([f"- [{marker}] {todo_text}", metadata_line] if metadata_line else [f"- [{marker}] {todo_text}"])
        if bounds:
            insert_into_existing_section(lines, bounds[0], bounds[1], todo_line)
        else:
            insert_new_section(lines, role, todo_line)
        effective_metadata = parse_todo_metadata_line(metadata_line or "") or {}
    else:
        updates: dict[str, Any] = {
            "todo_id": block.get("todo_id"),
            "status": normalized_status if status else block.get("status") or TODO_STATUS_OPEN,
        }
        if status:
            status_changed = set_todo_marker(lines, block, normalized_status)
        if task_class:
            updates["task_class"] = task_class
        if action_kind:
            updates["action_kind"] = action_kind
        if task_repository:
            updates["task_repository"] = task_repository
        if continuation_policy:
            updates["continuation_policy"] = continuation_policy
        if required_write_scopes is not None:
            updates["required_write_scopes"] = required_write_scopes
        if required_capabilities is not None:
            updates["required_capabilities"] = required_capabilities
        if target_capabilities is not None:
            updates["target_capabilities"] = target_capabilities
        if explore_result_node_refs is not None:
            updates["explore_result_node_refs"] = explore_result_node_refs
        if decision_scope is not None:
            updates["decision_scope"] = decision_scope
        if required_decision_scopes is not None:
            updates["required_decision_scopes"] = required_decision_scopes
        if claimed_by:
            updates["claimed_by"] = claimed_by
        if bound_agent:
            updates["bound_agent"] = bound_agent
            updates["goal_bound"] = None
        elif goal_bound is not None:
            updates["bound_agent"] = None
            updates["goal_bound"] = goal_bound
        if blocks_agent:
            updates["blocks_agent"] = blocks_agent
        if excluded_agents is not None:
            updates["excluded_agents"] = excluded_agents
        if global_gate is not None:
            updates["global_gate"] = global_gate
        if unblocks_todo_id:
            updates["unblocks_todo_id"] = unblocks_todo_id
        if normalized_resume_when:
            updates["resume_when"] = normalized_resume_when
        updates.update(normalized_monitor_metadata)
        if evidence:
            updates["evidence"] = evidence
        if updated_at and not block.get("updated_at"):
            updates["updated_at"] = updated_at
        metadata_line = metadata_line_for_todo_block(block, updates)
        metadata_updated = upsert_todo_metadata(lines, block, metadata_line)
        todo_id = str(block.get("todo_id") or "")
        effective_metadata = parse_todo_metadata_line(metadata_line or "") or {}

    return {
        "added": added,
        "already_exists": not added,
        "metadata_updated": metadata_updated,
        "status_changed": status_changed,
        "changed": added or metadata_updated or status_changed,
        "role": role,
        "section": section,
        "todo": todo_text,
        "todo_id": todo_id,
        "status": normalize_todo_status(effective_metadata.get("status")) or normalized_status,
        "task_class": effective_metadata.get("task_class") or task_class,
        "action_kind": effective_metadata.get("action_kind") or action_kind,
        "task_repository": normalize_todo_task_repository(
            effective_metadata.get("task_repository") or task_repository
        ),
        "continuation_policy": normalize_todo_continuation_policy(
            effective_metadata.get("continuation_policy") or continuation_policy
        ),
        "required_write_scopes": normalize_required_write_scopes(
            effective_metadata.get("required_write_scopes") or required_write_scopes
        ),
        "required_capabilities": normalize_required_capabilities(
            effective_metadata.get("required_capabilities") or required_capabilities
        ),
        "target_capabilities": normalize_target_capabilities(
            effective_metadata.get("target_capabilities") or target_capabilities
        ),
        "explore_result_node_refs": normalize_explore_result_node_refs(
            effective_metadata.get("explore_result_node_refs") or explore_result_node_refs
        ),
        "decision_scope": normalize_todo_decision_scope(
            effective_metadata.get("decision_scope") or decision_scope
        ),
        "required_decision_scopes": normalize_todo_required_decision_scopes(
            effective_metadata.get("required_decision_scopes") or required_decision_scopes
        ),
        "claimed_by": normalize_todo_claimed_by(effective_metadata.get("claimed_by")),
        "bound_agent": normalize_todo_bound_agent(effective_metadata.get("bound_agent")),
        "goal_bound": normalize_todo_goal_bound(effective_metadata.get("goal_bound")),
        "blocks_agent": normalize_todo_blocks_agent(effective_metadata.get("blocks_agent")),
        "excluded_agents": normalize_todo_excluded_agents(
            effective_metadata.get("excluded_agents")
        ),
        "global_gate": normalize_todo_global_gate(effective_metadata.get("global_gate")),
        "unblocks_todo_id": normalize_todo_id(effective_metadata.get("unblocks_todo_id")),
        "resume_when": normalize_todo_resume_when(effective_metadata.get("resume_when")),
        "target_key": effective_metadata.get("target_key"),
        "cadence": effective_metadata.get("cadence"),
        "next_due_at": effective_metadata.get("next_due_at"),
        "expires_at": effective_metadata.get("expires_at"),
        "evidence": effective_metadata.get("evidence") or evidence,
        "updated_at": effective_metadata.get("updated_at") or updated_at,
    }


def add_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    role: str,
    text: str,
    status: str | None = None,
    task_class: str | None = None,
    action_kind: str | None = None,
    task_repository: str | None = None,
    continuation_policy: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    explore_result_node_refs: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    bound_agent: str | None = None,
    goal_bound: bool = False,
    blocks_agent: str | None = None,
    excluded_agents: list[str] | None = None,
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
    if role == "agent" and blocks_agent:
        raise ValueError(
            "blocks_agent is only valid for user gates; use --excluded-agent for "
            "agent executor constraints"
        )
    if role == "user" and claimed_by:
        raise ValueError(
            "claimed_by is execution ownership for agent todos, not a user-todo "
            "binding; use --bound-agent or --goal-bound"
        )
    if task_repository and role != "agent":
        raise ValueError("task_repository is only valid for agent todos")
    normalized_status = normalize_todo_status(status) if status else TODO_STATUS_OPEN
    if status and not normalized_status:
        raise ValueError("todo status must be one of: open, done, blocked, deferred")
    if normalized_status == TODO_STATUS_DONE:
        raise ValueError("todo add cannot create completed work; add it open and use `loopx todo complete`")
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
        registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
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
        inferred_bound_agent = bound_agent
        if role == "user" and not inferred_bound_agent and not goal_bound:
            if effective_agent_id:
                inferred_bound_agent = effective_agent_id
            elif task_class == TODO_TASK_CLASS_USER_GATE and effective_blocks_agent:
                inferred_bound_agent = effective_blocks_agent
            elif len(registered_agents) == 1:
                inferred_bound_agent = registered_agents[0]
        effective_bound_agent = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=inferred_bound_agent,
                field="bound_agent",
            )
            if inferred_bound_agent
            else None
        )
        effective_goal_bound = bool(goal_bound or global_gate)
        effective_excluded_agents = require_registered_todo_excluded_agents(
            registry_path=registry_path,
            goal_id=goal_id,
            excluded_agents=excluded_agents,
        )
        if role != "agent" and effective_excluded_agents:
            raise ValueError("excluded_agents is only valid for agent todos")
        require_user_gate_scope(
            registry_path=registry_path,
            goal_id=goal_id,
            role=role,
            task_class=task_class,
            blocks_agent=effective_blocks_agent,
            global_gate=True if global_gate else None,
        )
        require_user_todo_binding(
            registry_path=registry_path,
            goal_id=goal_id,
            role=role,
            task_class=task_class,
            bound_agent=effective_bound_agent,
            goal_bound=effective_goal_bound,
            blocks_agent=effective_blocks_agent,
            global_gate=True if global_gate else None,
        )
        normalized_unblocks_todo_id = normalize_todo_id(unblocks_todo_id) if unblocks_todo_id else None
        if unblocks_todo_id and not normalized_unblocks_todo_id:
            raise ValueError("unblocks_todo_id must use the public token shape todo_<letters-digits-underscore-hyphen>")
        normalized_resume_when = require_supported_todo_resume_when(resume_when)
        if normalized_status == TODO_STATUS_DEFERRED and not normalized_resume_when:
            raise ValueError("deferred todo add requires --resume-when with a supported condition")
        normalized_monitor_metadata = require_monitor_metadata_scope(
            monitor_metadata=monitor_metadata,
            role=role,
            task_class=task_class,
        )
        add_result = add_todo_to_lines(
            lines,
            role=role,
            text=todo_text,
            status=normalized_status,
            task_class=task_class,
            action_kind=action_kind,
            task_repository=task_repository,
            continuation_policy=continuation_policy,
            required_write_scopes=required_write_scopes,
            required_capabilities=required_capabilities,
            target_capabilities=target_capabilities,
            explore_result_node_refs=explore_result_node_refs,
            decision_scope=decision_scope,
            required_decision_scopes=required_decision_scopes,
            claimed_by=effective_claimed_by,
            bound_agent=effective_bound_agent,
            goal_bound=(
                True if role == "user" and effective_goal_bound else None
            ),
            blocks_agent=effective_blocks_agent,
            excluded_agents=effective_excluded_agents,
            global_gate=True if global_gate else None,
            unblocks_todo_id=normalized_unblocks_todo_id,
            resume_when=normalized_resume_when,
            monitor_metadata=normalized_monitor_metadata,
            updated_at=updated_at,
        )
        added = bool(add_result["added"])
        metadata_updated = bool(add_result["metadata_updated"])
        changed = bool(add_result["changed"])

        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if changed:
            new_text = replace_updated_at(new_text, updated_at)
        if changed and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")

    payload = {
        "ok": True,
        "dry_run": dry_run,
        "added": added,
        "already_exists": bool(add_result["already_exists"]),
        "metadata_updated": metadata_updated,
        "status_changed": bool(add_result.get("status_changed")),
        "goal_id": goal_id,
        "role": role,
        "section": add_result.get("section"),
        "todo": todo_text,
        "todo_id": add_result.get("todo_id"),
        "status": add_result.get("status"),
        "task_class": add_result.get("task_class"),
        "action_kind": add_result.get("action_kind"),
        "task_repository": add_result.get("task_repository"),
        "continuation_policy": add_result.get("continuation_policy"),
        "required_write_scopes": add_result.get("required_write_scopes"),
        "required_capabilities": add_result.get("required_capabilities"),
        "target_capabilities": add_result.get("target_capabilities"),
        "explore_result_node_refs": add_result.get("explore_result_node_refs"),
        "decision_scope": add_result.get("decision_scope"),
        "required_decision_scopes": add_result.get("required_decision_scopes"),
        "claimed_by": add_result.get("claimed_by"),
        "bound_agent": add_result.get("bound_agent"),
        "goal_bound": add_result.get("goal_bound"),
        "agent_id": effective_agent_id,
        "blocks_agent": add_result.get("blocks_agent"),
        "excluded_agents": add_result.get("excluded_agents"),
        "global_gate": add_result.get("global_gate"),
        "unblocks_todo_id": add_result.get("unblocks_todo_id"),
        "resume_when": add_result.get("resume_when"),
        "target_key": add_result.get("target_key"),
        "cadence": add_result.get("cadence"),
        "next_due_at": add_result.get("next_due_at"),
        "expires_at": add_result.get("expires_at"),
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
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
    task_repository: str | None = None,
    continuation_policy: str | None = None,
    required_write_scopes: list[str] | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
    explore_result_node_refs: list[str] | None = None,
    decision_scope: Any = None,
    required_decision_scopes: Any = None,
    claimed_by: str | None = None,
    bound_agent: str | None = None,
    goal_bound: bool = False,
    blocks_agent: str | None = None,
    clear_blocks_agent: bool = False,
    excluded_agents: list[str] | None = None,
    clear_excluded_agents: bool = False,
    global_gate: bool = False, clear_global_gate: bool = False,
    agent_id: str | None = None, authority_reason: str | None = None,
    unblocks_todo_id: str | None = None,
    successor_todo_ids: list[str] | None = None,
    resume_when: str | None = None,
    clear_resume_when: bool = False,
    no_followup: bool | None = None,
    monitor_metadata: dict[str, Any] | None = None,
    clear_claim: bool = False,
    claim_only: bool = False,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if excluded_agents and clear_excluded_agents:
        raise ValueError(
            "todo update accepts either excluded_agents or clear_excluded_agents, not both"
        )
    if blocks_agent and clear_blocks_agent:
        raise ValueError("todo update accepts either blocks_agent or clear_blocks_agent, not both")
    if bound_agent and goal_bound:
        raise ValueError("todo update accepts either bound_agent or goal_bound, not both")
    if resume_when and clear_resume_when:
        raise ValueError(
            "todo update accepts either resume_when or clear_resume_when, not both"
        )
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
        effective_blocks_agent = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=blocks_agent,
                field="blocks_agent",
            )
            if blocks_agent
            else None
        )
        effective_bound_agent = (
            require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=bound_agent,
                field="bound_agent",
            )
            if bound_agent
            else None
        )
        existing_block_match = find_todo_block(lines, todo_id=todo_id, role=role)
        if not existing_block_match:
            normalized_todo_id = normalize_todo_id(todo_id) or todo_id
            raise ValueError(f"todo_id {normalized_todo_id!r} was not found in active user or agent todos")
        existing_role, _section, _start, _end, existing_block = existing_block_match
        target_role = role or existing_role
        authority_todo = dict(existing_block)
        authority_todo["role"] = target_role
        authority_action = todo_update_authority_action(
            existing_role=existing_role,
            role=role,
            claimed_by=claimed_by,
            clear_claim=clear_claim,
            other_values=(
                text, status, note, evidence, reason, task_class, action_kind,
                task_repository, continuation_policy, required_write_scopes,
                required_capabilities, target_capabilities,
                explore_result_node_refs, decision_scope,
                required_decision_scopes, blocks_agent, clear_blocks_agent,
                bound_agent, goal_bound,
                excluded_agents, clear_excluded_agents, global_gate,
                clear_global_gate, unblocks_todo_id, successor_todo_ids,
                resume_when, clear_resume_when, no_followup,
            ),
            monitor_metadata=monitor_metadata,
        )
        mutation_authority = authorize_todo_lifecycle_mutation(
            registry_path=registry_path,
            goal_id=goal_id,
            command="claim" if claim_only else "update",
            todo=authority_todo,
            actor_agent_id=effective_agent_id,
            authority_action=None if claim_only else authority_action,
            authority_reason=authority_reason,
            requested_claimed_by=effective_claimed_by,
        )
        target_task_class = task_class or str(existing_block.get("task_class") or "")
        if target_role == "user" and claimed_by:
            raise ValueError(
                "claimed_by is execution ownership for agent todos, not a user-todo "
                "binding; use --bound-agent or --goal-bound"
            )
        if target_role == "agent" and blocks_agent:
            raise ValueError(
                "blocks_agent is only valid for user gates; use excluded_agents for "
                "agent executor constraints"
            )
        if task_repository and target_role != "agent":
            raise ValueError("task_repository is only valid for agent todos")
        effective_excluded_agents = (
            []
            if clear_excluded_agents
            else require_registered_todo_excluded_agents(
                registry_path=registry_path,
                goal_id=goal_id,
                excluded_agents=excluded_agents,
            )
            if excluded_agents is not None
            else None
        )
        existing_excluded_agents = normalize_todo_excluded_agents(
            existing_block.get("excluded_agents")
        )
        target_excluded_agents = (
            effective_excluded_agents
            if effective_excluded_agents is not None
            else existing_excluded_agents
        )
        if target_role != "agent" and target_excluded_agents:
            raise ValueError(
                "excluded_agents is only valid for agent todos; clear exclusions before "
                "moving this todo to a user role"
            )
        target_status = (
            normalize_todo_status(status)
            if status
            else str(existing_block.get("status") or TODO_STATUS_OPEN)
        )
        if status and target_role == "agent" and target_status == TODO_STATUS_DONE:
            raise ValueError(
                "agent todo completion must use complete_goal_todo "
                "(CLI: `loopx todo complete`) so completion policy, successor, "
                "and no-follow-up contracts are enforced"
            )
        existing_blocks_agent = normalize_todo_blocks_agent(existing_block.get("blocks_agent"))
        existing_global_gate = normalize_todo_global_gate(existing_block.get("global_gate"))
        existing_bound_agent = normalize_todo_bound_agent(existing_block.get("bound_agent"))
        existing_goal_bound = normalize_todo_goal_bound(existing_block.get("goal_bound"))
        target_blocks_agent = None if clear_blocks_agent else effective_blocks_agent or existing_blocks_agent
        target_global_gate = resolve_user_gate_global_gate_update(
            role=target_role,
            task_class=target_task_class,
            existing_global_gate=existing_global_gate,
            global_gate=global_gate,
            clear_global_gate=clear_global_gate,
        )
        target_bound_agent = (
            effective_bound_agent
            if bound_agent
            else None
            if goal_bound
            else existing_bound_agent
        )
        target_goal_bound = True if goal_bound else False if bound_agent else existing_goal_bound
        registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
        if target_role != "user":
            target_bound_agent = None
            target_goal_bound = None
        elif target_task_class == TODO_TASK_CLASS_USER_GATE and target_global_gate:
            target_bound_agent = None
            target_goal_bound = True
        elif target_task_class == TODO_TASK_CLASS_USER_GATE and target_blocks_agent:
            target_bound_agent = target_blocks_agent
            target_goal_bound = False
        elif not target_bound_agent and not target_goal_bound:
            if len(registered_agents) == 1:
                target_bound_agent = registered_agents[0]
        if target_status != TODO_STATUS_DONE:
            require_user_todo_task_class(
                role=target_role,
                task_class=target_task_class,
                blocks_agent=target_blocks_agent,
                global_gate=target_global_gate,
            )
            require_user_todo_binding(
                registry_path=registry_path,
                goal_id=goal_id,
                role=target_role,
                task_class=target_task_class,
                bound_agent=target_bound_agent,
                goal_bound=target_goal_bound,
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
        normalized_resume_when = require_supported_todo_resume_when(resume_when)
        effective_resume_when = (
            None
            if clear_resume_when
            else normalized_resume_when
            or normalize_supported_todo_resume_when(existing_block.get("resume_when"))
        )
        if target_status == TODO_STATUS_DEFERRED and not effective_resume_when:
            raise ValueError("transition to deferred requires --resume-when with a supported condition")
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
            task_repository=task_repository,
            continuation_policy=continuation_policy,
            required_write_scopes=required_write_scopes,
            required_capabilities=required_capabilities,
            target_capabilities=target_capabilities,
            explore_result_node_refs=explore_result_node_refs,
            decision_scope=decision_scope,
            required_decision_scopes=required_decision_scopes,
            claimed_by=effective_claimed_by,
            bound_agent=target_bound_agent if target_role == "user" else None,
            goal_bound=(
                True
                if target_role == "user" and target_goal_bound
                else None
            ),
            clear_user_binding=(
                target_role != "user"
                and bool(existing_bound_agent or existing_goal_bound is not None)
            ),
            blocks_agent=effective_blocks_agent,
            clear_blocks_agent=clear_blocks_agent,
            excluded_agents=effective_excluded_agents,
            global_gate=True if global_gate else None,
            clear_global_gate=clear_global_gate,
            unblocks_todo_id=normalized_unblocks_todo_id,
            successor_todo_ids=normalized_successor_todo_ids if successor_todo_ids is not None else None,
            resume_when=normalized_resume_when,
            clear_resume_when=clear_resume_when,
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
        "mutation_authority": mutation_authority,
        **update_result,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
    }
    if successor_todo_ids is not None:
        parent_successor_advisory = build_open_parent_successor_advisory(
            todo_id=update_result.get("todo_id"),
            status=update_result.get("status"),
            successor_todo_ids=update_result.get("successor_todo_ids"),
        )
        if parent_successor_advisory:
            payload["parent_successor_advisory"] = parent_successor_advisory
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
    decision_outcome: str | None = None,
    evidence: str | None = None,
    note: str | None = None,
    no_followup: bool = False,
    successor_todo_ids: list[str] | None = None,
    claimed_by: str | None = None,
    clear_claim: bool = False,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_user_task_class: str | None = None,
    next_claimed_by: str | None = None,
    next_task_class: str | None = None,
    next_action_kind: str | None = None,
    next_task_repository: str | None = None,
    next_required_capabilities: list[str] | None = None,
    next_continuation_policy: str | None = None,
    next_excluded_agents: list[str] | None = None,
    self_merged: bool = False,
    agent_id: str | None = None, authority_reason: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if next_task_repository and not next_agent_todo:
        raise ValueError("--next-task-repository requires --next-agent-todo")
    if next_required_capabilities and not next_agent_todo:
        raise ValueError("--next-required-capability requires --next-agent-todo")
    effective_next_user_task_class = resolve_next_user_task_class(
        next_user_todo,
        next_user_task_class,
    )
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
        completion_match = find_todo_block(lines, todo_id=todo_id, role=role)
        completion_todo = None
        event_context = None
        if completion_match:
            completion_role, _section, _start, _end, completion_block = completion_match
            completion_todo = dict(completion_block)
            completion_todo["role"] = completion_role
        else:
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
                completion_todo = dict(event_context["item"])
                completion_todo["role"] = event_context["role"]
        effective_decision_outcome = require_completion_decision_outcome(
            completion_todo,
            decision_outcome,
            materialized=bool(completion_match),
        )
        if completion_todo is None:
            normalized_todo_id = normalize_todo_id(todo_id) or todo_id
            raise ValueError(
                f"todo_id {normalized_todo_id!r} was not found in active user or agent todos"
            )
        decision_target = None
        target_todo_id = normalize_todo_id(completion_todo.get("unblocks_todo_id"))
        if target_todo_id:
            target_match = find_todo_block(
                lines,
                todo_id=target_todo_id,
                role="agent",
            )
            if target_match:
                target_role, _target_section, _target_start, _target_end, target_block = (
                    target_match
                )
                decision_target = dict(target_block)
                decision_target["role"] = target_role
        mutation_authority = authorize_todo_lifecycle_mutation(
            registry_path=registry_path,
            goal_id=goal_id,
            command="complete",
            todo=completion_todo,
            actor_agent_id=agent_id, authority_reason=authority_reason,
            requested_claimed_by=claimed_by,
            decision_outcome=effective_decision_outcome,
            decision_target=decision_target,
        )
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
                continue
            if event_context:
                for successor_role in ("user", "agent"):
                    summary = event_context["fields"].get(f"{successor_role}_todos")
                    items = summary.get("items") if isinstance(summary, dict) else []
                    successor_item = next(
                        (
                            dict(item)
                            for item in items or []
                            if isinstance(item, dict)
                            and normalize_todo_id(item.get("todo_id"))
                            == successor_todo_id
                        ),
                        None,
                    )
                    if successor_item:
                        successor_item["role"] = successor_role
                        linked_successors.append(
                            linked_successor_from_todo(successor_item)
                        )
                        break
        completion_policy = resolve_completion_policy(
            registry_path=registry_path,
            goal_id=goal_id,
            claimed_by=claimed_by,
            next_claimed_by=next_claimed_by,
            next_agent_todo=next_agent_todo,
            next_action_kind=next_action_kind,
            next_continuation_policy=next_continuation_policy,
            next_excluded_agents=next_excluded_agents or [],
            self_merged=self_merged,
            evidence=evidence,
            no_followup=no_followup,
            linked_successors=linked_successors,
            completion_todo=completion_todo,
        )
        effective_claimed_by = completion_policy.effective_claimed_by
        registered_agents = completion_policy.registered_agents
        effective_next_claimed_by = completion_policy.effective_next_claimed_by
        effective_next_excluded_agents = (
            completion_policy.effective_next_excluded_agents
        )
        effective_self_merged = completion_policy.self_merged
        if not completion_match:
            if event_context:
                event_result = complete_event_projected_goal_todo(
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
                    next_user_task_class=effective_next_user_task_class,
                    next_claimed_by=effective_next_claimed_by,
                    next_task_class=next_task_class,
                    next_action_kind=next_action_kind,
                    next_task_repository=next_task_repository,
                    next_required_capabilities=next_required_capabilities,
                    next_continuation_policy=next_continuation_policy,
                    self_merged=effective_self_merged,
                    next_excluded_agents=effective_next_excluded_agents,
                    registered_agents=registered_agents,
                    updated_at=updated_at,
                    dry_run=dry_run,
                )
                event_result["linked_successor_id"] = completion_policy.linked_successor_id
                event_result["mutation_authority"] = mutation_authority
                return event_result
        update_result = apply_todo_update_to_lines(
            lines,
            todo_id=todo_id,
            status=TODO_STATUS_DONE,
            role=role,
            decision_outcome=effective_decision_outcome,
            note=note,
            evidence=evidence,
            claimed_by=effective_claimed_by,
            clear_claim=clear_claim,
            no_followup=True if no_followup else None,
            successor_todo_ids=normalized_successor_todo_ids if successor_todo_ids is not None else None,
            updated_at=updated_at,
        )
        unblock_resume, decision_scope_resolution = (
            apply_completed_user_todo_lifecycle(
                lines,
                completion_todo=completion_todo,
                update_result=update_result,
                fallback_todo_id=todo_id,
                decision_outcome=effective_decision_outcome,
                updated_at=updated_at,
                apply_update=apply_todo_update_to_lines,
            )
        )
        next_unblocks_todo_id = (
            normalize_todo_id(str(update_result.get("todo_id") or todo_id))
            if next_agent_todo
            else None
        )
        next_user_bound_agent = None
        if next_user_todo and len(registered_agents) > 1:
            next_user_bound_agent = effective_claimed_by
            if not next_user_bound_agent:
                raise ValueError(
                    "multi-agent --next-user-todo requires a completing --claimed-by "
                    "agent so the user todo can be bound"
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
                    task_repository=next_task_repository,
                    required_capabilities=next_required_capabilities,
                    continuation_policy=next_continuation_policy,
                    claimed_by=effective_next_claimed_by,
                    excluded_agents=effective_next_excluded_agents,
                    unblocks_todo_id=next_unblocks_todo_id,
                    updated_at=updated_at,
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
                    task_class=effective_next_user_task_class,
                    action_kind=(
                        "gate"
                        if effective_next_user_task_class == TODO_TASK_CLASS_USER_GATE
                        else None
                    ),
                    bound_agent=next_user_bound_agent,
                    blocks_agent=(
                        next_user_bound_agent
                        if effective_next_user_task_class == TODO_TASK_CLASS_USER_GATE
                        else None
                    ),
                    updated_at=updated_at,
                )
            )
        generated_successor_todo_ids = [
            todo_id
            for todo_id in normalize_todo_id_list([item.get("todo_id") for item in next_results])
        ]
        successor_metadata_updated = link_generated_successor_todo_ids(
            lines,
            update_result=update_result,
            role=role,
            successor_todo_ids=generated_successor_todo_ids,
        )
        next_changed = any(item.get("added") or item.get("metadata_updated") for item in next_results)
        changed = bool(
            update_result["changed"]
            or next_changed
            or successor_metadata_updated
            or (unblock_resume or {}).get("changed")
            or (decision_scope_resolution or {}).get("changed")
        )
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if changed:
            new_text = replace_updated_at(new_text, updated_at)
        if changed and not dry_run:
            resolved_state_file.write_text(new_text, encoding="utf-8")
    result = {
        "ok": True,
        "dry_run": dry_run,
        "completed": True,
        "goal_id": goal_id,
        **update_result,
        "changed": changed,
        "next_todos": next_results,
        "linked_successor_id": completion_policy.linked_successor_id,
        "mutation_authority": mutation_authority,
        "state_file": str(resolved_state_file),
        "project": str(resolved_project) if resolved_project else None,
        "updated_at": updated_at if changed else None,
    }
    if unblock_resume:
        result["unblock_resume"] = unblock_resume
    if decision_scope_resolution:
        result["decision_scope_resolution"] = decision_scope_resolution
    if effective_decision_outcome:
        result["decision_outcome"] = effective_decision_outcome
    result["self_merged"] = effective_self_merged
    return result

def supersede_goal_todo(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    role: str | None = None,
    reason: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_user_task_class: str | None = None,
    next_claimed_by: str | None = None,
    next_task_class: str | None = None,
    next_action_kind: str | None = None,
    next_task_repository: str | None = None,
    next_required_capabilities: list[str] | None = None,
    next_continuation_policy: str | None = None,
    next_excluded_agents: list[str] | None = None,
    agent_id: str | None = None, authority_reason: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if next_task_repository and not next_agent_todo:
        raise ValueError("--next-task-repository requires --next-agent-todo")
    if next_required_capabilities and not next_agent_todo:
        raise ValueError("--next-required-capability requires --next-agent-todo")
    effective_next_user_task_class = resolve_next_user_task_class(
        next_user_todo,
        next_user_task_class,
    )
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
        current_match = find_todo_block(lines, todo_id=todo_id, role=role)
        if not current_match:
            normalized_todo_id = normalize_todo_id(todo_id) or todo_id
            raise ValueError(
                f"todo_id {normalized_todo_id!r} was not found in active user or agent todos"
            )
        current_role, _section, _start, _end, current_block = current_match
        authority_todo = dict(current_block)
        authority_todo["role"] = current_role
        mutation_authority = authorize_todo_lifecycle_mutation(
            registry_path=registry_path,
            goal_id=goal_id,
            command="supersede",
            todo=authority_todo,
            actor_agent_id=agent_id, authority_reason=authority_reason,
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
        effective_next_excluded_agents = require_registered_todo_excluded_agents(
            registry_path=registry_path,
            goal_id=goal_id,
            excluded_agents=next_excluded_agents,
            field="next_excluded_agents",
        )
        if effective_next_claimed_by and not next_agent_todo:
            raise ValueError("--next-claimed-by requires --next-agent-todo")
        if effective_next_excluded_agents and not next_agent_todo:
            raise ValueError("--next-excluded-agent requires --next-agent-todo")
        update_result = apply_todo_update_to_lines(
            lines,
            todo_id=todo_id,
            status=TODO_STATUS_DONE,
            role=role,
            reason=reason,
            note="superseded",
            updated_at=updated_at,
        )
        current_claimed_by = normalize_todo_claimed_by(update_result.get("claimed_by"))
        next_policy = resolve_todo_continuation_policy(
            next_continuation_policy,
            action_kind=next_action_kind,
        )
        if (
            next_agent_todo
            and not effective_next_claimed_by
            and next_policy == TodoContinuationPolicy.SAME_AGENT_NON_DELIVERY
        ):
            effective_next_claimed_by = current_claimed_by
        if effective_next_claimed_by in effective_next_excluded_agents:
            raise ValueError(
                f"next_claimed_by={effective_next_claimed_by!r} cannot also appear in "
                "next_excluded_agents"
            )
        next_unblocks_todo_id = normalize_todo_id(update_result.get("unblocks_todo_id"))
        registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
        next_user_bound_agent = (
            normalize_todo_bound_agent(update_result.get("bound_agent"))
            or normalize_todo_blocks_agent(update_result.get("blocks_agent"))
        )
        if next_user_todo and len(registered_agents) > 1 and not next_user_bound_agent:
            next_user_bound_agent = (
                normalize_todo_claimed_by(update_result.get("claimed_by"))
                or effective_next_claimed_by
            )
            if not next_user_bound_agent:
                raise ValueError(
                    "multi-agent supersede --next-user-todo requires inherited "
                    "blocks_agent, current claimed_by, or next_claimed_by "
                    "so the user todo can be bound"
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
                    task_repository=next_task_repository,
                    required_capabilities=next_required_capabilities,
                    continuation_policy=next_continuation_policy,
                    claimed_by=effective_next_claimed_by,
                    excluded_agents=effective_next_excluded_agents,
                    unblocks_todo_id=next_unblocks_todo_id,
                    updated_at=updated_at,
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
                    task_class=effective_next_user_task_class,
                    action_kind=(
                        "gate"
                        if effective_next_user_task_class == TODO_TASK_CLASS_USER_GATE
                        else None
                    ),
                    bound_agent=next_user_bound_agent,
                    blocks_agent=(
                        next_user_bound_agent
                        if effective_next_user_task_class == TODO_TASK_CLASS_USER_GATE
                        else None
                    ),
                    updated_at=updated_at,
                )
            )
        superseded_by = next((item.get("todo_id") for item in next_results if item.get("todo_id")), None)
        generated_successor_todo_ids = [
            todo_id
            for todo_id in normalize_todo_id_list([item.get("todo_id") for item in next_results])
        ]
        if superseded_by:
            block_match = find_todo_block(lines, todo_id=str(update_result["todo_id"]), role=role)
            if block_match:
                _resolved_role, _section, _start, _end, block = block_match
                update_result["metadata_updated"] = upsert_todo_metadata(
                    lines,
                    block,
                    metadata_line_for_todo_block(
                        block,
                        {
                            "superseded_by": superseded_by,
                            "successor_todo_ids": merge_todo_id_lists(
                                update_result.get("successor_todo_ids"),
                                generated_successor_todo_ids,
                            ),
                        },
                    ),
                ) or update_result["metadata_updated"]
                update_result["superseded_by"] = superseded_by
                update_result["successor_todo_ids"] = merge_todo_id_lists(
                    update_result.get("successor_todo_ids"),
                    generated_successor_todo_ids,
                )
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
        "mutation_authority": mutation_authority,
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
    max_active_done: int = ARCHIVE_COMPLETED_DEFAULT_MAX_ACTIVE_DONE,
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
