from __future__ import annotations

from typing import Any

from ..work_items.delivery_outcome import DeliveryOutcome
from .state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    CODEX_APP_SURFACE,
    build_scheduler_state,
    normalize_scheduler_host_update_failures,
    normalize_scheduler_rrule,
    retained_scheduler_host_update_failures,
    scheduler_rrule_interval_minutes,
)


SCHEDULER_ACK_STALE_HINT_TOLERANCE_MINUTES = 2


def _accepts_stale_monitor_ack_rrule(
    scheduler_hint: dict[str, Any],
    stateful_backoff: dict[str, Any],
    *,
    applied_rrule: str,
    expected_rrule: str,
    reset_token: str | None,
    identity_signature: str | None,
) -> bool:
    if str(scheduler_hint.get("cadence_class") or "") != "monitor_wait":
        return False
    safe_reset_token = str(reset_token or "").strip()
    safe_identity_signature = str(identity_signature or "").strip()
    if not safe_reset_token or not safe_identity_signature:
        return False
    if safe_reset_token != str(stateful_backoff.get("reset_token") or ""):
        return False
    if safe_identity_signature != str(stateful_backoff.get("identity_signature") or ""):
        return False
    applied_minutes = scheduler_rrule_interval_minutes(applied_rrule)
    expected_minutes = scheduler_rrule_interval_minutes(expected_rrule)
    if applied_minutes is None or expected_minutes is None:
        return False
    if applied_minutes < expected_minutes:
        return False
    return (
        applied_minutes - expected_minutes <= SCHEDULER_ACK_STALE_HINT_TOLERANCE_MINUTES
    )


def _scheduler_ack_rrule_acceptance(
    scheduler_hint: dict[str, Any],
    codex_app: dict[str, Any],
    stateful_backoff: dict[str, Any],
    *,
    applied_rrule: str,
    reset_token: str | None,
    identity_signature: str | None,
) -> dict[str, Any]:
    expected_rrule = normalize_scheduler_rrule(
        codex_app.get("recommended_rrule") or stateful_backoff.get("current_rrule")
    )
    if not expected_rrule:
        return {
            "ok": False,
            "reason": "quota scheduler-ack has no current recommended_rrule to acknowledge",
            "expected_rrule": "",
        }
    if applied_rrule == expected_rrule:
        return {
            "ok": True,
            "applied_rrule": applied_rrule,
            "expected_rrule": expected_rrule,
        }
    if _accepts_stale_monitor_ack_rrule(
        scheduler_hint,
        stateful_backoff,
        applied_rrule=applied_rrule,
        expected_rrule=expected_rrule,
        reset_token=reset_token,
        identity_signature=identity_signature,
    ):
        return {
            "ok": True,
            "applied_rrule": applied_rrule,
            "expected_rrule": expected_rrule,
            "stale_hint_accepted": True,
            "stale_hint_tolerance_minutes": SCHEDULER_ACK_STALE_HINT_TOLERANCE_MINUTES,
        }
    return {
        "ok": False,
        "reason": (
            f"quota scheduler-ack applied_rrule {applied_rrule!r} "
            f"does not match expected {expected_rrule!r}"
        ),
        "expected_rrule": expected_rrule,
    }


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
    scheduler_hint, codex_app, stateful_backoff = scheduler_backoff_packet(before)
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
    if reset_token and str(reset_token).strip() != str(
        stateful_backoff.get("reset_token") or ""
    ):
        return {
            "ok": False,
            "reason": "--reset-token does not match the current scheduler hint",
        }
    if identity_signature and str(identity_signature).strip() != str(
        stateful_backoff.get("identity_signature") or ""
    ):
        return {
            "ok": False,
            "reason": "--identity-signature does not match the current scheduler hint",
        }
    safe_applied_rrule = normalize_scheduler_rrule(applied_rrule)
    apply_needed = stateful_backoff.get("apply_needed") is True
    ack_needed = stateful_backoff.get("ack_needed") is True
    if not apply_needed and not ack_needed:
        return {
            "ok": True,
            "already_applied": True,
            "applied_rrule": safe_applied_rrule,
        }
    if not safe_applied_rrule:
        return {
            "ok": False,
            "reason": "`loopx quota scheduler-ack` requires --applied-rrule when an ack is needed",
        }
    acceptance = _scheduler_ack_rrule_acceptance(
        scheduler_hint,
        codex_app,
        stateful_backoff,
        applied_rrule=safe_applied_rrule,
        reset_token=reset_token,
        identity_signature=identity_signature,
    )
    if not acceptance.get("ok"):
        return {
            "ok": False,
            "reason": str(
                acceptance.get("reason") or "scheduler ack RRULE validation failed"
            ),
        }
    result = {
        "ok": True,
        "already_applied": False,
        "applied_rrule": acceptance["applied_rrule"],
        "expected_rrule": acceptance["expected_rrule"],
    }
    if ack_needed and not apply_needed:
        result["host_match_ack"] = True
    if acceptance.get("stale_hint_accepted"):
        result["stale_hint_accepted"] = True
        result["stale_hint_tolerance_minutes"] = acceptance.get(
            "stale_hint_tolerance_minutes"
        )
    return result


