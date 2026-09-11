"""Legacy input codec for the single typed decision-dependency rule owner."""
from __future__ import annotations

from typing import Any

from ..effect_runtime import effect_runtime_result
from .contract import (
    normalize_todo_blocks_agent, normalize_todo_claimed_by,
    normalize_todo_decision_scope, normalize_todo_decision_scope_outcomes,
    normalize_todo_global_gate, normalize_todo_id, normalize_todo_required_decision_scopes,
)
from .user_gate import is_user_gate_todo_item

TODO_GATE_BLOCKING_STATES = frozenset(
    {"gate_targets_todo", "gate_covers_action", "projection_repair_required"}
)
DECISION_SCOPE_CONSISTENCY_SCHEMA_VERSION = "required_decision_scope_consistency_v0"
STANDING_DECISION_AUTHORITY_SCHEMA_VERSION = "standing_decision_authority_v0"
_AGENT_SUMMARY_ITEM_KEYS = (
    "current_agent_claimed_open_items", "current_agent_claimed_advancement_items",
    "first_executable_items", "executable_backlog_items", "first_open_items", "backlog_items", "items",
)
_USER_SUMMARY_ITEM_KEYS = (
    "gate_open_items", "user_action_open_items", "first_open_items",
    "backlog_items", "items", "other_agent_scoped_items",
)


def _evaluate(operation: str, **facts: Any) -> Any:
    result = effect_runtime_result("todo.decision_scope.evaluate", {
        "schema_version": "todo_decision_scope_request_v0", "operation": operation, **facts,
    })
    if not isinstance(result, dict) or result.get("schema_version") != "todo_decision_scope_result_v0":
        raise TypeError("invalid typed decision scope projection")
    return result["result"]


def _facts(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "todo_id": normalize_todo_id(item.get("todo_id")),
        "status": str(item.get("status") or "open"), "done": item.get("done") is True,
        "claimed_by": normalize_todo_claimed_by(item.get("claimed_by")),
        "blocks_agent": normalize_todo_blocks_agent(item.get("blocks_agent")),
        "global_gate": bool(normalize_todo_global_gate(item.get("global_gate"))),
        "unblocks_todo_id": normalize_todo_id(item.get("unblocks_todo_id")),
        "decision_scope": normalize_todo_decision_scope(item.get("decision_scope")),
        "required_decision_scopes": normalize_todo_required_decision_scopes(item.get("required_decision_scopes")),
        "decision_scope_outcomes": normalize_todo_decision_scope_outcomes(item.get("decision_scope_outcomes")),
        # Preserve the existing legacy classification boundary, not new prose authority.
        "is_gate": is_user_gate_todo_item(item),
    }


