from __future__ import annotations

import copy
import errno
import json
import os
from pathlib import Path
from typing import Any

from .authority import compact_authority_registry
from .control_plane.runtime.time import now_local_iso
from .history import load_registry
from .paths import DEFAULT_RUNTIME_ROOT, global_registry_path, resolve_runtime_root
from .registry import registry_goals
from .registry_writability import is_write_denied_error, probe_registry_write_path


ATTENTION_OVERRIDE_FIELDS = (
    "waiting_on",
    "attention_status",
    "operator_question",
    "recommended_action",
    "next_handoff_condition",
)

ROUTE_FIELDS = ("source_registry", "repo", "state_file")


def now_local() -> str:
    return now_local_iso()


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def global_write_denied_payload(
    *,
    registry_path: Path,
    global_path: Path,
    runtime_root: Path,
    dry_run: bool,
    goals: list[dict[str, Any]],
    merged_goals: list[Any],
    actions: list[str],
    attempted_goal_ids: list[str],
    route_collisions: list[dict[str, Any]],
    allow_route_replacement: bool,
    backup_path: str | None,
    synced_at: str,
    exc: BaseException,
    writability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errno_value = getattr(exc, "errno", None)
    return {
        "ok": False,
        "dry_run": dry_run,
        "skipped": False,
        "registry": str(registry_path),
        "global_registry": str(global_path),
        "runtime_root": str(runtime_root),
        "source_goal_count": len(goals),
        "global_goal_count": len(merged_goals),
        "synced_goal_ids": [],
        "attempted_goal_ids": attempted_goal_ids,
        "actions": actions,
        "route_collisions": route_collisions,
        "route_replacement_allowed": allow_route_replacement,
        "backup_path": backup_path,
        "updated_at": synced_at,
        "wrote": False,
        "write_denied": True,
        "error_kind": "global_registry_write_denied",
        "errno": errno_value,
        "error": str(exc),
        "project_registry_usable": True,
        "fallback_registry": str(registry_path),
        "global_registry_writability": writability or {},
        "requires_global_registry_repair": True,
        "requires_host_permission": bool(
            (writability or {}).get("requires_host_permission") or is_write_denied_error(exc)
        ),
        "recommended_action": (
            f"Fix write access for `{global_path}` and rerun `loopx sync-global` "
            f"from `{registry_path}`. Project-local state is still available through "
            f"`loopx --registry {registry_path} ...`, but shared status/quota is not healthy "
            "until the global registry can be written."
        ),
    }


def sanitize_goal_for_global(goal: dict[str, Any], *, source_registry: Path, synced_at: str) -> dict[str, Any]:
    copied = copy.deepcopy(goal)
    authority_sources = copied.pop("authority_sources", [])
    repo = Path(str(copied.get("repo"))).expanduser() if copied.get("repo") else None
    authority_registry = compact_authority_registry(copied, project=repo)
    authority_registry.pop("default_entries", None)
    copied.pop("authority_registry", None)
    copied["source_registry"] = str(source_registry.expanduser().resolve())
    copied["synced_at"] = synced_at
    copied["authority_source_count"] = len(authority_sources) if isinstance(authority_sources, list) else 0
    copied["authority_registry"] = authority_registry
    return copied


def same_source_registry(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    existing_source = existing.get("source_registry")
    incoming_source = incoming.get("source_registry")
    if not existing_source or not incoming_source:
        return False
    try:
        return Path(str(existing_source)).expanduser().resolve() == Path(str(incoming_source)).expanduser().resolve()
    except OSError:
        return str(existing_source) == str(incoming_source)


def _resolved_route_value(goal: dict[str, Any], field: str) -> str | None:
    value = goal.get(field)
    if value is None:
        return None
    text = str(value)
    if field == "source_registry":
        try:
            return str(Path(text).expanduser().resolve())
        except OSError:
            return text
    return text


def route_snapshot(goal: dict[str, Any] | None) -> dict[str, str | None]:
    if not isinstance(goal, dict):
        return {field: None for field in ROUTE_FIELDS}
    return {field: _resolved_route_value(goal, field) for field in ROUTE_FIELDS}


def route_collision(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any] | None:
    existing_route = route_snapshot(existing)
    incoming_route = route_snapshot(incoming)
    changed = [
        field
        for field in ROUTE_FIELDS
        if existing_route.get(field)
        and incoming_route.get(field)
        and existing_route.get(field) != incoming_route.get(field)
    ]
    if not changed:
        return None
    return {
        "goal_id": str(incoming.get("id") or existing.get("id") or ""),
        "changed_fields": changed,
        "existing_route": existing_route,
        "incoming_route": incoming_route,
    }


def collision_message(collision: dict[str, Any]) -> str:
    goal_id = collision.get("goal_id") or "<unknown>"
    fields = ", ".join(collision.get("changed_fields") or [])
    return (
        f"global route collision for goal_id {goal_id}: {fields} would change. "
        "Use the existing source_registry to register agents, choose a new --fork-goal id, "
        "or rerun with --replace-state to write a global registry backup and replace the route."
    )


def preserve_attention_override(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = {key: value for key, value in incoming.items() if key != "clear_attention_override"}
    if incoming.get("clear_attention_override"):
        return merged
    if same_source_registry(existing, incoming):
        return merged

    preserved = False
    for field in ATTENTION_OVERRIDE_FIELDS:
        if merged.get(field) or not existing.get(field):
            continue
        merged[field] = existing[field]
        preserved = True
    if preserved and existing.get("attention_override_synced_from"):
        merged["attention_override_synced_from"] = existing.get("attention_override_synced_from")
    return merged


def merge_goal_entries(
    existing: list[Any],
    incoming: list[dict[str, Any]],
    *,
    allow_route_replacement: bool = False,
) -> tuple[list[Any], list[str], list[str], list[dict[str, Any]]]:
    merged: list[Any] = []
    seen_incoming = {str(goal.get("id")) for goal in incoming if goal.get("id")}
    actions: list[str] = []
    synced_ids: list[str] = []
    collisions: list[dict[str, Any]] = []

    existing_by_id = {
        str(item.get("id")): item
        for item in existing
        if isinstance(item, dict) and item.get("id")
    }

    for item in existing:
        if isinstance(item, dict) and str(item.get("id")) in seen_incoming:
            continue
        merged.append(item)

    for goal in incoming:
        goal_id = str(goal.get("id") or "")
        if not goal_id:
            continue
        existing_goal = existing_by_id.get(goal_id)
        action = "updated" if existing_goal else "added"
        if existing_goal:
            collision = route_collision(existing_goal, goal)
            if collision:
                collisions.append(collision)
                if not allow_route_replacement:
                    raise ValueError(collision_message(collision))
                action = "replaced-route"
            goal = preserve_attention_override(existing_goal, goal)
        merged.append(goal)
        actions.append(f"{goal_id}:{action}")
        synced_ids.append(goal_id)
    return merged, actions, synced_ids, collisions


def write_recovery_backup(global_path: Path, payload: dict[str, Any], *, dry_run: bool) -> str | None:
    timestamp = now_local().replace(":", "").replace("-", "")
    backup_path = global_path.with_name(f"{global_path.name}.route-collision-backup-{timestamp}.bak")
    if not dry_run:
        write_json(backup_path, payload)
    return str(backup_path)


def sync_project_registry_to_global(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str | None = None,
    dry_run: bool = False,
    allow_route_replacement: bool = False,
) -> dict[str, Any]:
    registry_path = registry_path.expanduser()
    if not registry_path.exists():
        raise FileNotFoundError(f"registry file does not exist: {registry_path}")
    project_registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(project_registry, runtime_root_override)
    global_path = global_registry_path(runtime_root)
    if registry_path.resolve() == global_path.resolve():
        return {
            "ok": True,
            "dry_run": dry_run,
            "skipped": True,
            "reason": "source registry is already the global registry",
            "registry": str(registry_path),
            "global_registry": str(global_path),
            "runtime_root": str(runtime_root),
            "synced_goal_ids": [],
            "actions": [],
        }

    goals = registry_goals(project_registry)
    if goal_id:
        goals = [goal for goal in goals if str(goal.get("id")) == goal_id]
    if goal_id and not goals:
        raise ValueError(f"goal id not found in source registry: {goal_id}")

    synced_at = now_local()
    incoming = [
        sanitize_goal_for_global(goal, source_registry=registry_path, synced_at=synced_at)
        for goal in goals
    ]
    existing = read_json_if_exists(global_path)
    existing_goals = existing.get("goals")
    if not isinstance(existing_goals, list):
        existing_goals = []

    merged_goals, actions, synced_ids, collisions = merge_goal_entries(
        existing_goals,
        incoming,
        allow_route_replacement=allow_route_replacement,
    )
    backup_path = None
    payload = dict(existing)
    payload["schema_version"] = str(payload.get("schema_version") or project_registry.get("schema_version") or "0.1")
    payload["updated_at"] = synced_at
    payload["common_runtime_root"] = str(runtime_root or DEFAULT_RUNTIME_ROOT)
    payload["registry_role"] = "global-local"
    payload["goals"] = merged_goals

    writability = None
    if not dry_run:
        writability = probe_registry_write_path(global_path, create_parent=True)
        if not writability.get("ok"):
            exc = PermissionError(
                writability.get("errno") if isinstance(writability.get("errno"), int) else errno.EPERM,
                str(writability.get("error") or "global registry is not writable"),
                str(global_path),
            )
            return global_write_denied_payload(
                registry_path=registry_path,
                global_path=global_path,
                runtime_root=runtime_root,
                dry_run=dry_run,
                goals=goals,
                merged_goals=merged_goals,
                actions=actions,
                attempted_goal_ids=synced_ids,
                route_collisions=collisions,
                allow_route_replacement=allow_route_replacement,
                backup_path=backup_path,
                synced_at=synced_at,
                exc=exc,
                writability=writability,
            )

    try:
        backup_path = (
            write_recovery_backup(global_path, existing, dry_run=dry_run)
            if collisions and allow_route_replacement
            else None
        )
        if not dry_run:
            write_json(global_path, payload)
    except OSError as exc:
        if not is_write_denied_error(exc):
            raise
        return global_write_denied_payload(
            registry_path=registry_path,
            global_path=global_path,
            runtime_root=runtime_root,
            dry_run=dry_run,
            goals=goals,
            merged_goals=merged_goals,
            actions=actions,
            attempted_goal_ids=synced_ids,
            route_collisions=collisions,
            allow_route_replacement=allow_route_replacement,
            backup_path=backup_path,
            synced_at=synced_at,
            exc=exc,
            writability=writability,
        )

    return {
        "ok": True,
        "dry_run": dry_run,
        "skipped": False,
        "registry": str(registry_path),
        "global_registry": str(global_path),
        "runtime_root": str(runtime_root),
        "source_goal_count": len(goals),
        "global_goal_count": len(merged_goals),
        "synced_goal_ids": synced_ids,
        "actions": actions,
        "route_collisions": collisions,
        "route_replacement_allowed": allow_route_replacement,
        "backup_path": backup_path,
        "updated_at": synced_at,
        "wrote": not dry_run,
        "global_registry_writability": writability or {},
    }


def render_global_sync_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Global Registry Sync",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- skipped: `{payload.get('skipped')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- global_registry: `{payload.get('global_registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- source_goal_count: `{payload.get('source_goal_count')}`",
        f"- global_goal_count: `{payload.get('global_goal_count')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        if payload.get("write_denied"):
            lines.append(f"- error_kind: `{payload.get('error_kind')}`")
            lines.append(f"- fallback_registry: `{payload.get('fallback_registry')}`")
            lines.append(f"- project_registry_usable: `{payload.get('project_registry_usable')}`")
            if payload.get("recommended_action"):
                lines.append(f"- recommended_action: {payload.get('recommended_action')}")
        return "\n".join(lines)
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    if payload.get("backup_path"):
        lines.append(f"- backup_path: `{payload.get('backup_path')}`")
    collisions = payload.get("route_collisions") or []
    if collisions:
        lines.extend(["", "## Route Replacements"])
        for collision in collisions:
            lines.append(f"- {collision_message(collision)}")
    synced = payload.get("synced_goal_ids") or []
    if synced:
        lines.extend(["", "## Synced Goals"])
        lines.extend(f"- `{goal_id}`" for goal_id in synced)
    actions = payload.get("actions") or []
    if actions:
        lines.extend(["", "## Actions"])
        lines.extend(f"- {action}" for action in actions)
    return "\n".join(lines)
