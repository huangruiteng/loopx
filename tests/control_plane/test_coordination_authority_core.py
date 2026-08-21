from __future__ import annotations

from dataclasses import fields, replace

import pytest

from loopx.control_plane.coordination.authority_core import (
    CoordinationSnapshot,
    DecisionOutcome,
    HandoffMode,
    HandoffModeTransitionCommand,
    LeaseAcquireCommand,
    LeaseAction,
    LeaseFence,
    LeaseModeGateCommand,
    LeaseOwnerEligibilityCommand,
    LeaseReleaseCommand,
    LeaseRenewCommand,
    LeaseSnapshot,
    LeaseTransferCommand,
    LifecycleGrant,
    OtherLeaseSnapshot,
    OwnershipGate,
    TerminalFenceCommand,
    TodoAction,
    TodoMutationCommand,
    TodoSnapshot,
    decide,
)


AGENT_A = "agent-a"
AGENT_B = "agent-b"
ORCHESTRATOR = "orchestrator"
SCOPE = ("direction", "action", "publish-release")


def todo(**overrides: object) -> TodoSnapshot:
    values: dict[str, object] = {
        "todo_id": "todo_target",
        "status": "open",
        "role": "agent",
    }
    values.update(overrides)
    return TodoSnapshot(**values)  # type: ignore[arg-type]


def lease(**overrides: object) -> LeaseSnapshot:
    values: dict[str, object] = {
        "present": True,
        "active": True,
        "status": "active",
        "owner": AGENT_A,
        "idempotency_key": "execution-a",
        "version": 3,
        "lease_epoch": 7,
        "write_scopes": ("src/",),
        "acquire_ttl_seconds": 300,
    }
    values.update(overrides)
    return LeaseSnapshot(**values)  # type: ignore[arg-type]


def snapshot(**overrides: object) -> CoordinationSnapshot:
    values: dict[str, object] = {
        "handoff_mode": HandoffMode.LEGACY,
        "registered_agents": (AGENT_A, AGENT_B, ORCHESTRATOR),
        "todo": todo(),
    }
    values.update(overrides)
    return CoordinationSnapshot(**values)  # type: ignore[arg-type]


def claim(**overrides: object) -> TodoMutationCommand:
    values: dict[str, object] = {
        "action": TodoAction.CLAIM,
        "actor_agent_id": AGENT_A,
        "requested_claimed_by": AGENT_A,
        "ownership_mutation": True,
    }
    values.update(overrides)
    return TodoMutationCommand(**values)  # type: ignore[arg-type]


def terminal(
    action: TodoAction = TodoAction.COMPLETE,
    **overrides: object,
) -> TodoMutationCommand:
    values: dict[str, object] = {
        "action": action,
        "actor_agent_id": AGENT_A,
    }
    values.update(overrides)
    return TodoMutationCommand(**values)  # type: ignore[arg-type]


def test_decision_is_deterministic_and_target_scoped() -> None:
    base = snapshot()
    command = claim()

    first = decide(base, command)
    second = decide(base, command)
    unrelated = replace(
        base,
        other_leases=(
            OtherLeaseSnapshot(
                todo_id="todo_unrelated",
                active=True,
                effective=True,
                write_scopes=("docs/",),
            ),
        ),
    )

    assert first == second
    unrelated_plan = decide(unrelated, command)
    assert unrelated_plan.outcome == first.outcome
    assert unrelated_plan.code == first.code
    assert unrelated_plan.next_snapshot is not None
    assert first.next_snapshot is not None
    assert unrelated_plan.next_snapshot.todo == first.next_snapshot.todo
    assert unrelated_plan.next_snapshot.other_leases == unrelated.other_leases
    assert first.outcome is DecisionOutcome.APPLY


