#!/usr/bin/env python3
"""Smoke-test the SkillsBench goal-start product-mode route plan surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _assert_adapter_route_contract_surface() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench import (
        build_skillsbench_benchflow_result_benchmark_run,
        build_skillsbench_benchmark_run,
        skillsbench_route_contract,
    )

    route = "loopx-goal-start-product-mode"
    contract = skillsbench_route_contract(route)
    assert contract["mode"] == "skillsbench_loopx_goal_start_product_mode_treatment"
    assert contract["arm_id"] == "loopx_goal_start_product_mode"
    assert contract["product_mode"] is True, contract
    assert contract["loopx_inside_case"] is True, contract
    assert contract["loopx_automation_loop"] is True, contract
    assert "ranked_todo_plan" in contract["skillsbench_route_semantics"], contract

    skeleton = build_skillsbench_benchmark_run(route=route)
    assert skeleton["route"] == route, skeleton
    assert skeleton["mode"] == contract["mode"], skeleton
    assert skeleton["source_runner"] == contract["source_runner"], skeleton
    counters = skeleton["interaction_counters"]
    assert counters["product_mode"] is True, counters
    assert counters["case_goal_state_packet_present"] is True, counters
    assert counters["case_goal_state_init_required"] is True, counters
    assert counters["goal_start_product_mode"] is True, counters
    assert counters["declared_done_requires_no_remaining_goals"] is True, counters
    policy = skeleton["episode_policy"]
    assert policy["outer_controller"] == "loopx_goal_start_product_mode", policy
    assert policy["inner_case_actor"] == "ordinary_codex_acp_agent", policy
    kwargs_keys = skeleton["agent"]["kwargs_keys"]
    assert "loopx_goal_start_product_mode" in kwargs_keys, kwargs_keys
    assert "ranked_todo_plan_selected_p0_lifecycle" in kwargs_keys, kwargs_keys

    controller_trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "product_mode": True,
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
        "remote_command_file_bridge_driver_lifecycle_failure_count": 0,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        result_path = Path(temp_dir) / "result.json"
        result_path.write_text(
            json.dumps(
                {
                    "task_name": "planning-granularity",
                    "agent": "codex-acp",
                    "model": "gpt-5.5",
                    "rollout_name": "planning-granularity__loopx_goal_start_product_mode",
                    "rewards": {"reward": 0},
                    "n_tool_calls": 0,
                }
            ),
            encoding="utf-8",
        )
        reduced = build_skillsbench_benchflow_result_benchmark_run(
            result_path,
            route=route,
            controller_trace=controller_trace,
        )
    reduced_counters = reduced["interaction_counters"]
    assert reduced_counters["goal_start_product_mode"] is True, reduced_counters
    assert reduced_counters["goal_start_plan_observed"] is True, reduced_counters
    assert reduced_counters["planned_todo_count"] == 3, reduced_counters
    assert reduced_counters["planned_p0_count"] == 1, reduced_counters
    assert reduced_counters["selected_p0_todo_id"] == "todo_public_solver"
    assert reduced_counters["selected_todo_claimed"] is True, reduced_counters
    assert (
        reduced_counters["selected_todo_updated_before_solver"] is True
    ), reduced_counters
    assert (
        reduced_counters["non_selected_todos_preserved_open_or_deferred"] is True
    ), reduced_counters

    feedback_route = "loopx-goal-start-verifier-feedback-todo"
    feedback_contract = skillsbench_route_contract(feedback_route)
    assert (
        feedback_contract["mode"]
        == "skillsbench_loopx_goal_start_verifier_feedback_todo_experiment"
    )
    assert (
        feedback_contract["arm_id"]
        == "loopx_goal_start_verifier_feedback_todo"
    )
    assert feedback_contract["product_mode"] is True, feedback_contract
    assert feedback_contract["official_feedback_blinded"] is False, feedback_contract
    assert feedback_contract["reward_feedback_forwarded"] is True, feedback_contract
    assert (
        feedback_contract["verifier_failure_todo_required"] is True
    ), feedback_contract

    feedback_skeleton = build_skillsbench_benchmark_run(route=feedback_route)
    assert feedback_skeleton["route"] == feedback_route, feedback_skeleton
    feedback_counters = feedback_skeleton["interaction_counters"]
    assert feedback_counters["goal_start_product_mode"] is True, feedback_counters
    assert (
        feedback_counters["verifier_failure_feedback_todo_route"] is True
    ), feedback_counters
    assert feedback_counters["verifier_failure_todo_required"] is True
    assert "verifier_failure_feedback_todo" in feedback_skeleton["agent"]["kwargs_keys"]


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


def _assert_host_local_acp_return_arity_compat() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.skillsbench_automation_loop import (
        _benchflow_connect_as_unpack_arity,
        _benchflow_connect_acp_return_arity,
        _benchflow_rollout_planes_class,
        _tuple_annotation_arity,
    )

    async def current_benchflow_shape() -> tuple[object, object, str]:
        raise AssertionError("signature-only helper should not call target")

    async def legacy_adapter_shape() -> tuple[object, object, object, str]:
        raise AssertionError("signature-only helper should not call target")

    async def unannotated_shape():
        raise AssertionError("signature-only helper should not call target")

    assert _benchflow_connect_acp_return_arity(current_benchflow_shape) == 3
    assert _benchflow_connect_acp_return_arity(legacy_adapter_shape) == 4
    assert _benchflow_connect_acp_return_arity(unannotated_shape) == 3
    assert _tuple_annotation_arity("tuple[object, ...]") is None

    async def connect_as_shape():
        (
            self._acp_client,
            self._session,
            self._session_adapter,
            self._agent_name,
        ) = await self._planes.connect_acp()

    assert _benchflow_connect_as_unpack_arity(connect_as_shape) == 4

    class FactoryOnlyPlanes:
        async def connect_acp(self):
            raise AssertionError("signature-only helper should not call target")

    class FactoryOnlyModule:
        @staticmethod
        def default_rollout_planes():
            return FactoryOnlyPlanes()

    assert _benchflow_rollout_planes_class(FactoryOnlyModule) is FactoryOnlyPlanes


def _assert_verifier_failure_feedback_todo_prompt() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.skillsbench_automation_loop import (
        _build_verifier_failure_feedback_todo_prompt,
    )

    prompt = _build_verifier_failure_feedback_todo_prompt(
        round_number=3,
        max_rounds=16,
        case_cli_prefix="/app/.local/bin/loopx --registry /app/.loopx/registry.json",
        case_goal_id="skillsbench-case",
        case_agent_id="codex-main-control",
        case_state_path="/app/.codex/goals/skillsbench-case/ACTIVE_GOAL_STATE.md",
        reward=0.0,
    )
    assert "previous_reward=0.0" in prompt, prompt
    assert "todo add --goal-id skillsbench-case --role agent" in prompt, prompt
    assert "--action-kind verifier_failure_repair" in prompt, prompt
    assert "refresh-state --goal-id skillsbench-case" in prompt, prompt
    assert "Do not copy raw verifier output into LoopX state" in prompt


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
    feedback_result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--route",
            "loopx-goal-start-verifier-feedback-todo",
            "--task-id",
            "planning-granularity",
            "--plan-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    feedback_payload = json.loads(feedback_result.stdout)
    feedback_plan = feedback_payload["launch_plan"]
    assert (
        feedback_plan["rollout_name"].endswith(
            "__loopx_goal_start_verifier_feedback_todo"
        )
    ), feedback_plan
    feedback_prereqs = feedback_plan["runner_prerequisites"]
    assert feedback_prereqs["goal_start_product_mode"] is True, feedback_prereqs
    assert (
        feedback_prereqs["verifier_failure_feedback_todo_route"] is True
    ), feedback_prereqs
    assert (
        feedback_prereqs["verifier_failure_feedback_forwarded_to_agent"] is True
    ), feedback_prereqs
    assert feedback_prereqs["verifier_failure_todo_required"] is True, feedback_prereqs
    _assert_adapter_route_contract_surface()
    _assert_control_score_surface()
    _assert_host_local_acp_return_arity_compat()
    _assert_verifier_failure_feedback_todo_prompt()
    print("skillsbench-goal-start-product-mode-route-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
