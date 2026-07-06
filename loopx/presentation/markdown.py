from __future__ import annotations

from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def markdown_scalar(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").replace("|", "\\|").strip()
