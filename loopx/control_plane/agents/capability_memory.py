"""Adapt registered host-local Agent observations to the typed state owner."""
from pathlib import Path
from typing import Any

from ...agent_registry import load_goal_from_registry, registered_agent_ids_for_goal
from ..effect_runtime import effect_runtime_result
from ..todos.contract import normalize_required_capabilities, normalize_todo_claimed_by


def agent_capability_memory(
    *, registry_path: Path, runtime_root: Path, goal_id: str, agent_id: str,
    available: Any = None, unavailable: Any = None, forget: Any = None,
    execute: bool = False,
) -> dict[str, Any]:
    goal_id = str(goal_id).strip()
    normalized_agent = normalize_todo_claimed_by(agent_id)
    if not normalized_agent:
        raise ValueError("agent_id must be a public-safe registered agent id")
    goal = load_goal_from_registry(registry_path, goal_id)
    result = effect_runtime_result("agent.capability_memory", {
        "schema_version": "agent_runtime_capability_request_v0",
        "runtime_root": str(runtime_root.expanduser().resolve()),
        "registry": str(registry_path.expanduser().resolve()),
        "goal_id": goal_id, "agent_id": normalized_agent,
        "registered_agents": registered_agent_ids_for_goal(goal),
        "available": normalize_required_capabilities(available),
        "unavailable": normalize_required_capabilities(unavailable),
        "forget": normalize_required_capabilities(forget),
        "execute": execute,
    })
    if not isinstance(result, dict) or result.get("schema_version") != "agent_runtime_capabilities_v0":
        raise TypeError("invalid agent runtime capability memory result")
    return result


def resolve_agent_capabilities(
    status_payload: dict[str, Any], *, goal_id: str, agent_identity: dict[str, Any] | None,
    item: dict[str, Any], project_asset: dict[str, Any], available: Any,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read current scoped observations even when the caller's status is cached."""
    from .capability_gate import _evaluate
    from ..quota.goal_boundary import declared_available_capabilities

    root, registry = status_payload.get("runtime_root"), status_payload.get("registry")
    if state is None and agent_identity and root and registry:
        state = agent_capability_memory(
            registry_path=Path(str(registry)), runtime_root=Path(str(root)),
            goal_id=goal_id, agent_id=agent_identity["agent_id"],
        )
    availability = _evaluate(
        "availability",
        goal=[*declared_available_capabilities(item), *declared_available_capabilities(project_asset)],
        runtime=normalize_required_capabilities(available), agent=state or {},
    )
    if agent_identity:
        agent_identity["capability_availability"] = availability
    return availability
