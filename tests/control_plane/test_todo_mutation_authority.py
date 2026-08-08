from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.scheduler.monitor_poll_writeback import (
    write_monitor_poll_todo_state,
)
from loopx.control_plane.todos.event_writeback import (
    complete_event_projected_goal_todo,
)
from loopx.control_plane.work_items.task_lease import (
    TaskLeaseError,
    acquire_task_lease,
)
from loopx.event_sourced_state import (
    TODO_ADDED,
    TODO_UPDATED,
    AppendOnlyStateEventStore,
    StateEventError,
    backfill_todo_events_from_markdown,
    build_state_projection,
    make_state_event,
)
from loopx.status import parse_active_state_todos
from loopx.todos import (
    add_goal_todo,
    complete_goal_todo,
    supersede_goal_todo,
    update_goal_todo,
)

GOAL_ID = "todo-mutation-authority"
AUTHOR_AGENT = "codex-author"
REVIEW_AGENT = "codex-review"
ORCHESTRATION_AGENT = "codex-orchestrator"
DECISION_SCOPE = "direction:action:publish_release"


def _write_fixture(
    tmp_path: Path,
    *,
    multi_agent: bool = True,
    lifecycle_authority: list[dict] | None = None,
) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    state = repo / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "\n".join(
            [
                "---",
                f"goal_id: {GOAL_ID}",
                "updated_at: 2026-07-18T00:00:00+00:00",
                "---",
                "",
                "## Agent Todo",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    agents = (
        [AUTHOR_AGENT, REVIEW_AGENT, ORCHESTRATION_AGENT]
        if multi_agent
        else [AUTHOR_AGENT]
    )
    coordination = {
        "agent_model": "peer_v1",
        "registered_agents": agents,
    }
    if lifecycle_authority is not None:
        coordination["todo_lifecycle_authority"] = lifecycle_authority
    registry = tmp_path / "registry.global.json"
    registry.write_text(
        json.dumps(
            {
                "common_runtime_root": str(tmp_path / "runtime"),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "harness_self_improvement",
                        "status": "active",
                        "repo": str(repo),
                        "state_file": state.name,
                        "adapter": {"kind": "harness_self_improvement"},
                        "coordination": coordination,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return registry, state


def _agent_todo(state: Path, todo_id: str) -> dict:
    todos = parse_active_state_todos(state.read_text(encoding="utf-8"))
    return next(
        item
        for item in todos["agent_todos"]["items"]
        if item["todo_id"] == todo_id
    )


def _add_agent_todo(
    registry: Path,
    *,
    claimed_by: str | None = AUTHOR_AGENT,
    excluded_agents: list[str] | None = None,
) -> dict:
    return add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Deliver one bounded control-plane change.",
        task_class="advancement_task",
        claimed_by=claimed_by,
        excluded_agents=excluded_agents,
    )


def test_multi_agent_update_requires_actor_and_is_atomic(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_agent_todo(registry)
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="requires --agent-id"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            note="This must not be written without an attributed actor.",
        )

    assert state.read_text(encoding="utf-8") == before


def test_excluded_actor_cannot_mutate_unclaimed_todo(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_agent_todo(
        registry,
        claimed_by=None,
        excluded_agents=[AUTHOR_AGENT],
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="is excluded from mutating"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            agent_id=AUTHOR_AGENT,
            note="An excluded author cannot rewrite review work.",
        )

    assert state.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("command", ["update", "complete", "supersede"])
def test_non_owner_cannot_mutate_claimed_todo(
    tmp_path: Path,
    command: str,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_agent_todo(registry, claimed_by=REVIEW_AGENT)
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="claimed_by='codex-review'"):
        if command == "update":
            update_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                todo_id=todo["todo_id"],
                agent_id=AUTHOR_AGENT,
                note="unauthorized",
            )
        elif command == "complete":
            complete_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                todo_id=todo["todo_id"],
                agent_id=AUTHOR_AGENT,
                evidence="unauthorized",
            )
        else:
            supersede_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                todo_id=todo["todo_id"],
                agent_id=AUTHOR_AGENT,
                reason="unauthorized",
            )

    assert state.read_text(encoding="utf-8") == before


def test_owner_actor_update_returns_typed_receipt(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_agent_todo(registry)

    result = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        agent_id=AUTHOR_AGENT,
        note="owner-attributed update",
    )

    assert result["mutation_authority"] == {
        "schema_version": "todo_mutation_authority_v0",
        "command": "update",
        "mode": "registered_peer_actor",
        "actor_agent_id": AUTHOR_AGENT,
        "todo_id": todo["todo_id"],
        "claim_owner": AUTHOR_AGENT,
        "registered_agent_count": 3,
    }
    assert _agent_todo(state, todo["todo_id"])["note"] == "owner-attributed update"


def test_advancement_todo_preserves_public_target_key(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)

    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Advance the admitted issue-fix route.",
        task_class="advancement_task",
        action_kind="issue_fix_branch_validation",
        claimed_by=AUTHOR_AGENT,
        monitor_metadata={"target_key": "issue-fix:owner/repo:issue_42"},
    )

    projected = _agent_todo(state, todo["todo_id"])
    assert projected["action_kind"] == "issue_fix_branch_validation"
    assert projected["target_key"] == "issue-fix:owner/repo:issue_42"


def test_capability_binding_follows_generated_agent_successor(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Advance the admitted issue-fix route.",
        task_class="advancement_task",
        action_kind="issue_fix_branch_validation",
        capability_binding_ref="issue-fix:feasibility-a1b2c3d4",
        claimed_by=AUTHOR_AGENT,
    )

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        agent_id=AUTHOR_AGENT,
        evidence="bounded validation passed",
        next_agent_todo="Open the validated issue-fix review packet.",
        next_action_kind="issue_fix_reviewer_request",
        next_claimed_by=AUTHOR_AGENT,
        next_continuation_policy="same_agent_non_delivery",
    )

    successor = _agent_todo(state, result["next_todos"][0]["todo_id"])
    assert successor["capability_binding_ref"] == (
        "issue-fix:feasibility-a1b2c3d4"
    )


