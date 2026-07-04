from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION = "monitor_writeback_contract_v0"


def _attach_monitor_writeback_contract(
    fields: dict[str, Any],
    *,
    supported: bool,
    source: str,
) -> None:
    if supported:
        return
    contract = {
        "schema_version": MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION,
        "supported": False,
        "source": source,
    }
    for key in ("user_todos", "agent_todos"):
        summary = fields.get(key)
        if isinstance(summary, dict):
            summary["monitor_writeback"] = dict(contract)


def attach_monitor_writeback_contract(
    fields: dict[str, Any],
    *,
    supported: bool,
    source: str,
) -> None:
    _attach_monitor_writeback_contract(fields, supported=supported, source=source)


def _redacted_status_todo_fields(fields: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(fields)
    for key in ("user_todos", "agent_todos"):
        group = redacted.get(key)
        if not isinstance(group, dict):
            continue
        group_copy = dict(group)
        items: list[Any] = []
        for item in group_copy.get("items") or []:
            if not isinstance(item, dict):
                items.append(item)
                continue
            item_copy = dict(item)
            materials = item_copy.get("review_materials")
            if isinstance(materials, list):
                redacted_materials = []
                for material in materials:
                    if not isinstance(material, dict):
                        redacted_materials.append(material)
                        continue
                    material_copy = dict(material)
                    material_copy.pop("resolved_path", None)
                    redacted_materials.append(material_copy)
                item_copy["review_materials"] = redacted_materials
            items.append(item_copy)
        group_copy["items"] = items
        redacted[key] = group_copy
    return redacted


def redacted_status_todo_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return _redacted_status_todo_fields(fields)


def active_state_todo_fields(
    goal: dict[str, Any],
    *,
    runtime_root: Path | None = None,
    resolve_goal_local_path: Callable[..., Path | None],
    active_state_next_action_entries: Callable[..., list[str]],
    active_next_action_todo_ids: Callable[[str], set[str]],
    load_rollout_events: Callable[..., list[dict[str, Any]]],
    rollout_event_log_path: Callable[[Path, str], Path],
    max_todo_index_rollout_events_per_goal: int,
    active_state_event_projection_fields: Callable[..., dict[str, Any]],
    parse_active_state_todos: Callable[..., dict[str, Any]],
    parse_issue_meta_surface: Callable[[str], dict[str, Any] | None],
    backlog_hygiene_warning: Callable[..., dict[str, Any] | None],
    completed_todo_archive_warning: Callable[[dict[str, Any] | None], dict[str, Any] | None],
    autonomous_replan_obligation: Callable[..., dict[str, Any] | None],
    state_projection_gap_warning: Callable[..., dict[str, Any] | None],
    attach_monitor_writeback_contract: Callable[..., None] | None = None,
    redacted_status_todo_fields: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    monitor_writeback_contract_writer = attach_monitor_writeback_contract or _attach_monitor_writeback_contract
    todo_field_redactor = redacted_status_todo_fields or _redacted_status_todo_fields
    state_path = resolve_goal_local_path(goal.get("state_file"), goal, fallback_base=Path.cwd())
    if state_path is None or not state_path.exists():
        return {}
    try:
        state_text = state_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    next_action_entries = active_state_next_action_entries(state_text, limit=3)
    preferred_todo_ids: set[str] = set()
    for entry in next_action_entries:
        preferred_todo_ids.update(active_next_action_todo_ids(entry))
    rollout_events: list[dict[str, Any]] = []
    goal_id = str(goal.get("id") or "").strip()
    if runtime_root is not None and goal_id:
        rollout_events = load_rollout_events(
            rollout_event_log_path(runtime_root, goal_id),
            limit=max_todo_index_rollout_events_per_goal,
        )
    event_fields = active_state_event_projection_fields(
        goal,
        state_path=state_path,
        preferred_todo_ids=preferred_todo_ids,
        rollout_events=rollout_events,
    )
    if event_fields.get("user_todos") or event_fields.get("agent_todos"):
        fields = event_fields
        monitor_writeback_contract_writer(
            fields,
            supported=False,
            source="event_projection_read_model",
        )
    else:
        fields = parse_active_state_todos(
            state_text,
            goal=goal,
            state_path=state_path,
            preferred_todo_ids=preferred_todo_ids,
            rollout_events=rollout_events,
        )
        monitor_writeback_contract_writer(
            fields,
            supported=True,
            source="markdown_active_state",
        )
        if event_fields:
            fields.update(event_fields)
    issue_meta_surface = parse_issue_meta_surface(state_text)
    if issue_meta_surface:
        fields["issue_meta_surface"] = issue_meta_surface
    if next_action_entries:
        fields["active_state_next_action"] = next_action_entries[0]
        fields["active_state_next_action_entries"] = next_action_entries
    warning = backlog_hygiene_warning(
        state_text,
        agent_todos=fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None,
    )
    if warning:
        fields["backlog_hygiene_warning"] = warning
    archive_warning = completed_todo_archive_warning(
        fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None
    )
    if archive_warning:
        fields["completed_todo_archive_warning"] = archive_warning
    replan_obligation = autonomous_replan_obligation(
        state_text,
        agent_todos=fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None,
    )
    if replan_obligation:
        fields["autonomous_replan_obligation"] = replan_obligation
    projection_gap = state_projection_gap_warning(
        state_text,
        user_todos=fields.get("user_todos") if isinstance(fields.get("user_todos"), dict) else None,
        agent_todos=fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None,
    )
    if projection_gap:
        fields["state_projection_gap"] = projection_gap
    if fields:
        fields = todo_field_redactor(fields)
    return fields
