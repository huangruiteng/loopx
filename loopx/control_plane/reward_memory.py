from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .todos.contract import normalize_todo_claimed_by


def reward_memory_goal_policy(goal: Mapping[str, Any]) -> dict[str, Any]:
    """Return the provider-neutral opt-in policy for one goal."""

    control_plane = (
        goal.get("control_plane")
        if isinstance(goal.get("control_plane"), Mapping)
        else {}
    )
    raw = (
        control_plane.get("reward_memory")
        if isinstance(control_plane.get("reward_memory"), Mapping)
        else {}
    )
    enabled_agents: list[str] = []
    for value in raw.get("enabled_agents") or []:
        agent_id = normalize_todo_claimed_by(value)
        if agent_id and agent_id not in enabled_agents:
            enabled_agents.append(agent_id)
    experimental = raw.get("experimental") is True
    return {
        "enabled": raw.get("enabled") is True and experimental,
        "experimental": experimental,
        "config_path": str(raw.get("config_path") or "").strip(),
        "enabled_agents": enabled_agents,
    }


def reward_memory_goal_policy_summary(goal: Mapping[str, Any]) -> dict[str, Any]:
    policy = reward_memory_goal_policy(goal)
    return {
        "enabled": policy["enabled"],
        "experimental": policy["experimental"],
        "config_pointer_registered": bool(policy["config_path"]),
        "enabled_agents": list(policy["enabled_agents"]),
    }
