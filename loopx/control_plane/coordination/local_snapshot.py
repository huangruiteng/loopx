"""Normalize current local-state records for the coordination core.

This is the behavior-preserving edge between the existing Markdown/JSON
writers and the provider-neutral domain model.  It performs no I/O and owns no
authority decision.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..todos.contract import (
    normalize_required_write_scopes,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
)
from .authority_core import (
    CoordinationSnapshot,
    HandoffMode,
    LeaseSnapshot,
    OtherLeaseSnapshot,
    TodoSnapshot,
)


def _scope_identity(scope: Any) -> tuple[str, str, str] | None:
    normalized = normalize_todo_decision_scope(scope)
    if not normalized:
        return None
    return (
        normalized["kind"],
        normalized["granularity"],
        normalized["scope_key"],
    )


def todo_snapshot_from_mapping(
    todo: Mapping[str, Any] | None,
    *,
    infer_status_from_done: bool = False,
) -> TodoSnapshot | None:
    if todo is None:
        return None
    status = str(todo.get("status") or "").strip().lower()
    if not status and infer_status_from_done:
        status = "done" if todo.get("done") is True else "open"
    required_scopes = frozenset(
        identity
        for scope in normalize_todo_required_decision_scopes(
            todo.get("required_decision_scopes")
        )
        if (identity := _scope_identity(scope)) is not None
    )
    return TodoSnapshot(
        todo_id=normalize_todo_id(todo.get("todo_id")) or "",
        status=status,
        role=str(todo.get("role") or ""),
        task_class=str(todo.get("task_class") or "") or None,
        claimed_by=normalize_todo_claimed_by(todo.get("claimed_by")),
        excluded_agents=frozenset(
            normalize_todo_excluded_agents(todo.get("excluded_agents"))
        ),
        bound_agent=normalize_todo_bound_agent(todo.get("bound_agent")),
        blocks_agent=normalize_todo_blocks_agent(todo.get("blocks_agent")),
        decision_scope=_scope_identity(todo.get("decision_scope")),
        required_decision_scopes=required_scopes,
        unblocks_todo_id=normalize_todo_id(todo.get("unblocks_todo_id")),
    )


def lease_snapshot_from_mapping(
    lease: Mapping[str, Any] | None,
    *,
    active: bool,
    version: int = 0,
    lease_epoch: int = 0,
    acquire_ttl_seconds: int | None = None,
) -> LeaseSnapshot | None:
    if lease is None:
        return None
    return LeaseSnapshot(
        present=True,
        active=active,
        status=str(lease.get("status") or "") or None,
        owner=normalize_todo_claimed_by(lease.get("owner")),
        idempotency_key=str(lease.get("idempotency_key") or "") or None,
        version=version,
        lease_epoch=lease_epoch,
        write_scopes=tuple(
            normalize_required_write_scopes(lease.get("write_scopes"))
        ),
        acquire_ttl_seconds=acquire_ttl_seconds,
    )


def lease_coordination_snapshot(
    *,
    handoff_mode: str,
    registered_agents: Sequence[str] = (),
    todo: Mapping[str, Any] | None = None,
    lease: Mapping[str, Any] | None = None,
    lease_active: bool = False,
    lease_version: int = 0,
    lease_epoch: int = 0,
    lease_acquire_ttl_seconds: int | None = None,
    conflicts: Sequence[Mapping[str, Any]] = (),
) -> CoordinationSnapshot:
    normalized_todo = dict(todo) if todo is not None else None
    if normalized_todo is not None:
        # A successful owner guard is this adapter's input contract.
        normalized_todo.setdefault("status", "open")
        normalized_todo.setdefault("role", "agent")
    return CoordinationSnapshot(
        handoff_mode=HandoffMode(handoff_mode),
        registered_agents=tuple(registered_agents),
        todo=todo_snapshot_from_mapping(normalized_todo),
        lease=lease_snapshot_from_mapping(
            lease,
            active=lease_active,
            version=lease_version,
            lease_epoch=lease_epoch,
            acquire_ttl_seconds=lease_acquire_ttl_seconds,
        ),
        other_leases=tuple(
            OtherLeaseSnapshot(
                todo_id=str(conflict.get("todo_id") or ""),
                active=True,
                effective=True,
                write_scopes=tuple(
                    normalize_required_write_scopes(
                        conflict.get("write_scopes")
                    )
                ),
            )
            for conflict in conflicts
        ),
    )


def lease_transition_error(
    *,
    code: str,
    action: str,
    lease: Mapping[str, Any] | None,
    lease_path: str,
    expected_version: int | None = None,
    requested_write_scopes: Sequence[str] = (),
    requested_ttl_seconds: int | None = None,
    conflicts: Sequence[Mapping[str, Any]] = (),
    idempotency_reuse_kind: str | None = None,
) -> tuple[str, dict[str, Any]]:
    if code == "version_required":
        return (
            f"task lease {action} requires the current lease version",
            {"action": action},
        )
    if code == "version_mismatch":
        actual = int((lease or {}).get("version") or 0)
        return (
            f"lease version mismatch: expected {expected_version}, got {actual}",
            {"expected_version": expected_version, "actual_version": actual},
        )
    if code == "idempotency_key_reuse":
        if idempotency_reuse_kind == "retired":
            return (
                "idempotency key belongs to an expired or released lease "
                "generation; a new execution must use a new key",
                {"lease": lease, "lease_path": lease_path},
            )
        if idempotency_reuse_kind == "transfer":
            return (
                "lease transfer must mint a new execution idempotency key",
                {"lease": lease, "lease_path": lease_path},
            )
        return (
            "idempotency key was reused with different acquire parameters",
            {
                "lease": lease,
                "lease_path": lease_path,
                "requested_write_scopes": list(requested_write_scopes),
                "requested_ttl_seconds": requested_ttl_seconds,
            },
        )
    if code == "todo_lease_conflict":
        return (
            "todo already has an active lease",
            {"lease": lease, "lease_path": lease_path},
        )
    if code == "write_scope_conflict":
        return (
            "write scope overlaps another active task lease",
            {"conflicts": [dict(conflict) for conflict in conflicts]},
        )
    if code == "lease_not_active":
        return "lease is missing or expired", {}
    if code == "lease_cas_mismatch":
        return "lease owner or idempotency key mismatch", {}
    return (
        f"task lease {action} rejected by authority core: {code}",
        {"lease": lease, "lease_path": lease_path},
    )