@pytest.mark.parametrize(
    ("state", "command", "code"),
    [
        (snapshot(), claim(actor_agent_id=None), "actor_required"),
        (snapshot(), claim(actor_agent_id="unknown"), "actor_not_registered"),
        (
            snapshot(todo=todo(excluded_agents=frozenset({AGENT_A}))),
            claim(),
            "actor_excluded",
        ),
        (
            snapshot(todo=todo(role="user", bound_agent=AGENT_B)),
            terminal(),
            "bound_agent_mismatch",
        ),
        (
            snapshot(todo=todo(claimed_by=AGENT_B)),
            terminal(),
            "claim_owner_mismatch",
        ),
        (
            snapshot(),
            claim(requested_claimed_by=AGENT_B),
            "claim_actor_mismatch",
        ),
    ],
)
def test_todo_authority_rejections_are_typed(
    state: CoordinationSnapshot,
    command: TodoMutationCommand,
    code: str,
) -> None:
    plan = decide(state, command)
    assert plan.outcome is DecisionOutcome.REJECTED
    assert plan.code == code
    assert plan.next_snapshot is None


def test_single_agent_compatibility_and_delegated_authority_are_explicit() -> None:
    single = snapshot(registered_agents=(AGENT_A,))
    single_plan = decide(single, terminal(actor_agent_id=None))
    assert single_plan.outcome is DecisionOutcome.APPLY
    assert single_plan.authority_mode == "single_agent_compatibility"

    claimed = snapshot(
        todo=todo(claimed_by=AGENT_B),
        lifecycle_grants=(
            LifecycleGrant(
                agent_id=ORCHESTRATOR,
                actions=frozenset({"complete"}),
                requires_reason=True,
            ),
        ),
    )
    missing_reason = decide(
        claimed,
        terminal(actor_agent_id=ORCHESTRATOR),
    )
    assert missing_reason.code == "delegation_reason_required"

    delegated = decide(
        claimed,
        terminal(
            actor_agent_id=ORCHESTRATOR,
            authority_reason="Recover the stalled owner.",
        ),
    )
    assert delegated.outcome is DecisionOutcome.APPLY
    assert delegated.authority_mode == "delegated_orchestration_override"


def test_exact_user_gate_override_requires_the_exact_linked_scope() -> None:
    gate = todo(
        todo_id="todo_gate",
        role="user",
        task_class="user_gate",
        decision_scope=SCOPE,
        unblocks_todo_id="todo_target",
    )
    target = todo(required_decision_scopes=frozenset({SCOPE}))
    state = snapshot(todo=gate, decision_target=target)
    command = terminal(actor_agent_id=None, decision_outcome="approve")

    plan = decide(state, command)
    assert plan.outcome is DecisionOutcome.APPLY
    assert plan.authority_mode == "exact_user_gate_decision_scope_override"

    wrong_scope = replace(
        state,
        decision_target=replace(target, required_decision_scopes=frozenset()),
    )
    rejected = decide(wrong_scope, command)
    assert rejected.outcome is DecisionOutcome.REJECTED
    assert rejected.code == "actor_required"


@pytest.mark.parametrize(
    ("mode", "current_lease", "expected", "gate"),
    [
        (HandoffMode.LEGACY, None, DecisionOutcome.APPLY, OwnershipGate.NOT_REQUIRED),
        (
            HandoffMode.SOFT_CLAIM,
            None,
            DecisionOutcome.APPLY,
            OwnershipGate.NOT_REQUIRED,
        ),
        (
            HandoffMode.HARD_LEASE,
            None,
            DecisionOutcome.REJECTED,
            OwnershipGate.REQUIRE_HOLDER,
        ),
        (
            HandoffMode.HARD_LEASE,
            lease(),
            DecisionOutcome.APPLY,
            OwnershipGate.REQUIRE_HOLDER,
        ),
    ],
)
def test_ownership_handoff_preserves_the_three_modes(
    mode: HandoffMode,
    current_lease: LeaseSnapshot | None,
    expected: DecisionOutcome,
    gate: OwnershipGate,
) -> None:
    plan = decide(snapshot(handoff_mode=mode, lease=current_lease), claim())
    assert plan.outcome is expected
    assert plan.ownership_gate is gate


