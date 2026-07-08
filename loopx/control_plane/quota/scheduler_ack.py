from __future__ import annotations

from pathlib import Path
from typing import Any

from .decision_summary import compact_quota_decision, quota_decision_agent_id
from ..runtime.time import now_local_iso
from ..scheduler.scheduler_hint import (
    build_codex_app_scheduler_ack_event,
    build_scheduler_ack_plan,
)
from ..scheduler.state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    CODEX_APP_SURFACE,
    scheduler_state_path,
    write_scheduler_state,
)
from ..todos.contract import normalize_todo_claimed_by


QUOTA_SCHEDULER_ACK_CLASSIFICATION = "quota_scheduler_ack"


def _now_local() -> str:
    return now_local_iso()


def scheduler_ack_failure(
    *,
    goal_id: str,
    agent_id: str | None,
    execute: bool,
    surface: str,
    state_key: str,
    applied_rrule: str | None,
    reason: str,
    before: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "mode": "scheduler-ack",
        "dry_run": not execute,
        "goal_id": goal_id,
        "agent_id": normalize_todo_claimed_by(agent_id),
        "surface": surface,
        "state_key": state_key,
        "applied_rrule": applied_rrule,
        "appended": False,
        "registry_mutated": False,
        "reason": reason,
        "before": before,
        "after": None,
    }


def _resolve_scheduler_ack_current_hint(
    before: dict[str, Any],
    *,
    surface: str,
    applied_rrule: str | None,
    reset_token: str | None,
    identity_signature: str | None,
) -> tuple[str | None, str | None, str | None]:
    scheduler_hint = before.get("scheduler_hint") if isinstance(before.get("scheduler_hint"), dict) else {}
    surface_packet = (
        scheduler_hint.get(surface)
        if isinstance(scheduler_hint.get(surface), dict)
        else {}
    )
    stateful_backoff = (
        surface_packet.get("stateful_backoff")
        if isinstance(surface_packet.get("stateful_backoff"), dict)
        else {}
    )
    ack_hint = (
        surface_packet.get("ack_hint")
        if isinstance(surface_packet.get("ack_hint"), dict)
        else {}
    )
    ack_args = ack_hint.get("args") if isinstance(ack_hint.get("args"), dict) else {}
    resolved_rrule = (
        str(applied_rrule or "").strip()
        or str(ack_args.get("applied_rrule") or "").strip()
        or str(surface_packet.get("recommended_rrule") or "").strip()
    )
    resolved_reset = (
        str(stateful_backoff.get("reset_token") or "").strip()
        or str(ack_args.get("reset_token") or "").strip()
        or str(reset_token or "").strip()
    )
    resolved_identity = (
        str(stateful_backoff.get("identity_signature") or "").strip()
        or str(ack_args.get("identity_signature") or "").strip()
        or str(identity_signature or "").strip()
    )
    return resolved_rrule, resolved_reset, resolved_identity


def build_quota_scheduler_ack_event(
    before: dict[str, Any],
    *,
    applied_rrule: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    reset_token: str | None = None,
    identity_signature: str | None = None,
    generated_at: str | None = None,
    reason_summary: str | None = None,
) -> dict[str, Any]:
    return build_codex_app_scheduler_ack_event(
        before,
        agent_id=quota_decision_agent_id(before),
        applied_rrule=applied_rrule,
        classification=QUOTA_SCHEDULER_ACK_CLASSIFICATION,
        surface=surface,
        state_key=state_key,
        reset_token=reset_token,
        identity_signature=identity_signature,
        generated_at=generated_at or _now_local(),
        reason_summary=reason_summary,
        compact_before=compact_quota_decision(before),
    )


