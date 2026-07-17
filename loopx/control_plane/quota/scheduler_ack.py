from __future__ import annotations

from pathlib import Path
from typing import Any

from .decision_summary import compact_quota_decision, quota_decision_agent_id
from ..runtime.time import now_local_iso
from ..scheduler.ack import (
    build_codex_app_scheduler_ack_event,
    build_scheduler_ack_plan,
    scheduler_backoff_packet,
)
from ..scheduler.state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    CODEX_APP_SURFACE,
    SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
    build_scheduler_state,
    merge_scheduler_host_update_failure,
    normalize_scheduler_host_update_failures,
    normalize_scheduler_rrule,
    retained_scheduler_host_update_failures,
    scheduler_state_path,
    write_scheduler_state,
)
from ..todos.contract import normalize_todo_claimed_by


QUOTA_SCHEDULER_ACK_CLASSIFICATION = "quota_scheduler_ack"
QUOTA_SCHEDULER_FAILURE_CLASSIFICATION = "quota_scheduler_host_update_failure"


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


def _annotate_current_hint(payload: dict[str, Any], *, use_current_hint: bool) -> dict[str, Any]:
    if use_current_hint:
        payload["used_current_hint"] = True
        payload["current_hint_source"] = "quota.should-run.scheduler_hint"
    return payload


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
    host_match_observed: bool = False,
) -> dict[str, Any]:
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    if host_match_observed and (
        not str(applied_rrule or "").strip()
        or not str(reset_token or "").strip()
        or not str(identity_signature or "").strip()
    ):
        return scheduler_ack_failure(
            goal_id=goal_id,
            agent_id=safe_agent_id,
            execute=execute,
            surface=surface,
            state_key=state_key,
            applied_rrule=applied_rrule,
            reason=(
                "host-match scheduler ACK requires applied RRULE, reset token, "
                "and identity signature"
            ),
            before=before,
        )
    if use_current_hint and not host_match_observed:
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
        return _annotate_current_hint(
            scheduler_ack_failure(
                goal_id=goal_id,
                agent_id=safe_agent_id,
                execute=execute,
                surface=surface,
                state_key=state_key,
                applied_rrule=applied_rrule,
                reason=str(ack_plan.get("reason") or "scheduler ack validation failed"),
                before=before,
            ),
            use_current_hint=use_current_hint,
        )
    if ack_plan.get("already_applied"):
        output_before = compact_quota_decision(before) if execute else before
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
            "before": output_before,
            "after": output_before,
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
        return _annotate_current_hint(
            scheduler_ack_failure(
                goal_id=goal_id,
                agent_id=safe_agent_id,
                execute=execute,
                surface=surface,
                state_key=state_key,
                applied_rrule=applied_rrule,
                reason=str(exc),
                before=before,
            ),
            use_current_hint=use_current_hint,
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
        "before": compact_quota_decision(before) if execute else before,
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
    if ack_plan.get("host_match_ack"):
        payload["host_match_ack"] = True
        payload["reason"] = (
            f"{'updated' if execute else 'dry-run preview'} scheduler state from "
            f"matching host RRULE: {goal_id}/{safe_agent_id} observed "
            f"{record['scheduler_ack_event']['applied_rrule']}"
        )
    if use_current_hint:
        payload["used_current_hint"] = True
        payload["current_hint_source"] = "quota.should-run.scheduler_hint"
    return payload


def record_quota_scheduler_failure_for_decision(
    before: dict[str, Any],
    *,
    runtime_root: Path,
    goal_id: str,
    agent_id: str | None,
    execute: bool = False,
    surface: str = CODEX_APP_SURFACE,
    state_key: str = CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
    failed_rrule: str | None = None,
    observed_host_rrule: str | None = None,
    failure_kind: str = "host_tool_failure",
    generated_at: str | None = None,
) -> dict[str, Any]:
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    if not safe_agent_id:
        return scheduler_ack_failure(
            goal_id=goal_id,
            agent_id=agent_id,
            execute=execute,
            surface=surface,
            state_key=state_key,
            applied_rrule=failed_rrule,
            reason="quota scheduler-fail-current requires a scoped --agent-id",
            before=before,
        )
    _, codex_app, stateful_backoff = scheduler_backoff_packet(before)
    target_rrule = normalize_scheduler_rrule(
        failed_rrule
        or codex_app.get("recommended_rrule")
        or stateful_backoff.get("current_rrule")
    )
    current_rrule = normalize_scheduler_rrule(stateful_backoff.get("current_rrule"))
    host_observation = (
        stateful_backoff.get("host_observation")
        if isinstance(stateful_backoff.get("host_observation"), dict)
        else {}
    )
    observed_rrule = normalize_scheduler_rrule(
        observed_host_rrule or host_observation.get("current_rrule")
    )
    if str(stateful_backoff.get("state_key") or "") != state_key:
        reason = "--state-key does not match the current scheduler hint"
    elif stateful_backoff.get("apply_needed") is not True:
        reason = "scheduler host update failure is not recordable because no host update is needed"
    elif not target_rrule or target_rrule != current_rrule:
        reason = "--failed-rrule does not match the current scheduler target"
    else:
        reason = ""
    if reason:
        payload = scheduler_ack_failure(
            goal_id=goal_id,
            agent_id=safe_agent_id,
            execute=execute,
            surface=surface,
            state_key=state_key,
            applied_rrule=target_rrule,
            reason=reason,
            before=before,
        )
        payload["mode"] = "scheduler-fail-current"
        payload["failed_rrule"] = target_rrule
        return payload

    safe_generated_at = generated_at or _now_local()
    prior_failures = retained_scheduler_host_update_failures(
        normalize_scheduler_host_update_failures(
            stateful_backoff.get("host_update_failures"),
            legacy_failure=stateful_backoff.get("host_update_failure"),
        ),
        reference_time=safe_generated_at,
        observed_host_rrule=observed_rrule,
    )
    prior_failure = next(
        (
            failure
            for failure in reversed(prior_failures)
            if normalize_scheduler_rrule(failure.get("target_rrule")) == target_rrule
        ),
        {},
    )
    same_pair = bool(prior_failure)
    try:
        prior_failure_count = int(prior_failure.get("failure_count") or 0)
    except (TypeError, ValueError):
        prior_failure_count = 0
    failure_count = prior_failure_count + 1 if same_pair else 1
    host_update_failure = {
        "schema_version": SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
        "target_rrule": target_rrule,
        "observed_host_rrule": observed_rrule,
        "failure_kind": str(failure_kind or "host_tool_failure").strip(),
        "failure_count": failure_count,
        "failed_at": safe_generated_at,
    }
    host_update_failures = merge_scheduler_host_update_failure(
        prior_failures,
        host_update_failure,
        reference_time=safe_generated_at,
    )
    progression_minutes = (
        codex_app.get("example_progression_minutes")
        if isinstance(codex_app.get("example_progression_minutes"), list)
        else []
    )
    scheduler_state = build_scheduler_state(
        goal_id=goal_id,
        agent_id=safe_agent_id,
        surface=surface,
        state_key=state_key,
        reset_token=stateful_backoff.get("reset_token"),
        identity_signature=stateful_backoff.get("identity_signature"),
        progression_index=max(0, int(stateful_backoff.get("progression_index") or 0)),
        progression_minutes=progression_minutes,
        last_applied_rrule=observed_rrule,
        updated_at=safe_generated_at,
        source=QUOTA_SCHEDULER_FAILURE_CLASSIFICATION,
        host_update_failure=host_update_failure,
        host_update_failures=host_update_failures,
    )
    state_path = scheduler_state_path(
        runtime_root,
        goal_id=goal_id,
        agent_id=safe_agent_id,
        surface=surface,
        state_key=state_key,
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
        "mode": "scheduler-fail-current",
        "dry_run": not execute,
        "goal_id": goal_id,
        "agent_id": safe_agent_id,
        "surface": surface,
        "state_key": state_key,
        "failed_rrule": target_rrule,
        "observed_host_rrule": observed_rrule,
        "failure_kind": host_update_failure["failure_kind"],
        "classification": QUOTA_SCHEDULER_FAILURE_CLASSIFICATION,
        "generated_at": safe_generated_at,
        "appended": False,
        "registry_mutated": False,
        "scheduler_state_mutated": execute,
        "scheduler_failure_event": {
            "event_type": QUOTA_SCHEDULER_FAILURE_CLASSIFICATION,
            "surface": surface,
            "state_key": state_key,
            "before": compact_quota_decision(before),
            "scheduler_state": scheduler_state,
        },
        "scheduler_state_path": str(state_path),
        "health_check": "scheduler host update failure cached; repeated retained target/host pairs suppressed; no quota spend",
        "delivery_outcome": "surface_only",
        "before": compact_quota_decision(before) if execute else before,
        "after": None,
        "reason": (
            f"{'recorded' if execute else 'dry-run preview'} scheduler host update "
            f"failure for {goal_id}/{safe_agent_id}: {target_rrule}"
        ),
    }
