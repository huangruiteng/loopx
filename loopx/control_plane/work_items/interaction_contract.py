from __future__ import annotations

from typing import Any

from ..agents.agent_scope import AgentScopeFrontierAction
from ..goals.goal_frontier import AUTONOMOUS_REPLAN_REQUIRED_MODE
from ..todos.contract import TODO_TASK_CLASS_ADVANCEMENT, TODO_TASK_CLASS_MONITOR
from ..todos.projection import todo_item_is_actionable_open, todo_item_task_class


INTERACTION_CONTRACT_SCHEMA_VERSION = "loopx_interaction_contract_v0"
PROTOCOL_ACTION_PACKET_SCHEMA_VERSION = "protocol_action_packet_v0"


def protocol_action_text(value: Any, *, limit: int = 220) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _protocol_action_label(value: Any, *, limit: int = 80) -> str | None:
    text = protocol_action_text(value)
    if not text:
        return None
    head, separator, _tail = text.partition(":")
    if separator and "[" in head and "]" in head and 8 <= len(head) <= limit:
        return head.strip()
    return protocol_action_text(text, limit=limit)


def _protocol_todo_actions(summary: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(summary, dict):
        return []
    first_open_items = summary.get("first_open_items")
    if not isinstance(first_open_items, list):
        return []
    actions: list[str] = []
    for item in first_open_items:
        if not isinstance(item, dict):
            continue
        text = _protocol_action_label(item.get("text"))
        if not text:
            continue
        actions.append(text)
        if len(actions) >= limit:
            break
    return actions


def _user_todo_item_is_explicitly_non_gating(item: dict[str, Any]) -> bool:
    if item.get("gating") is False or item.get("non_gating") is True:
        return True
    if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR:
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


def user_channel_action_required(payload: dict[str, Any]) -> bool:
    return bool(payload.get("requires_user_action")) or bool(
        user_channel_action_todo_actions(payload.get("user_todo_summary"))
    )


def _agent_scope_frontier_action(value: Any) -> AgentScopeFrontierAction | None:
    try:
        return AgentScopeFrontierAction(str(value or ""))
    except ValueError:
        return None


def _protocol_first_candidate_action(payload: dict[str, Any]) -> str | None:
    goal_id = str(payload.get("goal_id") or "")
    agent_lane_next_action = (
        payload.get("agent_lane_next_action")
        if isinstance(payload.get("agent_lane_next_action"), dict)
        else {}
    )
    lane_text = _protocol_action_label(agent_lane_next_action.get("text"))
    if lane_text:
        todo_id = str(agent_lane_next_action.get("todo_id") or "").strip()
        return f"{todo_id}: {lane_text}" if todo_id else lane_text
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    if capability_gate.get("action") == "run":
        runnable_candidates = (
            capability_gate.get("runnable_candidates")
            if isinstance(capability_gate.get("runnable_candidates"), list)
            else []
        )
        if runnable_candidates:
            return (
                f"choose one of {len(runnable_candidates)} "
                "capability-runnable todo(s) after steering audit"
            )
    scoped_fallback = (
        payload.get("scoped_user_gate_fallback")
        if isinstance(payload.get("scoped_user_gate_fallback"), dict)
        else {}
    )
    selected = (
        scoped_fallback.get("selected_executable")
        if isinstance(scoped_fallback.get("selected_executable"), dict)
        else {}
    )
    text = _protocol_action_label(selected.get("text"))
    if text:
        return text

    work_lane = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    if work_lane.get("monitor_kind") == "todo_monitor_due":
        due_items = (
            work_lane.get("monitor_due_items")
            if isinstance(work_lane.get("monitor_due_items"), list)
            else []
        )
        for item in due_items:
            if not isinstance(item, dict):
                continue
            text = _protocol_action_label(item.get("text"))
            if text:
                todo_id = str(item.get("todo_id") or "").strip()
                return f"{todo_id}: {text}" if todo_id else text

    agent_todos = (
        payload.get("agent_todo_summary")
        if isinstance(payload.get("agent_todo_summary"), dict)
        else {}
    )
    for key in ("first_executable_items", "first_open_items"):
        items = agent_todos.get(key) if isinstance(agent_todos.get(key), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not todo_item_is_actionable_open(item):
                continue
            if todo_item_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
                continue
            text = _protocol_action_label(item.get("text"))
            if text:
                return text

    backlog = (
        payload.get("autonomous_backlog_candidates")
        if isinstance(payload.get("autonomous_backlog_candidates"), dict)
        else {}
    )
    items = backlog.get("items") if isinstance(backlog.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if goal_id and str(item.get("goal_id") or "") != goal_id:
            continue
        text = _protocol_action_label(item.get("text"))
        if text:
            return text

    reason_codes = (
        work_lane.get("reason_codes")
        if isinstance(work_lane.get("reason_codes"), list)
        else []
    )
    if "next_action_requires_advancement" in reason_codes:
        text = protocol_action_text(payload.get("recommended_action"))
        if text:
            return text
    for key in ("action", "obligation"):
        text = protocol_action_text(work_lane.get(key))
        if text:
            return text
    return protocol_action_text(payload.get("recommended_action"))


def _protocol_monitor_action(payload: dict[str, Any]) -> str | None:
    goal_id = str(payload.get("goal_id") or "")
    work_lane = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    if work_lane.get("obligation") == "quiet_until_material_monitor_transition":
        return "quiet until a material monitor transition, regression, or concrete blocker appears"
    monitors = (
        payload.get("autonomous_monitor_candidates")
        if isinstance(payload.get("autonomous_monitor_candidates"), dict)
        else {}
    )
    items = monitors.get("items") if isinstance(monitors.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if goal_id and str(item.get("goal_id") or "") != goal_id:
            continue
        text = _protocol_action_label(item.get("text"), limit=160)
        if text:
            return text
    return None


def build_protocol_action_packet(payload: dict[str, Any]) -> dict[str, Any]:
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
    must_attempt_work = bool(execution_obligation.get("must_attempt_work"))
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

    user_actions = _protocol_todo_actions(payload.get("user_todo_summary"))
    if requires_user_action and not user_actions:
        capability_gate = (
            payload.get("capability_gate")
            if isinstance(payload.get("capability_gate"), dict)
            else {}
        )
        if capability_gate.get("action") == "ask_owner":
            owner_action = protocol_action_text(capability_gate.get("owner_action"))
            if owner_action:
                user_actions = [owner_action]
        for key in ("gate_prompt", "operator_question", "open_todo_notify_reason"):
            if user_actions:
                break
            text = protocol_action_text(payload.get(key))
            if text:
                user_actions = [text]
                break

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
    summary_parts = [
        f"actor={primary_actor}",
        f"user_action_required={str(requires_user_action).lower()}",
        f"agent_action_required={str(agent_action_required).lower()}",
        f"quiet_noop_allowed={str(quiet_noop_allowed).lower()}",
    ]
    if work_lane.get("lane"):
        summary_parts.append(f"lane={work_lane.get('lane')}")
    if automation_liveness.get("automation_action"):
        summary_parts.append(f"automation={automation_liveness.get('automation_action')}")
    if scheduler_hint.get("action"):
        summary_parts.append(f"scheduler={scheduler_hint.get('action')}")
    if automation_liveness.get("pause_allowed") is False:
        summary_parts.append("pause_allowed=false")
    summary_parts.append("llm=no_api")
    if user_actions and (not requires_user_action or action_key != "user_action"):
        summary_parts.append("user_action_pending=true")
        text = protocol_action_text(user_actions[0], limit=80)
        if text:
            summary_parts.append(f"user_action={text}")
    text = protocol_action_text(action_value, limit=80)
    if text:
        summary_parts.append(f"{action_key}={text}")
    return {
        "schema_version": PROTOCOL_ACTION_PACKET_SCHEMA_VERSION,
        "summary": " ".join(summary_parts),
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
    if payload.get("scoped_user_gate_fallback"):
        return "scoped_user_gate_fallback"
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
    agent_scope_action = _agent_scope_frontier_action(effective_action)
    if agent_scope_action is not None:
        return agent_scope_action.value
    if effective_action == "monitor_quiet_skip":
        return "monitor_quiet_skip"
    if payload.get("recovery_delivery_allowed") or effective_action == "outcome_floor_recovery":
        return "outcome_floor_recovery"
    if effective_action == "capability_bridge_repair":
        return "capability_bridge_repair"
    if effective_action == "side_agent_workspace_repair":
        return "side_agent_workspace_repair"
    if effective_action == "boundary_projection_repair":
        return "boundary_projection_repair"
    if payload.get("self_repair_allowed"):
        return "control_plane_self_repair"
    if payload.get("normal_delivery_allowed") or payload.get("should_run"):
        return "bounded_delivery"
    if heartbeat_recommendation.get("stop_if_unchanged"):
        return "mapped_noop_if_unchanged"
    if state == "blocked_health":
        return "health_blocked"
    if state == "throttled":
        return "quota_throttled"
    if state in {"waiting", "focus_wait"}:
        return "blocked_wait"
    return "skip"


def _interaction_primary_agent_action(payload: dict[str, Any], *, mode: str) -> str:
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    if mode == "external_evidence_observation":
        external_observation = (
            payload.get("external_evidence_observation")
            if isinstance(payload.get("external_evidence_observation"), dict)
            else {}
        )
        observation_target = protocol_action_text(
            external_observation.get("observation_target"),
            limit=220,
        )
        if observation_target:
            return observation_target
        return (
            "verify an observable external handle or compact writeback channel; "
            "write a compact blocker when it is absent"
        )
    if mode == "autonomous_replan":
        lane_action = _protocol_first_candidate_action(payload)
        if lane_action:
            return f"run one bounded autonomous replan slice around {lane_action}"
        return "run one bounded self-repair or replan segment before another quiet no-op"
    if mode == "monitor_quiet_skip":
        return "record at most one no-spend monitor-poll event, rerun the guard, then stay quiet if unchanged"
    if _agent_scope_frontier_action(mode) is not None:
        agent_scope_frontier = (
            payload.get("agent_scope_frontier")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else {}
        )
        action = protocol_action_text(agent_scope_frontier.get("recommended_action"), limit=260)
        return action or "stay quiet until this agent has a concrete in-scope runnable todo"
    if mode == "scoped_user_gate_fallback":
        return _protocol_first_candidate_action(payload) or (
            "surface the scoped user gate, then advance one non-gated fallback"
        )
    if mode == "bounded_delivery_with_user_notice":
        return _protocol_first_candidate_action(payload) or "advance one bounded validated segment"
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return "wait for user/owner action after surfacing the blocker or gate"
    if mode == "outcome_floor_recovery":
        return "produce the required outcome-floor evidence artifact or write the concrete blocker"
    if mode == "capability_bridge_repair":
        return "repair or materialize the missing bridge capability, rewrite the todo, or write a compact blocker"
    if mode == "side_agent_workspace_repair":
        return "create or switch to an independent worktree/branch, then rerun quota guard before file edits"
    if mode == "automation_prompt_upgrade":
        return "regenerate the installed automation prompt with a registered agent id and scope, then rerun quota guard"
    if mode == "control_plane_self_repair":
        return "repair the bounded control-plane/status projection fault exposed by quota"
    if mode == "boundary_projection_repair":
        return "repair goal_boundary.write_scope projection before attempting the selected write"
    if mode == "bounded_delivery":
        return _protocol_first_candidate_action(payload) or "advance one bounded validated segment"
    if mode == "mapped_noop_if_unchanged":
        return "confirm no new instruction/evidence/todo/stale source/safe handoff, then quiet no-op"
    if execution_obligation.get("contract_obligation"):
        return str(execution_obligation.get("contract_obligation"))
    return "do not run delivery work for this goal in this turn"


def interaction_next_cli_actions(payload: dict[str, Any], *, mode: str) -> list[str]:
    goal_id = str(payload.get("goal_id") or "<GOAL_ID>")
    agent_identity = (
        payload.get("agent_identity")
        if isinstance(payload.get("agent_identity"), dict)
        else {}
    )
    agent_arg = (
        f" --agent-id {agent_identity.get('agent_id')}"
        if agent_identity.get("agent_id")
        else ""
    )
    if mode == "automation_prompt_upgrade":
        automation_prompt_upgrade = (
            payload.get("automation_prompt_upgrade")
            if isinstance(payload.get("automation_prompt_upgrade"), dict)
            else {}
        )
        actions = [
            str(automation_prompt_upgrade.get("primary_example_command") or "").strip(),
            str(automation_prompt_upgrade.get("side_agent_example_command") or "").strip(),
        ]
        return [action for action in actions if action] or [
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} --agent-id <registered-agent> --agent-scope '<scope>'",
        ]
    if mode == "monitor_quiet_skip":
        return [
            f"loopx quota monitor-poll --goal-id {goal_id}{agent_arg} --execute",
            f"loopx --format json quota should-run --goal-id {goal_id}{agent_arg}",
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
                f"loopx todo complete --goal-id {goal_id} --todo-id {monitor_todo_id} --evidence '<validated gate evidence>'",
                f"loopx todo update --goal-id {goal_id} --todo-id {gated_todo_id} --note '<public-safe gate repair reason>'",
                f"loopx refresh-state --goal-id {goal_id} --classification standing_monitor_gate_repair_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress{agent_arg}",
                f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{agent_arg}",
            ]
        route_candidates = (
            agent_scope_frontier.get("route_continuation_replan_candidates")
            if isinstance(agent_scope_frontier.get("route_continuation_replan_candidates"), list)
            else []
        )
        if route_candidates:
            return [
                f"loopx todo add --goal-id {goal_id} --role agent --text '<public-safe route continuation advancement todo>'",
                f"loopx refresh-state --goal-id {goal_id} --classification route_continuation_replan_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress{agent_arg}",
                f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{agent_arg}",
            ]
        candidates = (
            agent_scope_frontier.get("deferred_resume_candidates")
            if isinstance(agent_scope_frontier.get("deferred_resume_candidates"), list)
            else []
        )
        first_candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        todo_id = str(first_candidate.get("todo_id") or "<todo_id>")
        return [
            f"loopx todo update --goal-id {goal_id} --todo-id {todo_id} --status open --note '<public-safe successor replan reason>'",
            f"loopx refresh-state --goal-id {goal_id} --classification successor_replan_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress{agent_arg}",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute{agent_arg}",
        ]
    if _agent_scope_frontier_action(mode) is not None:
        return [
            "no quota spend while this agent has no in-scope runnable candidate",
            f"loopx --format json quota should-run --goal-id {goal_id}{agent_arg}",
        ]
    if mode == "external_evidence_observation":
        return [
            "read approved controller/job/marker/writeback surfaces only",
            f"loopx refresh-state --goal-id {goal_id} --classification <compact_blocker_or_transition>",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
    if mode == "side_agent_workspace_repair":
        agent_identity = (
            payload.get("agent_identity")
            if isinstance(payload.get("agent_identity"), dict)
            else {}
        )
        agent_arg = (
            f" --agent-id {agent_identity.get('agent_id')}"
            if agent_identity.get("agent_id")
            else ""
        )
        return [
            "create or switch to an independent git worktree/branch",
            f"loopx --format json quota should-run --goal-id {goal_id}{agent_arg}",
        ]
    if mode == "autonomous_replan":
        lane_action = _protocol_first_candidate_action(payload)
        first_action = (
            "run one bounded autonomous replan slice around "
            f"{lane_action}; write back the selected todo/frontier changes"
            if lane_action
            else "run one bounded autonomous replan slice and write back the selected next action/todo changes"
        )
        return [
            first_action,
            f"loopx refresh-state --goal-id {goal_id} --classification autonomous_replan_recorded --autonomous-replan-recorded --repair-delta-kind <delta_kind> --delivery-batch-scale <scale> --delivery-outcome <outcome>",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
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
            f"loopx refresh-state --goal-id {goal_id} --classification <validated_progress>",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return ["no quota spend for blocker-push/gate-notification"]
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
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return "no spend for gate or blocker push"
    if mode == "monitor_quiet_skip":
        return "no spend for unchanged monitor poll"
    if mode == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        return "spend once after validated successor replan/todo writeback"
    if _agent_scope_frontier_action(mode) is not None:
        return "no spend while the current agent has no in-scope runnable candidate"
    if mode == "side_agent_workspace_repair":
        return "no spend for moving side-agent work into an independent worktree"
    if mode == "automation_prompt_upgrade":
        return "no spend until the automation reruns quota guard with --agent-id"
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


def build_interaction_contract(payload: dict[str, Any]) -> dict[str, Any]:
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
    user_required = user_channel_action_required(payload)
    scoped_user_gate_fallback = mode == "scoped_user_gate_fallback"
    bounded_delivery_with_user_notice = mode == "bounded_delivery_with_user_notice"
    must_attempt = bool(execution_obligation.get("must_attempt_work")) if (
        not user_required or scoped_user_gate_fallback or bounded_delivery_with_user_notice
    ) else False
    delivery_allowed = (
        not user_required
        or scoped_user_gate_fallback
        or bounded_delivery_with_user_notice
    ) and bool(
        execution_obligation.get(
            "delivery_allowed",
            payload.get("normal_delivery_allowed")
            or payload.get("recovery_delivery_allowed")
            or payload.get("self_repair_allowed")
            or payload.get("should_run"),
        )
    )
    quiet_noop_allowed = (
        not user_required
        and not must_attempt
        and (
            _agent_scope_frontier_action(mode) is not None
            or mode
            in {
                "monitor_quiet_skip",
                "mapped_noop_if_unchanged",
                "quota_throttled",
                "blocked_wait",
                "skip",
            }
        )
    )
    spend_allowed_now = False
    spend_after_validation = mode in {
        "bounded_delivery",
        "outcome_floor_recovery",
        "capability_bridge_repair",
        "autonomous_replan",
        "control_plane_self_repair",
        "boundary_projection_repair",
        "external_evidence_observation",
        AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
        "scoped_user_gate_fallback",
        "bounded_delivery_with_user_notice",
    }
    user_channel: dict[str, Any] = {
        "action_required": user_required,
        "notify": "NOTIFY" if user_required else heartbeat_recommendation.get("notify", "DONT_NOTIFY"),
    }
    if user_required:
        user_channel["max_items"] = 3
    user_reason = (
        payload.get("open_todo_notify_reason")
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
    if user_reason:
        user_channel["reason"] = user_reason
    required_reads = _interaction_required_reads(payload)

    contract = {
        "schema_version": INTERACTION_CONTRACT_SCHEMA_VERSION,
        "mode": mode,
        "user_channel": user_channel,
        "agent_channel": {
            "must_attempt": must_attempt,
            "delivery_allowed": delivery_allowed,
            "quiet_noop_allowed": quiet_noop_allowed,
            "primary_action": _interaction_primary_agent_action(payload, mode=mode),
        },
        "cli_channel": {
            "next_cli_actions": interaction_next_cli_actions(payload, mode=mode),
            "spend_allowed_now": spend_allowed_now,
            "spend_after_validation": spend_after_validation,
            "spend_policy": _interaction_spend_policy(
                execution_obligation,
                heartbeat_recommendation,
                mode=mode,
                spend_after_validation=spend_after_validation,
            ),
        },
    }
    if required_reads:
        contract["agent_channel"]["required_reads"] = required_reads
        contract["cli_channel"]["required_reads"] = required_reads
    vision_continuation_audit = (
        payload.get("vision_continuation_audit")
        if isinstance(payload.get("vision_continuation_audit"), dict)
        else {}
    )
    if vision_continuation_audit.get("required"):
        contract["agent_channel"]["vision_continuation_audit"] = vision_continuation_audit
        vision_gap_judge = (
            vision_continuation_audit.get("vision_gap_judge")
            if isinstance(vision_continuation_audit.get("vision_gap_judge"), dict)
            else {}
        )
        contract["cli_channel"]["vision_continuation_audit"] = {
            "required": True,
            "required_before_closeout": vision_continuation_audit.get("required_before_closeout")
            or [],
            "recommended_action": vision_continuation_audit.get("recommended_action"),
        }
        if vision_gap_judge:
            contract["cli_channel"]["vision_continuation_audit"]["vision_gap_judge"] = {
                "done": vision_gap_judge.get("done"),
                "decision": vision_gap_judge.get("decision"),
                "reason": vision_gap_judge.get("reason"),
                "agent_judge_instruction": vision_gap_judge.get("agent_judge_instruction"),
                "evidence_read_instruction": vision_gap_judge.get("evidence_read_instruction"),
                "done_only_when": vision_gap_judge.get("done_only_when") or [],
                "continue_when": vision_gap_judge.get("continue_when") or [],
                "otherwise": vision_gap_judge.get("otherwise"),
            }
    if mode in {
        "user_gate",
        "user_todo_blocker_push",
        "user_action_required",
        "outcome_floor_recovery",
        "external_evidence_observation",
        "scoped_user_gate_fallback",
    } or payload.get("blocked_priority_fallback"):
        contract["fallback_policy"] = {"do_not_cancel_on_block": True}
    return contract
