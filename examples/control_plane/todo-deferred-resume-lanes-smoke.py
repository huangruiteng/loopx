#!/usr/bin/env python3
"""Smoke-test todo deferred/resume-blocked lane projection helpers."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.deferred_resume import (  # noqa: E402
    TODO_DEFERRED_RESUME_SELECTION_POLICY,
    TODO_MONITOR_BLOCKED_RESUME_SELECTION_POLICY,
    build_todo_deferred_visibility_lanes,
    build_todo_resume_blocked_visibility_lanes,
    todo_summary_monitor_blocked_resume_items,
    todo_summary_resume_blocked_items,
)


CURRENT_AGENT = "codex-product-capability"
OTHER_AGENT = "codex-main-control"


def monitor_todo() -> dict:
    return {
        "index": 1,
        "todo_id": "todo_monitor_open",
        "text": "[P1 monitor] Watch the upstream signal.",
        "status": "open",
        "task_class": "continuous_monitor",
        "claimed_by": CURRENT_AGENT,
    }


def blocked_advancement(
    todo_id: str,
    *,
    index: int,
    claimed_by: str | None,
    target_task_class: str | None = "continuous_monitor",
    target_status: str = "open",
) -> dict:
    condition = {
        "target_todo_id": "todo_monitor_open",
        "target_status": target_status,
    }
    if target_task_class is not None:
        condition["target_task_class"] = target_task_class
    item = {
        "index": index,
        "todo_id": todo_id,
        "text": f"[P1] Resume blocked advancement {todo_id}.",
        "status": "open",
        "task_class": "advancement_task",
        "claimed_by": claimed_by,
        "resume_when": "todo_done:todo_monitor_open",
        "resume_ready": False,
        "resume_condition": condition,
    }
    return {key: value for key, value in item.items() if value is not None}


def ready_deferred(
    todo_id: str,
    *,
    index: int,
    claimed_by: str | None,
    excluded_agents: list[str] | None = None,
) -> dict:
    item = {
        "index": index,
        "todo_id": todo_id,
        "text": f"[P1] Ready deferred candidate {todo_id}.",
        "status": "deferred",
        "task_class": "advancement_task",
        "claimed_by": claimed_by,
        "resume_when": "todo_done:todo_gate",
        "resume_ready": True,
        "required_write_scopes": [" loopx/** ", "loopx/**"],
        "decision_scope": "direction:action:resume",
        "excluded_agents": excluded_agents,
    }
    return {key: value for key, value in item.items() if value is not None}


def assert_deferred_resume_lanes_filter_current_unclaimed_and_other_agents() -> None:
    summary = {
        "schema_version": "todo_summary_v0",
        "items": [
            {
                "index": 0,
                "todo_id": "todo_deferred_backlog",
                "text": "[P2] Deferred backlog item.",
                "status": "deferred",
                "task_class": "advancement_task",
            },
        ],
        "deferred_resume_candidates": [
            ready_deferred("todo_current_ready", index=2, claimed_by=CURRENT_AGENT),
            ready_deferred("todo_unclaimed_ready", index=3, claimed_by=None),
            ready_deferred("todo_other_ready", index=4, claimed_by=OTHER_AGENT),
            ready_deferred(
                "todo_excluded_ready",
                index=5,
                claimed_by=None,
                excluded_agents=[CURRENT_AGENT],
            ),
            {
                **ready_deferred("todo_not_ready", index=6, claimed_by=CURRENT_AGENT),
                "resume_ready": False,
            },
        ],
    }

    lanes = build_todo_deferred_visibility_lanes(
        summary,
        agent_identity={"agent_id": CURRENT_AGENT},
        item_limit=10,
    )
    assert lanes["deferred_count"] == 1, lanes
    assert lanes["deferred_visibility_limit"] == 10, lanes
    assert lanes["deferred_items"][0]["todo_id"] == "todo_deferred_backlog", lanes
    assert [item["todo_id"] for item in lanes["deferred_resume_candidates"]] == [
        "todo_current_ready",
        "todo_unclaimed_ready",
        "todo_other_ready",
        "todo_excluded_ready",
    ], lanes
    assert lanes["current_agent_deferred_resume_count"] == 1, lanes
    assert lanes["unclaimed_deferred_resume_count"] == 1, lanes
    assert lanes["other_agent_deferred_resume_count"] == 1, lanes
    assert lanes["executor_excluded_self_deferred_resume_count"] == 1, lanes
    assert lanes["executor_excluded_self_deferred_resume_candidates"][0]["todo_id"] == (
        "todo_excluded_ready"
    ), lanes
    current = lanes["current_agent_deferred_resume_candidates"][0]
    assert current["required_write_scopes"] == ["loopx/**"], current
    assert current["decision_scope"]["scope_key"] == "resume", current
    assert lanes["deferred_resume_selection_policy"] == (
        TODO_DEFERRED_RESUME_SELECTION_POLICY
    ), lanes


def assert_monitor_blocked_resume_lanes_filter_by_claim_and_monitor_target() -> None:
    current = blocked_advancement(
        "todo_current_blocked",
        index=2,
        claimed_by=CURRENT_AGENT,
    )
    unclaimed = blocked_advancement(
        "todo_unclaimed_blocked",
        index=3,
        claimed_by=None,
        target_task_class=None,
    )
    other = blocked_advancement(
        "todo_other_blocked",
        index=4,
        claimed_by=OTHER_AGENT,
    )
    non_monitor = blocked_advancement(
        "todo_non_monitor_blocked",
        index=5,
        claimed_by=CURRENT_AGENT,
        target_task_class="advancement_task",
    )
    non_monitor["resume_condition"]["target_todo_id"] = "todo_regular_open"
    excluded = blocked_advancement(
        "todo_excluded_blocked",
        index=6,
        claimed_by=None,
    )
    excluded["excluded_agents"] = [CURRENT_AGENT]
    summary = {
        "schema_version": "todo_summary_v0",
        "items": [monitor_todo(), current, unclaimed, other, non_monitor, excluded],
        "backlog_items": [current],
    }

    resume_blocked = todo_summary_resume_blocked_items(summary)
    assert [item["todo_id"] for item in resume_blocked] == [
        "todo_current_blocked",
        "todo_unclaimed_blocked",
        "todo_other_blocked",
        "todo_non_monitor_blocked",
        "todo_excluded_blocked",
    ], resume_blocked
    monitor_blocked = todo_summary_monitor_blocked_resume_items(summary)
    assert [item["todo_id"] for item in monitor_blocked] == [
        "todo_current_blocked",
        "todo_unclaimed_blocked",
        "todo_other_blocked",
        "todo_excluded_blocked",
    ], monitor_blocked
    assert all(
        item["blocking_monitor_todo_id"] == "todo_monitor_open"
        for item in monitor_blocked
    ), monitor_blocked

    lanes = build_todo_resume_blocked_visibility_lanes(
        summary,
        agent_identity={"agent_id": CURRENT_AGENT},
        item_limit=10,
    )
    assert lanes["resume_blocked_count"] == 5, lanes
    assert lanes["monitor_blocked_resume_count"] == 4, lanes
    assert lanes["current_agent_monitor_blocked_resume_count"] == 1, lanes
    assert lanes["unclaimed_monitor_blocked_resume_count"] == 1, lanes
    assert lanes["other_agent_monitor_blocked_resume_count"] == 1, lanes
    assert lanes["executor_excluded_self_monitor_blocked_resume_count"] == 1, lanes
    assert lanes["monitor_blocked_resume_selection_policy"] == (
        TODO_MONITOR_BLOCKED_RESUME_SELECTION_POLICY
    ), lanes


def main() -> int:
    assert_deferred_resume_lanes_filter_current_unclaimed_and_other_agents()
    assert_monitor_blocked_resume_lanes_filter_by_claim_and_monitor_target()
    print("todo-deferred-resume-lanes-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
