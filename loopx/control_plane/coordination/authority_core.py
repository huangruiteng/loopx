"""Pure coordination decisions shared by the current state writers.

Adapters normalize their persisted state while holding the existing lock, call
``decide``, and only then perform their current write.  A returned transition is
a proposal, not proof that any write committed.  Durable execution results and
storage outcomes deliberately live outside this module.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, replace
from enum import StrEnum


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


def _actual_version(lease: LeaseSnapshot | None) -> int:
    return lease.version if lease is not None and lease.present else 0


def _invalid_lease_snapshot(lease: LeaseSnapshot | None) -> bool:
    """Reject contradictory normalized states at the pure-core boundary."""

    return bool(
        lease is not None
        and lease.active
        and (not lease.present or lease.status == "released")
    )


def _version_conflict(
    lease: LeaseSnapshot | None,
    expected_version: int | None,
) -> bool:
    return expected_version is not None and _actual_version(lease) != expected_version


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


def _scope_has_glob(scope: str) -> bool:
    return any(token in scope for token in ("*", "?", "["))


def _scope_literal_prefix(scope: str) -> str:
    indexes = [
        scope.find(token)
        for token in ("*", "?", "[")
        if scope.find(token) >= 0
    ]
    return scope[: min(indexes)] if indexes else scope


def _scope_pair_overlaps(left: str, right: str) -> bool:
    if left == right:
        return True
    if left in {"*", "**", "./"} or right in {"*", "**", "./"}:
        return True
    left_glob, right_glob = _scope_has_glob(left), _scope_has_glob(right)
    if left_glob and not right_glob:
        prefix = _scope_literal_prefix(left)
        return fnmatch.fnmatchcase(right, left) or (
            prefix.endswith("/") and right.rstrip("/") == prefix.rstrip("/")
        )
    if right_glob and not left_glob:
        prefix = _scope_literal_prefix(right)
        return fnmatch.fnmatchcase(left, right) or (
            prefix.endswith("/") and left.rstrip("/") == prefix.rstrip("/")
        )
    if left_glob and right_glob:
        left_prefix = _scope_literal_prefix(left)
        right_prefix = _scope_literal_prefix(right)
        return bool(
            not left_prefix
            or not right_prefix
            or left_prefix.startswith(right_prefix)
            or right_prefix.startswith(left_prefix)
        )
    left_root, right_root = left.rstrip("/"), right.rstrip("/")
    return bool(
        (left.endswith("/") and right.startswith(left_root + "/"))
        or (right.endswith("/") and left.startswith(right_root + "/"))
    )


def write_scopes_overlap(
    left: tuple[str, ...] | list[str],
    right: tuple[str, ...] | list[str],
) -> bool:
    """Return whether two already-normalized scope sets overlap."""

    if not left or not right:
        return False
    return any(_scope_pair_overlaps(a, b) for a in left for b in right)


def _exact_user_gate_override(
    snapshot: CoordinationSnapshot,
    command: TodoMutationCommand,
) -> bool:
    todo = snapshot.todo
    target = snapshot.decision_target
    return bool(
        todo is not None
        and target is not None
        and command.action is TodoAction.COMPLETE
        and todo.role == "user"
        and todo.task_class == "user_gate"
        and command.decision_outcome
        and todo.decision_scope is not None
        and todo.unblocks_todo_id == target.todo_id
        and todo.decision_scope in target.required_decision_scopes
    )


def _todo_after_command(
    todo: TodoSnapshot,
    command: TodoMutationCommand,
) -> TodoSnapshot:
    if command.action in {TodoAction.COMPLETE, TodoAction.SUPERSEDE}:
        return replace(todo, status="done")
    if command.action is TodoAction.CLAIM:
        return replace(todo, claimed_by=command.requested_claimed_by)
    if command.ownership_mutation:
        return replace(
            todo,
            claimed_by=(None if command.clear_claim else command.requested_claimed_by),
        )
    return todo


def _authority_for_todo(
    snapshot: CoordinationSnapshot,
    command: TodoMutationCommand,
) -> tuple[str | None, str | None]:
    """Return ``(authority_mode, rejection_code)``."""

    todo = snapshot.todo
    if todo is None:
        return None, "todo_not_found"
    actor = command.actor_agent_id
    if len(snapshot.registered_agents) <= 1:
        if actor and snapshot.registered_agents and actor not in snapshot.registered_agents:
            return None, "actor_not_registered"
        return "single_agent_compatibility", None
    if _exact_user_gate_override(snapshot, command):
        return "exact_user_gate_decision_scope_override", None
    if not actor:
        return None, "actor_required"
    if actor not in snapshot.registered_agents:
        return None, "actor_not_registered"
    if actor in todo.excluded_agents:
        return None, "actor_excluded"
    bound_agent = todo.bound_agent
    if not bound_agent and todo.role == "user":
        bound_agent = todo.blocks_agent
    if bound_agent and bound_agent != actor:
        return None, "bound_agent_mismatch"
    if todo.claimed_by and todo.claimed_by != actor:
        action = command.authority_action or command.action.value
        grant = next(
            (item for item in snapshot.lifecycle_grants if item.agent_id == actor),
            None,
        )
        if grant is None:
            return None, "claim_owner_mismatch"
        if action not in grant.actions:
            return None, "delegation_action_not_granted"
        if grant.requires_reason and not str(command.authority_reason or "").strip():
            return None, "delegation_reason_required"
        return "delegated_orchestration_override", None
    if (
        command.action is TodoAction.CLAIM
        and command.requested_claimed_by != actor
    ):
        return None, "claim_actor_mismatch"
    return "registered_peer_actor", None


def _terminal_fence_decision(
    snapshot: CoordinationSnapshot,
    *,
    actor_agent_id: str | None,
    lease_idempotency_key: str | None,
    lease_expected_version: int | None,
    delegated_authority: bool,
    allow_user_gate_auto_acquire: bool,
    require_active_when_fence_supplied: bool,
) -> TransitionPlan:
    todo = snapshot.todo
    assert todo is not None
    lease = snapshot.lease
    time_active = bool(lease and lease.present and lease.active)
    effective = _lease_is_effective(snapshot, lease)
    explicit_fence = bool(
        lease_idempotency_key is not None or lease_expected_version is not None
    )
    auto_acquire = bool(
        snapshot.handoff_mode is HandoffMode.HARD_LEASE
        and not delegated_authority
        and allow_user_gate_auto_acquire
        and todo.role == "user"
        and todo.task_class == "user_gate"
    )
    if auto_acquire and not effective and not time_active:
        rejection = _lease_owner_rejection(snapshot, actor_agent_id)
        if rejection is not None:
            return _result(
                DecisionOutcome.REJECTED,
                "handoff_mode_requires_lease",
                lease_fence=LeaseFence.AUTO_ACQUIRE,
            )
        existing = lease or LeaseSnapshot()
        acquired = LeaseSnapshot(
            present=True,
            active=True,
            status="active",
            owner=actor_agent_id,
            idempotency_key=lease_idempotency_key or f"auto-{todo.todo_id}",
            version=_actual_version(existing) + 1,
            lease_epoch=existing.lease_epoch + 1,
            write_scopes=(),
            acquire_ttl_seconds=2700,
        )
        next_snapshot = replace(
            snapshot,
            lease=replace(acquired, active=False, status="released"),
        )
        return _result(
            DecisionOutcome.APPLY,
            "terminal_fence_verified",
            next_snapshot=next_snapshot,
            lease_fence=LeaseFence.AUTO_ACQUIRE,
        )
    if not effective:
        if (
            snapshot.handoff_mode is HandoffMode.HARD_LEASE
            and not delegated_authority
        ):
            return _result(
                DecisionOutcome.REJECTED,
                (
                    "handoff_mode_lease_claim_divergence"
                    if time_active
                    else "handoff_mode_requires_lease"
                ),
                lease_fence=LeaseFence.REQUIRED,
            )
        if explicit_fence and require_active_when_fence_supplied:
            return _result(
                DecisionOutcome.REJECTED,
                "lease_not_active",
            )
        return _result(
            DecisionOutcome.APPLY,
            "terminal_fence_not_required",
            next_snapshot=snapshot,
            lease_fence=(
                LeaseFence.DELEGATED_OVERRIDE
                if delegated_authority
                and snapshot.handoff_mode is HandoffMode.HARD_LEASE
                else LeaseFence.NOT_REQUIRED
            ),
        )
    assert lease is not None
    if lease_idempotency_key is None:
        return _result(
            DecisionOutcome.REJECTED,
            "lease_fence_required",
            lease_fence=LeaseFence.REQUIRED,
        )
    if (
        lease.owner != actor_agent_id
        or lease.idempotency_key != lease_idempotency_key
    ):
        return _result(
            DecisionOutcome.REJECTED,
            "lease_cas_mismatch",
            lease_fence=LeaseFence.REQUIRED,
        )
    if lease_expected_version is None:
        return _result(
            DecisionOutcome.REJECTED,
            "version_required",
            lease_fence=LeaseFence.REQUIRED,
        )
    if _version_conflict(lease, lease_expected_version):
        return _result(
            DecisionOutcome.CONFLICT,
            "version_mismatch",
            lease_fence=LeaseFence.REQUIRED,
        )
    next_snapshot = replace(
        snapshot,
        lease=replace(lease, active=False, status="released"),
    )
    return _result(
        DecisionOutcome.APPLY,
        "terminal_fence_verified",
        next_snapshot=next_snapshot,
        lease_fence=LeaseFence.REQUIRED,
    )


def _terminal_decision(
    snapshot: CoordinationSnapshot,
    command: TodoMutationCommand,
    *,
    authority_mode: str,
    ownership_gate: OwnershipGate,
) -> TransitionPlan:
    todo = snapshot.todo
    assert todo is not None
    if todo.status == "done":
        return _result(
            DecisionOutcome.NO_CHANGE,
            "terminal_replay",
            next_snapshot=snapshot,
            authority_mode=authority_mode,
            ownership_gate=ownership_gate,
            idempotent=True,
        )
    fence = _terminal_fence_decision(
        snapshot,
        actor_agent_id=command.actor_agent_id,
        lease_idempotency_key=command.lease_idempotency_key,
        lease_expected_version=command.lease_expected_version,
        delegated_authority=(
            authority_mode == "delegated_orchestration_override"
        ),
        allow_user_gate_auto_acquire=(
            command.allow_user_gate_auto_acquire
        ),
        require_active_when_fence_supplied=True,
    )
    if fence.outcome is not DecisionOutcome.APPLY:
        return replace(
            fence,
            authority_mode=authority_mode,
            ownership_gate=ownership_gate,
        )
    next_snapshot = fence.next_snapshot or snapshot
    return replace(
        fence,
        code="terminal_transition",
        next_snapshot=replace(
            next_snapshot,
            todo=_todo_after_command(todo, command),
        ),
        authority_mode=authority_mode,
        ownership_gate=ownership_gate,
    )


def _decide_todo(
    snapshot: CoordinationSnapshot,
    command: TodoMutationCommand,
) -> TransitionPlan:
    authority_mode, rejection = _authority_for_todo(snapshot, command)
    if rejection is not None:
        return _result(DecisionOutcome.REJECTED, rejection)
    assert authority_mode is not None and snapshot.todo is not None
    ownership_gate = OwnershipGate.NOT_REQUIRED
    if (
        command.ownership_mutation
        and snapshot.handoff_mode is HandoffMode.HARD_LEASE
    ):
        if authority_mode == "delegated_orchestration_override":
            ownership_gate = OwnershipGate.DELEGATED_OVERRIDE
        else:
            ownership_gate = OwnershipGate.REQUIRE_HOLDER
            lease = snapshot.lease
            if not lease or not lease.present or not lease.active:
                return _result(
                    DecisionOutcome.REJECTED,
                    "handoff_mode_requires_lease",
                    authority_mode=authority_mode,
                    ownership_gate=ownership_gate,
                )
            if lease.owner != command.actor_agent_id:
                return _result(
                    DecisionOutcome.REJECTED,
                    "handoff_mode_requires_lease",
                    authority_mode=authority_mode,
                    ownership_gate=ownership_gate,
                )
    if command.action in {TodoAction.COMPLETE, TodoAction.SUPERSEDE}:
        return _terminal_decision(
            snapshot,
            command,
            authority_mode=authority_mode,
            ownership_gate=ownership_gate,
        )
    return _result(
        DecisionOutcome.APPLY,
        "todo_transition",
        next_snapshot=replace(
            snapshot,
            todo=_todo_after_command(snapshot.todo, command),
        ),
        authority_mode=authority_mode,
        ownership_gate=ownership_gate,
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
    handoff_rejection = _lease_handoff_rejection(snapshot)
    if handoff_rejection:
        return _result(DecisionOutcome.REJECTED, handoff_rejection)
    owner_rejection = _lease_owner_rejection(snapshot, command.owner)
    if owner_rejection:
        return _result(DecisionOutcome.REJECTED, owner_rejection)
    lease = snapshot.lease
    if _version_conflict(lease, command.expected_version):
        return _result(DecisionOutcome.CONFLICT, "version_mismatch")
    if _lease_is_effective(snapshot, lease):
        assert lease is not None
        if lease.owner == command.owner and lease.idempotency_key == command.idempotency_key:
            matches = set(lease.write_scopes) == set(command.write_scopes)
            if lease.acquire_ttl_seconds is not None:
                matches = matches and lease.acquire_ttl_seconds == command.ttl_seconds
            if not matches:
                return _result(DecisionOutcome.REJECTED, "idempotency_key_reuse")
            return _result(
                DecisionOutcome.NO_CHANGE,
                "lease_acquire_replay",
                next_snapshot=snapshot,
                idempotent=True,
            )
        return _result(DecisionOutcome.CONFLICT, "todo_lease_conflict")
    if lease is not None and lease.present and lease.idempotency_key == command.idempotency_key:
        return _result(DecisionOutcome.REJECTED, "idempotency_key_reuse")
    if any(
        other.active
        and other.effective
        and write_scopes_overlap(command.write_scopes, other.write_scopes)
        for other in snapshot.other_leases
    ):
        return _result(DecisionOutcome.CONFLICT, "write_scope_conflict")
    previous = lease or LeaseSnapshot()
    next_lease = LeaseSnapshot(
        present=True,
        active=True,
        status="active",
        owner=command.owner,
        idempotency_key=command.idempotency_key,
        version=_actual_version(previous) + 1,
        lease_epoch=previous.lease_epoch + 1,
        write_scopes=tuple(command.write_scopes),
        acquire_ttl_seconds=command.ttl_seconds,
    )
    return _result(
        DecisionOutcome.APPLY,
        "lease_acquire",
        next_snapshot=replace(snapshot, lease=next_lease),
    )


def _decide_renew(
    snapshot: CoordinationSnapshot,
    command: LeaseRenewCommand,
) -> TransitionPlan:
    handoff_rejection = _lease_handoff_rejection(snapshot)
    if handoff_rejection:
        return _result(DecisionOutcome.REJECTED, handoff_rejection)
    if command.expected_version is None:
        return _result(DecisionOutcome.REJECTED, "version_required")
    owner_rejection = _lease_owner_rejection(snapshot, command.owner)
    if owner_rejection:
        return _result(DecisionOutcome.REJECTED, owner_rejection)
    lease = snapshot.lease
    if _version_conflict(lease, command.expected_version):
        return _result(DecisionOutcome.CONFLICT, "version_mismatch")
    if not lease or not lease.present or not lease.active:
        return _result(DecisionOutcome.REJECTED, "lease_not_active")
    if lease.owner != command.owner or lease.idempotency_key != command.idempotency_key:
        return _result(DecisionOutcome.REJECTED, "lease_cas_mismatch")
    return _result(
        DecisionOutcome.APPLY,
        "lease_renew",
        next_snapshot=replace(
            snapshot,
            lease=replace(
                lease,
                version=lease.version + 1,
            ),
        ),
    )


def _decide_transfer(
    snapshot: CoordinationSnapshot,
    command: LeaseTransferCommand,
) -> TransitionPlan:
    handoff_rejection = _lease_handoff_rejection(snapshot)
    if handoff_rejection:
        return _result(DecisionOutcome.REJECTED, handoff_rejection)
    if command.expected_version is None:
        return _result(DecisionOutcome.REJECTED, "version_required")
    if command.owner not in snapshot.registered_agents:
        return _result(DecisionOutcome.REJECTED, "owner_not_registered")
    owner_rejection = _lease_owner_rejection(snapshot, command.new_owner)
    if owner_rejection:
        return _result(DecisionOutcome.REJECTED, owner_rejection)
    lease = snapshot.lease
    if _version_conflict(lease, command.expected_version):
        return _result(DecisionOutcome.CONFLICT, "version_mismatch")
    if not lease or not lease.present or not lease.active:
        return _result(DecisionOutcome.REJECTED, "lease_not_active")
    if lease.owner != command.owner or lease.idempotency_key != command.idempotency_key:
        return _result(DecisionOutcome.REJECTED, "lease_cas_mismatch")
    if command.new_idempotency_key == command.idempotency_key:
        return _result(DecisionOutcome.REJECTED, "idempotency_key_reuse")
    return _result(
        DecisionOutcome.APPLY,
        "lease_transfer",
        next_snapshot=replace(
            snapshot,
            lease=replace(
                lease,
                owner=command.new_owner,
                idempotency_key=command.new_idempotency_key,
                version=lease.version + 1,
                lease_epoch=lease.lease_epoch + 1,
            ),
        ),
    )


def _decide_release(
    snapshot: CoordinationSnapshot,
    command: LeaseReleaseCommand,
) -> TransitionPlan:
    lease = snapshot.lease
    if command.expected_version is None:
        return _result(DecisionOutcome.REJECTED, "version_required")
    if _version_conflict(lease, command.expected_version):
        return _result(DecisionOutcome.CONFLICT, "version_mismatch")
    if not lease or not lease.present:
        return _result(
            DecisionOutcome.NO_CHANGE,
            "lease_missing",
            next_snapshot=snapshot,
            idempotent=True,
        )
    if lease.status == "released":
        if lease.owner != command.owner or lease.idempotency_key != command.idempotency_key:
            return _result(DecisionOutcome.REJECTED, "lease_cas_mismatch")
        return _result(
            DecisionOutcome.NO_CHANGE,
            "lease_release_replay",
            next_snapshot=snapshot,
            idempotent=True,
        )
    if (
        lease.owner != command.owner or lease.idempotency_key != command.idempotency_key
    ):
        return _result(DecisionOutcome.REJECTED, "lease_cas_mismatch")
    return _result(
        DecisionOutcome.APPLY,
        "lease_release",
        next_snapshot=replace(
            snapshot,
            lease=replace(lease, active=False, status="released"),
        ),
    )


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

    if _invalid_lease_snapshot(snapshot.lease):
        return _result(DecisionOutcome.REJECTED, "invalid_lease_snapshot")
    if isinstance(command, TodoMutationCommand):
        return _decide_todo(snapshot, command)
    if isinstance(command, LeaseAcquireCommand):
        return _decide_acquire(snapshot, command)
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
        if snapshot.todo is None:
            return _result(DecisionOutcome.REJECTED, "todo_not_found")
        return _terminal_fence_decision(
            snapshot,
            actor_agent_id=command.actor_agent_id,
            lease_idempotency_key=command.lease_idempotency_key,
            lease_expected_version=command.lease_expected_version,
            delegated_authority=command.delegated_authority,
            allow_user_gate_auto_acquire=command.allow_user_gate_auto_acquire,
            require_active_when_fence_supplied=(
                command.require_active_when_fence_supplied
            ),
        )
    if isinstance(command, HandoffModeTransitionCommand):
        return _decide_handoff_transition(snapshot, command)
    raise TypeError(f"unsupported coordination command: {type(command).__name__}")