def test_active_task_lease_fences_same_agent_completion_instance(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path, multi_agent=False)
    todo = _add_agent_todo(registry)
    lease_key = "turn-owner-instance"
    acquire_task_lease(
        registry_path=registry,
        runtime_root=tmp_path / "runtime",
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        owner=AUTHOR_AGENT,
        idempotency_key=lease_key,
        ttl_seconds=600,
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(TaskLeaseError) as missing_fence:
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            claimed_by=AUTHOR_AGENT,
            evidence="stale execution instance",
            next_agent_todo="Create a stale successor.",
        )
    assert missing_fence.value.code == "lease_fence_required"
    assert state.read_text(encoding="utf-8") == before

    with pytest.raises(TaskLeaseError) as mismatched_fence:
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            claimed_by=AUTHOR_AGENT,
            task_lease_idempotency_key="other-instance",
            evidence="wrong execution instance",
        )
    assert mismatched_fence.value.code == "lease_cas_mismatch"
    assert state.read_text(encoding="utf-8") == before

    completed = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        claimed_by=AUTHOR_AGENT,
        task_lease_idempotency_key=lease_key,
        task_lease_expected_version=1,
        evidence="lease owner validated the result",
        next_agent_todo="Create the canonical successor.",
    )
    assert completed["task_lease_fence"] == {
        "schema_version": "task_lease_v0",
        "required": True,
        "active": True,
        "owner": AUTHOR_AGENT,
        "version": 1,
        "execution_instance_verified": True,
    }

    replayed = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        claimed_by=AUTHOR_AGENT,
        evidence="late result from another execution instance",
        next_agent_todo="Create a duplicate stale successor.",
    )
    assert replayed["idempotent_replay"] is True
    assert replayed["changed"] is False
    agent_todos = parse_active_state_todos(state.read_text(encoding="utf-8"))[
        "agent_todos"
    ]["items"]
    todo_titles = [
        str(item.get("title") or item.get("text") or "") for item in agent_todos
    ]
    assert todo_titles.count("Create the canonical successor.") == 1
    assert "Create a duplicate stale successor." not in todo_titles


