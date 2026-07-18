from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ...agent_registry import (
    registered_agent_ids_from_registry,
    require_registered_agent_id,
)
from .contract import (
    TODO_TASK_CLASS_USER_GATE,
    normalize_todo_claimed_by,
    normalize_todo_decision_outcome,
    normalize_todo_decision_scope,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
)


TODO_MUTATION_AUTHORITY_SCHEMA_VERSION = "todo_mutation_authority_v0"


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
    claim_owner = normalize_todo_claimed_by(todo.get("claimed_by"))
    if claim_owner and claim_owner != normalized_actor:
        raise ValueError(
            f"agent_id={normalized_actor!r} cannot {command} todo_id="
            f"{normalized_todo_id!r}; it is claimed_by={claim_owner!r}"
        )
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
