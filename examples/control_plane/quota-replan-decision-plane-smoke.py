#!/usr/bin/env python3
"""Smoke-test autonomous replan isolation from local lane quiet/wait state."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import (  # noqa: E402
    AUTONOMOUS_REPLAN_ACK_NEUTRAL_CLASSIFICATIONS,
    build_quota_should_run,
    render_quota_should_run_markdown,
)
from loopx.control_plane.goals.goal_frontier import (  # noqa: E402
    build_goal_frontier_projection_context_from_status,
)
from loopx.control_plane.scheduler.execution_context import (  # noqa: E402
    scheduler_execution_context_for_runtime_profile,
)
from loopx.control_plane.todos.quota_summary import (  # noqa: E402
    select_quota_todo_summary,
)
from loopx.status import build_autonomous_replan_obligation, compact_todo_group  # noqa: E402


GOAL_ID = "replan-decision-plane-fixture"
PRIMARY_AGENT = "codex-main-control"
SIDE_AGENT = "codex-side-bypass"
FUTURE_DUE_AT = "2999-01-01T00:00:00+00:00"
APP_SCHEDULER_CONTEXT = scheduler_execution_context_for_runtime_profile(
    "codex_app_heartbeat"
)


GLOBAL_REPLAN_OBLIGATION = {
    "schema_version": "autonomous_replan_obligation_v0",
    "required": True,
    "stall_threshold": 2,
    "trigger_count": 1,
    "triggers": [{"kind": "periodic_review_due", "source": "fixture"}],
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


def primary_excluded_unclaimed_advancement() -> dict:
    item = primary_claimed_advancement()
    item.pop("claimed_by")
    item["excluded_agents"] = [SIDE_AGENT]
    return item


def primary_owned_lifecycle_monitor() -> dict:
    item = monitor_item()
    item["claimed_by"] = PRIMARY_AGENT
    item["excluded_agents"] = [SIDE_AGENT]
    return item


def side_agent_claimed_advancement(
    *,
    index: int = 2,
    todo_id: str = "todo_side_canary_refactor",
    text: str = "[P1] Continue the next non-benchmark canary/refactor batch.",
) -> dict:
    return {
        "index": index,
        "todo_id": todo_id,
        "text": text,
        "role": "agent",
        "status": "open",
        "priority": "P1",
        "task_class": "advancement_task",
        "action_kind": "canary_refactor_next_batch",
        "claimed_by": SIDE_AGENT,
    }


def long_side_agent_todo_chain() -> list[dict]:
    return [
        side_agent_claimed_advancement(
            index=index,
            todo_id=f"todo_side_chain_{index:02d}",
            text=f"[P1] Continue long-chain fixture slice {index}.",
        )
        for index in range(1, 16)
    ]


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
        "continuation_policy": "independent_handoff",
        "claimed_by": PRIMARY_AGENT,
        "excluded_agents": [SIDE_AGENT],
        "unblocks_todo_id": "todo_monitor_wait",
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
                    "coordination": {
                        "agent_model": "peer_v1",
                        "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
                    },
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
                        "agent_model": "peer_v1",
                        "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
                    },
                    "latest_runs": latest_runs or [],
                }
            ]
        },
    }


def peer_status_payload(
    agent_todo_items: list[dict],
    *,
    replan_obligation: dict | None = GLOBAL_REPLAN_OBLIGATION,
) -> dict:
    payload = status_payload(
        agent_todo_items,
        replan_obligation=replan_obligation,
    )
    coordination = {
        "agent_model": "peer_v1",
        "registered_agents": [PRIMARY_AGENT, SIDE_AGENT],
    }
    payload["attention_queue"]["items"][0]["coordination"] = coordination
    payload["run_history"]["goals"][0]["coordination"] = coordination
    return payload


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


def closed_agent_vision_run(*, state: str = "vision_closed") -> dict:
    run = agent_vision_gap_run()
    run["generated_at"] = "2026-07-04T00:10:00+00:00"
    run["classification"] = "vision_gap_closed"
    run["agent_vision"]["state"] = state
    return run


def agent_vision_acceptance_only_run(
    *,
    advancement_policy: str | None = None,
) -> dict:
    vision_patch = {
        "acceptance_summary": "A visible successor frontier must exist before the lane is monitor-only.",
    }
    if advancement_policy:
        vision_patch["advancement_policy"] = advancement_policy
    return {
        "classification": "state_refreshed",
        "generated_at": "2026-07-04T00:00:00+00:00",
        "agent_id": SIDE_AGENT,
        "progress_scope": "agent_lane",
        "agent_vision": {
            "schema_version": "goal_vision_replan_contract_v0",
            "agent_id": SIDE_AGENT,
            "state": "vision_patch_proposed",
            "vision_patch": vision_patch,
            "todo_delta": [],
            "vision_budget": {
                "schema_version": "goal_vision_budget_v0",
                "status": "ok",
            },
        },
    }


def watch_lane_continuation_ack_run(
    *,
    delta_kinds: list[str] | None = None,
) -> dict:
    return {
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
                "delta_kinds": delta_kinds or ["watch_lane_continuation"],
            },
        },
    }


def material_progress_runs_after_replan_ack(count: int) -> list[dict]:
    return [
        {
            "classification": "benchmark_rotation_iteration",
            "generated_at": f"2026-07-04T00:{minute:02d}:00+00:00",
            "agent_id": SIDE_AGENT,
            "progress_scope": "agent_lane",
            "delivery_outcome": "outcome_progress",
        }
        for minute in range(count, 0, -1)
    ]


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


def satisfied_vision_checkpoint_run(*, decision: str, agent_id: str = SIDE_AGENT) -> dict:
    checkpoint: dict = {
        "schema_version": "vision_checkpoint_v0",
        "agent_id": agent_id,
        "required": True,
        "satisfied": True,
        "decision": decision,
        "triggers": [
            {
                "kind": "material_delivery_outcome",
                "delivery_outcome": "outcome_progress",
            }
        ],
    }
    if decision == "unchanged_with_reason":
        checkpoint["unchanged_reason"] = "The current per-agent vision still applies."
    if decision == "retired_or_superseded":
        checkpoint["repair_delta_kinds"] = ["no_followup"]
    return {
        "classification": f"vision_checkpoint_{decision}",
        "generated_at": "2026-07-04T00:10:00+00:00",
        "agent_id": agent_id,
        "progress_scope": "agent_lane",
        "delivery_outcome": "outcome_progress",
        "vision_checkpoint": checkpoint,
    }


def projected_autonomous_replan_ack(
    delta_kinds: list[str],
    *,
    agent_id: str | None = None,
) -> dict:
    ack = {
        "schema_version": "autonomous_replan_ack_v0",
        "recorded": True,
        "source": "refresh_state",
        "delta_contract": {
            "schema_version": "repair_delta_contract_v0",
            "delta_present": True,
            "delta_kinds": delta_kinds,
        },
    }
    if agent_id:
        ack["agent_id"] = agent_id
    return ack


def assert_frontier_delta_ack_clears_existing_replan_obligation() -> None:
    payload = status_payload(
        [side_agent_claimed_advancement()],
        replan_obligation=SIDE_AGENT_REPLAN_OBLIGATION,
        latest_runs=[
            {
                "classification": "autonomous_replan_recorded",
                "agent_id": SIDE_AGENT,
                "progress_scope": "goal",
                "delivery_outcome": "outcome_progress",
                "autonomous_replan_ack": projected_autonomous_replan_ack(
                    ["runnable_todo_set", "successor_or_supersede"],
                    agent_id=SIDE_AGENT,
                ),
            }
        ],
    )
    guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["effective_action"] == "normal_run", guard
    assert guard["normal_delivery_allowed"] is True, guard
    assert guard.get("autonomous_replan_obligation") is None, guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard


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
    assert required_reads[0]["todo_id"] is None, required_reads
    assert "evidence-log" in required_reads[0]["command"], required_reads
    assert " --agent-id codex-side-bypass " in f" {required_reads[0]['command']} ", required_reads
    assert "--todo-id" not in required_reads[0]["command"], required_reads
    assert "across this agent lane" in required_reads[0]["reason"], required_reads
    assert "public-safe search" in required_reads[0]["reason"], required_reads
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


def assert_future_scheduled_monitor_requires_replan_without_frontier_delta() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item()], replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == (
        "autonomous_replan_required"
    ), guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["triggers"][0]["kind"] == "frontier_exhausted_monitor_lane", guard
    assert obligation["triggers"][0]["future_monitor_schedule_present"] is True, guard
    assert "watch-lane continuation" in obligation["recommended_action"], guard
    assert "required_reads" in guard, guard
    assert "required_reads" in guard["interaction_contract"]["agent_channel"], guard
    assert "required_reads" in guard["interaction_contract"]["cli_channel"], guard


def assert_due_monitor_requires_replan_without_advancement_frontier() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item(next_due_at="2000-01-01T00:00:00+00:00")],
            replan_obligation=None,
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    assert guard["goal_frontier_projection"]["monitor_only_lanes"]["present"] is True, guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["triggers"][0]["kind"] == "frontier_exhausted_monitor_lane", guard
    assert obligation["triggers"][0]["future_monitor_schedule_present"] is False, guard


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


def assert_long_agent_todo_chain_derives_replan_before_linear_delivery() -> None:
    guard = build_quota_should_run(
        status_payload(long_side_agent_todo_chain(), replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["should_run"] is True, guard
    assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["agent_id"] == SIDE_AGENT, guard
    assert obligation["triggers"][0]["kind"] == "long_todo_chain", guard
    assert obligation["stall_threshold"] == 15, guard
    assert obligation["trigger_count"] == 15, guard
    assert "run_bounded_public_research_if_local_evidence_is_missing" in (
        obligation["guidance_actions"]
    ), guard
    assert "group/prune" in obligation["recommended_action"], guard
    frontier = guard["goal_frontier_projection"]["remaining_advancement_frontier"]
    assert frontier["current_agent_claimed_advancement_count"] == 15, guard
    assert frontier["unclaimed_advancement_count"] == 0, guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard
    assert guard["autonomous_replan_decision"]["triggers"] == ["long_todo_chain"], guard
    required_reads = guard["required_reads"]
    assert required_reads[0]["kind"] == "agent_scoped_evidence_log", required_reads
    assert required_reads[0]["todo_id"] is None, required_reads
    assert "--todo-id" not in required_reads[0]["command"], required_reads
    markdown = render_quota_should_run_markdown(guard)
    assert "triggers=long_todo_chain" in markdown, markdown


def assert_material_progress_does_not_immediately_invalidate_long_chain_replan_ack() -> None:
    guard = build_quota_should_run(
        status_payload(
            long_side_agent_todo_chain(),
            replan_obligation=None,
            latest_runs=[
                *material_progress_runs_after_replan_ack(1),
                watch_lane_continuation_ack_run(
                    delta_kinds=["runnable_todo_set", "monitor_target"]
                ),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert "autonomous_replan_obligation" not in guard, guard


def assert_long_chain_replan_ack_expires_after_material_review_window() -> None:
    guard = build_quota_should_run(
        status_payload(
            long_side_agent_todo_chain(),
            replan_obligation=None,
            latest_runs=[
                *material_progress_runs_after_replan_ack(20),
                watch_lane_continuation_ack_run(
                    delta_kinds=["runnable_todo_set", "monitor_target"]
                ),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["autonomous_replan_obligation"]["triggers"][0]["kind"] == (
        "long_todo_chain"
    ), guard


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
    assert "public_web_research_findings" in audit["authoritative_evidence_kinds"], guard
    assert "Show the next runnable auto-research frontier" in audit["acceptance_requirements"][0], guard
    judge = audit["vision_gap_judge"]
    assert judge["schema_version"] == "vision_gap_judge_v0", guard
    assert judge["goal_id"] == "replan-decision-plane-fixture", guard
    assert judge["done"] is False, guard
    assert judge["decision"] == "continue", guard
    assert "synthetic" in judge["reason"], guard
    assert "Judge vision closure" in judge["agent_judge_instruction"], guard
    assert "evidence-log" in judge["agent_judge_instruction"], guard
    assert "public web research" in judge["agent_judge_instruction"], guard
    assert "primary or authoritative sources" in (
        judge["external_research_instruction"]
    ), guard
    assert "source_url_or_public_reference" in (
        judge["research_writeback_required_when_used"]
    ), guard
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


def assert_closed_agent_vision_allows_bounded_monitor_wait() -> None:
    for state in ("vision_closed", "vision_satisfied", "closed_no_followup"):
        guard = build_quota_should_run(
            status_payload(
                [monitor_item()],
                replan_obligation=None,
                latest_runs=[
                    watch_lane_continuation_ack_run(
                        delta_kinds=["watch_lane_continuation", "no_followup"]
                    ),
                    closed_agent_vision_run(state=state),
                ],
            ),
            goal_id=GOAL_ID,
            agent_id=SIDE_AGENT,
        )
        assert guard["decision"] == "skip", (state, guard)
        assert guard["effective_action"] == "monitor_quiet_skip", (state, guard)
        assert guard["goal_frontier_projection"]["acceptance_gaps"] == [], (
            state,
            guard,
        )
        assert guard["goal_frontier_projection"]["replan_required"] is False, (
            state,
            guard,
        )
        assert guard.get("autonomous_replan_obligation") is None, (state, guard)


def assert_generic_replan_ack_does_not_silence_empty_monitor_frontier() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
                watch_lane_continuation_ack_run(
                    delta_kinds=[
                        "active_state_next_action",
                        "goal_vision_patch",
                        "no_followup",
                    ]
                ),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    frontier = guard["goal_frontier_projection"]
    assert frontier["monitor_only_lanes"]["present"] is True, frontier
    assert frontier["replan_required"] is True, frontier
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["triggers"][0]["kind"] == "frontier_exhausted_monitor_lane", guard


def assert_custom_agent_vision_state_remains_open() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[closed_agent_vision_run(state="completed_current_slice")],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert len(guard["goal_frontier_projection"]["acceptance_gaps"]) == 1, guard


def assert_goal_frontier_context_helper_matches_quota_payload() -> None:
    payload = status_payload(
        [monitor_item()],
        replan_obligation=None,
        latest_runs=[agent_vision_gap_run()],
    )
    guard = build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=SIDE_AGENT)
    item = payload["attention_queue"]["items"][0]
    context = build_goal_frontier_projection_context_from_status(
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
        status_payload=payload,
        item=item,
        project_asset=item["project_asset"],
        user_todo_summary=select_quota_todo_summary(
            item.get("user_todos"),
            item.get("project_asset", {}).get("user_todos"),
            agent_identity=guard["agent_identity"],
            filter_user_gate_blocks_agent=True,
        ),
        agent_todo_summary=guard["agent_todo_summary"],
        work_lane_contract=guard["work_lane_contract"],
        neutral_replan_ack_classifications=AUTONOMOUS_REPLAN_ACK_NEUTRAL_CLASSIFICATIONS,
    )
    context_obligation = dict(context["replan_obligation"])
    guard_obligation = dict(guard["autonomous_replan_obligation"])
    guard_obligation.pop("required_reads", None)
    assert context_obligation == guard_obligation, guard
    assert context["replan_scope"] == guard["autonomous_replan_scope"], guard
    assert context["goal_frontier_projection"] == guard["goal_frontier_projection"], guard
    assert context["acceptance_gaps"] == guard["goal_frontier_projection"]["acceptance_gaps"], guard


def assert_open_agent_vision_uses_watch_lane_continuation_ack() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
                watch_lane_continuation_ack_run(),
                agent_vision_acceptance_only_run(),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "skip", guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    gaps = guard["goal_frontier_projection"]["acceptance_gaps"]
    assert len(gaps) == 1, guard
    assert gaps[0]["kind"] == "vision_acceptance_gap", guard
    assert gaps[0]["acceptance_summary"].startswith("A visible successor"), guard
    assert gaps[0]["replan_trigger_source"] == "implicit_open_acceptance", guard
    assert "acceptance evidence still required" in (
        gaps[0]["replan_trigger_summary"]
    ), guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard
    assert guard["vision_continuation_audit"]["required"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is True, (
        guard
    )


def assert_due_monitor_runs_under_watched_open_agent_vision() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item(next_due_at="2000-01-01T00:00:00+00:00")],
            replan_obligation=None,
            latest_runs=[
                watch_lane_continuation_ack_run(),
                agent_vision_acceptance_only_run(),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    lane = guard["work_lane_contract"]
    assert lane["obligation"] == "attempt_due_monitor", guard
    assert lane["selected_todo_id"] == "todo_monitor_wait", guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard
    assert guard["vision_continuation_audit"]["required"] is True, guard


def assert_repeat_advancement_vision_beats_watch_lane_continuation_ack() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
                watch_lane_continuation_ack_run(),
                agent_vision_acceptance_only_run(
                    advancement_policy="repeat_until_closed"
                ),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    gap = guard["goal_frontier_projection"]["acceptance_gaps"][0]
    assert gap["advancement_policy"] == "repeat_until_closed", guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["triggers"][0]["advancement_policy"] == (
        "repeat_until_closed"
    ), guard


def assert_repeat_advancement_vision_replans_past_peer_only_work() -> None:
    guard = build_quota_should_run(
        status_payload(
            [
                primary_owned_lifecycle_monitor(),
                primary_excluded_unclaimed_advancement(),
            ],
            replan_obligation=None,
            latest_runs=[
                agent_vision_acceptance_only_run(
                    advancement_policy="repeat_until_closed"
                ),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )

    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    frontier = guard["goal_frontier_projection"]["remaining_advancement_frontier"]
    assert frontier["current_agent_claimed_advancement_count"] == 0, guard
    assert frontier["unclaimed_advancement_count"] == 0, guard
    assert guard["agent_todo_summary"]["claim_scope"]["executor_excluded_self_count"] == 2, guard
    monitors = guard["agent_todo_summary"]["claimed_monitor_open_items"]
    assert monitors[0]["todo_id"] == "todo_monitor_wait", guard
    route_hint = guard["goal_route_hint"]
    assert route_hint["counts"]["unclaimed_advancement_count"] == 0, guard
    assert "unclaimed_next_actions" not in route_hint, guard
    action = guard["autonomous_replan_obligation"]["todo_actions"][0]
    assert action["action"] == "add", guard
    assert "next runnable" in action["text"], guard


def assert_required_profile_without_vision_replans_past_peer_only_work() -> None:
    payload = status_payload(
        [monitor_item(), primary_claimed_advancement()],
        replan_obligation=None,
    )
    profile = {
        "schema_version": "agent_profile_v1",
        "agent_id": SIDE_AGENT,
        "profile_role": "quality-qualification",
        "scope_summary": "Continuous qualification and maintainability work.",
        "default_task_classes": ["advancement_task", "continuous_monitor"],
    }
    for coordination in (
        payload["attention_queue"]["items"][0]["coordination"],
        payload["run_history"]["goals"][0]["coordination"],
    ):
        coordination["agent_profiles"] = {SIDE_AGENT: profile}

    guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )

    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["agent_identity"]["agent_profile"]["vision_requirement"] == (
        "required"
    ), guard
    gaps = guard["goal_frontier_projection"]["acceptance_gaps"]
    assert gaps[0]["kind"] == "required_agent_vision_missing", guard
    assert gaps[0]["source"] == "agent_profile", guard
    frontier = guard["goal_frontier_projection"]["remaining_advancement_frontier"]
    assert frontier == {
        "current_agent_claimed_advancement_count": 0,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 1,
    }, guard
    assert "agent_scope_frontier" not in guard, guard

    profile["vision_requirement"] = "optional"
    optional_guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert optional_guard["decision"] != "autonomous_replan_required", optional_guard
    assert optional_guard["goal_frontier_projection"]["acceptance_gaps"] == [], (
        optional_guard
    )


def assert_repeat_advancement_vision_accepts_runnable_successor() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item(), side_agent_claimed_advancement()],
            replan_obligation=None,
            latest_runs=[
                watch_lane_continuation_ack_run(),
                agent_vision_acceptance_only_run(
                    advancement_policy="repeat_until_closed"
                ),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard


def assert_non_watch_replan_ack_does_not_suppress_open_agent_vision() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
                watch_lane_continuation_ack_run(
                    delta_kinds=["runnable_todo_set"]
                ),
                agent_vision_acceptance_only_run(),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["triggers"][0]["kind"] == "vision_acceptance_gap", guard


def assert_open_agent_vision_with_runnable_frontier_uses_neutral_gap_trigger() -> None:
    guard = build_quota_should_run(
        status_payload(
            [monitor_item(), side_agent_claimed_advancement()],
            replan_obligation=None,
            latest_runs=[agent_vision_acceptance_only_run()],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    frontier = guard["goal_frontier_projection"]["remaining_advancement_frontier"]
    assert frontier["current_agent_claimed_advancement_count"] == 1, guard
    gaps = guard["goal_frontier_projection"]["acceptance_gaps"]
    assert len(gaps) == 1, guard
    trigger = gaps[0]["replan_trigger_summary"]
    assert "acceptance evidence still required" in trigger, guard
    assert "without a runnable advancement frontier" not in trigger, guard
    assert guard["vision_continuation_audit"]["required"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["primary_action"].startswith(
        "todo_side_canary_refactor:"
    ), guard


def assert_retired_agent_vision_allows_bounded_monitor_wait() -> None:
    retired_run = satisfied_vision_checkpoint_run(decision="retired_or_superseded")
    retired_run["autonomous_replan_ack"] = watch_lane_continuation_ack_run(
        delta_kinds=["watch_lane_continuation", "no_followup"]
    )["autonomous_replan_ack"]
    guard = build_quota_should_run(
        status_payload(
            [monitor_item()],
            replan_obligation=None,
            latest_runs=[
                retired_run,
                agent_vision_acceptance_only_run(),
            ],
        ),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "skip", guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert guard["goal_frontier_projection"]["acceptance_gaps"] == [], guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard


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


def assert_satisfied_vision_checkpoint_supersedes_older_missing_but_not_empty_frontier() -> None:
    for decision in ("patched", "unchanged_with_reason", "retired_or_superseded"):
        guard = build_quota_should_run(
            status_payload(
                [monitor_item()],
                replan_obligation=None,
                latest_runs=[
                    satisfied_vision_checkpoint_run(decision=decision),
                    missing_vision_checkpoint_run(),
                ],
            ),
            goal_id=GOAL_ID,
            agent_id=SIDE_AGENT,
        )
        assert guard["decision"] == "autonomous_replan_required", guard
        assert guard["effective_action"] == "autonomous_replan_required", guard
        assert guard["should_run"] is True, guard
        assert guard["interaction_contract"]["mode"] == "autonomous_replan", guard
        assert guard["goal_frontier_projection"]["acceptance_gaps"] == [], guard
        assert guard["goal_frontier_projection"]["replan_required"] is True, guard
        assert guard["autonomous_replan_obligation"]["triggers"][0]["kind"] == (
            "frontier_exhausted_monitor_lane"
        ), guard
        assert guard.get("vision_continuation_audit") is None, guard


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


def assert_unscoped_peer_replan_has_one_deterministic_owner() -> None:
    payload = peer_status_payload([primary_claimed_advancement()])
    guards = {
        agent_id: build_quota_should_run(
            payload,
            goal_id=GOAL_ID,
            agent_id=agent_id,
        )
        for agent_id in (PRIMARY_AGENT, SIDE_AGENT)
    }
    selected = {
        guard["autonomous_replan_scope"]["selected_peer_agent"]
        for guard in guards.values()
    }
    assert len(selected) == 1, guards
    selected_agent = selected.pop()
    assert selected_agent in guards, guards

    selected_guard = guards[selected_agent]
    assert selected_guard["agent_identity"]["agent_model"] == "peer_v1", selected_guard
    assert "role" not in selected_guard["agent_identity"], selected_guard
    assert "primary_agent" not in selected_guard["agent_identity"], selected_guard
    assert selected_guard["decision"] == "autonomous_replan_required", selected_guard
    assert selected_guard["effective_action"] == "autonomous_replan_required", selected_guard
    assert selected_guard["autonomous_replan_scope"]["scope"] == (
        "deterministic_peer_assignment"
    ), selected_guard
    assert selected_guard["autonomous_replan_scope"]["applies"] is True, selected_guard
    assert "primary_agent_id" not in selected_guard["autonomous_replan_scope"], selected_guard

    waiting_agent = next(agent for agent in guards if agent != selected_agent)
    waiting_guard = guards[waiting_agent]
    assert waiting_guard["autonomous_replan_scope"]["scope"] == (
        "deterministic_peer_assignment"
    ), waiting_guard
    assert waiting_guard["autonomous_replan_scope"]["applies"] is False, waiting_guard
    assert waiting_guard.get("autonomous_replan_obligation") is None, waiting_guard
    assert waiting_guard["effective_action"] != "autonomous_replan_required", waiting_guard

    reversed_payload = peer_status_payload([primary_claimed_advancement()])
    reversed_payload["attention_queue"]["items"][0]["coordination"][
        "registered_agents"
    ].reverse()
    reversed_payload["run_history"]["goals"][0]["coordination"][
        "registered_agents"
    ].reverse()
    reversed_guard = build_quota_should_run(
        reversed_payload,
        goal_id=GOAL_ID,
        agent_id=selected_agent,
    )
    assert reversed_guard["autonomous_replan_scope"]["selected_peer_agent"] == (
        selected_agent
    ), reversed_guard


def assert_state_replan_follows_claimed_frontier_not_monitor_peer() -> None:
    items = [primary_claimed_advancement(), monitor_item()]
    agent_todos = compact_todo_group(
        items,
        source_section="Agent Todo",
        role="agent",
    )
    obligation = build_autonomous_replan_obligation(
        [
            {
                "kind": "no_progress_streak",
                "section": "Next Action",
                "text": "Keep the primary peer's blocked action fail-closed.",
            }
        ],
        agent_todos=agent_todos,
    )
    assert obligation is not None, obligation
    assert obligation["agent_id"] == PRIMARY_AGENT, obligation

    payload = status_payload(items, replan_obligation=obligation)
    primary_guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=PRIMARY_AGENT,
    )
    assert primary_guard["effective_action"] == "autonomous_replan_required", primary_guard
    assert primary_guard["autonomous_replan_scope"]["scope"] == (
        "explicit_agent_owner"
    ), primary_guard

    monitor_guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert monitor_guard.get("autonomous_replan_obligation") is None, monitor_guard
    assert monitor_guard["effective_action"] == "monitor_quiet_skip", monitor_guard
    assert monitor_guard["interaction_contract"]["mode"] == "monitor_quiet_skip", monitor_guard


def assert_monitor_schedule_gap_requires_bounded_repair() -> None:
    guard = build_quota_should_run(
        status_payload([monitor_item(cadence=None, next_due_at=None)], replan_obligation=None),
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
        scheduler_execution_context=APP_SCHEDULER_CONTEXT,
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


def assert_non_frontier_replan_ack_does_not_clear_monitor_replan() -> None:
    for delta_kinds in (["interaction_contract"], ["unknown_delta_kind"], []):
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
                                "delta_kinds": delta_kinds,
                            },
                        },
                    },
                ],
            ),
            goal_id=GOAL_ID,
            agent_id=SIDE_AGENT,
        )
        assert guard["decision"] == "autonomous_replan_required", guard
        assert guard["effective_action"] == "autonomous_replan_required", guard
        assert guard["goal_frontier_projection"]["replan_required"] is True, guard
        obligation = guard["autonomous_replan_obligation"]
        assert obligation["triggers"][0]["kind"] == "frontier_exhausted_monitor_lane", guard


def assert_projected_replan_ack_is_agent_scoped() -> None:
    unscoped_payload = status_payload([monitor_item()], replan_obligation=None)
    unscoped_item = unscoped_payload["attention_queue"]["items"][0]
    unscoped_item["autonomous_replan_ack"] = projected_autonomous_replan_ack(
        ["no_followup"]
    )
    unscoped_item["project_asset"]["autonomous_replan_ack"] = projected_autonomous_replan_ack(
        ["no_followup"],
        agent_id=PRIMARY_AGENT,
    )
    guard = build_quota_should_run(
        unscoped_payload,
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["effective_action"] == "autonomous_replan_required", guard
    assert guard["goal_frontier_projection"]["replan_required"] is True, guard

    scoped_payload = status_payload([monitor_item()], replan_obligation=None)
    scoped_item = scoped_payload["attention_queue"]["items"][0]
    scoped_ack = projected_autonomous_replan_ack(
        ["watch_lane_continuation"],
        agent_id=SIDE_AGENT,
    )
    scoped_item["autonomous_replan_ack"] = scoped_ack
    scoped_item["project_asset"]["autonomous_replan_ack"] = scoped_ack
    scoped_guard = build_quota_should_run(
        scoped_payload,
        goal_id=GOAL_ID,
        agent_id=SIDE_AGENT,
    )
    assert scoped_guard["decision"] == "skip", scoped_guard
    assert scoped_guard["effective_action"] == "monitor_quiet_skip", scoped_guard
    assert scoped_guard["goal_frontier_projection"]["replan_required"] is False, scoped_guard


def assert_explicit_as_needed_vision_gap_uses_watch_lane_continuation_ack() -> None:
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
    assert guard["decision"] == "skip", guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    gaps = guard["goal_frontier_projection"]["acceptance_gaps"]
    assert len(gaps) == 1, guard
    assert gaps[0]["kind"] == "vision_acceptance_gap", guard
    assert gaps[0]["replan_trigger_source"] == "explicit_vision_trigger", guard
    assert guard["goal_frontier_projection"]["replan_required"] is False, guard
    assert guard.get("autonomous_replan_obligation") is None, guard
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
    assert_frontier_delta_ack_clears_existing_replan_obligation()
    assert_future_scheduled_monitor_requires_replan_without_frontier_delta()
    assert_due_monitor_requires_replan_without_advancement_frontier()
    assert_ready_deferred_successor_beats_monitor_quiet_skip()
    assert_completed_advancement_without_successor_beats_monitor_quiet_skip()
    assert_replan_preserves_current_agent_runnable_frontier()
    assert_long_agent_todo_chain_derives_replan_before_linear_delivery()
    assert_material_progress_does_not_immediately_invalidate_long_chain_replan_ack()
    assert_long_chain_replan_ack_expires_after_material_review_window()
    assert_agent_vision_gap_derives_replan()
    assert_closed_agent_vision_allows_bounded_monitor_wait()
    assert_generic_replan_ack_does_not_silence_empty_monitor_frontier()
    assert_custom_agent_vision_state_remains_open()
    assert_goal_frontier_context_helper_matches_quota_payload()
    assert_open_agent_vision_uses_watch_lane_continuation_ack()
    assert_due_monitor_runs_under_watched_open_agent_vision()
    assert_repeat_advancement_vision_beats_watch_lane_continuation_ack()
    assert_repeat_advancement_vision_replans_past_peer_only_work()
    assert_required_profile_without_vision_replans_past_peer_only_work()
    assert_repeat_advancement_vision_accepts_runnable_successor()
    assert_non_watch_replan_ack_does_not_suppress_open_agent_vision()
    assert_open_agent_vision_with_runnable_frontier_uses_neutral_gap_trigger()
    assert_retired_agent_vision_allows_bounded_monitor_wait()
    assert_missing_vision_checkpoint_derives_agent_scoped_replan()
    assert_satisfied_vision_checkpoint_supersedes_older_missing_but_not_empty_frontier()
    assert_agent_scoped_replan_beats_agent_scope_wait()
    assert_unscoped_peer_replan_has_one_deterministic_owner()
    assert_state_replan_follows_claimed_frontier_not_monitor_peer()
    assert_monitor_schedule_gap_requires_bounded_repair()
    assert_agent_ack_survives_other_agent_run_and_monitor_poll()
    assert_non_frontier_replan_ack_does_not_clear_monitor_replan()
    assert_projected_replan_ack_is_agent_scoped()
    assert_explicit_as_needed_vision_gap_uses_watch_lane_continuation_ack()
    assert_blocking_handoff_gate_beats_derived_monitor_replan()
    print("quota-replan-decision-plane-smoke ok")


if __name__ == "__main__":
    main()
