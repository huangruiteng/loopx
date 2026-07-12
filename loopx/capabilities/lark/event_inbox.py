from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


EVENT_SCHEMA_VERSION = "lark_event_inbox_event_v0"
CONFIG_SCHEMA_VERSION = "lark_event_inbox_config_v0"
PROCESSED_SCHEMA_VERSION = "lark_event_inbox_processed_v0"
CAPTURE_SCOPES = {"addressed_only", "configured_chat_all"}
MESSAGE_ID_PATTERN = re.compile(r"om_[A-Za-z0-9_-]+")
EVENT_ID_PATTERN = re.compile(r"[A-Za-z0-9:_-]{1,200}")


def _safe_inbox_path(project: str | Path, raw_path: str) -> Path:
    relative = PurePosixPath(str(raw_path or "").strip().replace("\\", "/"))
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[:2] != (".loopx", "inbox")
    ):
        raise ValueError("lark inbox path must stay under .loopx/inbox")
    root = Path(project).expanduser().resolve()
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("lark inbox path escapes the project") from exc
    return resolved


def load_lark_event_inbox_config(
    *, project: str | Path, config_path: str | Path
) -> dict[str, Any]:
    root = Path(project).expanduser().resolve()
    path = Path(config_path).expanduser()
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("lark inbox config must stay inside the project") from exc
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != CONFIG_SCHEMA_VERSION
    ):
        raise ValueError("lark inbox config schema is invalid")
    enabled = payload.get("enabled") is True
    inbox_dir = str(payload.get("inbox_dir") or "").strip()
    if enabled and not inbox_dir:
        raise ValueError("enabled lark event inbox requires inbox_dir")
    capture_scope = str(payload.get("capture_scope") or "addressed_only").strip()
    if capture_scope not in CAPTURE_SCOPES:
        raise ValueError(
            "lark inbox capture_scope must be addressed_only or configured_chat_all"
        )
    return {
        "enabled": enabled,
        "configured": True,
        "inbox_path": _safe_inbox_path(root, inbox_dir) if enabled else None,
        "capture_scope": capture_scope,
        "thread_complete": capture_scope == "configured_chat_all",
    }


def _load_processed(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != PROCESSED_SCHEMA_VERSION
    ):
        raise ValueError("lark inbox processed-state schema is invalid")
    values = payload.get("message_ids") if isinstance(payload, Mapping) else []
    return {
        str(value)
        for value in (values if isinstance(values, list) else [])
        if MESSAGE_ID_PATTERN.fullmatch(str(value))
    }


def _event_from_payload(payload: object) -> dict[str, Any] | None:
    if (
        not isinstance(payload, Mapping)
        or payload.get("schema_version") != EVENT_SCHEMA_VERSION
    ):
        return None
    message_id = str(payload.get("message_id") or "").strip()
    event_id = str(payload.get("event_id") or message_id).strip()
    if not MESSAGE_ID_PATTERN.fullmatch(message_id) or not EVENT_ID_PATTERN.fullmatch(
        event_id
    ):
        return None
    content = " ".join(str(payload.get("content") or "").split())[:1200]
    if not content:
        return None
    return {
        "event_id": event_id,
        "message_id": message_id,
        "create_time": str(payload.get("create_time") or "")[:40],
        "content": content,
    }


def _event_from_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _event_from_payload(payload)


