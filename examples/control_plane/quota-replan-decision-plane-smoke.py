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


GLOBAL_REPLAN_OBLIGATION = {
    "schema_version": "autonomous_replan_obligation_v0",
    "required": True,
    "stall_threshold": 2,
    "trigger_count": 1,
    "triggers": [{"kind": "periodic_review_due", "source": "fixture"}],
    "next_validation_command": "python3 examples/control_plane/quota-replan-decision-plane-smoke.py",
    "stop_condition": "stop after one bounded replan slice writes back a concrete frontier delta",
}

SIDE_AGENT_REPLAN_OBLIGATION = {
    **GLOBAL_REPLAN_OBLIGATION,
    "triggers": [
        {"kind": "periodic_review_due", "source": "fixture", "agent_id": SIDE_AGENT}
    ],
}


def monitor_item(
    *,
    cadence: str | None = "15m",
    next_due_at: str | None = FUTURE_DUE_AT,
) -> dict:
    item = {
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
    }
    if cadence is not None:
        item["cadence"] = cadence
    if next_due_at is not None:
        item["next_due_at"] = next_due_at
    return item


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


def side_agent_claimed_advancement() -> dict:
    return {
        "index": 2,
        "todo_id": "todo_side_canary_refactor",
        "text": "[P1] Continue the next non-benchmark canary/refactor batch.",
        "role": "agent",
        "status": "open",
        "priority": "P1",
        "task_class": "advancement_task",
        "action_kind": "canary_refactor_next_batch",
        "claimed_by": SIDE_AGENT,
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
    replan_obligation: dict | None = GLOBAL_REPLAN_OBLIGATION,
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


def agent_vision_gap_run() -> dict:
    return {
        "classification": "state_refreshed",
        "generated_at": "2026-07-04T00:00:00+00:00",
        "agent_id": SIDE_AGENT,
        "progress_scope": "agent_lane",
        "agent_vision": {
            "schema_version": "goal_vision_replan_contract_v0",
            "agent_id": SIDE_AGENT,
            "state": "vision_drift_detected",
            "vision_patch": {
                "acceptance_summary": "Show the next runnable auto-research frontier without owner prompting.",
                "replan_trigger_summary": "Auto-research evidence is still synthetic and needs a next-round live validation todo.",
            },
            "todo_delta": [],
            "vision_budget": {
                "schema_version": "goal_vision_budget_v0",
                "status": "ok",
            },
        },
    }


def assert_replan_beats_monitor_quiet_skip() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item()], replan_obligation=SIDE_AGENT_REPLAN_OBLIGATION),
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
    assert guard["autonomous_replan_scope"]["applies"] is True, guard
    required_reads = guard["required_reads"]
    assert required_reads[0]["kind"] == "agent_scoped_evidence_log", required_reads
    assert required_reads[0]["agent_id"] == SIDE_AGENT, required_reads
    assert required_reads[0]["todo_id"] == "todo_monitor_wait", required_reads
    assert "evidence-log" in required_reads[0]["command"], required_reads
    assert " --agent-id codex-side-bypass " in f" {required_reads[0]['command']} ", required_reads
    assert guard["autonomous_replan_obligation"]["required_reads"] == required_reads, guard
    assert (
        guard["interaction_contract"]["agent_channel"]["required_reads"] == required_reads
    ), guard
    assert (
        guard["interaction_contract"]["cli_channel"]["required_reads"] == required_reads
    ), guard
    assert guard["autonomous_replan_decision"]["decision_plane"] == (
        "goal_frontier_before_lane_quiet_or_agent_scope_wait"
    ), guard
    assert "monitor_quiet_skip" in guard["autonomous_replan_decision"]["not_disturbed_by"], guard
    markdown = render_quota_should_run_markdown(guard)
    assert "goal_frontier_projection: replan_required=True" in markdown, markdown
    assert "deferred_ready=0 acceptance_gaps=0" in markdown, markdown
    assert "autonomous_replan_decision: decision=autonomous_replan_required" in markdown, markdown
    assert "required_read: kind=agent_scoped_evidence_log" in markdown, markdown
    assert "evidence-log --goal-id replan-decision-plane-fixture" in markdown, markdown


def assert_future_scheduled_monitor_quiets_without_generated_replan() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item()], replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "skip", guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert guard["should_run"] is False, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == (
        "monitor_quiet_until_material_transition"
    ), guard
    assert guard["interaction_contract"]["mode"] == "monitor_quiet_skip", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is False, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is True, guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard


