from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any

from ..agents.agent_scope_frontier import (
    AgentScopeFrontierAction,
    agent_scope_frontier_action as _agent_scope_frontier_action,
)
from ..agents.capability_gate import runtime_capabilities_for_cli_projection
from ..goals.goal_frontier import AUTONOMOUS_REPLAN_REQUIRED_MODE
from ..goals.goal_vision_wait import exact_blocked_successor_wait_state
from ..scheduler.execution_context import (
    SchedulerExecutionContextResolution,
    render_scheduler_execution_args,
)
from ..todos.contract import (
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_ACTION,
)
from ..todos.projection import todo_item_task_class
from ..todos.user_gate import open_todo_count
from ..todos.write_hint import build_capability_resolution_writeback_actions
from .primary_action import (
    build_primary_action_projection,
    protocol_action_label as _protocol_action_label,
    protocol_action_text,
    protocol_first_candidate_action as _protocol_first_candidate_action,
    protocol_monitor_action as _protocol_monitor_action,
)

INTERACTION_CONTRACT_SCHEMA_VERSION = "loopx_interaction_contract_v0"
INTERACTION_RESPONSE_PLAN_SCHEMA_VERSION = "interaction_response_plan_v0"
PROTOCOL_ACTION_PACKET_SCHEMA_VERSION = "protocol_action_packet_v0"
PROTOCOL_ACTION_PACKET_LLM_POLICY = "no_api"


def _blocked_successor_wait_observation_required(payload: dict[str, Any]) -> bool:
    return bool(
        payload.get("effective_action")
        == AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value
        and exact_blocked_successor_wait_state(payload)
    )


def _user_todo_item_is_explicitly_non_gating(item: dict[str, Any]) -> bool:
    if item.get("gating") is False or item.get("non_gating") is True:
        return True
    if todo_item_task_class(item) in {
        TODO_TASK_CLASS_MONITOR,
        TODO_TASK_CLASS_USER_ACTION,
    }:
        return True
    action_kind = str(item.get("action_kind") or "").strip().lower()
    return action_kind in {
        "monitor",
        "observe",
        "watch",
        "fyi",
        "informational",
        "non_gating",
    }


