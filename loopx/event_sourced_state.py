from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .file_lock import exclusive_file_lock
from .todo_contract import (
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    build_todo_id,
    format_todo_metadata_line,
    normalize_explicit_todo_task_class,
    normalize_todo_action_kind,
    normalize_todo_claimed_by,
    normalize_todo_id,
    normalize_todo_status,
    todo_done_for_status,
    todo_marker_for_status,
)


STATE_EVENT_SCHEMA_VERSION = "loopx_state_event_v0"
STATE_PROJECTION_SCHEMA_VERSION = "event_sourced_state_projection_v0"
STATE_PROJECTION_VERSION = "event_sourced_state_contract_v0"

PUBLIC_PRIVACY = "public_safe"
LOCAL_PRIVATE_PRIVACY = "local_private"
PRIVATE_POINTER_PRIVACY = "private_pointer"
PRIVACY_VALUES = {PUBLIC_PRIVACY, LOCAL_PRIVATE_PRIVACY, PRIVATE_POINTER_PRIVACY}

TODO_ADDED = "todo_added"
TODO_CLAIMED = "todo_claimed"
TODO_UPDATED = "todo_updated"
TODO_BLOCKED = "todo_blocked"
TODO_DEFERRED = "todo_deferred"
TODO_COMPLETED = "todo_completed"
REFRESH_RECORDED = "refresh_recorded"
RUN_RECORDED = "run_recorded"
QUOTA_SPENT = "quota_spent"
EVIDENCE_ATTACHED = "evidence_attached"

SUPPORTED_EVENT_TYPES = {
    TODO_ADDED,
    TODO_CLAIMED,
    TODO_UPDATED,
    TODO_BLOCKED,
    TODO_DEFERRED,
    TODO_COMPLETED,
    REFRESH_RECORDED,
    RUN_RECORDED,
    QUOTA_SPENT,
    EVIDENCE_ATTACHED,
}

TODO_EVENT_TYPES = {
    TODO_ADDED,
    TODO_CLAIMED,
    TODO_UPDATED,
    TODO_BLOCKED,
    TODO_DEFERRED,
    TODO_COMPLETED,
}


class StateEventError(ValueError):
    """Raised when a state event cannot be accepted or replayed."""


class StateEventConflictError(StateEventError):
    """Raised when a duplicate event id carries different event content."""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _sorted_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in sorted(value)}


