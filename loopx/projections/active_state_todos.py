from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


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
    attach_monitor_writeback_contract: Callable[..., None],
    parse_active_state_todos: Callable[..., dict[str, Any]],
    parse_issue_meta_surface: Callable[[str], dict[str, Any] | None],
    backlog_hygiene_warning: Callable[..., dict[str, Any] | None],
    completed_todo_archive_warning: Callable[[dict[str, Any] | None], dict[str, Any] | None],
    autonomous_replan_obligation: Callable[..., dict[str, Any] | None],
    state_projection_gap_warning: Callable[..., dict[str, Any] | None],
    redacted_status_todo_fields: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
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
        attach_monitor_writeback_contract(
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
        attach_monitor_writeback_contract(
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
        fields = redacted_status_todo_fields(fields)
    return fields
