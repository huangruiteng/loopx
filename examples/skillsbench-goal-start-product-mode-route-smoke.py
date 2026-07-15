#!/usr/bin/env python3
"""Smoke-test the SkillsBench goal-start product-mode route plan surface."""

from __future__ import annotations

import asyncio
import json
from argparse import Namespace
import shlex
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]


def _assert_agent_authored_goal_start_bootstrap() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_case_state import benchmark_case_loopx_install_payload

    payload = benchmark_case_loopx_install_payload(
        benchmark_id="skillsbench",
        case_id="planning-granularity",
        arm_id="loopx_goal_start_product_mode",
        route="loopx-goal-start-product-mode",
        max_rounds=5,
        goal_start_product_mode=True,
    )
    command = str(payload["command"])
    assert payload["case_todo_seeded"] is False, payload
    assert payload["canonical_product_mode_lifecycle_driver"] is False, payload
    assert payload["goal_start_plan_observed"] is False, payload
    assert payload["goal_start_guided_command_required"] is True, payload
    assert payload["goal_start_agent_authored_plan_required"] is True, payload
    assert payload["goal_start_host_preseed_forbidden"] is True, payload
    assert payload["planned_todo_count"] == 0, payload
    assert payload["planned_todo_count_expected"] == 3, payload
    assert "bootstrap-command-pack" not in command, command
    assert " todo add " not in command, command
    assert " quota should-run " not in command, command
    assert " refresh-state " not in command, command
    assert "loopx_case_init_phase:await_agent_goal_start" in command, command


def _assert_bridge_tracks_guided_start_without_task_text() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
    )
    private_task_text = "PRIVATE_TASK_SENTINEL do not publish"
    todo_id = "todo_agent_ranked_solver"
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        summary_path = temp_path / "agent-operations.jsonl"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(remote_command_file_bridge_command="cat")
        )
        wrapper = relay._write_instrumented_bridge_wrapper(
            tmp_path=temp_path,
            summary_path=summary_path,
        )
        start_request = {
            "operation": "exec",
            "cwd": "/app",
            "command": (
                "/app/.local/bin/loopx --registry /app/.loopx/registry.json "
                "--runtime-root /app/.loopx/runtime --format json start-goal "
                "--guided --project /app --goal-text "
                + json.dumps(private_task_text)
            ),
        }
        subprocess.run(
            [str(wrapper)],
            input=json.dumps(start_request),
            text=True,
            check=True,
            capture_output=True,
        )
        todo_request = {
            "operation": "exec",
            "cwd": "/app",
            "command": (
                "/app/.local/bin/loopx --format json todo add "
                "--goal-id skillsbench-case --role agent --todo-id "
                f"{todo_id} "
                "--text 'public safe solver todo'"
            ),
        }
        subprocess.run(
            [str(wrapper)],
            input=json.dumps(todo_request),
            text=True,
            check=True,
            capture_output=True,
        )
        summary_text = summary_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in summary_text.splitlines()]
    assert private_task_text not in summary_text, summary_text
    completed = [record for record in records if record.get("record_phase") == "complete"]
    assert completed[0]["loopx_subcommands"] == ["start-goal"], completed
    assert completed[0]["loopx_state_read"] is True, completed
    assert completed[0]["raw_task_text_recorded"] is False, completed
    assert completed[1]["loopx_subcommands"] == ["todo", "add"], completed
    assert completed[1]["loopx_state_write"] is True, completed
    assert completed[1]["loopx_todo_id"] == todo_id


