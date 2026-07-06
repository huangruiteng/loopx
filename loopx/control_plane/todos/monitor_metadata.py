from __future__ import annotations

import re
from typing import Any

from ..runtime.time import parse_timestamp
from .contract import TODO_MONITOR_METADATA_FIELDS


MONITOR_CADENCE_PATTERN = re.compile(
    r"^\s*(?P<count>[1-9][0-9]{0,4})\s*"
    r"(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
    re.IGNORECASE,
)


def normalize_monitor_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        if key not in TODO_MONITOR_METADATA_FIELDS:
            continue
        candidate = str(value or "").strip()
        if candidate:
            normalized[key] = candidate
    if "cadence" in normalized and not MONITOR_CADENCE_PATTERN.match(normalized["cadence"]):
        raise ValueError("--cadence must look like 30m, 2h, or 1d")
    if "next_due_at" in normalized and parse_timestamp(normalized["next_due_at"]) is None:
        raise ValueError("--next-due-at must be an ISO timestamp")
    if "expires_at" in normalized and parse_timestamp(normalized["expires_at"]) is None:
        raise ValueError("--expires-at must be an ISO timestamp")
    if "last_checked_at" in normalized and parse_timestamp(normalized["last_checked_at"]) is None:
        raise ValueError("--last-checked-at must be an ISO timestamp")
    if "consecutive_no_change" in normalized:
        try:
            int(normalized["consecutive_no_change"])
        except ValueError as exc:
            raise ValueError("--consecutive-no-change must be an integer") from exc
    if "material_change" in normalized and normalized["material_change"] not in {"true", "false"}:
        raise ValueError("--material-change metadata must be true or false")
    return normalized


def require_monitor_metadata_scope(
    *,
    monitor_metadata: dict[str, Any] | None,
    role: str,
    task_class: str | None,
) -> dict[str, str]:
    normalized = normalize_monitor_metadata(monitor_metadata)
    if not normalized:
        return {}
    if role != "agent" or task_class != "continuous_monitor":
        raise ValueError(
            "monitor schedule metadata requires --role agent --task-class continuous_monitor"
        )
    return normalized
