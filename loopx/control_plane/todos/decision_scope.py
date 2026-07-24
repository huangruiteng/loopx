"""Decision-scope relation helpers for LoopX user gates.

This module keeps user-gate dependency semantics out of quota allocation so
other control-plane surfaces can reason about the same exact-todo and
decision-scope relations without importing the quota runtime.
"""

from __future__ import annotations

from typing import Any

from .contract import (
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_outcome,
    normalize_todo_decision_scope,
    normalize_todo_decision_scope_outcomes,
    normalize_todo_global_gate,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
    normalize_todo_status,
)
from .user_gate import is_user_gate_todo_item

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

DECISION_SCOPE_CONSISTENCY_SCHEMA_VERSION = "required_decision_scope_consistency_v0"
STANDING_DECISION_AUTHORITY_SCHEMA_VERSION = "standing_decision_authority_v0"
STANDING_DECISION_RECEIPT_SCHEMA_VERSION = "standing_decision_receipt_v0"
STANDING_DECISION_GRANULARITIES = frozenset({"goal", "project", "global"})
_AGENT_SUMMARY_ITEM_KEYS = (
    "current_agent_claimed_open_items",
    "current_agent_claimed_advancement_items",
    "first_executable_items",
    "executable_backlog_items",
    "first_open_items",
    "backlog_items",
    "items",
)
_USER_SUMMARY_ITEM_KEYS = (
    "gate_open_items",
    "user_action_open_items",
    "first_open_items",
    "backlog_items",
    "items",
    "other_agent_scoped_items",
)


def _summary_open_items(
    summary: dict[str, Any] | None,
    *,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    items: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for key in keys:
        values = summary.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict) or item.get("done") is True:
                continue
            if str(item.get("status") or "open") not in {"open", "blocked"}:
                continue
            identity = (item.get("todo_id"), item.get("index"), item.get("text"))
            if identity in seen:
                continue
            seen.add(identity)
            items.append(item)
    return items


