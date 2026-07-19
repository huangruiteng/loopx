from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .control_plane.agents.agent_scope import (
    AgentScopeFrontierAction,
    _action_scope_tokens_from_text,
    _agent_lane_frontier_hint,
    _agent_scope_deferred_resume_candidates,
    _agent_scope_frontier_action,
    _agent_scope_no_candidate_frontier,
    _agent_scoped_user_todo_override,
    _scoped_user_gate_fallback,
)
from .control_plane.agents.agent_lane_recommendation import (
    build_agent_lane_next_action,
    selected_action_with_agent_lane,
    selected_recommended_action_from_work_lane,
)
from .control_plane.agents.workspace_guard import build_agent_workspace_guard
from .control_plane.agents.identity import build_identity_aware_prompt_upgrade, build_quota_agent_identity
from .control_plane import compact_control_plane_policy
from .execution_profile import (
    execution_profile_outcome_floor,
    outcome_floor_threshold,
)
from .control_plane.work_items.execution_obligation import build_execution_obligation
from .control_plane.work_items.interaction_contract import (
    build_interaction_contract,
    build_protocol_action_packet,
    finalize_user_gate_notification_cooldown,
    user_channel_action_required as _user_channel_action_required,
)
from .control_plane.work_items.primary_action import (
    protocol_action_text as _protocol_action_text,
)
from .control_plane.goals.goal_frontier import (
    AUTONOMOUS_REPLAN_REQUIRED_MODE,
    autonomous_replan_decision_allowed,
    build_goal_frontier_projection_context_from_status,
    goal_frontier_is_terminal_no_followup,
)
from .control_plane.quota.heartbeat_recommendation import (
    HEARTBEAT_HANDOFF_READINESS_COMPACT_FIELDS as HANDOFF_READINESS_COMPACT_FIELDS,
    HEARTBEAT_POST_HANDOFF_RUN_COMPACT_FIELDS as POST_HANDOFF_RUN_COMPACT_FIELDS,
    build_heartbeat_recommendation,
    open_todo_notify_reason,
)
from .control_plane.quota.projection_repair import (
    build_boundary_projection_repair_hint,
    build_state_projection_gap,
    build_state_projection_gap_repair_hint,
)
from .control_plane.quota.stall_repair import (
    apply_stall_repair_delivery_guard,
    build_quota_stall_self_repair_hint,
    stall_repair_blocked_action_scope,
    stall_repair_payload,
)
from .control_plane.quota.decision_summary import (
    quota_decision_agent_id,
)
from .control_plane.quota.goal_boundary import effective_available_capabilities as _effective_available_capabilities, goal_boundary as _goal_boundary, quota_execution_profile_summary as _quota_execution_profile_summary
from .control_plane.quota.monitor_poll import (
    QUOTA_MONITOR_POLL_CLASSIFICATION as QUOTA_MONITOR_POLL_CLASSIFICATION,
    build_quota_monitor_poll_event as build_quota_monitor_poll_event,
    record_quota_monitor_poll_for_decision,
)
from .control_plane.quota.recent_runs import (
    build_monitor_debt_arbitration as _build_monitor_debt_arbitration,
    goal_latest_runs as _goal_latest_runs,
    recent_external_monitor_observation_unchanged as _recent_external_monitor_observation_unchanged,
)
from .presentation.renderers.quota_event_markdown import render_quota_monitor_poll_markdown as _render_quota_monitor_poll_markdown, render_quota_slot_preview_markdown as _render_quota_slot_preview_markdown, render_quota_slot_preview_markdown as render_quota_slot_preview_markdown
from .presentation.renderers.quota_markdown import render_quota_markdown as render_quota_markdown, render_quota_scheduler_ack_markdown as render_quota_scheduler_ack_markdown, render_quota_should_run_markdown as render_quota_should_run_markdown
from .control_plane.quota.scheduler_ack import (
    QUOTA_SCHEDULER_ACK_CLASSIFICATION,
    record_quota_scheduler_ack_for_decision,
)
from .control_plane.quota.selected_todo_projection import (
    selected_todo_projection as _selected_todo_projection,
)
from .capabilities.reward_memory.experiment import (
    resolve_reward_memory_experiment_from_status as _resolve_reward_memory_experiment_from_status,
)
from .control_plane.quota.task_orchestration import (
    apply_task_orchestration_contract,
    attach_task_orchestration_payload,
    build_quota_work_lane_contract,
    payload_work_lane_contract as _payload_work_lane_contract,
    task_goal_route_hint,
    task_orchestration_effective_action,
    task_selected_recommended_action,
)
from .control_plane.quota.slot_accounting import (
    QUOTA_SLOT_SPENT_CLASSIFICATION,
    QUOTA_SLOT_VOIDED_CLASSIFICATION,
    build_quota_slot_preview_for_decision,
    build_quota_slot_spend_event as _build_quota_slot_spend_event,
    build_quota_slot_void_event as build_quota_slot_void_event,
    build_quota_slot_void_preview_for_decision,
    load_quota_event_from_run,
    record_quota_slot_spend_from_preview,
    record_quota_slot_void_from_preview,
)
from .control_plane.quota.spend_sources import (
    DEFAULT_SLOT_SPEND_SOURCE,
)
from .control_plane.quota.states import QUOTA_STATE_ORDER
from .control_plane.runtime.decision_freshness import (
    decision_freshness_warning as _decision_freshness_warning,
)
from .control_plane.runtime.time import parse_timestamp as _parse_timestamp
from .control_plane.runtime.agent_scoped_evidence_log import (
    build_agent_scoped_required_read,
)
from .control_plane.runtime.promotion_readiness import (
    promotion_readiness_warning as _promotion_readiness_warning,
)
from .control_plane.work_items.goal_route_hint import build_goal_route_hint
from .control_plane.work_items.capability_monitor_fallback import build_capability_gate_with_monitor_fallback
from .control_plane.work_items.work_lane import lark_inbox_reply_due_work_lane_contract, scoped_user_gate_due_monitor_contract, work_lane_contract_is_due_monitor_attempt, work_lane_contract_is_lark_inbox_reply_due
from .control_plane.scheduler.scheduler_hint import build_scheduler_hint
from .control_plane.scheduler.execution_context import (
    SchedulerExecutionContextResolution,
    resolve_scheduler_execution_context,
)
from .control_plane.scheduler.external_evidence_observation import build_external_evidence_observation_obligation
from .control_plane.scheduler.automation_liveness import build_automation_liveness
from .control_plane.scheduler.state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    CODEX_APP_SURFACE,
    load_scheduler_state,
)
from .state_projection import (
    actions_are_projection_aligned,
    next_action_projection_warning,
    state_action_projection_warning as build_state_action_projection_warning,
)
from .control_plane.todos.contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_BLOCKER,
    normalize_todo_claimed_by,
    normalize_todo_status,
)
from .control_plane.todos.summary_item import (
    compact_todo_summary_item,
)
from .control_plane.todos.projection import (
    todo_index_rank as projection_todo_index_rank,
    todo_item_expires_at as projection_todo_item_expires_at,
    todo_item_is_actionable_open as projection_todo_item_is_actionable_open,
    todo_item_is_due_monitor as projection_todo_item_is_due_monitor,
    todo_item_is_expired_monitor as projection_todo_item_is_expired_monitor,
    todo_item_missing_monitor_schedule as projection_todo_item_missing_monitor_schedule,
    todo_item_next_due_at as projection_todo_item_next_due_at,
    todo_item_task_class as projection_todo_item_task_class,
    todo_priority_label as projection_todo_priority_label,
    todo_priority_rank as projection_todo_priority_rank,
    todo_projection_sort_key as projection_todo_projection_sort_key,
    todo_summary_claim_scope_agent_id as projection_todo_summary_claim_scope_agent_id,
)
from .control_plane.todos.quota_summary import (
    compact_quota_todo_summary_for_payload,
    select_quota_todo_source_items,
    select_quota_todo_summary,
)
from .control_plane.todos.user_gate import (
    build_gate_prompt as _build_gate_prompt,
    has_open_user_gate_todo as _has_open_user_gate_todo,
    open_todo_count as _open_todo_count,
    should_notify_user_on_open_todo as _should_notify_user_on_open_todo,
    user_gate_todo_notify_reason as _user_gate_todo_notify_reason,
)
from .control_plane.todos.write_hint import build_todo_write_hint


_PUBLIC_COMPAT_REEXPORTS = {
    "QUOTA_MONITOR_POLL_CLASSIFICATION": "loopx.control_plane.quota.monitor_poll",
    "build_quota_monitor_poll_event": "loopx.control_plane.quota.monitor_poll",
    "render_quota_markdown": "loopx.presentation.renderers.quota_markdown",
    "render_quota_scheduler_ack_markdown": "loopx.presentation.renderers.quota_markdown",
    "render_quota_should_run_markdown": "loopx.presentation.renderers.quota_markdown",
    "build_quota_slot_void_event": "loopx.control_plane.quota.slot_accounting",
    "render_quota_slot_preview_markdown": "loopx.presentation.renderers.quota_event_markdown",
}


DEFAULT_COMPUTE_QUOTA = 1.0
DEFAULT_WINDOW_HOURS = 24
DEFAULT_SLOT_MINUTES = 1
AUTONOMOUS_REPLAN_ACK_NEUTRAL_CLASSIFICATIONS = {
    QUOTA_SLOT_SPENT_CLASSIFICATION,
    QUOTA_SLOT_VOIDED_CLASSIFICATION,
    QUOTA_SCHEDULER_ACK_CLASSIFICATION,
    "delivery_completion_spend_accounted_v0",
}
FOCUS_WAIT_LIFECYCLE_MARKERS = {
    "continuation_boundary",
    "focus_wait",
}
FOCUS_WAIT_REASON = (
    "focus wait: delivery lane has a continuation boundary or missing novelty; "
    "wait for new evidence, owner input, external eval, or a clean baseline before "
    "spending delivery compute"
)
AUTONOMOUS_CANDIDATE_CONTEXT_FIELDS = (
    "source",
    "open_count",
    "task_class",
    "items",
)
SELF_REPAIR_SPEND_ACTIONS = {
    "control_plane_health_repair",
    "control_plane_projection_repair",
    "state_projection_gap_repair",
    "boundary_projection_repair",
    "todo_decision_scope_projection_repair",
}
MONITOR_DUE_ITEM_LIMIT = 1

def _validate_goal_id_path_segment(goal_id: str) -> str:
    value = goal_id.strip()
    if not value:
        raise ValueError("goal id is required")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("goal id must be a single path segment")
    if Path(value).name != value:
        raise ValueError("goal id must not include path traversal")
    return value


