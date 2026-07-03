from __future__ import annotations

from typing import Any, Callable


def todo_summary_open_count(
    summary: dict[str, Any] | None,
    *,
    open_todo_items: Callable[..., list[dict[str, Any]]],
    todo_item_is_actionable_open: Callable[[dict[str, Any]], bool],
    fallback_limit: int,
) -> int:
    if not isinstance(summary, dict):
        return 0
    for key in ("open_count", "open"):
        value = summary.get(key)
        if isinstance(value, int):
            return max(0, value)
    return len(
        [
            item
            for item in open_todo_items(summary, limit=fallback_limit)
            if todo_item_is_actionable_open(item)
        ]
    )


def todo_summary_lane_items(summary: dict[str, Any] | None, lane: str) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    raw_items = summary.get(lane)
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def attention_item_is_monitor_quiet_display_candidate(
    item: dict[str, Any],
    *,
    open_todo_items: Callable[..., list[dict[str, Any]]],
    todo_item_is_actionable_open: Callable[[dict[str, Any]], bool],
    fallback_limit: int,
) -> bool:
    if item.get("waiting_on") != "codex" or item.get("severity") != "action":
        return False
    agent_todos = item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None
    if not agent_todos:
        return False
    user_todos = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else None
    if (
        todo_summary_open_count(
            user_todos,
            open_todo_items=open_todo_items,
            todo_item_is_actionable_open=todo_item_is_actionable_open,
            fallback_limit=fallback_limit,
        )
        > 0
    ):
        return False
    open_count = todo_summary_open_count(
        agent_todos,
        open_todo_items=open_todo_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        fallback_limit=fallback_limit,
    )
    if open_count <= 0:
        return False
    monitor_items = [
        item
        for item in todo_summary_lane_items(agent_todos, "monitor_open_items")
        if todo_item_is_actionable_open(item)
    ]
    executable_items = [
        *todo_summary_lane_items(agent_todos, "first_executable_items"),
        *todo_summary_lane_items(agent_todos, "executable_backlog_items"),
        *todo_summary_lane_items(agent_todos, "claimed_advancement_open_items"),
    ]
    if any(todo_item_is_actionable_open(todo) for todo in executable_items):
        return False
    return len(monitor_items) == open_count


def quiet_monitor_display_action(
    raw_action: str | None,
    *,
    fallback_action: str,
) -> str:
    action = str(raw_action or "").strip()
    if not action:
        return fallback_action
    lowered = action.lower()
    if lowered.startswith("no immediate agent work"):
        return action
    if lowered.startswith("quiet monitor only until "):
        suffix = action[len("Quiet monitor only until ") :].strip()
        if suffix:
            return f"No immediate agent work; keep the monitor quiet until {suffix}"
    if lowered.startswith("wait quietly"):
        return f"No immediate agent work; {action[0].lower()}{action[1:]}"
    return f"No immediate agent work; monitor quietly. Context: {action}"


def normalize_monitor_quiet_attention_display(
    item: dict[str, Any],
    *,
    is_monitor_quiet_display_candidate: Callable[[dict[str, Any]], bool],
    display_fallback_action: str,
    monitor_signal_waiting_on: str,
    monitor_display_schema_version: str,
    monitor_display_stop_condition: str,
) -> None:
    if not is_monitor_quiet_display_candidate(item):
        return
    old_waiting_on = str(item.get("waiting_on") or "")
    old_severity = str(item.get("severity") or "")
    display_action = quiet_monitor_display_action(
        str(item.get("recommended_action") or ""),
        fallback_action=display_fallback_action,
    )
    item["execution_waiting_on"] = old_waiting_on
    item["waiting_on"] = monitor_signal_waiting_on
    item["severity"] = "watch"
    item["recommended_action"] = display_action
    item["monitor_display"] = {
        "schema_version": monitor_display_schema_version,
        "mode": "monitor_quiet",
        "no_immediate_agent_work": True,
        "execution_waiting_on": old_waiting_on,
        "execution_severity": old_severity,
        "waiting_on": monitor_signal_waiting_on,
        "severity": "watch",
        "material_transition": (
            "write back only a material monitor transition, regression, or concrete blocker"
        ),
    }
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        project_asset["owner"] = monitor_signal_waiting_on
        project_asset["gate"] = "none"
        project_asset["support_mode"] = "read_only_observer"
        project_asset["next_action"] = display_action
        project_asset["stop_condition"] = monitor_display_stop_condition
        project_asset["monitor_display"] = dict(item["monitor_display"])