def test_delegated_hard_lease_ownership_change_uses_the_only_override() -> None:
    state = snapshot(
        handoff_mode=HandoffMode.HARD_LEASE,
        todo=todo(claimed_by=AGENT_B),
        lifecycle_grants=(
            LifecycleGrant(
                agent_id=ORCHESTRATOR,
                actions=frozenset({"reassign"}),
            ),
        ),
    )
    plan = decide(
        state,
        TodoMutationCommand(
            action=TodoAction.UPDATE,
            actor_agent_id=ORCHESTRATOR,
            requested_claimed_by=ORCHESTRATOR,
            authority_action="reassign",
            authority_reason="Owner handoff.",
            ownership_mutation=True,
        ),
    )
    assert plan.outcome is DecisionOutcome.APPLY
    assert plan.ownership_gate is OwnershipGate.DELEGATED_OVERRIDE


@pytest.mark.parametrize("action", [TodoAction.COMPLETE, TodoAction.SUPERSEDE])
def test_terminal_verbs_share_one_lease_fence(action: TodoAction) -> None:
    legacy = decide(snapshot(), terminal(action))
    assert legacy.outcome is DecisionOutcome.APPLY
    assert legacy.lease_fence is LeaseFence.NOT_REQUIRED

    hard_missing = decide(
        snapshot(handoff_mode=HandoffMode.HARD_LEASE),
        terminal(action),
    )
    assert hard_missing.outcome is DecisionOutcome.REJECTED
    assert hard_missing.code == "handoff_mode_requires_lease"

    hard_verified = decide(
        snapshot(handoff_mode=HandoffMode.HARD_LEASE, lease=lease()),
        terminal(
            action,
            lease_idempotency_key="execution-a",
            lease_expected_version=3,
        ),
    )
    assert hard_verified.outcome is DecisionOutcome.APPLY
    assert hard_verified.lease_fence is LeaseFence.REQUIRED


def test_exact_user_gate_can_plan_auto_acquire_but_never_displaces_a_live_lease() -> None:
    user_gate = todo(role="user", task_class="user_gate")
    auto = decide(
        snapshot(
            handoff_mode=HandoffMode.HARD_LEASE,
            registered_agents=(AGENT_A,),
            todo=user_gate,
        ),
        terminal(allow_user_gate_auto_acquire=True),
    )
    assert auto.outcome is DecisionOutcome.APPLY
    assert auto.lease_fence is LeaseFence.AUTO_ACQUIRE

    foreign_live = decide(
        snapshot(
            handoff_mode=HandoffMode.HARD_LEASE,
            registered_agents=(AGENT_A, AGENT_B),
            todo=user_gate,
            lease=lease(owner=AGENT_B, idempotency_key="foreign"),
        ),
        terminal(),
    )
    assert foreign_live.outcome is DecisionOutcome.REJECTED
    assert foreign_live.code == "lease_fence_required"


def test_terminal_entrypoints_share_user_gate_auto_acquire_policy() -> None:
    state = snapshot(
        handoff_mode=HandoffMode.HARD_LEASE,
        registered_agents=(AGENT_A,),
        todo=todo(role="user", task_class="user_gate"),
    )
    full = decide(
        state,
        terminal(
            lease_idempotency_key="auto-turn-key",
            allow_user_gate_auto_acquire=True,
        ),
    )
    fence = decide(
        state,
        TerminalFenceCommand(
            actor_agent_id=AGENT_A,
            lease_idempotency_key="auto-turn-key",
            allow_user_gate_auto_acquire=True,
            require_active_when_fence_supplied=False,
        ),
    )

    assert full.outcome is fence.outcome is DecisionOutcome.APPLY
    assert full.lease_fence is fence.lease_fence is LeaseFence.AUTO_ACQUIRE
    assert full.next_snapshot is not None and fence.next_snapshot is not None
    assert full.next_snapshot.lease == fence.next_snapshot.lease


