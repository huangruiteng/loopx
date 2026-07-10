#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from loopx.control_plane.agents.identity import (  # noqa: E402
    build_identity_aware_prompt_upgrade,
    build_quota_agent_identity,
    quota_primary_agent,
    quota_registered_agents,
)
from loopx.control_plane.agents.runtime_model import (  # noqa: E402
    AgentRuntimeModel,
    agent_runtime_model_for_goal,
    peer_work_key,
    select_peer_for_work,
)


def sample_goal() -> dict:
    return {
        "id": "sample-goal",
        "coordination": {
            "registered_agents": [
                "codex-main",
                {"agent_id": "codex-side"},
                {"name": "codex-reviewer"},
                "codex-side",
            ],
            "primary_agent": "codex-main",
            "side_agent_handoff_agent": "codex-reviewer",
            "agent_profiles": {
                "codex-profiled": {
                    "review_policy": {
                        "handoff_agent": "codex-profile-reviewer",
                    }
                }
            },
        },
    }


def sample_peer_goal() -> dict:
    goal = sample_goal()
    goal["coordination"]["agent_model"] = "peer_v1"
    return goal


def assert_registered_agent_identity_contract() -> None:
    goal = sample_goal()
    goal["coordination"]["registered_agents"].extend(
        ["codex-profiled", "codex-profile-reviewer"]
    )

    assert quota_registered_agents(goal) == [
        "codex-main",
        "codex-side",
        "codex-reviewer",
        "codex-profiled",
        "codex-profile-reviewer",
    ]
    assert quota_primary_agent(goal) == "codex-main"

    primary = build_quota_agent_identity(goal, agent_id="codex-main")
    assert primary["role"] == "primary-agent", primary
    assert primary["primary_agent"] == "codex-main", primary
    assert primary["registered_agents"] == quota_registered_agents(goal), primary

    side = build_quota_agent_identity(goal, agent_id="codex-side")
    assert side["role"] == "side-agent", side
    assert side["handoff_agent"] == "codex-reviewer", side

    profiled = build_quota_agent_identity(goal, agent_id="codex-profiled")
    assert profiled["handoff_agent"] == "codex-profile-reviewer", profiled


def assert_identity_prompt_upgrade_contract() -> None:
    upgrade = build_identity_aware_prompt_upgrade(
        sample_goal(),
        goal_id="sample-goal",
        agent_identity=None,
    )
    assert upgrade["contract"] == "identity_aware_heartbeat_prompt_v1", upgrade
    assert upgrade["blocks_should_run"] is True, upgrade
    assert "codex-main" in upgrade["primary_example_command"], upgrade
    assert "codex-side" in upgrade["side_agent_example_command"], upgrade

    assert (
        build_identity_aware_prompt_upgrade(
            sample_goal(),
            goal_id="sample-goal",
            agent_identity={"agent_id": "codex-main"},
        )
        is None
    )


def assert_peer_identity_has_no_rank_or_handoff_authority() -> None:
    goal = sample_peer_goal()
    identity = build_quota_agent_identity(goal, agent_id="codex-side")
    assert identity == {
        "schema_version": "peer_agent_identity_v1",
        "agent_model": "peer_v1",
        "agent_id": "codex-side",
        "registered": True,
        "registered_agents": ["codex-main", "codex-side", "codex-reviewer"],
    }, identity

    upgrade = build_identity_aware_prompt_upgrade(
        goal,
        goal_id="sample-goal",
        agent_identity=None,
    )
    assert upgrade["contract"] == "peer_agent_heartbeat_prompt_v1", upgrade
    assert upgrade["agent_model"] == "peer_v1", upgrade
    assert "primary_example_command" not in upgrade, upgrade
    assert "side_agent_example_command" not in upgrade, upgrade
    assert [item["agent_id"] for item in upgrade["agent_example_commands"]] == [
        "codex-main",
        "codex-side",
        "codex-reviewer",
    ], upgrade


def assert_peer_model_inference_and_assignment_are_deterministic() -> None:
    inferred = sample_goal()
    inferred["coordination"].pop("primary_agent")
    inferred["coordination"].pop("side_agent_handoff_agent")
    assert agent_runtime_model_for_goal(inferred) == AgentRuntimeModel.PEER_V1
    assert agent_runtime_model_for_goal({"coordination": {}}) == (
        AgentRuntimeModel.LEGACY_HIERARCHY
    )

    work_key = peer_work_key(
        {"todo_id": "todo_peer_assignment", "reason": "frontier_exhausted"},
        fallback="replan",
    )
    selected = select_peer_for_work(
        ["codex-reviewer", "codex-main", "codex-side"],
        work_key=work_key,
    )
    assert selected in {"codex-main", "codex-side", "codex-reviewer"}
    assert select_peer_for_work(
        ["codex-side", "codex-reviewer", "codex-main", "codex-side"],
        work_key=work_key,
    ) == selected


def assert_identity_errors_are_actionable() -> None:
    try:
        build_quota_agent_identity(sample_goal(), agent_id="codex-missing")
    except ValueError as exc:
        text = str(exc)
        assert "codex-missing" in text, text
        assert "registered_agents=" in text, text
    else:
        raise AssertionError("unregistered agent should fail")

    goal = sample_goal()
    goal["coordination"]["registered_agents"] = ["codex-main", "codex-side"]
    try:
        build_quota_agent_identity(goal, agent_id="codex-side")
    except ValueError as exc:
        text = str(exc)
        assert "side_agent_handoff_agent" in text, text
        assert "codex-reviewer" in text, text
    else:
        raise AssertionError("unregistered handoff agent should fail")

    invalid_model = sample_goal()
    invalid_model["coordination"]["agent_model"] = "leader_and_workers"
    try:
        build_quota_agent_identity(invalid_model, agent_id="codex-main")
    except ValueError as exc:
        text = str(exc)
        assert "coordination.agent_model" in text, text
        assert "peer_v1" in text, text
        assert "legacy_hierarchy" in text, text
    else:
        raise AssertionError("unsupported agent runtime model should fail")


def main() -> None:
    assert_registered_agent_identity_contract()
    assert_identity_prompt_upgrade_contract()
    assert_peer_identity_has_no_rank_or_handoff_authority()
    assert_peer_model_inference_and_assignment_are_deterministic()
    assert_identity_errors_are_actionable()
    print("agent-identity-readmodel-smoke ok")


if __name__ == "__main__":
    main()
