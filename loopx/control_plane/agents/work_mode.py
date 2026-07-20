from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..todos.contract import normalize_todo_claimed_by


AGENT_WORK_MODE_ACTIVE = "active"
AGENT_WORK_MODE_MONITOR_ONLY = "monitor_only"
AGENT_WORK_MODE_VALUES = {
    AGENT_WORK_MODE_ACTIVE,
    AGENT_WORK_MODE_MONITOR_ONLY,
}


def normalize_agent_work_modes(
    value: Any,
    *,
    registered_agents: list[str],
) -> dict[str, str]:
    if value in (None, {}):
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("coordination.agent_work_modes must be an object")
    registered = set(registered_agents)
    result: dict[str, str] = {}
    for raw_agent_id, raw_mode in value.items():
        agent_id = normalize_todo_claimed_by(raw_agent_id)
        if not agent_id or agent_id not in registered:
            raise ValueError("agent work mode must name a registered peer")
        mode = str(raw_mode or "").strip().lower()
        if mode not in AGENT_WORK_MODE_VALUES:
            raise ValueError(
                "agent work mode must be one of: "
                + ", ".join(sorted(AGENT_WORK_MODE_VALUES))
            )
        result[agent_id] = mode
    return dict(sorted(result.items()))


def agent_work_mode_for_goal(
    goal: Mapping[str, Any] | None,
    agent_id: Any,
) -> str | None:
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    if not isinstance(goal, Mapping) or not safe_agent_id:
        return None
    coordination = goal.get("coordination")
    if not isinstance(coordination, Mapping):
        return None
    modes = coordination.get("agent_work_modes")
    if not isinstance(modes, Mapping):
        return None
    mode = str(modes.get(safe_agent_id) or "").strip().lower()
    return mode if mode in AGENT_WORK_MODE_VALUES else None