def test_preauthorized_terminal_fence_preserves_mode_and_delegation_rules() -> None:
    legacy = decide(
        snapshot(),
        TerminalFenceCommand(actor_agent_id=AGENT_A),
    )
    assert legacy.outcome is DecisionOutcome.APPLY
    assert legacy.lease_fence is LeaseFence.NOT_REQUIRED

    hard_missing = decide(
        snapshot(handoff_mode=HandoffMode.HARD_LEASE),
        TerminalFenceCommand(actor_agent_id=AGENT_A),
    )
    assert hard_missing.outcome is DecisionOutcome.REJECTED
    assert hard_missing.code == "handoff_mode_requires_lease"

    delegated = decide(
        snapshot(handoff_mode=HandoffMode.HARD_LEASE),
        TerminalFenceCommand(
            actor_agent_id=ORCHESTRATOR,
            delegated_authority=True,
        ),
    )
    assert delegated.outcome is DecisionOutcome.APPLY
    assert delegated.lease_fence is LeaseFence.DELEGATED_OVERRIDE

    verified = decide(
        snapshot(handoff_mode=HandoffMode.HARD_LEASE, lease=lease()),
        TerminalFenceCommand(
            actor_agent_id=AGENT_A,
            lease_idempotency_key="execution-a",
            lease_expected_version=3,
        ),
    )
    assert verified.outcome is DecisionOutcome.APPLY
    assert verified.lease_fence is LeaseFence.REQUIRED
    assert verified.next_snapshot is not None
    assert verified.next_snapshot.lease is not None
    assert verified.next_snapshot.lease.status == "released"


@pytest.mark.parametrize(
    ("target", "owner", "code"),
    [
        (None, AGENT_A, "todo_not_found"),
        (todo(status="done"), AGENT_A, "todo_not_open"),
        (todo(), "unknown", "owner_not_registered"),
        (todo(excluded_agents=frozenset({AGENT_A})), AGENT_A, "owner_excluded_from_todo"),
        (todo(claimed_by=AGENT_B), AGENT_A, "owner_conflicts_with_claim"),
    ],
)
def test_lease_owner_eligibility_is_one_rule(
    target: TodoSnapshot | None,
    owner: str,
    code: str,
) -> None:
    plan = decide(
        snapshot(todo=target),
        LeaseOwnerEligibilityCommand(owner=owner),
    )
    assert plan.outcome is DecisionOutcome.REJECTED
    assert plan.code == code


def test_lease_acquire_distinguishes_exact_replay_reuse_and_conflict() -> None:
    state = snapshot(lease=lease())
    exact = LeaseAcquireCommand(
        owner=AGENT_A,
        idempotency_key="execution-a",
        ttl_seconds=300,
        write_scopes=("src/",),
        expected_version=3,
    )
    replay = decide(state, exact)
    assert replay.outcome is DecisionOutcome.NO_CHANGE
    assert replay.idempotent is True

    reuse = decide(state, replace(exact, ttl_seconds=301))
    assert reuse.outcome is DecisionOutcome.REJECTED
    assert reuse.code == "idempotency_key_reuse"

    conflict = decide(
        state,
        replace(exact, owner=AGENT_B, idempotency_key="execution-b"),
    )
    assert conflict.outcome is DecisionOutcome.CONFLICT
    assert conflict.code == "todo_lease_conflict"


def test_lease_acquire_checks_version_scope_and_generation_fields_independently() -> None:
    stale = decide(
        snapshot(lease=lease()),
        LeaseAcquireCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            ttl_seconds=300,
            expected_version=2,
        ),
    )
    assert stale.outcome is DecisionOutcome.CONFLICT
    assert stale.code == "version_mismatch"

    scope_conflict = decide(
        snapshot(
            lease=None,
            other_leases=(
                OtherLeaseSnapshot(
                    todo_id="todo_other",
                    active=True,
                    effective=True,
                    write_scopes=("src/**",),
                ),
            ),
        ),
        LeaseAcquireCommand(
            owner=AGENT_A,
            idempotency_key="execution-new",
            ttl_seconds=300,
            write_scopes=("src/core.py",),
        ),
    )
    assert scope_conflict.outcome is DecisionOutcome.CONFLICT
    assert scope_conflict.code == "write_scope_conflict"

    replaced_generation = decide(
        snapshot(lease=lease(active=False, status="released")),
        LeaseAcquireCommand(
            owner=AGENT_A,
            idempotency_key="execution-new",
            ttl_seconds=300,
            expected_version=3,
        ),
    )
    assert replaced_generation.outcome is DecisionOutcome.APPLY
    assert replaced_generation.next_snapshot is not None
    next_lease = replaced_generation.next_snapshot.lease
    assert next_lease is not None
    assert next_lease.version == 4
    assert next_lease.lease_epoch == 8


