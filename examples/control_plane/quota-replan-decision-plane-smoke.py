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


def completed_side_agent_advancement_without_successor() -> dict:
    return {
        "index": 3,
        "todo_id": "todo_completed_without_successor",
        "text": "[P0] Complete a visible auto-research advancement slice.",
        "role": "agent",
        "status": "done",
        "done": True,
        "priority": "P0",
        "task_class": "advancement_task",
        "action_kind": "fix_visible_auto_research_tick",
        "claimed_by": SIDE_AGENT,
        "completed_at": "2026-07-05T13:36:19+08:00",
    }


def completed_side_agent_prerequisite_with_successor() -> dict:
    return {
        "index": 3,
        "todo_id": "todo_completed_with_deferred_successor",
        "text": "[P1] Finish the visible auto-research tick honesty prerequisite.",
        "role": "agent",
        "status": "done",
        "done": True,
        "priority": "P1",
        "task_class": "advancement_task",
        "action_kind": "fix_visible_auto_research_tick",
        "claimed_by": SIDE_AGENT,
        "successor_todo_ids": ["todo_ready_deferred_successor"],
        "completed_at": "2026-07-05T13:36:19+08:00",
    }


def ready_deferred_side_agent_successor() -> dict:
    return {
        "index": 4,
        "todo_id": "todo_ready_deferred_successor",
        "text": "[P2] Follow up with higher-value research artifacts for the KNN showcase.",
        "role": "agent",
        "status": "deferred",
        "priority": "P2",
        "task_class": "advancement_task",
        "action_kind": "improve_auto_research_artifact_value",
        "claimed_by": SIDE_AGENT,
        "resume_when": "todo_done:todo_completed_with_deferred_successor",
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


def missing_vision_checkpoint_run(*, agent_id: str = SIDE_AGENT) -> dict:
    return {
        "classification": "state_refreshed",
        "generated_at": "2026-07-04T00:05:00+00:00",
        "agent_id": agent_id,
        "progress_scope": "agent_lane",
        "delivery_outcome": "outcome_progress",
        "vision_checkpoint": {
            "schema_version": "vision_checkpoint_v0",
            "agent_id": agent_id,
            "required": True,
            "satisfied": False,
            "decision": "missing_required",
            "triggers": [
                {
                    "kind": "material_delivery_outcome",
                    "delivery_outcome": "outcome_progress",
                }
            ],
            "required_resolution": [
                "write_agent_vision_patch",
                "record_unchanged_reason",
            ],
        },
    }


def assert_replan_beats_monitor_quiet_skip() -> None:
    payload = status_payload([monitor_item()], replan_obligation=SIDE_AGENT_REPLAN_OBLIGATION)
    guard = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=SIDE_AGENT)
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
    repeat_guard = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=SIDE_AGENT)
    assert repeat_guard["required_reads"] == required_reads, repeat_guard
    assert (
        repeat_guard["interaction_contract"]["agent_channel"]["required_reads"] == required_reads
    ), repeat_guard
    assert (
        repeat_guard["interaction_contract"]["cli_channel"]["required_reads"] == required_reads
    ), repeat_guard


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
    assert "vision_continuation_audit" not in guard, guard
    assert guard.get("autonomous_replan_obligation") is None, guard
    assert "required_reads" not in guard, guard
    assert "required_reads" not in guard["interaction_contract"]["agent_channel"], guard
    assert "required_reads" not in guard["interaction_contract"]["cli_channel"], guard


