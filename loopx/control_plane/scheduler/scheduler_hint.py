from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Collection, Mapping
from datetime import datetime, timedelta
from typing import Any

from ..runtime.time import now_utc, utc_isoformat
from . import ack as scheduler_ack
from .arbitration import (
    SchedulerDisposition,
    build_scheduler_arbitration,
)
from .execution_context import (
    SchedulerExecutionContextResolution,
    apply_scheduler_execution_context,
    resolve_scheduler_execution_context,
)
from .state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    CODEX_APP_SURFACE,
    normalize_scheduler_host_update_failures,
    normalize_scheduler_rrule,
    retained_scheduler_host_update_failures,
    rrule_for_minutes,
    scheduler_rrule_interval_minutes,
)
from .state_transition_rules import (
    decide_scheduler_cadence_transition,
    decide_scheduler_host_transition,
)
from .time import parse_scheduler_timestamp


SCHEDULER_HINT_SCHEMA_VERSION = "scheduler_hint_v0"
SCHEDULER_RESET_POLICY_SCHEMA_VERSION = "scheduler_reset_policy_v0"
SCHEDULER_HINT_DETAIL_SCHEMA_VERSION = "scheduler_hint_detail_v0"
CODEX_APP_STATEFUL_BACKOFF_SCHEMA_VERSION = "codex_app_stateful_backoff_v0"
CODEX_APP_SCHEDULER_ACK_HINT_SCHEMA_VERSION = "codex_app_scheduler_ack_hint_v0"
CODEX_APP_SCHEDULER_FAILURE_HINT_SCHEMA_VERSION = "codex_app_scheduler_failure_hint_v0"
USER_GATE_NOTIFICATION_COOLDOWN_SCHEMA_VERSION = "user_gate_notification_cooldown_v0"
MONITOR_CADENCE_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd])\s*$", re.IGNORECASE)
MONITOR_WAIT_PROGRESSION_MINUTES = [15, 30, 60]
CODEX_APP_MAX_INTERVAL_MINUTES = 60
DEFAULT_ACK_CAPABILITIES = {"shell", "filesystem_read", "filesystem_write"}
MONITOR_WAIT_HOST_FLOOR_MINUTES = 15
MONITOR_WAIT_NEAR_WINDOW_LEAD_MINUTES = 60
MONITOR_WAIT_PHASE_RANK = {
    "active_window": 0,
    "near_window": 1,
    "cadence_only": 2,
    "far_window": 3,
}

build_codex_app_scheduler_ack_event = scheduler_ack.build_codex_app_scheduler_ack_event
build_scheduler_ack_plan = scheduler_ack.build_scheduler_ack_plan
scheduler_backoff_packet = scheduler_ack.scheduler_backoff_packet


def _scheduler_progression_interval_elapsed(
    scheduler_state: Mapping[str, Any],
    *,
    current_time: datetime,
) -> bool:
    """Advance only after the applied host cadence has had one real interval."""

    updated_at = parse_scheduler_timestamp(scheduler_state.get("updated_at"))
    applied_interval = scheduler_rrule_interval_minutes(
        scheduler_state.get("last_applied_rrule")
    )
    if updated_at is None or applied_interval is None:
        # Legacy or partial state has no trustworthy settlement clock. Preserve
        # the historical progression behavior instead of pinning it forever.
        return True
    return current_time >= updated_at + timedelta(minutes=applied_interval)


