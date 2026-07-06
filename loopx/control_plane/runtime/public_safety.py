from __future__ import annotations

import re
from typing import Any, Callable, Optional


NormalizeText = Callable[..., str]
CompactText = Callable[..., Optional[str]]
DEFAULT_PUBLIC_SAFE_LIST_LIMIT = 4
LOCAL_PATH_SURFACE_PATTERN = re.compile(
    r"(?<!<)/(?:Users|Volumes|var/folders|tmp|private/tmp)/[^\s`'\"<>]+"
)
SECRET_LIKE_SURFACE_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+[a-z0-9._~+/=-]{16,}|"
    r"(?<![a-z0-9_])(?:ak|sk)[-_=:][a-z0-9_=-]{10,}|"
    r"\btoken\s*[=:]\s*[^\s`'\"<>]{12,})"
)
LOOPX_COMMAND_RECORD_ALLOWED_SUBCOMMANDS = {
    "quota should-run",
    "todo claim",
    "todo update",
    "todo complete",
    "refresh-state",
    "quota spend-slot",
    "status",
    "diagnose",
}
LOOPX_COMMAND_RECORD_TODO_ID_PATTERN = re.compile(r"^todo_[A-Za-z0-9_-]{6,80}$")
LOOPX_COMMAND_RECORD_GOAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,120}$")


def compact_text(text: str, *, limit: int) -> str:
    compact = " ".join(str(text or "").strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def public_safe_compact_text(
    value: Any,
    *,
    limit: int = 220,
    normalize_text: NormalizeText | None = None,
    local_path_surface_pattern: Any = LOCAL_PATH_SURFACE_PATTERN,
    secret_like_surface_pattern: Any = SECRET_LIKE_SURFACE_PATTERN,
) -> str | None:
    normalize = normalize_text or compact_text
    text = normalize(str(value or ""), limit=limit)
    if not text:
        return None
    if local_path_surface_pattern.search(text) or secret_like_surface_pattern.search(text):
        return None
    return text


def public_safe_compact_list(
    value: Any,
    *,
    limit: int = DEFAULT_PUBLIC_SAFE_LIST_LIMIT,
    compact_text: CompactText | None = None,
    item_limit: int = 160,
) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    result: list[str] = []
    compact_item = compact_text or public_safe_compact_text
    for item in values:
        text = compact_item(item, limit=item_limit)
        if not text:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def compact_numeric_map(value: Any, *, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    selected_keys = keys or tuple(str(key) for key in value.keys())
    compact: dict[str, Any] = {}
    for key in selected_keys:
        raw = value.get(key)
        if isinstance(raw, bool) or raw is None:
            continue
        if isinstance(raw, (int, float)):
            compact[key] = raw
            continue
        try:
            if isinstance(raw, str) and raw.strip():
                compact[key] = float(raw) if "." in raw else int(raw)
        except ValueError:
            continue
    return compact


def compact_loopx_command_records(value: Any, *, limit: int = 128) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    records: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        subcommand = public_safe_compact_text(item.get("subcommand"), limit=80)
        if subcommand not in LOOPX_COMMAND_RECORD_ALLOWED_SUBCOMMANDS:
            continue
        record: dict[str, str] = {"subcommand": subcommand}
        todo_id = public_safe_compact_text(item.get("todo_id"), limit=100)
        if todo_id and LOOPX_COMMAND_RECORD_TODO_ID_PATTERN.match(todo_id):
            record["todo_id"] = todo_id
        goal_id = public_safe_compact_text(item.get("goal_id"), limit=140)
        if goal_id and LOOPX_COMMAND_RECORD_GOAL_ID_PATTERN.match(goal_id):
            record["goal_id"] = goal_id
        records.append(record)
        if len(records) >= limit:
            break
    return records