def _source_open_items(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if items is None:
        return []
    return [
        item
        for item in items
        if isinstance(item, dict)
        and item.get("done") is not True
        and str(item.get("status") or "open") in {"open", "blocked"}
    ]


def _gate_owner_compatible(gate: dict[str, Any], *, agent_id: str | None) -> bool:
    if normalize_todo_global_gate(gate.get("global_gate")):
        return True
    normalized_agent_id = normalize_todo_claimed_by(agent_id)
    blocks_agent = normalize_todo_blocks_agent(gate.get("blocks_agent"))
    claimed_by = normalize_todo_claimed_by(gate.get("claimed_by"))
    if not normalized_agent_id:
        return not blocks_agent and not claimed_by
    if blocks_agent and blocks_agent != normalized_agent_id:
        return False
    return not claimed_by or claimed_by == normalized_agent_id


def _scope_identity(scope: dict[str, Any]) -> str:
    return f"{scope['kind']}:{scope['granularity']}:{scope['scope_key']}"


def is_standing_decision_receipt_item(item: dict[str, Any]) -> bool:
    """Return whether a completed user gate is a reusable decision receipt."""

    if not is_user_gate_todo_item(item):
        return False
    status = normalize_todo_status(
        item.get("status") or ("done" if item.get("done") else "open")
    )
    if status != "done":
        return False
    if normalize_todo_id(item.get("unblocks_todo_id")):
        return False
    scope = normalize_todo_decision_scope(item.get("decision_scope"))
    outcome = normalize_todo_decision_outcome(item.get("decision_outcome"))
    if not scope or not outcome:
        return False
    if scope["granularity"] not in STANDING_DECISION_GRANULARITIES:
        return False
    return bool(
        normalize_todo_global_gate(item.get("global_gate"))
        or normalize_todo_blocks_agent(item.get("blocks_agent"))
    )


def build_standing_decision_authority(
    user_items: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Compile latest broad, unlinked user-gate decisions into receipts."""

    latest_by_identity: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in user_items or []:
        if not isinstance(item, dict) or not is_standing_decision_receipt_item(item):
            continue
        scope = normalize_todo_decision_scope(item.get("decision_scope"))
        outcome = normalize_todo_decision_outcome(item.get("decision_outcome"))
        source_todo_id = normalize_todo_id(item.get("todo_id"))
        if not scope or not outcome or not source_todo_id:
            continue
        global_gate = bool(normalize_todo_global_gate(item.get("global_gate")))
        blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
        owner_key = "global" if global_gate else f"agent:{blocks_agent}"
        receipt: dict[str, Any] = {
            "schema_version": STANDING_DECISION_RECEIPT_SCHEMA_VERSION,
            "source_todo_id": source_todo_id,
            "decision_scope": scope,
            "outcome": outcome,
            "active": outcome == "approve",
            "global_gate": global_gate,
        }
        if blocks_agent:
            receipt["blocks_agent"] = blocks_agent
        for key in ("completed_at", "updated_at"):
            value = str(item.get(key) or "").strip()
            if value:
                receipt[key] = value
        identity = (
            scope["kind"],
            scope["granularity"],
            scope["scope_key"],
            owner_key,
        )
        latest_by_identity[identity] = receipt
    if not latest_by_identity:
        return None
    entries = list(latest_by_identity.values())
    return {
        "schema_version": STANDING_DECISION_AUTHORITY_SCHEMA_VERSION,
        "active_count": sum(entry["active"] is True for entry in entries),
        "inactive_count": sum(entry["active"] is not True for entry in entries),
        "entries": entries,
    }


def standing_decision_authority_for_agent(
    authority: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> dict[str, Any] | None:
    """Filter standing decision receipts to one agent lane."""

    if not isinstance(authority, dict):
        return None
    entries = authority.get("entries")
    if not isinstance(entries, list):
        return None
    compatible = [
        dict(entry)
        for entry in entries
        if isinstance(entry, dict)
        and _gate_owner_compatible(entry, agent_id=agent_id)
    ]
    if not compatible:
        return None
    return {
        "schema_version": STANDING_DECISION_AUTHORITY_SCHEMA_VERSION,
        "agent_id": normalize_todo_claimed_by(agent_id),
        "active_count": sum(entry.get("active") is True for entry in compatible),
        "inactive_count": sum(entry.get("active") is not True for entry in compatible),
        "entries": compatible,
    }


def _standing_authority_receipts_covering(
    authority: dict[str, Any] | None,
    required_scope: dict[str, Any],
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    scoped = standing_decision_authority_for_agent(authority, agent_id=agent_id)
    if not scoped:
        return []
    return [
        entry
        for entry in scoped["entries"]
        if entry.get("active") is True
        and decision_scope_covers(entry.get("decision_scope"), required_scope)
    ]


def build_required_decision_scope_consistency(
    agent_todo_summary: dict[str, Any] | None,
    user_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
    registered_agent_ids: list[str] | None = None,
    agent_source_items: list[dict[str, Any]] | None = None,
    user_source_items: list[dict[str, Any]] | None = None,
    standing_decision_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate that blocking decision dependencies resolve to live user gates."""

    agent_items = (
        _source_open_items(agent_source_items)
        if agent_source_items is not None
        else _summary_open_items(agent_todo_summary, keys=_AGENT_SUMMARY_ITEM_KEYS)
    )
    user_items = (
        _source_open_items(user_source_items)
        if user_source_items is not None
        else _summary_open_items(user_todo_summary, keys=_USER_SUMMARY_ITEM_KEYS)
    )
    gates = [item for item in user_items if is_user_gate_todo_item(item)]
    user_actions = [item for item in user_items if not is_user_gate_todo_item(item)]
    errors: list[dict[str, Any]] = []
    checked_scope_count = 0
    terminal_outcome_count = 0
    standing_authority_match_count = 0

    registered_agents = sorted(
        {
            normalized
            for value in registered_agent_ids or []
            if (normalized := normalize_todo_claimed_by(value))
        }
    )
    if len(registered_agents) > 1:
        for gate in gates:
            if normalize_todo_global_gate(gate.get("global_gate")):
                continue
            if normalize_todo_blocks_agent(gate.get("blocks_agent")):
                continue
            errors.append(
                {
                    "reason_code": "multi_agent_user_gate_missing_scope",
                    "user_todo_id": normalize_todo_id(gate.get("todo_id")),
                    "registered_agent_ids": registered_agents,
                }
            )

    for agent_item in agent_items:
        claimed_by = normalize_todo_claimed_by(agent_item.get("claimed_by"))
        normalized_agent_id = normalize_todo_claimed_by(agent_id)
        if claimed_by and normalized_agent_id and claimed_by != normalized_agent_id:
            continue
        effective_owner = normalized_agent_id or claimed_by
        required_scopes = normalize_todo_required_decision_scopes(
            agent_item.get("required_decision_scopes")
        )
        for required_scope in required_scopes:
            checked_scope_count += 1
            matching_gates = [
                gate
                for gate in gates
                if decision_scope_covers(gate.get("decision_scope"), required_scope)
            ]
            compatible_gates = [
                gate
                for gate in matching_gates
                if _gate_owner_compatible(gate, agent_id=effective_owner)
            ]
            if compatible_gates:
                continue
            standing_receipts = _standing_authority_receipts_covering(
                standing_decision_authority,
                required_scope,
                agent_id=effective_owner,
            )
            if standing_receipts:
                standing_authority_match_count += 1
                continue
            terminal_outcomes = [
                item
                for item in normalize_todo_decision_scope_outcomes(
                    agent_item.get("decision_scope_outcomes")
                )
                if item.get("outcome") in {"reject", "cancel"}
                and decision_scope_covers(
                    item.get("decision_scope"),
                    required_scope,
                )
            ]
            if terminal_outcomes:
                terminal_outcome_count += 1
                if str(agent_item.get("status") or "open") != "blocked":
                    errors.append(
                        {
                            "reason_code": "terminal_decision_outcome_target_not_blocked",
                            "agent_todo_id": normalize_todo_id(
                                agent_item.get("todo_id")
                            ),
                            "required_scope": _scope_identity(required_scope),
                            "related_user_todo_ids": [
                                item["source_todo_id"] for item in terminal_outcomes
                            ],
                        }
                    )
                continue
            matching_actions = [
                item
                for item in user_actions
                if decision_scope_covers(item.get("decision_scope"), required_scope)
            ]
            if matching_actions:
                reason_code = "non_blocking_user_action_scope_collision"
                related_ids = [normalize_todo_id(item.get("todo_id")) for item in matching_actions]
            elif matching_gates:
                reason_code = "required_decision_scope_gate_owner_mismatch"
                related_ids = [normalize_todo_id(item.get("todo_id")) for item in matching_gates]
            else:
                reason_code = "dangling_required_decision_scope"
                related_ids = []
            errors.append(
                {
                    "reason_code": reason_code,
                    "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
                    "required_scope": _scope_identity(required_scope),
                    "related_user_todo_ids": [item for item in related_ids if item],
                }
            )

    return {
        "schema_version": DECISION_SCOPE_CONSISTENCY_SCHEMA_VERSION,
        "ok": not errors,
        "status": "consistent" if not errors else "projection_repair_required",
        "agent_id": normalize_todo_claimed_by(agent_id),
        "checked_agent_todo_count": len(agent_items),
        "checked_required_scope_count": checked_scope_count,
        "terminal_outcome_count": terminal_outcome_count,
        "standing_authority_match_count": standing_authority_match_count,
        "errors": errors,
    }


def build_required_decision_scope_repair_hint(
    consistency: dict[str, Any],
) -> dict[str, Any] | None:
    if consistency.get("ok") is not False:
        return None
    errors = consistency.get("errors") if isinstance(consistency.get("errors"), list) else []
    missing_gate_scope = any(
        isinstance(error, dict)
        and error.get("reason_code") == "multi_agent_user_gate_missing_scope"
        for error in errors
    )
    if missing_gate_scope:
        return {
            "source": "quota.should-run",
            "trigger": "user_gate_scope_projection_drift",
            "recommended_mode": "repair_user_gate_scope_projection",
            "effective_action": "todo_decision_scope_projection_repair",
            "blocked_action_scope": "todo_user_gate_scope_projection",
            "allowed": True,
            "notify": "DONT_NOTIFY",
            "reason": (
                "a multi-agent user_gate lacks blocks_agent or explicit "
                "global_gate=true, so its blocking authority is ambiguous"
            ),
            "repair_focus": (
                "set blocks_agent to one registered agent, set global_gate=true for "
                "intentional goal-wide authority, or downgrade the item to user_action"
            ),
            "spend_policy": (
                "spend once only after the gate-scope projection repair is validated "
                "and written back"
            ),
            "consistency": consistency,
        }
    return {
        "source": "quota.should-run",
        "trigger": "required_decision_scope_projection_drift",
        "recommended_mode": "repair_required_decision_scope_projection",
        "effective_action": "todo_decision_scope_projection_repair",
        "blocked_action_scope": "todo_decision_scope_projection",
        "allowed": True,
        "notify": "DONT_NOTIFY",
        "reason": (
            "an agent todo requires a decision scope that does not resolve to a "
            "compatible open user_gate"
        ),
        "repair_focus": (
            "remove stale required_decision_scopes, create the explicit blocking "
            "user_gate, or correct its agent ownership; user_action remains non-blocking"
        ),
        "spend_policy": (
            "spend once only after the todo/gate projection repair is validated and written back"
        ),
        "consistency": consistency,
    }


def decision_scope_covers(gate_scope: Any, required_scope: Any) -> bool:
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
