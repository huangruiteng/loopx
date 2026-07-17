from __future__ import annotations

from loopx.control_plane.quota.turn_envelope import build_turn_envelope
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run


GOAL_ID = "user-gate-lane-progress-fixture"
AGENT_ID = "codex-main-control"


def _status_payload(*, gate_action_kind: str) -> dict:
    completed = quota_todo_item(
        todo_id="todo_prerequisite",
        status="done",
        text="[P0] Complete the prerequisite.",
        claimed_by=AGENT_ID,
    )
    deferred = quota_todo_item(
        todo_id="todo_ready_deferred",
        status="deferred",
        text="[P1] Continue benchmark treatment refinement.",
        claimed_by=AGENT_ID,
        action_kind="refine_benchmark_treatment",
        resume_when="todo_done:todo_prerequisite",
        done=True,
    )
    agent_todos = quota_todo_summary(
        [completed, deferred],
        role="agent",
        claim_scope_agent_id=AGENT_ID,
    )
    gate = quota_todo_item(
        todo_id="todo_product_doc_gate",
        role="user",
        status="open",
        task_class="user_gate",
        text="[P2-user] Review the product first screen.",
        action_kind=gate_action_kind,
        blocks_agent=AGENT_ID,
    )
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Continue benchmark treatment refinement.",
        agent_todos=agent_todos,
        user_todos=quota_todo_summary([gate], role="user"),
        quota_state="operator_gate",
        safe_bypass=True,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [AGENT_ID],
        },
    )


def test_unrelated_user_gate_allows_ready_deferred_successor_replan() -> None:
    payload = build_quota_should_run(
        _status_payload(gate_action_kind="approve_product_first_screen"),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )

    fallback = payload["scoped_user_gate_fallback"]
    selected = fallback["selected_executable"]
    assert selected["todo_id"] == "todo_ready_deferred"
    assert selected["fallback_kind"] == "deferred_successor_replan"
    assert payload["interaction_contract"]["mode"] == "scoped_user_gate_fallback"
    assert payload["interaction_contract"]["agent_channel"]["must_attempt"] is True
    assert payload["interaction_contract"]["agent_channel"]["delivery_allowed"] is True
    assert "response_plan" not in payload["interaction_contract"]
    assert "replan ready deferred successor" in payload["interaction_contract"][
        "agent_channel"
    ]["primary_action"]
    assert payload["scheduler_hint"]["cadence_class"] == "active_work"


def test_blocking_user_gate_backs_off_instead_of_polling_as_active_work() -> None:
    payload = build_quota_should_run(
        _status_payload(gate_action_kind="refine_benchmark_treatment"),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )

    assert "scoped_user_gate_fallback" not in payload
    assert payload["interaction_contract"]["mode"] == "user_gate"
    assert payload["interaction_contract"]["agent_channel"]["must_attempt"] is False
    expected_response_plan = {
        "schema_version": "interaction_response_plan_v0",
        "kind": "surface_user_gate",
        "decision": "ask_user",
        "action_sequence": ["notify", "wait"],
        "silent_wait_allowed": False,
    }
    assert payload["interaction_contract"]["response_plan"] == expected_response_plan
    envelope = build_turn_envelope(payload)
    assert envelope["response_plan"] == expected_response_plan
    assert envelope["action_signature"]["matches"] is True
    assert envelope["action_signature"]["coverage"] == (
        "turn_envelope_action_dimensions_v1"
    )
    assert payload["scheduler_hint"]["cadence_class"] == "human_gate"
    assert payload["scheduler_hint"]["codex_app"]["recommended_interval_minutes"] == 30

    initial_backoff = payload["scheduler_hint"]["codex_app"]["stateful_backoff"]
    next_hint = build_scheduler_hint(
        payload,
        user_action_required=True,
        codex_app_scheduler_state={
            "reset_token": initial_backoff["reset_token"],
            "identity_signature": initial_backoff["identity_signature"],
            "progression_index": initial_backoff["progression_index"],
            "last_applied_rrule": initial_backoff["current_rrule"],
        },
        codex_app_current_rrule=initial_backoff["current_rrule"],
    )

    assert next_hint["cadence_class"] == "human_gate"
    assert next_hint["codex_app"]["recommended_interval_minutes"] == 60
    assert next_hint["codex_app"]["stateful_backoff"]["progression_index"] == 1
    assert next_hint["codex_app"]["stateful_backoff"]["apply_needed"] is True
    assert next_hint["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=60"
