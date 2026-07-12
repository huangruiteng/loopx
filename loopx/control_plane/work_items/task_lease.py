from __future__ import annotations

import fnmatch
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ...agent_registry import registered_agent_ids_from_registry, require_registered_agent_id
from ...file_lock import exclusive_file_lock
from ...history import load_registry
from ...paths import resolve_runtime_root
from ..runtime.time import now_utc as runtime_now_utc
from ..runtime.time import parse_timestamp, utc_isoformat
from ..todos.contract import (
    normalize_required_write_scopes,
    normalize_todo_claimed_by,
    normalize_todo_excluded_agents,
    normalize_todo_id,
)


TASK_LEASE_SCHEMA_VERSION = "task_lease_v0"
DEFAULT_TASK_LEASE_TTL_SECONDS = 45 * 60
MAX_TASK_LEASE_TTL_SECONDS = 24 * 60 * 60
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:@/-]{1,160}$")


class TaskLeaseError(ValueError):
    def __init__(self, message: str, *, code: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


def now_utc() -> datetime:
    return runtime_now_utc()


def isoformat(value: datetime) -> str:
    return utc_isoformat(value)


def normalize_idempotency_key(value: Any) -> str:
    candidate = str(value or "").strip()
    if not candidate or not IDEMPOTENCY_KEY_PATTERN.match(candidate):
        raise TaskLeaseError(
            "idempotency key must be a public-safe token",
            code="invalid_idempotency_key",
        )
    return candidate


def normalize_owner(value: Any) -> str:
    owner = normalize_todo_claimed_by(value)
    if not owner:
        raise TaskLeaseError("owner must be a public-safe agent id", code="invalid_owner")
    return owner


def normalize_ttl_seconds(value: int | None) -> int:
    ttl = DEFAULT_TASK_LEASE_TTL_SECONDS if value is None else int(value)
    if ttl <= 0 or ttl > MAX_TASK_LEASE_TTL_SECONDS:
        raise TaskLeaseError(
            f"ttl seconds must be between 1 and {MAX_TASK_LEASE_TTL_SECONDS}",
            code="invalid_ttl",
        )
    return ttl


def normalize_goal_id(value: Any) -> str:
    goal_id = str(value or "").strip()
    if not goal_id or goal_id in {".", ".."} or "/" in goal_id or "\\" in goal_id:
        raise TaskLeaseError("goal id must be a single path segment", code="invalid_goal_id")
    if Path(goal_id).name != goal_id:
        raise TaskLeaseError("goal id must not include path traversal", code="invalid_goal_id")
    return goal_id


def normalize_lease_todo_id(value: Any) -> str:
    todo_id = normalize_todo_id(value)
    if not todo_id:
        raise TaskLeaseError("todo id must use the todo_<token> shape", code="invalid_todo_id")
    return todo_id


def task_lease_dir(*, runtime_root: Path, goal_id: str) -> Path:
    return runtime_root / "goals" / normalize_goal_id(goal_id) / "task-leases"


def task_lease_path(*, runtime_root: Path, goal_id: str, todo_id: str) -> Path:
    return task_lease_dir(runtime_root=runtime_root, goal_id=goal_id) / f"{normalize_lease_todo_id(todo_id)}.json"


def task_lease_lock_path(*, runtime_root: Path, goal_id: str) -> Path:
    return task_lease_dir(runtime_root=runtime_root, goal_id=goal_id) / ".task-leases"


def runtime_root_from_registry(registry_path: Path, runtime_root_override: str | None) -> Path:
    registry = load_registry(registry_path)
    return resolve_runtime_root(registry, runtime_root_override)


def task_lease_todo_projection(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
) -> dict[str, Any] | None:
    """Resolve the canonical Markdown/event todo projection for lease guards."""

    from ...todos import list_goal_todos

    try:
        payload = list_goal_todos(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
        )
    except (OSError, ValueError) as exc:
        raise TaskLeaseError(
            "cannot resolve todo projection for task lease",
            code="todo_projection_unavailable",
            payload={"goal_id": goal_id, "todo_id": todo_id, "error": str(exc)},
        ) from exc
    todo = payload.get("todo")
    return dict(todo) if isinstance(todo, dict) else None


def task_lease_owner_constraint(
    todo: dict[str, Any] | None,
    *,
    owner: Any,
    registered_agents: list[str] | None = None,
) -> dict[str, Any]:
    if todo is None:
        return {"effective": False, "reason": "todo_not_found"}
    todo_status = str(todo.get("status") or "").strip().lower()
    if todo_status != "open":
        return {
            "effective": False,
            "reason": "todo_not_open",
            "todo_status": todo_status or "unknown",
        }
    normalized_owner = normalize_todo_claimed_by(owner)
    if not normalized_owner:
        return {"effective": False, "reason": "invalid_owner"}
    if registered_agents is not None and normalized_owner not in registered_agents:
        return {
            "effective": False,
            "reason": "owner_not_registered",
            "registered_agents": registered_agents,
        }
    excluded_agents = normalize_todo_excluded_agents(todo.get("excluded_agents"))
    if normalized_owner in excluded_agents:
        return {
            "effective": False,
            "reason": "owner_excluded_from_todo",
            "excluded_agents": excluded_agents,
        }
    return {"effective": True}


def require_registered_task_lease_owner(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    owner: str,
) -> str:
    try:
        return require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=owner,
            field="task lease owner",
        )
    except ValueError as exc:
        raise TaskLeaseError(
            str(exc),
            code="owner_not_registered",
            payload={"goal_id": goal_id, "todo_id": todo_id, "owner": owner},
        ) from exc


