from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .control_plane.runtime.time import now_utc_iso as runtime_now_utc_iso
from .file_lock import exclusive_file_lock
from .control_plane.todos.contract import (
    TODO_MONITOR_METADATA_FIELDS,
    TODO_STATUS_DONE,
    TODO_STATUS_BLOCKED,
    TODO_STATUS_DEFERRED,
    TODO_STATUS_OPEN,
    TODO_TASK_PATTERN,
    build_todo_id,
    format_todo_metadata_line,
    normalize_explicit_todo_task_class,
    normalize_required_write_scopes,
    normalize_removed_todo_continuation_policy,
    normalize_todo_action_kind,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_continuation_policy,
    normalize_todo_excluded_agents,
    normalize_todo_global_gate,
    normalize_todo_goal_bound,
    normalize_todo_id,
    normalize_todo_id_list,
    normalize_todo_status,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_marker_for_status,
    todo_status_from_marker,
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
SUPERVISOR_PROPOSED = "supervisor_proposed"
SUPERVISOR_RECEIPT_RECORDED = "supervisor_receipt_recorded"

MARKDOWN_BACKFILL_PRODUCER = "loopx.backfill"
MARKDOWN_HEADING_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
TODO_PRIORITY_PREFIX_PATTERN = re.compile(r"^\[(P[0-4])\]\s+(.+)$", re.IGNORECASE)
PUBLIC_BACKFILL_REDACTION = "[redacted-private-state]"
PUBLIC_BACKFILL_UNSAFE_PATTERNS = (
    re.compile(r"(?i)(?:^|[\s`'\"])(?:/Users/|/private/|/var/folders/)"),
    re.compile(r"(?i)\b(?:secret|password|credential|token)\b"),
    re.compile(r"https?://"),
)

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
    SUPERVISOR_PROPOSED,
    SUPERVISOR_RECEIPT_RECORDED,
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
    return runtime_now_utc_iso()


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _redact_public_backfill_text(value: Any, *, privacy: str) -> str:
    text = compact_text(value)
    if privacy != PUBLIC_PRIVACY:
        return text
    if any(pattern.search(text) for pattern in PUBLIC_BACKFILL_UNSAFE_PATTERNS):
        return PUBLIC_BACKFILL_REDACTION
    return text


def _redact_public_backfill_source_ref(value: Any, *, privacy: str) -> str:
    text = compact_text(value) or "ACTIVE_GOAL_STATE.md"
    if privacy != PUBLIC_PRIVACY:
        return text
    if any(pattern.search(text) for pattern in PUBLIC_BACKFILL_UNSAFE_PATTERNS):
        return "ACTIVE_GOAL_STATE.md"
    return text


def _role_for_markdown_heading(heading: str) -> str | None:
    normalized = compact_text(heading).lower()
    if normalized.startswith("user todo") or "owner review" in normalized:
        return "user"
    if normalized.startswith("agent todo"):
        return "agent"
    return None


def _todo_priority_and_title(text: Any, *, privacy: str) -> tuple[str, str]:
    compact = compact_text(text)
    match = TODO_PRIORITY_PREFIX_PATTERN.match(compact)
    if match:
        return match.group(1).upper(), _redact_public_backfill_text(match.group(2), privacy=privacy)
    return "P2", _redact_public_backfill_text(compact, privacy=privacy)


def _backfill_event_id(*, goal_id: str, todo_id: str, suffix: str) -> str:
    digest = hashlib.sha1(f"{goal_id}|{todo_id}|{suffix}".encode("utf-8")).hexdigest()[:16]
    return f"backfill-{suffix}-{digest}"


def _backfill_source_refs(
    *,
    source_ref: str,
    source_section: str,
    source_line: int | None,
    privacy: str,
) -> dict[str, Any]:
    refs: dict[str, Any] = {
        "source_ref": _redact_public_backfill_source_ref(source_ref, privacy=privacy),
        "source_section": compact_text(source_section),
    }
    if source_line is not None:
        refs["source_line"] = source_line
    return refs


def _markdown_todo_records(state_text: str) -> list[dict[str, Any]]:
    role: str | None = None
    source_section: str | None = None
    current: dict[str, Any] | None = None
    records: list[dict[str, Any]] = []
    role_indexes = {"user": 0, "agent": 0}

    for line_number, line in enumerate(state_text.splitlines(), start=1):
        heading_match = MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            source_section = compact_text(heading_match.group(1))
            role = _role_for_markdown_heading(source_section)
            current = None
            continue
        if role is None or source_section is None:
            continue
        todo_match = TODO_TASK_PATTERN.match(line)
        if todo_match:
            marker, text = todo_match.groups()
            role_indexes[role] += 1
            current = {
                "role": role,
                "source_section": source_section,
                "source_line": line_number,
                "planner_order": role_indexes[role],
                "status": todo_status_from_marker(marker),
                "text": compact_text(text),
            }
            records.append(current)
            continue
        if current is None or not line.startswith((" ", "\t")):
            continue
        metadata = parse_todo_metadata_line(line)
        if metadata:
            current.update(metadata)
            continue
        continuation = compact_text(line)
        if continuation:
            current["text"] = compact_text(f"{current.get('text', '')} {continuation}")
    for record in records:
        role = str(record.get("role") or "agent")
        source_section = str(record.get("source_section") or "")
        title_text = compact_text(record.get("text"))
        if not normalize_todo_id(record.get("todo_id")):
            record["todo_id"] = build_todo_id(
                role=role,
                source_section=source_section,
                index=record.get("planner_order"),
                text=title_text,
            )
        record["status"] = normalize_todo_status(record.get("status")) or TODO_STATUS_OPEN
    return records


def backfill_todo_events_from_markdown(
    state_text: str,
    *,
    goal_id: str,
    source_ref: str = "ACTIVE_GOAL_STATE.md",
    recorded_at: str | None = None,
    producer: str = MARKDOWN_BACKFILL_PRODUCER,
    privacy: str = LOCAL_PRIVATE_PRIVACY,
) -> list[dict[str, Any]]:
    """Convert Markdown workbench todos into idempotent append-only events.

    The helper does not mutate the Markdown source. When writing a public-safe
    stream, compact todo titles/evidence/reasons that look like private state
    are redacted; local-private streams preserve the workbench text.
    """
    normalized_goal_id = compact_text(goal_id)
    if not normalized_goal_id:
        raise StateEventError("goal_id is required")
    if privacy not in PRIVACY_VALUES:
        raise StateEventError(f"privacy must be one of: {', '.join(sorted(PRIVACY_VALUES))}")

    events: list[dict[str, Any]] = []
    for record in _markdown_todo_records(state_text):
        role = str(record.get("role") or "agent")
        todo_id = normalize_todo_id(record.get("todo_id")) or build_todo_id(
            role=role,
            source_section=record.get("source_section"),
            index=record.get("planner_order"),
            text=record.get("text"),
        )
        priority, title = _todo_priority_and_title(record.get("text"), privacy=privacy)
        refs = {
            "todo_id": todo_id,
            **_backfill_source_refs(
                source_ref=source_ref,
                source_section=str(record.get("source_section") or ""),
                source_line=record.get("source_line"),
                privacy=privacy,
            ),
        }
        payload: dict[str, Any] = {
            "role": role,
            "priority": priority,
            "title": title,
            "planner_order": record.get("planner_order"),
        }
        task_class = normalize_explicit_todo_task_class(record.get("task_class"))
        action_kind = normalize_todo_action_kind(record.get("action_kind"))
        continuation_policy = normalize_todo_continuation_policy(
            record.get("continuation_policy")
        )
        removed_continuation_policy = normalize_removed_todo_continuation_policy(
            record.get("removed_continuation_policy")
        )
        required_write_scopes = normalize_required_write_scopes(
            record.get("required_write_scopes")
        )
        blocks_agent = normalize_todo_blocks_agent(record.get("blocks_agent"))
        bound_agent = normalize_todo_bound_agent(record.get("bound_agent"))
        goal_bound = normalize_todo_goal_bound(record.get("goal_bound"))
        global_gate = normalize_todo_global_gate(record.get("global_gate"))
        excluded_agents = normalize_todo_excluded_agents(record.get("excluded_agents"))
        if task_class:
            payload["task_class"] = task_class
        if action_kind:
            payload["action_kind"] = action_kind
        if continuation_policy:
            payload["continuation_policy"] = continuation_policy
        if removed_continuation_policy:
            payload["removed_continuation_policy"] = removed_continuation_policy
        if required_write_scopes:
            payload["required_write_scopes"] = required_write_scopes
        if blocks_agent:
            payload["blocks_agent"] = blocks_agent
        if bound_agent:
            payload["bound_agent"] = bound_agent
        if goal_bound is not None:
            payload["goal_bound"] = goal_bound
        if global_gate is not None:
            payload["global_gate"] = global_gate
        if excluded_agents:
            payload["excluded_agents"] = excluded_agents
        events.append(
            make_state_event(
                event_id=_backfill_event_id(goal_id=normalized_goal_id, todo_id=todo_id, suffix="add"),
                goal_id=normalized_goal_id,
                event_type=TODO_ADDED,
                refs=refs,
                payload=payload,
                recorded_at=recorded_at,
                producer=producer,
                privacy=privacy,
            )
        )

        claimed_by = normalize_todo_claimed_by(record.get("claimed_by"))
        if claimed_by:
            events.append(
                make_state_event(
                    event_id=_backfill_event_id(goal_id=normalized_goal_id, todo_id=todo_id, suffix="claim"),
                    goal_id=normalized_goal_id,
                    event_type=TODO_CLAIMED,
                    refs=refs,
                    payload={"claimed_by": claimed_by},
                    recorded_at=recorded_at,
                    producer=producer,
                    privacy=privacy,
                )
            )

        status = normalize_todo_status(record.get("status")) or TODO_STATUS_OPEN
        if status == TODO_STATUS_DONE:
            completion_payload: dict[str, Any] = {}
            for key in ("evidence", "reason"):
                if record.get(key):
                    completion_payload[key] = _redact_public_backfill_text(record[key], privacy=privacy)
            events.append(
                make_state_event(
                    event_id=_backfill_event_id(goal_id=normalized_goal_id, todo_id=todo_id, suffix="complete"),
                    goal_id=normalized_goal_id,
                    event_type=TODO_COMPLETED,
                    refs=refs,
                    payload=completion_payload,
                    recorded_at=recorded_at,
                    producer=producer,
                    privacy=privacy,
                )
            )
        elif status == TODO_STATUS_DEFERRED:
            deferred_payload = {}
            for key in ("reason", "resume_when"):
                if record.get(key):
                    deferred_payload[key] = _redact_public_backfill_text(record[key], privacy=privacy)
            events.append(
                make_state_event(
                    event_id=_backfill_event_id(goal_id=normalized_goal_id, todo_id=todo_id, suffix="defer"),
                    goal_id=normalized_goal_id,
                    event_type=TODO_DEFERRED,
                    refs=refs,
                    payload=deferred_payload,
                    recorded_at=recorded_at,
                    producer=producer,
                    privacy=privacy,
                )
            )
        elif status == TODO_STATUS_BLOCKED:
            blocked_payload = {}
            if record.get("reason"):
                blocked_payload["reason"] = _redact_public_backfill_text(record["reason"], privacy=privacy)
            events.append(
                make_state_event(
                    event_id=_backfill_event_id(goal_id=normalized_goal_id, todo_id=todo_id, suffix="block"),
                    goal_id=normalized_goal_id,
                    event_type=TODO_BLOCKED,
                    refs=refs,
                    payload=blocked_payload,
                    recorded_at=recorded_at,
                    producer=producer,
                    privacy=privacy,
                )
            )
    return events


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
    continuation_policy = normalize_todo_continuation_policy(
        payload.get("continuation_policy")
    )
    removed_continuation_policy = normalize_removed_todo_continuation_policy(
        payload.get("removed_continuation_policy")
        or payload.get("continuation_policy")
    )
    required_write_scopes = normalize_required_write_scopes(
        payload.get("required_write_scopes")
    )
    blocks_agent = normalize_todo_blocks_agent(payload.get("blocks_agent"))
    bound_agent = normalize_todo_bound_agent(payload.get("bound_agent"))
    goal_bound = normalize_todo_goal_bound(payload.get("goal_bound"))
    global_gate = normalize_todo_global_gate(payload.get("global_gate"))
    excluded_agents = normalize_todo_excluded_agents(payload.get("excluded_agents"))
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
    if removed_continuation_policy:
        todo["removed_continuation_policy"] = removed_continuation_policy
    elif continuation_policy:
        todo["continuation_policy"] = continuation_policy
    if required_write_scopes:
        todo["required_write_scopes"] = required_write_scopes
    if blocks_agent:
        todo["blocks_agent"] = blocks_agent
    if bound_agent:
        todo["bound_agent"] = bound_agent
    if goal_bound is not None:
        todo["goal_bound"] = goal_bound
    if global_gate is not None:
        todo["global_gate"] = global_gate
    if excluded_agents:
        todo["excluded_agents"] = excluded_agents
    unblocks_todo_id = normalize_todo_id(payload.get("unblocks_todo_id"))
    if unblocks_todo_id:
        todo["unblocks_todo_id"] = unblocks_todo_id
    for key in TODO_MONITOR_METADATA_FIELDS:
        if payload.get(key):
            todo[key] = compact_text(payload[key])
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
        continuation_policy = normalize_todo_continuation_policy(
            payload.get("continuation_policy")
        )
        removed_continuation_policy = normalize_removed_todo_continuation_policy(
            payload.get("removed_continuation_policy")
            or payload.get("continuation_policy")
        )
        update_excluded_agents = normalize_todo_excluded_agents(
            payload.get("excluded_agents")
        )
        if removed_continuation_policy:
            todo.pop("continuation_policy", None)
            todo["removed_continuation_policy"] = removed_continuation_policy
        elif continuation_policy:
            explicit_repair = (
                todo.get("removed_continuation_policy")
                and continuation_policy == "independent_handoff"
                and bool(update_excluded_agents)
            )
            if not todo.get("removed_continuation_policy") or explicit_repair:
                todo["continuation_policy"] = continuation_policy
            if explicit_repair:
                todo.pop("removed_continuation_policy", None)
        required_write_scopes = normalize_required_write_scopes(
            payload.get("required_write_scopes")
        )
        if required_write_scopes:
            todo["required_write_scopes"] = required_write_scopes
        blocks_agent = normalize_todo_blocks_agent(payload.get("blocks_agent"))
        if blocks_agent:
            todo["blocks_agent"] = blocks_agent
        bound_agent = normalize_todo_bound_agent(payload.get("bound_agent"))
        if bound_agent:
            todo["bound_agent"] = bound_agent
            todo.pop("goal_bound", None)
        goal_bound = normalize_todo_goal_bound(payload.get("goal_bound"))
        if goal_bound is not None:
            todo["goal_bound"] = goal_bound
            if goal_bound:
                todo.pop("bound_agent", None)
        global_gate = normalize_todo_global_gate(payload.get("global_gate"))
        if global_gate is not None:
            todo["global_gate"] = global_gate
        if update_excluded_agents:
            todo["excluded_agents"] = update_excluded_agents
        for key in TODO_MONITOR_METADATA_FIELDS:
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
        for key in (
            "evidence",
            "reason",
            "note",
            "completed_at",
            "updated_at",
            "no_followup",
        ):
            if payload.get(key) is not None:
                todo[key] = compact_text(payload[key])
        successor_todo_ids = normalize_todo_id_list(payload.get("successor_todo_ids"))
        if successor_todo_ids:
            todo["successor_todo_ids"] = successor_todo_ids
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
    monitor_metadata = {
        key: item.get(key)
        for key in TODO_MONITOR_METADATA_FIELDS
    }
    metadata = format_todo_metadata_line(
        todo_id=item.get("todo_id"),
        status=status,
        task_class=item.get("task_class"),
        action_kind=item.get("action_kind"),
        continuation_policy=item.get("continuation_policy"),
        removed_continuation_policy=item.get("removed_continuation_policy"),
        required_write_scopes=item.get("required_write_scopes"),
        claimed_by=item.get("claimed_by"),
        bound_agent=item.get("bound_agent"),
        goal_bound=item.get("goal_bound"),
        blocks_agent=item.get("blocks_agent"),
        excluded_agents=item.get("excluded_agents"),
        global_gate=item.get("global_gate"),
        unblocks_todo_id=item.get("unblocks_todo_id"),
        successor_todo_ids=item.get("successor_todo_ids"),
        no_followup=True if item.get("no_followup") == "true" else None,
        **monitor_metadata,
        note=item.get("note"),
        evidence=item.get("evidence"),
        reason=item.get("reason"),
        completed_at=item.get("completed_at"),
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