def user_channel_action_todo_actions(summary: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(summary, dict):
        return []
    first_open_items = summary.get("first_open_items")
    if not isinstance(first_open_items, list):
        return []
    actions: list[str] = []
    for item in first_open_items:
        if not isinstance(item, dict):
            continue
        if _user_todo_item_is_explicitly_non_gating(item):
            continue
        text = _protocol_action_label(item.get("text"))
        if not text:
            continue
        actions.append(text)
        if len(actions) >= limit:
            break
    return actions


def user_channel_notice_todo_actions(summary: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(summary, dict):
        return []
    source_items = summary.get("user_action_items")
    if not isinstance(source_items, list):
        source_items = summary.get("first_open_items")
    if not isinstance(source_items, list):
        return []
    actions: list[str] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        if todo_item_task_class(item) != TODO_TASK_CLASS_USER_ACTION:
            continue
        text = _protocol_action_label(item.get("text"))
        if not text:
            continue
        actions.append(text)
        if len(actions) >= limit:
            break
    return actions


def user_channel_action_required(payload: dict[str, Any]) -> bool:
    if payload.get("agent_work_mode") == "monitor_only":
        return False
    if _user_gate_scope_projection_repair_active(payload):
        return False
    if _user_gate_notification_suppressed(payload):
        return False
    return bool(payload.get("requires_user_action")) or bool(
        user_channel_action_todo_actions(payload.get("user_todo_summary"))
    )


def _user_gate_notification_suppressed(payload: dict[str, Any]) -> bool:
    cooldown = payload.get("user_gate_notification_cooldown")
    return isinstance(cooldown, dict) and cooldown.get("notification_suppressed") is True


def _user_gate_scope_projection_repair_active(payload: dict[str, Any]) -> bool:
    repair = payload.get("stall_self_repair")
    return bool(
        isinstance(repair, dict)
        and repair.get("trigger") == "user_gate_scope_projection_drift"
    )


def _capability_resolution_user_actions(payload: dict[str, Any]) -> list[str]:
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    if not capability_gate.get("owner_missing"):
        return []
    owner_action = protocol_action_text(capability_gate.get("owner_action"))
    return [owner_action] if owner_action else []


def finalize_user_gate_notification_cooldown(
    payload: dict[str, Any],
    *,
    available_capabilities: Any = None,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ) = None,
) -> None:
    scheduler_hint = payload.get("scheduler_hint")
    cooldown = (
        scheduler_hint.get("user_gate_notification_cooldown")
        if isinstance(scheduler_hint, dict)
        else None
    )
    if isinstance(cooldown, dict):
        payload["user_gate_notification_cooldown"] = dict(cooldown)
    if _user_gate_notification_suppressed(payload):
        payload["pending_user_action"] = bool(
            payload.get("requires_user_action")
            or user_channel_action_todo_actions(payload.get("user_todo_summary"))
        )
        payload["requires_user_action"] = False
    payload["interaction_contract"] = build_interaction_contract(
        payload,
        available_capabilities=available_capabilities,
        scheduler_execution_context=scheduler_execution_context,
    )
    attach_user_action_compat_fields(payload)


def projected_user_channel_actions(
    payload: dict[str, Any],
    *,
    limit: int = 3,
) -> list[str]:
    if payload.get("agent_work_mode") == "monitor_only":
        return []
    if _user_gate_scope_projection_repair_active(payload):
        return []
    if _user_gate_notification_suppressed(payload):
        return []
    actions = user_channel_action_todo_actions(
        payload.get("user_todo_summary"),
        limit=limit,
    )
    if actions:
        return actions
    notices = user_channel_notice_todo_actions(
        payload.get("user_todo_summary"),
        limit=limit,
    )
    if notices:
        return notices
    capability_actions = _capability_resolution_user_actions(payload)
    if capability_actions:
        return capability_actions[:limit]
    if not user_channel_action_required(payload):
        return []
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    if capability_gate.get("owner_missing"):
        owner_action = protocol_action_text(capability_gate.get("owner_action"))
        if owner_action:
            return [owner_action]
    for key in ("gate_prompt", "operator_question", "open_todo_notify_reason"):
        text = protocol_action_text(payload.get(key))
        if text:
            return [text]
    return []


def attach_user_action_compat_fields(payload: dict[str, Any]) -> None:
    action_required = user_channel_action_required(payload)
    payload["requires_user_action"] = action_required
    payload["action_required"] = action_required
    if _user_gate_scope_projection_repair_active(payload):
        for key in ("notify_user_on_gate", "gate_prompt", "open_todo_notify_reason"):
            payload.pop(key, None)
    payload["open_count"] = open_todo_count(payload.get("user_todo_summary"))


def protocol_action_packet_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the ordered semantic fields rendered by protocol_action_packet_v0."""

    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    work_lane = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    automation_liveness = (
        payload.get("automation_liveness")
        if isinstance(payload.get("automation_liveness"), dict)
        else {}
    )
    scheduler_hint = (
        payload.get("scheduler_hint")
        if isinstance(payload.get("scheduler_hint"), dict)
        else {}
    )
    requires_user_action = user_channel_action_required(payload)
    blocked_successor_wait_observation = (
        _blocked_successor_wait_observation_required(payload)
    )
    must_attempt_work = bool(execution_obligation.get("must_attempt_work")) or (
        blocked_successor_wait_observation
    )
    scoped_user_gate_fallback = isinstance(payload.get("scoped_user_gate_fallback"), dict)
    bounded_delivery_with_user_notice = (
        requires_user_action
        and not scoped_user_gate_fallback
        and must_attempt_work
        and bool(
            execution_obligation.get(
                "delivery_allowed",
                payload.get("normal_delivery_allowed")
                or payload.get("recovery_delivery_allowed")
                or payload.get("self_repair_allowed")
                or payload.get("should_run"),
            )
        )
    )
    quiet_noop_allowed = (
        not requires_user_action
        and not must_attempt_work
        and not scoped_user_gate_fallback
    )

    user_actions = projected_user_channel_actions(payload)

    if requires_user_action and scoped_user_gate_fallback:
        primary_actor = "agent_with_user_gate"
        agent_action_required = True
        agent_action = _protocol_first_candidate_action(payload) or (
            "surface the scoped user gate, then advance one non-gated fallback"
        )
    elif bounded_delivery_with_user_notice:
        primary_actor = "agent_with_user_gate"
        agent_action_required = True
        agent_action = _protocol_first_candidate_action(payload) or "advance one bounded segment"
    elif requires_user_action:
        primary_actor = "user"
        agent_action_required = False
        capability_gate = (
            payload.get("capability_gate")
            if isinstance(payload.get("capability_gate"), dict)
            else {}
        )
        agent_action = (
            capability_gate.get("owner_action")
            if capability_gate.get("action") == "ask_owner"
            and capability_gate.get("owner_action")
            else "wait for user/owner action after surfacing the blocker or gate"
        )
    elif blocked_successor_wait_observation:
        primary_actor = "agent"
        agent_action_required = True
        agent_action = (
            "record one no-spend blocked-successor wait observation, then rerun quota"
        )
    elif must_attempt_work and payload.get("agent_work_mode") == "monitor_only":
        primary_actor = "agent"
        agent_action_required = True
        agent_action = (
            protocol_action_text(work_lane.get("action"), limit=220)
            or "attempt the due monitor and write back only a material transition"
        )
    elif must_attempt_work:
        primary_actor = "agent"
        agent_action_required = True
        if str(execution_obligation.get("kind") or "") == "outcome_floor_recovery":
            agent_action = (
                "produce the required outcome-floor evidence artifact or write "
                "the concrete blocker"
            )
        else:
            agent_action = _protocol_first_candidate_action(payload) or "advance one bounded segment"
    else:
        primary_actor = "agent"
        agent_action_required = False
        agent_action = _protocol_monitor_action(payload) or "quiet no-op; no material transition"

    action_key = (
        "agent_action"
        if agent_action_required
        else "user_action"
        if requires_user_action
        else "agent_action"
    )
    action_value = (
        agent_action
        if agent_action_required
        else user_actions[0]
        if requires_user_action and user_actions
        else agent_action
    )
    fields: dict[str, Any] = {
        "actor": primary_actor,
        "user_action_required": requires_user_action,
        "agent_action_required": agent_action_required,
        "quiet_noop_allowed": quiet_noop_allowed,
    }
    if work_lane.get("lane"):
        fields["lane"] = work_lane.get("lane")
    if automation_liveness.get("automation_action"):
        fields["automation"] = automation_liveness.get("automation_action")
    if scheduler_hint.get("action"):
        fields["scheduler"] = scheduler_hint.get("action")
    if automation_liveness.get("pause_allowed") is False:
        fields["pause_allowed"] = False
    fields["llm"] = PROTOCOL_ACTION_PACKET_LLM_POLICY
    if user_actions and (not requires_user_action or action_key != "user_action"):
        fields["user_action_pending"] = True
        text = protocol_action_text(user_actions[0], limit=80)
        if text:
            fields["user_action"] = text
    text = protocol_action_text(action_value, limit=80)
    if text:
        fields[action_key] = text
    return fields


def render_protocol_action_packet_summary(fields: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in fields.items():
        if isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return " ".join(parts)


def build_protocol_action_packet(payload: dict[str, Any]) -> dict[str, Any]:
    fields = protocol_action_packet_fields(payload)
    return {
        "schema_version": PROTOCOL_ACTION_PACKET_SCHEMA_VERSION,
        "summary": render_protocol_action_packet_summary(fields),
    }


def _interaction_mode(payload: dict[str, Any]) -> str:
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    kind = str(execution_obligation.get("kind") or "")
    effective_action = str(payload.get("effective_action") or "")
    state = str(payload.get("state") or "")
    if effective_action == "agent_monitor_only":
        return "agent_monitor_only"
    if effective_action == "monitor_due":
        return "monitor_due"
    if effective_action == "terminal_no_followup" or state == "terminal_no_followup":
        return "terminal_no_followup"
    if payload.get("scoped_user_gate_fallback"):
        return "scoped_user_gate_fallback"
    if _user_gate_notification_suppressed(payload):
        return "user_gate_cooldown_wait"
    if effective_action == "automation_prompt_upgrade_required":
        return "automation_prompt_upgrade"
    if user_channel_action_required(payload):
        if (
            bool(execution_obligation.get("must_attempt_work"))
            and bool(
                execution_obligation.get(
                    "delivery_allowed",
                    payload.get("normal_delivery_allowed")
                    or payload.get("recovery_delivery_allowed")
                    or payload.get("self_repair_allowed")
                    or payload.get("should_run"),
                )
            )
        ):
            return "bounded_delivery_with_user_notice"
        if payload.get("notify_user_on_gate") or state == "operator_gate":
            return "user_gate"
        if payload.get("notify_user_on_open_todo"):
            return "user_todo_blocker_push"
        return "user_action_required"
    if kind == "external_evidence_observation_required":
        return "external_evidence_observation"
    if kind == AUTONOMOUS_REPLAN_REQUIRED_MODE:
        return "autonomous_replan"
    if effective_action == "coordinate_task_bundle":
        return "task_orchestration"
    agent_scope_action = _agent_scope_frontier_action(effective_action)
    if agent_scope_action is not None:
        return agent_scope_action.value
    if effective_action == "monitor_quiet_skip":
        return "monitor_quiet_skip"
    if payload.get("recovery_delivery_allowed") or effective_action == "outcome_floor_recovery":
        return "outcome_floor_recovery"
    if effective_action == "capability_bridge_repair":
        return "capability_bridge_repair"
    if effective_action == "agent_workspace_repair":
        return effective_action
    if effective_action == "boundary_projection_repair":
        return "boundary_projection_repair"
    if payload.get("self_repair_allowed"):
        return "control_plane_self_repair"
    if heartbeat_recommendation.get("stop_if_unchanged"):
        return "mapped_noop_if_unchanged"
    if payload.get("normal_delivery_allowed") or payload.get("should_run"):
        return "bounded_delivery"
    if state == "blocked_health":
        return "health_blocked"
    if state == "throttled":
        return "quota_throttled"
    if state in {"waiting", "focus_wait"}:
        return "blocked_wait"
    return "skip"


def _scoped_cli_args(
    agent_identity: dict[str, Any],
    *,
    available_capabilities: Any,
) -> str:
    agent_id = str(agent_identity.get("agent_id") or "").strip()
    if not agent_id:
        return ""
    capability_args = "".join(
        f" --available-capability {shlex.quote(capability)}"
        for capability in runtime_capabilities_for_cli_projection(
            available_capabilities
        )
    )
    return f" --agent-id {agent_id}{capability_args}"


def interaction_next_cli_actions(
    payload: dict[str, Any],
    *,
    mode: str,
    available_capabilities: Any = None,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ) = None,
) -> list[str]:
    goal_id = str(payload.get("goal_id") or "<GOAL_ID>")
    agent_identity = (
        payload.get("agent_identity")
        if isinstance(payload.get("agent_identity"), dict)
        else {}
    )
    scoped_cli_args = _scoped_cli_args(
        agent_identity,
        available_capabilities=available_capabilities,
    )
    lifecycle_actor_args = (
        f" --agent-id {shlex.quote(str(agent_identity.get('agent_id')).strip())}"
        if agent_identity.get("agent_id")
        else ""
    )
    try:
        scheduler_args = render_scheduler_execution_args(
            scheduler_execution_context=scheduler_execution_context,
        )
    except ValueError:
        scheduler_args = ""
    typed_quota_guard = (
        f"loopx --format json quota should-run --goal-id {goal_id}"
        f"{scoped_cli_args}{scheduler_args}"
        if scheduler_args
        else "rerun the typed quota_guard from the current host packet"
    )
    typed_monitor_poll = (
        f"loopx quota monitor-poll --goal-id {goal_id}{scoped_cli_args}"
        f"{scheduler_args} --execute"
        if scheduler_args
        else "use the current host packet's typed monitor command"
    )
    capability_resolution_actions = build_capability_resolution_writeback_actions(
        payload.get("capability_gate"),
        goal_id=goal_id,
        agent_id=(
            str(agent_identity.get("agent_id"))
            if agent_identity.get("agent_id")
            else None
        ),
    )
    if mode == "terminal_no_followup":
        return ["no quota spend until explicit goal resume or newly projected work"]
    if mode == "agent_monitor_only":
        return [
            "no quota spend until a due monitor, verified direct reply, or explicit work-mode change"
        ]
    if mode == "automation_prompt_upgrade":
        automation_prompt_upgrade = (
            payload.get("automation_prompt_upgrade")
            if isinstance(payload.get("automation_prompt_upgrade"), dict)
            else {}
        )
        actions = [
            str(item.get("command") or "").strip()
            for item in automation_prompt_upgrade.get("agent_example_commands") or []
            if isinstance(item, dict)
        ]
        completion_command = str(
            automation_prompt_upgrade.get("completion_command") or ""
        ).strip()
        if completion_command:
            actions.append(completion_command)
        return [action for action in actions if action] or [
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} --agent-id <registered-agent> --agent-scope '<scope>'",
        ]
    if mode == "monitor_quiet_skip":
        return [
            typed_monitor_poll,
            typed_quota_guard,
        ]
    if mode == "monitor_due":
        return [
            typed_monitor_poll,
            typed_quota_guard,
        ]
    if mode == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        agent_scope_frontier = (
            payload.get("agent_scope_frontier")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else {}
        )
        monitor_candidates = (
            agent_scope_frontier.get("monitor_blocked_resume_candidates")
            if isinstance(agent_scope_frontier.get("monitor_blocked_resume_candidates"), list)
            else []
        )
        if monitor_candidates:
            first_candidate = (
                monitor_candidates[0]
                if isinstance(monitor_candidates[0], dict)
                else {}
            )
            monitor_todo_id = str(
                first_candidate.get("blocking_monitor_todo_id") or "<monitor_todo_id>"
            )
            gated_todo_id = str(first_candidate.get("todo_id") or "<gated_todo_id>")
            return [
                f"loopx todo complete --goal-id {goal_id} --todo-id {monitor_todo_id}{lifecycle_actor_args} --evidence '<validated gate evidence>'",
                f"loopx todo update --goal-id {goal_id} --todo-id {gated_todo_id}{lifecycle_actor_args} --note '<public-safe gate repair reason>'",
                f"loopx refresh-state --goal-id {goal_id} --classification standing_monitor_gate_repair_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress{scoped_cli_args}",
                f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{scoped_cli_args}",
            ]
        route_candidates = (
            agent_scope_frontier.get("route_continuation_replan_candidates")
            if isinstance(agent_scope_frontier.get("route_continuation_replan_candidates"), list)
            else []
        )
        if route_candidates:
            return [
                f"loopx todo add --goal-id {goal_id} --role agent --text '<public-safe route continuation advancement todo>'",
                f"loopx refresh-state --goal-id {goal_id} --classification route_continuation_replan_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress{scoped_cli_args}",
                f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{scoped_cli_args}",
            ]
        candidates = (
            agent_scope_frontier.get("deferred_resume_candidates")
            if isinstance(agent_scope_frontier.get("deferred_resume_candidates"), list)
            else []
        )
        first_candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        todo_id = str(first_candidate.get("todo_id") or "<todo_id>")
        return [
            (
                f"loopx todo update --goal-id {goal_id} --todo-id {todo_id}"
                f"{lifecycle_actor_args} --status open --clear-resume-when "
                "--note '<public-safe successor replan reason>'"
            ),
            f"loopx refresh-state --goal-id {goal_id} --classification successor_replan_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress{scoped_cli_args}",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{scoped_cli_args}",
        ]
    if (
        mode == AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value
        and _blocked_successor_wait_observation_required(payload)
    ):
        return [
            typed_monitor_poll,
            typed_quota_guard,
        ]
    if _agent_scope_frontier_action(mode) is not None:
        return [
            "no quota spend while this agent has no in-scope runnable candidate",
            typed_quota_guard,
        ]
    if mode == "external_evidence_observation":
        return [
            "read approved controller/job/marker/writeback surfaces only",
            f"loopx refresh-state --goal-id {goal_id} --classification <compact_blocker_or_transition>{scoped_cli_args}",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{scoped_cli_args}",
        ]
    if mode == "agent_workspace_repair":
        return [
            "create or switch to an independent git worktree/branch",
            typed_quota_guard,
        ]
    if mode == "autonomous_replan":
        replan_obligation = (
            payload.get("autonomous_replan_obligation")
            if isinstance(payload.get("autonomous_replan_obligation"), dict)
            else {}
        )
        agent_todo_writeback_required = (
            replan_obligation.get("agent_todo_writeback_required") is True
        )
        lane_action = _protocol_first_candidate_action(payload)
        first_action = (
            "run one bounded autonomous replan slice around "
            f"{lane_action}; write back the selected todo/frontier changes"
            if lane_action
            else "run one bounded autonomous replan slice and write back the selected next action/todo changes"
        )
        actions = [
            first_action,
        ]
        if agent_todo_writeback_required:
            actor_id = str(agent_identity.get("agent_id") or "").strip()
            actor_args = (
                f" --agent-id {shlex.quote(actor_id)} --claimed-by {shlex.quote(actor_id)}"
                if actor_id
                else " --agent-id <agent-id> --claimed-by <agent-id>"
            )
            actions.append(
                f"loopx todo add --goal-id {goal_id} --role agent "
                "--task-class advancement_task --text '<selected runnable next slice>'"
                f"{actor_args}"
            )
        delta_kind = (
            "runnable_todo_set" if agent_todo_writeback_required else "<delta_kind>"
        )
        actions.extend([
            f"loopx refresh-state --goal-id {goal_id} --classification autonomous_replan_recorded --autonomous-replan-recorded --repair-delta-kind {delta_kind} --delivery-batch-scale <scale> --delivery-outcome <outcome>{scoped_cli_args}",
            (
                "if the replan writeback records an accountable delta such as "
                "outcome_progress or primary_goal_outcome, run "
                f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{scoped_cli_args}; "
                "otherwise do not spend for surface_only watch-lane continuation/no-followup"
            ),
        ])
        return actions
    if mode in {
        "bounded_delivery",
        "outcome_floor_recovery",
        "capability_bridge_repair",
        "control_plane_self_repair",
        "boundary_projection_repair",
        "scoped_user_gate_fallback",
        "bounded_delivery_with_user_notice",
    }:
        return [
            *capability_resolution_actions,
            f"loopx refresh-state --goal-id {goal_id} --classification <validated_progress>{scoped_cli_args}",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{scoped_cli_args}",
        ]
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return [
            *capability_resolution_actions,
            "no quota spend for blocker-push/gate-notification",
        ]
    return ["no quota spend without validated transition/blocker writeback"]


def _interaction_required_reads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    reads = payload.get("required_reads")
    if not isinstance(reads, list):
        return []
    result: list[dict[str, Any]] = []
    for item in reads:
        if not isinstance(item, dict):
            continue
        command = protocol_action_text(item.get("command"), limit=360)
        if not command:
            continue
        result.append({**item, "command": command})
    return result


def _interaction_spend_policy(
    execution_obligation: dict[str, Any],
    heartbeat_recommendation: dict[str, Any],
    *,
    mode: str,
    spend_after_validation: bool,
) -> str | None:
    if mode == "terminal_no_followup":
        return "no spend for terminal automation shutdown"
    if mode == "agent_monitor_only":
        return "no spend while advancement is paused and no monitor is due"
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return "no spend for gate or blocker push"
    if mode == "monitor_quiet_skip":
        return "no spend for unchanged monitor poll"
    if mode == "monitor_due":
        return (
            "spend once only after a validated material monitor transition; "
            "unchanged monitor polls are no-spend"
        )
    if mode == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        return "spend once after validated successor replan/todo writeback"
    if _agent_scope_frontier_action(mode) is not None:
        return "no spend while the current agent has no in-scope runnable candidate"
    if mode == "agent_workspace_repair":
        return "no spend for moving agent work into an independent worktree"
    if mode == "automation_prompt_upgrade":
        return "no spend until the host update is acknowledged and quota reruns"
    if mode == "autonomous_replan":
        return (
            "spend only after accountable replan delta; no spend for "
            "surface_only watch-lane continuation"
        )
    if spend_after_validation:
        return "spend once after validated writeback"
    raw_policy = execution_obligation.get("spend_policy") or heartbeat_recommendation.get(
        "spend_policy"
    )
    if isinstance(raw_policy, str) and len(raw_policy) <= 80:
        return raw_policy
    return "no spend without validated transition"


def _blocked_priority_fallback_user_reason(payload: dict[str, Any]) -> str | None:
    fallback = (
        payload.get("blocked_priority_fallback")
        if isinstance(payload.get("blocked_priority_fallback"), dict)
        else {}
    )
    if not fallback:
        return None
    if (
        fallback.get("requires_user_action") is not True
        and fallback.get("notify_user") is not True
    ):
        return None
    reason = str(fallback.get("reason") or "").strip()
    return reason or None


def _interaction_must_attempt(
    execution_obligation: dict[str, Any],
    *,
    user_required: bool,
    scoped_user_gate_fallback: bool,
    bounded_delivery_with_user_notice: bool,
) -> bool:
    if user_required and not (
        scoped_user_gate_fallback or bounded_delivery_with_user_notice
    ):
        return False
    return bool(execution_obligation.get("must_attempt_work"))


def _interaction_delivery_allowed(
    payload: dict[str, Any],
    execution_obligation: dict[str, Any],
    *,
    mode: str,
    user_required: bool,
    scoped_user_gate_fallback: bool,
    bounded_delivery_with_user_notice: bool,
) -> bool:
    if mode == "mapped_noop_if_unchanged":
        return False
    if user_required and not (
        scoped_user_gate_fallback or bounded_delivery_with_user_notice
    ):
        return False
    return bool(
        execution_obligation.get(
            "delivery_allowed",
            payload.get("normal_delivery_allowed")
            or payload.get("recovery_delivery_allowed")
            or payload.get("self_repair_allowed")
            or payload.get("should_run"),
        )
    )


def _interaction_quiet_noop_allowed(
    *,
    mode: str,
    user_required: bool,
    must_attempt: bool,
) -> bool:
    if user_required or must_attempt:
        return False
    return _agent_scope_frontier_action(mode) is not None or mode in {
        "monitor_quiet_skip",
        "mapped_noop_if_unchanged",
        "quota_throttled",
        "blocked_wait",
        "user_gate_cooldown_wait",
        "terminal_no_followup",
        "agent_monitor_only",
        "skip",
    }


def _interaction_spend_after_validation(mode: str) -> bool:
    return mode in {
        "bounded_delivery",
        "outcome_floor_recovery",
        "capability_bridge_repair",
        "autonomous_replan",
        "control_plane_self_repair",
        "boundary_projection_repair",
        "external_evidence_observation",
        "monitor_due",
        "task_orchestration",
        AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
        "scoped_user_gate_fallback",
        "bounded_delivery_with_user_notice",
    }


def _interaction_user_reason(payload: dict[str, Any]) -> Any:
    return (
        (
            payload.get("user_gate_notification_cooldown", {}).get("reason")
            if _user_gate_notification_suppressed(payload)
            else None
        )
        or payload.get("open_todo_notify_reason")
        or payload.get("gate_prompt")
        or payload.get("operator_question")
        or _blocked_priority_fallback_user_reason(payload)
        or (
            payload.get("scoped_user_gate_fallback", {}).get("reason")
            if isinstance(payload.get("scoped_user_gate_fallback"), dict)
            else None
        )
        or (
            "open user todo requires user-visible follow-up while independent "
            "agent work may continue"
            if user_channel_action_todo_actions(payload.get("user_todo_summary"))
            else None
        )
        or (
            "open non-blocking user action should be surfaced while independent "
            "agent work continues"
            if user_channel_notice_todo_actions(payload.get("user_todo_summary"))
            else None
        )
        or (
            payload.get("agent_scope_frontier", {}).get("reason")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else None
        )
        or (
            payload.get("capability_gate", {}).get("reason")
            if isinstance(payload.get("capability_gate"), dict)
            else None
        )
    )


def _build_interaction_agent_channel(
    payload: dict[str, Any],
    *,
    mode: str,
    must_attempt: bool,
    delivery_allowed: bool,
    quiet_noop_allowed: bool,
) -> dict[str, Any]:
    channel: dict[str, Any] = {
        "must_attempt": must_attempt,
        "delivery_allowed": delivery_allowed,
        "quiet_noop_allowed": quiet_noop_allowed,
    }
    channel.update(build_primary_action_projection(payload, mode=mode))
    if _blocked_successor_wait_observation_required(payload):
        channel["primary_action"] = (
            "record one no-spend blocked-successor wait observation, rerun quota, "
            "then replan after the second unchanged frontier"
        )
    return channel


def _build_interaction_user_channel(
    payload: dict[str, Any],
    heartbeat_recommendation: dict[str, Any],
    *,
    user_required: bool,
) -> dict[str, Any]:
    actions = projected_user_channel_actions(payload, limit=3)
    non_blocking_notice = bool(
        not user_required
        and user_channel_notice_todo_actions(payload.get("user_todo_summary"), limit=3)
    )
    channel: dict[str, Any] = {
        "action_required": user_required,
        "notify": "NOTIFY"
        if user_required or non_blocking_notice
        else "DONT_NOTIFY"
        if _user_gate_notification_suppressed(payload)
        else heartbeat_recommendation.get("notify", "DONT_NOTIFY"),
    }
    if actions:
        channel["max_items"] = 3
        channel["actions"] = actions
    if non_blocking_notice:
        channel["non_blocking"] = True
    reason = _interaction_user_reason(payload)
    if reason:
        channel["reason"] = reason
    return channel


def _build_interaction_response_plan(
    *,
    user_channel: dict[str, Any],
    agent_channel: dict[str, Any],
) -> dict[str, Any] | None:
    """Project the exact host-visible response for a blocking user gate."""

    if not (
        user_channel.get("action_required") is True
        and user_channel.get("notify") == "NOTIFY"
        and agent_channel.get("must_attempt") is False
        and agent_channel.get("delivery_allowed") is False
        and agent_channel.get("quiet_noop_allowed") is False
    ):
        return None
    return {
        "schema_version": INTERACTION_RESPONSE_PLAN_SCHEMA_VERSION,
        "kind": "surface_user_gate",
        "decision": "ask_user",
        "action_sequence": ["notify", "wait"],
        "silent_wait_allowed": False,
    }


def _build_interaction_cli_channel(
    payload: dict[str, Any],
    execution_obligation: dict[str, Any],
    heartbeat_recommendation: dict[str, Any],
    *,
    mode: str,
    spend_after_validation: bool,
    available_capabilities: Any = None,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ) = None,
) -> dict[str, Any]:
    return {
        "next_cli_actions": interaction_next_cli_actions(
            payload,
            mode=mode,
            available_capabilities=available_capabilities,
            scheduler_execution_context=scheduler_execution_context,
        ),
        "spend_allowed_now": False,
        "spend_after_validation": spend_after_validation,
        "spend_policy": _interaction_spend_policy(
            execution_obligation,
            heartbeat_recommendation,
            mode=mode,
            spend_after_validation=spend_after_validation,
        ),
    }


def _attach_interaction_required_reads(
    contract: dict[str, Any],
    required_reads: list[dict[str, Any]],
) -> None:
    if not required_reads:
        return
    contract["agent_channel"]["required_reads"] = required_reads
    contract["cli_channel"]["required_reads"] = required_reads


def _attach_interaction_post_writeback_actions(
    contract: dict[str, Any], payload: dict[str, Any]
) -> None:
    goal_boundary = (
        payload.get("goal_boundary")
        if isinstance(payload.get("goal_boundary"), Mapping)
        else {}
    )
    actions = goal_boundary.get("post_writeback_actions")
    if isinstance(actions, list) and actions:
        contract["cli_channel"]["post_writeback_actions"] = actions


def _attach_interaction_vision_continuation_audit(
    contract: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    vision_continuation_audit = (
        payload.get("vision_continuation_audit")
        if isinstance(payload.get("vision_continuation_audit"), dict)
        else {}
    )
    if not vision_continuation_audit.get("required"):
        return
    contract["agent_channel"]["vision_continuation_audit"] = vision_continuation_audit
    vision_gap_judge = (
        vision_continuation_audit.get("vision_gap_judge")
        if isinstance(vision_continuation_audit.get("vision_gap_judge"), dict)
        else {}
    )
    contract["cli_channel"]["vision_continuation_audit"] = {
        "required": True,
        "required_before_closeout": vision_continuation_audit.get(
            "required_before_closeout"
        )
        or [],
        "recommended_action": vision_continuation_audit.get("recommended_action"),
    }
    if vision_gap_judge:
        contract["cli_channel"]["vision_continuation_audit"]["vision_gap_judge"] = {
            "done": vision_gap_judge.get("done"),
            "decision": vision_gap_judge.get("decision"),
            "reason": vision_gap_judge.get("reason"),
            "agent_judge_instruction": vision_gap_judge.get("agent_judge_instruction"),
            "evidence_read_instruction": vision_gap_judge.get(
                "evidence_read_instruction"
            ),
            "done_only_when": vision_gap_judge.get("done_only_when") or [],
            "continue_when": vision_gap_judge.get("continue_when") or [],
            "otherwise": vision_gap_judge.get("otherwise"),
        }


def _attach_interaction_vision_wait_state(
    contract: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    vision_wait_state = (
        payload.get("vision_wait_state")
        if isinstance(payload.get("vision_wait_state"), dict)
        else {}
    )
    if vision_wait_state.get("state") != "waiting":
        return
    contract["agent_channel"]["vision_wait_state"] = vision_wait_state
    contract["cli_channel"]["vision_wait_state"] = {
        "state": "waiting",
        "reason_code": vision_wait_state.get("reason_code"),
        "selected_todo_id": vision_wait_state.get("selected_todo_id"),
        "resume_when": vision_wait_state.get("resume_when"),
        "automatic_resume": vision_wait_state.get("automatic_resume") is True,
        "spend_policy": "no spend while the exact resume condition is pending",
    }


def _interaction_fallback_policy_required(payload: dict[str, Any], *, mode: str) -> bool:
    return mode in {
        "user_gate",
        "user_todo_blocker_push",
        "user_action_required",
        "outcome_floor_recovery",
        "external_evidence_observation",
        "scoped_user_gate_fallback",
    } or bool(payload.get("blocked_priority_fallback"))


def build_interaction_contract(
    payload: dict[str, Any],
    *,
    available_capabilities: Any = None,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ) = None,
) -> dict[str, Any]:
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    mode = _interaction_mode(payload)
    monitor_only = payload.get("agent_work_mode") == "monitor_only"
    user_required = False if monitor_only else user_channel_action_required(payload)
    scoped_user_gate_fallback = mode == "scoped_user_gate_fallback"
    bounded_delivery_with_user_notice = mode == "bounded_delivery_with_user_notice"
    must_attempt = _interaction_must_attempt(
        execution_obligation,
        user_required=user_required,
        scoped_user_gate_fallback=scoped_user_gate_fallback,
        bounded_delivery_with_user_notice=bounded_delivery_with_user_notice,
    )
    if mode == "automation_prompt_upgrade":
        must_attempt = True
    if _blocked_successor_wait_observation_required(payload):
        must_attempt = True
    delivery_allowed = _interaction_delivery_allowed(
        payload,
        execution_obligation,
        mode=mode,
        user_required=user_required,
        scoped_user_gate_fallback=scoped_user_gate_fallback,
        bounded_delivery_with_user_notice=bounded_delivery_with_user_notice,
    )
    quiet_noop_allowed = _interaction_quiet_noop_allowed(
        mode=mode,
        user_required=user_required,
        must_attempt=must_attempt,
    )
    spend_after_validation = _interaction_spend_after_validation(mode)
    required_reads = _interaction_required_reads(payload)

    user_channel = _build_interaction_user_channel(
        payload,
        heartbeat_recommendation,
        user_required=user_required,
    )
    if monitor_only:
        user_channel = {
            "action_required": False,
            "notify": "DONT_NOTIFY",
            "reason": payload.get("reason"),
        }
    agent_channel = _build_interaction_agent_channel(
        payload,
        mode=mode,
        must_attempt=must_attempt,
        delivery_allowed=delivery_allowed,
        quiet_noop_allowed=quiet_noop_allowed,
    )
    contract = {
        "schema_version": INTERACTION_CONTRACT_SCHEMA_VERSION,
        "mode": mode,
        "user_channel": user_channel,
        "agent_channel": agent_channel,
        "cli_channel": _build_interaction_cli_channel(
            payload,
            execution_obligation,
            heartbeat_recommendation,
            mode=mode,
            spend_after_validation=spend_after_validation,
            available_capabilities=available_capabilities,
            scheduler_execution_context=scheduler_execution_context,
        ),
    }
    response_plan = _build_interaction_response_plan(
        user_channel=user_channel,
        agent_channel=agent_channel,
    )
    if response_plan is not None:
        contract["response_plan"] = response_plan
    _attach_interaction_required_reads(contract, required_reads)
    _attach_interaction_post_writeback_actions(contract, payload)
    _attach_interaction_vision_continuation_audit(contract, payload)
    _attach_interaction_vision_wait_state(contract, payload)
    if _interaction_fallback_policy_required(payload, mode=mode):
        contract["fallback_policy"] = {"do_not_cancel_on_block": True}
    return contract
