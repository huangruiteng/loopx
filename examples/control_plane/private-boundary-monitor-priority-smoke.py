#!/usr/bin/env python3
"""Guard private/local due monitors from preempting public advancement work."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run  # noqa: E402


GOAL_ID = "private-boundary-monitor-priority-fixture"
PAST_DUE_AT = "2000-01-01T00:00:00+00:00"


def status_payload(*, monitor_todo: dict, advancement_todo: dict) -> dict:
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": 2,
        "open_count": 2,
        "done_count": 0,
        "first_open_items": [monitor_todo, advancement_todo],
        "monitor_open_items": [monitor_todo],
        "monitor_due_items": [monitor_todo],
        "monitor_due_count": 1,
        "first_executable_items": [advancement_todo],
        "claim_scope": {"agent_id": "codex-product-capability"},
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "eligible",
                    "waiting_on": "codex",
                    "severity": "info",
                    "source": "project_asset",
                    "recommended_action": advancement_todo["text"],
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
                        "next_action": advancement_todo["text"],
                        "stop_condition": "stop on fixture boundary",
                        "agent_todos": agent_todos,
                    },
                    "agent_todos": agent_todos,
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": [
                            "codex-main-control",
                            "codex-product-capability",
                        ],
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ]
        },
    }


def test_private_boundary_due_monitor_is_context_only() -> None:
    monitor_todo = {
        "index": 1,
        "text": "[P0-local] Keep private planning material aligned without authorized read.",
        "role": "agent",
        "status": "open",
        "priority": "P0-LOCAL",
        "task_class": "continuous_monitor",
        "action_kind": "local_department_doc_todo_projection_monitor",
        "claimed_by": "codex-product-capability",
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
        "claimed_by": "codex-product-capability",
    }
    guard = build_quota_should_run(
        status_payload(
            monitor_todo=monitor_todo,
            advancement_todo=advancement_todo,
        ),
        goal_id=GOAL_ID,
        agent_id="codex-product-capability",
    )
    lane = guard["work_lane_contract"]
    assert guard["agent_todo_summary"]["monitor_due_count"] == 1, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo", "due_monitor_context"], lane
    assert guard["recommended_action"] == advancement_todo["text"], guard
    assert (
        guard["interaction_contract"]["agent_channel"]["primary_action"]
        == f"{advancement_todo['text']}"
    ), guard


def main() -> int:
    test_private_boundary_due_monitor_is_context_only()
    print("private-boundary-monitor-priority-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