def _user_gate_notification_cooldown(
    *,
    cadence_class: str,
    host_failure_suppressed: bool,
    current_interval_minutes: int,
    effective_host_rrule: str,
    recorded_host_failure: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Bound repeat gate notices when a failed host update leaves a tight poll."""

    if cadence_class != "human_gate" or not host_failure_suppressed:
        return None
    failed_at = parse_scheduler_timestamp((recorded_host_failure or {}).get("failed_at"))
    host_interval = scheduler_rrule_interval_minutes(effective_host_rrule)
    target_interval = max(1, int(current_interval_minutes))
    if failed_at is None or host_interval is None or host_interval >= target_interval:
        return None
    current_time = now_utc()
    elapsed_seconds = max(0.0, (current_time - failed_at).total_seconds())
    cooldown_seconds = target_interval * 60
    window_seconds = host_interval * 60
    cycle_index = int(elapsed_seconds // cooldown_seconds)
    cycle_position = elapsed_seconds - cycle_index * cooldown_seconds
    notification_due = cycle_index >= 1 and cycle_position < window_seconds
    next_reminder_at = failed_at + timedelta(
        seconds=(cycle_index + 1) * cooldown_seconds
    )
    return {
        "schema_version": USER_GATE_NOTIFICATION_COOLDOWN_SCHEMA_VERSION,
        "active": True,
        "notification_due": notification_due,
        "notification_suppressed": not notification_due,
        "policy": "failed_host_update_bounded_reminder_window",
        "cooldown_minutes": target_interval,
        "reminder_window_minutes": host_interval,
        "failed_at": utc_isoformat(failed_at),
        "next_reminder_at": utc_isoformat(next_reminder_at),
        "reason": (
            "the user gate is still pending, but the failed host cadence update "
            "left a tighter poll; suppress duplicate notices outside the bounded "
            "human-gate reminder window"
        ),
    }


def _monitor_rrule_applied_within_stale_tolerance(
    *,
    cadence_class: str,
    last_applied_rrule: str,
    current_rrule: str,
) -> bool:
    if cadence_class != "monitor_wait":
        return False
    applied_minutes = scheduler_rrule_interval_minutes(last_applied_rrule)
    current_minutes = scheduler_rrule_interval_minutes(current_rrule)
    if applied_minutes is None or current_minutes is None:
        return False
    if applied_minutes < current_minutes:
        return False
    return (
        applied_minutes - current_minutes
        <= scheduler_ack.SCHEDULER_ACK_STALE_HINT_TOLERANCE_MINUTES
    )


def build_codex_app_scheduler_ack_hint(
    *,
    goal_id: Any,
    agent_id: Any,
    applied_rrule: Any,
    reset_token: Any,
    identity_signature: Any,
    available_capabilities: Any = None,
    after: str = "automation_update_rrule_success",
    host_match_observed: bool = False,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
) -> dict[str, Any]:
    safe_rrule = normalize_scheduler_rrule(applied_rrule)
    safe_goal_id = str(goal_id or "").strip()
    safe_agent_id = str(agent_id or "").strip()
    safe_surface = str(surface or "").strip()
    safe_state_key = str(state_key or "").strip()
    safe_reset_token = str(reset_token or "").strip()
    safe_identity_signature = str(identity_signature or "").strip()
    safe_available_capabilities: list[str] = []
    if isinstance(available_capabilities, (list, tuple, set)):
        for capability in available_capabilities:
            safe_capability = str(capability or "").strip()
            if (
                safe_capability
                and safe_capability not in DEFAULT_ACK_CAPABILITIES
                and safe_capability not in safe_available_capabilities
            ):
                safe_available_capabilities.append(safe_capability)
    cli_args = [
        "quota",
        "scheduler-ack-current",
        "--goal-id",
        safe_goal_id,
        "--agent-id",
        safe_agent_id,
        "-A",
    ]
    for capability in safe_available_capabilities:
        cli_args.extend(["--available-capability", capability])
    if safe_surface != CODEX_APP_SURFACE:
        cli_args.extend(["--surface", safe_surface])
    if safe_state_key != CODEX_APP_STATEFUL_BACKOFF_STATE_KEY:
        cli_args.extend(["--state-key", safe_state_key])
    cli_args.extend(["--applied-rrule", safe_rrule])
    if host_match_observed:
        cli_args.extend(
            [
                "--host-match-observed",
                "--reset-token",
                safe_reset_token,
                "--identity-signature",
                safe_identity_signature,
            ]
        )
    cli_args.append("--execute")
    args = {
        "goal_id": safe_goal_id,
        "agent_id": safe_agent_id,
        "surface": safe_surface,
        "state_key": safe_state_key,
        "applied_rrule": safe_rrule,
        "reset_token": safe_reset_token,
        "identity_signature": safe_identity_signature,
    }
    if safe_available_capabilities:
        args["available_capabilities"] = safe_available_capabilities
    if host_match_observed:
        args["host_match_observed"] = True
    return {
        "schema_version": CODEX_APP_SCHEDULER_ACK_HINT_SCHEMA_VERSION,
        "after": str(after or "automation_update_rrule_success").strip(),
        "command": "quota scheduler-ack-current",
        "execute": True,
        "cli_args": cli_args,
        "args": args,
        "uses_current_hint": True,
        "no_spend": True,
    }


def build_codex_app_scheduler_failure_hint(
    *,
    goal_id: Any,
    agent_id: Any,
    failed_rrule: Any,
    observed_host_rrule: Any = None,
    available_capabilities: Any = None,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    safe_agent_id = str(agent_id or "").strip()
    safe_rrule = normalize_scheduler_rrule(failed_rrule)
    safe_observed_rrule = normalize_scheduler_rrule(observed_host_rrule)
    safe_capabilities: list[str] = []
    if isinstance(available_capabilities, (list, tuple, set)):
        for capability in available_capabilities:
            safe_capability = str(capability or "").strip()
            if (
                safe_capability
                and safe_capability not in DEFAULT_ACK_CAPABILITIES
                and safe_capability not in safe_capabilities
            ):
                safe_capabilities.append(safe_capability)
    cli_args = [
        "quota",
        "scheduler-fail-current",
        "--goal-id",
        safe_goal_id,
        "--agent-id",
        safe_agent_id,
        "-A",
    ]
    for capability in safe_capabilities:
        cli_args.extend(["--available-capability", capability])
    cli_args.extend(
        [
            "--failed-rrule",
            safe_rrule,
        ]
    )
    if safe_observed_rrule:
        cli_args.extend(["--codex-app-current-rrule", safe_observed_rrule])
    cli_args.append("--execute")
    return {
        "schema_version": CODEX_APP_SCHEDULER_FAILURE_HINT_SCHEMA_VERSION,
        "cli_args": cli_args,
    }


def _parse_monitor_timestamp(value: Any) -> datetime | None:
    return parse_scheduler_timestamp(value)


def _monitor_cadence_minutes(value: Any) -> int | None:
    match = MONITOR_CADENCE_PATTERN.match(str(value or ""))
    if not match:
        return None
    amount = max(1, int(match.group(1)))
    unit = match.group(2).lower()
    if unit == "h":
        return amount * 60
    if unit == "d":
        return amount * 24 * 60
    return amount


def _monitor_wait_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = payload.get("agent_todo_summary")
    if not isinstance(summary, dict):
        return []
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for key in ("current_agent_claimed_monitor_items", "monitor_open_items"):
        values = summary.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            todo_id = str(value.get("todo_id") or "")
            if todo_id and todo_id in seen_ids:
                continue
            if todo_id:
                seen_ids.add(todo_id)
            items.append(value)
    return items


def _monitor_item_identity(item: dict[str, Any]) -> str:
    for key in ("todo_id", "target_key", "action_kind", "title"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return str(item.get("index") or "monitor")


def _minutes_until(value: datetime, current_time: datetime) -> int:
    return max(1, int(math.ceil((value - current_time).total_seconds() / 60)))


def _cap_monitor_progression(*, cap_minutes: int, host_floor_minutes: int) -> list[int]:
    safe_cap = max(1, int(cap_minutes))
    safe_floor = max(1, int(host_floor_minutes))
    # Keep host RRULEs on stable buckets; the exact due horizon still gates routing.
    progression = [
        max(safe_floor, interval)
        for interval in MONITOR_WAIT_PROGRESSION_MINUTES
        if interval <= safe_cap
    ]
    return progression or [safe_floor]


def _monitor_wait_item_plan(
    item: dict[str, Any],
    *,
    current_time: datetime,
) -> dict[str, Any] | None:
    expires_at = _parse_monitor_timestamp(item.get("expires_at"))
    if expires_at is not None and expires_at <= current_time:
        return {
            "phase": "expired",
            "selected_monitor_identity": _monitor_item_identity(item),
        }

    next_due_at = _parse_monitor_timestamp(item.get("next_due_at"))
    last_checked_at = _parse_monitor_timestamp(item.get("last_checked_at"))
    cadence_minutes = _monitor_cadence_minutes(item.get("cadence"))
    host_floor = MONITOR_WAIT_HOST_FLOOR_MINUTES
    phase: str | None = None
    cap_candidates: list[int] = []
    include_next_due_in_reset = False

    if expires_at is not None and last_checked_at is not None and last_checked_at <= current_time:
        phase = "active_window"
        if cadence_minutes is not None:
            cap_candidates.append(max(host_floor, cadence_minutes))
        if next_due_at is not None and next_due_at > current_time:
            cap_candidates.append(max(host_floor, _minutes_until(next_due_at, current_time)))
    elif next_due_at is not None and next_due_at > current_time:
        minutes_until_due = _minutes_until(next_due_at, current_time)
        phase = (
            "near_window"
            if minutes_until_due <= MONITOR_WAIT_NEAR_WINDOW_LEAD_MINUTES
            else "far_window"
        )
        cap_candidates.append(max(host_floor, minutes_until_due))
        include_next_due_in_reset = True
    elif cadence_minutes is not None:
        phase = "cadence_only"
        cap_candidates.append(max(host_floor, cadence_minutes))

    if phase is None or not cap_candidates:
        return None

    cap_minutes = max(host_floor, min(cap_candidates))
    selected_identity = _monitor_item_identity(item)
    reset_profile = {
        "monitor_wait_phase": phase,
        "monitor_wait_host_floor_minutes": host_floor,
        "monitor_wait_selected_identity": selected_identity,
        "monitor_wait_cadence_minutes": cadence_minutes,
        "monitor_wait_window_start_at": (
            next_due_at.isoformat()
            if include_next_due_in_reset and next_due_at is not None
            else None
        ),
        "monitor_wait_window_end_at": expires_at.isoformat() if expires_at is not None else None,
    }
    progression = _cap_monitor_progression(
        cap_minutes=cap_minutes,
        host_floor_minutes=host_floor,
    )
    return {
        "phase": phase,
        "selected_monitor_identity": selected_identity,
        "selected_todo_id": item.get("todo_id"),
        "selected_target_key": item.get("target_key"),
        "host_floor_minutes": host_floor,
        "cap_minutes": cap_minutes,
        "cadence_minutes": cadence_minutes,
        "next_due_at": next_due_at.isoformat() if next_due_at is not None else None,
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
        "last_checked_at": last_checked_at.isoformat() if last_checked_at is not None else None,
        "progression_minutes": progression,
        "reset_profile": reset_profile,
    }


def _monitor_wait_cadence_plan(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Build phase-aware monitor backoff without turning due horizon into identity."""

    current_time = now_utc()
    plans: list[dict[str, Any]] = []
    expired_count = 0
    for item in _monitor_wait_items(payload):
        plan = _monitor_wait_item_plan(item, current_time=current_time)
        if not plan:
            continue
        if plan.get("phase") == "expired":
            expired_count += 1
            continue
        plans.append(plan)

    if not plans:
        if expired_count:
            return {
                "phase": "expired",
                "expired_monitor_count": expired_count,
                "host_floor_minutes": MONITOR_WAIT_HOST_FLOOR_MINUTES,
                "base_progression_minutes": MONITOR_WAIT_PROGRESSION_MINUTES,
                "progression_minutes": None,
                "reset_profile": None,
            }
        return None

    selected = min(
        plans,
        key=lambda plan: (
            int(plan.get("cap_minutes") or 10**9),
            MONITOR_WAIT_PHASE_RANK.get(str(plan.get("phase") or ""), 99),
            str(plan.get("selected_monitor_identity") or ""),
        ),
    )
    return {
        **selected,
        "base_progression_minutes": MONITOR_WAIT_PROGRESSION_MINUTES,
        "candidate_count": len(plans),
        "expired_monitor_count": expired_count,
    }


def build_scheduler_hint(
    payload: dict[str, Any],
    *,
    user_action_required: bool = False,
    agent_scope_frontier_actions: Collection[str] = (),
    include_detail: bool = False,
    codex_app_scheduler_state: dict[str, Any] | None = None,
    available_capabilities: Any = None,
    codex_app_current_rrule: Any = None,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ) = None,
) -> dict[str, Any]:
    """Project host-runtime cadence/backoff policy from a quota decision.

    This helper is intentionally pure: callers provide the few quota-local
    classification facts it needs, and it returns the public scheduler contract
    without reading files, mutating state, or depending on the full quota module.
    """

    execution_context = resolve_scheduler_execution_context(
        scheduler_execution_context
    )
    if not execution_context.ok:
        return {
            "schema_version": SCHEDULER_HINT_SCHEMA_VERSION,
            "source": "quota.should-run",
            "action": "repair_scheduler_execution_context",
            "cadence_class": "control_plane_repair",
            "reason_code": "invalid_scheduler_execution_context",
            "reason": (
                "scheduler ownership is missing or contradictory; repair the "
                "typed execution context before applying cadence"
            ),
            "spend_policy": "no quota spend for scheduler context repair",
            "execution_context": execution_context.projection(),
            "execution_phase": {
                "schema_version": "scheduler_execution_phase_v0",
                "disposition": "contract_error",
                "completed": False,
                "apply_needed": False,
                "ack_needed": False,
                "acknowledged": False,
            },
            "codex_app": {
                "applicability": "blocked_invalid_context",
                "apply": "none",
                "host_action": "none",
                "ack_required": False,
            },
            "unchanged_poll": {
                "local_scheduler": "stop_until_context_repaired",
                "codex_cli_tui": "stop_until_context_repaired",
                "claude_code_loop": "stop_until_context_repaired",
                "final_quota_replan_check_enabled": False,
                "spend_policy": "no quota spend for scheduler context repair",
            },
            "consistency_error": {
                "source": "scheduler_execution_context",
                "errors": list(execution_context.errors),
            },
        }

    def contextualize(result: dict[str, Any]) -> dict[str, Any]:
        return apply_scheduler_execution_context(result, execution_context)

    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    automation_liveness = (
        payload.get("automation_liveness")
        if isinstance(payload.get("automation_liveness"), dict)
        else {}
    )
    spend_policy = (
        automation_liveness.get("spend_policy")
        or execution_obligation.get("spend_policy")
        or heartbeat_recommendation.get("spend_policy")
    )
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    scheduler_ack_capabilities = (
        available_capabilities
        if available_capabilities is not None
        else capability_gate.get("available")
        if isinstance(capability_gate.get("available"), list)
        else []
    )
    base_identity_keys = [
        "goal_id",
        "agent_identity.agent_id",
        "effective_action",
        "heartbeat_recommendation.recommended_mode",
        "interaction_contract.mode",
        "recommended_action",
    ]
    monitor_wait_identity_keys = [
        "goal_id",
        "agent_identity.agent_id",
        "effective_action",
        "heartbeat_recommendation.recommended_mode",
        "interaction_contract.mode",
    ]
    agent_scope_action_set = {str(value) for value in agent_scope_frontier_actions}
    arbitration = build_scheduler_arbitration(
        payload,
        agent_scope_frontier_actions=agent_scope_action_set,
    )

    def identity_value(path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    if arbitration.disposition == SchedulerDisposition.TERMINAL_STOP:
        return contextualize({
            "schema_version": SCHEDULER_HINT_SCHEMA_VERSION,
            "source": "quota.should-run",
            "action": "stop_until_explicit_resume",
            "cadence_class": "terminal_no_followup",
            "reason_code": arbitration.reason_code,
            "reason": (
                "validated closure evidence derives no-follow-up and confirms no "
                "remaining frontier; recurring polling must stop until resume"
            ),
            "spend_policy": "no quota spend for terminal automation shutdown",
            "codex_app": {
                "apply": "pause_or_delete_current_heartbeat_if_possible",
                "host_tool": "automation_update",
                "host_action": "pause_or_delete_current_heartbeat",
                "host_action_required": True,
                "attempt_limit": 1,
                "verify_host_result": True,
                "ack_required": False,
                "resume_trigger": "explicit goal resume or newly projected work",
                "no_spend_for_host_action": True,
            },
            "unchanged_poll": {
                "local_scheduler": "stop",
                "codex_cli_tui": "exit",
                "claude_code_loop": "stop",
                "final_quota_replan_check_enabled": False,
                "spend_policy": "no quota spend for terminal loop stop",
            },
            "unchanged_identity_keys": base_identity_keys,
        })

    def hint(
        *,
        action: str,
        cadence_class: str,
        reason: str,
        codex_interval: int,
        codex_max: int,
        cli_limit: int | None,
        claude_limit: int | None,
        multiplier: int = 2,
        cadence_progression_override: list[int] | None = None,
        reset_profile_snapshot_override: dict[str, Any] | None = None,
        cadence_context_detail: dict[str, Any] | None = None,
        advance_same_identity: bool = True,
    ) -> dict[str, Any]:
        local_cadence_progression = cadence_progression_override or [
            min(codex_interval * (multiplier**step), codex_max)
            for step in range(3)
        ]
        codex_host_max = min(max(1, codex_max), CODEX_APP_MAX_INTERVAL_MINUTES)
        codex_cadence_progression: list[int] = []
        for interval in local_cadence_progression:
            bounded_interval = min(max(1, int(interval)), codex_host_max)
            if (
                not codex_cadence_progression
                or codex_cadence_progression[-1] != bounded_interval
            ):
                codex_cadence_progression.append(bounded_interval)
        codex_initial_interval = (
            codex_cadence_progression[0]
            if codex_cadence_progression
            else min(codex_interval, codex_host_max)
        )
        local_initial_interval = (
            local_cadence_progression[0]
            if local_cadence_progression
            else codex_interval
        )
        final_replan_check = {
            "enabled": cli_limit is not None or claude_limit is not None,
            "trigger": "before_unchanged_poll_after_limit",
            "action": "rerun_quota_should_run_once",
            "if_changed": "follow_new_scheduler_hint",
            "if_run_now": "execute_new_quota_contract",
            "if_unchanged": "apply_after_limit_without_spend",
            "spend_policy": "no quota spend for final replan check or loop stop",
        }
        identity_keys = (
            monitor_wait_identity_keys
            if cadence_class == "monitor_wait"
            else base_identity_keys
        )
        identity_snapshot = {key: identity_value(key) for key in identity_keys}
        codex_rrule = rrule_for_minutes(codex_initial_interval)
        profile_snapshot = {
            "cadence_class": cadence_class,
            "codex_app_initial_interval_minutes": codex_initial_interval,
            "codex_app_initial_rrule": codex_rrule,
            "codex_app_max_interval_minutes": codex_host_max,
            "codex_app_progression_minutes": codex_cadence_progression,
            "unchanged_poll_backoff_multiplier": multiplier,
            "local_scheduler_unchanged_poll_limit": cli_limit,
            "claude_code_loop_unchanged_poll_limit": claude_limit,
        }
        reset_profile_snapshot = reset_profile_snapshot_override or profile_snapshot
        reset_token_payload = {
            "action": action,
            "identity_snapshot": identity_snapshot,
            "profile_snapshot": reset_profile_snapshot,
        }
        reset_token = hashlib.sha256(
            json.dumps(
                reset_token_payload,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:16]
        identity_signature = hashlib.sha256(
            json.dumps(
                identity_snapshot,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:12]
        profile_signature = hashlib.sha256(
            json.dumps(
                profile_snapshot,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:12]
        reset_profile_signature = hashlib.sha256(
            json.dumps(
                reset_profile_snapshot,
                ensure_ascii=True,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:12]
        reset_policy_detail = {
            "schema_version": SCHEDULER_RESET_POLICY_SCHEMA_VERSION,
            "source": "quota.should-run",
            "reset_to": "profile_initial_interval",
            "profile_action": action,
            "reset_token": reset_token,
            "host_state_key": "scheduler_hint.reset_policy.reset_token",
            "codex_app_initial_interval_minutes": codex_initial_interval,
            "codex_app_initial_rrule": codex_rrule,
            "local_scheduler_initial_interval_minutes": local_initial_interval,
            "clear_unchanged_poll_state": True,
            "identity_key_count": len(identity_keys),
            "identity_signature": identity_signature,
            "profile_signature": profile_signature,
            "reset_profile_signature": reset_profile_signature,
            "reset_condition_summary": "token_changed|user_feedback|new_or_reassigned_todo|gate_or_material_transition|active_work_projected",
            "after_reset": "apply_initial_interval_before_backoff",
            "codex_app_tool": "automation_update",
            "codex_app_apply": "call_automation_update_to_restore_initial_rrule_on_token_change",
            "no_spend_for_reset": True,
        }
        reset_policy = {
            "reset_token": reset_token,
            "host_state_key": "scheduler_hint.reset_policy.reset_token",
            "codex_app_initial_interval_minutes": codex_initial_interval,
            "codex_app_initial_rrule": codex_rrule,
            "identity_signature": identity_signature,
        }
        local_scheduler = {
            "recommended_interval_minutes": local_initial_interval,
            "max_interval_minutes": codex_max,
            "unchanged_poll_backoff_multiplier": multiplier,
            "example_progression_minutes": local_cadence_progression,
            "unchanged_poll_limit": cli_limit,
            "after_limit": "stop_tick_loop" if cli_limit is not None else "continue",
            "final_quota_replan_check": final_replan_check,
            "no_spend_for_cadence_change": True,
        }
        codex_cli_tui = {
            "unchanged_poll_limit": cli_limit,
            "after_limit": "exit_goal_loop" if cli_limit is not None else "continue",
            "final_quota_replan_check": final_replan_check,
            "no_spend_for_exit": True,
        }
        claude_code_loop = {
            "unchanged_poll_limit": claude_limit,
            "after_limit": "stop_loop" if claude_limit is not None else "continue",
            "final_quota_replan_check": final_replan_check,
            "no_spend_for_stop": True,
        }
        scheduler_state = (
            codex_app_scheduler_state
            if isinstance(codex_app_scheduler_state, dict)
            else {}
        )
        scheduler_now = now_utc()
        all_host_update_failures = retained_scheduler_host_update_failures(
            normalize_scheduler_host_update_failures(
                scheduler_state.get("host_update_failures"),
                legacy_failure=scheduler_state.get("host_update_failure"),
            ),
            reference_time=scheduler_now,
        )
        cadence_decision = decide_scheduler_cadence_transition(
            codex_cadence_progression,
            scheduler_state=scheduler_state,
            reset_token=reset_token,
            identity_signature=identity_signature,
            advance_same_identity=advance_same_identity,
            applied_interval_elapsed=_scheduler_progression_interval_elapsed(
                scheduler_state,
                current_time=scheduler_now,
            ),
            has_host_update_failures=bool(all_host_update_failures),
        )
        current_index = cadence_decision.current_index
        state_status = cadence_decision.state_status
        current_interval = codex_cadence_progression[current_index]
        current_rrule = rrule_for_minutes(current_interval)
        last_applied_rrule = str(scheduler_state.get("last_applied_rrule") or "").strip()
        observed_host_rrule = normalize_scheduler_rrule(codex_app_current_rrule)
        effective_host_rrule = observed_host_rrule or last_applied_rrule
        host_update_failures = retained_scheduler_host_update_failures(
            all_host_update_failures,
            reference_time=scheduler_now,
            observed_host_rrule=effective_host_rrule,
        )
        recorded_host_failure = next(
            (
                failure
                for failure in reversed(host_update_failures)
                if normalize_scheduler_rrule(failure.get("target_rrule"))
                == current_rrule
            ),
            host_update_failures[-1] if host_update_failures else None,
        )
        current_rrule_already_applied = effective_host_rrule == current_rrule
        if (
            not current_rrule_already_applied
            and not observed_host_rrule
            and state_status == "same_identity"
        ):
            current_rrule_already_applied = _monitor_rrule_applied_within_stale_tolerance(
                cadence_class=cadence_class,
                last_applied_rrule=effective_host_rrule,
                current_rrule=current_rrule,
            )
        host_decision = decide_scheduler_host_transition(
            state_status=state_status,
            observed_host_rrule=observed_host_rrule,
            effective_host_rrule=effective_host_rrule,
            current_rrule=current_rrule,
            current_rrule_already_applied=current_rrule_already_applied,
            scheduler_state_acknowledges_current_rrule=(
                state_status == "same_identity"
                and normalize_scheduler_rrule(last_applied_rrule) == current_rrule
            ),
            all_host_update_failures=all_host_update_failures,
            recorded_host_failure=recorded_host_failure,
        )
        apply_needed = host_decision.apply_needed
        ack_needed = host_decision.ack_needed
        host_match_ack_needed = host_decision.host_match_ack_needed
        host_failure_suppressed = host_decision.host_failure_suppressed
        if host_failure_suppressed:
            state_status = "host_update_failure_suppressed"
        stateful_backoff_detail = {
            "progression_minutes": codex_cadence_progression,
            "current_interval_minutes": current_interval,
            "host_max_interval_minutes": codex_host_max,
            "coarser_wait_fallback": "local_scheduler_only",
            "host_update_failure": "cache_recent_failed_target_and_observed_host_pairs_then_suppress_each_exact_repeat_until_host_changes_ack_or_expiry",
            "ack_required_after_apply": apply_needed,
            "ack_required_from_host_match": host_match_ack_needed,
            "persist": "reset_token|identity_signature|progression_index|last_applied_rrule|host_update_failures|host_update_failure_compat",
            "same_identity_action": (
                "advance_index_after_applied_interval_elapsed"
                if advance_same_identity
                else "keep_initial_interval_while_active_work"
            ),
            "reset_action": "clear_progression_index_apply_initial_rrule",
            "automation_update_scope": "rrule_only_preserve_body_name_status",
        }
        codex_app = {
            "recommended_interval_minutes": current_interval,
            "max_interval_minutes": codex_host_max,
            "unchanged_poll_backoff_multiplier": multiplier,
            "example_progression_minutes": codex_cadence_progression,
            "apply": (
                "update_automation_cadence_if_possible"
                if apply_needed
                else (
                    "none_recorded_host_failure"
                    if host_failure_suppressed
                    else "none_already_applied"
                )
            ),
            "host_tool": "automation_update",
            "host_action": (
                "update_current_heartbeat_rrule"
                if apply_needed
                else (
                    "none_recorded_host_failure"
                    if host_failure_suppressed
                    else
                    "ack_observed_rrule_without_update"
                    if host_match_ack_needed
                    else "none"
                )
            ),
            "host_action_contract": (
                "automation_update_rrule_then_quota_scheduler_ack"
                if apply_needed
                else (
                    "skip_automation_update_for_recorded_host_failure"
                    if host_failure_suppressed
                    else
                    "quota_scheduler_ack_from_matching_host_observation"
                    if host_match_ack_needed
                    else "skip_automation_update_when_apply_needed_false"
                )
            ),
            "rrule_source": (
                "scheduler_hint.codex_app.recommended_rrule"
                if apply_needed
                else None
            ),
            "stateful_backoff": {
                "schema_version": CODEX_APP_STATEFUL_BACKOFF_SCHEMA_VERSION,
                "state_key": CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
                "identity_signature": identity_signature,
                "reset_token": reset_token,
                "progression_index": current_index,
                "current_rrule": current_rrule,
                "apply_needed": apply_needed,
                "ack_needed": ack_needed,
                "state_status": state_status,
            },
            "no_spend_for_cadence_change": True,
        }
        if host_update_failures:
            codex_app["stateful_backoff"]["host_update_failures"] = [
                dict(failure) for failure in host_update_failures
            ]
        if recorded_host_failure:
            codex_app["stateful_backoff"]["host_update_failure"] = dict(
                recorded_host_failure
            )
        if observed_host_rrule:
            codex_app["stateful_backoff"]["host_observation"] = {
                "source": "quota_should_run_host_observation",
                "current_rrule": observed_host_rrule,
                "status": (
                    "matches_recommended"
                    if current_rrule_already_applied
                    else "drift_detected"
                ),
            }
        if apply_needed:
            codex_app["recommended_rrule"] = current_rrule
            if payload.get("goal_id") and identity_value("agent_identity.agent_id"):
                codex_app["failure_hint"] = build_codex_app_scheduler_failure_hint(
                    goal_id=payload.get("goal_id"),
                    agent_id=identity_value("agent_identity.agent_id"),
                    failed_rrule=current_rrule,
                    observed_host_rrule=effective_host_rrule,
                    available_capabilities=scheduler_ack_capabilities,
                )
        if ack_needed:
            if payload.get("goal_id") and identity_value("agent_identity.agent_id"):
                codex_app["ack_hint"] = build_codex_app_scheduler_ack_hint(
                    goal_id=payload.get("goal_id"),
                    agent_id=identity_value("agent_identity.agent_id"),
                    applied_rrule=current_rrule,
                    reset_token=reset_token,
                    identity_signature=identity_signature,
                    available_capabilities=scheduler_ack_capabilities,
                    after=(
                        "automation_update_rrule_success"
                        if apply_needed
                        else "matching_host_rrule_observed"
                    ),
                    # An ACK hint is executable only after either a successful
                    # host update or a matching host readback. Carry that proof
                    # and the originating identity so scheduler-ack-current
                    # cannot recompute an unbound hint and silently no-op.
                    host_match_observed=True,
                )
        scheduler_hint = {
            "schema_version": SCHEDULER_HINT_SCHEMA_VERSION,
            "source": "quota.should-run",
            "action": action,
            "cadence_class": cadence_class,
            "reason_code": arbitration.reason_code,
            "reason": reason,
            "spend_policy": spend_policy,
            "codex_app": codex_app,
            "unchanged_poll": {
                "limits": {
                    "local_scheduler": cli_limit,
                    "codex_cli_tui": cli_limit,
                    "claude_code_loop": claude_limit,
                },
                "after_limits": {
                    "local_scheduler": local_scheduler["after_limit"],
                    "codex_cli_tui": codex_cli_tui["after_limit"],
                    "claude_code_loop": claude_code_loop["after_limit"],
                },
                "final_quota_replan_check_enabled": final_replan_check["enabled"],
                "final_quota_replan_check_action": (
                    final_replan_check["action"] if final_replan_check["enabled"] else None
                ),
                "spend_policy": final_replan_check["spend_policy"],
            },
            "unchanged_identity_keys": identity_keys,
            "reset_policy": reset_policy,
            "detail_ref": {
                "schema_version": SCHEDULER_HINT_DETAIL_SCHEMA_VERSION,
                "omitted_by_default": True,
                "execution_required": False,
                "request": "loopx quota should-run --include-scheduler-detail",
                "hot_path_runtime_fields": [
                    "codex_app",
                    "unchanged_poll",
                    "reset_policy",
                ],
                "contains": [
                    "local_scheduler",
                    "codex_cli_tui",
                    "claude_code_loop",
                    "final_quota_replan_check",
                    "reset_policy_detail",
                    "stateful_backoff_detail",
                ],
            },
        }
        notification_cooldown = _user_gate_notification_cooldown(
            cadence_class=cadence_class,
            host_failure_suppressed=host_failure_suppressed,
            current_interval_minutes=current_interval,
            effective_host_rrule=effective_host_rrule,
            recorded_host_failure=recorded_host_failure,
        )
        if notification_cooldown:
            scheduler_hint["user_gate_notification_cooldown"] = notification_cooldown
        if include_detail:
            scheduler_hint["cold_path_detail"] = {
                "schema_version": SCHEDULER_HINT_DETAIL_SCHEMA_VERSION,
                "source": "quota.should-run",
                "local_scheduler": local_scheduler,
                "codex_cli_tui": codex_cli_tui,
                "claude_code_loop": claude_code_loop,
                "final_quota_replan_check": final_replan_check,
                "reset_policy_detail": reset_policy_detail,
                "stateful_backoff_detail": stateful_backoff_detail,
            }
            if cadence_context_detail:
                scheduler_hint["cold_path_detail"]["cadence_context"] = cadence_context_detail
        return contextualize(scheduler_hint)

    if arbitration.disposition == SchedulerDisposition.CONSISTENCY_REPAIR:
        result = hint(
            action="repair_interaction_contract_projection",
            cadence_class="control_plane_repair",
            reason=(
                "scheduler inputs disagree with the final interaction contract; "
                "repair the projection before applying delivery or wait cadence"
            ),
            codex_interval=3,
            codex_max=10,
            cli_limit=None,
            claude_limit=None,
            advance_same_identity=False,
        )
        result["consistency_error"] = arbitration.consistency_error()
        return result

    if arbitration.disposition == SchedulerDisposition.HUMAN_GATE:
        return hint(
            action="backoff_waiting_for_user",
            cadence_class="human_gate",
            reason=(
                "user/controller action is the next unlock; surface the concrete "
                "gate once, then stop repeating the same quiet poll"
            ),
            codex_interval=30,
            codex_max=120,
            cli_limit=3,
            claude_limit=3,
        )

    if arbitration.disposition == SchedulerDisposition.ACTIVE_WORK:
        return hint(
            action="run_now",
            cadence_class="active_work",
            reason=(
                "the interaction contract requires an agent attempt; keep the active "
                "scheduler cadence until the turn validates or blocks"
            ),
            codex_interval=3,
            codex_max=10,
            cli_limit=None,
            claude_limit=None,
            advance_same_identity=False,
        )

    if arbitration.disposition == SchedulerDisposition.UNCHANGED_WAIT:
        return hint(
            action="backoff_until_fresh_evidence",
            cadence_class="unchanged_noop",
            reason=(
                "the current mapped or post-handoff source is unchanged; do not "
                "keep a tight loop while waiting for fresh evidence or a concrete handoff"
            ),
            codex_interval=60,
            codex_max=240,
            cli_limit=3,
            claude_limit=3,
        )

    if arbitration.disposition == SchedulerDisposition.AGENT_SCOPE_WAIT:
        return hint(
            action="backoff_until_reassigned",
            cadence_class="agent_scope_wait",
            reason=(
                "this registered agent has no in-scope advancement candidate; "
                "agent-to-agent handoffs may change quickly, so stay closer to "
                "the prior scheduler cadence while waiting for handoff owner "
                "progress, reassignment, or a current-agent todo"
            ),
            codex_interval=10,
            codex_max=60,
            cli_limit=3,
            claude_limit=3,
            cadence_progression_override=[10, 20, 30, 60],
        )

    if arbitration.disposition == SchedulerDisposition.MONITOR_WAIT:
        monitor_plan = _monitor_wait_cadence_plan(payload)
        monitor_progression = (
            monitor_plan.get("progression_minutes")
            if isinstance(monitor_plan, dict)
            else None
        )
        monitor_reset_profile = (
            {
                "cadence_class": "monitor_wait",
                "codex_app_initial_interval_minutes": MONITOR_WAIT_HOST_FLOOR_MINUTES,
                "codex_app_initial_rrule": rrule_for_minutes(MONITOR_WAIT_HOST_FLOOR_MINUTES),
                "codex_app_max_interval_minutes": 60,
                "unchanged_poll_backoff_multiplier": 2,
                "local_scheduler_unchanged_poll_limit": 3,
                "claude_code_loop_unchanged_poll_limit": 3,
                **monitor_plan["reset_profile"],
            }
            if isinstance(monitor_plan, dict)
            and isinstance(monitor_plan.get("reset_profile"), dict)
            else None
        )
        return hint(
            action="backoff_until_material_transition",
            cadence_class="monitor_wait",
            reason=(
                "monitor-only quiet polls should remain alive but use a slower "
                "cadence until material evidence, a blocker, or replan obligation appears"
            ),
            codex_interval=15,
            codex_max=60,
            cli_limit=3,
            claude_limit=3,
            cadence_progression_override=(
                monitor_progression or MONITOR_WAIT_PROGRESSION_MINUTES
            ),
            reset_profile_snapshot_override=monitor_reset_profile,
            cadence_context_detail=monitor_plan,
        )

    if arbitration.disposition == SchedulerDisposition.QUIET_WAIT:
        return hint(
            action="backoff_until_state_change",
            cadence_class="quiet_wait",
            reason=(
                "quota blocks delivery and no immediate user/monitor-specific path "
                "is projected; poll at a slower cadence until the status changes"
            ),
            codex_interval=30,
            codex_max=120,
            cli_limit=3,
            claude_limit=3,
        )

    raise AssertionError(f"unhandled scheduler disposition: {arbitration.disposition}")