def require_task_lease_owner_allowed(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str,
    owner: str,
) -> dict[str, Any]:
    owner = require_registered_task_lease_owner(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=todo_id,
        owner=owner,
    )
    todo = task_lease_todo_projection(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=todo_id,
    )
    constraint = task_lease_owner_constraint(
        todo,
        owner=owner,
        registered_agents=registered_agent_ids_from_registry(registry_path, goal_id),
    )
    if constraint.get("effective") is not True:
        reason = str(constraint.get("reason") or "owner_not_allowed")
        if reason == "todo_not_found":
            message = "todo is missing from the canonical projection"
        elif reason == "todo_not_open":
            message = (
                f"task lease requires an open todo; "
                f"{todo_id!r} is {constraint.get('todo_status')!r}"
            )
        elif reason == "owner_excluded_from_todo":
            message = f"task lease owner {owner!r} is excluded from todo {todo_id!r}"
        elif reason == "owner_not_registered":
            message = f"task lease owner {owner!r} is not registered for goal {goal_id!r}"
        else:
            message = f"task lease owner {owner!r} is not eligible for todo {todo_id!r}"
        raise TaskLeaseError(
            message,
            code=reason,
            payload={
                "goal_id": goal_id,
                "todo_id": todo_id,
                "owner": owner,
                **constraint,
            },
        )
    return todo


