from __future__ import annotations
from .effective_action import EffectiveAction

from typing import Any, Protocol

from ..effect_program import ReceiptBoundReplayPhase


HEARTBEAT_SETTLED_REPLAY_REASON = (
    "the receipt-bound Todo completion and required settlement receipts "
    "are complete for this heartbeat turn; defer successor selection to a new turn"
)

_ACTION_PROJECTION_KEYS = (
    "agent_command",
    "action_portfolio",
    "agent_lane_frontier_hint",
    "agent_lane_next_action",
    "agent_scope_frontier",
    "autonomous_replan_decision",
    "autonomous_replan_obligation",
    "autonomous_replan_scope",
    "blocked_priority_fallback",
    "capability_gate",
    "capability_monitor_fallback",
    "external_evidence_observation",
    "goal_route_hint",
    "notify_user_on_capability_gate",
    "notify_user_on_gate",
    "notify_user_on_open_todo",
    "open_todo_notification_policy",
    "open_todo_notify_reason",
    "required_reads",
    "replan_action_packet",
    "scoped_user_gate_fallback",
    "stall_self_repair",
    "vision_continuation_audit",
    "vision_wait_state",
    "workspace_guard",
)


class SettledReplayRoute(Protocol):
    normal_delivery_allowed: bool
    recovery_allowed: bool
    self_repair_allowed: bool
    capability_repair_allowed: bool
    workspace_repair_allowed: bool
    should_run: bool
    effective_action: str
    reason: str
    replan_decision_allowed: bool
    receipt_bound_replan_decision: bool
    heartbeat_recommendation: dict[str, Any]
    external_evidence_observation: dict[str, Any] | None
    external_evidence_observation_recent: dict[str, Any] | None
    selected_recommended_action: Any
    agent_lane_next_action: dict[str, Any] | None
    agent_scope_frontier: dict[str, Any] | None
    agent_lane_frontier_hint: dict[str, Any] | None
    state_action_projection_warning: dict[str, Any] | None
    next_action_warning: dict[str, Any] | None
    goal_route_hint: dict[str, Any] | None


def apply_settled_replay_route_precedence(
    route: SettledReplayRoute,
    *,
    replay_phase: ReceiptBoundReplayPhase | None,
) -> None:
    """Prevent a settled heartbeat identity from selecting work in the same turn."""

    if replay_phase is not ReceiptBoundReplayPhase.SETTLED:
        return
    route.normal_delivery_allowed = False
    route.recovery_allowed = False
    route.self_repair_allowed = False
    route.capability_repair_allowed = False
    route.workspace_repair_allowed = False
    route.should_run = False
    route.effective_action = EffectiveAction.HEARTBEAT_SETTLED_SKIP.value
    route.reason = HEARTBEAT_SETTLED_REPLAY_REASON
    route.replan_decision_allowed = False
    route.receipt_bound_replan_decision = False
    route.heartbeat_recommendation = {
        **route.heartbeat_recommendation,
        "recommended_mode": route.effective_action,
        "notify": "DONT_NOTIFY",
        "reason": route.reason,
        "spend_policy": "no quota spend for an already-settled heartbeat turn",
    }
    route.external_evidence_observation = None
    route.external_evidence_observation_recent = None
    route.selected_recommended_action = route.reason
    route.agent_lane_next_action = None
    route.agent_scope_frontier = None
    route.agent_lane_frontier_hint = None
    route.state_action_projection_warning = None
    route.next_action_warning = None
    route.goal_route_hint = None


def clear_quota_action_projections(
    payload: dict[str, Any],
    *,
    additional_keys: tuple[str, ...] = (),
) -> None:
    for key in (*_ACTION_PROJECTION_KEYS, *additional_keys):
        payload.pop(key, None)


def apply_settled_replay_payload_precedence(
    payload: dict[str, Any],
    *,
    replay_phase: ReceiptBoundReplayPhase | None,
) -> None:
    """Keep late supporting projections from reopening a settled heartbeat turn."""

    if replay_phase is not ReceiptBoundReplayPhase.SETTLED:
        return
    reason = HEARTBEAT_SETTLED_REPLAY_REASON
    payload.update(
        {
            "decision": "skip",
            "should_run": False,
            "normal_delivery_allowed": False,
            "recovery_delivery_allowed": False,
            "self_repair_allowed": False,
            "capability_repair_allowed": False,
            "workspace_repair_allowed": False,
            "effective_action": EffectiveAction.HEARTBEAT_SETTLED_SKIP.value,
            "actionable_by_codex": False,
            "reason": reason,
            "requires_user_action": False,
            "recommended_action": (
                "Finish this heartbeat without another action; use a fresh turn "
                "identity for successor selection."
            ),
            "heartbeat_recommendation": {
                "recommended_mode": "heartbeat_settled_skip",
                "notify": "DONT_NOTIFY",
                "reason": reason,
                "spend_policy": "no quota spend for an already-settled heartbeat turn",
                "agent_must_attempt": False,
            },
            "execution_obligation": {
                "must_attempt_work": False,
                "kind": "heartbeat_settled_skip",
                "delivery_allowed": False,
                "notify_is_execution_gate": False,
                "reason": reason,
                "spend_policy": "no quota spend for an already-settled heartbeat turn",
            },
        }
    )
    frontier = payload.get("goal_frontier_projection")
    if isinstance(frontier, dict):
        payload["goal_frontier_projection"] = {
            key: value
            for key, value in frontier.items()
            if key
            not in {
                "autonomous_replan_decision",
                "replan_ack_feedback",
                "replan_obligation",
                "vision_continuation_audit",
                "vision_wait_state",
            }
        }
    clear_quota_action_projections(
        payload,
        additional_keys=(
            "boundary_projection_gap",
            "operator_question",
            "selected_todo",
            "state_projection_gap",
            "task_orchestration_contract",
            "todo_write_hint",
        ),
    )
