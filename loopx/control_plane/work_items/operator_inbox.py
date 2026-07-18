from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


OPERATOR_INBOX_URGENCY_SCHEMA_VERSION = "operator_inbox_urgency_v0"
CAPTURE_SCOPES = {"addressed_only", "configured_chat_all"}
QUESTION_SIGNAL_PATTERN = re.compile(
    r"[?？]|(?:请问|怎么|怎样|为何|为什么|是不是|是否|能否|可以吗|行吗|结论呢|回复吗)"
)


def _safe_inbox_path(project: Path, raw_path: object) -> Path:
    relative = PurePosixPath(str(raw_path or "").strip().replace("\\", "/"))
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or relative.parts[:2] != (".loopx", "inbox")
    ):
        raise ValueError("operator inbox path must stay under .loopx/inbox")
    resolved = (project / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(project)
    except ValueError as exc:
        raise ValueError("operator inbox path escapes the project") from exc
    return resolved


def _read_mapping(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"operator inbox JSON must be an object: {path.name}")
    return payload


def _pending_events(
    inbox: Path,
    *,
    event_schema_version: str,
    processed_schema_version: str,
) -> list[dict[str, Any]]:
    processed_path = inbox / "processed.json"
    processed: set[str] = set()
    if processed_path.is_file():
        processed_payload = _read_mapping(processed_path)
        if processed_payload.get("schema_version") != processed_schema_version:
            raise ValueError("operator inbox processed-state schema is invalid")
        message_ids = processed_payload.get("message_ids")
        if not isinstance(message_ids, list):
            raise ValueError("operator inbox processed message_ids must be a list")
        processed = {str(value).strip() for value in message_ids if str(value).strip()}

    events: dict[str, dict[str, Any]] = {}
    for path in sorted(inbox.glob("*.json")) if inbox.is_dir() else []:
        if path.name == "processed.json":
            continue
        try:
            payload = _read_mapping(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        message_id = str(payload.get("message_id") or "").strip()
        content = " ".join(str(payload.get("content") or "").split())[:1200]
        if (
            payload.get("schema_version") != event_schema_version
            or not message_id
            or not content
        ):
            continue
        events.setdefault(
            message_id,
            {
                "message_id": message_id,
                "create_time": str(payload.get("create_time") or "")[:40],
                "content": content,
                "reply_context_verified": payload.get("reply_context_verified") is True,
                "reply_to_operator": bool(
                    payload.get("reply_context_verified") is True
                    and str(payload.get("parent_id") or "").strip()
                    and payload.get("reply_to_bot") is True
                ),
            },
        )
    return [
        event for message_id, event in events.items() if message_id not in processed
    ]


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


def operator_inbox_attention_kind(
    event: Mapping[str, Any],
    *,
    operator_display_name: str,
    capture_scope: str,
) -> str | None:
    if (
        event.get("reply_context_verified") is True
        and event.get("reply_to_operator") is True
    ):
        return "reply_to_operator"
    content = str(event.get("content") or "")
    folded = content.casefold()
    operator_name = " ".join(operator_display_name.split()).casefold()
    explicit_mention = bool(
        operator_name and "@" in content and operator_name in folded
    )
    loopx_mention = "@" in content and "loopx" in folded
    if capture_scope != "addressed_only" and not explicit_mention and not loopx_mention:
        return None
    if QUESTION_SIGNAL_PATTERN.search(content):
        return "direct_question"
    if explicit_mention or loopx_mention:
        return "direct_mention"
    return None


def project_operator_inbox_urgency(
    *,
    project: str | Path,
    config_path: str | Path,
    config_schema_version: str,
    event_schema_version: str,
    processed_schema_version: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Project provider-owned inbox files into a content-free control-plane read model."""

    root = Path(project).expanduser().resolve()
    path = Path(config_path).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("operator inbox config must stay inside the project") from exc
    config = _read_mapping(path)
    if config.get("schema_version") != config_schema_version:
        raise ValueError("operator inbox config schema is invalid")
    enabled = config.get("enabled") is True
    if not enabled:
        return {
            "schema_version": OPERATOR_INBOX_URGENCY_SCHEMA_VERSION,
            "enabled": False,
            "pending_count": 0,
            "direct_question_count": 0,
            "direct_mention_count": 0,
            "reply_to_operator_count": 0,
            "attention_required_count": 0,
            "reply_due": False,
            "local_private_content_returned": False,
        }

    capture_scope = str(config.get("capture_scope") or "addressed_only").strip()
    if capture_scope not in CAPTURE_SCOPES:
        raise ValueError("operator inbox capture_scope is invalid")
    reply = config.get("reply")
    reply = reply if isinstance(reply, Mapping) else {}
    reply_enabled = reply.get("enabled") is True
    operator_display_name = " ".join(
        str(
            reply.get("bot_display_name") or reply.get("operator_display_name") or ""
        ).split()
    )[:100]
    if reply_enabled and not operator_display_name:
        raise ValueError(
            "enabled operator inbox reply requires an operator display name"
        )
    inbox = _safe_inbox_path(root, config.get("inbox_dir"))
    pending = _pending_events(
        inbox,
        event_schema_version=event_schema_version,
        processed_schema_version=processed_schema_version,
    )
    kinds = [
        operator_inbox_attention_kind(
            event,
            operator_display_name=operator_display_name,
            capture_scope=capture_scope,
        )
        for event in pending
    ]
    direct_question_count = kinds.count("direct_question")
    direct_mention_count = kinds.count("direct_mention")
    reply_to_operator_count = kinds.count("reply_to_operator")
    attention_required_count = (
        direct_question_count + direct_mention_count + reply_to_operator_count
    )
    parsed_times = [
        parsed
        for event in pending
        if (parsed := _parse_event_time(event.get("create_time"))) is not None
    ]
    oldest = min(parsed_times) if parsed_times else None
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "schema_version": OPERATOR_INBOX_URGENCY_SCHEMA_VERSION,
        "enabled": True,
        "thread_complete": capture_scope == "configured_chat_all",
        "pending_count": len(pending),
        "direct_question_count": direct_question_count,
        "direct_mention_count": direct_mention_count,
        "reply_to_operator_count": reply_to_operator_count,
        "attention_required_count": attention_required_count,
        "oldest_pending_at": oldest.isoformat() if oldest else None,
        "oldest_pending_age_seconds": (
            max(0, int((current - oldest).total_seconds())) if oldest else None
        ),
        "reply_due": bool(attention_required_count > 0 and reply_enabled),
        "local_private_content_returned": False,
    }
