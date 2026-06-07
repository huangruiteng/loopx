#!/usr/bin/env python3
"""Smoke-test monitor-vs-advancement lane projection in quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown


GOAL_ID = "work-lane-fixture"


def status_payload(*, status: str, has_agent_todo: bool = True) -> dict:
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": 1 if has_agent_todo else 0,
        "open_count": 1 if has_agent_todo else 0,
        "done_count": 0,
        "first_open_items": [
            {
                "index": 1,
                "text": "[P1] Advance the self-repair planning slice with a validation-backed patch.",
                "role": "agent",
                "status": "open",
                "priority": "P1",
            }
        ]
        if has_agent_todo
        else [],
    }
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
                    "recommended_action": "Observe dependency state and then advance backlog if unchanged.",
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
                        "next_action": "Observe dependency state and then advance backlog if unchanged.",
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
                }
            ]
        },
    }


def assert_dependency_monitor_requires_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(status="side_bypass_dependency_observation"),
        goal_id=GOAL_ID,
    )
    assert guard["should_run"] is True, guard
    lane = guard["work_lane_contract"]
    assert lane["schema_version"] == "work_lane_contract_v0", lane
    assert lane["current_lane"] == "continuous_monitor", lane
    assert lane["monitor_kind"] == "dependency_observation", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["advancement_required"] is True, lane
    recommendation = guard["heartbeat_recommendation"]
    assert recommendation["recommended_mode"] == "advance_primary_backlog_after_dependency_observation", recommendation
    assert "dependency_observation_cap" in recommendation, recommendation
    assert guard["execution_obligation"]["kind"] == "advance_primary_backlog_after_dependency_observation", guard
    assert guard["execution_obligation"]["minimum"] == "one_primary_backlog_segment_or_material_transition", guard
    assert guard["execution_obligation"]["work_lane"] == "continuous_monitor", guard
    assert guard["execution_obligation"]["next_lane"] == "advancement_task", guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: current=continuous_monitor next=advancement_task" in markdown, markdown
    assert "dependency_observation_cap" in markdown, markdown


def assert_primary_status_stays_advancement_lane() -> None:
    guard = build_quota_should_run(
        status_payload(status="self_repair_planning_slice"),
        goal_id=GOAL_ID,
    )
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "steering_audit_then_one_step", guard
    lane = guard["work_lane_contract"]
    assert lane["current_lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["advancement_required"] is True, lane


def main() -> int:
    assert_dependency_monitor_requires_advancement()
    assert_primary_status_stays_advancement_lane()
    print("work-lane-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
