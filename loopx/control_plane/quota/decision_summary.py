from __future__ import annotations

from typing import Any

from ..todos.contract import normalize_todo_claimed_by


def compact_quota_decision(decision: dict[str, Any]) -> dict[str, Any]:
    quota = decision.get("quota") if isinstance(decision.get("quota"), dict) else {}
    return {
        "should_run": bool(decision.get("should_run")),
        "normal_delivery_allowed": bool(decision.get("normal_delivery_allowed")),
        "recovery_delivery_allowed": bool(decision.get("recovery_delivery_allowed")),
        "effective_action": decision.get("effective_action"),
        "self_repair_allowed": bool(decision.get("self_repair_allowed")),
        "capability_repair_allowed": bool(decision.get("capability_repair_allowed")),
        "workspace_repair_allowed": bool(decision.get("workspace_repair_allowed")),
        "state": str(decision.get("state") or ""),
        "safe_bypass_allowed": bool(decision.get("safe_bypass_allowed")),
        "safe_bypass_kind": decision.get("safe_bypass_kind"),
        "blocked_action_scope": decision.get("blocked_action_scope"),
        "compute": quota.get("compute"),
        "window_hours": quota.get("window_hours"),
        "slot_minutes": quota.get("slot_minutes"),
        "spent_slots": quota.get("spent_slots"),
        "allowed_slots": quota.get("allowed_slots"),
    }


def quota_decision_agent_id(decision: dict[str, Any]) -> str | None:
    agent_identity = (
        decision.get("agent_identity")
        if isinstance(decision.get("agent_identity"), dict)
        else {}
    )
    return normalize_todo_claimed_by(agent_identity.get("agent_id"))


def goal_status_health_ok(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    fallback: bool,
) -> bool:
    """Isolate goal-owned todo errors while keeping global guards fail-closed."""

    contract = status_payload.get("contract")
    if not isinstance(contract, dict) or "global_errors" not in contract:
        return fallback
    global_registry = status_payload.get("global_registry")
    if isinstance(global_registry, dict) and global_registry.get("ok") is False:
        return False
    global_errors = contract.get("global_errors")
    if isinstance(global_errors, list) and global_errors:
        return False
    goal_errors = contract.get("goal_errors")
    if not isinstance(goal_errors, dict):
        return fallback
    selected_errors = goal_errors.get(goal_id)
    return not (isinstance(selected_errors, list) and selected_errors)
