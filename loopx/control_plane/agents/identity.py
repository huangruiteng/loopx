from __future__ import annotations

from typing import Any

from ...agent_registry import (
    primary_agent_id_for_goal,
    registered_agent_ids_for_goal,
    side_agent_handoff_agent_id_for_goal,
)
from ..todos.contract import normalize_todo_claimed_by
from .runtime_model import (
    PEER_AGENT_IDENTITY_SCHEMA_VERSION,
    AgentRuntimeModel,
    agent_runtime_model_for_goal,
)


def quota_registered_agents(goal: dict[str, Any]) -> list[str]:
    return registered_agent_ids_for_goal(goal)


def quota_primary_agent(goal: dict[str, Any]) -> str | None:
    return primary_agent_id_for_goal(goal)


def build_quota_agent_identity(
    goal: dict[str, Any],
    *,
    agent_id: str | None,
) -> dict[str, Any] | None:
    normalized_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
    if agent_id and not normalized_agent_id:
        raise ValueError("agent_id must be a public-safe registered agent id")
    registered_agents = quota_registered_agents(goal)
    if not normalized_agent_id:
        return None
    if not registered_agents:
        raise ValueError(
            "quota should-run --agent-id requires coordination.registered_agents; "
            "register this agent identity first"
        )
    if normalized_agent_id not in registered_agents:
        raise ValueError(
            f"agent_id={normalized_agent_id!r} is not registered; "
            f"registered_agents={', '.join(registered_agents)}"
        )
    runtime_model = agent_runtime_model_for_goal(goal)
    if runtime_model == AgentRuntimeModel.PEER_V1:
        return {
            "schema_version": PEER_AGENT_IDENTITY_SCHEMA_VERSION,
            "agent_model": runtime_model.value,
            "agent_id": normalized_agent_id,
            "registered": True,
            "registered_agents": registered_agents,
        }
    primary_agent = quota_primary_agent(goal)
    handoff_agent = side_agent_handoff_agent_id_for_goal(goal, agent_id=normalized_agent_id)
    if handoff_agent:
        if handoff_agent not in registered_agents:
            raise ValueError(
                f"side_agent_handoff_agent={handoff_agent!r} is not registered; "
                f"registered_agents={', '.join(registered_agents)}"
            )
    return {
        "agent_id": normalized_agent_id,
        "registered": True,
        "role": "primary-agent" if primary_agent and normalized_agent_id == primary_agent else "side-agent",
        "primary_agent": primary_agent,
        "handoff_agent": handoff_agent,
        "registered_agents": registered_agents,
    }


def build_identity_aware_prompt_upgrade(
    goal: dict[str, Any],
    *,
    goal_id: str,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    registered_agents = quota_registered_agents(goal)
    if not registered_agents or agent_identity:
        return None
    runtime_model = agent_runtime_model_for_goal(goal)
    if runtime_model == AgentRuntimeModel.PEER_V1:
        return {
            "contract": "peer_agent_heartbeat_prompt_v1",
            "required": True,
            "blocks_should_run": True,
            "reason": (
                "coordination.registered_agents is configured for peer_v1, but quota "
                "should-run was called without --agent-id; the installed automation "
                "prompt is stale or unscoped"
            ),
            "agent_model": runtime_model.value,
            "registered_agents": registered_agents,
            "recommended_action": (
                "Regenerate each installed heartbeat with its registered --agent-id, "
                "then rerun quota should-run with the same identity."
            ),
            "agent_example_commands": [
                {
                    "agent_id": agent,
                    "command": (
                        f"loopx heartbeat-prompt --thin --goal-id {goal_id} "
                        f"--agent-id {agent} --agent-scope 'peer task claims and leases'"
                    ),
                }
                for agent in registered_agents
            ],
        }
    primary_agent = quota_primary_agent(goal)
    primary_hint = primary_agent if primary_agent in registered_agents else registered_agents[0]
    side_hint = next((agent for agent in registered_agents if agent != primary_hint), primary_hint)
    return {
        "contract": "identity_aware_heartbeat_prompt_v1",
        "required": True,
        "blocks_should_run": True,
        "reason": (
            "coordination.registered_agents is configured, but quota should-run "
            "was called without --agent-id; the installed automation prompt is "
            "likely stale or unscoped"
        ),
        "registered_agents": registered_agents,
        "primary_agent": primary_agent,
        "recommended_action": (
            "Regenerate the installed heartbeat automation prompt with a "
            "registered --agent-id and at least one --agent-scope, then rerun "
            "quota should-run with the same --agent-id."
        ),
        "primary_example_command": (
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} "
            f"--agent-id {primary_hint} --agent-scope "
            "'primary review, verification, merge, and coordination'"
        ),
        "side_agent_example_command": (
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} "
            f"--agent-id {side_hint} --agent-scope "
            "'bounded side-agent work in an independent worktree'"
        ),
    }