def event_fingerprint(event: dict[str, Any]) -> str:
    comparable = {key: value for key, value in event.items() if key != "append_sequence"}
    return json.dumps(comparable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_stream_checksum(events: Iterable[dict[str, Any]]) -> str:
    body = "\n".join(
        json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for event in events
    )
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise StateEventError(f"{field_name} must be an object")
    return dict(value)


def normalize_state_event(event: dict[str, Any], *, append_sequence: int | None = None) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise StateEventError("event must be an object")

    event_id = compact_text(event.get("event_id"))
    goal_id = compact_text(event.get("goal_id"))
    event_type = compact_text(event.get("event_type"))
    if not event_id:
        raise StateEventError("event_id is required")
    if not goal_id:
        raise StateEventError("goal_id is required")
    if event_type not in SUPPORTED_EVENT_TYPES:
        raise StateEventError(f"unsupported event_type: {event_type}")

    refs = _require_dict(event.get("refs"), field_name="refs")
    if refs.get("mutates_prior_event_id"):
        raise StateEventError("events must not mutate prior events")
    payload = _require_dict(event.get("payload"), field_name="payload")

    if event_type in TODO_EVENT_TYPES:
        todo_id = normalize_todo_id(refs.get("todo_id"))
        if not todo_id:
            raise StateEventError(f"{event_type} requires refs.todo_id")
        refs["todo_id"] = todo_id

    privacy = compact_text(event.get("privacy") or PUBLIC_PRIVACY)
    if privacy not in PRIVACY_VALUES:
        raise StateEventError(f"privacy must be one of: {', '.join(sorted(PRIVACY_VALUES))}")

    sequence = append_sequence if append_sequence is not None else event.get("append_sequence")
    if sequence is not None:
        try:
            sequence = int(sequence)
        except (TypeError, ValueError) as exc:
            raise StateEventError("append_sequence must be an integer") from exc
        if sequence < 1:
            raise StateEventError("append_sequence must be positive")

    normalized = {
        "schema_version": compact_text(event.get("schema_version") or STATE_EVENT_SCHEMA_VERSION),
        "event_id": event_id,
        "goal_id": goal_id,
        "event_type": event_type,
        "recorded_at": compact_text(event.get("recorded_at") or now_utc_iso()),
        "producer": compact_text(event.get("producer") or "loopx.event_sourced_state"),
        "privacy": privacy,
        "projection_version": compact_text(event.get("projection_version") or STATE_PROJECTION_VERSION),
        "refs": _sorted_dict(refs),
        "payload": _sorted_dict(payload),
    }
    if normalized["schema_version"] != STATE_EVENT_SCHEMA_VERSION:
        raise StateEventError(f"schema_version must be {STATE_EVENT_SCHEMA_VERSION}")
    if sequence is not None:
        normalized["append_sequence"] = sequence
    return normalized


def make_state_event(
    *,
    event_id: str,
    goal_id: str,
    event_type: str,
    refs: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    recorded_at: str | None = None,
    producer: str | None = None,
    privacy: str = PUBLIC_PRIVACY,
    projection_version: str = STATE_PROJECTION_VERSION,
) -> dict[str, Any]:
    return normalize_state_event(
        {
            "schema_version": STATE_EVENT_SCHEMA_VERSION,
            "event_id": event_id,
            "goal_id": goal_id,
            "event_type": event_type,
            "recorded_at": recorded_at or now_utc_iso(),
            "producer": producer or "loopx.event_sourced_state",
            "privacy": privacy,
            "projection_version": projection_version,
            "refs": refs or {},
            "payload": payload or {},
        }
    )


@dataclass
class AppendOnlyStateEventStore:
    path: Path
    _events: list[dict[str, Any]] = field(default_factory=list)
    _loaded: bool = False

    def load(self) -> list[dict[str, Any]]:
        if self._loaded:
            return list(self._events)
        events: list[dict[str, Any]] = []
        if self.path.exists():
            for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise StateEventError(f"invalid JSONL at line {line_number}: {exc}") from exc
                events.append(normalize_state_event(raw))
        self._events = _dedupe_events(events)
        self._loaded = True
        return list(self._events)

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        with exclusive_file_lock(self.path):
            self._loaded = False
            events = self.load()
            existing = {item["event_id"]: item for item in events}
            next_sequence = max((int(item["append_sequence"]) for item in events), default=0) + 1
            normalized = normalize_state_event(event, append_sequence=next_sequence)
            prior = existing.get(normalized["event_id"])
            if prior is not None:
                if event_fingerprint(prior) != event_fingerprint(normalized):
                    raise StateEventConflictError(f"conflicting event_id: {normalized['event_id']}")
                return prior

            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(normalized, sort_keys=True, ensure_ascii=False) + "\n")
            self._events.append(normalized)
            return normalized

    def append_many(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.append(event) for event in events]


def _dedupe_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for event in events:
        prior = by_id.get(event["event_id"])
        if prior is not None:
            if event_fingerprint(prior) != event_fingerprint(event):
                raise StateEventConflictError(f"conflicting event_id: {event['event_id']}")
            continue
        by_id[event["event_id"]] = event
        ordered.append(event)
    return ordered


def event_sort_key(event: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(event.get("append_sequence") or 0),
        str(event.get("recorded_at") or ""),
        str(event.get("event_id") or ""),
    )