def test_capability_binding_cannot_be_rebound_by_duplicate_add(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Advance the admitted issue-fix route.",
        task_class="advancement_task",
        capability_binding_ref="issue-fix:feasibility-a1b2c3d4",
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="immutable once set"):
        add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text="Advance the admitted issue-fix route.",
            task_class="advancement_task",
            capability_binding_ref="issue-fix:feasibility-e5f6a7b8",
        )

    assert state.read_text(encoding="utf-8") == before


def test_capability_binding_follows_event_projected_successor(tmp_path: Path) -> None:
    event_log = tmp_path / "todo-events.jsonl"
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        make_state_event(
            event_id="evt-binding-parent",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": "todo_binding_parent"},
            payload={
                "role": "agent",
                "title": "Advance the admitted issue-fix route.",
                "task_class": "advancement_task",
                "action_kind": "issue_fix_branch_validation",
                "capability_binding_ref": "issue-fix:feasibility-a1b2c3d4",
                "claimed_by": AUTHOR_AGENT,
            },
            recorded_at="2026-07-18T00:00:00+00:00",
        )
    )
    projection = build_state_projection(store.load())
    parent = projection["agent_todos"]["items"][0]

    result = complete_event_projected_goal_todo(
        goal_id=GOAL_ID,
        context={
            "item": parent,
            "role": "agent",
            "event_log_path": event_log,
            "fields": {"agent_todos": projection["agent_todos"]},
        },
        evidence="bounded validation passed",
        note=None,
        no_followup=False,
        successor_todo_ids=[],
        claimed_by=AUTHOR_AGENT,
        clear_claim=False,
        next_agent_todo="Open the validated issue-fix review packet.",
        next_user_todo=None,
        next_user_task_class="user_gate",
        next_claimed_by=AUTHOR_AGENT,
        next_task_class="advancement_task",
        next_action_kind="issue_fix_reviewer_request",
        next_task_repository=None,
        next_required_capabilities=None,
        next_continuation_policy="same_agent_non_delivery",
        self_merged=False,
        next_excluded_agents=[],
        registered_agents=[AUTHOR_AGENT],
        updated_at="2026-07-18T00:01:00+00:00",
        dry_run=False,
    )

    successor_id = result["next_todos"][0]["todo_id"]
    replayed = build_state_projection(AppendOnlyStateEventStore(event_log).load())
    replayed_agent_todos = {
        item["todo_id"]: item for item in replayed["agent_todos"]["items"]
    }
    assert successor_id in replayed_agent_todos, (result, replayed)
    successor = next(
        item
        for item in replayed["agent_todos"]["items"]
        if item["todo_id"] == successor_id
    )
    assert successor["capability_binding_ref"] == (
        "issue-fix:feasibility-a1b2c3d4"
    )

    event_count = len(AppendOnlyStateEventStore(event_log).load())
    completed_parent = next(
        item
        for item in replayed["agent_todos"]["items"]
        if item["todo_id"] == parent["todo_id"]
    )
    duplicate = complete_event_projected_goal_todo(
        goal_id=GOAL_ID,
        context={
            "item": completed_parent,
            "role": "agent",
            "event_log_path": event_log,
            "fields": {"agent_todos": replayed["agent_todos"]},
        },
        evidence="late stale completion",
        note=None,
        no_followup=False,
        successor_todo_ids=[],
        claimed_by=AUTHOR_AGENT,
        clear_claim=False,
        next_agent_todo="Create a duplicate event successor.",
        next_user_todo=None,
        next_user_task_class="user_gate",
        next_claimed_by=AUTHOR_AGENT,
        next_task_class="advancement_task",
        next_action_kind="issue_fix_reviewer_request",
        next_task_repository=None,
        next_required_capabilities=None,
        next_continuation_policy="same_agent_non_delivery",
        self_merged=False,
        next_excluded_agents=[],
        registered_agents=[AUTHOR_AGENT],
        updated_at="2026-07-18T00:02:00+00:00",
        dry_run=False,
    )
    assert duplicate["idempotent_replay"] is True
    assert duplicate["changed"] is False
    assert len(AppendOnlyStateEventStore(event_log).load()) == event_count


