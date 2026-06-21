from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .history import load_registry
from .paths import resolve_runtime_root
from .registry import registry_goals


def validate_goal_id_path_segment(goal_id: str) -> str:
    value = goal_id.strip()
    if not value:
        raise ValueError("goal id is required")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("goal id must be a single path segment")
    if Path(value).name != value:
        raise ValueError("goal id must not include path traversal")
    return value


def unique_archive_path(archive_root: Path, goal_id: str, timestamp: str) -> Path:
    base = archive_root / f"{goal_id}-{timestamp}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = archive_root / f"{goal_id}-{timestamp}-{suffix}"
        suffix += 1
    return candidate


def archive_runtime_goal(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    archive_root: Path | None,
    allow_registered: bool,
    execute: bool,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    safe_goal_id = validate_goal_id_path_segment(goal_id)
    registered_ids = {str(goal.get("id")) for goal in registry_goals(registry)}
    registry_member = safe_goal_id in registered_ids
    if registry_member and not allow_registered:
        raise ValueError("goal exists in registry; pass --allow-registered only after confirming it is obsolete")

    source = runtime_root / "goals" / safe_goal_id
    if not source.exists():
        raise FileNotFoundError(f"runtime goal directory does not exist: {source}")
    if not source.is_dir():
        raise ValueError(f"runtime goal path is not a directory: {source}")

    goals_root = (runtime_root / "goals").resolve()
    if source.resolve().parent != goals_root:
        raise ValueError("runtime goal directory resolved outside the goals root")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_base = archive_root.expanduser() if archive_root else runtime_root / "archived-goals"
    destination = unique_archive_path(archive_base, safe_goal_id, timestamp)

    if execute:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    return {
        "ok": True,
        "goal_id": safe_goal_id,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "registry_member": registry_member,
        "source": str(source),
        "archive_root": str(archive_base),
        "archive_path": str(destination),
        "dry_run": not execute,
        "archived": execute,
        "action": "moved" if execute else "would-move",
        "checks": [
            "goal id is a single path segment",
            "source runtime goal directory exists",
            "source resolves under runtime_root/goals",
            "registry membership checked",
        ],
    }


def render_archive_runtime_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Runtime Archive",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- registry_member: `{payload.get('registry_member')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- archived: `{payload.get('archived')}`",
        f"- action: `{payload.get('action')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- source: `{payload.get('source')}`",
        f"- archive_path: `{payload.get('archive_path')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    if checks:
        lines.extend(["", "## Checks"])
        lines.extend(f"- {check}" for check in checks)
    if payload.get("dry_run"):
        lines.extend(["", "Run again with `--execute` to move the runtime directory."])
    return "\n".join(lines)
