from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .history import load_registry
from .paths import resolve_runtime_root


STATUS_PROJECTION_CACHE_SCHEMA_VERSION = "status_projection_cache_v0"


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_utc_iso() -> str:
    return now_utc().isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_status_projection_cache_runtime_root(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
) -> Path:
    registry = load_registry(registry_path)
    return resolve_runtime_root(registry, runtime_root_override)


def status_projection_cache_dir(runtime_root: Path) -> Path:
    return runtime_root / "status-projection-cache"


def status_projection_cache_key(
    *,
    registry_path: Path,
    runtime_root: Path,
    scan_roots: list[Path],
    limit: int,
    include_task_graph: bool,
    goal_id: str | None,
) -> str:
    request = {
        "schema_version": STATUS_PROJECTION_CACHE_SCHEMA_VERSION,
        "collector": "collect_status",
        "registry_path": str(registry_path.expanduser().resolve()),
        "runtime_root": str(runtime_root.expanduser()),
        "scan_roots": [str(path.expanduser().resolve()) for path in scan_roots],
        "limit": max(0, int(limit)),
        "include_task_graph": bool(include_task_graph),
        "goal_id": str(goal_id or "").strip() or None,
    }
    encoded = json.dumps(
        request,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def status_projection_cache_path(runtime_root: Path, key: str) -> Path:
    return status_projection_cache_dir(runtime_root) / f"{key}.json"


def status_projection_cache_metadata(
    *,
    registry_path: Path,
    runtime_root: Path,
    scan_roots: list[Path],
    limit: int,
    include_task_graph: bool,
    goal_id: str | None,
    max_age_seconds: int,
) -> dict[str, Any]:
    key = status_projection_cache_key(
        registry_path=registry_path,
        runtime_root=runtime_root,
        scan_roots=scan_roots,
        limit=limit,
        include_task_graph=include_task_graph,
        goal_id=goal_id,
    )
    return {
        "schema_version": STATUS_PROJECTION_CACHE_SCHEMA_VERSION,
        "key": key,
        "path": str(status_projection_cache_path(runtime_root, key)),
        "max_age_seconds": max(0, int(max_age_seconds)),
        "goal_id": str(goal_id or "").strip() or None,
        "limit": max(0, int(limit)),
        "include_task_graph": bool(include_task_graph),
        "scan_roots": [str(path.expanduser()) for path in scan_roots],
    }


def load_status_projection_cache(
    *,
    registry_path: Path,
    runtime_root: Path,
    scan_roots: list[Path],
    limit: int,
    include_task_graph: bool,
    goal_id: str | None,
    max_age_seconds: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    metadata = status_projection_cache_metadata(
        registry_path=registry_path,
        runtime_root=runtime_root,
        scan_roots=scan_roots,
        limit=limit,
        include_task_graph=include_task_graph,
        goal_id=goal_id,
        max_age_seconds=max_age_seconds,
    )
    path = Path(str(metadata["path"]))
    metadata["hit"] = False
    if max_age_seconds < 0:
        metadata["miss_reason"] = "disabled"
        return None, metadata
    if not path.exists():
        metadata["miss_reason"] = "missing"
        return None, metadata
    try:
        cache_record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        metadata["miss_reason"] = "unreadable"
        metadata["error"] = str(exc)
        return None, metadata
    if not isinstance(cache_record, dict):
        metadata["miss_reason"] = "invalid_record"
        return None, metadata
    if cache_record.get("schema_version") != STATUS_PROJECTION_CACHE_SCHEMA_VERSION:
        metadata["miss_reason"] = "schema_mismatch"
        return None, metadata
    generated_at = _parse_timestamp(cache_record.get("generated_at"))
    if generated_at is None:
        metadata["miss_reason"] = "missing_generated_at"
        return None, metadata
    age_seconds = max(0.0, (now_utc() - generated_at).total_seconds())
    metadata["generated_at"] = cache_record.get("generated_at")
    metadata["age_seconds"] = age_seconds
    if age_seconds > max(0, int(max_age_seconds)):
        metadata["miss_reason"] = "expired"
        return None, metadata
    payload = cache_record.get("payload")
    if not isinstance(payload, dict):
        metadata["miss_reason"] = "missing_payload"
        return None, metadata
    metadata["hit"] = True
    metadata["miss_reason"] = None
    payload = dict(payload)
    payload["projection_cache"] = dict(metadata)
    return payload, metadata


def write_status_projection_cache(
    *,
    registry_path: Path,
    runtime_root: Path,
    scan_roots: list[Path],
    limit: int,
    include_task_graph: bool,
    goal_id: str | None,
    payload: dict[str, Any],
    max_age_seconds: int,
) -> dict[str, Any]:
    metadata = status_projection_cache_metadata(
        registry_path=registry_path,
        runtime_root=runtime_root,
        scan_roots=scan_roots,
        limit=limit,
        include_task_graph=include_task_graph,
        goal_id=goal_id,
        max_age_seconds=max_age_seconds,
    )
    path = Path(str(metadata["path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    stored_payload = dict(payload)
    stored_payload.pop("projection_cache", None)
    record = {
        "schema_version": STATUS_PROJECTION_CACHE_SCHEMA_VERSION,
        "generated_at": now_utc_iso(),
        "payload": stored_payload,
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
    metadata.update(
        {
            "hit": False,
            "written": True,
            "generated_at": record["generated_at"],
        }
    )
    return metadata
