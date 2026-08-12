"""Append-only, lease-fenced persistence for one LoopX Turn."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from ...file_lock import exclusive_file_lock
from ..work_items.task_lease import (
    _require_task_lease_fence_unlocked,
    normalize_goal_id,
    normalize_idempotency_key,
    normalize_lease_todo_id,
    normalize_owner,
    read_lease,
    task_lease_lock_path,
    task_lease_path,
)


TURN_JOURNAL_EVENT_SCHEMA_VERSION = "loopx_turn_journal_event_v1"
TURN_JOURNAL_PROJECTION_SCHEMA_VERSION = "loopx_turn_journal_projection_v1"
TURN_KEY_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PUBLIC_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:@/-]{1,512}$")
MAX_EVENT_BYTES = 128 * 1024
MAX_EVENT_COUNT = 100_000
EVENT_FIELDS = {
    "schema_version",
    "turn_key",
    "goal_id",
    "event_type",
    "phase_key",
    "fencing_token",
    "payload",
    "event_hash",
}


class TurnJournalError(ValueError):
    """The authoritative Turn journal is malformed or internally inconsistent."""


class TurnJournalStore(Protocol):
    """Persistence interface for a Turn journal at its lease-authority seam."""

    def load_events(
        self,
        *,
        runtime_root: Path,
        goal_id: str,
        turn_key: str,
    ) -> list[dict[str, Any]]: ...

    def append_event(
        self,
        *,
        runtime_root: Path,
        goal_id: str,
        turn_key: str,
        event_type: str,
        phase_key: str,
        fencing: object,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]: ...


def _require_turn_key(value: object) -> str:
    turn_key = str(value or "")
    if not TURN_KEY_RE.fullmatch(turn_key):
        raise TurnJournalError("turn_key must be a sha256 digest")
    return turn_key


def _require_public_token(value: object, *, field: str) -> str:
    token = str(value or "")
    if not PUBLIC_TOKEN_RE.fullmatch(token):
        raise TurnJournalError(f"{field} must be a public-safe token")
    return token


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TurnJournalError("turn event must be JSON serializable") from exc


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _turn_digest(turn_key: str) -> str:
    return _require_turn_key(turn_key).removeprefix("sha256:")


def turn_journal_path(runtime_root: Path, goal_id: str, turn_key: str) -> Path:
    return (
        runtime_root
        / "goals"
        / normalize_goal_id(goal_id)
        / "turn-journals"
        / f"{_turn_digest(turn_key)}.jsonl"
    )


def turn_projection_path(runtime_root: Path, goal_id: str, turn_key: str) -> Path:
    return turn_journal_path(runtime_root, goal_id, turn_key).with_suffix(".json")


def build_turn_event(
    *,
    turn_key: str,
    goal_id: str,
    event_type: str,
    phase_key: str,
    fencing_token: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_payload = dict(payload)
    body = {
        "schema_version": TURN_JOURNAL_EVENT_SCHEMA_VERSION,
        "turn_key": _require_turn_key(turn_key),
        "goal_id": normalize_goal_id(goal_id),
        "event_type": _require_public_token(event_type, field="event_type"),
        "phase_key": _require_public_token(phase_key, field="phase_key"),
        "fencing_token": _require_public_token(
            fencing_token,
            field="fencing_token",
        ),
        "payload": normalized_payload,
    }
    if len(_canonical_json(body)) > MAX_EVENT_BYTES:
        raise TurnJournalError("turn event exceeds the size limit")
    body["event_hash"] = _canonical_hash(body)
    return body


def _validate_event(
    value: object,
    *,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TurnJournalError("turn journal line must be one JSON object")
    unknown = sorted(set(value) - EVENT_FIELDS)
    missing = sorted(EVENT_FIELDS - set(value))
    if unknown or missing:
        raise TurnJournalError("turn journal event fields are invalid")
    if value.get("schema_version") != TURN_JOURNAL_EVENT_SCHEMA_VERSION:
        raise TurnJournalError("turn journal schema is unsupported")
    if value.get("goal_id") != goal_id or value.get("turn_key") != turn_key:
        raise TurnJournalError("turn journal identity does not match its path")
    if not isinstance(value.get("payload"), dict):
        raise TurnJournalError("turn journal payload must be an object")
    _require_public_token(value.get("event_type"), field="event_type")
    _require_public_token(value.get("phase_key"), field="phase_key")
    _require_public_token(value.get("fencing_token"), field="fencing_token")
    without_hash = {key: value[key] for key in EVENT_FIELDS if key != "event_hash"}
    if value.get("event_hash") != _canonical_hash(without_hash):
        raise TurnJournalError("turn journal event hash does not match")
    return dict(value)


def _load_turn_events_unlocked(
    path: Path,
    *,
    goal_id: str,
    turn_key: str,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise TurnJournalError("turn journal contains a truncated line")
    events: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        if not raw_line or len(raw_line) > MAX_EVENT_BYTES:
            raise TurnJournalError(f"turn journal line {line_number} is invalid")
        try:
            decoded = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TurnJournalError(
                f"turn journal line {line_number} is not valid JSON"
            ) from exc
        event = _validate_event(decoded, goal_id=goal_id, turn_key=turn_key)
        phase_key = str(event["phase_key"])
        if prior := seen.get(phase_key):
            if prior != event:
                raise TurnJournalError("turn journal contains a phase key conflict")
            raise TurnJournalError("turn journal contains a duplicate phase key")
        seen[phase_key] = event
        events.append(event)
        if len(events) > MAX_EVENT_COUNT:
            raise TurnJournalError("turn journal exceeds the event count limit")
    return events


def load_turn_events(
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
) -> list[dict[str, Any]]:
    normalized_goal_id = normalize_goal_id(goal_id)
    normalized_turn_key = _require_turn_key(turn_key)
    path = turn_journal_path(runtime_root, normalized_goal_id, normalized_turn_key)
    with exclusive_file_lock(
        path,
        operation="turn_journal_read",
    ):
        return _load_turn_events_unlocked(
            path,
            goal_id=normalized_goal_id,
            turn_key=normalized_turn_key,
        )


def _projection(
    *,
    goal_id: str,
    turn_key: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    last = events[-1] if events else None
    payload = last.get("payload") if isinstance(last, dict) else {}
    last_phase = payload.get("phase") if isinstance(payload, dict) else None
    return {
        "schema_version": TURN_JOURNAL_PROJECTION_SCHEMA_VERSION,
        "goal_id": goal_id,
        "turn_key": turn_key,
        "event_count": len(events),
        "phase_keys": [event["phase_key"] for event in events],
        "last_phase": last_phase,
        "last_event_type": last.get("event_type") if last else None,
        "last_event_hash": last.get("event_hash") if last else None,
        "fencing_token": last.get("fencing_token") if last else None,
    }


def _atomic_write_projection(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = _canonical_json(value) + b"\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{id(value)}.tmp")
    try:
        descriptor = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory = os.open(
                path.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def _write_projection(
    projection_path: Path,
    *,
    goal_id: str,
    turn_key: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    projection = _projection(goal_id=goal_id, turn_key=turn_key, events=events)
    _atomic_write_projection(projection_path, projection)
    return projection


def rebuild_turn_projection(
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
) -> dict[str, Any]:
    normalized_goal_id = normalize_goal_id(goal_id)
    normalized_turn_key = _require_turn_key(turn_key)
    journal_path = turn_journal_path(
        runtime_root,
        normalized_goal_id,
        normalized_turn_key,
    )
    projection_path = turn_projection_path(
        runtime_root,
        normalized_goal_id,
        normalized_turn_key,
    )
    with exclusive_file_lock(journal_path, operation="turn_projection_rebuild"):
        events = _load_turn_events_unlocked(
            journal_path,
            goal_id=normalized_goal_id,
            turn_key=normalized_turn_key,
        )
        return _write_projection(
            projection_path,
            goal_id=normalized_goal_id,
            turn_key=normalized_turn_key,
            events=events,
        )


def _fencing_value(fencing: object, name: str) -> object:
    if isinstance(fencing, Mapping):
        return fencing.get(name)
    return getattr(fencing, name, None)


def append_turn_event(
    *,
    runtime_root: Path,
    goal_id: str,
    turn_key: str,
    event_type: str,
    phase_key: str,
    fencing: object,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_goal_id = normalize_goal_id(goal_id)
    normalized_turn_key = _require_turn_key(turn_key)
    todo_id = normalize_lease_todo_id(_fencing_value(fencing, "todo_id"))
    owner = normalize_owner(_fencing_value(fencing, "owner"))
    idempotency_key = normalize_idempotency_key(
        _fencing_value(fencing, "idempotency_key")
    )
    fencing_token = str(_fencing_value(fencing, "token") or "")
    event = build_turn_event(
        turn_key=normalized_turn_key,
        goal_id=normalized_goal_id,
        event_type=event_type,
        phase_key=phase_key,
        fencing_token=fencing_token,
        payload=payload,
    )
    lease_lock = task_lease_lock_path(
        runtime_root=runtime_root,
        goal_id=normalized_goal_id,
    )
    lease_path = task_lease_path(
        runtime_root=runtime_root,
        goal_id=normalized_goal_id,
        todo_id=todo_id,
    )
    journal_path = turn_journal_path(
        runtime_root,
        normalized_goal_id,
        normalized_turn_key,
    )
    projection_path = turn_projection_path(
        runtime_root,
        normalized_goal_id,
        normalized_turn_key,
    )
    with exclusive_file_lock(
        lease_lock,
        agent_id=owner,
        operation="turn_journal_lease_fence",
    ):
        _require_task_lease_fence_unlocked(
            read_lease(lease_path),
            owner=owner,
            idempotency_key=idempotency_key,
            fencing_token=fencing_token,
        )
        with exclusive_file_lock(
            journal_path,
            agent_id=owner,
            operation="turn_journal_append",
        ):
            events = _load_turn_events_unlocked(
                journal_path,
                goal_id=normalized_goal_id,
                turn_key=normalized_turn_key,
            )
            for existing in events:
                if existing["phase_key"] != event["phase_key"]:
                    continue
                if existing == event:
                    _write_projection(
                        projection_path,
                        goal_id=normalized_goal_id,
                        turn_key=normalized_turn_key,
                        events=events,
                    )
                    return existing
                raise TurnJournalError("turn journal phase key conflict")
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                journal_path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            with os.fdopen(descriptor, "ab") as handle:
                os.fchmod(handle.fileno(), 0o600)
                handle.write(_canonical_json(event) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            events.append(event)
            _write_projection(
                projection_path,
                goal_id=normalized_goal_id,
                turn_key=normalized_turn_key,
                events=events,
            )
            return event


class LocalTurnJournalStore:
    """Local filesystem adapter for the canonical fenced Turn journal."""

    def load_events(
        self,
        *,
        runtime_root: Path,
        goal_id: str,
        turn_key: str,
    ) -> list[dict[str, Any]]:
        return load_turn_events(runtime_root, goal_id, turn_key)

    def append_event(
        self,
        *,
        runtime_root: Path,
        goal_id: str,
        turn_key: str,
        event_type: str,
        phase_key: str,
        fencing: object,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        return append_turn_event(
            runtime_root=runtime_root,
            goal_id=goal_id,
            turn_key=turn_key,
            event_type=event_type,
            phase_key=phase_key,
            fencing=fencing,
            payload=payload,
        )
