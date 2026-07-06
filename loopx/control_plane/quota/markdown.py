from __future__ import annotations

from typing import Any

from ...control_plane import control_plane_policy_summary
from ...execution_profile import execution_profile_summary
from ...long_task_cadence import long_task_cadence_hint_summary
from ...orchestration import orchestration_policy_summary
from ..runtime.decision_freshness import DECISION_FRESHNESS_WARNING_ITEM_LIMIT
from .states import QUOTA_STATE_ORDER


def render_quota_markdown(payload: dict[str, Any]) -> str:
    title = "Quota Plan" if payload.get("mode") == "plan" else "Quota Status"
    lines = [
        f"# LoopX {title}",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- goals: `{payload.get('goal_count')}`",
        f"- runs: `{payload.get('run_count')}`",
    ]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    states = summary.get("states") if isinstance(summary.get("states"), dict) else {}
    state_text = ", ".join(f"{state}={states.get(state, 0)}" for state in QUOTA_STATE_ORDER)
    lines.append(
        "- summary: "
        f"registered_goals={summary.get('registered_goals')}, "
        f"health_blockers={summary.get('health_blockers')}, "
        f"next_automatic_turn={summary.get('next_automatic_turn') or 'none'}"
    )
    lines.append(f"- states: {state_text}")

    next_turn = payload.get("next_automatic_turn") if isinstance(payload.get("next_automatic_turn"), dict) else {}
    lines.extend(["", "## Next Automatic Turn"])
    if next_turn:
        quota = next_turn.get("quota") if isinstance(next_turn.get("quota"), dict) else {}
        lines.append(
            "- "
            f"`{next_turn.get('goal_id')}` "
            f"compute={quota.get('compute')} "
            f"slot_minutes={quota.get('slot_minutes')} "
            f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')} "
            f"action={next_turn.get('recommended_action') or 'inspect latest run'}"
        )
    else:
        lines.append("- none")

    health_items = payload.get("health_items") if isinstance(payload.get("health_items"), list) else []
    if health_items:
        lines.extend(["", "## Health Items"])
        for item in health_items:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"`{item.get('goal_id')}` "
                f"severity={item.get('severity')} "
                f"waiting_on={item.get('waiting_on')} "
                f"action={item.get('recommended_action')}"
            )

    groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
    lines.extend(["", "## Groups"])
    render_states = list(QUOTA_STATE_ORDER)
    if groups.get("unknown"):
        render_states.append("unknown")
    for state in render_states:
        items = groups.get(state) if isinstance(groups.get(state), list) else []
        if payload.get("mode") == "plan" and not items:
            continue
        lines.extend(["", f"### {state}"])
        if not items:
            lines.append("- none")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
            action = str(item.get("recommended_action") or "").replace("|", "\\|")
            lines.append(
                "- "
                f"`{item.get('goal_id')}`: "
                f"compute={quota.get('compute')} "
                f"slot_minutes={quota.get('slot_minutes')} "
                f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')} "
                f"waiting_on={item.get('waiting_on')} "
                f"status={item.get('status')} "
                f"phase={item.get('lifecycle_phase')}"
            )
            reason = quota.get("reason")
            if reason:
                lines.append(f"  - reason: {reason}")
            if action:
                lines.append(f"  - action: {action}")
            control_plane = item.get("control_plane") if isinstance(item.get("control_plane"), dict) else None
            if control_plane:
                lines.append(f"  - control_plane: {control_plane_policy_summary(control_plane)}")
            if item.get("agent_command"):
                lines.append(f"  - agent_command: `{item.get('agent_command')}`")
            if item.get("next_handoff_condition"):
                lines.append(f"  - next_handoff_condition: {item.get('next_handoff_condition')}")
    return "\n".join(lines)


def render_quota_scheduler_ack_markdown(payload: dict[str, Any]) -> str:
    event = payload.get("scheduler_ack_event") if isinstance(payload.get("scheduler_ack_event"), dict) else {}
    state = event.get("scheduler_state") if isinstance(event.get("scheduler_state"), dict) else {}
    before = event.get("before") if isinstance(event.get("before"), dict) else {}
    lines = [
        "# LoopX Quota Scheduler Ack",
        "",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- agent_id: `{payload.get('agent_id') or event.get('agent_id') or state.get('agent_id') or ''}`",
        f"- surface: `{payload.get('surface') or event.get('surface')}`",
        f"- state_key: `{payload.get('state_key') or event.get('state_key')}`",
        f"- applied_rrule: `{payload.get('applied_rrule') or event.get('applied_rrule')}`",
        f"- progression_index: `{state.get('progression_index')}`",
        f"- reset_token: `{state.get('reset_token') or ''}`",
        f"- identity_signature: `{state.get('identity_signature') or ''}`",
        f"- appended: `{payload.get('appended')}`",
        f"- registry_mutated: `{payload.get('registry_mutated')}`",
        f"- effective_action: `{before.get('effective_action')}`",
        f"- state: `{before.get('state')}`",
        f"- should_run: `{before.get('should_run')}`",
        f"- health_check: {payload.get('health_check') or 'scheduler ack state updated; no quota spend'}",
    ]
    if payload.get("scheduler_state_path"):
        lines.append(f"- scheduler_state_path: `{payload.get('scheduler_state_path')}`")
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    return "\n".join(lines)


