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


def build_quota_scheduler_ack_event(
    before: dict[str, Any],
    *,
    applied_rrule: str,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
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
) -> dict[str, Any]:
    safe_agent_id = normalize_todo_claimed_by(agent_id)
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
    if ack_plan.get("already_applied"):
        return {
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

    safe_generated_at = generated_at or _now_local()
    try:
        record = build_quota_scheduler_ack_event(
            before,
            applied_rrule=str(applied_rrule),
            surface=surface,
            state_key=state_key,
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

    return {
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
