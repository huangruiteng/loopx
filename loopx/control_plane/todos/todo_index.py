from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ...rollout_event_log import load_rollout_events, rollout_event_log_path
from .contract import normalize_todo_id, normalize_todo_status, todo_done_for_status
from .handoff_note import attach_todo_handoff_note
from .todo_summary import compact_todo_item


TODO_INDEX_SCHEMA_VERSION = "todo_index_v0"
TODO_INDEX_ITEM_SCHEMA_VERSION = "todo_index_item_v0"
MAX_TODO_INDEX_ITEMS = 240
MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL = 500

CompactText = Callable[..., Any]


def _todo_index_key(goal_id: str, todo: dict[str, Any]) -> tuple[str, str]:
    todo_id = normalize_todo_id(todo.get("todo_id")) or ""
    if todo_id:
        return goal_id, todo_id
    return goal_id, f"synthetic:{todo.get('role') or ''}:{todo.get('index') or ''}:{todo.get('text') or ''}"


def _indexed_status_todo(
    *,
    goal_id: str,
    role: str,
    todo: dict[str, Any],
    source: str,
    public_safe_compact_text: CompactText,
) -> dict[str, Any] | None:
    text = public_safe_compact_text(todo.get("title") or todo.get("text"), limit=320)
    if not text:
        return None
    item = compact_todo_item(todo)
    item.update(
        {
            "schema_version": TODO_INDEX_ITEM_SCHEMA_VERSION,
            "goal_id": goal_id,
            "role": role,
            "source": source,
            "text": text,
            "title": public_safe_compact_text(todo.get("title"), limit=320) or text,
        }
    )
    attach_todo_handoff_note(item, goal_id=goal_id, source=source)
    return item


def _rollout_event_todo_status(event: dict[str, Any]) -> str:
    status = normalize_todo_status(event.get("status"))
    if status:
        return status
    kind = str(event.get("event_kind") or "")
    if kind in {"todo_complete", "todo_archive_completed"}:
        return "done"
    if kind == "todo_supersede":
        return "deferred"
    return "open"


def _indexed_rollout_todo_event(
    event: dict[str, Any],
    *,
    public_safe_compact_text: CompactText,
) -> dict[str, Any] | None:
    todo_id = normalize_todo_id(event.get("todo_id"))
    goal_id = str(event.get("goal_id") or "").strip()
    if not goal_id or not todo_id:
        return None
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    role = str(details.get("role") or "agent").strip().lower()
    if role not in {"user", "agent"}:
        role = "agent"
    status = _rollout_event_todo_status(event)
    summary = public_safe_compact_text(
        event.get("summary") or f"{event.get('event_kind') or 'todo_event'} recorded for {todo_id}",
        limit=320,
    )
    if not summary:
        summary = f"todo event recorded for {todo_id}"
    item = {
        "schema_version": TODO_INDEX_ITEM_SCHEMA_VERSION,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "role": role,
        "status": status,
        "done": todo_done_for_status(status),
        "index": 0,
        "text": summary,
        "title": summary,
        "source": "rollout_event_log",
        "event_count": 1,
        "event_kinds": [str(event.get("event_kind") or "todo_event")],
        "latest_event_kind": str(event.get("event_kind") or "todo_event"),
        "latest_event_at": public_safe_compact_text(event.get("recorded_at"), limit=80),
        "latest_event_status": status,
        "agent_id": public_safe_compact_text(event.get("agent_id"), limit=120),
    }
    handoff = event.get("handoff") or details.get("handoff")
    if isinstance(handoff, dict):
        item["handoff"] = handoff
    attach_todo_handoff_note(item, goal_id=goal_id, source="rollout_event_log")
    return item


def build_todo_index(
    *,
    queue: dict[str, Any],
    history: dict[str, Any],
    runtime_root: Path,
    public_safe_compact_text: CompactText,
    limit: int = MAX_TODO_INDEX_ITEMS,
    max_rollout_events_per_goal: int = MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL,
) -> dict[str, Any]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    current_count = 0
    for item in queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "")
        if not goal_id:
            continue
        for role in ("user", "agent"):
            todos = item.get(f"{role}_todos")
            if not isinstance(todos, dict):
                continue
            for todo in todos.get("items") or []:
                if not isinstance(todo, dict):
                    continue
                indexed_item = _indexed_status_todo(
                    goal_id=goal_id,
                    role=role,
                    todo=todo,
                    source="attention_queue",
                    public_safe_compact_text=public_safe_compact_text,
                )
                if indexed_item is None:
                    continue
                indexed[_todo_index_key(goal_id, indexed_item)] = indexed_item
                current_count += 1

    rollout_event_count = 0
    goal_ids = [
        str(goal.get("id") or "")
        for goal in history.get("goals") or []
        if isinstance(goal, dict) and str(goal.get("id") or "")
    ]
    for goal_id in sorted(set(goal_ids)):
        events = load_rollout_events(
            rollout_event_log_path(runtime_root, goal_id),
            limit=max_rollout_events_per_goal,
        )
        for event in events:
            if not isinstance(event, dict) or not str(event.get("event_kind") or "").startswith("todo_"):
                continue
            rollout_event_count += 1
            event_item = _indexed_rollout_todo_event(
                event,
                public_safe_compact_text=public_safe_compact_text,
            )
            if event_item is None:
                continue
            key = _todo_index_key(goal_id, event_item)
            existing = indexed.get(key)
            if existing:
                existing["event_count"] = int(existing.get("event_count") or 0) + 1
                kinds = list(existing.get("event_kinds") or [])
                latest_kind = event_item.get("latest_event_kind")
                if latest_kind and latest_kind not in kinds:
                    kinds.append(latest_kind)
                existing["event_kinds"] = kinds
                existing["latest_event_kind"] = latest_kind
                existing["latest_event_at"] = event_item.get("latest_event_at")
                existing["latest_event_status"] = event_item.get("latest_event_status")
                if event_item.get("status"):
                    existing["status"] = event_item.get("status")
                    existing["done"] = bool(event_item.get("done"))
                if event_item.get("agent_id"):
                    existing["agent_id"] = event_item.get("agent_id")
                continue
            indexed[key] = event_item

    items = sorted(
        indexed.values(),
        key=lambda item: (
            0 if not item.get("done") else 1,
            str(item.get("goal_id") or ""),
            str(item.get("todo_id") or ""),
            str(item.get("latest_event_at") or ""),
        ),
    )
    return {
        "schema_version": TODO_INDEX_SCHEMA_VERSION,
        "source": "attention_queue_and_rollout_event_log",
        "total_count": len(items),
        "current_projected_count": current_count,
        "rollout_event_count": rollout_event_count,
        "item_limit": limit,
        "items": items[: max(0, limit)],
    }