def _assert_bridge_tracks_generated_todo_id_without_raw_output() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
    )

    private_stdout = "PRIVATE_STDOUT_SENTINEL do not publish"
    generated_todo_id = "todo_generated_solver_plan"
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        fake_bridge = temp_path / "fake-bridge.py"
        fake_bridge.write_text(
            "import json, sys\n"
            "request = json.loads(sys.stdin.read() or '{}')\n"
            f"cli_payload = {{'ok': True, 'todo_id': {generated_todo_id!r}, "
            f"'detail': {private_stdout!r}}}\n"
            "print(json.dumps({'ok': True, 'exit_code': 0, "
            "'stdout': json.dumps(cli_payload), 'stderr': ''}))\n",
            encoding="utf-8",
        )
        summary_path = temp_path / "agent-operations.jsonl"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                remote_command_file_bridge_command=(
                    f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_bridge))}"
                )
            )
        )
        wrapper = relay._write_instrumented_bridge_wrapper(
            tmp_path=temp_path,
            summary_path=summary_path,
        )
        request = {
            "operation": "exec",
            "cwd": "/app",
            "command": (
                "/app/.local/bin/loopx --format json todo add "
                "--goal-id skillsbench-case --role agent "
                "--text 'public safe solver todo'"
            ),
        }
        result = subprocess.run(
            [str(wrapper)],
            input=json.dumps(request),
            text=True,
            check=True,
            capture_output=True,
        )
        summary_text = summary_path.read_text(encoding="utf-8")
        records = [json.loads(line) for line in summary_text.splitlines()]

    assert private_stdout in result.stdout, result.stdout
    assert private_stdout not in summary_text, summary_text
    completed = [record for record in records if record.get("record_phase") == "complete"]
    assert completed[-1]["loopx_todo_id"] == generated_todo_id, completed
    assert completed[-1]["raw_stdout_recorded"] is False, completed


def _assert_bridge_rejects_batched_loopx_commands() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        CodexExecConfig,
        SkillsBenchLocalAcpRelay,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        marker = temp_path / "bridge-invoked"
        fake_bridge = temp_path / "fake-bridge.py"
        fake_bridge.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('invoked', encoding='utf-8')\n"
            "print('{}')\n",
            encoding="utf-8",
        )
        summary_path = temp_path / "agent-operations.jsonl"
        relay = SkillsBenchLocalAcpRelay(
            CodexExecConfig(
                remote_command_file_bridge_command=(
                    f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_bridge))}"
                )
            )
        )
        wrapper = relay._write_instrumented_bridge_wrapper(
            tmp_path=temp_path,
            summary_path=summary_path,
        )
        commands = {
            "newline": (
                "/app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_first --role agent --text first\n"
                "/app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_second --role agent --text second"
            ),
            "if": (
                "if /app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_first --role agent --text first; then "
                "/app/.local/bin/loopx todo claim --goal-id case "
                "--todo-id todo_agent_first --claimed-by agent; fi"
            ),
            "command": (
                "command /app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_first --role agent --text first && "
                "command /app/.local/bin/loopx todo claim --goal-id case "
                "--todo-id todo_agent_first --claimed-by agent"
            ),
            "nested-shell": "sh -c "
            + shlex.quote(
                "/app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_first --role agent --text first; "
                "/app/.local/bin/loopx todo claim --goal-id case "
                "--todo-id todo_agent_first --claimed-by agent"
            ),
        }
        for label, command in commands.items():
            request = {"operation": "exec", "cwd": "/app", "command": command}
            result = subprocess.run(
                [str(wrapper)],
                input=json.dumps(request),
                text=True,
                check=False,
                capture_output=True,
            )
            records = [
                json.loads(line)
                for line in summary_path.read_text(encoding="utf-8").splitlines()
            ]
            assert result.returncode == 2, (label, result)
            assert "exactly one LoopX CLI command" in result.stderr, (
                label,
                result.stderr,
            )
            assert marker.exists() is False, label
            completed = [
                record for record in records if record.get("record_phase") == "complete"
            ]
            assert completed[-1]["loopx_invocation_count"] == 2, (label, completed)
            assert completed[-1]["failure_category"] == (
                "multiple_loopx_commands_per_bridge_request"
            ), (label, completed)

        wrapped_single_commands = {
            "command": (
                "command /app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_command --role agent "
                "--text 'mention sh -c loopx safely'"
            ),
            "nested-shell": "sh -c "
            + shlex.quote(
                "/app/.local/bin/loopx todo add --goal-id case "
                "--todo-id todo_agent_nested_shell --role agent --text nested"
            ),
        }
        for label, command in wrapped_single_commands.items():
            marker.unlink(missing_ok=True)
            request = {"operation": "exec", "cwd": "/app", "command": command}
            result = subprocess.run(
                [str(wrapper)],
                input=json.dumps(request),
                text=True,
                check=False,
                capture_output=True,
            )
            records = [
                json.loads(line)
                for line in summary_path.read_text(encoding="utf-8").splitlines()
            ]
            assert result.returncode == 0, (label, result)
            assert marker.exists() is True, label
            completed = [
                record for record in records if record.get("record_phase") == "complete"
            ]
            assert completed[-1]["loopx_invocation_count"] == 1, (label, completed)
            assert completed[-1]["loopx_subcommands"] == ["todo", "add"], (
                label,
                completed,
            )
            assert completed[-1]["loopx_todo_id"] == f"todo_agent_{label.replace('-', '_')}", (
                label,
                completed,
            )


