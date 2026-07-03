#!/usr/bin/env python3
"""Smoke-test autonomous replan isolation from local lane quiet/wait state."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.status import compact_todo_group  # noqa: E402


GOAL_ID = "replan-decision-plane-fixture"
PRIMARY_AGENT = "codex-main-control"
SIDE_AGENT = "codex-side-bypass"
FUTURE_DUE_AT = "2999-01-01T00:00:00+00:00"


REPLAN_OBLIGATION = {
    "schema_version": "autonomous_replan_obligation_v0",
    "required": True,
    "stall_threshold": 2,
    "trigger_count": 1,
    "triggers": [{"kind": "periodic_review_due", "source": "fixture"}],
    "next_validation_command": "python3 examples/control_plane/quota-replan-decision-plane-smoke.py",
    "stop_condition": "stop after one bounded replan slice writes back a concrete frontier delta",
}


def monitor_item() -> dict:
    return {
        "index": 1,
        "todo_id": "todo_monitor_wait",
        "text": "[P1-monitor] Monitor a fixture signal only when material transition appears.",
        "role": "agent",
        "status": "open",
        "priority": "P1",
        "task_class": "continuous_monitor",
        "action_kind": "monitor",
        "claimed_by": SIDE_AGENT,
        "target_key": "fixture-signal",
        "cadence": "15m",
        "next_due_at": FUTURE_DUE_AT,
    }


def primary_claimed_advancement() -> dict:
    return {
        "index": 1,
        "todo_id": "todo_primary_owned",
        "text": "[P0] Primary agent owns the next visible advancement slice.",
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "claimed_by": PRIMARY_AGENT,
    }


def blocking_handoff_review() -> dict:
    return {
        "index": 2,
        "todo_id": "todo_fixture_review_gate",
        "text": "[P1] Primary agent reviews the side-agent delivery PR.",
        "role": "agent",
        "status": "open",
        "priority": "P1",
        "task_class": "advancement_task",
        "action_kind": "review_merge",
        "claimed_by": PRIMARY_AGENT,
        "blocks_agent": SIDE_AGENT,
    }


def status_payload(
    agent_todo_items: list[dict],
    *,
    replan_obligation: dict | None = REPLAN_OBLIGATION,
    latest_runs: list[dict] | None = None,
) -> dict:
    agent_todos = compact_todo_group(
        agent_todo_items,
        source_section="Agent Todo",
        role="agent",
    )
    assert agent_todos is not None
    project_asset = {
        "next_action": "Observe the fixture signal; no material transition is available.",
        "agent_todos": agent_todos,
    }
    if replan_obligation is not None:
        project_asset["autonomous_replan_obligation"] = replan_obligation
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "",
                    "severity": "active",
                    "source": "active_state",
                    "recommended_action": "Observe the fixture signal; no material transition is available.",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                        "spent_slots": 0,
                        "state": "eligible",
                        "reason": "eligible fixture",
                    },
                    "project_asset": project_asset,
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "coordination": {
                        "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
                        "primary_agent": PRIMARY_AGENT,
                    },
                    "latest_runs": latest_runs or [],
                }
            ]
        },
    }


def assert_replan_beats_monitor_quiet_skip() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item()]),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "autonomous_replan_required", guard
    assert guard["execution_obligation"]["kind"] == "autonomous_replan_required", guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    assert guard["goal_frontier_projection"]["monitor_only_lanes"]["present"] is True, guard
    assert guard["goal_frontier_projection"]["deferred_successors"] == {
        "ready_count": 0,
        "blocked_count": 0,
        "current_agent_ready_count": 0,
        "ready_todo_ids": [],
    }, guard
    assert guard["goal_frontier_projection"]["acceptance_gaps"] == [], guard
    assert guard["autonomous_replan_decision"]["decision_plane"] == (
        "goal_frontier_before_lane_quiet_or_agent_scope_wait"
    ), guard
    assert "monitor_quiet_skip" in guard["autonomous_replan_decision"]["not_disturbed_by"], guard
    markdown = render_quota_should_run_markdown(guard)
    assert "goal_frontier_projection: replan_required=True" in markdown, markdown
    assert "deferred_ready=0 acceptance_gaps=0" in markdown, markdown
    assert "autonomous_replan_decision: decision=autonomous_replan_required" in markdown, markdown


def assert_replan_beats_agent_scope_wait() -> None:
    guard = build_quota_should_run(
        status_payload([primary_claimed_advancement()]),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "autonomous_replan_required", guard
    assert guard["execution_obligation"]["kind"] == "autonomous_replan_required", guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    assert "agent_scope_frontier" not in guard, guard
    frontier = guard["goal_frontier_projection"]["remaining_advancement_frontier"]
    assert frontier["current_agent_claimed_advancement_count"] == 0, guard
    assert frontier["unclaimed_advancement_count"] == 0, guard
    assert frontier["other_agent_claimed_advancement_count"] == 1, guard
    assert guard["goal_frontier_projection"]["deferred_successors"]["ready_count"] == 0, guard
    assert guard["goal_frontier_projection"]["acceptance_gaps"] == [], guard
    assert "agent_scope_wait" in guard["autonomous_replan_decision"]["not_disturbed_by"], guard


def assert_empty_monitor_frontier_derives_replan() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item()], replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["required"] is True, guard
    assert obligation["triggers"][0]["kind"] == "frontier_exhausted_monitor_lane", guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    assert guard["goal_frontier_projection"]["remaining_advancement_frontier"] == {
        "current_agent_claimed_advancement_count": 0,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 0,
    }, guard
    scheduler = guard["scheduler_hint"]
    assert scheduler["action"] == "run_now", guard
    assert scheduler["cadence_class"] == "active_work", guard


def assert_agent_ack_survives_other_agent_run_and_monitor_poll() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
                {
                    "classification": "state_refreshed",
                    "agent_id": PRIMARY_AGENT,
                    "progress_scope": "agent_lane",
                    "recommended_action": "Primary lane refreshed unrelated state.",
                },
                {
                    "classification": "quota_monitor_poll",
                    "agent_id": SIDE_AGENT,
                    "recommended_action": "Fixture monitor stayed unchanged.",
                    "monitor_target": {
                        "schema_version": "quota_monitor_target_v0",
                        "target_id": "fixture-monitor-target",
                        "monitor_mode": "monitor_quiet_until_material_transition",
                        "effective_action": "monitor_quiet_skip",
                        "agent_id": SIDE_AGENT,
                    },
                },
                {
                    "classification": "monitor_poll_autonomous_replan_recorded_v0",
                    "agent_id": SIDE_AGENT,
                    "progress_scope": "agent_lane",
                    "autonomous_replan_ack": {
                        "schema_version": "autonomous_replan_ack_v0",
                        "recorded": True,
                        "source": "refresh_state",
                        "delta_contract": {
                            "schema_version": "repair_delta_contract_v0",
                            "delta_present": True,
                            "delta_kinds": ["watch_lane_continuation", "no_followup"],
                        },
                    },
                },
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert guard["should_run"] is False, guard
    assert guard["interaction_contract"]["mode"] == "monitor_quiet_skip", guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard


def assert_blocking_handoff_gate_beats_derived_monitor_replan() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item(), blocking_handoff_review()], replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert guard["should_run"] is False, guard
    assert guard["interaction_contract"]["mode"] == "monitor_quiet_skip", guard
    assert guard["goal_route_hint"]["blocking_handoff_gates"][0]["todo_id"] == (
        "todo_fixture_review_gate"
    ), guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard


def main() -> None:
    assert_replan_beats_monitor_quiet_skip()
    assert_replan_beats_agent_scope_wait()
    assert_empty_monitor_frontier_derives_replan()
    assert_agent_ack_survives_other_agent_run_and_monitor_poll()
    assert_blocking_handoff_gate_beats_derived_monitor_replan()
    print("quota-replan-decision-plane-smoke ok")


if __name__ == "__main__":
    main()
