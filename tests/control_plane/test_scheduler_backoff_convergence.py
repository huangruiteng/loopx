from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_module
from loopx.control_plane.scheduler.scheduler_hint import (
    build_codex_app_scheduler_ack_event,
    build_scheduler_hint,
)


GOAL_ID = "scheduler-backoff-convergence"
AGENT_ID = "codex-fixture"
HOST_15 = "FREQ=MINUTELY;INTERVAL=15"
HOST_30 = "FREQ=MINUTELY;INTERVAL=30"


def _monitor_decision(*, now: datetime, minutes_until_due: int) -> dict:
    return {
        "goal_id": GOAL_ID,
        "agent_identity": {"agent_id": AGENT_ID},
        "should_run": False,
        "effective_action": "monitor_quiet_skip",
        "recommended_action": "Wait for material monitor evidence.",
        "heartbeat_recommendation": {
            "recommended_mode": "monitor_quiet_until_material_transition",
            "notify": "DONT_NOTIFY",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "monitor_quiet_skip",
            "user_channel": {"action_required": False, "notify": "DONT_NOTIFY"},
            "agent_channel": {
                "must_attempt": False,
                "delivery_allowed": False,
                "quiet_noop_allowed": True,
            },
        },
        "agent_todo_summary": {
            "current_agent_claimed_monitor_items": [
                {
                    "todo_id": "todo_scheduler_convergence",
                    "task_class": "continuous_monitor",
                    "target_key": "scheduler-convergence",
                    "cadence": "3m",
                    "next_due_at": (
                        now + timedelta(minutes=minutes_until_due)
                    ).isoformat(),
                    "expires_at": (
                        now + timedelta(minutes=minutes_until_due + 60)
                    ).isoformat(),
                }
            ],
            "monitor_open_items": [],
        },
    }


def _hint(
    monkeypatch,
    decision: dict,
    *,
    now: datetime,
    scheduler_state: dict | None = None,
    host_rrule: str | None = None,
) -> dict:
    monkeypatch.setattr(scheduler_hint_module, "now_utc", lambda: now)
    return build_scheduler_hint(
        decision,
        codex_app_scheduler_state=scheduler_state,
        codex_app_current_rrule=host_rrule,
    )


def _ack_state(hint: dict, *, applied_rrule: str, generated_at: datetime) -> dict:
    event = build_codex_app_scheduler_ack_event(
        {"goal_id": GOAL_ID, "scheduler_hint": hint},
        agent_id=AGENT_ID,
        applied_rrule=applied_rrule,
        generated_at=generated_at.isoformat(),
    )
    return event["scheduler_ack_event"]["scheduler_state"]


def test_monitor_ack_settles_before_progression_and_avoids_15_30_15_flip(
    monkeypatch,
) -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    decision = _monitor_decision(now=now, minutes_until_due=31)
    first = _hint(monkeypatch, decision, now=now)
    first_app = first["codex_app"]
    assert first_app["recommended_rrule"] == HOST_15

    settled_state = _ack_state(first, applied_rrule=HOST_15, generated_at=now)
    immediate = _hint(
        monkeypatch,
        decision,
        now=now,
        scheduler_state=settled_state,
        host_rrule=HOST_15,
    )
    immediate_app = immediate["codex_app"]
    assert immediate_app["stateful_backoff"]["state_status"] == "same_identity"
    assert immediate_app["stateful_backoff"]["current_rrule"] == HOST_15
    assert immediate_app["stateful_backoff"]["apply_needed"] is False
    assert immediate_app["stateful_backoff"]["host_observation"]["status"] == (
        "matches_recommended"
    )
    assert "recommended_rrule" not in immediate_app

    near_due = _hint(
        monkeypatch,
        decision,
        now=now + timedelta(minutes=2),
        scheduler_state=settled_state,
        host_rrule=HOST_15,
    )
    near_due_app = near_due["codex_app"]
    assert near_due_app["example_progression_minutes"] == [15]
    assert near_due_app["stateful_backoff"]["current_rrule"] == HOST_15
    assert near_due_app["stateful_backoff"]["apply_needed"] is False
    assert "recommended_rrule" not in near_due_app


def test_monitor_progression_advances_after_elapsed_interval_and_then_converges(
    monkeypatch,
) -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    decision = _monitor_decision(now=now, minutes_until_due=119)
    first = _hint(monkeypatch, decision, now=now)
    settled_15 = _ack_state(first, applied_rrule=HOST_15, generated_at=now)

    early = _hint(
        monkeypatch,
        decision,
        now=now + timedelta(minutes=14),
        scheduler_state=settled_15,
        host_rrule=HOST_15,
    )
    assert early["codex_app"]["stateful_backoff"]["current_rrule"] == HOST_15
    assert early["codex_app"]["stateful_backoff"]["apply_needed"] is False

    elapsed = now + timedelta(minutes=15)
    advance = _hint(
        monkeypatch,
        decision,
        now=elapsed,
        scheduler_state=settled_15,
        host_rrule=HOST_15,
    )
    advance_app = advance["codex_app"]
    assert advance_app["recommended_rrule"] == HOST_30
    assert advance_app["stateful_backoff"]["host_observation"]["status"] == (
        "drift_detected"
    )

    settled_30 = _ack_state(advance, applied_rrule=HOST_30, generated_at=elapsed)
    converged = _hint(
        monkeypatch,
        decision,
        now=elapsed,
        scheduler_state=settled_30,
        host_rrule=HOST_30,
    )
    converged_app = converged["codex_app"]
    assert converged_app["stateful_backoff"]["current_rrule"] == HOST_30
    assert converged_app["stateful_backoff"]["apply_needed"] is False
    assert converged_app["stateful_backoff"]["host_observation"]["status"] == (
        "matches_recommended"
    )
    assert "recommended_rrule" not in converged_app
