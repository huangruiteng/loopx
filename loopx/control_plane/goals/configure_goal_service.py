from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...configure_goal import configure_goal
from ...global_registry import (
    sanitize_goal_for_global,
    sync_project_registry_to_global,
)
from ...history import load_registry
from ...paths import global_registry_path, resolve_runtime_root
from ...registry import registry_goals
from ...registry_writability import probe_registry_write_path
from ..runtime.runtime_projection_route import (
    compact_runtime_projection_route,
    resolve_runtime_projection_route,
)


CONFIGURE_GOAL_GLOBAL_SYNC_SCHEMA_VERSION = "configure_goal_global_sync_v0"
CONFIGURE_GOAL_GLOBAL_SYNC_READBACK_SCHEMA_VERSION = (
    "configure_goal_global_sync_readback_v0"
)


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return str(left.expanduser()) == str(right.expanduser())


def _goal(payload: dict[str, Any], goal_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in registry_goals(payload)
            if str(item.get("id") or "") == goal_id
        ),
        None,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def resolve_configure_goal_sync_target(
    *,
    registry_path: Path,
    goal_id: str,
    runtime_root_override: str | None,
) -> dict[str, Any]:
    source_registry = registry_path.expanduser().resolve()
    source_payload = load_registry(source_registry)
    if _goal(source_payload, goal_id) is None:
        raise ValueError(f"goal id not found in source registry: {goal_id}")
    source_runtime = (
        resolve_runtime_root(
            source_payload,
            None,
            registry_path=source_registry,
        )
        .expanduser()
        .resolve()
    )

    if runtime_root_override:
        target_runtime = Path(runtime_root_override).expanduser().resolve()
        route = {
            "schema_version": "runtime_projection_route_v0",
            "status": "explicit_override",
            "projection_required": not _same_path(source_runtime, target_runtime),
            "declaration_source": "cli.runtime_root_override",
            "source_registry": str(source_registry),
            "source_runtime_root": str(source_runtime),
            "target_runtime_root": str(target_runtime),
            "target_registry": str(global_registry_path(target_runtime)),
            "match_count": 1,
            "source_mirror_match_count": 0,
            "conflict_count": 0,
            "unreadable_target_count": 0,
        }
    else:
        route = resolve_runtime_projection_route(
            registry_path=source_registry,
            goal_id=goal_id,
            source_runtime_root=source_runtime,
        )
        status = str(route.get("status") or "missing")
        if status not in {"resolved", "single_runtime"}:
            raise ValueError(
                f"configure-goal global sync route is {status}; refusing to write "
                "the source registry without one authoritative shared runtime"
            )
        target_text = str(route.get("target_runtime_root") or "").strip()
        if not target_text:
            raise ValueError(
                "configure-goal global sync route has no target runtime; refusing partial write"
            )
        target_runtime = Path(target_text).expanduser().resolve()

    target_registry = global_registry_path(target_runtime).expanduser().resolve()
    return {
        "ok": True,
        "schema_version": CONFIGURE_GOAL_GLOBAL_SYNC_SCHEMA_VERSION,
        "goal_id": goal_id,
        "status": route.get("status"),
        "declaration_source": route.get("declaration_source"),
        "explicit_runtime_override": bool(runtime_root_override),
        "source_registry": str(source_registry),
        "source_runtime_root": str(source_runtime),
        "target_runtime_root": str(target_runtime),
        "target_global_registry": str(target_registry),
        "route": compact_runtime_projection_route(route),
    }


def _readback(
    *,
    source_registry: Path,
    target_registry: Path,
    goal_id: str,
    sync_payload: dict[str, Any],
) -> dict[str, Any]:
    source_payload = load_registry(source_registry)
    target_payload = load_registry(target_registry)
    source_goal = _goal(source_payload, goal_id)
    target_goal = _goal(target_payload, goal_id)
    synced_at = str(sync_payload.get("updated_at") or "").strip()
    source_is_target = _same_path(source_registry, target_registry)

    expected_goal = source_goal
    if source_goal is not None and not source_is_target:
        expected_goal = sanitize_goal_for_global(
            source_goal,
            source_registry=source_registry,
            synced_at=synced_at,
        )
    expected_digest = _digest(expected_goal) if expected_goal is not None else None
    target_digest = _digest(target_goal) if target_goal is not None else None
    target_source_registry = str(
        (target_goal or {}).get("source_registry") or ""
    ).strip()
    source_registry_match = bool(
        target_goal is not None
        and (
            source_is_target
            or (
                target_source_registry
                and _same_path(Path(target_source_registry), source_registry)
            )
        )
    )
    synced_at_match = bool(
        source_is_target
        or (
            target_goal is not None
            and str(target_goal.get("synced_at") or "") == synced_at
        )
    )
    verified = bool(
        source_goal is not None
        and target_goal is not None
        and expected_digest == target_digest
        and source_registry_match
        and synced_at_match
    )
    return {
        "schema_version": CONFIGURE_GOAL_GLOBAL_SYNC_READBACK_SCHEMA_VERSION,
        "status": "verified" if verified else "mismatch",
        "verified": verified,
        "goal_id": goal_id,
        "target_global_registry": str(target_registry),
        "goal_present": target_goal is not None,
        "source_registry_match": source_registry_match,
        "synced_at_match": synced_at_match,
        "expected_goal_sha256_16": expected_digest,
        "target_goal_sha256_16": target_digest,
    }