def _assert_generated_prompt_requires_agent_authored_separate_requests() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_case_state import (
        BENCHMARK_CASE_LOOPX_GOAL_START_TODO_ACTION_KINDS,
        BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS,
        BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS,
        benchmark_case_loopx_install_payload,
    )
    from scripts.skillsbench_automation_loop import _build_product_mode_user

    class FakeBaseUser:
        pass

    class FakeRoundResult:
        pass

    benchflow_module = types.ModuleType("benchflow")
    sandbox_module = types.ModuleType("benchflow.sandbox")
    user_module = types.ModuleType("benchflow.sandbox.user")
    user_module.BaseUser = FakeBaseUser
    user_module.RoundResult = FakeRoundResult
    case_payload = benchmark_case_loopx_install_payload(
        benchmark_id="skillsbench",
        case_id="planning-granularity",
        arm_id="loopx_goal_start_product_mode",
        route="loopx-goal-start-product-mode",
        max_rounds=5,
        goal_start_product_mode=True,
    )
    plan = {
        "runner_prerequisites": {
            "goal_start_product_mode": True,
            "goal_start_planned_todo_count_expected": 3,
        }
    }
    with patch.dict(
        sys.modules,
        {
            "benchflow": benchflow_module,
            "benchflow.sandbox": sandbox_module,
            "benchflow.sandbox.user": user_module,
        },
    ):
        user = _build_product_mode_user(
            route="loopx-goal-start-product-mode",
            max_rounds=5,
            trace={},
            plan=plan,
            case_payload=case_payload,
        )
        prompt = asyncio.run(user.run(0, "PRIVATE TASK INSTRUCTION"))

    assert prompt is not None
    assert "Exactly one LoopX CLI command" in prompt, prompt
    assert "<TODO_ID>" in prompt, prompt
    assert "<SHELL_QUOTED_TODO_TEXT>" in prompt, prompt
    assert "<ACTION_KIND>" in prompt, prompt
    assert "<SELECTED_TODO_ID>" in prompt, prompt
    assert prompt.count("--todo-id <TODO_ID>") == 3, prompt
    for fixed_value in (
        *BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS,
        *BENCHMARK_CASE_LOOPX_GOAL_START_TODO_TEXTS,
        *BENCHMARK_CASE_LOOPX_GOAL_START_TODO_ACTION_KINDS,
    ):
        assert fixed_value not in prompt, (fixed_value, prompt)


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
    assert contract["loopx_slash_command"] == "/loopx <task objective>", contract
    assert contract["goal_start_guided_command_required"] is True, contract
    assert contract["goal_start_agent_authored_plan_required"] is True, contract
    assert contract["goal_start_host_preseed_forbidden"] is True, contract
    assert "guided_loopx_slash_start" in contract["skillsbench_route_semantics"], contract

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
    try:
        skillsbench_route_contract(feedback_route)
    except ValueError as exc:
        assert "unsupported SkillsBench route" in str(exc)
    else:
        raise AssertionError("verifier-feedback todo route must stay unsupported")
    try:
        build_skillsbench_benchmark_run(route=feedback_route)
    except ValueError as exc:
        assert "unsupported SkillsBench route" in str(exc)
    else:
        raise AssertionError("verifier-feedback todo skeleton must stay unsupported")


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
    planned_todo_ids = [
        "todo_agent_ranked_solver",
        "todo_agent_ranked_validation",
        "todo_agent_ranked_closeout",
    ]
    selected_todo_id = planned_todo_ids[0]
    command_records = [
        {"subcommand": "start-goal"},
        *[
            {"subcommand": "todo add", "todo_id": todo_id}
            for todo_id in planned_todo_ids
        ],
        {"subcommand": "todo claim", "todo_id": selected_todo_id},
        {"subcommand": "todo update", "todo_id": selected_todo_id},
        {"subcommand": "todo complete", "todo_id": selected_todo_id},
        {"subcommand": "refresh-state"},
        {"subcommand": "quota spend-slot"},
    ]

    compact = {
        "product_mode": True,
        "interaction_counters": {
            "goal_start_product_mode": True,
            "goal_start_plan_observed": False,
            "planned_todo_count": 0,
            "planned_p0_count": 0,
            "planner_before_todo_write": False,
            "same_priority_order_preserved": False,
            "remote_command_file_bridge_agent_successful_loopx_command_records": (
                command_records
            ),
            "remote_command_file_bridge_agent_successful_loopx_subcommand_counts": {
                "start-goal": 1,
                "todo add": 3,
                "todo claim": 1,
                "todo update": 1,
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
            "goal_start_guided_command_required": True,
            "goal_start_agent_authored_plan_required": True,
            "goal_start_host_preseed_forbidden": True,
            "goal_start_planned_todo_count_expected": 3,
            "goal_start_selected_p0_lifecycle_required": True,
        },
    }
    control_score = _build_goal_start_product_mode_control_score(compact, plan)
    assert control_score["satisfied"] is True, control_score
    assert control_score["score"] == 1.0, control_score
    assert control_score["raw_material_recorded"] is False, control_score
    assert control_score["goal_start_guided_command_observed"] is True, control_score
    assert control_score["agent_start_goal_count"] == 1, control_score
    assert control_score["agent_todo_add_count"] == 3, control_score
    assert control_score["planned_todo_ids"] == planned_todo_ids, control_score
    assert control_score["selected_todo_completed_before_spend"] is True, control_score
    host_preseeded_score = _build_goal_start_product_mode_control_score(
        {
            "interaction_counters": {
                "goal_start_product_mode": True,
                "goal_start_plan_observed": True,
                "planned_todo_count": 3,
                "planned_p0_count": 1,
                "planner_before_todo_write": True,
                "same_priority_order_preserved": True,
                "selected_p0_todo_id": selected_todo_id,
                "selected_todo_claimed": True,
                "selected_todo_updated_before_solver": True,
                "selected_todo_completed_before_spend": True,
                "non_selected_todos_preserved_open_or_deferred": True,
            }
        },
        plan,
    )
    assert host_preseeded_score["satisfied"] is False, host_preseeded_score
    assert (
        host_preseeded_score["goal_start_guided_command_observed"] is False
    ), host_preseeded_score
    assert host_preseeded_score["planned_todo_count"] == 0, host_preseeded_score
    duplicate_plan_score = _build_goal_start_product_mode_control_score(
        {
            "interaction_counters": {
                "goal_start_product_mode": True,
                "remote_command_file_bridge_agent_successful_loopx_command_records": [
                    {"subcommand": "start-goal"},
                    {"subcommand": "todo add", "todo_id": planned_todo_ids[0]},
                    {"subcommand": "todo add", "todo_id": planned_todo_ids[0]},
                    {"subcommand": "todo add", "todo_id": planned_todo_ids[1]},
                ],
            }
        },
        plan,
    )
    assert duplicate_plan_score["satisfied"] is False, duplicate_plan_score
    assert duplicate_plan_score["same_priority_order_preserved"] is False, (
        duplicate_plan_score
    )
    explicitly_selected_todo_id = planned_todo_ids[1]
    explicit_selection_score = _build_goal_start_product_mode_control_score(
        {
            "interaction_counters": {
                "goal_start_product_mode": True,
                "remote_command_file_bridge_agent_successful_loopx_command_records": [
                    {"subcommand": "start-goal"},
                    *[
                        {"subcommand": "todo add", "todo_id": todo_id}
                        for todo_id in planned_todo_ids
                    ],
                    {
                        "subcommand": "todo claim",
                        "todo_id": explicitly_selected_todo_id,
                    },
                    {
                        "subcommand": "todo update",
                        "todo_id": explicitly_selected_todo_id,
                    },
                    {
                        "subcommand": "todo complete",
                        "todo_id": explicitly_selected_todo_id,
                    },
                    {"subcommand": "quota spend-slot"},
                ],
            }
        },
        plan,
    )
    assert explicit_selection_score["satisfied"] is True, explicit_selection_score
    assert explicit_selection_score["selected_p0_todo_id"] == (
        explicitly_selected_todo_id
    ), explicit_selection_score
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
    assert goal_start["selected_p0_todo_id"] == selected_todo_id, goal_start
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
    assert compacted_prerequisites["goal_start_guided_command_required"] is True
    assert compacted_prerequisites["goal_start_agent_authored_plan_required"] is True
    assert compacted_prerequisites["goal_start_host_preseed_forbidden"] is True
    assert compacted_prerequisites["goal_start_planned_todo_count_expected"] == 3


def _assert_lifecycle_gates_use_successful_command_records() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.skillsbench_automation_loop import (
        _product_mode_agent_lifecycle_gate_satisfied,
        _product_mode_depth_gate_satisfied,
    )

    trace = {
        "remote_command_file_bridge_agent_operation_trace_required": True,
        "remote_command_file_bridge_agent_successful_loopx_command_records": [
            {"subcommand": "start-goal"},
            {"subcommand": "todo add", "todo_id": "todo_public_solver"},
        ],
    }
    assert _product_mode_agent_lifecycle_gate_satisfied(trace) is True, trace
    assert _product_mode_depth_gate_satisfied(trace) is True, trace

    read_only_trace = {
        "remote_command_file_bridge_agent_operation_trace_required": True,
        "remote_command_file_bridge_agent_successful_loopx_command_records": [
            {"subcommand": "start-goal"},
        ],
    }
    assert (
        _product_mode_agent_lifecycle_gate_satisfied(read_only_trace) is False
    ), read_only_trace
    assert _product_mode_depth_gate_satisfied(read_only_trace) is False, read_only_trace

    todo_read_trace = {
        "remote_command_file_bridge_agent_operation_trace_required": True,
        "remote_command_file_bridge_agent_successful_loopx_command_records": [
            {"subcommand": "start-goal"},
            {"subcommand": "todo list"},
        ],
    }
    assert (
        _product_mode_agent_lifecycle_gate_satisfied(todo_read_trace) is False
    ), todo_read_trace
    assert _product_mode_depth_gate_satisfied(todo_read_trace) is False, todo_read_trace


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


def _assert_app_server_goal_baseline_bridge_contract() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from loopx.benchmark_adapters.skillsbench_acp_relay import (
        _prompt_with_app_server_closeout_instruction,
    )
    from scripts.skillsbench_automation_loop import (
        _host_local_acp_launch_command,
    )

    args = Namespace(
        local_acp_relay_command="",
        route="codex-app-server-goal-baseline",
        app_server_reasoning_effort="high",
        app_server_acp_heartbeat_interval_sec=120.0,
        dataset="skillsbench@1.1",
        task_id="3d-scan-calc",
        local_codex_bin="codex",
        local_codex_sandbox="workspace-write",
        local_codex_first_action_timeout_sec=0,
        local_codex_bridge_idle_timeout_sec=3600,
        local_codex_exec_timeout_sec=3600,
        agent_idle_timeout=3600,
        model="gpt-5.5",
        host_local_acp_launch=True,
        remote_command_file_bridge_solver_command="python bridge.py",
        remote_command_file_bridge_ready=True,
        remote_command_file_bridge_probe=False,
        remote_command_file_bridge_probe_timeout_sec=10,
        remote_command_file_bridge_agent_command="",
    )
    command = _host_local_acp_launch_command(
        args,
        {"app_server_goal_worker_trace_dir": "/tmp/worker-traces"},
    )
    assert "--app-server-goal-worker" in command, command
    assert "--remote-command-file-bridge-command" in command, command
    bridge_index = command.index("--remote-command-file-bridge-command")
    assert command[bridge_index + 1] == "python bridge.py", command
    assert "--worker-public-trace-dir" in command, command

    prompt = _prompt_with_app_server_closeout_instruction(
        "Read /app/problem.json. It declares plan_output=task01.txt."
    )
    assert "Native Codex Goal worker closeout contract" in prompt, prompt
    assert "immediately end the turn" in prompt, prompt
    assert "scored output file" in prompt, prompt
    assert "Honor every task input and output path exactly" in prompt, prompt
    assert "directory containing the metadata file that declares it" in prompt, prompt
    assert "Do not force relative paths into `/root` or `/app`" in prompt, prompt
    assert "relative task output file names from `/root`" not in prompt, prompt
    assert "`/root/<name>`" not in prompt, prompt
    assert "Before writing the final scored output" in prompt, prompt
    assert "task-derived quality self-check" in prompt, prompt
    assert "visible task instructions and workspace data" in prompt, prompt
    assert "official verifier/reward/pass-fail output" in prompt, prompt
    assert "hidden tests" in prompt, prompt
    assert "final task-specified output" in prompt, prompt
    assert prompt.index("Before writing the final scored output") < prompt.index(
        "After the task-required scored output file"
    ), prompt


def _assert_verifier_feedback_routes_disabled() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    import scripts.skillsbench_automation_loop as runner

    assert not hasattr(runner, "_build_verifier_failure_feedback_todo_prompt")
    assert not hasattr(runner, "_record_verifier_failure_feedback_todo_prompt")
    assert "loopx-goal-start-verifier-feedback-todo" not in runner.SUPPORTED_ROUTES
    assert "automation-loop-treatment" not in runner.SUPPORTED_ROUTES


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
    assert prerequisites["goal_start_guided_command_required"] is True, prerequisites
    assert prerequisites["goal_start_agent_authored_plan_required"] is True, prerequisites
    assert prerequisites["goal_start_host_preseed_forbidden"] is True, prerequisites
    assert prerequisites["goal_start_planned_todo_count_expected"] == 3, prerequisites
    assert prerequisites["goal_start_selected_p0_lifecycle_required"] is True, prerequisites
    assert prerequisites["loopx_workflow_lifecycle_checkpoint"] is False, prerequisites
    assert prerequisites["loopx_product_mode_lifecycle_driver_kind"] == (
        "prompt_driven_loopx_cli"
    ), prerequisites
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
        check=False,
        capture_output=True,
        text=True,
    )
    assert feedback_result.returncode != 0, feedback_result
    assert "unsupported --route" in feedback_result.stderr, feedback_result.stderr
    _assert_adapter_route_contract_surface()
    _assert_agent_authored_goal_start_bootstrap()
    _assert_bridge_tracks_guided_start_without_task_text()
    _assert_bridge_tracks_generated_todo_id_without_raw_output()
    _assert_bridge_rejects_batched_loopx_commands()
    _assert_generated_prompt_requires_agent_authored_separate_requests()
    _assert_control_score_surface()
    _assert_lifecycle_gates_use_successful_command_records()
    _assert_host_local_acp_return_arity_compat()
    _assert_app_server_goal_baseline_bridge_contract()
    _assert_verifier_feedback_routes_disabled()
    print("skillsbench-goal-start-product-mode-route-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
