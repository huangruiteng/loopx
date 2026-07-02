from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .policies.monitor_todo import (
    monitor_todo_expires_at,
    monitor_todo_is_actionable_open,
    monitor_todo_is_due,
    monitor_todo_is_expired,
    monitor_todo_next_due_at,
    monitor_todo_task_class,
)


TODO_MISSING_PRIORITY_RANK = 50
TODO_MISSING_INDEX = 999999
TODO_PRIORITY_PREFIX_PATTERN = re.compile(
    r"^\s*\[(P[0-4][^\]]*)\]\s*(.+)$",
    re.IGNORECASE,
)
TODO_PRIORITY_LABEL_PATTERN = re.compile(r"\bP([0-4])\b", re.IGNORECASE)


def todo_priority_parts(text: str) -> tuple[str | None, str]:
    match = TODO_PRIORITY_PREFIX_PATTERN.match(text)
    if not match:
        return None, text
    return match.group(1).strip().upper(), match.group(2).strip()


def todo_priority_label(
    item: dict[str, Any],
    *,
    text_mode: str = "label",
) -> str | None:
    priority = item.get("priority")
    if isinstance(priority, str) and priority.strip():
        return priority.strip().upper()
    text = " ".join(
        str(value or "")
        for value in (item.get("title"), item.get("text"))
        if str(value or "").strip()
    )
    if text_mode == "prefix":
        priority, _ = todo_priority_parts(text)
        return priority
    match = TODO_PRIORITY_LABEL_PATTERN.search(text.upper())
    if not match:
        return None
    return f"P{match.group(1)}"


def todo_priority_rank(value: Any, *, text_mode: str = "label") -> int:
    if isinstance(value, dict):
        priority = todo_priority_label(value, text_mode=text_mode)
    elif isinstance(value, str):
        priority = value.strip().upper()
    else:
        priority = None
    if not priority:
        return TODO_MISSING_PRIORITY_RANK
    match = re.match(r"P([0-4])", priority)
    if not match:
        return TODO_MISSING_PRIORITY_RANK
    return int(match.group(1))


def todo_index_rank(item: dict[str, Any]) -> int:
    try:
        return int(item.get("index"))
    except (TypeError, ValueError):
        return TODO_MISSING_INDEX


def todo_projection_sort_key(
    item: dict[str, Any],
    *,
    text_mode: str = "label",
) -> tuple[int, int]:
    return (todo_priority_rank(item, text_mode=text_mode), todo_index_rank(item))


def todo_item_task_text(
    item: dict[str, Any],
    *,
    keys: tuple[str, ...] = ("title", "text"),
) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in keys
        if str(item.get(key) or "").strip()
    )


def todo_item_task_class(
    item: dict[str, Any],
    *,
    task_text_keys: tuple[str, ...] = ("title", "text"),
) -> str:
    return monitor_todo_task_class(
        item,
        task_text=todo_item_task_text(item, keys=task_text_keys),
    )


def todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    return monitor_todo_is_actionable_open(item)


def todo_item_next_due_at(item: dict[str, Any]) -> datetime | None:
    return monitor_todo_next_due_at(item)


def todo_item_expires_at(item: dict[str, Any]) -> datetime | None:
    return monitor_todo_expires_at(item)


def todo_item_is_expired_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    return monitor_todo_is_expired(item, now=now)


def todo_item_is_due_monitor(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
    task_text_keys: tuple[str, ...] = ("title", "text"),
) -> bool:
    return monitor_todo_is_due(
        item,
        now=now,
        task_text=todo_item_task_text(item, keys=task_text_keys),
    )
