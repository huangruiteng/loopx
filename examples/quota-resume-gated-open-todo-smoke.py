#!/usr/bin/env python3
"""Smoke-test quota routing for open todos gated by resume_when."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run  # noqa: E402
from loopx.status import compact_todo_group  # noqa: E402


GOAL_ID = "resume-gated-open-todo-fixture"
AGENT_ID = "codex-product-capability"
PRIMARY_AGENT = "codex-main-control"
BLOCKING_TODO_ID = "todo_projection_refresh"
GATED_TODO_ID = "todo_projection_wording"
FALLBACK_TODO_ID = "todo_catalog_canary"
GATED_ACTION = "[P0] Review refreshed projection wording."
FALLBACK_ACTION = "[P1] Continue catalog-driven product canary coverage."


def build_agent_todos(*, prerequisite_status: str) -> dict:
    agent_todos = compact_todo_group(
        [
            {
                "index": 1,
                "text": "[P0] Refresh the projection prerequisite.",
                "role": "agent",
                "status": prerequisite_status,
                "priority": "P0",
                "task_class": "continuous_monitor",
                "claimed_by": "codex-side-bypass",
                "todo_id": BLOCKING_TODO_ID,
            },
            {
                "index": 2,
                "text": GATED_ACTION,
                "role": "agent",
                "status": "open",
                "priority": "P0",
                "task_class": "advancement_task",
                "claimed_by": AGENT_ID,
                "todo_id": GATED_TODO_ID,
                "required_capabilities": ["shell"],
                "resume_when": f"todo_done:{BLOCKING_TODO_ID}",
            },
            {
                "index": 3,
                "text": FALLBACK_ACTION,
                "role": "agent",
                "status": "open",
                "priority": "P1",
                "task_class": "advancement_task",
                "claimed_by": AGENT_ID,
                "todo_id": FALLBACK_TODO_ID,
                "required_capabilities": ["shell"],
            },
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert agent_todos is not None, agent_todos
    return agent_todos


def status_payload(agent_todos: dict, *, next_action: str) -> dict:
    item = {
        "goal_id": GOAL_ID,
        "status": "resume_gated_open_todo_fixture",
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": next_action,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "coordination": {
            "primary_agent": PRIMARY_AGENT,
            "registered_agents": [PRIMARY_AGENT, "codex-side-bypass", AGENT_ID],
        },
        "project_asset": {
            "next_action": next_action,
            "stop_condition": "stop on private material",
            "agent_todos": agent_todos,
        },
        "agent_todos": agent_todos,
    }
    return {
        "ok": True,
        "attention_queue": {"items": [item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "resume_gated_open_todo_fixture",
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "coordination": item["coordination"],
                }
            ]
        },
    }


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


def main() -> int:
    assert_not_ready_open_resume_todo_is_not_executable()
    assert_ready_open_resume_todo_can_run()
    print("quota-resume-gated-open-todo-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