def _sync_plan(
    *,
    changed: bool,
    target_resolution: dict[str, Any] | None,
    execute: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": CONFIGURE_GOAL_GLOBAL_SYNC_SCHEMA_VERSION,
        "enabled": bool(changed),
        "required": bool(changed),
        "executed": False,
        "target_resolution": target_resolution,
        "selected_target": (
            {
                "runtime_root": target_resolution.get("target_runtime_root"),
                "global_registry": target_resolution.get("target_global_registry"),
                "declaration_source": target_resolution.get("declaration_source"),
                "explicit_runtime_override": target_resolution.get(
                    "explicit_runtime_override"
                ),
            }
            if target_resolution
            else None
        ),
        "readback": {
            "schema_version": CONFIGURE_GOAL_GLOBAL_SYNC_READBACK_SCHEMA_VERSION,
            "status": "not_required" if not changed else "not_executed",
            "verified": False,
        },
        "reason": (
            "no configuration change"
            if not changed
            else "dry-run preview; source and shared registries are unchanged"
            if not execute
            else None
        ),
    }


def configure_goal_with_global_sync(
    *,
    registry_path: Path,
    goal_id: str,
    runtime_root_override: str | None,
    execute: bool,
    **configure_options: Any,
) -> dict[str, Any]:
    """Configure one source goal and keep its authoritative shared read model current."""

    preview = configure_goal(
        registry_path=registry_path,
        goal_id=goal_id,
        execute=False,
        **configure_options,
    )
    changed = bool(preview.get("changed"))
    target_resolution = (
        resolve_configure_goal_sync_target(
            registry_path=registry_path,
            goal_id=goal_id,
            runtime_root_override=runtime_root_override,
        )
        if changed
        else None
    )
    preview["global_sync"] = _sync_plan(
        changed=changed,
        target_resolution=target_resolution,
        execute=execute,
    )
    if not execute:
        return preview

    if not changed:
        applied = configure_goal(
            registry_path=registry_path,
            goal_id=goal_id,
            execute=True,
            **configure_options,
        )
        applied["global_sync"] = preview["global_sync"]
        return applied

    if target_resolution is None:
        raise RuntimeError("configure-goal sync target was not resolved")
    target_registry = Path(str(target_resolution["target_global_registry"]))
    writability = probe_registry_write_path(target_registry, create_parent=True)
    if not writability.get("ok"):
        preview.update(
            {
                "ok": False,
                "dry_run": False,
                "execute": True,
                "written": False,
                "error": str(
                    writability.get("error")
                    or "authoritative shared registry is not writable"
                ),
                "recommended_action": writability.get("recommended_action"),
            }
        )
        preview["global_sync"].update(
            {
                "ok": False,
                "reason": "authoritative shared registry preflight failed",
                "global_registry_writability": writability,
            }
        )
        return preview

    applied = configure_goal(
        registry_path=registry_path,
        goal_id=goal_id,
        execute=True,
        **configure_options,
    )
    if not applied.get("written"):
        applied["global_sync"] = _sync_plan(
            changed=False,
            target_resolution=target_resolution,
            execute=True,
        )
        return applied

    sync_payload = sync_project_registry_to_global(
        registry_path=registry_path,
        runtime_root_override=str(target_resolution["target_runtime_root"]),
        goal_id=goal_id,
        dry_run=False,
    )
    readback = (
        _readback(
            source_registry=registry_path.expanduser().resolve(),
            target_registry=target_registry,
            goal_id=goal_id,
            sync_payload=sync_payload,
        )
        if sync_payload.get("ok")
        else {
            "schema_version": CONFIGURE_GOAL_GLOBAL_SYNC_READBACK_SCHEMA_VERSION,
            "status": "not_run",
            "verified": False,
        }
    )
    sync_ok = bool(sync_payload.get("ok") and readback.get("verified"))
    applied["global_sync"] = {
        **_sync_plan(
            changed=True,
            target_resolution=target_resolution,
            execute=True,
        ),
        "ok": sync_ok,
        "executed": True,
        "sync": sync_payload,
        "readback": readback,
        "global_registry_writability": writability,
    }
    applied["ok"] = bool(applied.get("ok") and sync_ok)
    applied["partial_write"] = bool(applied.get("written") and not sync_ok)
    if not sync_ok:
        applied["error"] = "configure-goal shared registry readback did not verify"
        applied["recommended_action"] = (
            sync_payload.get("recommended_action")
            or f"rerun loopx sync-global --goal-id {goal_id} after repairing the shared runtime route"
        )
    return applied
