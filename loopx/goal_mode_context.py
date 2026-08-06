"""Host-neutral project goal context resolution.

Host adapters own how a goal/agent binding is persisted. This module owns the
shared registry lookup and projection so every adapter selects the same LoopX
goal contract without reading another host's private state.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REGISTRY_DIRS = (".loopx", ".goal-harness")


def find_registry(cwd: str | Path) -> Path | None:
    """Return the nearest project-local LoopX registry."""
    try:
        current = Path(cwd).resolve()
    except (OSError, RuntimeError):
        return None
    for directory in (current, *current.parents):
        for registry_dir in REGISTRY_DIRS:
            candidate = directory / registry_dir / "registry.json"
            if candidate.is_file():
                return candidate
    return None


def project_root_for(cwd: str | Path) -> Path | None:
    registry = find_registry(cwd)
    return registry.parent.parent if registry else None


def registered_agent_ids(goal: dict[str, Any]) -> tuple[str, ...]:
    coordination = goal.get("coordination") or {}
    result: list[str] = []
    for entry in coordination.get("registered_agents") or []:
        value: Any = entry
        if isinstance(entry, dict):
            value = entry.get("id") or entry.get("agent_id") or entry.get("name")
        token = str(value or "").strip()
        if token and token not in result:
            result.append(token)
    return tuple(result)


def first_registered_agent(goal: dict[str, Any]) -> str | None:
    agents = registered_agent_ids(goal)
    return agents[0] if agents else None


def resolve_goal_context(
    cwd: str | Path,
    *,
    preferred_goal_id: str | None = None,
    preferred_agent_id: str | None = None,
    require_preferred_binding: bool = False,
) -> dict[str, Any] | None:
    """Resolve one goal from the nearest registry and an optional host binding.

    ``require_preferred_binding`` is used by hosts such as KunlunCode whose
    identity must never fall back to another host's first registered agent.
    """
    registry = find_registry(cwd)
    if registry is None:
        return None
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    goals = [goal for goal in data.get("goals") or [] if isinstance(goal, dict)]
    if not goals:
        return None
    chosen = None
    preferred_goal_matched = False
    if preferred_goal_id:
        chosen = next(
            (goal for goal in goals if str(goal.get("id") or "") == preferred_goal_id),
            None,
        )
        preferred_goal_matched = chosen is not None
        if chosen is None and require_preferred_binding:
            return None
    if chosen is None:
        chosen = goals[0]

    agents = registered_agent_ids(chosen)
    preferred_agent = str(preferred_agent_id or "").strip()
    if preferred_goal_id and not preferred_goal_matched:
        preferred_agent = ""
    agent_id = preferred_agent or first_registered_agent(chosen)
    if require_preferred_binding and (
        not preferred_agent_id or preferred_agent_id not in agents
    ):
        return None

    root = registry.parent.parent
    repo = chosen.get("repo")
    scope = str(repo or root).replace("\\", "/")
    return {
        "goal_id": chosen.get("id"),
        "registry": str(registry).replace("\\", "/"),
        "agent_id": agent_id,
        "write_scope": [scope],
        "project_root": str(root).replace("\\", "/"),
    }
