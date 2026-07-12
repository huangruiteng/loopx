#!/usr/bin/env python3
"""Smoke-test quota routing for open todos gated by resume_when."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run  # noqa: E402
from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "resume-gated-open-todo-fixture"
AGENT_ID = "codex-product-capability"
PRIMARY_AGENT = "codex-main-control"
BLOCKING_TODO_ID = "todo_projection_refresh"
GATED_TODO_ID = "todo_projection_wording"
FALLBACK_TODO_ID = "todo_catalog_canary"
ARCHIVED_DONE_TODO_ID = "todo_archived_pr_merge"
ARCHIVE_GATED_MONITOR_ID = "todo_archive_gated_monitor"
READY_DEFERRED_ID = "todo_ready_deferred_p0"
GATED_ACTION = "[P0] Review refreshed projection wording."
FALLBACK_ACTION = "[P1] Continue catalog-driven product canary coverage."
ARCHIVE_MONITOR_ACTION = "[P1] Monitor product refactor/catalog canary continuation."


def build_agent_todos(*, prerequisite_status: str) -> dict:
    agent_todos = quota_todo_summary(
        [
            quota_todo_item(
                todo_id=BLOCKING_TODO_ID,
                index=1,
                text="[P0] Refresh the projection prerequisite.",
                status=prerequisite_status,
                task_class="continuous_monitor",
                claimed_by="codex-side-bypass",
            ),
            quota_todo_item(
                todo_id=GATED_TODO_ID,
                index=2,
                text=GATED_ACTION,
                claimed_by=AGENT_ID,
                required_capabilities=["shell"],
                resume_when=f"todo_done:{BLOCKING_TODO_ID}",
            ),
            quota_todo_item(
                todo_id=FALLBACK_TODO_ID,
                index=3,
                priority="P1",
                text=FALLBACK_ACTION,
                claimed_by=AGENT_ID,
                required_capabilities=["shell"],
            ),
        ],
        role="agent",
    )
    return agent_todos


def status_payload(agent_todos: dict, *, next_action: str) -> dict:
    coordination = {
        "agent_model": "peer_v1",
        "registered_agents": [PRIMARY_AGENT, "codex-side-bypass", AGENT_ID],
    }
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="resume_gated_open_todo_fixture",
        recommended_action=next_action,
        next_action=next_action,
        agent_todos=agent_todos,
        coordination=coordination,
    )


def selected_todo_id(payload: dict) -> str:
    return payload["agent_lane_next_action"]["todo_id"]


def runnable_todo_ids(payload: dict) -> list[str]:
    return [
        item["todo_id"]
        for item in payload["capability_gate"]["runnable_candidates"]
    ]


def assert_not_ready_open_resume_todo_is_not_executable() -> None:
    agent_todos = build_agent_todos(prerequisite_status="open")
    gated = next(
        item for item in agent_todos["backlog_items"] if item["todo_id"] == GATED_TODO_ID
    )
    assert gated["resume_ready"] is False, gated
    executable_ids = {
        item["todo_id"] for item in agent_todos["executable_backlog_items"]
    }
    assert GATED_TODO_ID not in executable_ids, agent_todos
    assert FALLBACK_TODO_ID in executable_ids, agent_todos

    quota_payload = build_quota_should_run(
        status_payload(agent_todos, next_action=GATED_ACTION),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["normal_delivery_allowed"] is True, quota_payload
    assert selected_todo_id(quota_payload) == FALLBACK_TODO_ID, quota_payload
    assert GATED_TODO_ID not in runnable_todo_ids(quota_payload), quota_payload
    assert quota_payload["recommended_action"] == FALLBACK_ACTION, quota_payload


def assert_ready_open_resume_todo_can_run() -> None:
    agent_todos = build_agent_todos(prerequisite_status="done")
    gated = next(
        item for item in agent_todos["backlog_items"] if item["todo_id"] == GATED_TODO_ID
    )
    assert gated["resume_ready"] is True, gated
    executable_ids = {
        item["todo_id"] for item in agent_todos["executable_backlog_items"]
    }
    assert GATED_TODO_ID in executable_ids, agent_todos

    quota_payload = build_quota_should_run(
        status_payload(agent_todos, next_action=GATED_ACTION),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert quota_payload["should_run"] is True, quota_payload
    assert selected_todo_id(quota_payload) == GATED_TODO_ID, quota_payload
    assert runnable_todo_ids(quota_payload)[0] == GATED_TODO_ID, quota_payload
    assert quota_payload["recommended_action"] == GATED_ACTION, quota_payload


def assert_ready_deferred_p0_preempts_open_p1_for_successor_replan() -> None:
    deferred_action = "[P0] Resume the validated release successor."
    agent_todos = quota_todo_summary(
        [
            quota_todo_item(
                todo_id=BLOCKING_TODO_ID,
                index=1,
                text="[P0] Complete the release prerequisite.",
                status="done",
                claimed_by=PRIMARY_AGENT,
            ),
            quota_todo_item(
                todo_id=READY_DEFERRED_ID,
                index=2,
                text=deferred_action,
                status="deferred",
                claimed_by=AGENT_ID,
                resume_when=f"todo_done:{BLOCKING_TODO_ID}",
            ),
            quota_todo_item(
                todo_id=FALLBACK_TODO_ID,
                index=3,
                priority="P1",
                text=FALLBACK_ACTION,
                claimed_by=AGENT_ID,
                required_capabilities=["shell"],
            ),
        ],
        role="agent",
    )
    quota_payload = build_quota_should_run(
        status_payload(agent_todos, next_action=FALLBACK_ACTION),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert quota_payload["decision"] == "successor_replan_required", quota_payload
    assert quota_payload["normal_delivery_allowed"] is False, quota_payload
    assert quota_payload.get("agent_lane_next_action") is None, quota_payload
    frontier = quota_payload["agent_scope_frontier"]
    assert frontier["priority_preemption"] is True, frontier
    assert frontier["deferred_resume_candidates"][0]["todo_id"] == READY_DEFERRED_ID, frontier
    assert quota_payload["selected_todo"]["todo_id"] == READY_DEFERRED_ID, quota_payload
    assert quota_payload["selected_todo"]["source"] == (
        "agent_scope_frontier.deferred_resume_candidates"
    ), quota_payload
    assert quota_payload["goal_frontier_projection"]["deferred_successors"][
        "top_ready_todo_id"
    ] == READY_DEFERRED_ID, quota_payload

    for item in agent_todos["deferred_items"]:
        item["priority"] = "P1"
    equal_priority = build_quota_should_run(
        status_payload(agent_todos, next_action=FALLBACK_ACTION),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    assert equal_priority["decision"] == "run", equal_priority
    assert equal_priority["selected_todo"]["todo_id"] == FALLBACK_TODO_ID, equal_priority


def assert_archived_done_resume_target_wakes_claimed_monitor() -> None:
    fields = parse_active_state_todos(
        "# Active Goal State\n\n"
        "## Agent Todo\n\n"
        f"- [ ] {ARCHIVE_MONITOR_ACTION}\n"
        "  <!-- loopx:todo "
        f"todo_id={ARCHIVE_GATED_MONITOR_ID} "
        "status=open "
        "task_class=continuous_monitor "
        "claimed_by=codex-product-capability "
        f"resume_when=todo_done:{ARCHIVED_DONE_TODO_ID} "
        "cadence=6h "
        "next_due_at=2026-01-01T00:00:00+00:00 "
        "-->\n\n"
        "## Completed Work Archive\n\n"
        "- [x] [P0] Merge predecessor PR.\n"
        "  <!-- loopx:todo "
        f"todo_id={ARCHIVED_DONE_TODO_ID} "
        "status=done "
        "task_class=advancement_task "
        "claimed_by=codex-main-control "
        f"unblocks_todo_id={ARCHIVE_GATED_MONITOR_ID} "
        "-->\n"
    )
    agent_todos = fields["agent_todos"]
    active_ids = {item["todo_id"] for item in agent_todos["items"]}
    assert ARCHIVE_GATED_MONITOR_ID in active_ids, agent_todos
    assert ARCHIVED_DONE_TODO_ID not in active_ids, agent_todos

    monitor = next(
        item for item in agent_todos["items"] if item["todo_id"] == ARCHIVE_GATED_MONITOR_ID
    )
    assert monitor["resume_ready"] is True, monitor
    assert monitor["resume_condition"]["target_status"] == "done", monitor
    assert monitor["resume_condition"]["target_archive_state"] == "archive", monitor

    monitor_open_ids = {
        item["todo_id"] for item in agent_todos["monitor_open_items"]
    }
    assert ARCHIVE_GATED_MONITOR_ID in monitor_open_ids, agent_todos
    assert agent_todos["monitor_due_count"] == 1, agent_todos

    quota_payload = build_quota_should_run(
        status_payload(agent_todos, next_action=ARCHIVE_MONITOR_ACTION),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    summary = quota_payload["agent_todo_summary"]
    current_agent_monitor_ids = {
        item["todo_id"] for item in summary["current_agent_claimed_monitor_items"]
    }
    assert ARCHIVE_GATED_MONITOR_ID in current_agent_monitor_ids, quota_payload
    assert summary["current_agent_claimed_monitor_count"] == 1, quota_payload
    assert summary["monitor_due_count"] == 1, quota_payload


def main() -> int:
    assert_not_ready_open_resume_todo_is_not_executable()
    assert_ready_open_resume_todo_can_run()
    assert_ready_deferred_p0_preempts_open_p1_for_successor_replan()
    assert_archived_done_resume_target_wakes_claimed_monitor()
    print("quota-resume-gated-open-todo-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