def test_retired_lease_generation_rejects_same_execution_key() -> None:
    state = snapshot(lease=lease(active=False, status="released"))
    retired = decide(
        state,
        LeaseAcquireCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            ttl_seconds=300,
            expected_version=3,
        ),
    )
    assert retired.outcome is DecisionOutcome.REJECTED
    assert retired.code == "idempotency_key_reuse"

    next_generation = decide(
        state,
        LeaseAcquireCommand(
            owner=AGENT_A,
            idempotency_key="execution-next",
            ttl_seconds=300,
            expected_version=3,
        ),
    )
    assert next_generation.outcome is DecisionOutcome.APPLY
    assert next_generation.next_snapshot is not None
    assert next_generation.next_snapshot.lease is not None
    assert next_generation.next_snapshot.lease.version == 4
    assert next_generation.next_snapshot.lease.lease_epoch == 8


def test_renew_transfer_and_release_share_cas_rules() -> None:
    state = snapshot(lease=lease())
    renewed = decide(
        state,
        LeaseRenewCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            ttl_seconds=600,
            expected_version=3,
        ),
    )
    assert renewed.outcome is DecisionOutcome.APPLY
    assert renewed.next_snapshot is not None
    assert renewed.next_snapshot.lease is not None
    assert renewed.next_snapshot.lease.version == 4
    assert renewed.next_snapshot.lease.lease_epoch == 7
    assert renewed.next_snapshot.lease.acquire_ttl_seconds == 300

    transferred = decide(
        state,
        LeaseTransferCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            new_owner=AGENT_B,
            new_idempotency_key="execution-b",
            ttl_seconds=600,
            expected_version=3,
        ),
    )
    assert transferred.outcome is DecisionOutcome.APPLY
    assert transferred.next_snapshot is not None
    assert transferred.next_snapshot.lease is not None
    assert transferred.next_snapshot.lease.owner == AGENT_B
    assert transferred.next_snapshot.lease.lease_epoch == 8
    assert transferred.next_snapshot.lease.acquire_ttl_seconds == 300

    missing_version = decide(
        state,
        LeaseReleaseCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            expected_version=2,
        ),
    )
    assert missing_version.outcome is DecisionOutcome.CONFLICT
    assert missing_version.code == "version_mismatch"

    released = decide(
        state,
        LeaseReleaseCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            expected_version=3,
        ),
    )
    assert released.outcome is DecisionOutcome.APPLY
    assert released.next_snapshot is not None
    assert released.next_snapshot.lease is not None
    assert released.next_snapshot.lease.status == "released"
    assert released.next_snapshot.lease.active is False


def test_lease_generation_mutations_require_current_version_and_fresh_transfer_key() -> None:
    state = snapshot(lease=lease())
    commands = (
        LeaseRenewCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            ttl_seconds=600,
        ),
        LeaseTransferCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            new_owner=AGENT_B,
            new_idempotency_key="execution-b",
            ttl_seconds=600,
        ),
        LeaseReleaseCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
        ),
    )
    for command in commands:
        plan = decide(state, command)
        assert plan.outcome is DecisionOutcome.REJECTED
        assert plan.code == "version_required"

    same_key_transfer = decide(
        state,
        LeaseTransferCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            new_owner=AGENT_B,
            new_idempotency_key="execution-a",
            ttl_seconds=600,
            expected_version=3,
        ),
    )
    assert same_key_transfer.outcome is DecisionOutcome.REJECTED
    assert same_key_transfer.code == "idempotency_key_reuse"


