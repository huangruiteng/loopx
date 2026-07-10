from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Iterable, Mapping

from ..todos.contract import normalize_todo_claimed_by


PEER_AGENT_IDENTITY_SCHEMA_VERSION = "peer_agent_identity_v1"


class AgentRuntimeModel(str, Enum):
    LEGACY_HIERARCHY = "legacy_hierarchy"
    PEER_V1 = "peer_v1"


def agent_runtime_model_for_goal(goal: Mapping[str, Any] | None) -> AgentRuntimeModel:
    if not isinstance(goal, Mapping):
        return AgentRuntimeModel.LEGACY_HIERARCHY
    coordination = goal.get("coordination")
    raw = coordination.get("agent_model") if isinstance(coordination, Mapping) else None
    raw = raw or goal.get("agent_model")
    if not raw and isinstance(coordination, Mapping):
        registered_agents = coordination.get("registered_agents")
        has_registered_agents = bool(
            isinstance(registered_agents, (list, tuple)) and registered_agents
        )
        has_legacy_authority = bool(
            coordination.get("primary_agent")
            or coordination.get("side_agent_handoff_agent")
        )
        if has_registered_agents and not has_legacy_authority:
            return AgentRuntimeModel.PEER_V1
    try:
        return AgentRuntimeModel(str(raw or AgentRuntimeModel.LEGACY_HIERARCHY.value))
    except ValueError as error:
        raise ValueError(
            "coordination.agent_model must be one of: "
            + ", ".join(model.value for model in AgentRuntimeModel)
        ) from error


def agent_identity_is_peer(agent_identity: Mapping[str, Any] | None) -> bool:
    return bool(
        isinstance(agent_identity, Mapping)
        and agent_identity.get("agent_model") == AgentRuntimeModel.PEER_V1.value
    )


def normalized_peer_agent_ids(values: Iterable[Any]) -> list[str]:
    agents = sorted(
        {
            agent
            for value in values
            for agent in [normalize_todo_claimed_by(value)]
            if agent
        }
    )
    return agents


def peer_work_key(value: Mapping[str, Any] | None, *, fallback: str) -> str:
    if not isinstance(value, Mapping):
        return fallback
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def select_peer_for_work(
    registered_agents: Iterable[Any],
    *,
    work_key: str,
) -> str | None:
    agents = normalized_peer_agent_ids(registered_agents)
    if not agents:
        return None
    digest = hashlib.sha256(str(work_key).encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % len(agents)
    return agents[index]
