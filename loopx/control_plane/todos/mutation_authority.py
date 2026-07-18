from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ...agent_registry import (
    load_goal_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
)
from .contract import (
    TODO_TASK_CLASS_USER_GATE,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_outcome,
    normalize_todo_decision_scope,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
)


TODO_MUTATION_AUTHORITY_SCHEMA_VERSION = "todo_mutation_authority_v0"
TODO_LIFECYCLE_AUTHORITY_ACTIONS = frozenset(
    {"complete", "reassign", "supersede", "update"}
)


def normalize_todo_lifecycle_authority(
    values: Any,
    *,
    registered_agents: list[str],
) -> list[dict[str, Any]]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("coordination.todo_lifecycle_authority must be a list")
    normalized: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    for raw in values:
        if not isinstance(raw, Mapping):
            raise ValueError("each todo lifecycle authority grant must be an object")
        agent_id = normalize_todo_claimed_by(raw.get("agent_id"))
        if not agent_id:
            raise ValueError("todo lifecycle authority agent_id must be a public-safe token")
        if agent_id not in registered_agents:
            raise ValueError(
                f"todo lifecycle authority agent_id={agent_id!r} must already be registered"
            )
        if agent_id in seen_agents:
            raise ValueError(f"duplicate todo lifecycle authority grant for {agent_id!r}")
        raw_actions = raw.get("actions")
        if not isinstance(raw_actions, list) or not raw_actions:
            raise ValueError("todo lifecycle authority actions must be a non-empty list")
        actions: list[str] = []
        for value in raw_actions:
            action = str(value or "").strip().lower()
            if action not in TODO_LIFECYCLE_AUTHORITY_ACTIONS:
                raise ValueError(
                    f"unsupported todo lifecycle authority action={action!r}; "
                    "expected one of: "
                    + ", ".join(sorted(TODO_LIFECYCLE_AUTHORITY_ACTIONS))
                )
            if action not in actions:
                actions.append(action)
        requires_reason = raw.get("requires_reason", True)
        if not isinstance(requires_reason, bool):
            raise ValueError("todo lifecycle authority requires_reason must be boolean")
        normalized.append(
            {
                "agent_id": agent_id,
                "actions": actions,
                "requires_reason": requires_reason,
            }
        )
        seen_agents.add(agent_id)
    return normalized


def todo_lifecycle_authority_for_goal(
    goal: Mapping[str, Any] | None,
    *,
    agent_id: str,
    registered_agents: list[str],
) -> dict[str, Any] | None:
    if not isinstance(goal, Mapping):
        return None
    coordination = goal.get("coordination")
    if not isinstance(coordination, Mapping):
        return None
    grants = normalize_todo_lifecycle_authority(
        coordination.get("todo_lifecycle_authority"),
        registered_agents=registered_agents,
    )
    return next((grant for grant in grants if grant["agent_id"] == agent_id), None)


def todo_update_authority_action(
    *,
    existing_role: str,
    role: str | None,
    claimed_by: str | None,
    clear_claim: bool,
    other_values: tuple[Any, ...],
    monitor_metadata: Mapping[str, Any] | None,
) -> str | None:
    if claimed_by is None and not clear_claim:
        return None
    has_other_change = bool(
        (role is not None and role != existing_role)
        or any(value is not None and value is not False for value in other_values)
        or any(value is not None for value in (monitor_metadata or {}).values())
    )
    return "update" if has_other_change else "reassign"


def _scope_identity(scope: Mapping[str, Any] | None) -> tuple[str, str, str] | None:
    normalized = normalize_todo_decision_scope(scope)
    if not normalized:
        return None
    return (
        str(normalized.get("kind") or ""),
        str(normalized.get("granularity") or ""),
        str(normalized.get("scope_key") or ""),
    )


def _exact_user_gate_override(
    *,
    command: str,
    todo: Mapping[str, Any],
    decision_outcome: str | None,
    decision_target: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        command != "complete"
        or str(todo.get("role") or "") != "user"
        or str(todo.get("task_class") or "") != TODO_TASK_CLASS_USER_GATE
        or normalize_todo_decision_outcome(decision_outcome) is None
    ):
        return None
    gate_scope = normalize_todo_decision_scope(todo.get("decision_scope"))
    gate_scope_identity = _scope_identity(gate_scope)
    target_todo_id = normalize_todo_id(todo.get("unblocks_todo_id"))
    if (
        not gate_scope
        or not gate_scope_identity
        or not target_todo_id
        or not decision_target
        or normalize_todo_id(decision_target.get("todo_id")) != target_todo_id
    ):
        return None
    target_scope_identities = {
        identity
        for scope in normalize_todo_required_decision_scopes(
            decision_target.get("required_decision_scopes")
        )
        if (identity := _scope_identity(scope)) is not None
    }
    if gate_scope_identity not in target_scope_identities:
        return None
    return {
        "schema_version": TODO_MUTATION_AUTHORITY_SCHEMA_VERSION,
        "command": command,
        "mode": "exact_user_gate_decision_scope_override",
        "actor_agent_id": None,
        "todo_id": normalize_todo_id(todo.get("todo_id")),
        "target_todo_id": target_todo_id,
        "decision_outcome": normalize_todo_decision_outcome(decision_outcome),
        "decision_scope": gate_scope,
        "authority_source": "linked_user_gate_decision_scope",
    }


