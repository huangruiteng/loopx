"""Provider-neutral coordination decisions shared by current state writers.

Adapters normalize their persisted state while holding the existing lock, call
``decide``, and only then perform their current write.  A returned transition is
a proposal, not proof that any write committed.  Durable execution results and
storage outcomes deliberately live outside this module. Todo lifecycle admission,
ownership routing, terminal fences and task-lease acquire/renew/transfer/release
adapt to canonical pure TypeScript decisions;
Python retains typed snapshot/result projection rather than a second rule set.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from ..effect_runtime import effect_runtime_result


DecisionScope = tuple[str, str, str]


class HandoffMode(StrEnum):
    LEGACY = "legacy"
    SOFT_CLAIM = "soft_claim"
    HARD_LEASE = "hard_lease"


class TodoAction(StrEnum):
    CLAIM = "claim"
    UPDATE = "update"
    COMPLETE = "complete"
    SUPERSEDE = "supersede"


class LeaseAction(StrEnum):
    ACQUIRE = "acquire"
    RENEW = "renew"
    TRANSFER = "transfer"
    RELEASE = "release"


class DecisionOutcome(StrEnum):
    APPLY = "apply"
    NO_CHANGE = "no_change"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class OwnershipGate(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRE_HOLDER = "require_holder"
    DELEGATED_OVERRIDE = "delegated_override"


class LeaseFence(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    AUTO_ACQUIRE = "auto_acquire"
    DELEGATED_OVERRIDE = "delegated_override"


@dataclass(frozen=True)
class LifecycleGrant:
    agent_id: str
    actions: frozenset[str]
    requires_reason: bool = True


@dataclass(frozen=True)
class TodoSnapshot:
    todo_id: str
    status: str
    role: str
    task_class: str | None = None
    claimed_by: str | None = None
    excluded_agents: frozenset[str] = frozenset()
    bound_agent: str | None = None
    blocks_agent: str | None = None
    decision_scope: DecisionScope | None = None
    required_decision_scopes: frozenset[DecisionScope] = frozenset()
    unblocks_todo_id: str | None = None


@dataclass(frozen=True)
class LeaseSnapshot:
    present: bool = False
    active: bool = False
    status: str | None = None
    owner: str | None = None
    idempotency_key: str | None = None
    version: int = 0
    lease_epoch: int = 0
    write_scopes: tuple[str, ...] = ()
    acquire_ttl_seconds: int | None = None


@dataclass(frozen=True)
class OtherLeaseSnapshot:
    todo_id: str
    active: bool
    effective: bool
    write_scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoordinationSnapshot:
    handoff_mode: HandoffMode = HandoffMode.LEGACY
    registered_agents: tuple[str, ...] = ()
    lifecycle_grants: tuple[LifecycleGrant, ...] = ()
    todo: TodoSnapshot | None = None
    decision_target: TodoSnapshot | None = None
    lease: LeaseSnapshot | None = None
    other_leases: tuple[OtherLeaseSnapshot, ...] = ()
    active_claimed_todo_ids: tuple[str, ...] = ()
    active_lease_todo_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TodoMutationCommand:
    action: TodoAction
    actor_agent_id: str | None
    requested_claimed_by: str | None = None
    clear_claim: bool = False
    authority_action: str | None = None
    authority_reason: str | None = None
    decision_outcome: str | None = None
    ownership_mutation: bool = False
    lease_idempotency_key: str | None = None
    lease_expected_version: int | None = None
    allow_user_gate_auto_acquire: bool = False


@dataclass(frozen=True)
class LeaseAcquireCommand:
    owner: str
    idempotency_key: str
    ttl_seconds: int
    write_scopes: tuple[str, ...] = ()
    expected_version: int | None = None


@dataclass(frozen=True)
class LeaseRenewCommand:
    owner: str
    idempotency_key: str
    ttl_seconds: int
    expected_version: int | None = None


@dataclass(frozen=True)
class LeaseTransferCommand:
    owner: str
    idempotency_key: str
    new_owner: str
    new_idempotency_key: str
    ttl_seconds: int
    expected_version: int | None = None


@dataclass(frozen=True)
class LeaseReleaseCommand:
    owner: str
    idempotency_key: str
    expected_version: int | None = None


@dataclass(frozen=True)
class LeaseOwnerEligibilityCommand:
    owner: str | None


@dataclass(frozen=True)
class LeaseModeGateCommand:
    action: LeaseAction


@dataclass(frozen=True)
class TerminalFenceCommand:
    """Verify the lease side of an already-authorized terminal mutation."""

    actor_agent_id: str | None
    lease_idempotency_key: str | None = None
    lease_expected_version: int | None = None
    delegated_authority: bool = False
    allow_user_gate_auto_acquire: bool = False
    require_active_when_fence_supplied: bool = True


@dataclass(frozen=True)
class HandoffModeTransitionCommand:
    requested_mode: HandoffMode


CoordinationCommand = (
    TodoMutationCommand
    | LeaseAcquireCommand
    | LeaseRenewCommand
    | LeaseTransferCommand
    | LeaseReleaseCommand
    | LeaseOwnerEligibilityCommand
    | LeaseModeGateCommand
    | TerminalFenceCommand
    | HandoffModeTransitionCommand
)


@dataclass(frozen=True)
class TransitionPlan:
    outcome: DecisionOutcome
    code: str
    next_snapshot: CoordinationSnapshot | None = None
    authority_mode: str | None = None
    ownership_gate: OwnershipGate = OwnershipGate.NOT_REQUIRED
    lease_fence: LeaseFence = LeaseFence.NOT_REQUIRED
    idempotent: bool = False


def _result(
    outcome: DecisionOutcome,
    code: str,
    *,
    next_snapshot: CoordinationSnapshot | None = None,
    authority_mode: str | None = None,
    ownership_gate: OwnershipGate = OwnershipGate.NOT_REQUIRED,
    lease_fence: LeaseFence = LeaseFence.NOT_REQUIRED,
    idempotent: bool = False,
) -> TransitionPlan:
    return TransitionPlan(
        outcome=outcome,
        code=code,
        next_snapshot=next_snapshot,
        authority_mode=authority_mode,
        ownership_gate=ownership_gate,
        lease_fence=lease_fence,
        idempotent=idempotent,
    )


def _invalid_lease_snapshot(lease: LeaseSnapshot | None) -> bool:
    """Reject contradictory normalized states at the pure-core boundary."""

    return bool(
        lease is not None
        and lease.active
        and (not lease.present or lease.status == "released")
    )


def _lease_owner_rejection(
    snapshot: CoordinationSnapshot,
    owner: str | None,
) -> str | None:
    todo = snapshot.todo
    if todo is None:
        return "todo_not_found"
    if todo.status != "open":
        return "todo_not_open"
    if not owner:
        return "invalid_owner"
    if owner not in snapshot.registered_agents:
        return "owner_not_registered"
    if owner in todo.excluded_agents:
        return "owner_excluded_from_todo"
    if todo.claimed_by and todo.claimed_by != owner:
        return "owner_conflicts_with_claim"
    return None


def _lease_is_effective(
    snapshot: CoordinationSnapshot,
    lease: LeaseSnapshot | None,
) -> bool:
    return bool(
        lease is not None
        and lease.present
        and lease.active
        and _lease_owner_rejection(snapshot, lease.owner) is None
    )


def write_scopes_overlap(
    left: tuple[str, ...] | list[str],
    right: tuple[str, ...] | list[str],
) -> bool:
    """Return the canonical native overlap decision for normalized scopes."""

    payload = effect_runtime_result(
        "task_lease.write_scopes.overlap",
        {"left": list(left), "right": list(right)},
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("overlap"), bool):
        raise RuntimeError("native task-lease write-scope decision shape mismatch")
    return bool(payload["overlap"])


def _decision_scope_payload(scope: DecisionScope | None) -> dict[str, str] | None:
    if scope is None:
        return None
    return {
        "kind": scope[0],
        "granularity": scope[1],
        "scope_key": scope[2],
    }


def _todo_fact_payload(todo: TodoSnapshot) -> dict[str, Any]:
    return {
        "todo_id": todo.todo_id,
        "status": todo.status,
        "role": todo.role,
        "task_class": todo.task_class,
        "claimed_by": todo.claimed_by,
        "excluded_agents": sorted(todo.excluded_agents),
        "bound_agent": todo.bound_agent,
        "blocks_agent": todo.blocks_agent,
        "decision_scope": _decision_scope_payload(todo.decision_scope),
        "required_decision_scopes": [
            _decision_scope_payload(scope)
            for scope in sorted(todo.required_decision_scopes)
        ],
        "unblocks_todo_id": todo.unblocks_todo_id,
    }


def _lease_fact_payload(lease: LeaseSnapshot | None) -> dict[str, Any] | None:
    if lease is None:
        return None
    return {
        "present": lease.present,
        "active": lease.active,
        "status": lease.status,
        "owner": lease.owner,
        "idempotency_key": lease.idempotency_key,
        "version": lease.version,
        "lease_epoch": lease.lease_epoch,
        "write_scopes": list(lease.write_scopes),
        "acquire_ttl_seconds": lease.acquire_ttl_seconds,
    }


def _lease_fact_from_payload(value: Any) -> LeaseSnapshot | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeError("TypeScript terminal decision next_lease shape mismatch")
    return LeaseSnapshot(
        present=bool(value.get("present")),
        active=bool(value.get("active")),
        status=str(value["status"]) if value.get("status") is not None else None,
        owner=str(value["owner"]) if value.get("owner") is not None else None,
        idempotency_key=(
            str(value["idempotency_key"])
            if value.get("idempotency_key") is not None
            else None
        ),
        version=int(value.get("version") or 0),
        lease_epoch=int(value.get("lease_epoch") or 0),
        write_scopes=tuple(str(item) for item in value.get("write_scopes") or []),
        acquire_ttl_seconds=(
            int(value["acquire_ttl_seconds"])
            if value.get("acquire_ttl_seconds") is not None
            else None
        ),
    )


def _typescript_todo_decision(
    snapshot: CoordinationSnapshot,
    command: TodoMutationCommand,
) -> TransitionPlan:
    """Project the typed lifecycle decision; storage and locks stay with callers."""

    todo = snapshot.todo
    if todo is None:
        return _result(DecisionOutcome.REJECTED, "todo_not_found")
    terminal = command.action in {TodoAction.COMPLETE, TodoAction.SUPERSEDE}
    operation = "terminal" if terminal else "mutation"
    payload = effect_runtime_result(
        f"todo.{operation}.decide",
        {
            "schema_version": f"loopx_coordination_todo_{operation}_decision_request_v0",
            "command": command.action.value,
            "handoff_mode": snapshot.handoff_mode.value,
            "registered_agents": list(snapshot.registered_agents),
            "lifecycle_grants": [
                {
                    "agent_id": grant.agent_id,
                    "actions": sorted(grant.actions),
                    "requires_reason": grant.requires_reason,
                }
                for grant in snapshot.lifecycle_grants
            ],
            "todo": _todo_fact_payload(todo),
            "decision_target": (
                _todo_fact_payload(snapshot.decision_target)
                if snapshot.decision_target is not None
                else None
            ),
            "lease": _lease_fact_payload(snapshot.lease),
            "actor_agent_id": command.actor_agent_id,
            "authority_action": command.authority_action or command.action.value,
            "authority_reason": command.authority_reason,
            "decision_outcome": command.decision_outcome,
            "lease_idempotency_key": command.lease_idempotency_key,
            "lease_expected_version": command.lease_expected_version,
            "allow_user_gate_auto_acquire": command.allow_user_gate_auto_acquire,
            "requested_claimed_by": command.requested_claimed_by,
            "clear_claim": command.clear_claim,
            "ownership_mutation": command.ownership_mutation,
        },
    )
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        f"loopx_coordination_todo_{operation}_decision_result_v0"
    ):
        raise RuntimeError("TypeScript Todo lifecycle decision result shape mismatch")
    try:
        outcome = DecisionOutcome(str(payload["outcome"]))
        ownership_gate = OwnershipGate(str(payload["ownership_gate"]))
        lease_fence = LeaseFence(str(payload["lease_fence"]))
    except (KeyError, ValueError) as exc:
        raise RuntimeError(
            "TypeScript Todo lifecycle decision result shape mismatch"
        ) from exc
    next_snapshot = None
    if outcome is DecisionOutcome.APPLY:
        if payload.get("next_todo_status") != ("done" if terminal else todo.status):
            raise RuntimeError(
                "TypeScript Todo lifecycle decision returned invalid next Todo state"
            )
        next_lease_payload = payload.get("next_lease")
        next_snapshot = replace(
            snapshot,
            todo=replace(
                todo,
                status=str(payload["next_todo_status"]),
                claimed_by=(
                    todo.claimed_by if terminal else payload["next_todo_claimed_by"]
                ),
            ),
            lease=(
                snapshot.lease
                if next_lease_payload is None
                else _lease_fact_from_payload(next_lease_payload)
            ),
        )
    elif outcome is DecisionOutcome.NO_CHANGE:
        next_snapshot = snapshot
    return TransitionPlan(
        outcome=outcome,
        code=str(payload.get("code") or "terminal_decision_invalid"),
        next_snapshot=next_snapshot,
        authority_mode=(
            str(payload["authority_mode"])
            if payload.get("authority_mode") is not None
            else None
        ),
        ownership_gate=ownership_gate,
        lease_fence=lease_fence,
        idempotent=bool(payload.get("idempotent")),
    )


def ownership_gate_requirement(
    *,
    handoff_mode: HandoffMode,
    ownership_mutation: bool,
    authority_mode: str | None,
) -> OwnershipGate:
    """Route one claimed_by mutation on an existing todo into the holder gate.

    This is the single owner of the routing rule: only a hard_lease ownership
    mutation needs the holder gate, and the delegated orchestration override
    is the one audited door through it. Writers consult this instead of
    re-deriving the mode/door predicates at the edge.
    """

    payload = effect_runtime_result(
        "todo.ownership_gate.decide",
        {
            "handoff_mode": handoff_mode.value,
            "ownership_mutation": ownership_mutation,
            "authority_mode": authority_mode,
        },
    )
    if not isinstance(payload, dict):
        raise RuntimeError("TypeScript ownership gate result shape mismatch")
    return OwnershipGate(payload["ownership_gate"])


def _typescript_terminal_fence(
    snapshot: CoordinationSnapshot,
    command: TerminalFenceCommand,
) -> TransitionPlan:
    if snapshot.todo is None:
        return _result(DecisionOutcome.REJECTED, "todo_not_found")
    payload = effect_runtime_result(
        "task_lease.terminal_fence.decide",
        {
            "schema_version": "loopx_coordination_terminal_fence_request_v0",
            "todo": _todo_fact_payload(snapshot.todo),
            "lease": _lease_fact_payload(snapshot.lease),
            "registered_agents": list(snapshot.registered_agents),
            "handoff_mode": snapshot.handoff_mode.value,
            "actor_agent_id": command.actor_agent_id,
            "lease_idempotency_key": command.lease_idempotency_key,
            "lease_expected_version": command.lease_expected_version,
            "delegated_authority": command.delegated_authority,
            "allow_user_gate_auto_acquire": command.allow_user_gate_auto_acquire,
            "require_active_when_fence_supplied": command.require_active_when_fence_supplied,
        },
    )
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        "loopx_coordination_terminal_fence_result_v0"
    ):
        raise RuntimeError("TypeScript terminal fence result shape mismatch")
    outcome = DecisionOutcome(payload["outcome"])
    next_snapshot = None
    if outcome is DecisionOutcome.APPLY:
        next_snapshot = replace(
            snapshot,
            lease=(
                snapshot.lease
                if payload["next_lease"] is None
                else _lease_fact_from_payload(payload["next_lease"])
            ),
        )
    return TransitionPlan(
        outcome=outcome,
        code=payload["code"],
        next_snapshot=next_snapshot,
        lease_fence=LeaseFence(payload["lease_fence"]),
    )


def _lease_handoff_rejection(snapshot: CoordinationSnapshot) -> str | None:
    if snapshot.handoff_mode is HandoffMode.SOFT_CLAIM:
        return "handoff_mode_forbids_lease"
    return None


def _decide_lease_mode_gate(
    snapshot: CoordinationSnapshot,
    command: LeaseModeGateCommand,
) -> TransitionPlan:
    if (
        command.action is not LeaseAction.RELEASE
        and (rejection := _lease_handoff_rejection(snapshot)) is not None
    ):
        return _result(DecisionOutcome.REJECTED, rejection)
    return _result(
        DecisionOutcome.APPLY,
        "lease_mutation_allowed",
        next_snapshot=snapshot,
    )


def _decide_lease_owner_eligibility(
    snapshot: CoordinationSnapshot,
    command: LeaseOwnerEligibilityCommand,
) -> TransitionPlan:
    rejection = _lease_owner_rejection(snapshot, command.owner)
    if rejection is not None:
        return _result(DecisionOutcome.REJECTED, rejection)
    return _result(
        DecisionOutcome.APPLY,
        "lease_owner_allowed",
        next_snapshot=snapshot,
    )


def _decide_acquire(
    snapshot: CoordinationSnapshot,
    command: LeaseAcquireCommand,
) -> TransitionPlan:
    todo = snapshot.todo
    lease = snapshot.lease
    payload = effect_runtime_result(
        "task_lease.acquire.decide",
        {
            "handoff_mode": snapshot.handoff_mode.value,
            "registered_agents": list(snapshot.registered_agents),
            "todo": (
                {
                    "todo_id": todo.todo_id,
                    "status": todo.status,
                    "claimed_by": todo.claimed_by,
                    "excluded_agents": sorted(todo.excluded_agents),
                }
                if todo is not None
                else None
            ),
            "lease": (
                {
                    "present": lease.present,
                    "active": lease.active,
                    "effective": _lease_is_effective(snapshot, lease),
                    "status": lease.status,
                    "owner": lease.owner,
                    "idempotency_key": lease.idempotency_key,
                    "version": lease.version,
                    "lease_epoch": lease.lease_epoch,
                    "write_scopes": list(lease.write_scopes),
                    "acquire_ttl_seconds": lease.acquire_ttl_seconds,
                }
                if lease is not None
                else None
            ),
            "other_leases": [
                {
                    "todo_id": other.todo_id,
                    "active": other.active,
                    "effective": other.effective,
                    "write_scopes": list(other.write_scopes),
                }
                for other in snapshot.other_leases
            ],
            "command": {
                "owner": command.owner,
                "idempotency_key": command.idempotency_key,
                "ttl_seconds": command.ttl_seconds,
                "write_scopes": list(command.write_scopes),
                "expected_version": command.expected_version,
            },
        },
    )
    if not isinstance(payload, dict):
        raise RuntimeError("native task-lease acquire decision must return an object")
    raw_outcome = payload.get("outcome")
    raw_code = payload.get("code")
    raw_idempotent = payload.get("idempotent")
    if (
        not isinstance(raw_outcome, str)
        or not isinstance(raw_code, str)
        or not isinstance(raw_idempotent, bool)
    ):
        raise RuntimeError("native task-lease acquire decision shape mismatch")
    try:
        outcome = DecisionOutcome(raw_outcome)
    except ValueError as exc:
        raise RuntimeError(
            f"native task-lease acquire decision has unsupported outcome: {raw_outcome}"
        ) from exc
    next_snapshot: CoordinationSnapshot | None = None
    if outcome is DecisionOutcome.APPLY:
        raw_next = payload.get("next_lease")
        if not isinstance(raw_next, dict):
            raise RuntimeError("native task-lease acquire apply result omitted next_lease")
        next_lease = _native_acquire_lease_snapshot(raw_next)
        next_snapshot = replace(snapshot, lease=next_lease)
    elif outcome is DecisionOutcome.NO_CHANGE:
        next_snapshot = snapshot
    return _result(
        outcome,
        raw_code,
        next_snapshot=next_snapshot,
        idempotent=raw_idempotent,
    )


def _native_acquire_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeError(f"native task-lease acquire {label} must be non-negative")
    return int(value)


def _native_acquire_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"native task-lease acquire {label} must be non-empty")
    return value


def _native_acquire_lease_snapshot(value: dict[str, Any]) -> LeaseSnapshot:
    if value.get("present") is not True or value.get("active") is not True:
        raise RuntimeError("native task-lease acquire apply lease must be active")
    raw_scopes = value.get("write_scopes")
    if not isinstance(raw_scopes, list) or any(
        not isinstance(scope, str) for scope in raw_scopes
    ):
        raise RuntimeError("native task-lease acquire write_scopes shape mismatch")
    return LeaseSnapshot(
        present=True,
        active=True,
        status=_native_acquire_string(value.get("status"), "status"),
        owner=_native_acquire_string(value.get("owner"), "owner"),
        idempotency_key=_native_acquire_string(
            value.get("idempotency_key"), "idempotency_key"
        ),
        version=_native_acquire_integer(value.get("version"), "version"),
        lease_epoch=_native_acquire_integer(
            value.get("lease_epoch"), "lease_epoch"
        ),
        write_scopes=tuple(raw_scopes),
        acquire_ttl_seconds=_native_acquire_integer(
            value.get("acquire_ttl_seconds"), "acquire_ttl_seconds"
        ),
    )


def _native_lifecycle_lease_snapshot(value: dict[str, Any]) -> LeaseSnapshot:
    present = value.get("present")
    active = value.get("active")
    if not isinstance(present, bool) or not isinstance(active, bool):
        raise RuntimeError(
            "native task-lease lifecycle lease presence must be boolean"
        )
    status = value.get("status")
    owner = value.get("owner")
    idempotency_key = value.get("idempotency_key")
    if status is not None and not isinstance(status, str):
        raise RuntimeError("native task-lease lifecycle status must be a string")
    if owner is not None and not isinstance(owner, str):
        raise RuntimeError("native task-lease lifecycle owner must be a string")
    if idempotency_key is not None and not isinstance(idempotency_key, str):
        raise RuntimeError(
            "native task-lease lifecycle idempotency_key must be a string"
        )
    raw_scopes = value.get("write_scopes")
    if not isinstance(raw_scopes, list) or any(
        not isinstance(scope, str) for scope in raw_scopes
    ):
        raise RuntimeError("native task-lease lifecycle write_scopes shape mismatch")
    raw_ttl = value.get("acquire_ttl_seconds")
    if raw_ttl is not None:
        raw_ttl = _native_acquire_integer(raw_ttl, "acquire_ttl_seconds")
    return LeaseSnapshot(
        present=present,
        active=active,
        status=status,
        owner=owner,
        idempotency_key=idempotency_key,
        version=_native_acquire_integer(value.get("version"), "version"),
        lease_epoch=_native_acquire_integer(
            value.get("lease_epoch"), "lease_epoch"
        ),
        write_scopes=tuple(raw_scopes),
        acquire_ttl_seconds=raw_ttl,
    )


def _decide_native_lifecycle(
    snapshot: CoordinationSnapshot,
    command: LeaseRenewCommand | LeaseTransferCommand | LeaseReleaseCommand,
) -> TransitionPlan:
    todo = snapshot.todo
    lease = snapshot.lease
    if isinstance(command, LeaseRenewCommand):
        operation = "renew"
        ttl_seconds: int | None = command.ttl_seconds
        new_owner: str | None = None
        new_idempotency_key: str | None = None
    elif isinstance(command, LeaseTransferCommand):
        operation = "transfer"
        ttl_seconds = command.ttl_seconds
        new_owner = command.new_owner
        new_idempotency_key = command.new_idempotency_key
    else:
        operation = "release"
        ttl_seconds = None
        new_owner = None
        new_idempotency_key = None
    payload = effect_runtime_result(
        "task_lease.lifecycle.decide",
        {
            "handoff_mode": snapshot.handoff_mode.value,
            "registered_agents": list(snapshot.registered_agents),
            "todo": (
                {
                    "todo_id": todo.todo_id,
                    "status": todo.status,
                    "claimed_by": todo.claimed_by,
                    "excluded_agents": sorted(todo.excluded_agents),
                }
                if todo is not None
                else None
            ),
            "lease": (
                {
                    "present": lease.present,
                    "active": lease.active,
                    "status": lease.status,
                    "owner": lease.owner,
                    "idempotency_key": lease.idempotency_key,
                    "version": lease.version,
                    "lease_epoch": lease.lease_epoch,
                    "write_scopes": list(lease.write_scopes),
                    "acquire_ttl_seconds": lease.acquire_ttl_seconds,
                }
                if lease is not None
                else None
            ),
            "command": {
                "operation": operation,
                "owner": command.owner,
                "idempotency_key": command.idempotency_key,
                "expected_version": command.expected_version,
                "ttl_seconds": ttl_seconds,
                "new_owner": new_owner,
                "new_idempotency_key": new_idempotency_key,
            },
        },
    )
    if not isinstance(payload, dict):
        raise RuntimeError("native task-lease lifecycle decision shape mismatch")
    raw_outcome = payload.get("outcome")
    raw_code = payload.get("code")
    raw_idempotent = payload.get("idempotent")
    if not isinstance(raw_outcome, str) or not isinstance(raw_code, str):
        raise RuntimeError("native task-lease lifecycle decision omitted outcome")
    if not isinstance(raw_idempotent, bool):
        raise RuntimeError(
            "native task-lease lifecycle decision idempotent must be boolean"
        )
    try:
        outcome = DecisionOutcome(raw_outcome)
    except ValueError as exc:
        raise RuntimeError(
            f"native task-lease lifecycle decision has unsupported outcome: {raw_outcome}"
        ) from exc
    next_snapshot: CoordinationSnapshot | None = None
    if outcome is DecisionOutcome.APPLY:
        raw_next = payload.get("next_lease")
        if not isinstance(raw_next, dict):
            raise RuntimeError(
                "native task-lease lifecycle apply result omitted next_lease"
            )
        next_snapshot = replace(
            snapshot,
            lease=_native_lifecycle_lease_snapshot(raw_next),
        )
    elif outcome is DecisionOutcome.NO_CHANGE:
        next_snapshot = snapshot
    return _result(
        outcome,
        raw_code,
        next_snapshot=next_snapshot,
        idempotent=raw_idempotent,
    )


def _decide_renew(
    snapshot: CoordinationSnapshot,
    command: LeaseRenewCommand,
) -> TransitionPlan:
    return _decide_native_lifecycle(snapshot, command)


def _decide_transfer(
    snapshot: CoordinationSnapshot,
    command: LeaseTransferCommand,
) -> TransitionPlan:
    return _decide_native_lifecycle(snapshot, command)


def _decide_release(
    snapshot: CoordinationSnapshot,
    command: LeaseReleaseCommand,
) -> TransitionPlan:
    return _decide_native_lifecycle(snapshot, command)


def _decide_handoff_transition(
    snapshot: CoordinationSnapshot,
    command: HandoffModeTransitionCommand,
) -> TransitionPlan:
    if snapshot.handoff_mode is command.requested_mode:
        return _result(
            DecisionOutcome.NO_CHANGE,
            "handoff_mode_unchanged",
            next_snapshot=snapshot,
            idempotent=True,
        )
    if snapshot.active_claimed_todo_ids or snapshot.active_lease_todo_ids:
        return _result(DecisionOutcome.REJECTED, "handoff_mode_not_quiescent")
    return _result(
        DecisionOutcome.APPLY,
        "handoff_mode_transition",
        next_snapshot=replace(snapshot, handoff_mode=command.requested_mode),
    )


def decide(
    snapshot: CoordinationSnapshot,
    command: CoordinationCommand,
) -> TransitionPlan:
    """Evaluate one normalized command without reading or writing state."""

    if isinstance(command, LeaseAcquireCommand):
        return _decide_acquire(snapshot, command)
    if _invalid_lease_snapshot(snapshot.lease):
        return _result(DecisionOutcome.REJECTED, "invalid_lease_snapshot")
    if isinstance(command, TodoMutationCommand):
        return _typescript_todo_decision(snapshot, command)
    if isinstance(command, LeaseRenewCommand):
        return _decide_renew(snapshot, command)
    if isinstance(command, LeaseTransferCommand):
        return _decide_transfer(snapshot, command)
    if isinstance(command, LeaseReleaseCommand):
        return _decide_release(snapshot, command)
    if isinstance(command, LeaseOwnerEligibilityCommand):
        return _decide_lease_owner_eligibility(snapshot, command)
    if isinstance(command, LeaseModeGateCommand):
        return _decide_lease_mode_gate(snapshot, command)
    if isinstance(command, TerminalFenceCommand):
        return _typescript_terminal_fence(snapshot, command)
    if isinstance(command, HandoffModeTransitionCommand):
        return _decide_handoff_transition(snapshot, command)
    raise TypeError(f"unsupported coordination command: {type(command).__name__}")
