from __future__ import annotations

from typing import Any

from ...agent_registry import registered_agent_ids_for_goal
from ..todos.contract import normalize_todo_claimed_by
from .runtime_model import (
    PEER_AGENT_IDENTITY_SCHEMA_VERSION,
    agent_runtime_model_for_goal,
    legacy_agent_hierarchy_present,
    peer_agent_runtime_migration_id,
)


def quota_registered_agents(goal: dict[str, Any]) -> list[str]:
    return registered_agent_ids_for_goal(goal)


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
    return {
        "schema_version": PEER_AGENT_IDENTITY_SCHEMA_VERSION,
        "agent_model": runtime_model.value,
        "agent_id": normalized_agent_id,
        "registered": True,
        "registered_agents": registered_agents,
    }


def build_identity_aware_prompt_upgrade(
    goal: dict[str, Any],
    *,
    goal_id: str,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    registered_agents = quota_registered_agents(goal)
    if not registered_agents:
        return None
    migration_required = legacy_agent_hierarchy_present(goal)
    if agent_identity and not migration_required:
        return None
    runtime_model = agent_runtime_model_for_goal(goal)
    migration_id = (
        peer_agent_runtime_migration_id(goal_id, goal)
        if migration_required
        else None
    )
    return {
        "contract": "peer_agent_heartbeat_prompt_v1",
        "required": True,
        "blocks_should_run": True,
        "reason": (
            "v0.1 hierarchy fields are still present, so an installed automation may "
            "still carry main/side instructions"
            if migration_required
            else "coordination.registered_agents is configured for peer_v1, but quota "
            "should-run was called without --agent-id; the installed automation "
            "prompt is stale or unscoped"
        ),
        "agent_model": runtime_model.value,
        "registered_agents": registered_agents,
        "recommended_action": (
            "Regenerate each installed heartbeat with its registered --agent-id; "
            "update each host automation once using migration_id as its idempotency "
            "key; then run completion_command and rerun quota."
            if migration_required
            else "Regenerate each installed heartbeat with its registered --agent-id, "
            "then rerun quota should-run with the same identity."
        ),
        "registry_migration_required": migration_required,
        "migration_id": migration_id,
        "host_update_idempotency_key": migration_id,
        "delivery_semantics": (
            "stable_idempotent_until_ack" if migration_required else None
        ),
        "registry_migration_command": (
            "loopx configure-goal "
            f"--goal-id {goal_id} "
            f"--ack-automation-prompt-migration {migration_id} --execute"
            if migration_required
            else None
        ),
        "completion_command": (
            "loopx configure-goal "
            f"--goal-id {goal_id} "
            f"--ack-automation-prompt-migration {migration_id} --execute"
            if migration_required
            else None
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
