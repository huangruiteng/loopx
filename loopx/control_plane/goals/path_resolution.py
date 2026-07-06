from __future__ import annotations

from pathlib import Path
from typing import Any


def same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def resolve_goal_local_path(raw: Any, goal: dict[str, Any], *, fallback_base: Path) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path
    repo = goal.get("repo")
    if repo:
        return Path(str(repo)).expanduser() / path
    return fallback_base / path