def _int_number(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_codex_app_scheduler_ack_event(
    before: dict[str, Any],
    *,
    agent_id: str | None,
    applied_rrule: str,
    classification: str = "quota_scheduler_ack",
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    reset_token: str | None = None,
    identity_signature: str | None = None,
    generated_at: str | None = None,
    reason_summary: str | None = None,
    compact_before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_agent_id = str(agent_id or "").strip()
    if not safe_agent_id:
        raise ValueError("quota scheduler-ack requires a scoped --agent-id")
    scheduler_hint, codex_app, stateful_backoff = scheduler_backoff_packet(before)
    if not stateful_backoff:
        raise ValueError(
            "quota scheduler-ack requires scheduler_hint.codex_app.stateful_backoff"
        )
    if str(stateful_backoff.get("state_key") or "") != state_key:
        raise ValueError(
            "quota scheduler-ack state_key does not match current quota scheduler hint"
        )
    if (
        stateful_backoff.get("apply_needed") is not True
        and stateful_backoff.get("ack_needed") is not True
    ):
        raise ValueError(
            "quota scheduler-ack is not needed because the current RRULE is already applied"
        )
    safe_applied_rrule = normalize_scheduler_rrule(applied_rrule)
    acceptance = _scheduler_ack_rrule_acceptance(
        scheduler_hint,
        codex_app,
        stateful_backoff,
        applied_rrule=safe_applied_rrule,
        reset_token=reset_token,
        identity_signature=identity_signature,
    )
    if not acceptance.get("ok"):
        raise ValueError(
            str(acceptance.get("reason") or "scheduler ack RRULE validation failed")
        )
    expected_rrule = acceptance["expected_rrule"]
    acknowledged_rrule = acceptance["applied_rrule"]
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
    progression_index = max(
        0, _int_number(stateful_backoff.get("progression_index"), default=0)
    )
    safe_generated_at = generated_at or ""
    retained_host_update_failures = [
        failure
        for failure in retained_scheduler_host_update_failures(
            normalize_scheduler_host_update_failures(
                stateful_backoff.get("host_update_failures"),
                legacy_failure=stateful_backoff.get("host_update_failure"),
            ),
            reference_time=safe_generated_at,
            observed_host_rrule=acknowledged_rrule,
        )
        if normalize_scheduler_rrule(failure.get("target_rrule")) != acknowledged_rrule
    ]
    scheduler_state = build_scheduler_state(
        goal_id=before.get("goal_id"),
        agent_id=safe_agent_id,
        surface=surface,
        state_key=state_key,
        reset_token=stateful_backoff.get("reset_token"),
        identity_signature=stateful_backoff.get("identity_signature"),
        progression_index=progression_index,
        progression_minutes=progression_minutes,
        last_applied_rrule=acknowledged_rrule,
        updated_at=safe_generated_at,
        source=classification,
        host_update_failure=(
            retained_host_update_failures[-1] if retained_host_update_failures else None
        ),
        host_update_failures=retained_host_update_failures or None,
    )
    reason = str(reason_summary or "").strip() or (
        f"acknowledged Codex App scheduler RRULE {acknowledged_rrule}; no quota spend"
    )
    scheduler_ack_event = {
        "event_type": classification,
        "surface": surface,
        "state_key": state_key,
        "applied_rrule": acknowledged_rrule,
        "before": compact_before if isinstance(compact_before, dict) else before,
        "scheduler_state": scheduler_state,
    }
    if acceptance.get("stale_hint_accepted"):
        scheduler_ack_event["expected_rrule"] = expected_rrule
        scheduler_ack_event["stale_hint_accepted"] = True
        scheduler_ack_event["stale_hint_tolerance_minutes"] = acceptance.get(
            "stale_hint_tolerance_minutes"
        )
    return {
        "generated_at": safe_generated_at,
        "goal_id": before.get("goal_id"),
        "classification": classification,
        "agent_id": safe_agent_id,
        "recommended_action": reason,
        "health_check": "scheduler ack state updated; no quota spend",
        "delivery_outcome": DeliveryOutcome.SURFACE_ONLY.value,
        "scheduler_ack_event": scheduler_ack_event,
    }