def ingest_lark_event_inbox(
    *,
    project: str | Path,
    config_path: str | Path,
    events: Sequence[object],
    execute: bool = False,
) -> dict[str, Any]:
    """Persist canonical compact events supplied by a host collector or backfill."""

    config = load_lark_event_inbox_config(project=project, config_path=config_path)
    if not config["enabled"]:
        raise ValueError("lark event inbox is not enabled")
    inbox = config["inbox_path"]
    existing_message_ids = {
        event["message_id"]
        for path in sorted(inbox.glob("*.json"))
        if inbox.is_dir()
        if path.name != "processed.json"
        if (event := _event_from_file(path)) is not None
    }
    accepted: dict[str, dict[str, Any]] = {}
    invalid_count = 0
    duplicate_count = 0
    for payload in events:
        event = _event_from_payload(payload)
        if event is None:
            invalid_count += 1
            continue
        message_id = event["message_id"]
        if message_id in existing_message_ids or message_id in accepted:
            duplicate_count += 1
            continue
        accepted[message_id] = event

    if execute and accepted:
        inbox.mkdir(parents=True, exist_ok=True)
        for event in accepted.values():
            path = inbox / f"{event['message_id']}.json"
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(
                    {"schema_version": EVENT_SCHEMA_VERSION, **event},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
    return {
        "ok": True,
        "schema_version": "lark_event_inbox_ingest_v0",
        "execute": execute,
        "requested_count": len(events),
        "accepted_count": len(accepted),
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "write_performed": bool(execute and accepted),
        "local_private_content_returned": False,
        "external_reads_performed": False,
        "external_writes_performed": False,
    }


def inspect_lark_event_inbox(
    *, project: str | Path, config_path: str | Path, limit: int = 20
) -> dict[str, Any]:
    config = load_lark_event_inbox_config(project=project, config_path=config_path)
    if not config["enabled"]:
        return {
            "ok": True,
            "schema_version": "lark_event_inbox_projection_v0",
            "enabled": False,
            "configured": config["configured"],
            "capture_scope": config["capture_scope"],
            "thread_complete": config["thread_complete"],
            "pending_count": 0,
            "items": [],
            "local_private_content_returned": False,
            "external_reads_performed": False,
        }
    inbox = config["inbox_path"]
    processed = _load_processed(inbox / "processed.json")
    events: dict[str, dict[str, Any]] = {}
    invalid_count = 0
    for path in sorted(inbox.glob("*.json")) if inbox.is_dir() else []:
        if path.name == "processed.json":
            continue
        event = _event_from_file(path)
        if event is None:
            invalid_count += 1
            continue
        events.setdefault(event["message_id"], event)
    pending = [event for key, event in events.items() if key not in processed]
    pending.sort(key=lambda item: (item["create_time"], item["message_id"]))
    bounded = pending[: max(1, min(int(limit), 100))]
    return {
        "ok": True,
        "schema_version": "lark_event_inbox_projection_v0",
        "enabled": True,
        "configured": True,
        "capture_scope": config["capture_scope"],
        "thread_complete": config["thread_complete"],
        "coverage_warning": (
            None
            if config["thread_complete"]
            else "addressed_only capture does not include unaddressed thread replies"
        ),
        "pending_count": len(pending),
        "returned_count": len(bounded),
        "processed_count": len(processed),
        "invalid_count": invalid_count,
        "items": bounded,
        "local_private_content_returned": bool(bounded),
        "external_reads_performed": False,
        "instruction": (
            "Translate each actionable item into a todo, vision correction, PR update, "
            "or no-follow-up rationale, then acknowledge its message_id."
        ),
    }


def acknowledge_lark_event_inbox(
    *,
    project: str | Path,
    config_path: str | Path,
    message_ids: Sequence[str],
    execute: bool = False,
) -> dict[str, Any]:
    config = load_lark_event_inbox_config(project=project, config_path=config_path)
    if not config["enabled"]:
        raise ValueError("lark event inbox is not enabled")
    normalized = list(
        dict.fromkeys(
            str(value).strip()
            for value in message_ids
            if MESSAGE_ID_PATTERN.fullmatch(str(value).strip())
        )
    )
    if not normalized or len(normalized) != len(message_ids):
        raise ValueError("ack requires valid Lark message ids")
    inbox = config["inbox_path"]
    processed_path = inbox / "processed.json"
    existing = _load_processed(processed_path)
    added = [value for value in normalized if value not in existing]
    if execute and added:
        inbox.mkdir(parents=True, exist_ok=True)
        merged = sorted(existing | set(added))
        payload = {
            "schema_version": PROCESSED_SCHEMA_VERSION,
            "message_ids": merged,
            "last_processed_at": datetime.now(timezone.utc).isoformat(),
        }
        temporary = processed_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(processed_path)
    return {
        "ok": True,
        "schema_version": "lark_event_inbox_ack_v0",
        "execute": execute,
        "requested_count": len(normalized),
        "new_count": len(added),
        "already_acknowledged_count": len(normalized) - len(added),
        "write_performed": bool(execute and added),
        "message_ids": normalized,
        "local_private_content_captured": False,
        "external_writes_performed": False,
    }
