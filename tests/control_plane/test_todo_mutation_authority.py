from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.scheduler.monitor_poll_writeback import (
    write_monitor_poll_todo_state,
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
