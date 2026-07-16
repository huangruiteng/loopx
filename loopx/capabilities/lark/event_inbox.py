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
SAFE_PROFILE_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}")
CHAT_ID_PATTERN = re.compile(r"oc_[A-Za-z0-9_-]+")
QUESTION_SIGNAL_PATTERN = re.compile(
    r"[?？]|(?:请问|怎么|怎样|为何|为什么|是不是|是否|能否|可以吗|行吗|结论呢|回复吗)"
)


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
    reply_payload = payload.get("reply")
    if reply_payload is not None and not isinstance(reply_payload, Mapping):
        raise ValueError("lark inbox reply config must be an object")
    reply_payload = reply_payload if isinstance(reply_payload, Mapping) else {}
    reply_enabled = reply_payload.get("enabled") is True
    sender_profile = str(reply_payload.get("sender_profile") or "").strip()
    sender_identity = str(reply_payload.get("sender_identity") or "").strip()
    bot_display_name = " ".join(
        str(reply_payload.get("bot_display_name") or "").split()
    )[:100]
    chat_id = str(reply_payload.get("chat_id") or "").strip()
    if reply_enabled and (
        capture_scope != "configured_chat_all"
        or not SAFE_PROFILE_PATTERN.fullmatch(sender_profile)
        or sender_profile.lower() == "default"
        or sender_identity != "bot"
        or not bot_display_name
        or not CHAT_ID_PATTERN.fullmatch(chat_id)
    ):
        raise ValueError(
            "enabled lark inbox reply requires configured_chat_all plus an explicit "
            "non-default sender_profile, bot identity, bot_display_name, and chat_id"
        )
    return {
        "enabled": enabled,
        "configured": True,
        "inbox_path": _safe_inbox_path(root, inbox_dir) if enabled else None,
        "capture_scope": capture_scope,
        "thread_complete": capture_scope == "configured_chat_all",
        "reply": {
            "enabled": reply_enabled,
            "sender_profile": sender_profile,
            "sender_identity": sender_identity,
            "bot_display_name": bot_display_name,
            "chat_id": chat_id,
        },
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
    event = {
        "event_id": event_id,
        "message_id": message_id,
        "create_time": str(payload.get("create_time") or "")[:40],
        "content": content,
    }
    parent_id = str(payload.get("parent_id") or "").strip()
    root_id = str(payload.get("root_id") or "").strip()
    if MESSAGE_ID_PATTERN.fullmatch(parent_id):
        event["parent_id"] = parent_id
    if MESSAGE_ID_PATTERN.fullmatch(root_id):
        event["root_id"] = root_id
    reply_context_verified = payload.get("reply_context_verified") is True
    event["reply_context_verified"] = reply_context_verified
    event["reply_to_bot"] = bool(
        reply_context_verified
        and "parent_id" in event
        and payload.get("reply_to_bot") is True
    )
    return event


def _event_from_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _event_from_payload(payload)


def _pending_events(config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
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
    return pending, len(events), invalid_count


def _parse_event_time(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        number = int(raw)
        if number > 10_000_000_000:
            number //= 1000
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_attention_kind(
    event: Mapping[str, Any],
    *,
    bot_display_name: str,
    capture_scope: str,
) -> str | None:
    content = " ".join(str(event.get("content") or "").split())
    if not content:
        return None
    if (
        event.get("reply_context_verified") is True
        and event.get("reply_to_bot") is True
    ):
        return "reply_to_bot"
    folded = content.casefold()
    bot_name = " ".join(str(bot_display_name or "").split()).casefold()
    explicit_bot_mention = bool(bot_name and "@" in content and bot_name in folded)
    generic_loopx_mention = "@" in content and "loopx" in folded
    addressed = bool(
        capture_scope == "addressed_only"
        or explicit_bot_mention
        or generic_loopx_mention
    )
    if not addressed:
        return None
    if QUESTION_SIGNAL_PATTERN.search(content):
        return "direct_question"
    if explicit_bot_mention or generic_loopx_mention:
        return "direct_mention"
    return None


def project_lark_event_inbox_urgency(
    *,
    project: str | Path,
    config_path: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a content-free urgency read model for quota/status routing."""

    config = load_lark_event_inbox_config(project=project, config_path=config_path)
    if not config["enabled"]:
        return {
            "schema_version": "lark_event_inbox_urgency_v0",
            "enabled": False,
            "pending_count": 0,
            "direct_question_count": 0,
            "direct_mention_count": 0,
            "reply_to_bot_count": 0,
            "attention_required_count": 0,
            "reply_due": False,
            "local_private_content_returned": False,
        }
    pending, _, _ = _pending_events(config)
    kinds = [
        _event_attention_kind(
            event,
            bot_display_name=str(config["reply"].get("bot_display_name") or ""),
            capture_scope=str(config["capture_scope"]),
        )
        for event in pending
    ]
    direct_question_count = kinds.count("direct_question")
    direct_mention_count = kinds.count("direct_mention")
    reply_to_bot_count = kinds.count("reply_to_bot")
    attention_required_count = (
        direct_question_count + direct_mention_count + reply_to_bot_count
    )
    parsed_times = [
        parsed
        for event in pending
        if (parsed := _parse_event_time(event.get("create_time"))) is not None
    ]
    oldest = min(parsed_times) if parsed_times else None
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    oldest_age_seconds = (
        max(0, int((current - oldest).total_seconds())) if oldest else None
    )
    return {
        "schema_version": "lark_event_inbox_urgency_v0",
        "enabled": True,
        "thread_complete": bool(config["thread_complete"]),
        "pending_count": len(pending),
        "direct_question_count": direct_question_count,
        "direct_mention_count": direct_mention_count,
        "reply_to_bot_count": reply_to_bot_count,
        "attention_required_count": attention_required_count,
        "oldest_pending_at": oldest.isoformat() if oldest else None,
        "oldest_pending_age_seconds": oldest_age_seconds,
        "reply_due": bool(
            attention_required_count > 0 and config["reply"].get("enabled") is True
        ),
        "local_private_content_returned": False,
    }


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
    pending, captured_count, invalid_count = _pending_events(config)
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
        "captured_count": captured_count,
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
