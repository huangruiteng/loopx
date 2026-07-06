from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from ..runtime.time import now_utc
from ..todos.contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
)
from .time import parse_scheduler_timestamp

MONITOR_CADENCE_PATTERN = re.compile(
    r"^\s*(?P<count>[1-9][0-9]{0,4})\s*"
    r"(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
    re.IGNORECASE,
)


parse_monitor_timestamp = parse_scheduler_timestamp


def parse_monitor_counter(value: Any) -> int:
    try:
        return max(0, int(str(value or "0").strip()))
    except ValueError:
        return 0


def monitor_cadence_delta(value: Any) -> timedelta | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    match = MONITOR_CADENCE_PATTERN.match(candidate)
    if not match:
        return None
    count = int(match.group("count"))
    unit = match.group("unit").lower()
    if unit.startswith("s"):
        return timedelta(seconds=count)
    if unit.startswith("m"):
        return timedelta(minutes=count)
    if unit.startswith("h"):
        return timedelta(hours=count)
    return timedelta(days=count)


def monitor_next_due_at(
    *,
    generated_at: str,
    cadence: Any = None,
    explicit_next_due_at: Any = None,
) -> str | None:
    explicit = str(explicit_next_due_at or "").strip()
    if explicit:
        if parse_monitor_timestamp(explicit) is None:
            raise ValueError("--next-due-at must be an ISO timestamp")
        return explicit
    delta = monitor_cadence_delta(cadence)
    if delta is None:
        return None
    checked_at = parse_monitor_timestamp(generated_at)
    if checked_at is None:
        checked_at = now_utc()
    return (checked_at + delta).astimezone().replace(microsecond=0).isoformat()


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


def monitor_todo_has_schedule(item: dict[str, Any]) -> bool:
    return bool(
        str(item.get("cadence") or "").strip()
        or str(item.get("next_due_at") or "").strip()
    )


def monitor_todo_expires_at(item: dict[str, Any]) -> datetime | None:
    return parse_monitor_timestamp(item.get("expires_at"))


def monitor_todo_is_expired(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    expires_at = monitor_todo_expires_at(item)
    if expires_at is None:
        return False
    current_time = now or now_utc()
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
    current_time = now or now_utc()
    return next_due_at <= current_time


def monitor_todo_missing_schedule(
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
    return not monitor_todo_has_schedule(item)
