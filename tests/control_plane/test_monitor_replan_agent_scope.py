from __future__ import annotations

from loopx.control_plane.scheduler.execution_context import (
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run


GOAL_ID = "monitor-replan-agent-scope-fixture"
AGENT_ID = "codex-quality-agent"
PEER_AGENT_ID = "codex-delivery-peer"


def _guard(
    *,
    current_agent_advancement: bool = False,
    interleaved_monitors: bool = False,
) -> dict:
    monitor_items = [
        quota_todo_item(
            todo_id="todo_stalled_monitor",
            index=1,
            title="Watch the release qualification PR.",
            task_class="continuous_monitor",
            claimed_by=AGENT_ID,
            target_key="github-pr-123",
            consecutive_no_change="2",
            cadence="30m",
            next_due_at="2099-01-01T00:00:00+00:00",
        ),
    ]
    if interleaved_monitors:
        monitor_items = [
            quota_todo_item(
                todo_id="todo_unchanged_once",
                index=1,
                title="Watch the scheduler qualification PR.",
                task_class="continuous_monitor",
                claimed_by=AGENT_ID,
                target_key="github-pr-123",
                consecutive_no_change="1",
                cadence="30m",
                next_due_at="2099-01-01T00:00:00+00:00",
            ),
            quota_todo_item(
                todo_id="todo_second_unchanged_once",
                index=2,
                title="Watch the quota qualification PR.",
                task_class="continuous_monitor",
                claimed_by=AGENT_ID,
                target_key="github-pr-234",
                consecutive_no_change="1",
                cadence="45m",
                next_due_at="2099-01-01T00:00:00+00:00",
            ),
            quota_todo_item(
                todo_id="todo_unchanged_twice",
                index=3,
                title="Watch the control-plane qualification PR.",
                task_class="continuous_monitor",
                claimed_by=AGENT_ID,
                target_key="github-pr-456",
                consecutive_no_change="2",
                cadence="1h",
                next_due_at="2099-01-01T00:00:00+00:00",
            ),
            quota_todo_item(
                todo_id="todo_peer_monitor",
                index=4,
                title="Watch an independent peer PR.",
                task_class="continuous_monitor",
                claimed_by=PEER_AGENT_ID,
                target_key="github-pr-789",
                consecutive_no_change="5",
                cadence="15m",
                next_due_at="2099-01-01T00:00:00+00:00",
            ),
        ]
    items = [
        *monitor_items,
        quota_todo_item(
            todo_id="todo_peer_advancement",
            index=5 if interleaved_monitors else 4,
            title="Advance an independent peer delivery.",
            task_class="advancement_task",
            claimed_by=PEER_AGENT_ID,
        ),
    ]
    if current_agent_advancement:
        items.append(
            quota_todo_item(
                todo_id="todo_current_advancement",
                index=3,
                title="Advance the current quality lane.",
                task_class="advancement_task",
                claimed_by=AGENT_ID,
            )
        )
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Wait for material monitor evidence.",
        agent_todos=quota_todo_summary(items),
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [AGENT_ID, PEER_AGENT_ID],
        },
    )
    return build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=(
            GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT
        ),
    )


def test_peer_advancement_does_not_suppress_current_monitor_streak_replan() -> None:
    guard = _guard()

    assert guard["decision"] == "autonomous_replan_required"
    assert guard["effective_action"] == "autonomous_replan_required"
    assert guard["should_run"] is True
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["agent_id"] == AGENT_ID
    trigger = obligation["triggers"][0]
    assert trigger["kind"] == "monitor_no_change_streak"
    assert trigger["todo_id"] == "todo_stalled_monitor"
    assert trigger["run_count"] == 2
    assert trigger["threshold"] == 2

    frontier = guard["goal_frontier_projection"]
    assert frontier["monitor_only_lanes"]["present"] is True
    assert frontier["replan_required"] is True
    assert frontier["remaining_advancement_frontier"] == {
        "current_agent_claimed_advancement_count": 0,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 1,
    }


def test_current_agent_advancement_still_preempts_monitor_streak_replan() -> None:
    guard = _guard(current_agent_advancement=True)

    assert guard["decision"] == "run"
    assert guard["effective_action"] == "normal_run"
    assert guard["work_lane_contract"]["lane"] == "advancement_task"
    assert guard.get("autonomous_replan_obligation") is None


def test_interleaved_monitors_keep_independent_no_change_streaks() -> None:
    guard = _guard(interleaved_monitors=True)

    assert guard["decision"] == "autonomous_replan_required"
    trigger = guard["autonomous_replan_obligation"]["triggers"][0]
    assert trigger == {
        "kind": "monitor_no_change_streak",
        "section": "agent_todo_summary.monitor_open_items",
        "text": (
            "monitor github-pr-456 recorded 2 consecutive unchanged polls "
            "without selectable advancement"
        ),
        "todo_id": "todo_unchanged_twice",
        "monitor_target_id": "github-pr-456",
        "run_count": 2,
        "threshold": 2,
        "agent_id": AGENT_ID,
    }
    assert [
        item["todo_id"] for item in guard["agent_todo_summary"]["monitor_open_items"]
    ] == ["todo_unchanged_once", "todo_second_unchanged_once"]
    assert guard["agent_todo_summary"]["payload_compaction"]["compacted_lanes"][
        "monitor_open_items"
    ] == {"shown": 2, "total": 3}
