#!/usr/bin/env python3
"""Smoke-test scheduled monitor lane routing without growing the large lane smoke."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.status import compact_todo_group  # noqa: E402


GOAL_ID = "monitor-scheduler-fixture"
AGENT_ID = "codex-product-capability"
PAST_DUE_AT = "2000-01-01T00:00:00+00:00"
FUTURE_DUE_AT = "2999-01-01T00:00:00+00:00"
EXPIRED_AT = "2000-01-01T00:05:00+00:00"
FRONTIER_REPLAN_ACK_RUNS = [
    {
        "classification": "monitor_scheduler_replan_ack",
        "agent_id": AGENT_ID,
        "progress_scope": "agent_lane",
        "autonomous_replan_ack": {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "fixture",
            "delta_contract": {
                "schema_version": "repair_delta_contract_v0",
                "delta_present": True,
                "delta_kinds": ["watch_lane_continuation"],
            },
        },
    }
]


def status_payload(
    *,
    agent_todo_items: list[dict],
    status: str = "monitor_scheduler_fixture",
    coordination: dict | None = None,
    latest_runs: list[dict] | None = None,
) -> dict:
    agent_todos = compact_todo_group(
        agent_todo_items,
        source_section="Agent Todo",
        role="agent",
    )
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "severity": "info",
                    "source": "project_asset",
                    "recommended_action": "Route scheduled monitor todos from structured metadata.",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                        "spent_slots": 0,
                        "state": "eligible",
                        "reason": "eligible fixture",
                    },
                    "project_asset": {
                        "next_action": "Route scheduled monitor todos from structured metadata.",
                        "stop_condition": "stop on private material",
                        "agent_todos": agent_todos,
                    },
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": status,
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "coordination": coordination
                    or {
                        "registered_agents": [AGENT_ID],
                        "primary_agent": AGENT_ID,
                    },
                    "latest_runs": latest_runs
                    if latest_runs is not None
                    else FRONTIER_REPLAN_ACK_RUNS,
                }
            ]
        },
    }


def monitor_item(
    *,
    index: int,
    todo_id: str,
    priority: str,
    target_key: str,
    next_due_at: str | None = None,
    cadence: str | None = "15m",
    claimed_by: str | None = AGENT_ID,
    expires_at: str | None = None,
) -> dict:
    item = {
        "index": index,
        "text": f"[{priority}] Monitor {target_key} and write back only material transitions.",
        "todo_id": todo_id,
        "role": "agent",
        "status": "open",
        "priority": priority,
        "task_class": "continuous_monitor",
        "action_kind": "monitor",
        "target_key": target_key,
    }
    if claimed_by:
        item["claimed_by"] = claimed_by
    if cadence:
        item["cadence"] = cadence
    if next_due_at:
        item["next_due_at"] = next_due_at
    if expires_at:
        item["expires_at"] = expires_at
    return item


def blocking_handoff_item(*, index: int, todo_id: str = "todo_primary_handoff") -> dict:
    return {
        "index": index,
        "text": "[P1] Primary review gate that blocks the product-capability lane.",
        "todo_id": todo_id,
        "role": "agent",
        "status": "open",
        "priority": "P1",
        "task_class": "advancement_task",
        "action_kind": "pr_review_merge",
        "claimed_by": "codex-main-control",
        "blocks_agent": AGENT_ID,
        "unblocks_todo_id": "todo_after_handoff",
    }


def advancement_item(*, index: int, priority: str = "P1", claimed_by: str = AGENT_ID) -> dict:
    return {
        "index": index,
        "text": f"[{priority}] Advance the runtime contract slice with validation.",
        "todo_id": f"todo_adv_{index}",
        "role": "agent",
        "status": "open",
        "priority": priority,
        "task_class": "advancement_task",
        "claimed_by": claimed_by,
    }


def guard_for(
    items: list[dict],
    *,
    agent_id: str = AGENT_ID,
    coordination: dict | None = None,
    latest_runs: list[dict] | None = None,
) -> dict:
    return build_quota_should_run(
        status_payload(
            agent_todo_items=items,
            coordination=coordination,
            latest_runs=latest_runs,
        ),
        goal_id=GOAL_ID,
        agent_id=agent_id,
    )


def assert_not_due_monitor_waits_quietly() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_monitor_wait",
                priority="P1",
                next_due_at=FUTURE_DUE_AT,
                target_key="update-note-draft-pr",
            )
        ]
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "skip", guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert lane["obligation"] == "quiet_until_material_monitor_transition", lane
    assert lane["must_attempt_work"] is False, lane
    assert guard["agent_todo_summary"]["monitor_due_count"] == 0, guard


def assert_unscheduled_monitor_requires_metadata_repair() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_monitor_unscheduled",
                priority="P1",
                target_key="update-note-draft-pr",
                cadence=None,
                next_due_at=None,
            )
        ]
    )
    lane = guard["work_lane_contract"]
    summary = guard["agent_todo_summary"]
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["monitor_kind"] == "todo_monitor_schedule_gap", lane
    assert lane["obligation"] == "repair_monitor_schedule_metadata", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["selected_todo_id"] == "todo_monitor_unscheduled", lane
    assert summary["monitor_due_count"] == 0, summary
    assert summary["monitor_schedule_gap_count"] == 1, summary
    assert summary["monitor_schedule_gap_items"][0]["todo_id"] == "todo_monitor_unscheduled", summary
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is False, guard
    assert guard["scheduler_hint"]["cadence_class"] == "active_work", guard


def assert_unscheduled_monitor_repair_survives_handoff_gates() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_monitor_unscheduled",
                priority="P1",
                target_key="update-note-draft-pr",
                cadence=None,
                next_due_at=None,
                claimed_by=None,
            ),
            blocking_handoff_item(index=2),
        ],
        coordination={
            "registered_agents": ["codex-main-control", AGENT_ID],
            "primary_agent": "codex-main-control",
        },
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert "agent_scope_frontier" not in guard, guard
    frontier_hint = guard.get("agent_lane_frontier_hint", {})
    assert frontier_hint.get("decision") != "quiet_noop_blocker", guard
    assert lane["monitor_kind"] == "todo_monitor_schedule_gap", lane
    assert lane["obligation"] == "repair_monitor_schedule_metadata", lane
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard


def assert_due_monitor_requires_explicit_attempt() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_monitor_due",
                priority="P1",
                next_due_at=PAST_DUE_AT,
                target_key="update-note-draft-pr",
            )
        ]
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert lane["monitor_kind"] == "todo_monitor_due", lane
    assert lane["obligation"] == "attempt_due_monitor", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["selected_todo_id"] == "todo_monitor_due", lane
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is False, guard


def assert_expired_monitor_does_not_catch_up() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_monitor_expired",
                priority="P1",
                next_due_at=PAST_DUE_AT,
                expires_at=EXPIRED_AT,
                target_key="expired-publish-window",
            )
        ]
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "skip", guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert lane["obligation"] == "quiet_until_material_monitor_transition", lane
    assert lane["must_attempt_work"] is False, lane
    assert guard["agent_todo_summary"]["monitor_due_count"] == 0, guard
    monitor_items = guard["agent_todo_summary"]["monitor_open_items"]
    assert monitor_items[0]["todo_id"] == "todo_monitor_expired", monitor_items
    assert monitor_items[0]["expires_at"] == EXPIRED_AT, monitor_items


def assert_due_monitor_priority_does_not_steal_advancement_lane() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_monitor_due_p2",
                priority="P2",
                next_due_at=PAST_DUE_AT,
                target_key="low-priority-watch",
            ),
            advancement_item(index=2, priority="P1"),
        ]
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo", "due_monitor_context"], lane
    assert guard["agent_todo_summary"]["monitor_due_count"] == 1, guard


def assert_read_only_projected_due_monitor_does_not_force_writeback() -> None:
    status = status_payload(
        agent_todo_items=[
            monitor_item(
                index=1,
                todo_id="todo_projected_due_monitor",
                priority="P0",
                next_due_at=PAST_DUE_AT,
                target_key="event-projected-watch",
            ),
            advancement_item(index=2, priority="P1"),
        ]
    )
    agent_todos = status["attention_queue"]["items"][0]["project_asset"]["agent_todos"]
    agent_todos["monitor_writeback"] = {
        "schema_version": "monitor_writeback_contract_v0",
        "supported": False,
        "source": "event_projection_read_model",
    }

    guard = build_quota_should_run(
        status,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert lane.get("obligation") != "attempt_due_monitor", lane
    summary = guard["agent_todo_summary"]
    assert summary["monitor_due_count"] == 0, summary
    assert summary["monitor_open_items"][0]["todo_id"] == "todo_projected_due_monitor", summary
    assert summary["monitor_writeback"]["supported"] is False, summary


def assert_due_monitor_is_not_overridden_by_side_agent_scope_wait() -> None:
    other_agent = "codex-main-control"
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_side_due_monitor",
                priority="P1",
                next_due_at=PAST_DUE_AT,
                target_key="side-agent-due-watch",
            ),
            advancement_item(index=2, priority="P1", claimed_by=other_agent),
        ],
        coordination={
            "registered_agents": [other_agent, AGENT_ID],
            "primary_agent": other_agent,
        },
    )
    lane = guard["work_lane_contract"]
    assert guard["agent_identity"]["role"] == "side-agent", guard
    assert guard["decision"] == "run", guard
    assert guard["effective_action"] == "normal_run", guard
    assert guard["should_run"] is True, guard
    assert guard["normal_delivery_allowed"] is True, guard
    assert lane["monitor_kind"] == "todo_monitor_due", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["selected_todo_id"] == "todo_side_due_monitor", lane
    assert "agent_scope_frontier" not in guard, guard
    assert "agent_lane_frontier_hint" not in guard, guard
    claim_scope = guard["agent_todo_summary"]["claim_scope"]
    assert claim_scope["other_agent_claimed_open_count"] == 1, claim_scope
    assert claim_scope["other_agent_claimed_weight"] == "diagnostic_only", claim_scope
    contract = guard["interaction_contract"]
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is False, contract


def assert_multiple_due_monitor_cap_and_order() -> None:
    guard = guard_for(
        [
            monitor_item(
                index=5,
                todo_id="todo_monitor_due_p1",
                priority="P1",
                next_due_at=PAST_DUE_AT,
                target_key="p1-watch",
            ),
            monitor_item(
                index=9,
                todo_id="todo_monitor_due_p0_late",
                priority="P0",
                next_due_at=PAST_DUE_AT,
                target_key="p0-late-watch",
            ),
            monitor_item(
                index=3,
                todo_id="todo_monitor_due_p0_first",
                priority="P0",
                next_due_at=PAST_DUE_AT,
                target_key="p0-first-watch",
            ),
        ]
    )
    lane = guard["work_lane_contract"]
    assert lane["obligation"] == "attempt_due_monitor", lane
    assert lane["monitor_due_count"] == 3, lane
    assert len(lane["monitor_due_items"]) == 1, lane
    assert lane["monitor_due_items"][0]["todo_id"] == "todo_monitor_due_p0_first", lane
    assert lane["selected_todo_id"] == "todo_monitor_due_p0_first", lane
    assert guard["agent_todo_summary"]["monitor_due_count"] == 3, guard
    assert len(guard["agent_todo_summary"]["monitor_due_items"]) == 1, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_monitor_due: count=3" in markdown, markdown


def assert_other_agent_due_monitor_does_not_preempt_current_agent_lane() -> None:
    other_agent = "codex-main-control"
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_other_due_monitor",
                priority="P0",
                next_due_at=PAST_DUE_AT,
                target_key="other-agent-watch",
                claimed_by=other_agent,
            ),
            advancement_item(index=2, priority="P1"),
        ],
        coordination={
            "registered_agents": [other_agent, AGENT_ID],
            "primary_agent": other_agent,
        },
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert lane.get("monitor_due_count", 0) == 0, lane
    assert "monitor_due_items" not in lane, lane
    assert guard["agent_todo_summary"]["monitor_due_count"] == 0, guard
    claim_scope = guard["agent_todo_summary"]["claim_scope"]
    assert claim_scope["other_agent_claimed_open_count"] == 1, claim_scope
    assert claim_scope["other_agent_claimed_items"][0]["todo_id"] == "todo_other_due_monitor", claim_scope
    assert guard["recommended_action"] == advancement_item(index=2, priority="P1")["text"], guard


def assert_other_agent_claimed_work_stays_diagnostic_when_no_current_lane() -> None:
    other_agent = "codex-main-control"
    guard = guard_for(
        [
            monitor_item(
                index=1,
                todo_id="todo_other_due_monitor",
                priority="P0",
                next_due_at=PAST_DUE_AT,
                target_key="other-agent-watch",
                claimed_by=other_agent,
            ),
            advancement_item(index=2, priority="P0", claimed_by=other_agent),
        ],
        coordination={
            "registered_agents": [other_agent, AGENT_ID],
            "primary_agent": other_agent,
        },
    )
    summary = guard["agent_todo_summary"]
    lane = guard.get("work_lane_contract") or {}
    assert summary["open_count"] == 0, summary
    assert summary["first_executable_items"] == [], summary
    assert summary["monitor_due_count"] == 0, summary
    assert lane.get("must_attempt_work") is not True, lane
    claim_scope = summary["claim_scope"]
    assert claim_scope["selectable_open_count"] == 0, claim_scope
    assert claim_scope["other_agent_claimed_open_count"] == 2, claim_scope
    assert claim_scope["other_agent_claimed_weight"] == "diagnostic_only", claim_scope
    assert guard["recommended_action"] != advancement_item(index=2, priority="P0", claimed_by=other_agent)["text"], guard


def main() -> int:
    assert_not_due_monitor_waits_quietly()
    assert_unscheduled_monitor_requires_metadata_repair()
    assert_unscheduled_monitor_repair_survives_handoff_gates()
    assert_due_monitor_requires_explicit_attempt()
    assert_expired_monitor_does_not_catch_up()
    assert_due_monitor_priority_does_not_steal_advancement_lane()
    assert_read_only_projected_due_monitor_does_not_force_writeback()
    assert_due_monitor_is_not_overridden_by_side_agent_scope_wait()
    assert_multiple_due_monitor_cap_and_order()
    assert_other_agent_due_monitor_does_not_preempt_current_agent_lane()
    assert_other_agent_claimed_work_stays_diagnostic_when_no_current_lane()
    print("monitor-scheduler-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