def test_task_domain_survives_markdown_event_projection() -> None:
    events = backfill_todo_events_from_markdown(
        "\n".join(
            [
                "## Agent Todo",
                "",
                "- [ ] [P0] Validate one adaptive lane.",
                (
                    "  <!-- loopx:todo todo_id=todo_domain001 status=open "
                    "task_class=advancement_task action_kind=validate "
                    "task_domain=validation -->"
                ),
            ]
        ),
        goal_id=GOAL_ID,
    )

    projection = build_state_projection(events)

    assert projection["agent_todos"]["items"][0]["task_domain"] == "validation"


def test_task_domain_event_update_is_normalized_and_invalid_values_fail() -> None:
    added = make_state_event(
        event_id="evt-domain-add",
        goal_id=GOAL_ID,
        event_type=TODO_ADDED,
        refs={"todo_id": "todo_domain_update"},
        payload={
            "role": "agent",
            "title": "Validate one adaptive lane.",
            "task_class": "advancement_task",
            "task_domain": "validation",
        },
        recorded_at="2026-07-18T00:00:00+00:00",
    )
    updated = make_state_event(
        event_id="evt-domain-update",
        goal_id=GOAL_ID,
        event_type=TODO_UPDATED,
        refs={"todo_id": "todo_domain_update"},
        payload={"task_domain": "docs.review"},
        recorded_at="2026-07-18T00:01:00+00:00",
    )

    projection = build_state_projection([added, updated])

    assert projection["agent_todos"]["items"][0]["task_domain"] == "docs.review"
    with pytest.raises(StateEventError, match="task_domain"):
        make_state_event(
            event_id="evt-domain-invalid",
            goal_id=GOAL_ID,
            event_type=TODO_UPDATED,
            refs={"todo_id": "todo_domain_update"},
            payload={"task_domain": "../private"},
            recorded_at="2026-07-18T00:02:00+00:00",
        )


def test_duplicate_todo_add_rejects_invalid_task_domain_atomically(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Validate one adaptive lane.",
        task_class="advancement_task",
        task_domain="validation",
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="task_domain"):
        add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text="Validate one adaptive lane.",
            task_class="advancement_task",
            task_domain="../private",
        )

    assert state.read_text(encoding="utf-8") == before
    assert _agent_todo(state, todo["todo_id"])["task_domain"] == "validation"


def test_todo_update_rejects_invalid_task_domain_atomically(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Validate one adaptive lane.",
        task_class="advancement_task",
        task_domain="validation",
        claimed_by=AUTHOR_AGENT,
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="task_domain"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            task_domain="../private",
            agent_id=AUTHOR_AGENT,
        )

    assert state.read_text(encoding="utf-8") == before
    assert _agent_todo(state, todo["todo_id"])["task_domain"] == "validation"


def test_monitor_schedule_fields_remain_monitor_only(tmp_path: Path) -> None:
    registry, _state = _write_fixture(tmp_path)

    with pytest.raises(ValueError, match="monitor schedule metadata requires"):
        add_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            role="agent",
            text="Do not attach cadence to advancement work.",
            task_class="advancement_task",
            monitor_metadata={
                "target_key": "issue-fix:owner/repo:issue_42",
                "cadence": "15m",
            },
        )


def test_claim_actor_must_match_requested_owner(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_agent_todo(registry, claimed_by=None)
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="requires --claimed-by to match"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            claimed_by=AUTHOR_AGENT,
            agent_id=REVIEW_AGENT,
            claim_only=True,
        )
    assert state.read_text(encoding="utf-8") == before

    result = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        claimed_by=AUTHOR_AGENT,
        agent_id=AUTHOR_AGENT,
        claim_only=True,
    )
    assert result["mutation_authority"]["command"] == "claim"
    assert _agent_todo(state, todo["todo_id"])["claimed_by"] == AUTHOR_AGENT


