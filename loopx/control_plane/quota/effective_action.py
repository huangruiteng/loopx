"""Canonical value domain for the decision-slot effective action.

The Turn Envelope still carries a string for wire compatibility. This enum is
the owner of the finite value domain; callers may serialize ``.value`` while
the semantic drift smoke checks that new decision values are deliberate.
"""

from __future__ import annotations

from enum import Enum


class EffectiveAction(str, Enum):
    AGENT_MONITOR_ONLY = "agent_monitor_only"
    AGENT_WORKSPACE_REPAIR = "agent_workspace_repair"
    AUTOMATION_PROMPT_UPGRADE_REQUIRED = "automation_prompt_upgrade_required"
    AUTONOMOUS_REPLAN_REQUIRED = "autonomous_replan_required"
    BLOCK_REPLAY = "block_replay"
    BOUNDARY_PROJECTION_REPAIR = "boundary_projection_repair"
    CAPABILITY_BRIDGE_REPAIR = "capability_bridge_repair"
    CONTROL_PLANE_HEALTH_REPAIR = "control_plane_health_repair"
    CONTROL_PLANE_PROJECTION_REPAIR = "control_plane_projection_repair"
    COORDINATE_TASK_BUNDLE = "coordinate_task_bundle"
    EXTERNAL_EVIDENCE_OBSERVE = "external_evidence_observe"
    GOVERNED_CAPABILITY_INTENT = "governed_capability_intent"
    HEARTBEAT_RECEIPT_WRITE_FAILED = "heartbeat_receipt_write_failed"
    HEARTBEAT_SETTLED_SKIP = "heartbeat_settled_skip"
    LARK_INBOX_REPLY_DUE = "lark_inbox_reply_due"
    MONITOR_DUE = "monitor_due"
    MONITOR_QUIET_SKIP = "monitor_quiet_skip"
    NORMAL_RUN = "normal_run"
    OBSERVE_REPLAY = "observe_replay"
    OPERATOR_GATE = "operator_gate"
    OPERATOR_INBOX_MATERIAL_REVIEW_DUE = "operator_inbox_material_review_due"
    OUTCOME_FLOOR_RECOVERY = "outcome_floor_recovery"
    PEER_COORDINATION_BLOCKED = "peer_coordination_blocked"
    QUOTA_ACTION_SELECTION_DEFERRED = "quota_action_selection_deferred"
    QUOTA_ACTION_SELECTION_REJECTED = "quota_action_selection_rejected"
    QUOTA_SKIP = "quota_skip"
    RUNTIME_USER_GATE_PROJECTION_REPAIR = "runtime_user_gate_projection_repair"
    SCOPED_USER_GATE_FALLBACK = "scoped_user_gate_fallback"
    SKIP = "skip"
    STATE_PROJECTION_GAP_REPAIR = "state_projection_gap_repair"
    TERMINAL_NO_FOLLOWUP = "terminal_no_followup"
    TODO_DECISION_SCOPE_PROJECTION_REPAIR = "todo_decision_scope_projection_repair"
    UNSETTLED_HOST_TURN_RECOVERY = "unsettled_host_turn_recovery"


EFFECTIVE_ACTION_VALUES = tuple(item.value for item in EffectiveAction)