def _number(value: Any, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _int_number(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return default
    return default


def _clamp_compute(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 2)


def _text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return [str(value)]


def _has_focus_wait_marker(*values: Any) -> bool:
    for value in values:
        for text in _text_values(value):
            marker = text.strip().lower()
            if marker in FOCUS_WAIT_LIFECYCLE_MARKERS:
                return True
    return False


def _focus_wait_quota(payload: dict[str, Any]) -> dict[str, Any]:
    quota = dict(payload)
    quota["state"] = "focus_wait"
    quota["reason"] = FOCUS_WAIT_REASON
    quota["blocked_action_scope"] = "delivery_focus"
    quota["focus_wait"] = True
    return quota


def quota_with_handoff_outcome_floor(
    quota: dict[str, Any],
    *,
    waiting_on: str | None = None,
    project_asset: dict[str, Any] | None = None,
    handoff_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if waiting_on != "codex":
        return quota
    if not isinstance(handoff_readiness, dict) or not handoff_readiness:
        return quota
    profile = (
        project_asset.get("execution_profile")
        if isinstance(project_asset, dict) and isinstance(project_asset.get("execution_profile"), dict)
        else None
    )
    outcome_gap_streak = handoff_readiness.get("post_handoff_outcome_gap_streak")
    if not isinstance(outcome_gap_streak, int) or outcome_gap_streak <= 0:
        return quota
    threshold = outcome_floor_threshold(profile)
    if outcome_gap_streak < threshold:
        return quota
    state = str(quota.get("state") or "eligible")
    if state in {"blocked_health", "operator_gate", "waiting", "paused", "throttled"}:
        return quota

    floor = execution_profile_outcome_floor(profile)
    must_advance = [
        str(value).strip()
        for value in (floor.get("must_advance") if isinstance(floor.get("must_advance"), list) else [])
        if str(value).strip()
    ]
    avoid = [
        str(value).strip()
        for value in (floor.get("avoid") if isinstance(floor.get("avoid"), list) else [])
        if str(value).strip()
    ]
    reason_parts = [
        f"handoff outcome floor not met: outcome_gap_streak={outcome_gap_streak}/{threshold}",
        "report blocker without spend or return with outcome-scale evidence",
    ]
    if must_advance:
        reason_parts.append(f"must_advance={'+'.join(must_advance)}")
    if avoid:
        reason_parts.append(f"avoid={'+'.join(avoid)}")

    blocked = dict(quota)
    blocked["state"] = "focus_wait"
    blocked["reason"] = "; ".join(reason_parts)
    blocked["blocked_action_scope"] = "delivery_outcome_floor"
    blocked["focus_wait"] = True
    blocked["handoff_outcome_floor_block"] = True
    blocked["post_handoff_outcome_gap_streak"] = outcome_gap_streak
    blocked["outcome_gap_threshold"] = threshold
    if must_advance:
        blocked["must_advance"] = must_advance
        blocked["safe_bypass_allowed"] = True
        blocked["safe_bypass_kind"] = "outcome_floor_recovery"
        blocked["safe_bypass_policy"] = (
            "Outcome-floor recovery only: attempt one bounded "
            f"{'+'.join(must_advance)} evidence segment or write back a concrete blocker; "
            "avoid surface-only work; spend only after validated evidence/blocker writeback."
        )
    if avoid:
        blocked["avoid"] = avoid
    return blocked


def _quota_with_focus_wait_override(
    quota: dict[str, Any],
    *,
    waiting_on: str | None = None,
    lifecycle_phase: Any = None,
    lifecycle_flags: Any = None,
    status: Any = None,
) -> dict[str, Any]:
    if waiting_on != "codex":
        return quota
    if not _has_focus_wait_marker(lifecycle_phase, lifecycle_flags, status):
        return quota
    state = str(quota.get("state") or "eligible")
    if state in {"blocked_health", "operator_gate", "waiting", "paused"}:
        return quota
    return _focus_wait_quota(quota)


def goal_quota_config(goal: dict[str, Any] | None) -> dict[str, Any]:
    raw = goal.get("quota") if goal and isinstance(goal.get("quota"), dict) else {}
    if goal and "compute_quota" in goal and "compute" not in raw:
        raw = {**raw, "compute": goal.get("compute_quota")}
    compute = _clamp_compute(_number(raw.get("compute"), default=DEFAULT_COMPUTE_QUOTA))
    window_hours = max(1, _int_number(raw.get("window_hours"), default=DEFAULT_WINDOW_HOURS))
    slot_minutes = max(1, _int_number(raw.get("slot_minutes"), default=DEFAULT_SLOT_MINUTES))
    spent_slots = max(0, _int_number(raw.get("spent_slots"), default=0))
    default_allowed_slots = round((window_hours * 60 / slot_minutes) * compute)
    allowed_slots = max(0, _int_number(raw.get("allowed_slots"), default=default_allowed_slots))
    payload: dict[str, Any] = {
        "compute": compute,
        "window_hours": window_hours,
        "slot_minutes": slot_minutes,
        "allowed_slots": allowed_slots,
        "spent_slots": spent_slots,
    }
    if raw.get("next_eligible_at"):
        payload["next_eligible_at"] = str(raw.get("next_eligible_at"))
    return payload


def _quota_event_run_key(run: dict[str, Any], event: dict[str, Any]) -> str:
    return str(event.get("run_generated_at") or run.get("generated_at") or "")


def goal_quota_with_spend_ledger(
    goal: dict[str, Any] | None,
    runs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = goal_quota_config(goal)
    goal_id = str(goal.get("id") or "") if goal else ""
    current_time = now or datetime.now(timezone.utc).astimezone()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    window_start = current_time - timedelta(hours=int(payload["window_hours"]))
    spent_by_run: dict[str, int] = {}
    voided_by_run: dict[str, int] = {}
    spend_event_count = 0
    void_event_count = 0

    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("goal_id") or goal_id) != goal_id:
            continue
        generated_at = _parse_timestamp(run.get("generated_at"))
        if generated_at is None or generated_at < window_start or generated_at > current_time:
            continue
        event = load_quota_event_from_run(run)
        if not event:
            continue
        event_type = str(event.get("event_type") or "")
        slots = max(0, _int_number(event.get("slots"), default=0))
        if slots <= 0:
            continue
        if event_type == QUOTA_SLOT_SPENT_CLASSIFICATION:
            run_key = _quota_event_run_key(run, event)
            if not run_key:
                continue
            spent_by_run[run_key] = spent_by_run.get(run_key, 0) + slots
            spend_event_count += 1
        elif event_type == QUOTA_SLOT_VOIDED_CLASSIFICATION:
            voided_run_generated_at = str(event.get("voided_run_generated_at") or "")
            if not voided_run_generated_at:
                continue
            voided_by_run[voided_run_generated_at] = voided_by_run.get(voided_run_generated_at, 0) + slots
            void_event_count += 1

    spent_slots = 0
    for run_key, slots in spent_by_run.items():
        spent_slots += max(0, slots - voided_by_run.get(run_key, 0))
    payload["spent_slots"] = spent_slots
    payload["spend_source"] = "runtime_events"
    payload["spend_event_count"] = spend_event_count
    if void_event_count:
        payload["void_event_count"] = void_event_count
    return payload


def quota_status(
    goal: dict[str, Any] | None,
    *,
    waiting_on: str | None = None,
    severity: str | None = None,
    lifecycle_phase: Any = None,
    lifecycle_flags: Any = None,
    status: Any = None,
) -> dict[str, Any]:
    payload = goal_quota_config(goal)
    compute = float(payload["compute"])
    spent_slots = int(payload["spent_slots"])
    allowed_slots = int(payload["allowed_slots"])

    if compute <= 0:
        state = "paused"
        reason = "compute quota is 0; automatic agent turns are paused"
    elif severity == "high":
        state = "blocked_health"
        reason = "health or contract blocker must clear before compute is spent"
    elif waiting_on in {"user_or_controller", "controller"}:
        state = "operator_gate"
        reason = "operator gate blocks gated delivery; safe non-gated steering may continue"
        payload["blocked_action_scope"] = "gated_delivery"
        payload["safe_bypass_allowed"] = True
        payload["safe_bypass_policy"] = (
            "Do not execute agent_command, adapter work, write-control, production actions, "
            "or the gated path. A heartbeat may spend one bounded turn on read-only steering, "
            "analysis, documentation, or another priority-stack item that does not depend on this gate."
        )
    elif waiting_on == "external_evidence":
        state = "waiting"
        reason = "external evidence is still pending; do not spend delivery compute yet"
    elif waiting_on == "codex" and _has_focus_wait_marker(lifecycle_phase, lifecycle_flags, status):
        state = "focus_wait"
        reason = FOCUS_WAIT_REASON
        payload["blocked_action_scope"] = "delivery_focus"
        payload["focus_wait"] = True
    elif waiting_on == "codex":
        if allowed_slots > 0 and spent_slots >= allowed_slots:
            state = "throttled"
            reason = f"{compute:g} compute quota spent {spent_slots}/{allowed_slots} slots in this window"
        else:
            state = "eligible"
            reason = f"{compute:g} compute quota; eligible for the next automatic agent turn"
    else:
        state = "waiting"
        reason = "no active Codex-ready work is currently selected"

    payload["state"] = state
    payload["reason"] = reason
    return payload


def _latest_run(goal: dict[str, Any]) -> dict[str, Any]:
    latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
    if latest_runs and isinstance(latest_runs[0], dict):
        return latest_runs[0]
    return {}


def _quota_sort_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
    quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
    state = str(quota.get("state") or "waiting")
    state_index = QUOTA_STATE_ORDER.index(state) if state in QUOTA_STATE_ORDER else len(QUOTA_STATE_ORDER)
    compute = _number(quota.get("compute"), default=DEFAULT_COMPUTE_QUOTA)
    spent_slots = _int_number(quota.get("spent_slots"), default=0)
    return (state_index, -compute, spent_slots, str(item.get("goal_id") or ""))


def _todo_priority_label(item: dict[str, Any]) -> str | None:
    return projection_todo_priority_label(item)


def _todo_priority_rank(item: dict[str, Any]) -> int:
    return projection_todo_priority_rank(item)


def _todo_index_rank(item: dict[str, Any]) -> int:
    return projection_todo_index_rank(item)


def _todo_projection_sort_key(item: dict[str, Any]) -> tuple[int, int]:
    return projection_todo_projection_sort_key(item)


def _same_todo_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_id = str(left.get("todo_id") or "").strip()
    right_id = str(right.get("todo_id") or "").strip()
    if left_id and right_id:
        return left_id == right_id
    return (
        left.get("index") == right.get("index")
        and str(left.get("text") or "").strip() == str(right.get("text") or "").strip()
    )


def _blocked_priority_fallback(
    agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    first_open = (
        agent_todo_summary.get("first_open_items")
        if isinstance(agent_todo_summary.get("first_open_items"), list)
        else []
    )
    first_executable = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    selected = next((item for item in first_executable if isinstance(item, dict)), None)
    if not selected:
        return None

    blocked_items: list[dict[str, Any]] = []
    for item in first_open:
        if not isinstance(item, dict):
            continue
        if _same_todo_identity(item, selected):
            break
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        if item.get("done") is True:
            continue
        status = normalize_todo_status(item.get("status")) or TODO_STATUS_OPEN
        if status == TODO_STATUS_OPEN:
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        blocked_items.append(compact_todo_summary_item(item, text=text))

    if not blocked_items:
        return None
    selected_text = str(selected.get("text") or "").strip()
    selected_item = compact_todo_summary_item(selected, text=selected_text) if selected_text else dict(selected)
    return {
        "schema_version": "blocked_priority_fallback_v0",
        "kind": "blocked_priority_fallback",
        "severity": "warning",
        "notify_user": False,
        "requires_user_action": False,
        "reason": (
            "a higher-priority agent todo is blocked or deferred before the "
            "selected executable fallback"
        ),
        "blocked_items": blocked_items[:3],
        "selected_executable": selected_item,
        "recommended_action": (
            "Keep the blocked core todo visible in status while selecting fallback; "
            "continue the fallback only if it still matches the latest user priority."
        ),
    }


def _selected_action_with_capability_gate(
    selected_action: Any,
    *,
    capability_gate: dict[str, Any] | None,
) -> Any:
    if not isinstance(capability_gate, dict) or capability_gate.get("action") != "run":
        return selected_action
    blocked = (
        capability_gate.get("blocked_candidates")
        if isinstance(capability_gate.get("blocked_candidates"), list)
        else []
    )
    if not any(
        isinstance(item, dict)
        and actions_are_projection_aligned(selected_action, item.get("text"))
        for item in blocked
    ):
        return selected_action
    runnable = (
        capability_gate.get("runnable_candidates")
        if isinstance(capability_gate.get("runnable_candidates"), list)
        else []
    )
    for item in runnable:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            return text
    return selected_action


def _compact_handoff_readiness(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {field: value[field] for field in HANDOFF_READINESS_COMPACT_FIELDS if field in value}
    latest_run = (
        value.get("post_handoff_latest_run")
        if isinstance(value.get("post_handoff_latest_run"), dict)
        else {}
    )
    if latest_run:
        compact["post_handoff_latest_run"] = {
            field: latest_run[field]
            for field in POST_HANDOFF_RUN_COMPACT_FIELDS
            if field in latest_run
        }
    recent_runs = (
        value.get("post_handoff_recent_runs")
        if isinstance(value.get("post_handoff_recent_runs"), list)
        else []
    )
    compact_recent_runs: list[dict[str, Any]] = []
    for run in recent_runs:
        if not isinstance(run, dict):
            continue
        compact_run = {
            field: run[field]
            for field in POST_HANDOFF_RUN_COMPACT_FIELDS
            if field in run
        }
        if compact_run:
            compact_recent_runs.append(compact_run)
    if compact_recent_runs:
        compact["post_handoff_recent_runs"] = compact_recent_runs[:3]
    return compact or None


def _compact_autonomous_candidate_context(
    value: Any,
    *,
    goal_id: str | None = None,
    limit: int = 3,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {field: value[field] for field in AUTONOMOUS_CANDIDATE_CONTEXT_FIELDS if field in value}
    items = compact.get("items")
    if isinstance(items, list):
        compact_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if goal_id and str(item.get("goal_id") or "") != goal_id:
                continue
            compact_item = {
                key: item[key]
                for key in ("goal_id", "task_class", "text")
                if item.get(key) is not None
            }
            if compact_item:
                compact_items.append(compact_item)
            if len(compact_items) >= limit:
                break
        if not compact_items:
            return None
        compact["items"] = compact_items
        compact["open_count"] = len(compact_items)
    return compact or None


def _scheduler_hint(
    payload: dict[str, Any], *, include_detail: bool = False,
    codex_app_scheduler_state: dict[str, Any] | None = None, available_capabilities: Any = None, codex_app_current_rrule: Any = None,
    scheduler_execution_context: Mapping[str, Any] | SchedulerExecutionContextResolution | None = None,
) -> dict[str, Any]:
    return build_scheduler_hint(
        payload,
        user_action_required=_user_channel_action_required(payload),
        agent_scope_frontier_actions=[action.value for action in AgentScopeFrontierAction],
        include_detail=include_detail,
        codex_app_scheduler_state=codex_app_scheduler_state,
        available_capabilities=available_capabilities, codex_app_current_rrule=codex_app_current_rrule,
        scheduler_execution_context=scheduler_execution_context,
    )


def _load_codex_app_scheduler_state(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None,
) -> dict[str, Any] | None:
    raw_runtime_root = status_payload.get("runtime_root")
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    if not raw_runtime_root or not safe_agent_id:
        return None
    return load_scheduler_state(
        Path(str(raw_runtime_root)).expanduser(),
        goal_id=goal_id,
        agent_id=safe_agent_id,
        surface=CODEX_APP_SURFACE,
        state_key=CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    )


def _automation_prompt_upgrade(
    goal: dict[str, Any],
    *,
    goal_id: str,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return build_identity_aware_prompt_upgrade(
        goal,
        goal_id=goal_id,
        agent_identity=agent_identity,
    )


def _todo_task_class(item: dict[str, Any]) -> str:
    return projection_todo_item_task_class(item)


def _todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    return projection_todo_item_is_actionable_open(item)


def _todo_item_next_due_at(item: dict[str, Any]) -> datetime | None:
    return projection_todo_item_next_due_at(item)


def _todo_item_expires_at(item: dict[str, Any]) -> datetime | None:
    return projection_todo_item_expires_at(item)


def _todo_item_is_expired_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    return projection_todo_item_is_expired_monitor(item, now=now)


def _todo_item_is_due_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    return projection_todo_item_is_due_monitor(item, now=now)


def _todo_item_missing_monitor_schedule(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    return projection_todo_item_missing_monitor_schedule(item, now=now)


def _todo_summary_claim_scope_agent_id(summary: dict[str, Any]) -> str | None:
    return projection_todo_summary_claim_scope_agent_id(summary)


def _outcome_floor_blocker_already_projected(
    agent_todo_summary: dict[str, Any] | None,
) -> bool:
    if not isinstance(agent_todo_summary, dict):
        return False
    if _open_todo_count(agent_todo_summary) <= 0:
        return False

    executable_items = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    if any(
        isinstance(item, dict) and _todo_item_is_actionable_open(item)
        for item in executable_items
    ):
        return False

    first_open = (
        agent_todo_summary.get("first_open_items")
        if isinstance(agent_todo_summary.get("first_open_items"), list)
        else []
    )
    visible_open = [
        item
        for item in first_open
        if isinstance(item, dict) and _todo_item_is_actionable_open(item)
    ]
    if not visible_open:
        return False
    visible_classes = [_todo_task_class(item) for item in visible_open]
    return (
        TODO_TASK_CLASS_BLOCKER in visible_classes
        and all(task_class != TODO_TASK_CLASS_ADVANCEMENT for task_class in visible_classes)
    )


def _execution_obligation(
    *,
    should_run: bool,
    effective_action: str,
    heartbeat_recommendation: dict[str, Any],
    work_lane_contract: dict[str, Any] | None = None,
    external_evidence_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_execution_obligation(
        should_run=should_run,
        effective_action=effective_action,
        heartbeat_recommendation=heartbeat_recommendation,
        work_lane_contract=work_lane_contract,
        external_evidence_observation=external_evidence_observation,
        successor_replan_mode=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
    )


def build_quota_plan(status_payload: dict[str, Any], *, mode: str = "status") -> dict[str, Any]:
    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    queue_by_goal = {
        str(item.get("goal_id")): item
        for item in queue_items
        if isinstance(item, dict) and item.get("goal_id")
    }
    health_items = [
        item
        for item in queue_items
        if isinstance(item, dict) and not isinstance(item.get("quota"), dict)
    ]

    run_history = (
        status_payload.get("run_history")
        if isinstance(status_payload.get("run_history"), dict)
        else {}
    )
    run_goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    status_goals = status_payload.get("goals") if isinstance(status_payload.get("goals"), list) else []
    status_goal_by_id = {
        str(goal.get("id") or ""): goal
        for goal in status_goals
        if isinstance(goal, dict) and goal.get("id")
    }
    registry_goal_by_id = _registry_goal_by_id(status_payload)
    groups: dict[str, list[dict[str, Any]]] = {state: [] for state in QUOTA_STATE_ORDER}
    groups["unknown"] = []

    for goal in run_goals:
        if not isinstance(goal, dict) or not goal.get("registry_member"):
            continue
        goal_id = str(goal.get("id") or "")
        status_goal = status_goal_by_id.get(goal_id) or registry_goal_by_id.get(goal_id) or {}
        attention = queue_by_goal.get(goal_id, {})
        project_asset = (
            attention.get("project_asset")
            if isinstance(attention.get("project_asset"), dict)
            else {}
        )
        project_asset_quota = (
            project_asset.get("quota")
            if isinstance(project_asset.get("quota"), dict)
            else {}
        )
        latest = _latest_run(goal)
        waiting_on = attention.get("waiting_on") or "none"
        lifecycle_phase = attention.get("lifecycle_phase") or goal.get("lifecycle_phase")
        lifecycle_flags = attention.get("lifecycle_flags") or goal.get("lifecycle_flags")
        status = attention.get("status") or goal.get("status")
        control_plane = (
            compact_control_plane_policy(attention.get("control_plane"))
            or compact_control_plane_policy(project_asset.get("control_plane"))
            or compact_control_plane_policy(goal.get("control_plane"))
        )
        raw_quota = attention.get("quota") if isinstance(attention.get("quota"), dict) else goal.get("quota")
        if project_asset_quota:
            raw_quota_base = raw_quota if isinstance(raw_quota, dict) else {}
            quota = {**raw_quota_base, **project_asset_quota}
        elif isinstance(raw_quota, dict):
            quota = raw_quota
            quota = _quota_with_focus_wait_override(
                quota,
                waiting_on=str(waiting_on or ""),
                lifecycle_phase=lifecycle_phase,
                lifecycle_flags=lifecycle_flags,
                status=status,
            )
        else:
            quota = quota_status(
                goal,
                waiting_on=str(waiting_on or ""),
                severity=str(attention.get("severity") or ""),
                lifecycle_phase=lifecycle_phase,
                lifecycle_flags=lifecycle_flags,
                status=status,
            )
        quota = quota_with_handoff_outcome_floor(
            quota,
            waiting_on=str(waiting_on or ""),
            project_asset=project_asset,
            handoff_readiness=attention.get("handoff_readiness")
            if isinstance(attention.get("handoff_readiness"), dict)
            else None,
        )
        state = str(quota.get("state") or "waiting")
        item: dict[str, Any] = {
            "goal_id": goal_id,
            "status": status,
            "lifecycle_phase": lifecycle_phase,
            "lifecycle_flags": lifecycle_flags,
            "waiting_on": waiting_on,
            "severity": attention.get("severity") or "info",
            "source": attention.get("source") or "run_history",
            "recommended_action": project_asset.get("next_action")
            or attention.get("recommended_action")
            or latest.get("recommended_action"),
            "adapter_kind": goal.get("adapter_kind"),
            "adapter_status": goal.get("adapter_status"),
            "repo": (
                goal.get("repo")
                or goal.get("project")
                or goal.get("root")
                or status_goal.get("repo")
                or status_goal.get("project")
                or status_goal.get("root")
            ),
            "coordination": goal.get("coordination") if isinstance(goal.get("coordination"), dict) else None,
            "explore_graph": goal.get("explore_graph")
            if isinstance(goal.get("explore_graph"), dict)
            else None,
            "spawn_policy": goal.get("spawn_policy") if isinstance(goal.get("spawn_policy"), dict) else None,
            "guards": goal.get("guards") if isinstance(goal.get("guards"), list) else [],
            "next_probe": goal.get("next_probe"),
            "latest_run_generated_at": latest.get("generated_at"),
            "quota": quota,
        }
        workspace_guard_policy = (
            goal.get("workspace_guard_policy")
            if isinstance(goal.get("workspace_guard_policy"), dict)
            else status_goal.get("workspace_guard_policy")
            if isinstance(status_goal.get("workspace_guard_policy"), dict)
            else None
        )
        if workspace_guard_policy:
            item["workspace_guard_policy"] = workspace_guard_policy
        if control_plane:
            item["control_plane"] = control_plane
        if project_asset:
            item["project_asset"] = project_asset
            item["project_asset_source"] = "project_asset"
        else:
            item["project_asset_source"] = "legacy_raw_fallback"
        for optional_field in (
            "operator_question",
            "agent_command",
            "controller_stage",
            "missing_gates",
            "next_handoff_condition",
            "handoff_readiness",
            "user_todos",
            "agent_todos",
            "active_state_next_action",
            "active_state_next_action_entries",
        ):
            if optional_field in attention:
                if optional_field == "handoff_readiness":
                    compact_handoff = _compact_handoff_readiness(attention[optional_field])
                    if compact_handoff:
                        item[optional_field] = compact_handoff
                else:
                    item[optional_field] = attention[optional_field]
        groups.setdefault(state, []).append(item)

    for state_items in groups.values():
        state_items.sort(key=_quota_sort_key)

    ordered_items = [
        item
        for state in QUOTA_STATE_ORDER
        for item in groups.get(state, [])
    ] + groups.get("unknown", [])
    next_automatic_turn = (groups.get("eligible") or [None])[0]
    summary = {
        "registered_goals": len(ordered_items),
        "health_blockers": len(health_items),
        "next_automatic_turn": next_automatic_turn.get("goal_id") if next_automatic_turn else None,
        "states": {state: len(groups.get(state, [])) for state in QUOTA_STATE_ORDER},
    }
    if groups.get("unknown"):
        summary["states"]["unknown"] = len(groups["unknown"])

    return {
        "ok": status_payload.get("ok"),
        "mode": mode,
        "registry": status_payload.get("registry"),
        "runtime_root": status_payload.get("runtime_root"),
        "goal_count": status_payload.get("goal_count"),
        "run_count": status_payload.get("run_count"),
        "summary": summary,
        "next_automatic_turn": next_automatic_turn,
        "groups": groups,
        "health_items": health_items,
    }


def _quota_plan_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    groups = plan.get("groups") if isinstance(plan.get("groups"), dict) else {}
    items: list[dict[str, Any]] = []
    for state_items in groups.values():
        if not isinstance(state_items, list):
            continue
        items.extend(item for item in state_items if isinstance(item, dict))
    return items


def _recent_reward_lessons(status_payload: dict[str, Any], *, goal_id: str) -> list[dict[str, Any]]:
    lessons: list[dict[str, Any]] = []
    for run in _goal_latest_runs(status_payload, goal_id=goal_id):
        reward = run.get("human_reward") if isinstance(run.get("human_reward"), dict) else {}
        lesson = reward.get("lesson") if isinstance(reward.get("lesson"), dict) else {}
        if not lesson:
            continue
        lessons.append(
            {
                "generated_at": run.get("generated_at"),
                "decision": reward.get("decision"),
                "reward": reward.get("reward"),
                "kind": lesson.get("kind"),
                "summary": lesson.get("summary"),
                "avoid": lesson.get("avoid") if isinstance(lesson.get("avoid"), list) else [],
                "prefer": lesson.get("prefer") if isinstance(lesson.get("prefer"), list) else [],
            }
        )
    return lessons


def _reward_lesson_projection_warning(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    recommended_action: str | None,
) -> dict[str, Any] | None:
    action = str(recommended_action or "").strip()
    if not action:
        return None
    action_lower = action.lower()
    action_tokens = _action_scope_tokens_from_text(action)
    matches: list[dict[str, Any]] = []
    for lesson in _recent_reward_lessons(status_payload, goal_id=goal_id):
        for avoid in lesson.get("avoid") or []:
            avoid_text = str(avoid or "").strip()
            if not avoid_text:
                continue
            avoid_tokens = _action_scope_tokens_from_text(avoid_text)
            exact_match = avoid_text.lower() in action_lower
            if not exact_match and not avoid_tokens:
                continue
            token_overlap = sorted(action_tokens & avoid_tokens)
            if not exact_match and len(token_overlap) < min(2, len(avoid_tokens)):
                continue
            matches.append(
                {
                    "generated_at": lesson.get("generated_at"),
                    "decision": lesson.get("decision"),
                    "kind": lesson.get("kind"),
                    "summary": lesson.get("summary"),
                    "avoid": avoid_text,
                    "token_overlap": token_overlap[:5],
                }
            )
    if not matches:
        return None
    return {
        "schema_version": "reward_lesson_projection_warning_v0",
        "source": "run_history.human_reward.lesson",
        "goal_id": goal_id,
        "message": (
            "recommended_action overlaps a recent human_reward lesson avoid rule; "
            "rebase the route or update the affected todo/next action before continuing"
        ),
        "recommended_action": action,
        "match_count": len(matches),
        "matches": matches[:3],
    }


def _registry_goal_by_id(status_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    registry_value = status_payload.get("registry")
    if not registry_value:
        return {}
    registry_path = Path(str(registry_value)).expanduser()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    goals = payload.get("goals") if isinstance(payload, dict) else None
    if not isinstance(goals, list):
        return {}
    return {
        str(goal.get("id") or ""): goal
        for goal in goals
        if isinstance(goal, dict) and goal.get("id")
    }


def _recovery_delivery_allowed(quota: dict[str, Any], *, plan_ok: bool) -> bool:
    return (
        bool(plan_ok)
        and quota.get("safe_bypass_allowed") is True
        and str(quota.get("safe_bypass_kind") or "") == "outcome_floor_recovery"
    )


def _effective_action(
    *,
    normal_delivery_allowed: bool,
    recovery_delivery_allowed: bool,
    self_repair_allowed: bool,
    capability_repair_allowed: bool = False,
    workspace_repair_allowed: bool = False,
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
    if state in {"focus_wait", "waiting"}:
        return "blocked_wait"
    if quota.get("focus_wait"):
        return "blocked_wait"
    return "quota_skip"


def _quota_agent_profile(agent_identity: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict):
        return None
    profile = agent_identity.get("agent_profile")
    return profile if isinstance(profile, dict) else None


def build_quota_should_run(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None = None,
    available_capabilities: Any = None,
    include_scheduler_detail: bool = False, codex_app_current_rrule: Any = None,
    scheduler_execution_context: Mapping[str, Any] | SchedulerExecutionContextResolution | None = None, operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    resolved_scheduler_context = resolve_scheduler_execution_context(
        scheduler_execution_context
    )
    registry_goal = _registry_goal_by_id(status_payload).get(safe_goal_id) or {}
    plan = build_quota_plan(status_payload, mode="should-run")
    item = next((candidate for candidate in _quota_plan_items(plan) if candidate.get("goal_id") == safe_goal_id), None)
    health_items = plan.get("health_items") if isinstance(plan.get("health_items"), list) else []
    health_item = next(
        (
            candidate
            for candidate in health_items
            if isinstance(candidate, dict) and candidate.get("goal_id") == safe_goal_id
        ),
        None,
    )

    if item:
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        state = str(quota.get("state") or "unknown")
        normal_delivery_allowed = bool(plan.get("ok")) and state == "eligible"
        recovery_allowed = _recovery_delivery_allowed(quota, plan_ok=bool(plan.get("ok")))
        reason = str(quota.get("reason") or "quota state is not eligible")
        if not plan.get("ok"):
            reason = "status or contract health is not ok; skip automatic compute"
        project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
        agent_identity = build_quota_agent_identity(item, agent_id=agent_id)
        effective_available_capabilities = _effective_available_capabilities(
            available_capabilities,
            item=item,
            project_asset=project_asset,
        )
        user_todo_summary = select_quota_todo_summary(
            item.get("user_todos"),
            project_asset.get("user_todos") if project_asset else None,
            agent_identity=agent_identity,
            filter_user_gate_blocks_agent=True,
            available_capabilities=effective_available_capabilities,
        )
        agent_todo_summary = select_quota_todo_summary(
            item.get("agent_todos"),
            project_asset.get("agent_todos") if project_asset else None,
            agent_identity=agent_identity,
            available_capabilities=effective_available_capabilities,
        )
        user_todo_source_items = select_quota_todo_source_items(
            item.get("user_todos"),
            project_asset.get("user_todos") if project_asset else None,
        )
        agent_todo_source_items = select_quota_todo_source_items(
            item.get("agent_todos"),
            project_asset.get("agent_todos") if project_asset else None,
        )
        agent_scoped_user_todo_override = _agent_scoped_user_todo_override(
            state=state,
            item=item,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            agent_identity=agent_identity,
        )
        if agent_scoped_user_todo_override:
            state = str(agent_scoped_user_todo_override["to_state"])
            reason = str(agent_scoped_user_todo_override["reason"])
            quota = {
                **quota,
                **agent_scoped_user_todo_override.pop("quota_patch", {}),
                "state": state,
                str(agent_scoped_user_todo_override["kind"]): agent_scoped_user_todo_override,
                "reason": reason,
            }
            item = {**item, **agent_scoped_user_todo_override.pop("item_patch", {})}
            normal_delivery_allowed = bool(plan.get("ok")) and state == "eligible"
            recovery_allowed = _recovery_delivery_allowed(quota, plan_ok=bool(plan.get("ok")))
        outcome_floor_blocker_projected = (
            recovery_allowed
            and _outcome_floor_blocker_already_projected(agent_todo_summary)
        )
        if outcome_floor_blocker_projected:
            quota = {
                **quota,
                "safe_bypass_allowed": False,
                "safe_bypass_kind": None,
                "outcome_floor_blocker_projected": True,
                "reason": (
                    "handoff outcome floor blocker already projected: no executable "
                    "agent todo exists; wait for fresh ranker/cross-domain evidence "
                    "or a new manifest before spending recovery compute"
                ),
            }
            recovery_allowed = False
            reason = str(quota["reason"])
        boundary_agent_id = normalize_todo_claimed_by(
            (agent_identity or {}).get("agent_id")
        )
        reward_memory_experiment_status = _resolve_reward_memory_experiment_from_status(
            status_payload,
            goal_id=safe_goal_id,
            agent_id=boundary_agent_id,
        )
        boundary_registry_value = str(status_payload.get("registry") or "").strip()
        goal_boundary = _goal_boundary(
            registry_goal or item,
            item=item,
            agent_id=boundary_agent_id,
            registry_path=(
                Path(boundary_registry_value) if boundary_registry_value else None
            ),
            operator_inbox_urgency_projector=operator_inbox_urgency_projector, reward_memory_experiment_status=reward_memory_experiment_status,
        )
        workspace_guard = None
        automation_prompt_upgrade = _automation_prompt_upgrade(
            item,
            goal_id=safe_goal_id,
            agent_identity=agent_identity,
        )
        automation_prompt_upgrade_required = bool(
            automation_prompt_upgrade
            and automation_prompt_upgrade.get("blocks_should_run") is True
        )
        blocked_priority_fallback = _blocked_priority_fallback(agent_todo_summary)
        stall_self_repair = build_quota_stall_self_repair_hint(
            item,
            state=state,
            plan_ok=bool(plan.get("ok")),
            health_items=health_items,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            agent_id=normalize_todo_claimed_by((agent_identity or {}).get("agent_id")),
            user_todo_source_items=user_todo_source_items,
            agent_todo_source_items=agent_todo_source_items,
        )
        self_repair_allowed = bool(stall_self_repair and stall_self_repair.get("allowed"))
        normal_delivery_allowed, recovery_allowed, reason = apply_stall_repair_delivery_guard(
            stall_self_repair,
            normal_delivery_allowed=normal_delivery_allowed,
            recovery_allowed=recovery_allowed,
            reason=reason,
        )
        monitor_debt_arbitration = _build_monitor_debt_arbitration(
            status_payload, goal_id=safe_goal_id, agent_id=boundary_agent_id
        )
        work_lane_contract = build_quota_work_lane_contract(
            item,
            status_payload=status_payload,
            goal_id=safe_goal_id,
            agent_id=boundary_agent_id,
            agent_todo_summary=agent_todo_summary,
            monitor_due_item_limit=MONITOR_DUE_ITEM_LIMIT,
            monitor_debt_arbitration=monitor_debt_arbitration,
        )
        task_orchestration_contract, work_lane_contract = apply_task_orchestration_contract(
            fallback_work_lane_contract=work_lane_contract,
            goal_boundary=goal_boundary,
            agent_identity=agent_identity,
            agent_todo_summary=agent_todo_summary,
            raw_agent_todo_summary=(
                item.get("agent_todos")
                if isinstance(item.get("agent_todos"), dict)
                else project_asset.get("agent_todos")
                if isinstance(project_asset.get("agent_todos"), dict)
                else None
            ),
        )
        capability_gate, capability_monitor_contract, capability_monitor_fallback = build_capability_gate_with_monitor_fallback(agent_todo_summary, available_capabilities=effective_available_capabilities, agent_identity=agent_identity, monitor_item_limit=MONITOR_DUE_ITEM_LIMIT)
        if task_orchestration_contract:
            capability_monitor_contract = capability_monitor_fallback = None
        work_lane_contract = capability_monitor_contract or work_lane_contract
        scoped_user_gate_fallback = _scoped_user_gate_fallback(
            user_todo_summary, agent_todo_summary, capability_gate=capability_gate,
            allow_unrelated_gate=bool(quota.get("safe_bypass_allowed")),
            monitor_debt_backoff_active=bool(monitor_debt_arbitration.get("active")),
        )
        work_lane_contract = scoped_user_gate_due_monitor_contract(
            scoped_user_gate_fallback, current_contract=work_lane_contract) or work_lane_contract
        work_lane_contract = lark_inbox_reply_due_work_lane_contract(goal_boundary, current_contract=work_lane_contract)
        inbox_reply_due = work_lane_contract_is_lark_inbox_reply_due(work_lane_contract)
        work_lane_selected_todo = _selected_todo_projection(
            agent_lane_next_action=None, work_lane_contract=work_lane_contract)
        if inbox_reply_due:
            task_orchestration_contract = capability_gate = capability_monitor_contract = None
            capability_monitor_fallback = scoped_user_gate_fallback = workspace_guard = None
        else:
            workspace_guard = build_agent_workspace_guard(
                item, agent_identity, agent_todo_summary=agent_todo_summary,
                selected_todo=work_lane_selected_todo)
        agent_frontier_id = (
            normalize_todo_claimed_by(agent_identity.get("agent_id"))
            if isinstance(agent_identity, dict)
            else None
        )
        registered_agent_ids = (
            list(agent_identity.get("registered_agents") or [])
            if isinstance(agent_identity, dict)
            else []
        )
        goal_frontier_context = build_goal_frontier_projection_context_from_status(
            goal_id=safe_goal_id,
            agent_id=agent_frontier_id,
            status_payload=status_payload,
            item=item,
            project_asset=project_asset,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
            neutral_replan_ack_classifications=AUTONOMOUS_REPLAN_ACK_NEUTRAL_CLASSIFICATIONS,
            registered_agent_ids=registered_agent_ids,
            goal_status=str(registry_goal.get("status") or ""),
            agent_profile=_quota_agent_profile(agent_identity),
        )
        replan_obligation = goal_frontier_context.get("replan_obligation")
        replan_scope = goal_frontier_context.get("replan_scope") or {}
        goal_frontier_projection = (
            goal_frontier_context.get("goal_frontier_projection")
            if isinstance(goal_frontier_context.get("goal_frontier_projection"), dict)
            else {}
        )
        capability_repair_allowed = False
        workspace_repair_allowed = False
        projection_gap = build_state_projection_gap(item, project_asset)
        projection_gap_repair = build_state_projection_gap_repair_hint(
            projection_gap,
            candidate_should_run=bool(
                normal_delivery_allowed or recovery_allowed or self_repair_allowed
            ),
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
        )
        if projection_gap_repair:
            stall_self_repair = projection_gap_repair
            self_repair_allowed = True
            normal_delivery_allowed = False
            recovery_allowed = False
            reason = str(projection_gap_repair.get("reason") or reason)
        boundary_projection_repair = build_boundary_projection_repair_hint(
            goal_boundary,
            agent_todo_summary,
            candidate_should_run=bool(
                normal_delivery_allowed or recovery_allowed or self_repair_allowed
            ),
            capability_gate=capability_gate, selected_todo=work_lane_selected_todo,
        )
        if boundary_projection_repair:
            stall_self_repair = boundary_projection_repair
            self_repair_allowed = True
            normal_delivery_allowed = False
            recovery_allowed = False
            reason = str(boundary_projection_repair.get("reason") or reason)
        if capability_gate and capability_gate.get("action") != "run" and not capability_monitor_fallback:
            normal_delivery_allowed = False
            recovery_allowed = False
            if capability_gate.get("action") == "repair_bridge":
                capability_repair_allowed = True
                reason = str(capability_gate.get("reason") or "capability bridge repair required")
            else:
                reason = str(capability_gate.get("reason") or "selected todo capability is unavailable")
        if workspace_guard:
            normal_delivery_allowed = False
            recovery_allowed = False
            self_repair_allowed = False
            capability_repair_allowed = False
            workspace_repair_allowed = True
            reason = str(workspace_guard.get("reason") or "agent workspace guard blocks delivery")
        if automation_prompt_upgrade_required:
            normal_delivery_allowed = False
            recovery_allowed = False
            self_repair_allowed = False
            capability_repair_allowed = False
            workspace_repair_allowed = False
            reason = str(
                automation_prompt_upgrade.get("reason")
                or "identity-aware automation prompt upgrade is required"
            )
        should_run = bool(normal_delivery_allowed or recovery_allowed or self_repair_allowed
                          or capability_repair_allowed or workspace_repair_allowed)
        effective_action = _effective_action(
            normal_delivery_allowed=normal_delivery_allowed, recovery_delivery_allowed=recovery_allowed,
            self_repair_allowed=self_repair_allowed, capability_repair_allowed=capability_repair_allowed,
            workspace_repair_allowed=workspace_repair_allowed, stall_self_repair=stall_self_repair,
            state=state, quota=quota,
        )
        replan_decision_allowed = not inbox_reply_due and autonomous_replan_decision_allowed(
            replan_obligation=replan_obligation, plan_ok=bool(plan.get("ok")),
            workspace_blocked=bool(workspace_guard),
            automation_prompt_upgrade_required=automation_prompt_upgrade_required,
            agent_id=agent_frontier_id, registered_agent_ids=registered_agent_ids,
        )
        if replan_decision_allowed:
            normal_delivery_allowed = False
            recovery_allowed = False
            should_run = True
            effective_action = AUTONOMOUS_REPLAN_REQUIRED_MODE
            reason = (
                "autonomous replan obligation is selected before monitor quiet "
                "or agent-scope wait classification"
            )
        terminal_no_followup = goal_frontier_is_terminal_no_followup(projection=goal_frontier_projection)
        if terminal_no_followup and not inbox_reply_due:
            quota = {**quota, "state": "terminal_no_followup", "reason": (
                "derived terminal no-follow-up is confirmed by complete todo sources and an empty frontier")}
            state = "terminal_no_followup"
            normal_delivery_allowed = recovery_allowed = self_repair_allowed = False
            capability_repair_allowed = workspace_repair_allowed = should_run = False
            effective_action = "terminal_no_followup"
            reason = ("validated closure evidence derives terminal no-follow-up from complete todo sources "
                      "and an empty frontier; stop recurring automation until an explicit resume")
        if automation_prompt_upgrade_required and not terminal_no_followup:
            should_run = False
            effective_action = "automation_prompt_upgrade_required"
        elif inbox_reply_due:
            should_run, normal_delivery_allowed = True, True
            recovery_allowed = self_repair_allowed = capability_repair_allowed = workspace_repair_allowed = False
            effective_action, reason = "lark_inbox_reply_due", (
                "a direct Lark question, bot mention, or verified reply to the bot "
                "is pending reply"
            )
        effective_action, reason = task_orchestration_effective_action(
            task_orchestration_contract,
            should_run=should_run,
            normal_delivery_allowed=normal_delivery_allowed,
            effective_action=effective_action,
            reason=reason,
        )
        recommendation_item = {**item, "quota": quota}
        heartbeat_recommendation = build_heartbeat_recommendation(
            recommendation_item,
            goal_id=safe_goal_id,
            state=state,
            should_run=should_run,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
            stall_self_repair=stall_self_repair,
            replan_obligation=replan_obligation,
            select_replan_obligation=False,
            monitor_due_item_limit=MONITOR_DUE_ITEM_LIMIT,
        )
        if capability_gate and not capability_monitor_fallback and capability_gate.get("action") == "repair_bridge":
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "repair_capability_bridge",
                "notify": "DONT_NOTIFY",
                "reason": capability_gate.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": (
                    "append exactly one quota spend only after a validated bridge "
                    "repair, todo rewrite, or compact blocker writeback"
                ),
            }
        elif capability_gate and not capability_monitor_fallback and capability_gate.get("action") == "ask_owner":
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "ask_owner_for_capability",
                "notify": "NOTIFY",
                "reason": capability_gate.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": "do not append quota spend while asking for missing capability",
            }
        elif capability_gate and not capability_monitor_fallback and capability_gate.get("action") == "skip":
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "capability_skip",
                "notify": "DONT_NOTIFY",
                "reason": capability_gate.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": "do not append quota spend while all executable todos lack current capabilities",
            }
        if workspace_guard:
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "repair_agent_workspace",
                "notify": "DONT_NOTIFY",
                "reason": workspace_guard.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": (
                    "do not append quota spend for workspace relocation; rerun quota "
                    "from the independent worktree before delivery"
                ),
            }
        if automation_prompt_upgrade_required:
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "automation_prompt_upgrade",
                "notify": "DONT_NOTIFY",
                "reason": automation_prompt_upgrade.get("reason")
                or heartbeat_recommendation.get("reason"),
                "spend_policy": (
                    "do not append quota spend for stale/unscoped automation; "
                    "rerun quota should-run from an identity-scoped prompt"
                ),
            }
        if blocked_priority_fallback and should_run:
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "blocked_priority_fallback": blocked_priority_fallback,
            }
            if blocked_priority_fallback.get("notify_user") is True:
                heartbeat_recommendation = {
                    **heartbeat_recommendation,
                    "notify": "NOTIFY",
                    "reason": blocked_priority_fallback.get("reason")
                    or heartbeat_recommendation.get("reason"),
                }
        external_evidence_observation = build_external_evidence_observation_obligation(
            item,
            state=state,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
        )
        external_evidence_observation_recent = None
        if external_evidence_observation:
            external_evidence_observation_recent = _recent_external_monitor_observation_unchanged(
                status_payload,
                goal_id=safe_goal_id,
                agent_id=normalize_todo_claimed_by(agent_identity.get("agent_id"))
                if isinstance(agent_identity, dict)
                else None,
            )
            if external_evidence_observation_recent:
                external_evidence_observation = None
            elif external_evidence_observation.get("poll_window_status") == "before_next_due":
                external_evidence_observation = None
        ready_deferred_resume_candidates: list[dict[str, Any]] = []
        if (
            isinstance(agent_identity, dict)
            and isinstance(agent_todo_summary, dict)
        ):
            ready_deferred_resume_candidates = _agent_scope_deferred_resume_candidates(
                agent_todo_summary,
                agent_id=normalize_todo_claimed_by(agent_identity.get("agent_id")),
            )
        if external_evidence_observation and not workspace_guard and not inbox_reply_due:
            normal_delivery_allowed = False
            should_run = True
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "external_evidence_observe_or_blocker",
                "notify": "DONT_NOTIFY",
                "reason": (
                    "waiting external evidence requires a read-only observation "
                    "or compact blocker before quiet no-op"
                ),
                "spend_policy": external_evidence_observation.get("spend_policy")
                or heartbeat_recommendation.get("spend_policy"),
            }
            effective_action = "external_evidence_observe"
            reason = "external evidence monitor requires read-only observation before quiet no-op"
        monitor_quiet_skip = (
            not replan_decision_allowed
            and normal_delivery_allowed
            and not recovery_allowed
            and not self_repair_allowed
            and isinstance(work_lane_contract, dict)
            and work_lane_contract.get("obligation") == "quiet_until_material_monitor_transition"
            and work_lane_contract.get("must_attempt_work") is False
            and heartbeat_recommendation.get("recommended_mode") == "monitor_quiet_until_material_transition"
            and heartbeat_recommendation.get("notify") == "DONT_NOTIFY"
            and not ready_deferred_resume_candidates
        )
        if monitor_quiet_skip:
            normal_delivery_allowed = False
            should_run = False
            effective_action = "monitor_quiet_skip"
            reason = str(
                heartbeat_recommendation.get("reason")
                or "monitor-only polling has no material transition; skip delivery compute"
            )
        selected_recommended_action = selected_recommended_action_from_work_lane(
            item,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
        )
        selected_recommended_action = task_selected_recommended_action(
            task_orchestration_contract,
            selected_recommended_action,
        )
        if capability_monitor_fallback and isinstance(work_lane_contract, dict) and work_lane_contract.get("action"):
            selected_recommended_action = work_lane_contract["action"]
        due_monitor_attempt = work_lane_contract_is_due_monitor_attempt(work_lane_contract)
        if capability_gate and not due_monitor_attempt and not capability_monitor_fallback:
            if capability_gate.get("action") in {"repair_bridge", "ask_owner", "skip"}:
                selected_recommended_action = (
                    capability_gate.get("owner_action")
                    or capability_gate.get("reason")
                    or selected_recommended_action
                )
            else:
                selected_recommended_action = _selected_action_with_capability_gate(
                    selected_recommended_action,
                    capability_gate=capability_gate,
                )
        if workspace_guard:
            selected_recommended_action = (
                workspace_guard.get("required_action")
                or workspace_guard.get("reason")
                or selected_recommended_action
            )
        if automation_prompt_upgrade_required:
            selected_recommended_action = (
                automation_prompt_upgrade.get("recommended_action")
                or automation_prompt_upgrade.get("reason")
                or selected_recommended_action
            )
        if replan_decision_allowed:
            selected_recommended_action = (
                str(replan_obligation.get("recommended_action") or "").strip()
                or str(replan_obligation.get("stop_condition") or "").strip()
                or "Run one bounded autonomous replan slice and write back the selected todo/frontier changes."
            )
        agent_lane_next_action = None
        if not due_monitor_attempt and not inbox_reply_due and not task_orchestration_contract and not capability_monitor_fallback:
            agent_lane_next_action = build_agent_lane_next_action(
                agent_identity=agent_identity,
                agent_todo_summary=agent_todo_summary,
                capability_gate=capability_gate,
                scoped_user_gate_fallback=scoped_user_gate_fallback,
                active_next_action=(
                    item.get("active_state_next_action")
                    or (
                        item.get("project_asset", {}).get("next_action")
                        if isinstance(item.get("project_asset"), dict)
                        else None
                    )
                ),
            )
            if not replan_decision_allowed:
                selected_recommended_action = selected_action_with_agent_lane(
                    selected_recommended_action,
                    agent_lane_next_action=agent_lane_next_action,
                )
        agent_scope_frontier = None
        if not replan_decision_allowed:
            agent_scope_frontier = _agent_scope_no_candidate_frontier(
                agent_identity=agent_identity,
                agent_todo_summary=agent_todo_summary,
                agent_lane_next_action=agent_lane_next_action,
                work_lane_contract=work_lane_contract,
                candidate_should_run=bool(
                    (should_run and normal_delivery_allowed)
                    or ready_deferred_resume_candidates
                ),
            )
        if (
            isinstance(agent_scope_frontier, dict)
            and agent_scope_frontier.get("priority_preemption") is True
        ):
            agent_lane_next_action = None
        agent_lane_frontier_hint = None
        if not replan_decision_allowed:
            agent_lane_frontier_hint = _agent_lane_frontier_hint(
                goal_id=safe_goal_id,
                agent_identity=agent_identity,
                agent_todo_summary=agent_todo_summary,
                agent_lane_next_action=agent_lane_next_action,
                agent_scope_frontier=agent_scope_frontier,
                work_lane_contract=work_lane_contract,
            )
        if agent_scope_frontier and agent_lane_frontier_hint:
            agent_scope_frontier["frontier_hint"] = agent_lane_frontier_hint
        if agent_scope_frontier and not replan_decision_allowed:
            frontier_action = str(agent_scope_frontier.get("effective_action") or "")
            successor_replan_required = (
                frontier_action == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value
            )
            normal_delivery_allowed = False
            should_run = bool(successor_replan_required)
            effective_action = frontier_action
            reason = str(agent_scope_frontier.get("reason") or reason)
            selected_recommended_action = (
                agent_scope_frontier.get("recommended_action")
                or selected_recommended_action
            )
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": effective_action,
                "notify": "DONT_NOTIFY",
                "reason": reason,
                "spend_policy": agent_scope_frontier.get("spend_policy")
                or "do not append quota spend while the current agent has no in-scope runnable candidate",
            }
        state_action_projection_warning = build_state_action_projection_warning(
            item,
            agent_todo_summary=agent_todo_summary,
            selected_action=selected_recommended_action,
            work_lane_contract=work_lane_contract,
        )
        active_state_next_action_text = _protocol_action_text(
            item.get("active_state_next_action")
            or project_asset.get("active_state_next_action")
            or project_asset.get("next_action"),
            limit=320,
        )
        latest_run_recommended_action_text = _protocol_action_text(
            item.get("latest_run_recommended_action")
            or project_asset.get("latest_run_recommended_action"),
            limit=320,
        )
        next_action_warning = next_action_projection_warning(
            active_state_next_action=active_state_next_action_text,
            latest_run_recommended_action=latest_run_recommended_action_text,
            agent_lane_next_action=agent_lane_next_action,
        )
        goal_route_hint = build_goal_route_hint(
            agent_identity=agent_identity,
            agent_todo_summary=agent_todo_summary,
            agent_lane_next_action=agent_lane_next_action,
            agent_scope_frontier=agent_scope_frontier,
            agent_lane_frontier_hint=agent_lane_frontier_hint,
            active_state_next_action=active_state_next_action_text,
            latest_run_recommended_action=latest_run_recommended_action_text,
            selected_recommended_action=selected_recommended_action,
        )
        goal_route_hint = task_goal_route_hint(goal_route_hint, task_orchestration_contract)
        agent_scope_action = _agent_scope_frontier_action(effective_action)
        payload_work_lane_contract = _payload_work_lane_contract(
            work_lane_contract,
            effective_action=effective_action,
            recovery_allowed=recovery_allowed,
            agent_scope_frontier=agent_scope_frontier,
        )
        payload = {
            "ok": bool(plan.get("ok")) or self_repair_allowed or capability_repair_allowed or workspace_repair_allowed,
            "status_health_ok": bool(plan.get("ok")),
            "mode": "should-run",
            "goal_id": safe_goal_id,
            "decision": (
                AUTONOMOUS_REPLAN_REQUIRED_MODE
                if replan_decision_allowed
                else "run"
                if normal_delivery_allowed
                else "observe"
                if external_evidence_observation
                else "safe_bypass_recovery"
                if recovery_allowed
                else "self_repair"
                if self_repair_allowed
                else "repair_bridge"
                if capability_repair_allowed
                else "workspace_guard"
                if workspace_repair_allowed
                else "automation_prompt_upgrade"
                if automation_prompt_upgrade_required
                else agent_scope_action.value
                if agent_scope_action is not None
                else "skip"
            ),
            "should_run": should_run,
            "normal_delivery_allowed": normal_delivery_allowed,
            "recovery_delivery_allowed": recovery_allowed,
            "self_repair_allowed": self_repair_allowed,
            "capability_repair_allowed": capability_repair_allowed,
            "workspace_repair_allowed": workspace_repair_allowed,
            "effective_action": effective_action,
            "actionable_by_codex": bool(
                should_run
                or recovery_allowed
                or external_evidence_observation
                or capability_repair_allowed
                or workspace_repair_allowed
            ),
            "reason": (
                str(stall_self_repair.get("reason"))
                if self_repair_allowed and isinstance(stall_self_repair, dict)
                else reason
            ),
            "quota": quota,
            "state": state,
            "blocked_action_scope": (
                boundary_projection_repair.get("blocked_action_scope")
                if boundary_projection_repair
                else stall_repair_blocked_action_scope(stall_self_repair)
                or quota.get("blocked_action_scope")
            ),
            "safe_bypass_allowed": bool(quota.get("safe_bypass_allowed")),
            "safe_bypass_kind": quota.get("safe_bypass_kind"),
            "safe_bypass_policy": quota.get("safe_bypass_policy"),
            "waiting_on": item.get("waiting_on"),
            "status": item.get("status"),
            "lifecycle_phase": item.get("lifecycle_phase"),
            "lifecycle_flags": item.get("lifecycle_flags"),
            "source": item.get("source"),
            "project_asset_source": item.get("project_asset_source"),
            "recommended_action": selected_recommended_action,
            "active_state_next_action": active_state_next_action_text or None,
            "latest_run_recommended_action": latest_run_recommended_action_text or None,
            "execution_profile": _quota_execution_profile_summary(
                project_asset.get("execution_profile")
            )
            if project_asset
            else None,
            "long_task_cadence_hint": (
                project_asset.get("long_task_cadence_hint")
                if project_asset and isinstance(project_asset.get("long_task_cadence_hint"), dict)
                else (
                    item.get("long_task_cadence_hint")
                    if isinstance(item.get("long_task_cadence_hint"), dict)
                    else None
                )
            ),
            "handoff_readiness": item.get("handoff_readiness"),
            "heartbeat_recommendation": heartbeat_recommendation,
            "execution_obligation": _execution_obligation(
                should_run=should_run,
                effective_action=effective_action,
                heartbeat_recommendation=heartbeat_recommendation,
                work_lane_contract=payload_work_lane_contract,
                external_evidence_observation=external_evidence_observation,
            ),
            "goal_boundary": goal_boundary,
            "goal_frontier_projection": goal_frontier_projection,
            "plan_summary": plan.get("summary"),
            "todo_write_hint": build_todo_write_hint(safe_goal_id),
        }
        payload = attach_task_orchestration_payload(payload, task_orchestration_contract)
        for key in ("autonomous_replan_decision", "vision_continuation_audit",
                    "vision_wait_state"):
            if isinstance(value := goal_frontier_projection.get(key), dict):
                payload[key] = value
        if replan_scope.get("required"):
            payload["autonomous_replan_scope"] = replan_scope
        if agent_identity:
            payload["agent_identity"] = agent_identity
        if agent_lane_next_action:
            payload["agent_lane_next_action"] = agent_lane_next_action
        selected_todo_projection = _selected_todo_projection(
            agent_lane_next_action=agent_lane_next_action,
            work_lane_contract=payload_work_lane_contract,
            agent_scope_frontier=agent_scope_frontier,
        )
        if selected_todo_projection:
            payload["selected_todo"] = selected_todo_projection
        if agent_lane_frontier_hint:
            payload["agent_lane_frontier_hint"] = agent_lane_frontier_hint
        if goal_route_hint:
            payload["goal_route_hint"] = goal_route_hint
        if agent_scope_frontier:
            payload["agent_scope_frontier"] = agent_scope_frontier
        if workspace_guard:
            payload["workspace_guard"] = workspace_guard
        if automation_prompt_upgrade:
            payload["automation_prompt_upgrade"] = automation_prompt_upgrade
        if agent_scoped_user_todo_override:
            payload[str(agent_scoped_user_todo_override["kind"])] = agent_scoped_user_todo_override
        if payload_work_lane_contract:
            payload["work_lane_contract"] = payload_work_lane_contract
        if monitor_debt_arbitration.get("active"):
            payload["monitor_debt_arbitration"] = monitor_debt_arbitration
        if capability_gate:
            payload["capability_gate"] = capability_gate
            if capability_gate.get("owner_missing"):
                payload["notify_user_on_capability_gate"] = True
        if capability_monitor_fallback:
            payload["capability_monitor_fallback"] = capability_monitor_fallback
        if external_evidence_observation:
            payload["external_evidence_observation"] = external_evidence_observation
        if external_evidence_observation_recent:
            payload["external_evidence_observation_recent"] = external_evidence_observation_recent
        control_plane = compact_control_plane_policy(item.get("control_plane"))
        if control_plane:
            payload["control_plane"] = control_plane
        if stall_self_repair:
            payload["stall_self_repair"] = stall_self_repair
            payload.update(stall_repair_payload(stall_self_repair))
        if projection_gap:
            payload["state_projection_gap"] = projection_gap
        if boundary_projection_repair:
            payload["boundary_projection_gap"] = boundary_projection_repair
        if item.get("operator_question"):
            payload["operator_question"] = item.get("operator_question")
        if item.get("missing_gates"):
            payload["missing_gates"] = item.get("missing_gates")
        if user_todo_summary:
            payload["user_todo_summary"] = compact_quota_todo_summary_for_payload(user_todo_summary)
            repeat_open_todo_notification = (
                heartbeat_recommendation.get("repeat_notification_required") is True
            )
            user_gate_todo_open = _has_open_user_gate_todo(user_todo_summary)
            if user_gate_todo_open:
                payload["notify_user_on_gate"] = True
                payload["open_todo_notify_reason"] = _user_gate_todo_notify_reason(
                    user_todo_summary
                )
                payload["open_todo_notification_policy"] = "repeat_until_resolved"
            elif _should_notify_user_on_open_todo(
                state=state,
                waiting_on=str(item.get("waiting_on") or ""),
                user_todo_summary=user_todo_summary,
            ) or repeat_open_todo_notification:
                payload["notify_user_on_open_todo"] = True
                payload["open_todo_notify_reason"] = open_todo_notify_reason(
                    state=state,
                    waiting_on=str(item.get("waiting_on") or ""),
                )
                if repeat_open_todo_notification:
                    payload["open_todo_notify_reason"] = (
                        heartbeat_recommendation.get("reason")
                        or "no-work polling should ask the current open user todo"
                    )
                    payload["open_todo_notification_policy"] = "repeat_until_resolved"
        if scoped_user_gate_fallback and not replan_decision_allowed:
            payload["scoped_user_gate_fallback"] = scoped_user_gate_fallback
            payload["should_run"] = True
            if payload.get("decision") == "skip":
                payload["decision"] = "safe_bypass_user_gate_fallback"
            if payload.get("effective_action") in {"skip", "monitor_quiet_skip", None}:
                payload["effective_action"] = "scoped_user_gate_fallback"
            execution_obligation_payload = (
                dict(payload.get("execution_obligation"))
                if isinstance(payload.get("execution_obligation"), dict)
                else {}
            )
            execution_obligation_payload.update(
                {
                    "must_attempt_work": True,
                    "kind": "scoped_user_gate_fallback",
                    "minimum": "one_non_gated_fallback_segment_after_user_gate_notice",
                    "delivery_allowed": True,
                    "notify_is_execution_gate": False,
                    "contract": "scoped_user_gate_fallback",
                    "contract_obligation": scoped_user_gate_fallback.get(
                        "recommended_action"
                    ),
                    "reason": scoped_user_gate_fallback.get("reason"),
                }
            )
            payload["execution_obligation"] = execution_obligation_payload
            payload["safe_bypass_allowed"] = True
            payload["safe_bypass_kind"] = "scoped_user_gate_fallback"
            payload["safe_bypass_policy"] = (
                "The user gate blocks only the matched agent action scope. Surface "
                "that gate, then advance the selected non-gated fallback; spend only "
                "after validated writeback."
            )
            payload["actionable_by_codex"] = True
        payload["requires_user_action"] = bool(
            state == "operator_gate"
            or payload.get("notify_user_on_gate") is True
            or payload.get("notify_user_on_open_todo") is True
            or payload.get("notify_user_on_capability_gate") is True
        )
        if agent_todo_summary:
            payload["agent_todo_summary"] = compact_quota_todo_summary_for_payload(agent_todo_summary)
        if blocked_priority_fallback:
            payload["blocked_priority_fallback"] = blocked_priority_fallback
        attention_queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
        backlog_context = _compact_autonomous_candidate_context(
            attention_queue.get("autonomous_backlog_candidates"),
            goal_id=safe_goal_id,
        )
        if backlog_context:
            payload["autonomous_backlog_candidates"] = backlog_context
        monitor_context = _compact_autonomous_candidate_context(
            attention_queue.get("autonomous_monitor_candidates"),
            goal_id=safe_goal_id,
        )
        if monitor_context:
            payload["autonomous_monitor_candidates"] = monitor_context
        projection_warning = (
            item.get("stale_latest_run_warning")
            if isinstance(item.get("stale_latest_run_warning"), dict)
            else project_asset.get("stale_latest_run_warning")
            if isinstance(project_asset.get("stale_latest_run_warning"), dict)
            else None
        )
        if projection_warning:
            payload["stale_latest_run_warning"] = projection_warning
        if state_action_projection_warning:
            payload["state_action_projection_warning"] = state_action_projection_warning
        if next_action_warning:
            payload["next_action_projection_warning"] = next_action_warning
        backlog_warning = (
            item.get("backlog_hygiene_warning")
            if isinstance(item.get("backlog_hygiene_warning"), dict)
            else project_asset.get("backlog_hygiene_warning")
            if isinstance(project_asset.get("backlog_hygiene_warning"), dict)
            else None
        )
        if backlog_warning:
            payload["backlog_hygiene_warning"] = backlog_warning
        archive_warning = (
            item.get("completed_todo_archive_warning")
            if isinstance(item.get("completed_todo_archive_warning"), dict)
            else project_asset.get("completed_todo_archive_warning")
            if isinstance(project_asset.get("completed_todo_archive_warning"), dict)
            else None
        )
        if archive_warning:
            payload["completed_todo_archive_warning"] = archive_warning
        if replan_obligation:
            payload["autonomous_replan_obligation"] = replan_obligation
        dreaming_proposal = (
            item.get("dreaming_proposal")
            if isinstance(item.get("dreaming_proposal"), dict)
            else project_asset.get("dreaming_proposal")
            if isinstance(project_asset.get("dreaming_proposal"), dict)
            else None
        )
        if dreaming_proposal:
            payload["dreaming_proposal"] = dreaming_proposal
        dreaming_lane_badge = (
            item.get("dreaming_lane_badge")
            if isinstance(item.get("dreaming_lane_badge"), dict)
            else project_asset.get("dreaming_lane_badge")
            if isinstance(project_asset.get("dreaming_lane_badge"), dict)
            else None
        )
        if dreaming_lane_badge:
            payload["dreaming_lane_badge"] = dreaming_lane_badge
        interface_budget_cadence = (
            project_asset.get("interface_budget_cadence")
            if isinstance(project_asset.get("interface_budget_cadence"), dict)
            else None
        )
        if interface_budget_cadence:
            payload["interface_budget_cadence"] = interface_budget_cadence
        decision_warning = _decision_freshness_warning(status_payload, goal_id=safe_goal_id)
        if decision_warning:
            payload["decision_freshness_warning"] = decision_warning
        promotion_warning = _promotion_readiness_warning(status_payload)
        if promotion_warning:
            payload["promotion_readiness_warning"] = promotion_warning
        reward_lesson_warning = _reward_lesson_projection_warning(
            status_payload,
            goal_id=safe_goal_id,
            recommended_action=selected_recommended_action,
        )
        if reward_lesson_warning:
            payload["reward_lesson_projection_warning"] = reward_lesson_warning
        gate_prompt = (
            _build_gate_prompt(item, user_todo_summary=user_todo_summary)
            if state == "operator_gate"
            else None
        )
        if gate_prompt:
            payload["gate_prompt"] = gate_prompt
            payload["notify_user_on_gate"] = True
        if item.get("next_handoff_condition"):
            payload["next_handoff_condition"] = item.get("next_handoff_condition")
        if should_run and item.get("agent_command"):
            payload["agent_command"] = item.get("agent_command")
        required_reads = _quota_required_reads(payload)
        if required_reads:
            payload["required_reads"] = required_reads
            if isinstance(payload.get("autonomous_replan_obligation"), dict):
                payload["autonomous_replan_obligation"] = {
                    **payload["autonomous_replan_obligation"],
                    "required_reads": required_reads,
                }
        payload["automation_liveness"] = build_automation_liveness(payload)
        payload["interaction_contract"] = build_interaction_contract(
            payload,
            available_capabilities=effective_available_capabilities, scheduler_execution_context=resolved_scheduler_context,
        )
        payload["scheduler_hint"] = _scheduler_hint(
            payload,
            include_detail=include_scheduler_detail,
            available_capabilities=effective_available_capabilities,
            codex_app_scheduler_state=(
                _load_codex_app_scheduler_state(
                    status_payload,
                    goal_id=safe_goal_id,
                    agent_id=quota_decision_agent_id(payload) or agent_id,
                )
                if resolved_scheduler_context.ok
                and resolved_scheduler_context.context is not None
                and resolved_scheduler_context.context.codex_app_applicable
                else None
            ), codex_app_current_rrule=codex_app_current_rrule,
            scheduler_execution_context=resolved_scheduler_context,
        )
        finalize_user_gate_notification_cooldown(
            payload,
            available_capabilities=effective_available_capabilities, scheduler_execution_context=resolved_scheduler_context,
        )
        payload["protocol_action_packet"] = build_protocol_action_packet(payload)
        return payload

    if health_item:
        return {
            "ok": False,
            "mode": "should-run",
            "goal_id": safe_goal_id,
            "decision": "skip",
            "should_run": False,
            "reason": str(health_item.get("recommended_action") or "health item blocks automatic compute"),
            "state": "blocked_health",
            "waiting_on": health_item.get("waiting_on"),
            "status": health_item.get("status"),
            "source": health_item.get("source"),
            "recommended_action": health_item.get("recommended_action"),
            "plan_summary": plan.get("summary"),
        }

    return {
        "ok": False,
        "mode": "should-run",
        "goal_id": safe_goal_id,
        "decision": "skip",
        "should_run": False,
        "reason": "goal is not present in the registered quota plan",
        "state": "unknown",
        "waiting_on": None,
        "status": "goal_not_found",
        "source": "quota",
        "recommended_action": "run `loopx registry` and connect or sync the goal before spending compute",
        "plan_summary": plan.get("summary"),
    }


def build_quota_slot_preview(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    slots: int = 1,
    agent_id: str | None = None,
    available_capabilities: Any = None, operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    before = build_quota_should_run(
        status_payload,
        goal_id=safe_goal_id,
        agent_id=agent_id,
        available_capabilities=available_capabilities, operator_inbox_urgency_projector=operator_inbox_urgency_projector,
    )
    return build_quota_slot_preview_for_decision(
        status_payload,
        goal_id=safe_goal_id,
        slots=slots,
        agent_id=agent_id,
        before=before,
        after_decision=lambda after_status: build_quota_should_run(
            after_status,
            goal_id=safe_goal_id,
            agent_id=agent_id,
            available_capabilities=available_capabilities, operator_inbox_urgency_projector=operator_inbox_urgency_projector,
        ),
        quota_status_builder=quota_status,
        self_repair_spend_actions=SELF_REPAIR_SPEND_ACTIONS,
    )


def _quota_required_reads(decision: dict[str, Any]) -> list[dict[str, Any]]:
    effective_action = str(decision.get("effective_action") or "")
    replan_required = effective_action in {
        AUTONOMOUS_REPLAN_REQUIRED_MODE,
        AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
    } or isinstance(decision.get("autonomous_replan_obligation"), dict)
    if not replan_required:
        return []
    read = build_agent_scoped_required_read(
        goal_id=str(decision.get("goal_id") or ""),
        agent_id=quota_decision_agent_id(decision),
        reason=(
            "read recent public-safe evidence across this agent lane before "
            "replan; if local evidence is thin, use bounded public-safe search"
        ),
    )
    return [read] if read else []


def record_quota_scheduler_ack(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    execute: bool = False,
    agent_id: str | None = None,
    available_capabilities: Any = None,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    applied_rrule: str | None = None,
    reset_token: str | None = None,
    identity_signature: str | None = None,
    reason_summary: str | None = None, use_current_hint: bool = False, host_match_observed: bool = False,
    scheduler_execution_context: Mapping[str, Any] | SchedulerExecutionContextResolution | None = None, operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    before = build_quota_should_run(
        status_payload,
        goal_id=safe_goal_id,
        agent_id=safe_agent_id,
        available_capabilities=available_capabilities, codex_app_current_rrule=applied_rrule if host_match_observed else None,
        scheduler_execution_context=scheduler_execution_context, operator_inbox_urgency_projector=operator_inbox_urgency_projector,
    )
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    return record_quota_scheduler_ack_for_decision(
        before,
        runtime_root=runtime_root,
        goal_id=safe_goal_id,
        agent_id=safe_agent_id,
        execute=execute,
        surface=str(surface or CODEX_APP_SURFACE).strip() or CODEX_APP_SURFACE,
        state_key=str(state_key or CODEX_APP_STATEFUL_BACKOFF_STATE_KEY).strip(),
        applied_rrule=applied_rrule,
        reset_token=reset_token,
        identity_signature=identity_signature,
        reason_summary=reason_summary, use_current_hint=use_current_hint, host_match_observed=host_match_observed,
    )


def build_quota_slot_spend_event(
    preview: dict[str, Any],
    *,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return _build_quota_slot_spend_event(
        preview,
        self_repair_spend_actions=SELF_REPAIR_SPEND_ACTIONS,
        source=source,
        generated_at=generated_at,
    )


def record_quota_monitor_poll(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    registry_path: Path | None = None,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    agent_id: str | None = None,
    available_capabilities: Any = None,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
    cadence: str | None = None,
    next_due_at: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
    scheduler_execution_context: Mapping[str, Any] | SchedulerExecutionContextResolution | None = None,
    operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    def should_run(current_status: dict[str, Any]) -> dict[str, Any]:
        return build_quota_should_run(current_status,
            goal_id=safe_goal_id,
            agent_id=agent_id,
            available_capabilities=available_capabilities,
            scheduler_execution_context=scheduler_execution_context,
            operator_inbox_urgency_projector=operator_inbox_urgency_projector,
        )
    before = should_run(status_payload)
    return record_quota_monitor_poll_for_decision(
        before,
        status_payload,
        goal_id=safe_goal_id,
        render_markdown=_render_quota_monitor_poll_markdown,
        after_decision=should_run,
        registry_path=registry_path,
        execute=execute,
        source=source,
        reason_summary=reason_summary,
        agent_id=agent_id,
        todo_id=todo_id,
        target_key=target_key,
        result_hash=result_hash,
        material_change=material_change,
        cadence=cadence,
        next_due_at=next_due_at,
        next_agent_todo=next_agent_todo,
        next_user_todo=next_user_todo,
        next_claimed_by=next_claimed_by,
    )


def build_quota_slot_void_preview(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    voided_run_generated_at: str,
    agent_id: str | None = None, operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    before = build_quota_should_run(status_payload, goal_id=safe_goal_id, agent_id=agent_id, operator_inbox_urgency_projector=operator_inbox_urgency_projector)
    return build_quota_slot_void_preview_for_decision(
        status_payload,
        goal_id=safe_goal_id,
        voided_run_generated_at=voided_run_generated_at,
        before=before,
    )


def void_quota_slot(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    voided_run_generated_at: str,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    agent_id: str | None = None, operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    preview = build_quota_slot_void_preview(
        status_payload,
        goal_id=safe_goal_id,
        voided_run_generated_at=voided_run_generated_at,
        agent_id=agent_id, operator_inbox_urgency_projector=operator_inbox_urgency_projector,
    )
    if not preview.get("ok"):
        return preview

    return record_quota_slot_void_from_preview(
        preview,
        status_payload,
        goal_id=safe_goal_id,
        render_markdown=_render_quota_slot_preview_markdown,
        execute=execute,
        source=source,
        reason_summary=reason_summary,
    )


def spend_quota_slot(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    slots: int = 1,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    agent_id: str | None = None,
    available_capabilities: Any = None, operator_inbox_urgency_projector: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    preview = build_quota_slot_preview(
        status_payload,
        goal_id=safe_goal_id,
        slots=slots,
        agent_id=agent_id,
        available_capabilities=available_capabilities, operator_inbox_urgency_projector=operator_inbox_urgency_projector,
    )
    if not preview.get("ok"):
        return preview

    return record_quota_slot_spend_from_preview(
        preview,
        status_payload,
        goal_id=safe_goal_id,
        self_repair_spend_actions=SELF_REPAIR_SPEND_ACTIONS,
        render_markdown=_render_quota_slot_preview_markdown,
        execute=execute,
        source=source,
    )