def test_monitor_writeback_propagates_multi_agent_actor(tmp_path: Path) -> None:
    registry, _state = _write_fixture(tmp_path)
    todo = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Poll one public monitor target.",
        task_class="continuous_monitor",
        claimed_by=AUTHOR_AGENT,
        monitor_metadata={"target_key": "public-pr:42", "cadence": "15m"},
    )

    result = write_monitor_poll_todo_state(
        registry_path=registry,
        goal_id=GOAL_ID,
        generated_at="2026-07-18T00:15:00+00:00",
        execute=False,
        todo_id=todo["todo_id"],
        result_hash="unchanged",
        agent_id=AUTHOR_AGENT,
    )

    assert result is not None
    authority = result["todo_update"]["mutation_authority"]
    assert authority["mode"] == "registered_peer_actor"
    assert authority["actor_agent_id"] == AUTHOR_AGENT


def test_exact_user_gate_decision_scope_uses_controller_override(
    tmp_path: Path,
) -> None:
    registry, _state = _write_fixture(tmp_path)
    target = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Publish the approved release.",
        task_class="advancement_task",
        claimed_by=AUTHOR_AGENT,
        required_decision_scopes=[DECISION_SCOPE],
    )
    gate = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="user",
        text="Approve the exact release publication.",
        task_class="user_gate",
        blocks_agent=AUTHOR_AGENT,
        decision_scope=DECISION_SCOPE,
        unblocks_todo_id=target["todo_id"],
    )

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=gate["todo_id"],
        role="user",
        decision_outcome="approve",
        evidence="owner approved the exact decision scope",
    )

    authority = result["mutation_authority"]
    assert authority["mode"] == "exact_user_gate_decision_scope_override"
    assert authority["actor_agent_id"] is None
    assert authority["target_todo_id"] == target["todo_id"]
    assert authority["decision_scope"]["scope_key"] == "publish_release"


def test_non_exact_user_gate_cannot_bypass_actor_attribution(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    target = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="agent",
        text="Announce the approved release.",
        task_class="advancement_task",
        claimed_by=AUTHOR_AGENT,
        required_decision_scopes=["direction:action:announce_release"],
    )
    gate = add_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        role="user",
        text="Approve a different action.",
        task_class="user_gate",
        blocks_agent=AUTHOR_AGENT,
        decision_scope=DECISION_SCOPE,
        unblocks_todo_id=target["todo_id"],
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="requires --agent-id"):
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=gate["todo_id"],
            role="user",
            decision_outcome="approve",
            evidence="scope mismatch",
        )

    assert state.read_text(encoding="utf-8") == before


def test_single_agent_goal_keeps_lifecycle_compatibility(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path, multi_agent=False)
    todo = _add_agent_todo(registry)

    result = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        note="legacy single-agent update",
    )

    assert result["mutation_authority"]["mode"] == "single_agent_compatibility"
    assert _agent_todo(state, todo["todo_id"])["note"] == "legacy single-agent update"


@pytest.mark.parametrize("command", ["complete", "supersede"])
def test_author_cannot_replace_explicit_independent_review(
    tmp_path: Path,
    command: str,
) -> None:
    registry, state = _write_fixture(tmp_path)
    todo = _add_agent_todo(
        registry,
        claimed_by=REVIEW_AGENT,
        excluded_agents=[AUTHOR_AGENT],
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="is excluded from mutating"):
        if command == "complete":
            complete_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                todo_id=todo["todo_id"],
                agent_id=AUTHOR_AGENT,
                evidence="author cannot self-review",
            )
        else:
            supersede_goal_todo(
                registry_path=registry,
                goal_id=GOAL_ID,
                todo_id=todo["todo_id"],
                agent_id=AUTHOR_AGENT,
                reason="author cannot replace review",
            )

    assert state.read_text(encoding="utf-8") == before


