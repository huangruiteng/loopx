#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from loopx.control_plane.agents.identity import (  # noqa: E402
    build_identity_aware_prompt_upgrade,
    build_quota_agent_identity,
    quota_registered_agents,
)
from loopx.control_plane.agents.profile import normalize_agent_profile  # noqa: E402
from loopx.control_plane.agents.runtime_model import (  # noqa: E402
    AgentRuntimeModel,
    agent_runtime_model_for_goal,
    peer_work_key,
    select_peer_for_work,
)


AGENTS = ["codex-alpha", "codex-beta", "codex-reviewer"]


def peer_goal() -> dict:
    return {
        "id": "sample-goal",
        "coordination": {
            "agent_model": "peer_v1",
            "registered_agents": AGENTS,
        },
    }


def legacy_goal() -> dict:
    goal = peer_goal()
    goal["coordination"].update(
        {
            "agent_model": "peer_v1",
            "side_agent_handoff_agent": AGENTS[2],
        }
    )
    return goal


def assert_peer_identity_has_no_rank() -> None:
    goal = peer_goal()
    assert quota_registered_agents(goal) == AGENTS
    identity = build_quota_agent_identity(goal, agent_id=AGENTS[1])
    assert identity == {
        "schema_version": "peer_agent_identity_v1",
        "agent_model": "peer_v1",
        "agent_id": AGENTS[1],
        "registered": True,
        "registered_agents": AGENTS,
    }, identity
    assert build_identity_aware_prompt_upgrade(
        goal,
        goal_id="sample-goal",
        agent_identity=identity,
    ) is None


def assert_peer_identity_projects_only_valid_advisory_profile() -> None:
    goal = peer_goal()
    profile = {
        "schema_version": "agent_profile_v1",
        "agent_id": AGENTS[1],
        "profile_role": "runtime-validation",
        "scope_summary": "Runtime checks and focused control-plane repairs.",
        "default_task_classes": ["advancement_task"],
        "preferred_action_kinds": ["runtime_*"],
        "avoid_action_kinds": ["production_*"],
    }
    goal["coordination"]["agent_profiles"] = {AGENTS[1]: profile}
    identity = build_quota_agent_identity(goal, agent_id=AGENTS[1])
    assert identity is not None
    assert identity["agent_profile"] == profile, identity

    goal["coordination"]["agent_profiles"][AGENTS[1]]["profile_role"] = (
        "primary-agent"
    )
    invalid_identity = build_quota_agent_identity(goal, agent_id=AGENTS[1])
    assert invalid_identity is not None
    assert "agent_profile" not in invalid_identity, invalid_identity


def assert_long_lived_profile_requires_vision_by_default() -> None:
    profile = normalize_agent_profile(
        {
            "agent_id": AGENTS[1],
            "default_task_classes": ["advancement_task", "continuous_monitor"],
        },
        registered_agents=AGENTS,
    )
    assert profile["vision_requirement"] == "required", profile

    optional = normalize_agent_profile(
        {
            "agent_id": AGENTS[1],
            "default_task_classes": ["advancement_task", "continuous_monitor"],
            "vision_requirement": "optional",
        },
        registered_agents=AGENTS,
    )
    assert optional["vision_requirement"] == "optional", optional

    try:
        normalize_agent_profile(
            {
                "agent_id": AGENTS[1],
                "vision_requirement": "sometimes",
            },
            registered_agents=AGENTS,
        )
    except ValueError as exc:
        assert "vision_requirement" in str(exc), exc
    else:
        raise AssertionError("invalid vision requirement should fail closed")


def assert_legacy_state_only_projects_migration() -> None:
    goal = legacy_goal()
    identity = build_quota_agent_identity(goal, agent_id=AGENTS[1])
    assert "role" not in identity, identity
    upgrade = build_identity_aware_prompt_upgrade(
        goal,
        goal_id="sample-goal",
        agent_identity=identity,
    )
    assert upgrade["contract"] == "peer_agent_heartbeat_prompt_v1", upgrade
    assert upgrade["blocks_should_run"] is True, upgrade
    assert upgrade["delivery_semantics"] == "stable_idempotent_until_ack", upgrade
    assert upgrade["migration_id"] in upgrade["completion_command"], upgrade
    assert "primary_example_command" not in upgrade, upgrade


def assert_assignment_is_deterministic() -> None:
    assert agent_runtime_model_for_goal(peer_goal()) == AgentRuntimeModel.PEER_V1
    assert agent_runtime_model_for_goal({"coordination": {}}) == AgentRuntimeModel.PEER_V1
    work_key = peer_work_key(
        {"todo_id": "todo_peer_assignment", "reason": "frontier_exhausted"},
        fallback="replan",
    )
    selected = select_peer_for_work(AGENTS, work_key=work_key)
    assert selected in set(AGENTS)
    assert select_peer_for_work(reversed(AGENTS), work_key=work_key) == selected


def assert_errors_are_actionable() -> None:
    try:
        build_quota_agent_identity(peer_goal(), agent_id="codex-missing")
    except ValueError as exc:
        assert "registered_agents=" in str(exc), exc
    else:
        raise AssertionError("unregistered agent should fail")

    invalid = peer_goal()
    invalid["coordination"]["agent_model"] = "leader_and_workers"
    try:
        build_quota_agent_identity(invalid, agent_id=AGENTS[0])
    except ValueError as exc:
        assert "must be peer_v1" in str(exc), exc
    else:
        raise AssertionError("unsupported agent runtime model should fail")


def main() -> None:
    assert_peer_identity_has_no_rank()
    assert_peer_identity_projects_only_valid_advisory_profile()
    assert_long_lived_profile_requires_vision_by_default()
    assert_legacy_state_only_projects_migration()
    assert_assignment_is_deterministic()
    assert_errors_are_actionable()
    print("agent-identity-readmodel-smoke ok")


if __name__ == "__main__":
    main()