def render_quota_should_run_markdown(payload: dict[str, Any]) -> str:
    quota = payload.get("quota") if isinstance(payload.get("quota"), dict) else {}
    lines = [
        "# LoopX Quota Should Run",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- should_run: `{payload.get('should_run')}`",
        f"- normal_delivery_allowed: `{payload.get('normal_delivery_allowed')}`",
        f"- recovery_delivery_allowed: `{payload.get('recovery_delivery_allowed')}`",
        f"- self_repair_allowed: `{payload.get('self_repair_allowed')}`",
        f"- effective_action: `{payload.get('effective_action')}`",
        f"- actionable_by_codex: `{payload.get('actionable_by_codex')}`",
        f"- state: `{payload.get('state')}`",
        f"- waiting_on: `{payload.get('waiting_on')}`",
        f"- status: `{payload.get('status')}`",
    ]
    if payload.get("project_asset_source"):
        lines.append(f"- project_asset_source: {payload.get('project_asset_source')}")
    agent_identity = (
        payload.get("agent_identity")
        if isinstance(payload.get("agent_identity"), dict)
        else {}
    )
    if agent_identity:
        lines.append(
            "- agent_identity: "
            f"agent_id={agent_identity.get('agent_id')} "
            f"role={agent_identity.get('role')} "
            f"primary_agent={agent_identity.get('primary_agent')} "
            f"handoff_agent={agent_identity.get('handoff_agent')}"
        )
    if payload.get("active_state_next_action"):
        lines.append(f"- active_state_next_action: {payload.get('active_state_next_action')}")
    if payload.get("latest_run_recommended_action"):
        lines.append(
            f"- latest_run_recommended_action: {payload.get('latest_run_recommended_action')}"
        )
    agent_lane_next_action = (
        payload.get("agent_lane_next_action")
        if isinstance(payload.get("agent_lane_next_action"), dict)
        else {}
    )
    if agent_lane_next_action:
        lines.append(
            "- agent_lane_next_action: "
            f"todo_id={agent_lane_next_action.get('todo_id')} "
            f"selected_by={agent_lane_next_action.get('selected_by')} "
            f"confidence={agent_lane_next_action.get('confidence')}"
        )
        if agent_lane_next_action.get("text"):
            lines.append(f"- agent_lane_next_action_text: {agent_lane_next_action.get('text')}")
    agent_lane_frontier_hint = (
        payload.get("agent_lane_frontier_hint")
        if isinstance(payload.get("agent_lane_frontier_hint"), dict)
        else {}
    )
    if agent_lane_frontier_hint:
        lines.append(
            "- agent_lane_frontier_hint: "
            f"decision={agent_lane_frontier_hint.get('decision')} "
            f"source={agent_lane_frontier_hint.get('source')} "
            f"reason_code={agent_lane_frontier_hint.get('reason_code')} "
            f"target_todo_id={agent_lane_frontier_hint.get('target_todo_id')}"
        )
    goal_route_hint = (
        payload.get("goal_route_hint")
        if isinstance(payload.get("goal_route_hint"), dict)
        else {}
    )
    if goal_route_hint:
        counts = (
            goal_route_hint.get("counts")
            if isinstance(goal_route_hint.get("counts"), dict)
            else {}
        )
        lines.append(
            "- goal_route_hint: "
            f"decision={goal_route_hint.get('route_decision')} "
            f"agent_id={goal_route_hint.get('agent_id')} "
            f"preserves_goal_next_action={goal_route_hint.get('preserves_goal_next_action')} "
            f"other_agent_claimed_advancement_count={counts.get('other_agent_claimed_advancement_count')}"
        )
        current_action = (
            goal_route_hint.get("current_agent_next_action")
            if isinstance(goal_route_hint.get("current_agent_next_action"), dict)
            else {}
        )
        if current_action:
            lines.append(
                "- goal_route_hint_current_action: "
                f"todo_id={current_action.get('todo_id')} "
                f"selected_by={current_action.get('selected_by')}"
            )
    agent_scope_frontier = (
        payload.get("agent_scope_frontier")
        if isinstance(payload.get("agent_scope_frontier"), dict)
        else {}
    )
    if agent_scope_frontier:
        lines.append(
            "- agent_scope_frontier: "
            f"action={agent_scope_frontier.get('action')} "
            f"agent_id={agent_scope_frontier.get('agent_id')} "
            f"quiet_noop_allowed={agent_scope_frontier.get('quiet_noop_allowed')}"
        )
        if agent_scope_frontier.get("reason"):
            lines.append(f"- agent_scope_frontier_reason: {agent_scope_frontier.get('reason')}")
        deferred_resume_candidates = (
            agent_scope_frontier.get("deferred_resume_candidates")
            if isinstance(agent_scope_frontier.get("deferred_resume_candidates"), list)
            else []
        )
        if deferred_resume_candidates:
            first_candidate = (
                deferred_resume_candidates[0]
                if isinstance(deferred_resume_candidates[0], dict)
                else {}
            )
            lines.append(
                "- agent_scope_deferred_resume_candidates: "
                f"`{len(deferred_resume_candidates)}` "
                f"top_todo_id={first_candidate.get('todo_id')}"
            )
        route_continuation_candidates = (
            agent_scope_frontier.get("route_continuation_replan_candidates")
            if isinstance(agent_scope_frontier.get("route_continuation_replan_candidates"), list)
            else []
        )
        if route_continuation_candidates:
            first_candidate = (
                route_continuation_candidates[0]
                if isinstance(route_continuation_candidates[0], dict)
                else {}
            )
            lines.append(
                "- agent_scope_route_continuation_replan_candidates: "
                f"`{len(route_continuation_candidates)}` "
                f"top_todo_id={first_candidate.get('todo_id')} "
                f"route={first_candidate.get('route_id') or first_candidate.get('route_key') or ''}"
            )
    goal_frontier = (
        payload.get("goal_frontier_projection")
        if isinstance(payload.get("goal_frontier_projection"), dict)
        else {}
    )
    if goal_frontier:
        remaining = (
            goal_frontier.get("remaining_advancement_frontier")
            if isinstance(goal_frontier.get("remaining_advancement_frontier"), dict)
            else {}
        )
        deferred_successors = (
            goal_frontier.get("deferred_successors")
            if isinstance(goal_frontier.get("deferred_successors"), dict)
            else {}
        )
        acceptance_gaps = (
            goal_frontier.get("acceptance_gaps")
            if isinstance(goal_frontier.get("acceptance_gaps"), list)
            else []
        )
        lines.append(
            "- goal_frontier_projection: "
            f"replan_required={goal_frontier.get('replan_required')} "
            f"current_agent_advancement={remaining.get('current_agent_claimed_advancement_count')} "
            f"unclaimed_advancement={remaining.get('unclaimed_advancement_count')} "
            f"other_agent_advancement={remaining.get('other_agent_claimed_advancement_count')} "
            f"deferred_ready={deferred_successors.get('ready_count')} "
            f"acceptance_gaps={len(acceptance_gaps)}"
        )
        vision_audit = (
            goal_frontier.get("vision_continuation_audit")
            if isinstance(goal_frontier.get("vision_continuation_audit"), dict)
            else {}
        )
        if vision_audit:
            lines.append(
                "- vision_continuation_audit: "
                f"required={vision_audit.get('required')} "
                f"decision={vision_audit.get('decision')} "
                f"trigger_count={vision_audit.get('trigger_count')}"
            )
            vision_gap_judge = (
                vision_audit.get("vision_gap_judge")
                if isinstance(vision_audit.get("vision_gap_judge"), dict)
                else {}
            )
            if vision_gap_judge:
                lines.append(
                    "- vision_gap_judge: "
                    f"done={vision_gap_judge.get('done')} "
                    f"decision={vision_gap_judge.get('decision')}"
                )
    replan_decision = (
        payload.get("autonomous_replan_decision")
        if isinstance(payload.get("autonomous_replan_decision"), dict)
        else {}
    )
    if replan_decision:
        lines.append(
            "- autonomous_replan_decision: "
            f"decision={replan_decision.get('decision')} "
            f"plane={replan_decision.get('decision_plane')}"
        )
    automation_prompt_upgrade = (
        payload.get("automation_prompt_upgrade")
        if isinstance(payload.get("automation_prompt_upgrade"), dict)
        else {}
    )
    if automation_prompt_upgrade:
        lines.append(
            "- automation_prompt_upgrade: "
            f"required={automation_prompt_upgrade.get('required')} "
            f"blocks_should_run={automation_prompt_upgrade.get('blocks_should_run')} "
            f"contract={automation_prompt_upgrade.get('contract')}"
        )
        if automation_prompt_upgrade.get("recommended_action"):
            lines.append(f"- automation_prompt_upgrade_action: {automation_prompt_upgrade.get('recommended_action')}")
        if automation_prompt_upgrade.get("primary_example_command"):
            lines.append(f"- automation_prompt_upgrade_primary: {automation_prompt_upgrade.get('primary_example_command')}")
        if automation_prompt_upgrade.get("side_agent_example_command"):
            lines.append(f"- automation_prompt_upgrade_side: {automation_prompt_upgrade.get('side_agent_example_command')}")
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    if capability_gate:
        lines.append(
            "- capability_gate: "
            f"action={capability_gate.get('action')} "
            f"required={capability_gate.get('required')} "
            f"missing={capability_gate.get('missing')}"
        )
        if capability_gate.get("decision_owner"):
            lines.append(f"- capability_gate_decision_owner: {capability_gate.get('decision_owner')}")
        runnable_candidates = (
            capability_gate.get("runnable_candidates")
            if isinstance(capability_gate.get("runnable_candidates"), list)
            else []
        )
        if runnable_candidates:
            lines.append(f"- capability_gate_runnable_candidates: `{len(runnable_candidates)}`")
        blocked_candidates = (
            capability_gate.get("blocked_candidates")
            if isinstance(capability_gate.get("blocked_candidates"), list)
            else []
        )
        if blocked_candidates:
            lines.append(f"- capability_gate_blocked_candidates: `{len(blocked_candidates)}`")
    workspace_guard = (
        payload.get("workspace_guard")
        if isinstance(payload.get("workspace_guard"), dict)
        else {}
    )
    if workspace_guard:
        lines.append(
            "- workspace_guard: "
            f"action={workspace_guard.get('action')} "
            f"current_workspace={workspace_guard.get('current_workspace')} "
            f"required_workspace={workspace_guard.get('required_workspace')}"
        )
        if workspace_guard.get("required_action"):
            lines.append(f"- workspace_guard_action: {workspace_guard.get('required_action')}")
    stale_latest_run_warning = (
        payload.get("stale_latest_run_warning")
        if isinstance(payload.get("stale_latest_run_warning"), dict)
        else {}
    )
    if stale_latest_run_warning:
        lines.append(
            "- stale_latest_run_warning: "
            f"requires_refresh_state={stale_latest_run_warning.get('requires_refresh_state')} "
            f"active_state_updated_at={stale_latest_run_warning.get('active_state_updated_at')} "
            f"latest_run_generated_at={stale_latest_run_warning.get('latest_run_generated_at')} "
            f"reason={stale_latest_run_warning.get('reason')}"
        )
        if stale_latest_run_warning.get("recommended_action"):
            lines.append(f"- stale_latest_run_action: {stale_latest_run_warning.get('recommended_action')}")
    state_action_projection_warning = (
        payload.get("state_action_projection_warning")
        if isinstance(payload.get("state_action_projection_warning"), dict)
        else {}
    )
    if state_action_projection_warning:
        lines.append(
            "- state_action_projection_warning: "
            f"requires_state_writeback={state_action_projection_warning.get('requires_state_writeback')} "
            f"reason={state_action_projection_warning.get('reason')}"
        )
        if state_action_projection_warning.get("selected_recommended_action"):
            lines.append(
                "- state_action_selected: "
                f"{state_action_projection_warning.get('selected_recommended_action')}"
            )
        if state_action_projection_warning.get("active_state_next_action"):
            lines.append(
                "- state_action_visible_next: "
                f"{state_action_projection_warning.get('active_state_next_action')}"
            )
        if state_action_projection_warning.get("recommended_action"):
            lines.append(
                f"- state_action_projection_action: {state_action_projection_warning.get('recommended_action')}"
            )
    next_action_projection = (
        payload.get("next_action_projection_warning")
        if isinstance(payload.get("next_action_projection_warning"), dict)
        else {}
    )
    if next_action_projection:
        lines.append(
            "- next_action_projection_warning: "
            f"requires_state_writeback={next_action_projection.get('requires_state_writeback')} "
            f"reason={next_action_projection.get('reason')}"
        )
        if next_action_projection.get("latest_run_recommended_action"):
            lines.append(
                "- latest_run_projection_action: "
                f"{next_action_projection.get('latest_run_recommended_action')}"
            )
    backlog_hygiene_warning = (
        payload.get("backlog_hygiene_warning")
        if isinstance(payload.get("backlog_hygiene_warning"), dict)
        else {}
    )
    if backlog_hygiene_warning:
        lines.append(
            "- backlog_hygiene_warning: "
            f"requires_agent_todo={backlog_hygiene_warning.get('requires_agent_todo')} "
            f"evidence_count={backlog_hygiene_warning.get('evidence_count')} "
            f"source_sections={','.join(backlog_hygiene_warning.get('source_sections') or [])}"
        )
        if backlog_hygiene_warning.get("recommended_action"):
            lines.append(f"- backlog_hygiene_action: {backlog_hygiene_warning.get('recommended_action')}")
    projection_gap = (
        payload.get("state_projection_gap")
        if isinstance(payload.get("state_projection_gap"), dict)
        else {}
    )
    if projection_gap:
        lines.append(
            "- state_projection_gap: "
            f"requires_todo_expansion={projection_gap.get('requires_todo_expansion')} "
            f"user_open={projection_gap.get('user_open_count')} "
            f"agent_open={projection_gap.get('agent_open_count')} "
            f"target_roles={','.join(projection_gap.get('target_roles') or [])}"
        )
        if projection_gap.get("recommended_action"):
            lines.append(f"- state_projection_gap_action: {projection_gap.get('recommended_action')}")
    blocked_priority_fallback = (
        payload.get("blocked_priority_fallback")
        if isinstance(payload.get("blocked_priority_fallback"), dict)
        else {}
    )
    if blocked_priority_fallback:
        selected = (
            blocked_priority_fallback.get("selected_executable")
            if isinstance(blocked_priority_fallback.get("selected_executable"), dict)
            else {}
        )
        blocked_items = (
            blocked_priority_fallback.get("blocked_items")
            if isinstance(blocked_priority_fallback.get("blocked_items"), list)
            else []
        )
        lines.append(
            "- blocked_priority_fallback: "
            f"notify_user={blocked_priority_fallback.get('notify_user')} "
            f"blocked_count={len(blocked_items)} "
            f"selected_index={selected.get('index')} "
            f"reason={blocked_priority_fallback.get('reason')}"
        )
        for blocked in blocked_items[:3]:
            if not isinstance(blocked, dict):
                continue
            text = str(blocked.get("text") or "").strip()
            if not text:
                continue
            index = blocked.get("index")
            suffix = f"[{index}]" if index is not None else ""
            lines.append(f"- blocked_priority_item{suffix}: {text}")
        if selected.get("text"):
            lines.append(f"- blocked_priority_selected: {selected.get('text')}")
        if blocked_priority_fallback.get("recommended_action"):
            lines.append(
                f"- blocked_priority_action: {blocked_priority_fallback.get('recommended_action')}"
            )
    scoped_user_gate_fallback = (
        payload.get("scoped_user_gate_fallback")
        if isinstance(payload.get("scoped_user_gate_fallback"), dict)
        else {}
    )
    if scoped_user_gate_fallback:
        selected = (
            scoped_user_gate_fallback.get("selected_executable")
            if isinstance(scoped_user_gate_fallback.get("selected_executable"), dict)
            else {}
        )
        blocked_gate = (
            scoped_user_gate_fallback.get("blocked_user_gate")
            if isinstance(scoped_user_gate_fallback.get("blocked_user_gate"), dict)
            else {}
        )
        blocked_items = (
            scoped_user_gate_fallback.get("blocked_agent_items")
            if isinstance(scoped_user_gate_fallback.get("blocked_agent_items"), list)
            else []
        )
        lines.append(
            "- scoped_user_gate_fallback: "
            f"notify_user={scoped_user_gate_fallback.get('notify_user')} "
            f"blocked_count={len(blocked_items)} "
            f"selected_index={selected.get('index')} "
            f"reason={scoped_user_gate_fallback.get('reason')}"
        )
        if blocked_gate.get("text"):
            lines.append(f"- scoped_user_gate: {blocked_gate.get('text')}")
        for blocked in blocked_items[:3]:
            if not isinstance(blocked, dict):
                continue
            text = str(blocked.get("text") or "").strip()
            if not text:
                continue
            index = blocked.get("index")
            suffix = f"[{index}]" if index is not None else ""
            lines.append(f"- scoped_user_gate_blocked_item{suffix}: {text}")
        if selected.get("text"):
            lines.append(f"- scoped_user_gate_selected: {selected.get('text')}")
        if scoped_user_gate_fallback.get("recommended_action"):
            lines.append(
                f"- scoped_user_gate_action: {scoped_user_gate_fallback.get('recommended_action')}"
            )
    completed_todo_archive_warning = (
        payload.get("completed_todo_archive_warning")
        if isinstance(payload.get("completed_todo_archive_warning"), dict)
        else {}
    )
    if completed_todo_archive_warning:
        lines.append(
            "- completed_todo_archive_warning: "
            f"requires_archive={completed_todo_archive_warning.get('requires_archive')} "
            f"active_done={completed_todo_archive_warning.get('active_done_count')} "
            f"max_active_done={completed_todo_archive_warning.get('max_active_done_count')} "
            f"archive_section={completed_todo_archive_warning.get('archive_section')}"
        )
        if completed_todo_archive_warning.get("recommended_action"):
            lines.append(
                f"- completed_todo_archive_action: {completed_todo_archive_warning.get('recommended_action')}"
            )
    replan_obligation = (
        payload.get("autonomous_replan_obligation")
        if isinstance(payload.get("autonomous_replan_obligation"), dict)
        else {}
    )
    if replan_obligation:
        trigger_kinds = [
            str(trigger.get("kind") or "")
            for trigger in replan_obligation.get("triggers") or []
            if isinstance(trigger, dict) and trigger.get("kind")
        ]
        lines.append(
            "- autonomous_replan_obligation: "
            f"required={replan_obligation.get('required')} "
            f"trigger_count={replan_obligation.get('trigger_count')} "
            f"triggers={','.join(trigger_kinds)}"
        )
        if replan_obligation.get("next_validation_command"):
            lines.append(f"- autonomous_replan_validation: `{replan_obligation.get('next_validation_command')}`")
    required_reads = payload.get("required_reads") if isinstance(payload.get("required_reads"), list) else []
    for read in required_reads[:3]:
        if not isinstance(read, dict):
            continue
        command = str(read.get("command") or "").strip()
        if command:
            lines.append(
                "- required_read: "
                f"kind={read.get('kind')} "
                f"agent_id={read.get('agent_id')} "
                f"todo_id={read.get('todo_id') or ''} "
                f"command=`{command}`"
            )
    work_lane_contract = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    if work_lane_contract:
        lines.append(
            "- work_lane_contract: "
            f"lane={work_lane_contract.get('lane')} "
            f"next={work_lane_contract.get('next_lane')} "
            f"obligation={work_lane_contract.get('obligation')} "
            f"must_attempt_work={work_lane_contract.get('must_attempt_work')}"
        )
        reason_codes = (
            work_lane_contract.get("reason_codes")
            if isinstance(work_lane_contract.get("reason_codes"), list)
            else []
        )
        if reason_codes:
            lines.append(f"- work_lane_reason_codes: {','.join(str(code) for code in reason_codes)}")
        if work_lane_contract.get("monitor_policy"):
            lines.append(f"- work_lane_monitor_policy: {work_lane_contract.get('monitor_policy')}")
        if work_lane_contract.get("monitor_due_count"):
            lines.append(
                "- work_lane_monitor_due: "
                f"count={work_lane_contract.get('monitor_due_count')} "
                f"selected={work_lane_contract.get('selected_todo_id') or ''} "
                f"next_due_at={work_lane_contract.get('selected_next_due_at') or ''}"
            )
        if work_lane_contract.get("action"):
            lines.append(f"- work_lane_action: {work_lane_contract.get('action')}")
        outcome_followthrough = (
            work_lane_contract.get("outcome_followthrough")
            if isinstance(work_lane_contract.get("outcome_followthrough"), dict)
            else {}
        )
        if outcome_followthrough:
            lines.append(
                "- work_lane_outcome_followthrough: "
                f"latest_outcome={outcome_followthrough.get('latest_delivery_outcome')} "
                f"latest_kind={outcome_followthrough.get('latest_delivery_turn_kind')} "
                f"obligation={outcome_followthrough.get('obligation')}"
            )
    interface_budget_cadence = (
        payload.get("interface_budget_cadence")
        if isinstance(payload.get("interface_budget_cadence"), dict)
        else {}
    )
    if interface_budget_cadence:
        lines.append(
            "- interface_budget_cadence: "
            f"overdue={interface_budget_cadence.get('overdue')} "
            f"within_budget={interface_budget_cadence.get('within_budget')} "
            f"checked_at={interface_budget_cadence.get('checked_at')} "
            f"next_check_due_at={interface_budget_cadence.get('next_check_due_at')} "
            f"tightest={interface_budget_cadence.get('tightest_surface')}/"
            f"{interface_budget_cadence.get('tightest_metric')} "
            f"headroom={interface_budget_cadence.get('headroom_remaining')} "
            f"recommendation={interface_budget_cadence.get('recommendation')}"
        )
    execution_profile = (
        payload.get("execution_profile")
        if isinstance(payload.get("execution_profile"), dict)
        else {}
    )
    if execution_profile:
        lines.append(f"- execution_profile: {execution_profile_summary(execution_profile)}")
    long_task_cadence_hint = (
        payload.get("long_task_cadence_hint")
        if isinstance(payload.get("long_task_cadence_hint"), dict)
        else {}
    )
    if long_task_cadence_hint:
        lines.append(
            f"- long_task_cadence_hint: {long_task_cadence_hint_summary(long_task_cadence_hint)}"
        )
    control_plane = payload.get("control_plane") if isinstance(payload.get("control_plane"), dict) else None
    if control_plane:
        lines.append(f"- control_plane: {control_plane_policy_summary(control_plane)}")

    def append_todo_summary(label: str, summary: dict[str, Any]) -> None:
        summary_parts = [
            f"open={summary.get('open_count')}",
            f"total={summary.get('total_count')}",
        ]
        if summary.get("claimed_open_count"):
            summary_parts.insert(1, f"claimed={summary.get('claimed_open_count')}")
            summary_parts.insert(2, f"unclaimed={summary.get('unclaimed_open_count', 0)}")
        if summary.get("monitor_due_count"):
            summary_parts.append(f"monitor_due={summary.get('monitor_due_count')}")
        if summary.get("completed_without_successor_count"):
            summary_parts.append(
                f"succession_warning={summary.get('completed_without_successor_count')}"
            )
        lines.append(f"- {label}_summary: {' '.join(summary_parts)}")
        succession_warning = (
            summary.get("todo_succession_warning")
            if isinstance(summary.get("todo_succession_warning"), dict)
            else {}
        )
        if succession_warning:
            warning_items = (
                succession_warning.get("items")
                if isinstance(succession_warning.get("items"), list)
                else []
            )
            todo_ids = [
                str(item.get("todo_id"))
                for item in warning_items[:3]
                if isinstance(item, dict) and item.get("todo_id")
            ]
            todo_ids_text = ",".join(todo_ids) if todo_ids else "n/a"
            lines.append(
                f"- {label}_succession_warning: "
                f"reason={succession_warning.get('reason_code')} "
                f"count={succession_warning.get('count')} "
                f"todo_ids={todo_ids_text}"
            )
        first_open = list(summary.get("first_open_items") if isinstance(summary.get("first_open_items"), list) else [])
        if label == "user_todo" and isinstance(summary.get("user_action_items"), list):
            first_open.extend(
                item
                for item in summary.get("user_action_items", [])
                if isinstance(item, dict)
            )
        for todo in first_open[:3]:
            if not isinstance(todo, dict):
                continue
            text = str(todo.get("text") or "").strip()
            if not text:
                continue
            index = todo.get("index")
            suffix = f"[{index}]" if index is not None else ""
            claim_suffix = (
                f" claimed_by={todo.get('claimed_by')}"
                if todo.get("claimed_by")
                else ""
            )
            lines.append(f"- {label}_next{suffix}: {text}{claim_suffix}")
        first_keys = {
            (
                str(todo.get("todo_id") or ""),
                todo.get("index"),
                str(todo.get("text") or "").strip(),
            )
            for todo in first_open
            if isinstance(todo, dict)
        }
        backlog = summary.get("backlog_items") if isinstance(summary.get("backlog_items"), list) else []
        extra_count = 0
        for todo in backlog:
            if not isinstance(todo, dict):
                continue
            text = str(todo.get("text") or "").strip()
            if not text:
                continue
            key = (str(todo.get("todo_id") or ""), todo.get("index"), text)
            if key in first_keys:
                continue
            index = todo.get("index")
            suffix = f"[{index}]" if index is not None else ""
            claim_suffix = (
                f" claimed_by={todo.get('claimed_by')}"
                if todo.get("claimed_by")
                else ""
            )
            lines.append(f"- {label}_backlog{suffix}: {text}{claim_suffix}")
            extra_count += 1
            if extra_count >= 5:
                break

    if quota:
        lines.append(
            "- quota: "
            f"compute={quota.get('compute')} "
            f"slot_minutes={quota.get('slot_minutes')} "
            f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')}"
        )
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    handoff_readiness = (
        payload.get("handoff_readiness")
        if isinstance(payload.get("handoff_readiness"), dict)
        else {}
    )
    if handoff_readiness:
        lines.append(
            "- handoff_readiness: "
            f"ready={handoff_readiness.get('ready')} "
            f"codex_ready={handoff_readiness.get('codex_ready')} "
            f"source={handoff_readiness.get('source')} "
            f"quota_state={handoff_readiness.get('quota_state')}"
        )
        interface_budget = (
            handoff_readiness.get("handoff_interface_budget")
            if isinstance(handoff_readiness.get("handoff_interface_budget"), dict)
            else {}
        )
        if interface_budget:
            lines.append(
                "- handoff_interface_budget: "
                f"mode={interface_budget.get('mode')} "
                f"max_lines={interface_budget.get('max_lines')} "
                f"max_chars={interface_budget.get('max_chars')}"
            )
        lines.append(
            "- handoff_state: "
            f"status={handoff_readiness.get('handoff_status')} "
            f"post_handoff_run_seen={handoff_readiness.get('post_handoff_run_seen')} "
            f"ready_at={handoff_readiness.get('handoff_ready_at') or ''}"
        )
        latest_handoff_run = (
            handoff_readiness.get("post_handoff_latest_run")
            if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
            else {}
        )
        if latest_handoff_run:
            outcome_suffix = ""
            if latest_handoff_run.get("delivery_outcome"):
                outcome_suffix = f" outcome={latest_handoff_run.get('delivery_outcome')}"
            lines.append(
                "- post_handoff_run: "
                f"classification={latest_handoff_run.get('classification')} "
                f"at={latest_handoff_run.get('generated_at')} "
                f"scale={latest_handoff_run.get('delivery_batch_scale') or ''}"
                f"{outcome_suffix}"
            )
        recent_handoff_runs = (
            handoff_readiness.get("post_handoff_recent_runs")
            if isinstance(handoff_readiness.get("post_handoff_recent_runs"), list)
            else []
        )
        recent_scales = [
            str(run.get("delivery_batch_scale") or "")
            for run in recent_handoff_runs
            if isinstance(run, dict)
        ]
        if recent_scales:
            recent_outcomes = [
                str(run.get("delivery_outcome") or "")
                for run in recent_handoff_runs
                if isinstance(run, dict) and run.get("delivery_outcome")
            ]
            outcome_text = f" outcome={','.join(recent_outcomes)}" if recent_outcomes else ""
            gap_text = (
                f" outcome_gap_streak={handoff_readiness.get('post_handoff_outcome_gap_streak')}"
                if "post_handoff_outcome_gap_streak" in handoff_readiness
                else ""
            )
            lines.append(
                "- post_handoff_recent_scales: "
                f"{','.join(recent_scales)} "
                f"small_streak={handoff_readiness.get('post_handoff_small_scale_streak', 0)}"
                f"{outcome_text}"
                f"{gap_text}"
            )
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    if heartbeat_recommendation:
        lines.append(
            "- heartbeat_recommendation: "
            f"mode={heartbeat_recommendation.get('recommended_mode')} "
            f"notify={heartbeat_recommendation.get('notify')}"
        )
        if heartbeat_recommendation.get("command"):
            lines.append(f"- heartbeat_command: `{heartbeat_recommendation.get('command')}`")
        if heartbeat_recommendation.get("stop_if_unchanged"):
            lines.append("- heartbeat_stop_if_unchanged: `True`")
        if heartbeat_recommendation.get("repeat_notification_required"):
            lines.append("- heartbeat_repeat_notification_required: `True`")
        if heartbeat_recommendation.get("spend_policy"):
            lines.append(f"- heartbeat_spend_policy: {heartbeat_recommendation.get('spend_policy')}")
        if heartbeat_recommendation.get("reason"):
            lines.append(f"- heartbeat_reason: {heartbeat_recommendation.get('reason')}")
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    if execution_obligation:
        lines.append(
            "- execution_obligation: "
            f"must_attempt_work={execution_obligation.get('must_attempt_work')} "
            f"kind={execution_obligation.get('kind')} "
            f"notify_is_execution_gate={execution_obligation.get('notify_is_execution_gate')}"
        )
        if execution_obligation.get("contract_obligation"):
            lines.append(f"- execution_contract_obligation: {execution_obligation.get('contract_obligation')}")
        if execution_obligation.get("reason"):
            lines.append(f"- execution_obligation_reason: {execution_obligation.get('reason')}")
    interaction_contract = (
        payload.get("interaction_contract")
        if isinstance(payload.get("interaction_contract"), dict)
        else {}
    )
    if interaction_contract:
        user_channel = (
            interaction_contract.get("user_channel")
            if isinstance(interaction_contract.get("user_channel"), dict)
            else {}
        )
        agent_channel = (
            interaction_contract.get("agent_channel")
            if isinstance(interaction_contract.get("agent_channel"), dict)
            else {}
        )
        cli_channel = (
            interaction_contract.get("cli_channel")
            if isinstance(interaction_contract.get("cli_channel"), dict)
            else {}
        )
        lines.append(
            "- interaction_contract: "
            f"schema={interaction_contract.get('schema_version')} "
            f"mode={interaction_contract.get('mode')} "
            f"user_required={user_channel.get('action_required')} "
            f"agent_must_attempt={agent_channel.get('must_attempt')} "
            f"quiet_noop_allowed={agent_channel.get('quiet_noop_allowed')} "
            f"spend_after_validation={cli_channel.get('spend_after_validation')}"
        )
        if agent_channel.get("primary_action"):
            lines.append(f"- interaction_agent_action: {agent_channel.get('primary_action')}")
    automation_liveness = (
        payload.get("automation_liveness")
        if isinstance(payload.get("automation_liveness"), dict)
        else {}
    )
    if automation_liveness:
        lines.append(
            "- automation_liveness: "
            f"action={automation_liveness.get('automation_action')} "
            f"keep_active={automation_liveness.get('keep_active')} "
            f"pause_allowed={automation_liveness.get('pause_allowed')}"
        )
        if automation_liveness.get("reason"):
            lines.append(f"- automation_liveness_reason: {automation_liveness.get('reason')}")
        if automation_liveness.get("pause_policy"):
            lines.append(f"- automation_pause_policy: {automation_liveness.get('pause_policy')}")
    scheduler_hint = (
        payload.get("scheduler_hint")
        if isinstance(payload.get("scheduler_hint"), dict)
        else {}
    )
    if scheduler_hint:
        codex_app = (
            scheduler_hint.get("codex_app")
            if isinstance(scheduler_hint.get("codex_app"), dict)
            else {}
        )
        unchanged_poll = (
            scheduler_hint.get("unchanged_poll")
            if isinstance(scheduler_hint.get("unchanged_poll"), dict)
            else {}
        )
        limits = unchanged_poll.get("limits") if isinstance(unchanged_poll.get("limits"), dict) else {}
        codex_cli_tui = (
            scheduler_hint.get("codex_cli_tui")
            if isinstance(scheduler_hint.get("codex_cli_tui"), dict)
            else {}
        )
        claude_code_loop = (
            scheduler_hint.get("claude_code_loop")
            if isinstance(scheduler_hint.get("claude_code_loop"), dict)
            else {}
        )
        cli_unchanged_limit = (
            limits.get("codex_cli_tui")
            if "codex_cli_tui" in limits
            else codex_cli_tui.get("unchanged_poll_limit")
        )
        claude_unchanged_limit = (
            limits.get("claude_code_loop")
            if "claude_code_loop" in limits
            else claude_code_loop.get("unchanged_poll_limit")
        )
        lines.append(
            "- scheduler_hint: "
            f"action={scheduler_hint.get('action')} "
            f"cadence={scheduler_hint.get('cadence_class')} "
            f"codex_app_minutes={codex_app.get('recommended_interval_minutes')} "
            f"codex_app_rrule={codex_app.get('recommended_rrule')} "
            f"codex_app_apply_needed={(codex_app.get('stateful_backoff') or {}).get('apply_needed') if isinstance(codex_app.get('stateful_backoff'), dict) else None} "
            f"codex_app_progression={codex_app.get('example_progression_minutes')} "
            f"cli_unchanged_limit={cli_unchanged_limit} "
            f"claude_unchanged_limit={claude_unchanged_limit}"
        )
        if scheduler_hint.get("reason"):
            lines.append(f"- scheduler_hint_reason: {scheduler_hint.get('reason')}")
        reset_policy = (
            scheduler_hint.get("reset_policy")
            if isinstance(scheduler_hint.get("reset_policy"), dict)
            else {}
        )
        if reset_policy:
            lines.append(
                "- scheduler_reset: "
                f"initial_interval={reset_policy.get('codex_app_initial_interval_minutes')} "
                f"initial_rrule={reset_policy.get('codex_app_initial_rrule')} "
                f"reset_generation={reset_policy.get('reset_token')} "
                f"identity_signature={reset_policy.get('identity_signature')}"
            )
    protocol_action_packet = (
        payload.get("protocol_action_packet")
        if isinstance(payload.get("protocol_action_packet"), dict)
        else {}
    )
    if protocol_action_packet:
        lines.append(
            "- protocol_action_packet: "
            f"schema={protocol_action_packet.get('schema_version')} "
            f"{protocol_action_packet.get('summary') or ''}"
        )
    stall_self_repair = (
        payload.get("stall_self_repair")
        if isinstance(payload.get("stall_self_repair"), dict)
        else {}
    )
    if stall_self_repair:
        lines.append(
            "- stall_self_repair: "
            f"trigger={stall_self_repair.get('trigger')} "
            f"mode={stall_self_repair.get('recommended_mode')} "
            f"action={stall_self_repair.get('effective_action')}"
        )
        if stall_self_repair.get("repair_focus"):
            lines.append(f"- stall_repair_focus: {stall_self_repair.get('repair_focus')}")
        if stall_self_repair.get("missing_write_scopes"):
            lines.append(
                "- boundary_missing_write_scopes: "
                f"{', '.join(str(value) for value in stall_self_repair.get('missing_write_scopes') or [])}"
            )
        blockers = (
            stall_self_repair.get("blocking_health_items")
            if isinstance(stall_self_repair.get("blocking_health_items"), list)
            else []
        )
        for blocker in blockers[:3]:
            if not isinstance(blocker, dict):
                continue
            lines.append(
                "- stall_health_blocker: "
                f"goal={blocker.get('goal_id')} "
                f"status={blocker.get('status')} "
                f"waiting_on={blocker.get('waiting_on')} "
                f"action={blocker.get('recommended_action')}"
            )
    if payload.get("safe_bypass_allowed"):
        lines.append(f"- safe_bypass_allowed: `{payload.get('safe_bypass_allowed')}`")
    if payload.get("safe_bypass_kind"):
        lines.append(f"- safe_bypass_kind: {payload.get('safe_bypass_kind')}")
    if payload.get("blocked_action_scope"):
        lines.append(f"- blocked_action_scope: `{payload.get('blocked_action_scope')}`")
    if payload.get("safe_bypass_policy"):
        lines.append(f"- safe_bypass_policy: {payload.get('safe_bypass_policy')}")
    decision_freshness_warning = (
        payload.get("decision_freshness_warning")
        if isinstance(payload.get("decision_freshness_warning"), dict)
        else {}
    )
    if decision_freshness_warning:
        lines.append(
            "- decision_freshness_warning: "
            f"rebase_required={decision_freshness_warning.get('rebase_required_count')} "
            f"window_days={decision_freshness_warning.get('window_days')} "
            f"source={decision_freshness_warning.get('source')}"
        )
        if decision_freshness_warning.get("message"):
            lines.append(f"- decision_freshness_action: {decision_freshness_warning.get('message')}")
        freshness_items = (
            decision_freshness_warning.get("items")
            if isinstance(decision_freshness_warning.get("items"), list)
            else []
        )
        for item in freshness_items[:DECISION_FRESHNESS_WARNING_ITEM_LIMIT]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- decision_freshness_item: "
                f"kind={item.get('decision_kind')} "
                f"state={item.get('freshness_state')} "
                f"age_days={item.get('age_days')} "
                f"newer_7d={item.get('newer_event_count_7d')} "
                f"at={item.get('decision_at')}"
            )
    promotion_readiness_warning = (
        payload.get("promotion_readiness_warning")
        if isinstance(payload.get("promotion_readiness_warning"), dict)
        else {}
    )
    if promotion_readiness_warning:
        lines.append(
            "- promotion_readiness_warning: "
            f"status={promotion_readiness_warning.get('freshness_status')} "
            f"requires_readiness_run={promotion_readiness_warning.get('requires_readiness_run')} "
            f"window_hours={promotion_readiness_warning.get('freshness_window_hours')} "
            f"source={promotion_readiness_warning.get('source')}"
        )
        if promotion_readiness_warning.get("message"):
            lines.append(f"- promotion_readiness_action: {promotion_readiness_warning.get('message')}")
        lines.append(
            "- promotion_readiness_evidence: "
            f"goal={promotion_readiness_warning.get('goal_id') or ''} "
            f"generated_at={promotion_readiness_warning.get('generated_at') or ''} "
            f"age_hours={promotion_readiness_warning.get('age_hours')} "
            f"artifacts={promotion_readiness_warning.get('json_exists')}/{promotion_readiness_warning.get('markdown_exists')}"
        )
        if promotion_readiness_warning.get("reason"):
            lines.append(f"- promotion_readiness_reason: {promotion_readiness_warning.get('reason')}")
    reward_lesson_warning = (
        payload.get("reward_lesson_projection_warning")
        if isinstance(payload.get("reward_lesson_projection_warning"), dict)
        else {}
    )
    if reward_lesson_warning:
        lines.append(
            "- reward_lesson_projection_warning: "
            f"matches={reward_lesson_warning.get('match_count')} "
            f"source={reward_lesson_warning.get('source')}"
        )
        if reward_lesson_warning.get("message"):
            lines.append(f"- reward_lesson_action: {reward_lesson_warning.get('message')}")
        for match in (reward_lesson_warning.get("matches") or [])[:3]:
            if not isinstance(match, dict):
                continue
            lines.append(
                "- reward_lesson_match: "
                f"kind={match.get('kind')} "
                f"decision={match.get('decision')} "
                f"avoid={match.get('avoid')} "
                f"summary={match.get('summary')}"
            )
    goal_boundary = payload.get("goal_boundary") if isinstance(payload.get("goal_boundary"), dict) else {}
    if goal_boundary:
        adapter = goal_boundary.get("adapter") if isinstance(goal_boundary.get("adapter"), dict) else {}
        if adapter:
            lines.append(
                "- goal_boundary_adapter: "
                f"{adapter.get('kind') or ''}:{adapter.get('status') or ''}"
            )
        write_scope = goal_boundary.get("write_scope") if isinstance(goal_boundary.get("write_scope"), list) else []
        if write_scope:
            lines.append(f"- goal_boundary_write_scope: {', '.join(str(value) for value in write_scope)}")
        approvals = (
            goal_boundary.get("requires_parent_approval")
            if isinstance(goal_boundary.get("requires_parent_approval"), list)
            else []
        )
        if approvals:
            lines.append(f"- goal_boundary_requires_approval: {', '.join(str(value) for value in approvals)}")
        guards = goal_boundary.get("guards") if isinstance(goal_boundary.get("guards"), list) else []
        for guard in guards[:5]:
            lines.append(f"- goal_boundary_guard: {guard}")
        orchestration = (
            goal_boundary.get("orchestration")
            if isinstance(goal_boundary.get("orchestration"), dict)
            else None
        )
        if orchestration:
            lines.append(f"- goal_boundary_orchestration: {orchestration_policy_summary(orchestration)}")
        run_permission_policy = (
            goal_boundary.get("run_permission_policy")
            if isinstance(goal_boundary.get("run_permission_policy"), dict)
            else None
        )
        if run_permission_policy:
            lines.append(
                "- goal_boundary_run_permission_policy: "
                f"valid={run_permission_policy.get('valid')} "
                f"delivery_allowed={run_permission_policy.get('delivery_allowed')} "
                f"no_upload={run_permission_policy.get('no_upload_required')} "
                f"compact_only={run_permission_policy.get('compact_observation_only')} "
                f"max_minutes={run_permission_policy.get('max_wall_time_minutes')}"
            )
        if goal_boundary.get("stop_condition"):
            lines.append(f"- goal_boundary_stop_condition: {goal_boundary.get('stop_condition')}")
    if payload.get("operator_question"):
        lines.append(f"- operator_question: {payload.get('operator_question')}")
    if payload.get("notify_user_on_gate"):
        lines.append(f"- notify_user_on_gate: `{payload.get('notify_user_on_gate')}`")
    if payload.get("notify_user_on_open_todo"):
        lines.append(f"- notify_user_on_open_todo: `{payload.get('notify_user_on_open_todo')}`")
    if payload.get("open_todo_notify_reason"):
        lines.append(f"- open_todo_notify_reason: {payload.get('open_todo_notify_reason')}")
    if payload.get("open_todo_notification_policy"):
        lines.append(f"- open_todo_notification_policy: {payload.get('open_todo_notification_policy')}")
    if payload.get("gate_prompt"):
        lines.extend(["", "## Gate Prompt", str(payload.get("gate_prompt"))])
    user_todo_summary = (
        payload.get("user_todo_summary") if isinstance(payload.get("user_todo_summary"), dict) else {}
    )
    if user_todo_summary:
        append_todo_summary("user_todo", user_todo_summary)
    agent_todo_summary = (
        payload.get("agent_todo_summary") if isinstance(payload.get("agent_todo_summary"), dict) else {}
    )
    if agent_todo_summary:
        append_todo_summary("agent_todo", agent_todo_summary)
    todo_write_hint = payload.get("todo_write_hint") if isinstance(payload.get("todo_write_hint"), dict) else {}
    if todo_write_hint:
        lines.append(f"- todo_write_hint: {todo_write_hint.get('rule')}")
        lines.append(f"- user_gate_command_template: `{todo_write_hint.get('user_gate_command_template')}`")
        lines.append(f"- user_action_command_template: `{todo_write_hint.get('user_action_command_template')}`")
        lines.append(f"- agent_todo_command_template: `{todo_write_hint.get('agent_todo_command_template')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")
    if payload.get("agent_command"):
        lines.append(f"- agent_command: `{payload.get('agent_command')}`")
    if payload.get("next_handoff_condition"):
        lines.append(f"- next_handoff_condition: {payload.get('next_handoff_condition')}")
    summary = payload.get("plan_summary") if isinstance(payload.get("plan_summary"), dict) else {}
    states = summary.get("states") if isinstance(summary.get("states"), dict) else {}
    if summary:
        state_text = ", ".join(f"{state}={states.get(state, 0)}" for state in QUOTA_STATE_ORDER)
        lines.append(
            "- plan_summary: "
            f"next_automatic_turn={summary.get('next_automatic_turn') or 'none'} "
            f"{state_text}"
        )
    return "\n".join(lines)