def test_delegated_orchestrator_can_complete_claimed_todo_with_reason(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(
        tmp_path,
        lifecycle_authority=[
            {
                "agent_id": ORCHESTRATION_AGENT,
                "actions": ["complete", "reassign", "supersede"],
                "requires_reason": True,
            }
        ],
    )
    todo = _add_agent_todo(registry, claimed_by=REVIEW_AGENT)

    result = complete_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        agent_id=ORCHESTRATION_AGENT,
        authority_reason="Verified the worker result and closed the stalled lane.",
        evidence="validation://orchestrator-closeout",
    )

    assert result["mutation_authority"] == {
        "schema_version": "todo_mutation_authority_v0",
        "command": "complete",
        "mode": "delegated_orchestration_override",
        "actor_agent_id": ORCHESTRATION_AGENT,
        "todo_id": todo["todo_id"],
        "claim_owner": REVIEW_AGENT,
        "authority_action": "complete",
        "authority_source": "coordination.todo_lifecycle_authority",
        "authority_reason": "Verified the worker result and closed the stalled lane.",
        "requires_reason": True,
        "registered_agent_count": 3,
    }
    assert _agent_todo(state, todo["todo_id"])["status"] == "done"


def test_delegated_orchestrator_requires_reason_before_state_write(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(
        tmp_path,
        lifecycle_authority=[
            {
                "agent_id": ORCHESTRATION_AGENT,
                "actions": ["complete"],
                "requires_reason": True,
            }
        ],
    )
    todo = _add_agent_todo(registry, claimed_by=REVIEW_AGENT)
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="requires --authority-reason"):
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            agent_id=ORCHESTRATION_AGENT,
            evidence="must remain atomic",
        )

    assert state.read_text(encoding="utf-8") == before


def test_delegated_orchestration_authority_is_action_scoped(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(
        tmp_path,
        lifecycle_authority=[
            {
                "agent_id": ORCHESTRATION_AGENT,
                "actions": ["reassign"],
                "requires_reason": True,
            }
        ],
    )
    todo = _add_agent_todo(registry, claimed_by=REVIEW_AGENT)
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="does not grant action='complete'"):
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            agent_id=ORCHESTRATION_AGENT,
            authority_reason="This grant only permits reassignment.",
            evidence="unauthorized-action",
        )
    assert state.read_text(encoding="utf-8") == before

    with pytest.raises(ValueError, match="does not grant action='update'"):
        update_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            agent_id=ORCHESTRATION_AGENT,
            claimed_by=AUTHOR_AGENT,
            status="done",
            authority_reason="A reassign grant cannot carry another mutation.",
        )
    assert state.read_text(encoding="utf-8") == before

    result = update_goal_todo(
        registry_path=registry,
        goal_id=GOAL_ID,
        todo_id=todo["todo_id"],
        agent_id=ORCHESTRATION_AGENT,
        claimed_by=AUTHOR_AGENT,
        authority_reason="Move the stalled work to an available peer.",
    )

    assert result["mutation_authority"]["authority_action"] == "reassign"
    assert _agent_todo(state, todo["todo_id"])["claimed_by"] == AUTHOR_AGENT


def test_delegated_override_never_bypasses_explicit_exclusion(
    tmp_path: Path,
) -> None:
    registry, state = _write_fixture(
        tmp_path,
        lifecycle_authority=[
            {
                "agent_id": ORCHESTRATION_AGENT,
                "actions": ["complete", "supersede"],
                "requires_reason": True,
            }
        ],
    )
    todo = _add_agent_todo(
        registry,
        claimed_by=REVIEW_AGENT,
        excluded_agents=[ORCHESTRATION_AGENT],
    )
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="is excluded from mutating"):
        complete_goal_todo(
            registry_path=registry,
            goal_id=GOAL_ID,
            todo_id=todo["todo_id"],
            agent_id=ORCHESTRATION_AGENT,
            authority_reason="An explicit exclusion remains authoritative.",
            evidence="must-not-write",
        )

    assert state.read_text(encoding="utf-8") == before
