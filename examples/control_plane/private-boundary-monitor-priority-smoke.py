#!/usr/bin/env python3
"""Guard private/local due monitors from preempting public advancement work."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.quota_fixtures import quota_status_payload  # noqa: E402
from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "private-boundary-monitor-priority-fixture"
AGENT_ID = "codex-product-capability"
PAST_DUE_AT = "2000-01-01T00:00:00+00:00"


def status_payload(*, monitor_todo: dict, advancement_todo: dict) -> dict:
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="eligible",
        registry_status="active",
        agent_todo_items=[monitor_todo, advancement_todo],
        recommended_action=advancement_todo["text"],
        next_action=advancement_todo["text"],
        claim_scope_agent_id=AGENT_ID,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [
                "codex-main-control",
                AGENT_ID,
            ],
        },
        goal_extra={"quota": {"compute": 1.0, "window_hours": 24}},
    )


def test_private_boundary_due_monitor_is_context_only() -> None:
    monitor_todo = {
        "index": 1,
        "text": "[P0-local] Keep private planning material aligned without authorized read.",
        "role": "agent",
        "status": "open",
        "priority": "P0-LOCAL",
        "task_class": "continuous_monitor",
        "action_kind": "local_department_doc_todo_projection_monitor",
        "claimed_by": AGENT_ID,
        "next_due_at": PAST_DUE_AT,
        "result_hash": "private_boundary_no_authorized_read",
    }
    advancement_todo = {
        "index": 2,
        "text": "[P2] Continue canary-gated read-model cleanup.",
        "role": "agent",
        "status": "open",
        "priority": "P2",
        "task_class": "advancement_task",
        "action_kind": "continue_canary_refactor",
        "claimed_by": AGENT_ID,
    }
    guard = build_quota_should_run(
        status_payload(
            monitor_todo=monitor_todo,
            advancement_todo=advancement_todo,
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["agent_todo_summary"]["monitor_due_count"] == 1, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo", "due_monitor_context"], lane
    assert guard["recommended_action"] == advancement_todo["text"], guard
    primary_action = guard["interaction_contract"]["agent_channel"]["primary_action"]
    assert advancement_todo["text"] in primary_action, guard


def test_public_due_monitor_priority_matrix() -> None:
    public_high_monitor = {
        "index": 1,
        "text": "[P0] Poll public release signal before implementation.",
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "continuous_monitor",
        "action_kind": "public_release_monitor",
        "claimed_by": AGENT_ID,
        "next_due_at": PAST_DUE_AT,
    }
    public_low_monitor = {
        **public_high_monitor,
        "text": "[P2] Poll public release signal after implementation.",
        "priority": "P2",
    }
    advancement_todo = {
        "index": 2,
        "text": "[P1] Continue canary-gated read-model cleanup.",
        "role": "agent",
        "status": "open",
        "priority": "P1",
        "task_class": "advancement_task",
        "action_kind": "continue_canary_refactor",
        "claimed_by": AGENT_ID,
    }

    high_guard = build_quota_should_run(
        status_payload(
            monitor_todo=public_high_monitor,
            advancement_todo=advancement_todo,
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    high_lane = high_guard["work_lane_contract"]
    assert high_lane["lane"] == "continuous_monitor", high_lane
    assert high_lane["monitor_kind"] == "todo_monitor_due", high_lane
    assert high_lane["reason_codes"] == [
        "monitor_due",
        "due_monitor_priority_preempts_advancement",
    ], high_lane
    assert high_guard["recommended_action"] == public_high_monitor["text"], high_guard

    low_guard = build_quota_should_run(
        status_payload(
            monitor_todo=public_low_monitor,
            advancement_todo=advancement_todo,
        ),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    low_lane = low_guard["work_lane_contract"]
    assert low_lane["lane"] == "advancement_task", low_lane
    assert low_lane["reason_codes"] == ["open_agent_todo", "due_monitor_context"], low_lane
    assert low_guard["recommended_action"] == advancement_todo["text"], low_guard


def main() -> int:
    test_private_boundary_due_monitor_is_context_only()
    test_public_due_monitor_priority_matrix()
    print("private-boundary-monitor-priority-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
