from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from ...state_projection import actions_are_projection_aligned
from ..goals.contract_health import project_contract_health_for_goal
from ..goals.goal_frontier import (
    AUTONOMOUS_REPLAN_REQUIRED_MODE,
    autonomous_replan_decision_allowed,
    goal_frontier_is_terminal_no_followup,
)
from ..todos.contract import normalize_todo_claimed_by
from ..work_items.work_lane import work_lane_contract_is_due_monitor_attempt


class QuotaDecisionPacket(TypedDict, total=False):
    goal_id: str
    decision: str
    should_run: bool
    effective_action: str
    normal_delivery_allowed: bool
    recovery_delivery_allowed: bool
    self_repair_allowed: bool
    capability_repair_allowed: bool
    workspace_repair_allowed: bool
    state: str
    safe_bypass_allowed: bool
    safe_bypass_kind: str
    blocked_action_scope: str
    compute: float
    window_hours: int
    slot_minutes: int
    spent_slots: int
    allowed_slots: int
    capability_gate: dict[str, Any]
    interaction_contract: dict[str, Any]
    scheduler_hint: dict[str, Any]
    reason: str


def compact_quota_decision(decision: dict[str, Any]) -> QuotaDecisionPacket:
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
    """Keep global guards fail-closed without importing unrelated goal errors."""

    contract = (
        status_payload.get("contract")
        if isinstance(status_payload.get("contract"), dict)
        else {}
    )
    if "error_diagnostics" not in contract:
        return fallback
    global_registry = status_payload.get("global_registry")
    if isinstance(global_registry, dict) and global_registry.get("ok") is False:
        return False
    scoped = project_contract_health_for_goal(contract, goal_id=goal_id)
    return scoped.get("ok") is True


@dataclass(frozen=True)
class QuotaRunDecision:
    normal_delivery_allowed: bool
    recovery_delivery_allowed: bool
    self_repair_allowed: bool
    capability_repair_allowed: bool
    workspace_repair_allowed: bool
    should_run: bool
    effective_action: str
    reason: str
    state: str
    quota: dict[str, Any]
    replan_decision_allowed: bool


def refine_quota_recommended_action(
    selected_action: Any,
    *,
    task_orchestration_contract: dict[str, Any] | None,
    capability_gate: dict[str, Any] | None,
    capability_monitor_fallback: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    workspace_guard: dict[str, Any] | None,
    automation_prompt_upgrade: dict[str, Any] | None,
    automation_prompt_upgrade_required: bool,
    replan_obligation: dict[str, Any] | None,
    replan_decision_allowed: bool,
) -> Any:
    """Apply ordered quota guards before agent-lane frontier refinement."""

    refined = (
        str(
            task_orchestration_contract.get("coordinator_obligation")
            or selected_action
            or ""
        )
        if task_orchestration_contract
        else selected_action
    )
    if (
        capability_monitor_fallback
        and isinstance(work_lane_contract, dict)
        and work_lane_contract.get("action")
    ):
        refined = work_lane_contract["action"]

    due_monitor_attempt = work_lane_contract_is_due_monitor_attempt(work_lane_contract)
    if capability_gate and not due_monitor_attempt and not capability_monitor_fallback:
        if capability_gate.get("action") in {"repair_bridge", "ask_owner", "skip"}:
            refined = (
                capability_gate.get("owner_action")
                or capability_gate.get("reason")
                or refined
            )
        elif capability_gate.get("action") == "run":
            blocked = capability_gate.get("blocked_candidates")
            blocked = blocked if isinstance(blocked, list) else []
            runnable = capability_gate.get("runnable_candidates")
            runnable = runnable if isinstance(runnable, list) else []
            if any(
                isinstance(item, dict)
                and actions_are_projection_aligned(refined, item.get("text"))
                for item in blocked
            ):
                refined = next(
                    (
                        text
                        for item in runnable
                        if isinstance(item, dict)
                        and (text := str(item.get("text") or "").strip())
                    ),
                    refined,
                )

    if workspace_guard:
        refined = (
            workspace_guard.get("required_action")
            or workspace_guard.get("reason")
            or refined
        )
    if automation_prompt_upgrade_required:
        upgrade = automation_prompt_upgrade or {}
        refined = upgrade.get("recommended_action") or upgrade.get("reason") or refined
    if replan_decision_allowed:
        obligation = replan_obligation or {}
        refined = (
            str(obligation.get("recommended_action") or "").strip()
            or str(obligation.get("stop_condition") or "").strip()
            or (
                "Run one bounded autonomous replan slice and write back the "
                "selected todo/frontier changes."
            )
        )
    return refined


