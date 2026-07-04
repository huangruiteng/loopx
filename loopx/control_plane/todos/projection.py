from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from ..scheduler.monitor_todo import (
    monitor_todo_expires_at,
    monitor_todo_has_schedule,
    monitor_todo_is_actionable_open,
    monitor_todo_is_due,
    monitor_todo_is_expired,
    monitor_todo_missing_schedule,
    monitor_todo_next_due_at,
    monitor_todo_task_class,
)
from ...todo_contract import (
    TODO_STATUS_DEFERRED,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_claimed_by,
    normalize_todo_id,
    normalize_todo_status,
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


def todo_claimed_visibility_items(
    items: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0 or len(items) <= limit:
        return items[:limit]
    claim_order: list[str] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if not claimed_by:
            continue
        if claimed_by not in buckets:
            buckets[claimed_by] = []
            claim_order.append(claimed_by)
        buckets[claimed_by].append(item)
    if not buckets:
        return items[:limit]

    original_index = {id(item): index for index, item in enumerate(items)}
    per_claimant_cap = max(1, limit // len(buckets))
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for claimed_by in claim_order:
        taken = 0
        for item in buckets[claimed_by]:
            if taken >= per_claimant_cap:
                break
            if len(selected) >= limit:
                break
            selected.append(item)
            selected_ids.add(id(item))
            taken += 1
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for item in items:
            if id(item) in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(id(item))
            if len(selected) >= limit:
                break

    return sorted(selected, key=lambda item: original_index.get(id(item), TODO_MISSING_INDEX))[
        :limit
    ]


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


def todo_item_is_deferred(item: dict[str, Any]) -> bool:
    return (normalize_todo_status(item.get("status")) or "") == TODO_STATUS_DEFERRED


def todo_item_next_due_at(item: dict[str, Any]) -> datetime | None:
    return monitor_todo_next_due_at(item)


def todo_item_has_monitor_schedule(item: dict[str, Any]) -> bool:
    return monitor_todo_has_schedule(item)


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


def todo_item_missing_monitor_schedule(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
    task_text_keys: tuple[str, ...] = ("title", "text"),
) -> bool:
    return monitor_todo_missing_schedule(
        item,
        now=now,
        task_text=todo_item_task_text(item, keys=task_text_keys),
    )


def todo_item_claimed_by_agent_or_unclaimed(
    item: dict[str, Any],
    *,
    agent_id: str | None,
) -> bool:
    normalized_agent_id = normalize_todo_claimed_by(agent_id)
    if not normalized_agent_id:
        return True
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    return not claimed_by or claimed_by == normalized_agent_id


def todo_summary_claim_scope_agent_id(summary: dict[str, Any] | None) -> str | None:
    if not isinstance(summary, dict):
        return None
    claim_scope = summary.get("claim_scope")
    if not isinstance(claim_scope, dict):
        return None
    return normalize_todo_claimed_by(claim_scope.get("agent_id"))


def todo_summary_monitor_writeback_contract(
    summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(summary, dict):
        return None
    contract = summary.get("monitor_writeback")
    if not isinstance(contract, dict):
        return None
    if contract.get("supported") is not False:
        return None
    compact: dict[str, Any] = {"supported": False}
    source = str(contract.get("source") or "").strip()
    if source:
        compact["source"] = source
    return compact


def todo_summary_monitor_writeback_supported(summary: dict[str, Any] | None) -> bool:
    contract = todo_summary_monitor_writeback_contract(summary)
    if not contract:
        return True
    return contract.get("supported") is not False


def todo_summary_monitor_items(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for key in (
        "monitor_due_items",
        "current_agent_claimed_monitor_items",
        "monitor_open_items",
        "claimed_monitor_open_items",
        "first_open_items",
    ):
        values = summary.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            if not todo_item_is_actionable_open(value):
                continue
            if todo_item_task_class(value) != TODO_TASK_CLASS_MONITOR:
                continue
            identity = (normalize_todo_id(value.get("todo_id")) or "", id(value))
            if identity in seen:
                continue
            seen.add(identity)
            items.append(value)
    return items


def _summary_monitor_items(
    summary: dict[str, Any] | None,
    *,
    projected_key: str,
    predicate: Any,
    task_text_keys: tuple[str, ...],
    text_mode: str,
) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    if not todo_summary_monitor_writeback_supported(summary):
        return []
    projected_items = summary.get(projected_key)
    if isinstance(projected_items, list):
        items = [
            item
            for item in projected_items
            if isinstance(item, dict)
            if todo_item_is_actionable_open(item)
            if todo_item_task_class(item, task_text_keys=task_text_keys)
            == TODO_TASK_CLASS_MONITOR
            if predicate(item)
        ]
    else:
        raw_items = summary.get("monitor_open_items")
        items = [
            item
            for item in (raw_items if isinstance(raw_items, list) else [])
            if isinstance(item, dict)
            if predicate(item)
        ]
    agent_id = todo_summary_claim_scope_agent_id(summary)
    if agent_id:
        items = [
            item
            for item in items
            if todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
        ]
    return sorted(
        items,
        key=lambda item: todo_projection_sort_key(item, text_mode=text_mode),
    )


def todo_summary_monitor_due_items(
    summary: dict[str, Any] | None,
    *,
    task_text_keys: tuple[str, ...] = ("title", "text"),
    text_mode: str = "label",
) -> list[dict[str, Any]]:
    return _summary_monitor_items(
        summary,
        projected_key="monitor_due_items",
        predicate=lambda item: todo_item_is_due_monitor(
            item,
            task_text_keys=task_text_keys,
        ),
        task_text_keys=task_text_keys,
        text_mode=text_mode,
    )


def todo_summary_monitor_due_count(
    summary: dict[str, Any] | None,
    *,
    due_items: list[dict[str, Any]] | None = None,
    task_text_keys: tuple[str, ...] = ("title", "text"),
    text_mode: str = "label",
) -> int:
    if not isinstance(summary, dict):
        return 0
    if not todo_summary_monitor_writeback_supported(summary):
        return 0
    agent_id = todo_summary_claim_scope_agent_id(summary)
    if agent_id:
        raw_items = summary.get("monitor_open_items")
        if isinstance(raw_items, list):
            return len(
                [
                    item
                    for item in raw_items
                    if isinstance(item, dict)
                    if todo_item_is_due_monitor(item, task_text_keys=task_text_keys)
                    if todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
                ]
            )
        return len(
            due_items
            if due_items is not None
            else todo_summary_monitor_due_items(
                summary,
                task_text_keys=task_text_keys,
                text_mode=text_mode,
            )
        )
    projected_count = summary.get("monitor_due_count")
    if isinstance(projected_count, int):
        return max(0, projected_count)
    return len(
        due_items
        if due_items is not None
        else todo_summary_monitor_due_items(
            summary,
            task_text_keys=task_text_keys,
            text_mode=text_mode,
        )
    )


def todo_summary_monitor_schedule_gap_items(
    summary: dict[str, Any] | None,
    *,
    task_text_keys: tuple[str, ...] = ("title", "text"),
    text_mode: str = "label",
) -> list[dict[str, Any]]:
    return _summary_monitor_items(
        summary,
        projected_key="monitor_schedule_gap_items",
        predicate=lambda item: todo_item_missing_monitor_schedule(
            item,
            task_text_keys=task_text_keys,
        ),
        task_text_keys=task_text_keys,
        text_mode=text_mode,
    )


def todo_summary_monitor_schedule_gap_count(
    summary: dict[str, Any] | None,
    *,
    gap_items: list[dict[str, Any]] | None = None,
    task_text_keys: tuple[str, ...] = ("title", "text"),
    text_mode: str = "label",
) -> int:
    if not isinstance(summary, dict):
        return 0
    if not todo_summary_monitor_writeback_supported(summary):
        return 0
    agent_id = todo_summary_claim_scope_agent_id(summary)
    if agent_id:
        raw_items = summary.get("monitor_open_items")
        if isinstance(raw_items, list):
            return len(
                [
                    item
                    for item in raw_items
                    if isinstance(item, dict)
                    if todo_item_missing_monitor_schedule(
                        item,
                        task_text_keys=task_text_keys,
                    )
                    if todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
                ]
            )
        return len(
            gap_items
            if gap_items is not None
            else todo_summary_monitor_schedule_gap_items(
                summary,
                task_text_keys=task_text_keys,
                text_mode=text_mode,
            )
        )
    projected_count = summary.get("monitor_schedule_gap_count")
    if isinstance(projected_count, int):
        return max(0, projected_count)
    return len(
        gap_items
        if gap_items is not None
        else todo_summary_monitor_schedule_gap_items(
            summary,
            task_text_keys=task_text_keys,
            text_mode=text_mode,
        )
    )


def todo_summary_first_executable_item(
    summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(summary, dict):
        return None
    items = (
        summary.get("first_executable_items")
        if isinstance(summary.get("first_executable_items"), list)
        else []
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        if not todo_item_is_actionable_open(item):
            continue
        if todo_item_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        return item
    return None
