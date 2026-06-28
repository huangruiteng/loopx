"""Decision-scope relation helpers for LoopX user gates.

This module keeps user-gate dependency semantics out of quota allocation so
other control-plane surfaces can reason about the same exact-todo and
decision-scope relations without importing the quota runtime.
"""

from __future__ import annotations

from typing import Any

from .todo_contract import (
    normalize_todo_decision_scope,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
)


DECISION_SCOPE_GRANULARITY_RANK = {
    "action": 0,
    "lane": 1,
    "goal": 2,
    "project": 3,
    "global": 4,
}

TODO_GATE_BLOCKING_STATES = frozenset(
    {"gate_targets_todo", "gate_covers_action", "projection_repair_required"}
)


def decision_scope_covers(gate_scope: dict[str, Any], required_scope: dict[str, Any]) -> bool:
    gate = normalize_todo_decision_scope(gate_scope)
    required = normalize_todo_decision_scope(required_scope)
    if not gate or not required:
        return False
    if gate["kind"] != required["kind"]:
        return False
    if gate["scope_key"] not in {required["scope_key"], "*"}:
        return False
    return DECISION_SCOPE_GRANULARITY_RANK[gate["granularity"]] >= DECISION_SCOPE_GRANULARITY_RANK[
        required["granularity"]
    ]


def decision_scope_gate_relation(
    gate: dict[str, Any],
    agent_item: dict[str, Any],
) -> dict[str, Any] | None:
    gate_scope = normalize_todo_decision_scope(gate.get("decision_scope"))
    required_scopes = normalize_todo_required_decision_scopes(
        agent_item.get("required_decision_scopes")
    )
    if not gate_scope:
        return None
    if not required_scopes:
        return {
            "schema_version": "decision_scope_relation_v0",
            "source": "decision_scope",
            "state": "independent",
            "reason": "agent_todo_has_no_required_decision_scopes",
            "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
            "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
            "decision_scope": gate_scope,
            "required_decision_scopes": [],
        }
    for required_scope in required_scopes:
        if decision_scope_covers(gate_scope, required_scope):
            return {
                "schema_version": "decision_scope_relation_v0",
                "source": "decision_scope",
                "state": "gate_covers_action",
                "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
                "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
                "decision_scope": gate_scope,
                "matched_required_decision_scope": required_scope,
                "required_decision_scopes": required_scopes,
            }
    return {
        "schema_version": "decision_scope_relation_v0",
        "source": "decision_scope",
        "state": "independent",
        "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
        "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
        "decision_scope": gate_scope,
        "required_decision_scopes": required_scopes,
    }


def exact_todo_gate_relation(
    gate: dict[str, Any],
    agent_item: dict[str, Any],
) -> dict[str, Any] | None:
    target_todo_id = normalize_todo_id(gate.get("unblocks_todo_id"))
    if not target_todo_id:
        return None
    agent_todo_id = normalize_todo_id(agent_item.get("todo_id"))
    return {
        "schema_version": "todo_gate_relation_v0",
        "source": "unblocks_todo_id",
        "state": "gate_targets_todo" if target_todo_id == agent_todo_id else "independent",
        "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
        "target_todo_id": target_todo_id,
        "agent_todo_id": agent_todo_id,
    }


def todo_gate_relation(gate: dict[str, Any], agent_item: dict[str, Any]) -> dict[str, Any] | None:
    exact_relation = exact_todo_gate_relation(gate, agent_item)
    scope_relation = decision_scope_gate_relation(gate, agent_item)

    if (
        exact_relation
        and scope_relation
        and exact_relation.get("state") == "independent"
        and scope_relation.get("state") == "gate_covers_action"
    ):
        return {
            "schema_version": "todo_gate_relation_v0",
            "source": "unblocks_todo_id+decision_scope",
            "state": "projection_repair_required",
            "reason": "decision_scope_covers_agent_todo_but_unblocks_todo_targets_different_todo",
            "gate_todo_id": exact_relation.get("gate_todo_id"),
            "target_todo_id": exact_relation.get("target_todo_id"),
            "agent_todo_id": exact_relation.get("agent_todo_id"),
            "exact_todo_relation": exact_relation,
            "decision_scope_relation": scope_relation,
        }

    if exact_relation and exact_relation.get("state") == "gate_targets_todo":
        if scope_relation:
            exact_relation["decision_scope_relation"] = scope_relation
        return exact_relation

    if scope_relation and scope_relation.get("state") == "gate_covers_action":
        if exact_relation:
            scope_relation["exact_todo_relation"] = exact_relation
        return scope_relation

    if exact_relation:
        if scope_relation:
            exact_relation["decision_scope_relation"] = scope_relation
        return exact_relation

    return scope_relation


def todo_gate_relation_blocks_agent(relation: dict[str, Any] | None) -> bool:
    if not relation:
        return False
    return relation.get("state") in TODO_GATE_BLOCKING_STATES