def authorize_todo_lifecycle_mutation(
    *,
    registry_path: Path,
    goal_id: str,
    command: str,
    todo: Mapping[str, Any],
    actor_agent_id: str | None,
    authority_action: str | None = None,
    authority_reason: str | None = None,
    requested_claimed_by: str | None = None,
    decision_outcome: str | None = None,
    decision_target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Authorize one existing-todo lifecycle mutation before state changes."""

    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    normalized_actor = normalize_todo_claimed_by(actor_agent_id)
    normalized_todo_id = normalize_todo_id(todo.get("todo_id"))
    if len(registered_agents) <= 1:
        if normalized_actor and registered_agents:
            normalized_actor = require_registered_agent_id(
                registry_path=registry_path,
                goal_id=goal_id,
                agent_id=normalized_actor,
                field="agent_id",
            )
        return {
            "schema_version": TODO_MUTATION_AUTHORITY_SCHEMA_VERSION,
            "command": command,
            "mode": "single_agent_compatibility",
            "actor_agent_id": normalized_actor,
            "todo_id": normalized_todo_id,
            "registered_agent_count": len(registered_agents),
        }

    override = _exact_user_gate_override(
        command=command,
        todo=todo,
        decision_outcome=decision_outcome,
        decision_target=decision_target,
    )
    if override:
        override["registered_agent_count"] = len(registered_agents)
        return override

    if not normalized_actor:
        raise ValueError(
            f"multi-agent todo {command} requires --agent-id to attribute the "
            "lifecycle actor; only completion of an exactly linked user_gate "
            "decision_scope may use the typed owner/controller override"
        )
    normalized_actor = require_registered_agent_id(
        registry_path=registry_path,
        goal_id=goal_id,
        agent_id=normalized_actor,
        field="agent_id",
    )
    excluded_agents = normalize_todo_excluded_agents(todo.get("excluded_agents"))
    if normalized_actor in excluded_agents:
        raise ValueError(
            f"agent_id={normalized_actor!r} is excluded from mutating todo_id="
            f"{normalized_todo_id!r}"
        )
    bound_agent = normalize_todo_bound_agent(todo.get("bound_agent"))
    if not bound_agent and str(todo.get("role") or "") == "user":
        bound_agent = normalize_todo_blocks_agent(todo.get("blocks_agent"))
    if bound_agent and bound_agent != normalized_actor:
        raise ValueError(
            f"agent_id={normalized_actor!r} cannot {command} user todo_id="
            f"{normalized_todo_id!r}; its response continuation is bound to "
            f"bound_agent={bound_agent!r}"
        )
    claim_owner = normalize_todo_claimed_by(todo.get("claimed_by"))
    if claim_owner and claim_owner != normalized_actor:
        effective_action = str(authority_action or command).strip().lower()
        grant = todo_lifecycle_authority_for_goal(
            load_goal_from_registry(registry_path, goal_id),
            agent_id=normalized_actor,
            registered_agents=registered_agents,
        )
        if grant is None:
            raise ValueError(
                f"agent_id={normalized_actor!r} cannot {command} todo_id="
                f"{normalized_todo_id!r}; it is claimed_by={claim_owner!r}"
            )
        if effective_action not in grant["actions"]:
            raise ValueError(
                "coordination.todo_lifecycle_authority for "
                f"agent_id={normalized_actor!r} does not grant "
                f"action={effective_action!r}"
            )
        normalized_reason = str(authority_reason or "").strip()
        if grant["requires_reason"] and not normalized_reason:
            raise ValueError(
                f"delegated {effective_action} override requires --authority-reason"
            )
        return {
            "schema_version": TODO_MUTATION_AUTHORITY_SCHEMA_VERSION,
            "command": command,
            "mode": "delegated_orchestration_override",
            "actor_agent_id": normalized_actor,
            "todo_id": normalized_todo_id,
            "claim_owner": claim_owner,
            "authority_action": effective_action,
            "authority_source": "coordination.todo_lifecycle_authority",
            "authority_reason": normalized_reason or None,
            "requires_reason": grant["requires_reason"],
            "registered_agent_count": len(registered_agents),
        }
    requested_owner = normalize_todo_claimed_by(requested_claimed_by)
    if command == "claim" and requested_owner != normalized_actor:
        raise ValueError(
            "todo claim requires --claimed-by to match the lifecycle "
            "--agent-id; use todo update for an owner-attributed transfer"
        )
    return {
        "schema_version": TODO_MUTATION_AUTHORITY_SCHEMA_VERSION,
        "command": command,
        "mode": "registered_peer_actor",
        "actor_agent_id": normalized_actor,
        "todo_id": normalized_todo_id,
        "claim_owner": claim_owner,
        "registered_agent_count": len(registered_agents),
    }