def _source(summary: dict[str, Any] | None, source: list[dict[str, Any]] | None,
            keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if source is not None:
        return [_facts(item) for item in source if isinstance(item, dict)]
    if not isinstance(summary, dict):
        return []
    result = []
    seen = set()
    for key in keys:
        values = (summary or {}).get(key)
        for item in values if isinstance(values, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("done") is True or str(item.get("status") or "open") not in {"open", "blocked"}:
                continue
            identity = (item.get("todo_id"), item.get("index"), item.get("text"))
            if identity not in seen:
                seen.add(identity)
                result.append(_facts(item))
    return result


def _authority(authority: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(authority, dict) or not isinstance(authority.get("entries"), list):
        return None
    def decoded(entry: dict[str, Any]) -> dict[str, Any]:
        codecs = {"global_gate": normalize_todo_global_gate, "blocks_agent": normalize_todo_blocks_agent,
                  "claimed_by": normalize_todo_claimed_by, "decision_scope": normalize_todo_decision_scope}
        return {**entry, **{key: codec(entry[key]) for key, codec in codecs.items() if key in entry}}

    return {**authority, "entries": [decoded(entry) for entry in authority["entries"] if isinstance(entry, dict)],
            "conflicts": [decoded(entry) for entry in authority.get("conflicts", []) if isinstance(entry, dict)]
            if isinstance(authority.get("conflicts"), list) else []}


def standing_decision_authority_for_agent(authority: dict[str, Any] | None, *,
                                          agent_id: str | None) -> dict[str, Any] | None:
    if _authority(authority) is None:
        return None
    return _evaluate("standing", authority=_authority(authority),
                     agent_id=normalize_todo_claimed_by(agent_id))


def build_required_decision_scope_consistency(
    agent_todo_summary: dict[str, Any] | None, user_todo_summary: dict[str, Any] | None, *,
    agent_id: str | None, registered_agent_ids: list[str] | None = None,
    agent_source_items: list[dict[str, Any]] | None = None,
    user_source_items: list[dict[str, Any]] | None = None,
    standing_decision_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _evaluate("consistency",
        agent_items=_source(agent_todo_summary, agent_source_items, _AGENT_SUMMARY_ITEM_KEYS),
        user_items=_source(user_todo_summary, user_source_items, _USER_SUMMARY_ITEM_KEYS),
        agent_id=normalize_todo_claimed_by(agent_id),
        registered_agents=sorted({value for raw in registered_agent_ids or []
                                  if (value := normalize_todo_claimed_by(raw))}),
        standing_authority=_authority(standing_decision_authority),
    )


def build_required_decision_scope_repair_hint(
    consistency: dict[str, Any],
) -> dict[str, Any] | None:
    if consistency.get("ok") is not False:
        return None
    raw_errors = consistency.get("errors")
    errors = raw_errors if isinstance(raw_errors, list) else []
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
    result = {
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
    if any(isinstance(error, dict) and error.get("reason_code") == "standing_decision_order_unresolved"
           for error in errors):
        result.update(
            reason="contradictory standing decisions have no established chronological winner",
            repair_focus=(
                "reconcile decision chronology against explicit owner evidence; do not remove "
                "required_decision_scopes or invent approval merely to clear this conflict"
            ),
        )
    elif any(isinstance(error, dict) and error.get("reason_code") == "required_decision_scope_target_mismatch"
             for error in errors):
        result.update(
            reason="a scope-covering user gate explicitly targets a different Todo",
            repair_focus=(
                "reconcile the exact target and required scope against owner intent; do not "
                "remove the requirement, retarget the gate, or invent approval merely to clear the conflict"
            ),
        )
    return result


def decision_scope_covers(gate_scope: Any, required_scope: Any) -> bool:
    gate = normalize_todo_decision_scope(gate_scope)
    required = normalize_todo_decision_scope(required_scope)
    if not gate or not required:
        return False
    return _evaluate("covers", gate_scope=gate, required_scope=required)


def decision_scope_gate_relation(gate: dict[str, Any], agent_item: dict[str, Any]) -> dict[str, Any] | None:
    return _evaluate("scope_relation", gate=_facts(gate), item=_facts(agent_item))


def exact_todo_gate_relation(gate: dict[str, Any], agent_item: dict[str, Any]) -> dict[str, Any] | None:
    return _evaluate("exact_relation", gate=_facts(gate), item=_facts(agent_item))


def todo_gate_relation(gate: dict[str, Any], agent_item: dict[str, Any]) -> dict[str, Any] | None:
    return _evaluate("relation", gate=_facts(gate), item=_facts(agent_item))


def todo_gate_relations(gates: list[dict[str, Any]], items: list[dict[str, Any]]) -> list[list[dict[str, Any] | None]]:
    """Evaluate a consumer's candidate set in one RPC, retaining positional identity."""
    if not gates or not items:
        return [[] for _ in gates]
    return _evaluate("relations", gates=[_facts(gate) for gate in gates], items=[_facts(item) for item in items])


def todo_gate_relation_blocks_agent(relation: dict[str, Any] | None) -> bool:
    return bool(relation and relation.get("state") in TODO_GATE_BLOCKING_STATES)