def _todo_from_added_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    refs = event.get("refs") or {}
    text = compact_text(payload.get("text") or payload.get("title"))
    role = compact_text(payload.get("role") or "agent")
    source_section = (
        "User Todo / Owner Review Reading Queue" if role == "user" else "Agent Todo"
    )
    todo_id = normalize_todo_id(refs.get("todo_id")) or build_todo_id(
        role=role,
        source_section=source_section,
        index=event.get("append_sequence"),
        text=text,
    )
    task_class = normalize_explicit_todo_task_class(payload.get("task_class"))
    action_kind = normalize_todo_action_kind(payload.get("action_kind"))
    claimed_by = normalize_todo_claimed_by(payload.get("claimed_by"))
    todo: dict[str, Any] = {
        "schema_version": "todo_item_v0",
        "todo_id": todo_id,
        "role": role,
        "status": TODO_STATUS_OPEN,
        "done": False,
        "priority": compact_text(payload.get("priority") or "P2"),
        "title": text,
        "text": text if not payload.get("priority") else f"[{compact_text(payload.get('priority'))}] {text}",
        "source_section": source_section,
        "planner_order": payload.get("planner_order"),
        "append_sequence": event.get("append_sequence"),
        "last_event_id": event.get("event_id"),
    }
    if task_class:
        todo["task_class"] = task_class
    if action_kind:
        todo["action_kind"] = action_kind
    if claimed_by:
        todo["claimed_by"] = claimed_by
    return todo


def _update_todo_from_event(todo: dict[str, Any], event: dict[str, Any]) -> None:
    payload = event.get("payload") or {}
    event_type = event.get("event_type")
    if event_type == TODO_CLAIMED:
        claimed_by = normalize_todo_claimed_by(payload.get("claimed_by"))
        if claimed_by:
            todo["claimed_by"] = claimed_by
    elif event_type == TODO_UPDATED:
        for key in ("priority", "role", "title", "task_class", "action_kind"):
            if payload.get(key):
                todo[key] = compact_text(payload[key])
        if payload.get("text") or payload.get("title"):
            title = compact_text(payload.get("text") or payload.get("title"))
            todo["title"] = title
            priority = compact_text(todo.get("priority") or "")
            todo["text"] = f"[{priority}] {title}" if priority else title
    elif event_type == TODO_BLOCKED:
        todo["status"] = "blocked"
        todo["done"] = False
        if payload.get("reason"):
            todo["reason"] = compact_text(payload["reason"])
    elif event_type == TODO_DEFERRED:
        todo["status"] = "deferred"
        todo["done"] = False
        if payload.get("reason"):
            todo["reason"] = compact_text(payload["reason"])
        if payload.get("resume_when"):
            todo["resume_when"] = compact_text(payload["resume_when"])
    elif event_type == TODO_COMPLETED:
        todo["status"] = TODO_STATUS_DONE
        todo["done"] = True
        if payload.get("evidence"):
            todo["evidence"] = compact_text(payload["evidence"])
        if payload.get("reason"):
            todo["reason"] = compact_text(payload["reason"])
    todo["last_event_id"] = event.get("event_id")
    todo["last_append_sequence"] = event.get("append_sequence")


