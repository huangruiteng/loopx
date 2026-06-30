from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..todo_contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
)


def parse_monitor_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def monitor_todo_task_class(item: dict[str, Any], *, task_text: str | None = None) -> str:
    text = str(item.get("text") or "") if task_text is None else task_text
    return normalize_todo_task_class(
        item.get("task_class"),
        text=text,
        action_kind=item.get("action_kind"),
    )


def monitor_todo_is_actionable_open(item: dict[str, Any]) -> bool:
    if item.get("done") is True:
        return False
    status = normalize_todo_status(item.get("status")) or TODO_STATUS_OPEN
    if status != TODO_STATUS_OPEN:
        return False
    if normalize_todo_resume_when(item.get("resume_when")):
        return item.get("resume_ready") is True
    return True


def monitor_todo_next_due_at(item: dict[str, Any]) -> datetime | None:
    return parse_monitor_timestamp(item.get("next_due_at"))


def monitor_todo_expires_at(item: dict[str, Any]) -> datetime | None:
    return parse_monitor_timestamp(item.get("expires_at"))


def monitor_todo_is_expired(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    expires_at = monitor_todo_expires_at(item)
    if expires_at is None:
        return False
    current_time = now or datetime.now(timezone.utc)
    return expires_at <= current_time


def monitor_todo_is_due(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
    task_text: str | None = None,
) -> bool:
    if not monitor_todo_is_actionable_open(item):
        return False
    if monitor_todo_task_class(item, task_text=task_text) != TODO_TASK_CLASS_MONITOR:
        return False
    if monitor_todo_is_expired(item, now=now):
        return False
    next_due_at = monitor_todo_next_due_at(item)
    if next_due_at is None:
        return False
    current_time = now or datetime.now(timezone.utc)
    return next_due_at <= current_time
