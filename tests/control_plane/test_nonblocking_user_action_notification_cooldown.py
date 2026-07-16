from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_module
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint
from loopx.control_plane.scheduler.state import SCHEDULER_STATE_SCHEMA_VERSION
from loopx.control_plane.work_items.interaction_contract import (
    finalize_user_gate_notification_cooldown,
)


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "control_plane"
    / "nonblocking_user_action_notification_cooldown_v0.json"
)
AGENT_SCOPE_ACTIONS = {
    "agent_scope_exhausted",
    "agent_scope_wait",
    "reassignment_required",
    "successor_replan_required",
}


def _payload(replay: dict) -> dict:
    user_todo = dict(replay["user_todo"])
    return {
        "goal_id": replay["goal_id"],
        "agent_identity": {"agent_id": replay["agent_id"]},
        "state": "eligible",
        "should_run": False,
        "effective_action": "monitor_quiet_skip",
        "normal_delivery_allowed": False,
        "recovery_delivery_allowed": False,
        "self_repair_allowed": False,
        "recommended_action": "Wait quietly for material monitor evidence.",
        "heartbeat_recommendation": {
            "recommended_mode": "monitor_quiet_until_material_transition",
            "notify": "DONT_NOTIFY",
            "spend_policy": "no spend while the monitor target is unchanged",
        },
        "execution_obligation": {
            "must_attempt_work": False,
            "spend_policy": "do not spend",
        },
        "automation_liveness": {
            "automation_action": "keep_active_quiet",
            "spend_policy": "no quota spend for unchanged monitor-only polls",
        },
        "user_todo_summary": {
            "first_open_items": [user_todo],
            "user_action_items": [user_todo],
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "monitor_quiet_skip",
            "user_channel": {
                "action_required": False,
                "notify": "NOTIFY",
                "non_blocking": True,
                "actions": [user_todo["text"]],
            },
            "agent_channel": {
                "must_attempt": False,
                "delivery_allowed": False,
                "quiet_noop_allowed": True,
            },
        },
    }


def _host_failure_state(first_hint: dict, replay: dict, *, now: datetime) -> dict:
    stateful = first_hint["codex_app"]["stateful_backoff"]
    scheduler = replay["scheduler"]
    failed_at = now - timedelta(minutes=scheduler["failure_age_minutes"])
    return {
        "schema_version": SCHEDULER_STATE_SCHEMA_VERSION,
        "goal_id": replay["goal_id"],
        "agent_id": replay["agent_id"],
        "surface": "codex_app",
        "state_key": stateful["state_key"],
        "reset_token": stateful["reset_token"],
        "identity_signature": stateful["identity_signature"],
        "progression_index": stateful["progression_index"],
        "progression_minutes": first_hint["codex_app"][
            "example_progression_minutes"
        ],
        "last_applied_rrule": "",
        "updated_at": now.isoformat(),
        "host_update_failure": {
            "schema_version": "scheduler_host_update_failure_v0",
            "target_rrule": scheduler["recommended_rrule"],
            "observed_host_rrule": scheduler["observed_host_rrule"],
            "failure_kind": "host_tool_failure",
            "failure_count": 1,
            "failed_at": failed_at.isoformat(),
        },
    }


def _replay_hint(payload: dict, replay: dict) -> dict:
    now = datetime.fromisoformat(replay["observed_at"])
    first = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_current_rrule=replay["scheduler"]["observed_host_rrule"],
    )
    return build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=_host_failure_state(first, replay, now=now),
        codex_app_current_rrule=replay["scheduler"]["observed_host_rrule"],
    )


def test_public_safe_replay_cools_nonblocking_notice_without_closing_todo(
    monkeypatch,
) -> None:
    replay = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(replay["observed_at"])
    monkeypatch.setattr(scheduler_hint_module, "now_utc", lambda: now)
    payload = _payload(replay)
    hint = _replay_hint(payload, replay)
    payload["scheduler_hint"] = hint

    finalize_user_gate_notification_cooldown(payload)

    expected = replay["expected"]
    cooldown = payload["user_gate_notification_cooldown"]
    assert hint["cadence_class"] == expected["cadence_class"]
    assert cooldown["notification_scope"] == expected["notification_scope"]
    assert cooldown["notification_suppressed"] is expected[
        "notification_suppressed"
    ]
    assert payload["pending_user_action"] is expected["pending_user_action"]
    assert payload["interaction_contract"]["mode"] == expected["interaction_mode"]
    assert payload["interaction_contract"]["user_channel"]["notify"] == expected[
        "user_notify"
    ]
    assert payload["user_todo_summary"]["first_open_items"][0]["status"] == expected[
        "todo_status"
    ]


def test_monitor_wait_without_user_notice_does_not_create_notification_cooldown(
    monkeypatch,
) -> None:
    replay = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = datetime.fromisoformat(replay["observed_at"])
    monkeypatch.setattr(scheduler_hint_module, "now_utc", lambda: now)
    payload = _payload(replay)
    payload.pop("user_todo_summary")
    payload["interaction_contract"]["user_channel"] = {
        "action_required": False,
        "notify": "DONT_NOTIFY",
    }

    hint = _replay_hint(payload, replay)

    assert "user_gate_notification_cooldown" not in hint
