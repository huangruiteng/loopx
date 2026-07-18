from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_module
from loopx.control_plane.scheduler.ack import build_codex_app_scheduler_ack_event
from loopx.control_plane.quota.turn_envelope import build_turn_envelope
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint
from loopx.control_plane.scheduler.execution_context import (
    scheduler_execution_context_for_runtime_profile,
)
from loopx.control_plane.scheduler.state import (
    SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run


GOAL_ID = "user-gate-lane-progress-fixture"
AGENT_ID = "codex-main-control"
APP_CONTEXT = scheduler_execution_context_for_runtime_profile(
    "codex_app_heartbeat"
)


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


def _quality_vision_run() -> dict:
    return {
        "classification": "quality_vision_fixture",
        "generated_at": "2026-07-18T00:00:00+00:00",
        "agent_id": AGENT_ID,
        "progress_scope": "agent_lane",
        "agent_vision": {
            "schema_version": "goal_vision_replan_contract_v0",
            "agent_id": AGENT_ID,
            "state": "vision_active",
            "vision_patch": {
                "acceptance_summary": "Uncovered quality gaps remain.",
                "advancement_policy": "repeat_until_closed",
                "replan_trigger_summary": (
                    "Replan when no runnable quality advancement remains."
                ),
            },
        },
    }


def test_unrelated_user_gate_allows_ready_deferred_successor_replan() -> None:
    payload = build_quota_should_run(
        _status_payload(gate_action_kind="approve_product_first_screen"),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=APP_CONTEXT,
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


def test_consumed_review_gate_exposes_quality_vision_replan() -> None:
    completed = quota_todo_item(
        todo_id="todo_completed_design",
        status="done",
        text="[P0] Complete the reviewed design.",
        claimed_by=AGENT_ID,
    )

    def decide(gate_status: str) -> dict:
        gate = quota_todo_item(
            todo_id="todo_owner_review",
            role="user",
            status=gate_status,
            task_class="user_gate",
            text="[P0] Review the design.",
            blocks_agent=AGENT_ID,
        )
        status = quota_status_payload(
            goal_id=GOAL_ID,
            status="active",
            recommended_action="Review the design.",
            agent_todos=quota_todo_summary(
                [completed],
                role="agent",
                claim_scope_agent_id=AGENT_ID,
            ),
            user_todos=quota_todo_summary([gate], role="user"),
            quota_state="operator_gate",
            coordination={
                "agent_model": "peer_v1",
                "registered_agents": [AGENT_ID],
            },
            latest_runs=[_quality_vision_run()],
        )
        return build_quota_should_run(
            status,
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
            scheduler_execution_context=APP_CONTEXT,
        )

    waiting = decide("open")
    assert waiting["decision"] == "skip"
    assert waiting["interaction_contract"]["mode"] == "user_gate"

    recovered = decide("done")
    assert recovered["decision"] == "autonomous_replan_required"
    assert recovered["should_run"] is True
    assert recovered["goal_frontier_projection"]["acceptance_gaps"][0][
        "kind"
    ] == "vision_acceptance_gap"
    assert recovered["interaction_contract"]["agent_channel"]["must_attempt"] is True


def test_blocking_user_gate_backs_off_instead_of_polling_as_active_work() -> None:
    payload = build_quota_should_run(
        _status_payload(gate_action_kind="refine_benchmark_treatment"),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=APP_CONTEXT,
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
        scheduler_execution_context=APP_CONTEXT,
    )

    assert next_hint["cadence_class"] == "human_gate"
    assert next_hint["codex_app"]["recommended_interval_minutes"] == 60
    assert next_hint["codex_app"]["stateful_backoff"]["progression_index"] == 1
    assert next_hint["codex_app"]["stateful_backoff"]["apply_needed"] is True
    assert next_hint["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=60"


def test_acked_human_gate_advances_despite_unrelated_historical_host_failure(
    monkeypatch,
) -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(scheduler_hint_module, "now_utc", lambda: now)
    payload = build_quota_should_run(
        _status_payload(gate_action_kind="refine_benchmark_treatment"),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=APP_CONTEXT,
    )
    first_rrule = payload["scheduler_hint"]["codex_app"]["stateful_backoff"][
        "current_rrule"
    ]
    historical_failure = {
        "schema_version": SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
        "target_rrule": "FREQ=MINUTELY;INTERVAL=3",
        "observed_host_rrule": first_rrule,
        "failure_kind": "timeout",
        "failure_count": 1,
        "failed_at": now.isoformat(),
    }

    host_matched = build_scheduler_hint(
        payload,
        user_action_required=True,
        codex_app_scheduler_state={
            "reset_token": "previous-active-work",
            "identity_signature": "previous-active-work",
            "progression_index": 0,
            "progression_minutes": [3, 6, 10],
            "last_applied_rrule": first_rrule,
            "updated_at": now.isoformat(),
            "host_update_failures": [historical_failure],
        },
        codex_app_current_rrule=first_rrule,
        scheduler_execution_context=APP_CONTEXT,
    )
    matched_app = host_matched["codex_app"]
    assert matched_app["stateful_backoff"]["apply_needed"] is False
    assert matched_app["stateful_backoff"]["ack_needed"] is True
    assert matched_app["ack_hint"]["after"] == "matching_host_rrule_observed"

    fallback_ack = build_codex_app_scheduler_ack_event(
        {"goal_id": GOAL_ID, "scheduler_hint": host_matched},
        agent_id=AGENT_ID,
        applied_rrule=first_rrule,
        generated_at=now.isoformat(),
    )
    settled_state = fallback_ack["scheduler_ack_event"]["scheduler_state"]
    assert settled_state["last_applied_rrule"] == first_rrule
    assert settled_state["host_update_failures"] == [historical_failure]

    elapsed = now + timedelta(minutes=30)
    monkeypatch.setattr(scheduler_hint_module, "now_utc", lambda: elapsed)
    next_hint = build_scheduler_hint(
        payload,
        user_action_required=True,
        codex_app_scheduler_state=settled_state,
        codex_app_current_rrule=first_rrule,
        scheduler_execution_context=APP_CONTEXT,
    )

    next_app = next_hint["codex_app"]
    assert next_app["stateful_backoff"]["progression_index"] == 1
    assert next_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=60"
    assert next_app["stateful_backoff"]["apply_needed"] is True