def assert_replan_preserves_current_agent_runnable_frontier() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item(), side_agent_claimed_advancement()],
            replan_obligation=SIDE_AGENT_REPLAN_OBLIGATION,
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    lane_action = guard["agent_lane_next_action"]
    assert lane_action["todo_id"] == "todo_side_canary_refactor", guard
    assert lane_action["selected_by"] == "current_agent_claimed_todo", guard
    assert lane_action["preserves_goal_next_action"] is True, guard
    primary_action = guard["interaction_contract"]["agent_channel"]["primary_action"]
    assert "todo_side_canary_refactor" in primary_action, guard
    assert "bounded autonomous replan" in primary_action, guard
    cli_actions = guard["interaction_contract"]["cli_channel"]["next_cli_actions"]
    assert "todo_side_canary_refactor" in cli_actions[0], guard
    frontier = guard["goal_frontier_projection"]["remaining_advancement_frontier"]
    assert frontier["current_agent_claimed_advancement_count"] == 1, guard
    assert guard["goal_route_hint"]["current_agent_next_action"]["todo_id"] == (
        "todo_side_canary_refactor"
    ), guard
    markdown = render_quota_should_run_markdown(guard)
    assert "agent_lane_next_action: todo_id=todo_side_canary_refactor" in markdown, markdown


def assert_agent_vision_gap_derives_replan() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[agent_vision_gap_run()],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["triggers"][0]["kind"] == "vision_acceptance_gap", guard
    gaps = guard["goal_frontier_projection"]["acceptance_gaps"]
    assert len(gaps) == 1, guard
    assert gaps[0]["kind"] == "vision_acceptance_gap", guard
    assert "synthetic" in gaps[0]["replan_trigger_summary"], guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "deferred_ready=0 acceptance_gaps=1" in markdown, markdown


def assert_agent_scoped_replan_beats_agent_scope_wait() -> None:
    guard = build_quota_should_run(
        status_payload(
            [primary_claimed_advancement()],
            replan_obligation=SIDE_AGENT_REPLAN_OBLIGATION,
        ),
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


def assert_unscoped_replan_defaults_to_primary_agent() -> None:
    primary_guard = build_quota_should_run(
        status_payload([primary_claimed_advancement()]),
        goal_id=GOAL_ID,
        agent_id=PRIMARY_AGENT,
    )
    assert primary_guard["decision"] == "autonomous_replan_required", primary_guard
    assert primary_guard["effective_action"] == "autonomous_replan_required", primary_guard
    assert primary_guard["autonomous_replan_scope"]["scope"] == "default_primary_agent", primary_guard
    assert primary_guard["autonomous_replan_scope"]["applies"] is True, primary_guard

    side_guard = build_quota_should_run(
        status_payload([primary_claimed_advancement()]),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert side_guard["effective_action"] == "agent_scope_wait", side_guard
    assert side_guard["should_run"] is False, side_guard
    assert side_guard["interaction_contract"]["mode"] == "agent_scope_wait", side_guard
    assert side_guard["autonomous_replan_scope"]["scope"] == "default_primary_agent", side_guard
    assert side_guard["autonomous_replan_scope"]["applies"] is False, side_guard
    assert side_guard.get("autonomous_replan_obligation") is None, side_guard
    assert side_guard["goal_frontier_projection"]["replan_required"] is False, side_guard

    monitor_side_guard = build_quota_should_run(
        status_payload([monitor_item(), primary_claimed_advancement()]),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert monitor_side_guard["effective_action"] == "monitor_quiet_skip", monitor_side_guard
    assert monitor_side_guard["should_run"] is False, monitor_side_guard
    assert monitor_side_guard["interaction_contract"]["mode"] == "monitor_quiet_skip", monitor_side_guard
    assert monitor_side_guard["autonomous_replan_scope"]["applies"] is False, monitor_side_guard
    assert monitor_side_guard.get("autonomous_replan_obligation") is None, monitor_side_guard


def assert_monitor_schedule_gap_requires_bounded_repair() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item(cadence=None, next_due_at=None)], replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert guard["should_run"] is True, guard
    assert guard["interaction_contract"]["mode"] == "bounded_delivery", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard.get("autonomous_replan_obligation") is None, guard
    assert guard["execution_obligation"]["kind"] == "work_lane_contract", guard
    assert guard["execution_obligation"]["contract_obligation"] == (
        "repair_monitor_schedule_metadata"
    ), guard
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["monitor_kind"] == "todo_monitor_schedule_gap", lane
    assert lane["obligation"] == "repair_monitor_schedule_metadata", lane
    assert lane["monitor_schedule_gap_count"] == 1, lane
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
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
    assert_future_scheduled_monitor_quiets_without_generated_replan()
    assert_replan_preserves_current_agent_runnable_frontier()
    assert_agent_vision_gap_derives_replan()
    assert_agent_scoped_replan_beats_agent_scope_wait()
    assert_unscoped_replan_defaults_to_primary_agent()
    assert_monitor_schedule_gap_requires_bounded_repair()
    assert_agent_ack_survives_other_agent_run_and_monitor_poll()
    assert_blocking_handoff_gate_beats_derived_monitor_replan()
    print("quota-replan-decision-plane-smoke ok")


if __name__ == "__main__":
    main()