def resolve_quota_run_decision(
    *,
    normal_delivery_allowed: bool,
    recovery_delivery_allowed: bool,
    self_repair_allowed: bool,
    stall_self_repair: dict[str, Any] | None,
    state: str,
    quota: dict[str, Any],
    reason: str,
    capability_gate: dict[str, Any] | None,
    capability_monitor_fallback: dict[str, Any] | None,
    workspace_guard: dict[str, Any] | None,
    automation_prompt_upgrade: dict[str, Any] | None,
    automation_prompt_upgrade_required: bool,
    replan_obligation: dict[str, Any] | None,
    goal_health_ok: bool,
    inbox_reply_due: bool,
    agent_frontier_id: str | None,
    registered_agent_ids: list[str],
    goal_frontier_projection: dict[str, Any] | None,
    task_orchestration_contract: dict[str, Any] | None,
) -> QuotaRunDecision:
    """Apply the ordered final guards for one quota run decision."""

    capability_repair_allowed = False
    workspace_repair_allowed = False
    if (
        capability_gate
        and capability_gate.get("action") != "run"
        and not capability_monitor_fallback
    ):
        normal_delivery_allowed = False
        recovery_delivery_allowed = False
        if capability_gate.get("action") == "repair_bridge":
            capability_repair_allowed = True
            reason = str(
                capability_gate.get("reason") or "capability bridge repair required"
            )
        else:
            reason = str(
                capability_gate.get("reason")
                or "selected todo capability is unavailable"
            )
    if workspace_guard:
        normal_delivery_allowed = False
        recovery_delivery_allowed = False
        self_repair_allowed = False
        capability_repair_allowed = False
        workspace_repair_allowed = True
        reason = str(
            workspace_guard.get("reason") or "agent workspace guard blocks delivery"
        )
    if automation_prompt_upgrade_required:
        normal_delivery_allowed = False
        recovery_delivery_allowed = False
        self_repair_allowed = False
        capability_repair_allowed = False
        workspace_repair_allowed = False
        reason = str(
            (automation_prompt_upgrade or {}).get("reason")
            or "identity-aware automation prompt upgrade is required"
        )

    should_run = bool(
        normal_delivery_allowed
        or recovery_delivery_allowed
        or self_repair_allowed
        or capability_repair_allowed
        or workspace_repair_allowed
    )
    effective_action = quota_effective_action(
        normal_delivery_allowed=normal_delivery_allowed,
        recovery_delivery_allowed=recovery_delivery_allowed,
        self_repair_allowed=self_repair_allowed,
        capability_repair_allowed=capability_repair_allowed,
        workspace_repair_allowed=workspace_repair_allowed,
        stall_self_repair=stall_self_repair,
        state=state,
        quota=quota,
    )
    replan_decision_allowed = (
        not inbox_reply_due
        and autonomous_replan_decision_allowed(
            replan_obligation=replan_obligation,
            plan_ok=goal_health_ok,
            workspace_blocked=bool(workspace_guard),
            automation_prompt_upgrade_required=automation_prompt_upgrade_required,
            agent_id=agent_frontier_id,
            registered_agent_ids=registered_agent_ids,
        )
    )
    if replan_decision_allowed:
        normal_delivery_allowed = False
        recovery_delivery_allowed = False
        should_run = True
        effective_action = AUTONOMOUS_REPLAN_REQUIRED_MODE
        reason = (
            "autonomous replan obligation is selected before monitor quiet "
            "or agent-scope wait classification"
        )

    terminal_no_followup = goal_frontier_is_terminal_no_followup(
        projection=goal_frontier_projection
    )
    if terminal_no_followup and not inbox_reply_due:
        quota = {
            **quota,
            "state": "terminal_no_followup",
            "reason": (
                "derived terminal no-follow-up is confirmed by complete todo "
                "sources and an empty frontier"
            ),
        }
        state = "terminal_no_followup"
        normal_delivery_allowed = False
        recovery_delivery_allowed = False
        self_repair_allowed = False
        capability_repair_allowed = False
        workspace_repair_allowed = False
        should_run = False
        effective_action = "terminal_no_followup"
        reason = (
            "validated closure evidence derives terminal no-follow-up from "
            "complete todo sources and an empty frontier; stop recurring "
            "automation until an explicit resume"
        )

    if automation_prompt_upgrade_required and not terminal_no_followup:
        should_run = False
        effective_action = "automation_prompt_upgrade_required"
    elif inbox_reply_due:
        should_run = True
        normal_delivery_allowed = True
        recovery_delivery_allowed = False
        self_repair_allowed = False
        capability_repair_allowed = False
        workspace_repair_allowed = False
        effective_action = "lark_inbox_reply_due"
        reason = (
            "a direct Lark question, bot mention, or verified reply to the bot "
            "is pending reply"
        )

    effective_action, reason = _task_orchestration_effective_action(
        task_orchestration_contract,
        should_run=should_run,
        normal_delivery_allowed=normal_delivery_allowed,
        effective_action=effective_action,
        reason=reason,
    )
    return QuotaRunDecision(
        normal_delivery_allowed=normal_delivery_allowed,
        recovery_delivery_allowed=recovery_delivery_allowed,
        self_repair_allowed=self_repair_allowed,
        capability_repair_allowed=capability_repair_allowed,
        workspace_repair_allowed=workspace_repair_allowed,
        should_run=should_run,
        effective_action=effective_action,
        reason=reason,
        state=state,
        quota=quota,
        replan_decision_allowed=replan_decision_allowed,
    )


