from __future__ import annotations

import re
from typing import Any, Callable

from ..todo_contract import normalize_todo_action_kind, normalize_todo_task_class


AUTONOMOUS_PRIORITY_PATTERN = re.compile(r"^\s*\[(P[0-4][^\]]*)\]\s*(.+)$", re.I)


def autonomous_priority_label(text: str) -> str | None:
    match = AUTONOMOUS_PRIORITY_PATTERN.match(text)
    if not match:
        return None
    return match.group(1).strip().upper()


def autonomous_priority_rank(priority: str | None) -> int:
    if not priority:
        return 50
    match = re.match(r"P([0-4])", priority)
    if not match:
        return 50
    return int(match.group(1))


def autonomous_todo_candidates(
    items: list[dict[str, Any]],
    *,
    task_class: str,
    open_todo_items: Callable[..., list[dict[str, Any]]],
    todo_item_is_actionable_open: Callable[[dict[str, Any]], bool],
    normalize_todo_text: Callable[..., str],
    allowed_waiting_on: set[str] | None = None,
    limit: int,
) -> dict[str, Any] | None:
    allowed_waiting_on = allowed_waiting_on or {"codex"}
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("waiting_on") not in allowed_waiting_on:
            continue
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        if quota.get("state") != "eligible":
            continue
        todos = item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None
        for todo in open_todo_items(todos):
            if not todo_item_is_actionable_open(todo):
                continue
            todo_class = normalize_todo_task_class(
                todo.get("task_class"),
                text=str(todo.get("text") or ""),
                action_kind=todo.get("action_kind"),
            )
            if todo_class != task_class:
                continue
            text = normalize_todo_text(str(todo.get("text") or ""), limit=240)
            if not text:
                continue
            priority = autonomous_priority_label(text)
            candidates.append(
                {
                    "goal_id": item.get("goal_id"),
                    "status": item.get("status"),
                    "waiting_on": item.get("waiting_on"),
                    "quota_state": quota.get("state"),
                    "priority": priority,
                    "todo_index": todo.get("index"),
                    "task_class": todo_class,
                    "text": text,
                    "source": "agent_todos",
                }
            )
            action_kind = normalize_todo_action_kind(todo.get("action_kind"))
            if action_kind:
                candidates[-1]["action_kind"] = action_kind
    if not candidates:
        return None
    candidates.sort(
        key=lambda candidate: (
            autonomous_priority_rank(
                candidate.get("priority") if isinstance(candidate.get("priority"), str) else None
            ),
            str(candidate.get("goal_id") or ""),
            int(candidate.get("todo_index") or 0),
        )
    )
    return {
        "source": "attention_queue.agent_todos",
        "open_count": len(candidates),
        "task_class": task_class,
        "items": candidates[:limit],
    }