def build_state_projection(
    events: Iterable[dict[str, Any]],
    *,
    goal_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    normalized = _dedupe_events(normalize_state_event(event) for event in events)
    ordered = sorted(normalized, key=event_sort_key)
    inferred_goal_id = goal_id or (ordered[0]["goal_id"] if ordered else "")
    todos: dict[str, dict[str, Any]] = {}
    timeline: list[dict[str, Any]] = []

    for event in ordered:
        if inferred_goal_id and event["goal_id"] != inferred_goal_id:
            raise StateEventError("all events in a projection must share one goal_id")
        event_type = event["event_type"]
        todo_id = (event.get("refs") or {}).get("todo_id")
        if event_type == TODO_ADDED:
            todo = _todo_from_added_event(event)
            todos[todo["todo_id"]] = todo
        elif event_type in TODO_EVENT_TYPES and todo_id:
            todo = todos.get(todo_id)
            if todo is None:
                raise StateEventError(f"{event_type} references unknown todo_id: {todo_id}")
            _update_todo_from_event(todo, event)
        elif event_type in {REFRESH_RECORDED, RUN_RECORDED, QUOTA_SPENT, EVIDENCE_ATTACHED}:
            timeline.append(
                {
                    "event_id": event["event_id"],
                    "event_type": event_type,
                    "append_sequence": event.get("append_sequence"),
                    "recorded_at": event.get("recorded_at"),
                    "summary": compact_text((event.get("payload") or {}).get("summary")),
                    "refs": event.get("refs") or {},
                }
            )

    todo_items = sorted(
        todos.values(),
        key=lambda item: (
            item.get("role") != "user",
            str(item.get("priority") or "P9"),
            int(item.get("planner_order") or 9999),
            int(item.get("append_sequence") or 0),
        ),
    )
    user_todos = [item for item in todo_items if item.get("role") == "user"]
    agent_todos = [item for item in todo_items if item.get("role") != "user"]
    last_event = ordered[-1] if ordered else {}
    return {
        "schema_version": STATE_PROJECTION_SCHEMA_VERSION,
        "goal_id": inferred_goal_id,
        "generated_at": generated_at or now_utc_iso(),
        "source_event_count": len(ordered),
        "source_checksum": event_stream_checksum(ordered),
        "last_event_id": last_event.get("event_id"),
        "last_append_sequence": last_event.get("append_sequence"),
        "projection_version": STATE_PROJECTION_VERSION,
        "user_todos": _todo_summary(user_todos, role="user"),
        "agent_todos": _todo_summary(agent_todos, role="agent"),
        "timeline": timeline,
    }


def _todo_summary(items: list[dict[str, Any]], *, role: str) -> dict[str, Any]:
    open_items = [item for item in items if not todo_done_for_status(item.get("status"))]
    done_items = [item for item in items if todo_done_for_status(item.get("status"))]
    return {
        "schema_version": "todo_summary_v0",
        "role": role,
        "total_count": len(items),
        "open_count": len(open_items),
        "done_count": len(done_items),
        "items": items,
        "first_open_items": open_items[:5],
    }


def render_todo_markdown(item: dict[str, Any]) -> list[str]:
    status = normalize_todo_status(item.get("status")) or TODO_STATUS_OPEN
    marker = todo_marker_for_status(status)
    text = compact_text(item.get("text") or item.get("title"))
    if not text.startswith("[") and item.get("priority"):
        text = f"[{compact_text(item.get('priority'))}] {text}"
    lines = [f"- [{marker}] {text}"]
    metadata = format_todo_metadata_line(
        todo_id=item.get("todo_id"),
        status=status,
        task_class=item.get("task_class"),
        action_kind=item.get("action_kind"),
        claimed_by=item.get("claimed_by"),
        note=item.get("note"),
        evidence=item.get("evidence"),
        reason=item.get("reason"),
        updated_at=item.get("updated_at"),
    )
    if metadata:
        lines.append(metadata)
    return lines


def render_active_state_sections(projection: dict[str, Any]) -> str:
    lines: list[str] = []
    for heading, summary_key in (
        ("User Todo / Owner Review Reading Queue", "user_todos"),
        ("Agent Todo", "agent_todos"),
    ):
        items = ((projection.get(summary_key) or {}).get("items") or [])
        if not items:
            continue
        if lines:
            lines.append("")
        lines.extend([f"## {heading}", ""])
        for item in items:
            lines.extend(render_todo_markdown(item))

    timeline = projection.get("timeline") or []
    if timeline:
        if lines:
            lines.append("")
        lines.extend(["## Progress Ledger", ""])
        for event in timeline:
            event_type = compact_text(event.get("event_type"))
            summary = compact_text(event.get("summary")) or "event recorded"
            lines.append(f"- {event_type}: {summary}")
    return "\n".join(lines).rstrip() + "\n"