def quota_effective_action(
    *,
    normal_delivery_allowed: bool,
    recovery_delivery_allowed: bool,
    self_repair_allowed: bool,
    capability_repair_allowed: bool,
    workspace_repair_allowed: bool,
    stall_self_repair: dict[str, Any] | None,
    state: str,
    quota: dict[str, Any],
) -> str:
    if normal_delivery_allowed:
        return "normal_run"
    if recovery_delivery_allowed:
        return "outcome_floor_recovery"
    if workspace_repair_allowed:
        return "agent_workspace_repair"
    if self_repair_allowed:
        repair_action = (
            stall_self_repair.get("effective_action")
            if isinstance(stall_self_repair, dict)
            else None
        )
        return str(repair_action or "control_plane_repair")
    if capability_repair_allowed:
        return "capability_bridge_repair"
    if state == "operator_gate":
        return "operator_gate_notify"
    if state == "blocked_health":
        return "blocked_health"
    if state == "throttled":
        return "throttled_skip"
    if state in {"focus_wait", "waiting"} or quota.get("focus_wait"):
        return "blocked_wait"
    return "quota_skip"


def _task_orchestration_effective_action(
    contract: dict[str, Any] | None,
    *,
    should_run: bool,
    normal_delivery_allowed: bool,
    effective_action: str,
    reason: str,
) -> tuple[str, str]:
    if (
        contract
        and should_run
        and normal_delivery_allowed
        and effective_action == "normal_run"
    ):
        return (
            "coordinate_task_bundle",
            "the deterministic task coordinator must activate or resume eligible "
            "peer lanes before doing its own worker-lane delivery",
        )
    return effective_action, reason
