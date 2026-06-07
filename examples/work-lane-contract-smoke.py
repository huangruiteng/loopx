#!/usr/bin/env python3
"""Smoke-test monitor-vs-advancement lane projection in quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown


GOAL_ID = "work-lane-fixture"


def status_payload(
    *,
    status: str,
    has_agent_todo: bool = True,
    agent_todo_items: list[dict] | None = None,
    next_action: str = "Observe dependency state and then advance backlog if unchanged.",
) -> dict:
    if agent_todo_items is None:
        agent_todo_items = [
            {
                "index": 1,
                "text": "[P1] Advance the self-repair planning slice with a validation-backed patch.",
                "role": "agent",
                "status": "open",
                "priority": "P1",
            }
        ]
    open_items = agent_todo_items if has_agent_todo else []
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(open_items),
        "open_count": len(open_items),
        "done_count": 0,
        "first_open_items": open_items,
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
                    "project_asset": {
                        "next_action": next_action,
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
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["monitor_kind"] == "dependency_observation", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_unless_material_monitor_transition", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["dependency_observation", "open_agent_todo"], lane
    recommendation = guard["heartbeat_recommendation"]
    assert recommendation["recommended_mode"] == "follow_work_lane_contract", recommendation
    assert "dependency_observation_cap" not in recommendation, recommendation
    assert "work_lane_contract" not in recommendation, recommendation
    assert guard["execution_obligation"]["kind"] == "work_lane_contract", guard
    assert guard["execution_obligation"]["contract"] == "work_lane_contract", guard
    assert guard["execution_obligation"]["contract_obligation"] == lane["obligation"], guard
    assert "minimum" not in guard["execution_obligation"], guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: lane=continuous_monitor next=advancement_task" in markdown, markdown
    assert "obligation=advance_unless_material_monitor_transition" in markdown, markdown
    assert "work_lane_reason_codes: dependency_observation,open_agent_todo" in markdown, markdown


def assert_primary_status_stays_advancement_lane() -> None:
    guard = build_quota_should_run(
        status_payload(status="self_repair_planning_slice"),
        goal_id=GOAL_ID,
    )
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "steering_audit_then_one_step", guard
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane


def assert_monitor_only_todo_waits_quietly() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="typed_task_lane_planning_writeback",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P2] Meta canary/readiness observation lane: keep release readiness observable.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["monitor_kind"] == "todo_monitor", lane
    assert lane["next_lane"] == "continuous_monitor", lane
    assert lane["obligation"] == "quiet_until_material_monitor_transition", lane
    assert lane["must_attempt_work"] is False, lane
    assert lane["reason_codes"] == ["monitor_todo_only"], lane
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "monitor_quiet_until_material_transition", guard
    assert guard["execution_obligation"]["kind"] == "work_lane_contract", guard
    assert guard["execution_obligation"]["must_attempt_work"] is False, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert [item["task_class"] for item in first_items] == ["continuous_monitor", "continuous_monitor"], guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: lane=continuous_monitor next=continuous_monitor" in markdown, markdown
    assert "obligation=quiet_until_material_monitor_transition" in markdown, markdown


def assert_monitor_only_with_planning_next_action_materializes_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="benchmark_experiment_report_template",
            next_action=(
                "Post-reporting lane should route to the planning/self-repair capability lane "
                "as the next eligible advancement turn."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P2] Meta canary/readiness observation lane: keep release readiness observable.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "materialize_advancement_todo_or_blocker", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["monitor_todo_only", "next_action_requires_advancement"], lane
    assert "planning/self-repair" in lane["action"], lane
    assert guard["execution_obligation"]["contract_obligation"] == lane["obligation"], guard
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: lane=advancement_task next=advancement_task" in markdown, markdown
    assert "obligation=materialize_advancement_todo_or_blocker" in markdown, markdown
    assert "work_lane_reason_codes: monitor_todo_only,next_action_requires_advancement" in markdown, markdown


def assert_mixed_monitor_and_advancement_routes_to_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="typed_task_lane_planning_writeback",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P1] Add the typed task class routing smoke fixture.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["must_attempt_work"] is True, lane
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert [item["task_class"] for item in first_items] == ["continuous_monitor", "advancement_task"], guard


def main() -> int:
    assert_dependency_monitor_requires_advancement()
    assert_primary_status_stays_advancement_lane()
    assert_monitor_only_todo_waits_quietly()
    assert_monitor_only_with_planning_next_action_materializes_advancement()
    assert_mixed_monitor_and_advancement_routes_to_advancement()
    print("work-lane-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
