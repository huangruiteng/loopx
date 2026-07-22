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


def _combined_user_frontier_guard(*, user_task_class: str) -> dict:
    monitor = quota_todo_item(
        todo_id="todo_stalled_monitor",
        index=1,
        title="Watch the release qualification PR.",
        task_class="continuous_monitor",
        claimed_by=AGENT_ID,
        target_key="github-pr-123",
        consecutive_no_change="2",
        cadence="30m",
        next_due_at="2099-01-01T00:00:00+00:00",
    )
    blocked_successor = quota_todo_item(
        todo_id="todo_blocked_release_baseline",
        index=2,
        status="deferred",
        title="Run the release outcome baseline.",
        task_class="advancement_task",
        action_kind="release_outcome_baseline_qualification",
        claimed_by=AGENT_ID,
        required_capabilities=["benchmark_runner"],
        resume_when="capacity_available:benchmark_runner",
    )
    user_item = quota_todo_item(
        todo_id="todo_user_frontier",
        role="user",
        status="open",
        title="Review the public-safe qualification evidence.",
        task_class=user_task_class,
        blocks_agent=AGENT_ID if user_task_class == "user_gate" else None,
        bound_agent=AGENT_ID if user_task_class == "user_action" else None,
    )
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Wait for material monitor evidence.",
        agent_todos=quota_todo_summary([monitor, blocked_successor]),
        user_todos=quota_todo_summary([user_item], role="user"),
        quota_state="operator_gate" if user_task_class == "user_gate" else "eligible",
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [AGENT_ID, PEER_AGENT_ID],
        },
        latest_runs=[
            {
                "classification": "quality_vision_fixture",
                "generated_at": "2026-07-19T00:00:00+00:00",
                "agent_id": AGENT_ID,
                "progress_scope": "agent_lane",
                "agent_vision": {
                    "schema_version": "goal_vision_replan_contract_v0",
                    "agent_id": AGENT_ID,
                    "state": "vision_active",
                    "vision_patch": {
                        "acceptance_summary": (
                            "Keep release qualification advancing until closed."
                        ),
                        "advancement_policy": "repeat_until_closed",
                        "replan_trigger_summary": (
                            "Replan after two unchanged monitor observations."
                        ),
                    },
                },
            }
        ],
    )
    return build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=(
            GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT
        ),
    )


def test_nonblocking_user_action_does_not_suppress_stalled_monitor_replan() -> None:
    guard = _combined_user_frontier_guard(user_task_class="user_action")

    assert guard["decision"] == "autonomous_replan_required"
    assert guard["goal_frontier_projection"]["vision_wait_state"][
        "selected_todo_id"
    ] == "todo_blocked_release_baseline"
    trigger = guard["autonomous_replan_obligation"]["triggers"][0]
    assert trigger["kind"] == "monitor_no_change_streak"
    assert trigger["todo_id"] == "todo_stalled_monitor"
    assert guard["interaction_contract"]["user_channel"] == {
        "action_required": False,
        "notify": "NOTIFY",
        "max_items": 3,
        "actions": ["[P0] Review the public-safe qualification evidence."],
        "non_blocking": True,
        "reason": (
            "open non-blocking user action should be surfaced while independent "
            "agent work continues"
        ),
    }
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True


def test_nonblocking_user_action_does_not_suppress_empty_frontier_replan() -> None:
    user_action = quota_todo_item(
        todo_id="todo_review_reminder",
        role="user",
        status="open",
        title="Review the experiment integration PR.",
        task_class="user_action",
        bound_agent=AGENT_ID,
    )
    replan_obligation = {
        "schema_version": "autonomous_replan_obligation_v0",
        "required": True,
        "stall_threshold": 2,
        "trigger_count": 1,
        "triggers": [
            {
                "kind": "run_history_no_progress_repeat",
                "section": "run_history",
                "text": "two stalled turns left no runnable agent todo",
                "agent_id": AGENT_ID,
            }
        ],
        "todo_actions": [
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": "create the next runnable experiment slice",
            }
        ],
        "agent_todo_writeback_required": True,
        "stop_condition": "stop on owner-only authority",
    }
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        waiting_on="codex",
        recommended_action="Replan the empty agent frontier.",
        agent_todos=quota_todo_summary([], role="agent"),
        user_todos=quota_todo_summary([user_action], role="user"),
        project_asset_extra={
            "autonomous_replan_obligation": replan_obligation,
        },
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [AGENT_ID, PEER_AGENT_ID],
        },
    )
    guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=(
            GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT
        ),
    )

    assert guard["decision"] == "autonomous_replan_required", guard
    assert guard["state"] == "eligible", guard
    assert guard["requires_user_action"] is False, guard
    assert guard["execution_obligation"] == {
        "must_attempt_work": True,
        "kind": "autonomous_replan_required",
        "minimum": "one_bounded_replan_with_agent_todo_writeback",
        "notify_is_execution_gate": False,
        "stall_threshold": 2,
        "contract_obligation": (
            "apply autonomous_replan_obligation and create a concrete runnable "
            "agent todo; explicit terminal no-follow-up is allowed only with "
            "closure evidence"
        ),
        "reason": (
            "autonomous_replan_obligation is a machine execution contract; "
            "quiet no-op is not allowed until the replan slice is validated or blocked"
        ),
        "contract": "autonomous_replan_agent_todo_writeback",
    }, guard
    contract = guard["interaction_contract"]
    assert contract["mode"] == "autonomous_replan", contract
    assert contract["user_channel"]["non_blocking"] is True, contract
    assert contract["agent_channel"]["must_attempt"] is True, contract
    cli_actions = contract["cli_channel"]["next_cli_actions"]
    assert any(
        "todo add" in action
        and "--task-class advancement_task" in action
        and f"--claimed-by {AGENT_ID}" in action
        for action in cli_actions
    ), cli_actions
    assert any(
        "--repair-delta-kind runnable_todo_set" in action
        for action in cli_actions
    ), cli_actions


def test_blocking_user_gate_still_precedes_stalled_monitor_replan() -> None:
    guard = _combined_user_frontier_guard(user_task_class="user_gate")

    assert guard["decision"] == "skip"
    assert guard["interaction_contract"]["mode"] == "user_gate"
    assert guard["interaction_contract"]["user_channel"]["action_required"] is True
    assert guard.get("autonomous_replan_obligation") is None