def read_lease(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TaskLeaseError(
            f"lease file is not valid JSON: {path}",
            code="corrupt_lease",
            payload={"lease_path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        raise TaskLeaseError(
            f"lease file must contain an object: {path}",
            code="corrupt_lease",
            payload={"lease_path": str(path)},
        )
    return payload


def write_lease(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{id(payload)}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def remove_lease(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def lease_expires_at(lease: dict[str, Any] | None) -> datetime | None:
    return parse_timestamp((lease or {}).get("expires_at"))


def lease_is_active(lease: dict[str, Any] | None, *, at: datetime | None = None) -> bool:
    if not lease or lease.get("schema_version") != TASK_LEASE_SCHEMA_VERSION:
        return False
    expires_at = lease_expires_at(lease)
    return bool(expires_at and expires_at > (at or now_utc()))


def scope_root(scope: str) -> str:
    value = scope.strip()
    if value in {"*", "**", "./"}:
        return ""
    wildcard_indexes = [index for index in (value.find("*"), value.find("?"), value.find("[")) if index >= 0]
    if wildcard_indexes:
        value = value[: min(wildcard_indexes)]
    if "/" in value:
        value = value[: value.rfind("/") + 1]
    return value.rstrip("/")


def _scope_has_glob(scope: str) -> bool:
    return any(token in scope for token in ("*", "?", "["))


def _scope_literal_prefix(scope: str) -> str:
    indexes = [scope.find(token) for token in ("*", "?", "[") if scope.find(token) >= 0]
    return scope[: min(indexes)] if indexes else scope


def _scope_pair_overlaps(left: str, right: str) -> bool:
    if left == right:
        return True
    if left in {"*", "**", "./"} or right in {"*", "**", "./"}:
        return True

    left_has_glob = _scope_has_glob(left)
    right_has_glob = _scope_has_glob(right)
    if left_has_glob and not right_has_glob:
        prefix = _scope_literal_prefix(left)
        return fnmatch.fnmatchcase(right, left) or (
            prefix.endswith("/") and right.rstrip("/") == prefix.rstrip("/")
        )
    if right_has_glob and not left_has_glob:
        prefix = _scope_literal_prefix(right)
        return fnmatch.fnmatchcase(left, right) or (
            prefix.endswith("/") and left.rstrip("/") == prefix.rstrip("/")
        )
    if left_has_glob and right_has_glob:
        left_prefix = _scope_literal_prefix(left)
        right_prefix = _scope_literal_prefix(right)
        return bool(
            not left_prefix
            or not right_prefix
            or left_prefix.startswith(right_prefix)
            or right_prefix.startswith(left_prefix)
        )

    left_root = left.rstrip("/")
    right_root = right.rstrip("/")
    return bool(
        (left.endswith("/") and right.startswith(left_root + "/"))
        or (right.endswith("/") and left.startswith(right_root + "/"))
    )


def write_scopes_overlap(left: list[str], right: list[str]) -> bool:
    left_scopes = normalize_required_write_scopes(left)
    right_scopes = normalize_required_write_scopes(right)
    if not left_scopes or not right_scopes:
        return False
    for left_scope in left_scopes:
        for right_scope in right_scopes:
            if _scope_pair_overlaps(left_scope, right_scope):
                return True
    return False


def active_conflicts(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
    write_scopes: list[str],
    at: datetime,
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    lease_dir = task_lease_dir(runtime_root=runtime_root, goal_id=goal_id)
    if not lease_dir.exists():
        return conflicts
    for path in sorted(lease_dir.glob("todo_*.json")):
        lease = read_lease(path)
        if not lease_is_active(lease, at=at):
            continue
        lease_todo_id = normalize_lease_todo_id(lease.get("todo_id"))
        if lease_todo_id == todo_id:
            continue
        todo = task_lease_todo_projection(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=lease_todo_id,
        )
        if task_lease_owner_constraint(
            todo,
            owner=lease.get("owner"),
            registered_agents=registered_agents,
        ).get("effective") is not True:
            continue
        if write_scopes_overlap(write_scopes, normalize_required_write_scopes(lease.get("write_scopes"))):
            conflicts.append(
                {
                    "todo_id": lease.get("todo_id"),
                    "owner": lease.get("owner"),
                    "expires_at": lease.get("expires_at"),
                    "write_scopes": lease.get("write_scopes") or [],
                    "lease_path": str(path),
                }
            )
    return conflicts


def assert_expected_version(lease: dict[str, Any] | None, expected_version: int | None) -> None:
    if expected_version is None:
        return
    actual = int((lease or {}).get("version") or 0)
    if actual != expected_version:
        raise TaskLeaseError(
            f"lease version mismatch: expected {expected_version}, got {actual}",
            code="version_mismatch",
            payload={"expected_version": expected_version, "actual_version": actual},
        )


def build_lease(
    *,
    goal_id: str,
    todo_id: str,
    owner: str,
    idempotency_key: str,
    write_scopes: list[str],
    acquire_ttl_seconds: int,
    version: int,
    acquired_at: str,
    updated_at: str,
    expires_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": TASK_LEASE_SCHEMA_VERSION,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "owner": owner,
        "idempotency_key": idempotency_key,
        "write_scopes": write_scopes,
        "acquire_ttl_seconds": acquire_ttl_seconds,
        "version": version,
        "acquired_at": acquired_at,
        "updated_at": updated_at,
        "expires_at": expires_at,
        "status": "active",
    }


def acquire_task_lease(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
    owner: str,
    idempotency_key: str,
    ttl_seconds: int | None = None,
    write_scopes: list[str] | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    goal_id = normalize_goal_id(goal_id)
    todo_id = normalize_lease_todo_id(todo_id)
    owner = normalize_owner(owner)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    ttl = normalize_ttl_seconds(ttl_seconds)
    normalized_write_scopes = normalize_required_write_scopes(write_scopes)
    lease_dir = task_lease_dir(runtime_root=runtime_root, goal_id=goal_id)
    lock_target = task_lease_lock_path(runtime_root=runtime_root, goal_id=goal_id)
    lease_path = task_lease_path(runtime_root=runtime_root, goal_id=goal_id, todo_id=todo_id)
    at = now_utc()
    with exclusive_file_lock(lock_target):
        todo = require_task_lease_owner_allowed(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            owner=owner,
        )
        existing = read_lease(lease_path)
        assert_expected_version(existing, expected_version)
        existing_is_effective = bool(
            lease_is_active(existing, at=at)
            and task_lease_owner_constraint(
                todo,
                owner=(existing or {}).get("owner"),
                registered_agents=registered_agent_ids_from_registry(registry_path, goal_id),
            ).get("effective")
            is True
        )
        if existing_is_effective:
            if (
                existing.get("owner") == owner
                and existing.get("idempotency_key") == idempotency_key
            ):
                existing_write_scopes = normalize_required_write_scopes(
                    existing.get("write_scopes")
                )
                existing_ttl = existing.get("acquire_ttl_seconds")
                request_matches = set(existing_write_scopes) == set(normalized_write_scopes)
                if existing_ttl is not None:
                    request_matches = request_matches and int(existing_ttl) == ttl
                if not request_matches:
                    raise TaskLeaseError(
                        "idempotency key was reused with different acquire parameters",
                        code="idempotency_key_reuse",
                        payload={
                            "lease": existing,
                            "lease_path": str(lease_path),
                            "requested_write_scopes": normalized_write_scopes,
                            "requested_ttl_seconds": ttl,
                        },
                    )
                return {
                    "ok": True,
                    "schema_version": TASK_LEASE_SCHEMA_VERSION,
                    "action": "acquire",
                    "acquired": False,
                    "idempotent": True,
                    "lease": existing,
                    "lease_path": str(lease_path),
                }
            raise TaskLeaseError(
                "todo already has an active lease",
                code="todo_lease_conflict",
                payload={"lease": existing, "lease_path": str(lease_path)},
            )
        conflicts = active_conflicts(
            registry_path=registry_path,
            runtime_root=runtime_root,
            goal_id=goal_id,
            todo_id=todo_id,
            write_scopes=normalized_write_scopes,
            at=at,
        )
        if conflicts:
            raise TaskLeaseError(
                "write scope overlaps another active task lease",
                code="write_scope_conflict",
                payload={"conflicts": conflicts},
            )
        updated_at = isoformat(at)
        expires_at = isoformat(at + timedelta(seconds=ttl))
        lease = build_lease(
            goal_id=goal_id,
            todo_id=todo_id,
            owner=owner,
            idempotency_key=idempotency_key,
            write_scopes=normalized_write_scopes,
            acquire_ttl_seconds=ttl,
            version=int((existing or {}).get("version") or 0) + 1,
            acquired_at=updated_at,
            updated_at=updated_at,
            expires_at=expires_at,
        )
        lease_dir.mkdir(parents=True, exist_ok=True)
        write_lease(lease_path, lease)
        return {
            "ok": True,
            "schema_version": TASK_LEASE_SCHEMA_VERSION,
            "action": "acquire",
            "acquired": True,
            "idempotent": False,
            "lease": lease,
            "lease_path": str(lease_path),
        }


def renew_task_lease(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
    owner: str,
    idempotency_key: str,
    ttl_seconds: int | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    goal_id = normalize_goal_id(goal_id)
    todo_id = normalize_lease_todo_id(todo_id)
    owner = normalize_owner(owner)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    ttl = normalize_ttl_seconds(ttl_seconds)
    lock_target = task_lease_lock_path(runtime_root=runtime_root, goal_id=goal_id)
    lease_path = task_lease_path(runtime_root=runtime_root, goal_id=goal_id, todo_id=todo_id)
    at = now_utc()
    with exclusive_file_lock(lock_target):
        require_task_lease_owner_allowed(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            owner=owner,
        )
        lease = read_lease(lease_path)
        assert_expected_version(lease, expected_version)
        if not lease_is_active(lease, at=at):
            raise TaskLeaseError("lease is missing or expired", code="lease_not_active")
        if lease.get("owner") != owner or lease.get("idempotency_key") != idempotency_key:
            raise TaskLeaseError("lease owner or idempotency key mismatch", code="lease_cas_mismatch")
        lease = dict(lease)
        lease["version"] = int(lease.get("version") or 0) + 1
        lease["updated_at"] = isoformat(at)
        lease["expires_at"] = isoformat(at + timedelta(seconds=ttl))
        write_lease(lease_path, lease)
        return {
            "ok": True,
            "schema_version": TASK_LEASE_SCHEMA_VERSION,
            "action": "renew",
            "renewed": True,
            "lease": lease,
            "lease_path": str(lease_path),
        }


def transfer_task_lease(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
    owner: str,
    idempotency_key: str,
    new_owner: str,
    new_idempotency_key: str,
    ttl_seconds: int | None = None,
    expected_version: int | None = None,
) -> dict[str, Any]:
    goal_id = normalize_goal_id(goal_id)
    todo_id = normalize_lease_todo_id(todo_id)
    owner = normalize_owner(owner)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    new_owner = normalize_owner(new_owner)
    new_idempotency_key = normalize_idempotency_key(new_idempotency_key)
    ttl = normalize_ttl_seconds(ttl_seconds)
    lock_target = task_lease_lock_path(runtime_root=runtime_root, goal_id=goal_id)
    lease_path = task_lease_path(runtime_root=runtime_root, goal_id=goal_id, todo_id=todo_id)
    at = now_utc()
    with exclusive_file_lock(lock_target):
        require_registered_task_lease_owner(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            owner=owner,
        )
        require_task_lease_owner_allowed(
            registry_path=registry_path,
            goal_id=goal_id,
            todo_id=todo_id,
            owner=new_owner,
        )
        lease = read_lease(lease_path)
        assert_expected_version(lease, expected_version)
        if not lease_is_active(lease, at=at):
            raise TaskLeaseError("lease is missing or expired", code="lease_not_active")
        if lease.get("owner") != owner or lease.get("idempotency_key") != idempotency_key:
            raise TaskLeaseError("lease owner or idempotency key mismatch", code="lease_cas_mismatch")
        lease = dict(lease)
        lease["owner"] = new_owner
        lease["idempotency_key"] = new_idempotency_key
        lease["version"] = int(lease.get("version") or 0) + 1
        lease["updated_at"] = isoformat(at)
        lease["expires_at"] = isoformat(at + timedelta(seconds=ttl))
        write_lease(lease_path, lease)
        return {
            "ok": True,
            "schema_version": TASK_LEASE_SCHEMA_VERSION,
            "action": "transfer",
            "transferred": True,
            "lease": lease,
            "lease_path": str(lease_path),
        }


def release_task_lease(
    *,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
    owner: str,
    idempotency_key: str,
    expected_version: int | None = None,
) -> dict[str, Any]:
    goal_id = normalize_goal_id(goal_id)
    todo_id = normalize_lease_todo_id(todo_id)
    owner = normalize_owner(owner)
    idempotency_key = normalize_idempotency_key(idempotency_key)
    lock_target = task_lease_lock_path(runtime_root=runtime_root, goal_id=goal_id)
    lease_path = task_lease_path(runtime_root=runtime_root, goal_id=goal_id, todo_id=todo_id)
    at = now_utc()
    with exclusive_file_lock(lock_target):
        lease = read_lease(lease_path)
        assert_expected_version(lease, expected_version)
        if not lease:
            return {
                "ok": True,
                "schema_version": TASK_LEASE_SCHEMA_VERSION,
                "action": "release",
                "released": False,
                "missing": True,
                "lease_path": str(lease_path),
            }
        if lease_is_active(lease, at=at) and (
            lease.get("owner") != owner or lease.get("idempotency_key") != idempotency_key
        ):
            raise TaskLeaseError("lease owner or idempotency key mismatch", code="lease_cas_mismatch")
        remove_lease(lease_path)
        return {
            "ok": True,
            "schema_version": TASK_LEASE_SCHEMA_VERSION,
            "action": "release",
            "released": True,
            "lease": lease,
            "lease_path": str(lease_path),
        }


def inspect_task_lease(
    *,
    registry_path: Path,
    runtime_root: Path,
    goal_id: str,
    todo_id: str,
) -> dict[str, Any]:
    goal_id = normalize_goal_id(goal_id)
    todo_id = normalize_lease_todo_id(todo_id)
    lease_path = task_lease_path(runtime_root=runtime_root, goal_id=goal_id, todo_id=todo_id)
    lease = read_lease(lease_path)
    active = lease_is_active(lease)
    executor_constraint: dict[str, Any] | None = None
    if active and lease:
        try:
            todo = task_lease_todo_projection(
                registry_path=registry_path,
                goal_id=goal_id,
                todo_id=todo_id,
            )
        except TaskLeaseError as exc:
            active = False
            executor_constraint = {
                "effective": False,
                "reason": exc.code,
            }
        else:
            executor_constraint = task_lease_owner_constraint(
                todo,
                owner=lease.get("owner"),
                registered_agents=registered_agent_ids_from_registry(registry_path, goal_id),
            )
            if executor_constraint.get("effective") is not True:
                active = False
            else:
                executor_constraint = None
    return {
        "ok": True,
        "schema_version": TASK_LEASE_SCHEMA_VERSION,
        "action": "inspect",
        "goal_id": goal_id,
        "todo_id": todo_id,
        "active": active,
        "lease": lease,
        "lease_path": str(lease_path),
        **({"executor_constraint": executor_constraint} if executor_constraint else {}),
    }
