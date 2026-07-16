from __future__ import annotations

from typing import Any

from .. import compact_control_plane_policy, control_plane_self_repair_allows
from ..todos.decision_scope import (
    build_required_decision_scope_consistency,
    build_required_decision_scope_repair_hint,
)
from ..todos.user_gate import open_todo_count


STALL_HEALTH_ITEM_COMPACT_FIELDS = (
    "goal_id",
    "status",
    "waiting_on",
    "severity",
    "source",
    "recommended_action",
)
DECISION_SCOPE_REPAIR_TRIGGER = "required_decision_scope_projection_drift"


def _compact_health_items(
    items: list[Any],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = {
            field: item.get(field)
            for field in STALL_HEALTH_ITEM_COMPACT_FIELDS
            if item.get(field)
        }
        if payload:
            compact.append(payload)
        if len(compact) >= limit:
            break
    return compact


def build_quota_stall_self_repair_hint(
    item: dict[str, Any],
    *,
    state: str,
    plan_ok: bool,
    health_items: list[Any],
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_id: str | None,
    user_todo_source_items: list[dict[str, Any]] | None = None,
    agent_todo_source_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    decision_scope_consistency = build_required_decision_scope_consistency(
        agent_todo_summary,
        user_todo_summary,
        agent_id=agent_id,
        agent_source_items=agent_todo_source_items,
        user_source_items=user_todo_source_items,
    )
    decision_scope_repair = build_required_decision_scope_repair_hint(
        decision_scope_consistency
    )
    if decision_scope_repair:
        return decision_scope_repair

    control_plane = compact_control_plane_policy(item.get("control_plane"))
    if not control_plane:
        return None

    if not plan_ok and control_plane_self_repair_allows(
        control_plane,
        "health_blocker_repair",
    ):
        blockers = _compact_health_items(health_items)
        if blockers:
            return {
                "source": "quota.should-run",
                "trigger": "health_blocker",
                "recommended_mode": "repair_control_plane_health",
                "effective_action": "control_plane_health_repair",
                "allowed": True,
                "notify": "DONT_NOTIFY",
                "reason": (
                    "status or contract health blocks normal delivery; spend one "
                    "bounded turn on control-plane repair instead of quiet spinning"
                ),
                "repair_focus": (
                    "inspect the compact health blocker, repair registry/status/"
                    "contract projection or public-boundary scan scope, validate, "
                    "write a durable event, then spend once"
                ),
                "spend_policy": (
                    "append exactly one heartbeat spend only after the health blocker "
                    "is repaired, validated, and written back"
                ),
                "control_plane": control_plane,
                "blocking_health_items": blockers,
            }

    waiting_on = str(item.get("waiting_on") or "")
    has_user_todos = open_todo_count(user_todo_summary) > 0
    has_agent_todos = open_todo_count(agent_todo_summary) > 0
    has_next_action = bool(str(item.get("recommended_action") or "").strip())
    has_project_asset = isinstance(item.get("project_asset"), dict)
    unknown_waiting_owner = waiting_on in {"", "none", "unknown", "null"}
    if (
        control_plane_self_repair_allows(control_plane, "waiting_projection_repair")
        and state == "waiting"
        and unknown_waiting_owner
        and not has_user_todos
        and (has_next_action or has_agent_todos or has_project_asset)
    ):
        return {
            "source": "quota.should-run",
            "trigger": "waiting_without_owner_projection",
            "recommended_mode": "repair_waiting_projection",
            "effective_action": "control_plane_projection_repair",
            "allowed": True,
            "notify": "DONT_NOTIFY",
            "reason": (
                "goal is waiting without a concrete owner/evidence gate while current "
                "action or agent backlog exists"
            ),
            "repair_focus": (
                "rebase from registry, active state, status, and run history; either "
                "project waiting_on=codex for safe agent work or write the concrete "
                "user/controller/evidence blocker"
            ),
            "spend_policy": (
                "append exactly one heartbeat spend only after the projection or "
                "blocker writeback is validated"
            ),
            "control_plane": control_plane,
        }

    return None


def apply_stall_repair_delivery_guard(
    repair: dict[str, Any] | None,
    *,
    normal_delivery_allowed: bool,
    recovery_allowed: bool,
    reason: str,
) -> tuple[bool, bool, str]:
    if not repair or repair.get("trigger") != DECISION_SCOPE_REPAIR_TRIGGER:
        return normal_delivery_allowed, recovery_allowed, reason
    return False, False, str(repair.get("reason") or reason)


def stall_repair_blocked_action_scope(repair: dict[str, Any] | None) -> str | None:
    if not repair or repair.get("trigger") != DECISION_SCOPE_REPAIR_TRIGGER:
        return None
    value = str(repair.get("blocked_action_scope") or "").strip()
    return value or None


def stall_repair_payload(repair: dict[str, Any] | None) -> dict[str, Any]:
    if not repair or repair.get("trigger") != DECISION_SCOPE_REPAIR_TRIGGER:
        return {}
    consistency = repair.get("consistency")
    if not isinstance(consistency, dict):
        return {}
    return {"todo_decision_scope_consistency": consistency}