def test_release_checks_owner_and_key_for_an_expired_generation() -> None:
    expired = snapshot(lease=lease(active=False, status="active"))
    plan = decide(
        expired,
        LeaseReleaseCommand(
            owner=AGENT_B,
            idempotency_key="execution-a",
            expected_version=3,
        ),
    )

    assert plan.outcome is DecisionOutcome.REJECTED
    assert plan.code == "lease_cas_mismatch"


@pytest.mark.parametrize(
    "invalid",
    [
        lease(present=False, active=True),
        lease(active=True, status="released"),
    ],
)
def test_contradictory_normalized_lease_state_fails_closed(
    invalid: LeaseSnapshot,
) -> None:
    plan = decide(snapshot(lease=invalid), LeaseOwnerEligibilityCommand(owner=AGENT_A))

    assert plan.outcome is DecisionOutcome.REJECTED
    assert plan.code == "invalid_lease_snapshot"


def test_active_terminal_fence_requires_current_version_after_key_match() -> None:
    plan = decide(
        snapshot(handoff_mode=HandoffMode.HARD_LEASE, lease=lease()),
        TerminalFenceCommand(
            actor_agent_id=AGENT_A,
            lease_idempotency_key="execution-a",
        ),
    )
    assert plan.outcome is DecisionOutcome.REJECTED
    assert plan.code == "version_required"


def test_soft_claim_forbids_lease_mutation_but_allows_release() -> None:
    state = snapshot(handoff_mode=HandoffMode.SOFT_CLAIM, lease=lease())
    acquire = decide(
        state,
        LeaseAcquireCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            ttl_seconds=300,
        ),
    )
    assert acquire.outcome is DecisionOutcome.REJECTED
    assert acquire.code == "handoff_mode_forbids_lease"

    released = decide(
        state,
        LeaseReleaseCommand(
            owner=AGENT_A,
            idempotency_key="execution-a",
            expected_version=3,
        ),
    )
    assert released.outcome is DecisionOutcome.APPLY


def test_mode_gate_is_explicit_instead_of_a_synthetic_lease_command() -> None:
    state = snapshot(handoff_mode=HandoffMode.SOFT_CLAIM)
    for action in (LeaseAction.ACQUIRE, LeaseAction.RENEW, LeaseAction.TRANSFER):
        plan = decide(state, LeaseModeGateCommand(action=action))
        assert plan.outcome is DecisionOutcome.REJECTED
        assert plan.code == "handoff_mode_forbids_lease"

    release = decide(state, LeaseModeGateCommand(action=LeaseAction.RELEASE))
    assert release.outcome is DecisionOutcome.APPLY


def test_handoff_mode_transition_requires_materialized_quiescence() -> None:
    same = decide(
        snapshot(handoff_mode=HandoffMode.LEGACY),
        HandoffModeTransitionCommand(requested_mode=HandoffMode.LEGACY),
    )
    assert same.outcome is DecisionOutcome.NO_CHANGE

    blocked = decide(
        snapshot(
            active_claimed_todo_ids=("todo_claimed",),
            active_lease_todo_ids=("todo_leased",),
        ),
        HandoffModeTransitionCommand(requested_mode=HandoffMode.HARD_LEASE),
    )
    assert blocked.outcome is DecisionOutcome.REJECTED
    assert blocked.code == "handoff_mode_not_quiescent"

    changed = decide(
        snapshot(),
        HandoffModeTransitionCommand(requested_mode=HandoffMode.HARD_LEASE),
    )
    assert changed.outcome is DecisionOutcome.APPLY
    assert changed.next_snapshot is not None
    assert changed.next_snapshot.handoff_mode is HandoffMode.HARD_LEASE


def test_core_has_no_storage_or_receipt_version_domain() -> None:
    names = {
        field.name
        for model in (CoordinationSnapshot, TodoSnapshot, LeaseSnapshot)
        for field in fields(model)
    }
    assert "provider_generation" not in names
    assert "operation_id" not in names
    assert "receipt_index" not in names
    assert "path" not in names
    assert {"version", "lease_epoch"}.issubset(names)