def record_quota_scheduler_ack_for_decision(
    before: dict[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
    agent_id: str | None,
    execute: bool = False,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    applied_rrule: str | None = None,
    reset_token: str | None = None,
    identity_signature: str | None = None,
    reason_summary: str | None = None,
    generated_at: str | None = None,
    use_current_hint: bool = False,
) -> dict[str, Any]:
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    if use_current_hint:
        applied_rrule, reset_token, identity_signature = _resolve_scheduler_ack_current_hint(
            before,
            surface=surface,
            applied_rrule=applied_rrule,
            reset_token=reset_token,
            identity_signature=identity_signature,
        )
    ack_plan = build_scheduler_ack_plan(
        before,
        agent_id=safe_agent_id,
        state_key=state_key,
        applied_rrule=applied_rrule,
        reset_token=reset_token,
        identity_signature=identity_signature,
    )
    if not ack_plan.get("ok"):
        return scheduler_ack_failure(
            goal_id=goal_id,
            agent_id=safe_agent_id,
            execute=execute,
            surface=surface,
            state_key=state_key,
            applied_rrule=applied_rrule,
            reason=str(ack_plan.get("reason") or "scheduler ack validation failed"),
            before=before,
        )
        if use_current_hint:
            failure["used_current_hint"] = True
            failure["current_hint_source"] = "quota.should-run.scheduler_hint"
        return failure
    if ack_plan.get("already_applied"):
        payload = {
            "ok": True,
            "mode": "scheduler-ack",
            "dry_run": not execute,
            "goal_id": goal_id,
            "agent_id": safe_agent_id,
            "surface": surface,
            "state_key": state_key,
            "applied_rrule": ack_plan.get("applied_rrule"),
            "appended": False,
            "registry_mutated": False,
            "already_applied": True,
            "before": before,
            "after": before,
            "reason": "scheduler RRULE already applied; no ack write needed",
        }
        if use_current_hint:
            payload["used_current_hint"] = True
            payload["current_hint_source"] = "quota.should-run.scheduler_hint"
        return payload

    safe_generated_at = generated_at or _now_local()
    try:
        record = build_quota_scheduler_ack_event(
            before,
            applied_rrule=str(applied_rrule),
            surface=surface,
            state_key=state_key,
            reset_token=reset_token,
            identity_signature=identity_signature,
            generated_at=safe_generated_at,
            reason_summary=reason_summary,
        )
    except ValueError as exc:
        return scheduler_ack_failure(
            goal_id=goal_id,
            agent_id=safe_agent_id,
            execute=execute,
            surface=surface,
            state_key=state_key,
            applied_rrule=applied_rrule,
            reason=str(exc),
            before=before,
        )
        if use_current_hint:
            failure["used_current_hint"] = True
            failure["current_hint_source"] = "quota.should-run.scheduler_hint"
        return failure

    state_path = scheduler_state_path(
        runtime_root,
        goal_id=goal_id,
        agent_id=safe_agent_id,
        surface=surface,
        state_key=state_key,
    )
    scheduler_state = (
        record.get("scheduler_ack_event", {}).get("scheduler_state")
        if isinstance(record.get("scheduler_ack_event"), dict)
        else {}
    )
    if execute:
        write_scheduler_state(
            runtime_root,
            scheduler_state,
            goal_id=goal_id,
            agent_id=safe_agent_id,
            surface=surface,
            state_key=state_key,
        )

    payload = {
        "ok": True,
        "mode": "scheduler-ack",
        "dry_run": not execute,
        "goal_id": goal_id,
        "agent_id": safe_agent_id,
        "surface": surface,
        "state_key": state_key,
        "applied_rrule": record["scheduler_ack_event"]["applied_rrule"],
        "classification": QUOTA_SCHEDULER_ACK_CLASSIFICATION,
        "generated_at": safe_generated_at,
        "appended": False,
        "registry_mutated": False,
        "scheduler_state_mutated": execute,
        "already_applied": False,
        "scheduler_ack_event": record["scheduler_ack_event"],
        "health_check": record["health_check"],
        "delivery_outcome": record["delivery_outcome"],
        "scheduler_state_path": str(state_path),
        "before": before,
        "after": None,
        "post_ack_contract": {
            "next_action": "wait_for_next_scheduler_tick_or_material_state_transition",
            "do_not_apply_successor_rrule_from_ack_response": True,
            "next_rrule_source": "future_quota_should-run_only",
        },
        "reason": (
            f"{'updated' if execute else 'dry-run preview'} scheduler state ack: "
            f"{goal_id}/{safe_agent_id} applied {record['scheduler_ack_event']['applied_rrule']}"
        ),
    }
    if use_current_hint:
        payload["used_current_hint"] = True
        payload["current_hint_source"] = "quota.should-run.scheduler_hint"
    return payload
