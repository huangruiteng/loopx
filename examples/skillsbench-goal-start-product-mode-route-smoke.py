#!/usr/bin/env python3
"""Smoke-test the SkillsBench goal-start product-mode route plan surface."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _assert_control_score_surface() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.skillsbench_automation_loop import (
        _build_case_event_timeline,
        _build_goal_start_product_mode_control_score,
    )
    from loopx.benchmark_adapters.skillsbench import (
        _skillsbench_controller_trace_counters,
    )
    from loopx.status import (
        _compact_benchmark_interaction_counters,
        _compact_benchmark_runner_prerequisites,
    )

    compact = {
        "product_mode": True,
        "interaction_counters": {
            "goal_start_product_mode": True,
            "goal_start_plan_observed": True,
            "planned_todo_count": 3,
            "planned_p0_count": 1,
            "planner_before_todo_write": True,
            "same_priority_order_preserved": True,
            "selected_p0_todo_id": "todo_public_solver",
            "selected_todo_claimed": True,
            "selected_todo_updated_before_solver": True,
            "non_selected_todos_preserved_open_or_deferred": True,
            "remote_command_file_bridge_agent_successful_loopx_subcommand_counts": {
                "todo complete": 1,
                "quota spend-slot": 1,
            },
            "remote_command_file_bridge_agent_quota_spend_slot_count": 1,
        },
        "product_mode_lifecycle_contract": {
            "agent_bridge_quota_spend_slot_count": 1,
        },
    }
    plan = {
        "runner_prerequisites": {
            "goal_start_product_mode": True,
            "goal_start_plan_required": True,
            "goal_start_planned_todo_count_expected": 3,
            "goal_start_selected_p0_lifecycle_required": True,
        },
    }
    control_score = _build_goal_start_product_mode_control_score(compact, plan)
    assert control_score["satisfied"] is True, control_score
    assert control_score["score"] == 1.0, control_score
    assert control_score["raw_material_recorded"] is False, control_score
    assert control_score["selected_todo_completed_before_spend"] is True, control_score
    compact["goal_start_product_mode_control_score"] = control_score
    timeline = _build_case_event_timeline(compact, plan)
    events = timeline["events"]
    goal_start_events = [
        event
        for event in events
        if event["phase"] == "goal_start_plan"
    ]
    assert len(goal_start_events) == 1, timeline
    goal_start = goal_start_events[0]
    assert goal_start["status"] == "satisfied", goal_start
    assert goal_start["planned_todo_count"] == 3, goal_start
    assert goal_start["selected_p0_todo_id"] == "todo_public_solver", goal_start
    assert timeline["raw_material_recorded"] is False, timeline

    continuation_compact = {
        "product_mode": True,
        "interaction_counters": {
            "goal_start_product_mode": True,
            "goal_start_plan_observed": True,
            "planned_todo_count": 3,
            "planned_p0_count": 1,
            "planner_before_todo_write": True,
            "same_priority_order_preserved": True,
            "selected_p0_todo_id": "todo_public_solver",
            "selected_todo_claimed": True,
            "selected_todo_updated_before_solver": True,
            "non_selected_todos_preserved_open_or_deferred": True,
            "product_mode_declared_done_below_passing_reward": True,
            "product_mode_declared_done_below_passing_reward_count": 1,
            "last_decision": "send_product_mode_success_or_budget_continuation_after_declared_done",
        },
    }
    continuation_score = _build_goal_start_product_mode_control_score(
        continuation_compact,
        plan,
    )
    assert continuation_score["premature_done_signal_count"] == 1, continuation_score
    assert continuation_score["premature_done_stop_reason"] == "", continuation_score
    assert any(
        item["name"] == "no_premature_done_stop" and item["satisfied"] is True
        for item in continuation_score["component_results"]
    ), continuation_score

    controller_trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "goal_start_product_mode": True,
        "goal_start_plan_observed": True,
        "planned_todo_count": 3,
        "planned_p0_count": 1,
        "planner_before_todo_write": True,
        "same_priority_order_preserved": True,
        "selected_p0_todo_id": "todo_public_solver",
        "non_selected_todos_preserved_open_or_deferred": True,
        "remote_command_file_bridge_driver_lifecycle_command_counts": {
            "todo claim": 1,
            "todo update": 1,
        },
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts": {
            "todo complete": 1,
            "quota spend-slot": 1,
        },
    }
    projected = _skillsbench_controller_trace_counters(controller_trace)
    assert projected["selected_todo_claimed"] is True, projected
    assert projected["selected_todo_updated_before_solver"] is True, projected
    assert projected["selected_todo_completed_before_spend"] is True, projected
    compacted_counters = _compact_benchmark_interaction_counters(projected)
    assert compacted_counters["selected_p0_todo_id"] == "todo_public_solver"
    assert compacted_counters["planned_todo_count"] == 3
    assert (
        compacted_counters[
            "remote_command_file_bridge_agent_successful_loopx_subcommand_counts"
        ]["todo complete"]
        == 1
    )
    compacted_prerequisites = _compact_benchmark_runner_prerequisites(
        plan["runner_prerequisites"]
    )
    assert compacted_prerequisites["goal_start_plan_required"] is True
    assert compacted_prerequisites["goal_start_planned_todo_count_expected"] == 3


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--route",
            "loopx-goal-start-product-mode",
            "--task-id",
            "planning-granularity",
            "--plan-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["plan_only"] is True, payload
    plan = payload["launch_plan"]
    assert plan["route"] == "loopx-goal-start-product-mode", plan
    assert plan["rollout_name"].endswith("__loopx_goal_start_product_mode"), plan
    prerequisites = plan["runner_prerequisites"]
    assert prerequisites["goal_start_product_mode"] is True, prerequisites
    assert prerequisites["goal_start_plan_required"] is True, prerequisites
    assert prerequisites["goal_start_planned_todo_count_expected"] == 3, prerequisites
    assert prerequisites["goal_start_selected_p0_lifecycle_required"] is True, prerequisites
    assert prerequisites["benchflow_intermediate_soft_verify_policy"] == "every-round"
    assert plan["public_boundary"]["public_raw_prompt"] is False, plan
    assert plan["public_boundary"]["public_raw_trajectory"] is False, plan
    _assert_control_score_surface()
    print("skillsbench-goal-start-product-mode-route-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
