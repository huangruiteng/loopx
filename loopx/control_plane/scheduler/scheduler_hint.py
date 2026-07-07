from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Collection
from datetime import datetime
from typing import Any

from ..runtime.time import now_utc
from ..work_items.delivery_outcome import DeliveryOutcome
from .state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    CODEX_APP_SURFACE,
    build_scheduler_state,
    rrule_for_minutes,
)
from .time import parse_scheduler_timestamp


SCHEDULER_HINT_SCHEMA_VERSION = "scheduler_hint_v0"
SCHEDULER_RESET_POLICY_SCHEMA_VERSION = "scheduler_reset_policy_v0"
SCHEDULER_HINT_DETAIL_SCHEMA_VERSION = "scheduler_hint_detail_v0"
CODEX_APP_STATEFUL_BACKOFF_SCHEMA_VERSION = "codex_app_stateful_backoff_v0"
CODEX_APP_SCHEDULER_ACK_HINT_SCHEMA_VERSION = "codex_app_scheduler_ack_hint_v0"
MONITOR_CADENCE_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd])\s*$", re.IGNORECASE)
MONITOR_WAIT_PROGRESSION_MINUTES = [15, 30, 60, 120]


def normalize_scheduler_rrule(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if text.upper().startswith("RRULE:"):
        text = text[6:].strip()
    return text


def scheduler_backoff_packet(
    decision: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scheduler_hint = (
        decision.get("scheduler_hint")
        if isinstance(decision.get("scheduler_hint"), dict)
        else {}
    )
    codex_app = (
        scheduler_hint.get("codex_app")
        if isinstance(scheduler_hint.get("codex_app"), dict)
        else {}
    )
    stateful_backoff = (
        codex_app.get("stateful_backoff")
        if isinstance(codex_app.get("stateful_backoff"), dict)
        else {}
    )
    return scheduler_hint, codex_app, stateful_backoff


def build_codex_app_scheduler_ack_hint(
    *,
    goal_id: Any,
    agent_id: Any,
    applied_rrule: Any,
    reset_token: Any,
    identity_signature: Any,
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
    cli_args = [
        "quota",
        "scheduler-ack",
        "--goal-id",
        safe_goal_id,
        "--agent-id",
        safe_agent_id,
        "--surface",
        safe_surface,
        "--state-key",
        safe_state_key,
        "--applied-rrule",
        safe_rrule,
        "--reset-token",
        safe_reset_token,
        "--identity-signature",
        safe_identity_signature,
        "--execute",
    ]
    return {
        "schema_version": CODEX_APP_SCHEDULER_ACK_HINT_SCHEMA_VERSION,
        "after": "automation_update_rrule_success",
        "command": "quota scheduler-ack",
        "execute": True,
        "cli_args": cli_args,
        "args": {
            "goal_id": safe_goal_id,
            "agent_id": safe_agent_id,
            "surface": safe_surface,
            "state_key": safe_state_key,
            "applied_rrule": safe_rrule,
            "reset_token": safe_reset_token,
            "identity_signature": safe_identity_signature,
        },
        "no_spend": True,
    }


def build_scheduler_ack_plan(
    before: dict[str, Any],
    *,
    agent_id: str | None,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    applied_rrule: str | None = None,
    reset_token: str | None = None,
    identity_signature: str | None = None,
) -> dict[str, Any]:
    safe_agent_id = str(agent_id or "").strip()
    _, codex_app, stateful_backoff = scheduler_backoff_packet(before)
    if not safe_agent_id:
        return {
            "ok": False,
            "reason": "`loopx quota scheduler-ack` requires --agent-id",
        }
    if not stateful_backoff:
        return {
            "ok": False,
            "reason": "current quota decision has no Codex App stateful scheduler packet",
        }
    if str(stateful_backoff.get("state_key") or "") != state_key:
        return {
            "ok": False,
            "reason": "--state-key does not match scheduler_hint.codex_app.stateful_backoff.state_key",
        }
    if reset_token and str(reset_token).strip() != str(stateful_backoff.get("reset_token") or ""):
        return {
            "ok": False,
            "reason": "--reset-token does not match the current scheduler hint",
        }
    if (
        identity_signature
        and str(identity_signature).strip() != str(stateful_backoff.get("identity_signature") or "")
    ):
        return {
            "ok": False,
            "reason": "--identity-signature does not match the current scheduler hint",
        }
    safe_applied_rrule = normalize_scheduler_rrule(applied_rrule)
    if stateful_backoff.get("apply_needed") is not True:
        return {
            "ok": True,
            "already_applied": True,
            "applied_rrule": safe_applied_rrule,
        }
    expected_rrule = normalize_scheduler_rrule(
        codex_app.get("recommended_rrule") or stateful_backoff.get("current_rrule")
    )
    if not safe_applied_rrule:
        return {
            "ok": False,
            "reason": "`loopx quota scheduler-ack` requires --applied-rrule when apply_needed=true",
        }
    if expected_rrule and safe_applied_rrule != expected_rrule:
        return {
            "ok": False,
            "reason": (
                f"quota scheduler-ack applied_rrule {safe_applied_rrule!r} "
                f"does not match expected {expected_rrule!r}"
            ),
        }
    return {
        "ok": True,
        "already_applied": False,
        "applied_rrule": safe_applied_rrule,
        "expected_rrule": expected_rrule,
    }


def _int_number(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _monitor_wait_cadence_progression(payload: dict[str, Any]) -> list[int] | None:
    """Cap monitor quiet backoff so the host does not sleep past monitor due."""

    current_time = now_utc()
    caps: list[int] = []
    for item in _monitor_wait_items(payload):
        expires_at = _parse_monitor_timestamp(item.get("expires_at"))
        if expires_at is not None and expires_at <= current_time:
            continue
        item_caps: list[int] = []
        cadence_minutes = _monitor_cadence_minutes(item.get("cadence"))
        if cadence_minutes is not None:
            item_caps.append(cadence_minutes)
        next_due_at = _parse_monitor_timestamp(item.get("next_due_at"))
        if next_due_at is not None and next_due_at > current_time:
            seconds_until_due = (next_due_at - current_time).total_seconds()
            item_caps.append(max(1, int(math.ceil(seconds_until_due / 60))))
        if item_caps:
            caps.append(min(item_caps))
    if not caps:
        return None
    cap = max(1, min(caps))
    return [min(interval, cap) for interval in MONITOR_WAIT_PROGRESSION_MINUTES]


def build_codex_app_scheduler_ack_event(
    before: dict[str, Any],
    *,
    agent_id: str | None,
    applied_rrule: str,
    classification: str = "quota_scheduler_ack",
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    generated_at: str | None = None,
    reason_summary: str | None = None,
    compact_before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_agent_id = str(agent_id or "").strip()
    if not safe_agent_id:
        raise ValueError("quota scheduler-ack requires a scoped --agent-id")
    _, codex_app, stateful_backoff = scheduler_backoff_packet(before)
    if not stateful_backoff:
        raise ValueError("quota scheduler-ack requires scheduler_hint.codex_app.stateful_backoff")
    if str(stateful_backoff.get("state_key") or "") != state_key:
        raise ValueError("quota scheduler-ack state_key does not match current quota scheduler hint")
    if stateful_backoff.get("apply_needed") is not True:
        raise ValueError("quota scheduler-ack is not needed because the current RRULE is already applied")
    expected_rrule = normalize_scheduler_rrule(
        codex_app.get("recommended_rrule") or stateful_backoff.get("current_rrule")
    )
    safe_applied_rrule = normalize_scheduler_rrule(applied_rrule)
    if not expected_rrule:
        raise ValueError("quota scheduler-ack has no current recommended_rrule to acknowledge")
    if safe_applied_rrule != expected_rrule:
        raise ValueError(
            f"quota scheduler-ack applied_rrule {safe_applied_rrule!r} does not match expected {expected_rrule!r}"
        )
    codex_progression = (
        codex_app.get("example_progression_minutes")
        if isinstance(codex_app.get("example_progression_minutes"), list)
        else []
    )
    progression_minutes = (
        stateful_backoff.get("progression_minutes")
        if isinstance(stateful_backoff.get("progression_minutes"), list)
        else codex_progression
    )
    progression_index = max(0, _int_number(stateful_backoff.get("progression_index"), default=0))
    safe_generated_at = generated_at or ""
    scheduler_state = build_scheduler_state(
        goal_id=before.get("goal_id"),
        agent_id=safe_agent_id,
        surface=surface,
        state_key=state_key,
        reset_token=stateful_backoff.get("reset_token"),
        identity_signature=stateful_backoff.get("identity_signature"),
        progression_index=progression_index,
        progression_minutes=progression_minutes,
        last_applied_rrule=expected_rrule,
        updated_at=safe_generated_at,
        source=classification,
    )
    reason = str(reason_summary or "").strip() or (
        f"acknowledged Codex App scheduler RRULE {expected_rrule}; no quota spend"
    )
    return {
        "generated_at": safe_generated_at,
        "goal_id": before.get("goal_id"),
        "classification": classification,
        "agent_id": safe_agent_id,
        "recommended_action": reason,
        "health_check": "scheduler ack state updated; no quota spend",
        "delivery_outcome": DeliveryOutcome.SURFACE_ONLY.value,
        "scheduler_ack_event": {
            "event_type": classification,
            "surface": surface,
            "state_key": state_key,
            "applied_rrule": expected_rrule,
            "before": compact_before if isinstance(compact_before, dict) else before,
            "scheduler_state": scheduler_state,
        },
    }


def build_scheduler_hint(
    payload: dict[str, Any],
    *,
    user_action_required: bool = False,
    agent_scope_frontier_actions: Collection[str] = (),
    include_detail: bool = False,
    codex_app_scheduler_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project host-runtime cadence/backoff policy from a quota decision.

    This helper is intentionally pure: callers provide the few quota-local
    classification facts it needs, and it returns the public scheduler contract
    without reading files, mutating state, or depending on the full quota module.
    """

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
    interaction_contract = (
        payload.get("interaction_contract")
        if isinstance(payload.get("interaction_contract"), dict)
        else {}
    )
    user_channel = (
        interaction_contract.get("user_channel")
        if isinstance(interaction_contract.get("user_channel"), dict)
        else {}
    )
    effective_action = str(payload.get("effective_action") or "")
    recommended_mode = str(heartbeat_recommendation.get("recommended_mode") or "")
    must_attempt_work = bool(execution_obligation.get("must_attempt_work"))
    user_required = user_action_required or bool(user_channel.get("action_required"))
    automation_action = str(automation_liveness.get("automation_action") or "")
    spend_policy = (
        automation_liveness.get("spend_policy")
        or execution_obligation.get("spend_policy")
        or heartbeat_recommendation.get("spend_policy")
    )
    identity_keys = [
        "goal_id",
        "agent_identity.agent_id",
        "effective_action",
        "heartbeat_recommendation.recommended_mode",
        "interaction_contract.mode",
        "recommended_action",
    ]
    agent_scope_action_set = {str(value) for value in agent_scope_frontier_actions}

    def identity_value(path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

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
        advance_same_identity: bool = True,
    ) -> dict[str, Any]:
        cadence_progression = cadence_progression_override or [
            min(codex_interval * (multiplier**step), codex_max)
            for step in range(3)
        ]
        codex_initial_interval = cadence_progression[0] if cadence_progression else codex_interval
        final_replan_check = {
            "enabled": cli_limit is not None or claude_limit is not None,
            "trigger": "before_unchanged_poll_after_limit",
            "action": "rerun_quota_should_run_once",
            "if_changed": "follow_new_scheduler_hint",
            "if_run_now": "execute_new_quota_contract",
            "if_unchanged": "apply_after_limit_without_spend",
            "spend_policy": "no quota spend for final replan check or loop stop",
        }
        identity_snapshot = {key: identity_value(key) for key in identity_keys}
        codex_rrule = rrule_for_minutes(codex_initial_interval)
        profile_snapshot = {
            "cadence_class": cadence_class,
            "codex_app_initial_interval_minutes": codex_initial_interval,
            "codex_app_initial_rrule": codex_rrule,
            "codex_app_max_interval_minutes": codex_max,
            "codex_app_progression_minutes": cadence_progression,
            "unchanged_poll_backoff_multiplier": multiplier,
            "local_scheduler_unchanged_poll_limit": cli_limit,
            "claude_code_loop_unchanged_poll_limit": claude_limit,
        }
        reset_token_payload = {
            "action": action,
            "identity_snapshot": identity_snapshot,
            "profile_snapshot": profile_snapshot,
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
        reset_policy_detail = {
            "schema_version": SCHEDULER_RESET_POLICY_SCHEMA_VERSION,
            "source": "quota.should-run",
            "reset_to": "profile_initial_interval",
            "profile_action": action,
            "reset_token": reset_token,
            "host_state_key": "scheduler_hint.reset_policy.reset_token",
            "codex_app_initial_interval_minutes": codex_initial_interval,
            "codex_app_initial_rrule": codex_rrule,
            "local_scheduler_initial_interval_minutes": codex_initial_interval,
            "clear_unchanged_poll_state": True,
            "identity_key_count": len(identity_keys),
            "identity_signature": identity_signature,
            "profile_signature": profile_signature,
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
            "recommended_interval_minutes": codex_initial_interval,
            "max_interval_minutes": codex_max,
            "unchanged_poll_backoff_multiplier": multiplier,
            "example_progression_minutes": cadence_progression,
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
        current_index = 0
        state_status = "missing"
        scheduler_state = (
            codex_app_scheduler_state
            if isinstance(codex_app_scheduler_state, dict)
            else {}
        )
        if scheduler_state:
            same_identity = (
                scheduler_state.get("reset_token") == reset_token
                and scheduler_state.get("identity_signature") == identity_signature
            )
            if same_identity:
                state_status = "same_identity"
                try:
                    applied_index = int(scheduler_state.get("progression_index"))
                except (TypeError, ValueError):
                    applied_index = -1
                next_index = applied_index + 1 if advance_same_identity else 0
                current_index = min(max(next_index, 0), len(cadence_progression) - 1)
            else:
                state_status = "reset_required"
        current_interval = cadence_progression[current_index]
        current_rrule = rrule_for_minutes(current_interval)
        last_applied_rrule = str(scheduler_state.get("last_applied_rrule") or "").strip()
        apply_needed = state_status != "same_identity" or last_applied_rrule != current_rrule
        stateful_backoff_detail = {
            "progression_minutes": cadence_progression,
            "current_interval_minutes": current_interval,
            "ack_required_after_apply": apply_needed,
            "persist": "reset_token|identity_signature|progression_index|last_applied_rrule",
            "same_identity_action": (
                "advance_index_after_scheduler_ack"
                if advance_same_identity
                else "keep_initial_interval_while_active_work"
            ),
            "reset_action": "clear_progression_index_apply_initial_rrule",
            "automation_update_scope": "rrule_only_preserve_body_name_status",
        }
        codex_app = {
            "recommended_interval_minutes": current_interval,
            "max_interval_minutes": codex_max,
            "unchanged_poll_backoff_multiplier": multiplier,
            "example_progression_minutes": cadence_progression,
            "apply": (
                "update_automation_cadence_if_possible"
                if apply_needed
                else "none_already_applied"
            ),
            "host_tool": "automation_update",
            "host_action": (
                "update_current_heartbeat_rrule"
                if apply_needed
                else "none"
            ),
            "host_action_contract": (
                "automation_update_rrule_then_quota_scheduler_ack"
                if apply_needed
                else "skip_automation_update_when_apply_needed_false"
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
                "state_status": state_status,
            },
            "no_spend_for_cadence_change": True,
        }
        if apply_needed:
            codex_app["recommended_rrule"] = current_rrule
            if payload.get("goal_id") and identity_value("agent_identity.agent_id"):
                codex_app["ack_hint"] = build_codex_app_scheduler_ack_hint(
                    goal_id=payload.get("goal_id"),
                    agent_id=identity_value("agent_identity.agent_id"),
                    applied_rrule=current_rrule,
                    reset_token=reset_token,
                    identity_signature=identity_signature,
                )
        scheduler_hint = {
            "schema_version": SCHEDULER_HINT_SCHEMA_VERSION,
            "source": "quota.should-run",
            "action": action,
            "cadence_class": cadence_class,
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
        return scheduler_hint

    if (
        recommended_mode in {"mapped_noop_if_unchanged", "post_handoff_observe_if_unchanged"}
        or heartbeat_recommendation.get("stop_if_unchanged")
        or automation_action == "keep_active_noop_if_unchanged"
    ):
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

    if (
        payload.get("should_run") is True
        or must_attempt_work
        or automation_action
        in {
            "execute_bounded_work",
            "repair_automation_prompt_identity",
        }
    ):
        return hint(
            action="run_now",
            cadence_class="active_work",
            reason=(
                "quota projects runnable work or a required repair; keep the active "
                "scheduler cadence until the turn validates or blocks"
            ),
            codex_interval=3,
            codex_max=10,
            cli_limit=None,
            claude_limit=None,
            advance_same_identity=False,
        )

    if user_required or recommended_mode in {"ask_operator_gate", "blocker_push_notify"}:
        return hint(
            action="backoff_waiting_for_user",
            cadence_class="human_gate",
            reason=(
                "user/controller action is the next unlock; after surfacing the "
                "concrete todo or gate, external loops should stop repeating the "
                "same quiet poll"
            ),
            codex_interval=30,
            codex_max=120,
            cli_limit=3,
            claude_limit=3,
        )

    if effective_action in agent_scope_action_set:
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

    if (
        effective_action == "monitor_quiet_skip"
        or recommended_mode == "monitor_quiet_until_material_transition"
    ):
        monitor_progression = _monitor_wait_cadence_progression(payload)
        return hint(
            action="backoff_until_material_transition",
            cadence_class="monitor_wait",
            reason=(
                "monitor-only quiet polls should remain alive but use a slower "
                "cadence until material evidence, a blocker, or replan obligation appears"
            ),
            codex_interval=15,
            codex_max=120,
            cli_limit=3,
            claude_limit=3,
            cadence_progression_override=(
                monitor_progression or MONITOR_WAIT_PROGRESSION_MINUTES
            ),
        )

    if payload.get("should_run") is False:
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

    return hint(
        action="keep_default_cadence",
        cadence_class="default",
        reason="no scheduler backoff condition is projected",
        codex_interval=3,
        codex_max=30,
        cli_limit=None,
        claude_limit=None,
    )