def assert_ready_deferred_successor_beats_monitor_quiet_skip() -> None:
    guard = build_quota_should_run(
        status_payload(
            [
                monitor_item(),
                completed_side_agent_prerequisite_with_successor(),
                ready_deferred_side_agent_successor(),
            ],
            replan_obligation=None,
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "successor_replan_required", guard
    assert guard["effective_action"] == "successor_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["normal_delivery_allowed"] is False, guard
    assert guard["interaction_contract"]["mode"] == "successor_replan_required", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard["execution_obligation"]["contract"] == "deferred_resume_projection", guard
    frontier = guard["agent_scope_frontier"]
    assert frontier["deferred_resume_candidates"][0]["todo_id"] == (
        "todo_ready_deferred_successor"
    ), frontier
    assert frontier["quiet_noop_allowed"] is False, frontier
    assert frontier["requires_replan"] is True, frontier
    goal_frontier = guard["goal_frontier_projection"]
    assert goal_frontier["monitor_only_lanes"]["present"] is True, goal_frontier
    assert goal_frontier["deferred_successors"]["ready_count"] == 1, goal_frontier
    assert goal_frontier["deferred_successors"]["current_agent_ready_count"] == 1, goal_frontier
    assert guard.get("autonomous_replan_obligation") is None, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "agent_scope_frontier: action=successor_replan_required" in markdown, markdown
    assert "agent_scope_deferred_resume_candidates" in markdown, markdown


def assert_completed_advancement_without_successor_beats_monitor_quiet_skip() -> None:
    guard = build_quota_should_run(
        status_payload(
            [
                monitor_item(),
                completed_side_agent_advancement_without_successor(),
            ],
            replan_obligation=None,
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == (
        "autonomous_replan_required"
    ), guard
    assert guard["execution_obligation"]["kind"] == "autonomous_replan_required", guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    warning = guard["agent_todo_summary"]["todo_succession_warning"]
    assert warning["reason_code"] == "completed_advancement_without_successor", guard
    assert warning["items"][0]["todo_id"] == "todo_completed_without_successor", guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["agent_id"] == SIDE_AGENT, guard
    assert obligation["triggers"][0]["kind"] == "completed_advancement_without_successor", guard
    assert obligation["triggers"][0]["todo_id"] == "todo_completed_without_successor", guard
    assert "record explicit no-follow-up" in obligation["recommended_action"], guard
    assert guard["autonomous_replan_scope"]["scope"] == "explicit_agent_owner", guard
    assert guard["autonomous_replan_scope"]["applies"] is True, guard
    frontier = guard["goal_frontier_projection"]
    assert frontier["replan_required"] is True, guard
    assert frontier["monitor_only_lanes"]["present"] is True, guard
    assert frontier["remaining_advancement_frontier"] == {
        "current_agent_claimed_advancement_count": 0,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 0,
    }, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "goal_frontier_projection: replan_required=True" in markdown, markdown
    assert "autonomous_replan_decision: decision=autonomous_replan_required" in markdown, markdown


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
    audit = guard["vision_continuation_audit"]
    assert audit["schema_version"] == "vision_continuation_audit_v0", guard
    assert audit["required"] is True, guard
    assert audit["agent_id"] == SIDE_AGENT, guard
    assert audit["selected_todo_is_goal_completion"] is False, guard
    assert audit["closeout_allowed_without_evidence"] is False, guard
    assert "todo_completion_alone" in audit["not_satisfied_by"], guard
    assert "create_successor_or_write_vision_replan_trigger_when_unproven" in (
        audit["required_before_closeout"]
    ), guard
    assert "public_safe_evidence_records" in audit["authoritative_evidence_kinds"], guard
    assert "Show the next runnable auto-research frontier" in audit["acceptance_requirements"][0], guard
    judge = audit["vision_gap_judge"]
    assert judge["schema_version"] == "vision_gap_judge_v0", guard
    assert judge["goal_id"] == "replan-decision-plane-fixture", guard
    assert judge["done"] is False, guard
    assert judge["decision"] == "continue", guard
    assert "synthetic" in judge["reason"], guard
    assert "Judge vision closure" in judge["agent_judge_instruction"], guard
    assert "evidence-log" in judge["agent_judge_instruction"], guard
    assert (
        "loopx evidence-log --goal-id replan-decision-plane-fixture "
        "--agent-id codex-side-bypass --thin"
    ) in judge["evidence_read_instruction"], guard
    assert "authoritative_evidence_satisfies_acceptance" in (
        judge["done_only_when"]
    ), guard
    assert "todo_lifecycle_or_protocol_status_is_the_only_proof" in (
        judge["continue_when"]
    ), guard
    assert judge["otherwise"] == "continue", guard
    assert guard["goal_frontier_projection"]["vision_continuation_audit"] == audit, guard
    assert guard["interaction_contract"]["agent_channel"]["vision_continuation_audit"] == audit, guard
    assert guard["interaction_contract"]["cli_channel"]["vision_continuation_audit"]["required"] is True, guard
    assert guard["interaction_contract"]["cli_channel"]["vision_continuation_audit"][
        "vision_gap_judge"
    ]["done"] is False, guard
    cli_judge = guard["interaction_contract"]["cli_channel"][
        "vision_continuation_audit"
    ]["vision_gap_judge"]
    assert "Judge vision closure" in cli_judge["agent_judge_instruction"], guard
    assert "loopx evidence-log --goal-id replan-decision-plane-fixture" in (
        cli_judge["evidence_read_instruction"]
    ), guard
    assert "todo_lifecycle_or_protocol_status_is_the_only_proof" in (
        cli_judge["continue_when"]
    ), guard
    markdown = render_quota_should_run_markdown(guard)
    assert "deferred_ready=0 acceptance_gaps=1" in markdown, markdown
    assert "vision_continuation_audit: required=True" in markdown, markdown
    assert "vision_gap_judge: done=False decision=continue" in markdown, markdown


def assert_missing_vision_checkpoint_derives_agent_scoped_replan() -> None:
    side_guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[missing_vision_checkpoint_run()],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert side_guard["decision"] == "autonomous_replan_required", side_guard
    assert side_guard["effective_action"] == "autonomous_replan_required", side_guard
    obligation = side_guard["autonomous_replan_obligation"]
    assert obligation["agent_id"] == SIDE_AGENT, side_guard
    assert obligation["triggers"][0]["kind"] == "vision_checkpoint_missing", side_guard
    gaps = side_guard["goal_frontier_projection"]["acceptance_gaps"]
    assert len(gaps) == 1, side_guard
    assert gaps[0]["kind"] == "vision_checkpoint_missing", side_guard
    assert gaps[0]["agent_id"] == SIDE_AGENT, side_guard
    assert "material_delivery_outcome" in gaps[0]["replan_trigger_summary"], side_guard
    audit = side_guard["vision_continuation_audit"]
    assert audit["required"] is True, side_guard
    assert audit["agent_id"] == SIDE_AGENT, side_guard
    assert "Write a bounded agent vision patch" in audit["acceptance_requirements"][0], side_guard
    judge = audit["vision_gap_judge"]
    assert judge["schema_version"] == "vision_gap_judge_v0", side_guard
    assert judge["goal_id"] == "replan-decision-plane-fixture", side_guard
    assert judge["done"] is False, side_guard
    assert judge["decision"] == "continue", side_guard
    assert "material_delivery_outcome" in judge["reason"], side_guard
    assert (
        side_guard["interaction_contract"]["agent_channel"]["vision_continuation_audit"]
        == audit
    ), side_guard

    primary_guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[missing_vision_checkpoint_run()],
        ),
        goal_id=GOAL_ID,
        agent_id=PRIMARY_AGENT,
    )
    primary_gaps = primary_guard["goal_frontier_projection"]["acceptance_gaps"]
    assert primary_gaps == [], primary_guard
    assert "vision_continuation_audit" not in primary_guard, primary_guard
    assert primary_guard.get("autonomous_replan_obligation") is None, primary_guard


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


def assert_agent_vision_gap_beats_replan_ack() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
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
                agent_vision_gap_run(),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    gaps = guard["goal_frontier_projection"]["acceptance_gaps"]
    assert len(gaps) == 1, guard
    assert gaps[0]["kind"] == "vision_acceptance_gap", guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    assert guard["vision_continuation_audit"]["required"] is True, guard
    assert "autonomous_replan_ack_alone" in guard["vision_continuation_audit"]["not_satisfied_by"], guard


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
    assert_ready_deferred_successor_beats_monitor_quiet_skip()
    assert_completed_advancement_without_successor_beats_monitor_quiet_skip()
    assert_replan_preserves_current_agent_runnable_frontier()
    assert_agent_vision_gap_derives_replan()
    assert_missing_vision_checkpoint_derives_agent_scoped_replan()
    assert_agent_scoped_replan_beats_agent_scope_wait()
    assert_unscoped_replan_defaults_to_primary_agent()
    assert_monitor_schedule_gap_requires_bounded_repair()
    assert_agent_ack_survives_other_agent_run_and_monitor_poll()
    assert_agent_vision_gap_beats_replan_ack()
    assert_blocking_handoff_gate_beats_derived_monitor_replan()
    print("quota-replan-decision-plane-smoke ok")


if __name__ == "__main__":
    main()
