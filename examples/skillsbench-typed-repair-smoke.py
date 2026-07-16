#!/usr/bin/env python3

import asyncio
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_typed_repair import (
    advance_skillsbench_typed_repair_controller,
    begin_skillsbench_typed_repair,
    build_skillsbench_typed_repair_prompt,
    record_skillsbench_typed_repair_terminal,
    resolve_skillsbench_typed_repair,
    skillsbench_projected_open_todo_count,
    skillsbench_turn_recovery_checkpoint,
)
from loopx.benchmark import build_skillsbench_benchflow_result_benchmark_run
from loopx.control_plane.runtime.goal_start_control_score import (
    build_goal_start_product_mode_control_score,
    compact_goal_start_product_mode_control_score,
)
from loopx.status import compact_benchmark_run
from examples.skillsbench_fixtures import write_official_skillsbench_result
from scripts.skillsbench_automation_loop import _build_blind_loop_user


def base_trace() -> dict[str, object]:
    return {
        "selected_p0_todo_id": "todo_fixture_primary",
        "remote_command_file_bridge_agent_task_facing_success_count": 2,
        "remote_command_file_bridge_agent_successful_loopx_command_records": [
            {
                "subcommand": "todo complete",
                "todo_id": "todo_fixture_primary",
            }
        ],
    }


def failed_turn_execution() -> dict[str, object]:
    return {
        "status": "failed",
        "validation": {
            "status": "failed",
            "recovery_kind": "repair_required",
        },
        "receipt": {
            "status": "failed",
            "failed_phase": "validation",
        },
        "effects": {
            "state_written": False,
            "quota_spent": False,
        },
    }


def committed_turn_execution() -> dict[str, object]:
    return {
        "status": "committed",
        "validation": {"status": "passed"},
        "receipt": {"status": "committed"},
        "effects": {
            "state_written": True,
            "quota_spent": True,
        },
    }


def write_failed_turn_trace(trace_dir: Path, index: int) -> None:
    payload = {
        "schema_version": "skillsbench_host_local_acp_relay_public_trace_v0",
        "trace_kind": "loopx_turn_execution",
        "loopx_turn_execution": failed_turn_execution(),
        "boundary": {
            key: False
            for key in (
                "raw_task_text_recorded",
                "raw_trajectory_recorded",
                "raw_stdout_recorded",
                "raw_stderr_recorded",
                "credential_values_recorded",
                "host_paths_recorded",
                "remote_paths_recorded",
            )
        },
    }
    (trace_dir / f"turn-{index}.compact.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_one_attempt_per_unchanged_frontier_and_reward_blind_prompt() -> None:
    trace = base_trace()
    assert skillsbench_projected_open_todo_count(trace) == 0
    assert begin_skillsbench_typed_repair(
        trace,
        trigger_round=2,
        scheduled_round=3,
    )
    assert not begin_skillsbench_typed_repair(
        trace,
        trigger_round=2,
        scheduled_round=3,
    )
    prompt = build_skillsbench_typed_repair_prompt(
        scheduled_round=3,
        max_rounds=8,
        case_state_path="/app/.codex/goals/case/ACTIVE_GOAL_STATE.md",
        loop_alignment_contract="Keep the case todo ledger current. ",
    )
    assert "typed repair/replan round 3 of 8" in prompt
    assert "create one scoped successor agent todo" in prompt
    assert "reward" not in prompt.lower()
    assert "verifier" not in prompt.lower()
    assert "pass/fail" not in prompt.lower()

    trace["remote_command_file_bridge_agent_successful_loopx_command_records"].append(
        {"subcommand": "todo update", "todo_id": "todo_fixture_primary"}
    )
    assert skillsbench_projected_open_todo_count(trace) is None


def test_open_todo_projection_fails_closed_when_public_history_is_saturated() -> None:
    trace = {
        "remote_command_file_bridge_agent_successful_loopx_command_records": [
            {"subcommand": "todo complete", "todo_id": "todo_fixture_primary"}
            for _ in range(128)
        ]
    }
    assert skillsbench_projected_open_todo_count(trace) is None


def test_todo_identity_or_task_validation_delta_allows_continuation() -> None:
    todo_trace = base_trace()
    assert begin_skillsbench_typed_repair(
        todo_trace,
        trigger_round=2,
        scheduled_round=3,
    )
    todo_trace[
        "remote_command_file_bridge_agent_successful_loopx_command_records"
    ].append(
        {
            "subcommand": "todo add",
            "todo_id": "todo_fixture_repair",
        }
    )
    todo_outcome = resolve_skillsbench_typed_repair(
        todo_trace,
        agent_round=3,
    )
    assert todo_outcome["delta_observed"] is True, todo_outcome
    assert todo_outcome["todo_identity_observed"] is True, todo_outcome
    assert todo_outcome["todo_ids"] == ["todo_fixture_repair"], todo_outcome

    task_trace = base_trace()
    assert begin_skillsbench_typed_repair(
        task_trace,
        trigger_round=4,
        scheduled_round=5,
    )
    task_trace["remote_command_file_bridge_agent_task_facing_success_count"] = 3
    task_outcome = resolve_skillsbench_typed_repair(
        task_trace,
        agent_round=5,
    )
    assert task_outcome["delta_observed"] is True, task_outcome
    assert task_outcome["task_or_validation_delta"] is True, task_outcome
    assert task_outcome["task_facing_success_delta"] == 1, task_outcome


def test_turn_recovery_requires_todo_or_committed_validation_delta() -> None:
    repeated_failure_trace = base_trace()
    repeated_failure_trace["loopx_turn_executions"] = [failed_turn_execution()]
    checkpoint = skillsbench_turn_recovery_checkpoint(repeated_failure_trace)
    assert checkpoint["repair_required"] is True, checkpoint
    assert checkpoint["failed_transaction_with_durable_effects"] is False, checkpoint
    assert checkpoint["recovery_required_count"] == 1, checkpoint
    assert begin_skillsbench_typed_repair(
        repeated_failure_trace,
        trigger_round=2,
        scheduled_round=3,
        trigger_kind="turn_transaction_recovery",
    )
    repeated_failure_trace[
        "remote_command_file_bridge_agent_task_facing_success_count"
    ] = 12
    repeated_failure_trace["loopx_turn_executions"].append(failed_turn_execution())
    repeated_outcome = resolve_skillsbench_typed_repair(
        repeated_failure_trace,
        agent_round=3,
    )
    assert repeated_outcome["task_facing_success_delta"] == 10, repeated_outcome
    assert repeated_outcome["turn_execution_count_delta"] == 1, repeated_outcome
    assert repeated_outcome["turn_recovery_required_count_delta"] == 1, (
        repeated_outcome
    )
    assert repeated_outcome["turn_committed_count_delta"] == 0, repeated_outcome
    assert repeated_outcome["turn_validation_delta"] is False, repeated_outcome
    assert repeated_outcome["delta_observed"] is False, repeated_outcome

    committed_trace = base_trace()
    committed_trace["loopx_turn_executions"] = [failed_turn_execution()]
    assert begin_skillsbench_typed_repair(
        committed_trace,
        trigger_round=4,
        scheduled_round=5,
        trigger_kind="turn_transaction_recovery",
    )
    committed_trace["loopx_turn_executions"].append(committed_turn_execution())
    committed_outcome = resolve_skillsbench_typed_repair(
        committed_trace,
        agent_round=5,
    )
    assert committed_outcome["turn_validation_delta"] is True, committed_outcome
    assert committed_outcome["turn_committed_count_delta"] == 1, committed_outcome
    assert committed_outcome["delta_observed"] is True, committed_outcome

    prompt = build_skillsbench_typed_repair_prompt(
        scheduled_round=5,
        max_rounds=8,
        case_state_path="/app/.codex/goals/case/ACTIVE_GOAL_STATE.md",
        loop_alignment_contract="Keep the case todo ledger current. ",
        trigger_kind="turn_transaction_recovery",
    )
    assert "later Turn receipt commits" in prompt, prompt
    assert "reward" not in prompt.lower(), prompt
    assert "verifier" not in prompt.lower(), prompt


def test_turn_recovery_controller_stops_or_continues_from_receipts() -> None:
    repeated_failure_trace = base_trace()
    repeated_failure_trace["loopx_turn_executions"] = [failed_turn_execution()]
    decision = advance_skillsbench_typed_repair_controller(
        repeated_failure_trace,
        agent_round=2,
        scheduled_round=3,
        max_rounds=8,
        task_instruction_sent=True,
    )
    assert decision["action"] == "send_repair_prompt", decision
    repeated_failure_trace[
        "remote_command_file_bridge_agent_task_facing_success_count"
    ] = 12
    repeated_failure_trace["loopx_turn_executions"].append(failed_turn_execution())
    decision = advance_skillsbench_typed_repair_controller(
        repeated_failure_trace,
        agent_round=3,
        scheduled_round=4,
        max_rounds=8,
        task_instruction_sent=True,
    )
    assert decision["action"] == "stop", decision
    assert repeated_failure_trace["product_mode_typed_repair_terminal_reason"] == (
        "turn_repair_round_without_todo_or_committed_validation_delta"
    )

    committed_trace = base_trace()
    committed_trace["loopx_turn_executions"] = [failed_turn_execution()]
    decision = advance_skillsbench_typed_repair_controller(
        committed_trace,
        agent_round=4,
        scheduled_round=5,
        max_rounds=8,
        task_instruction_sent=True,
    )
    assert decision["action"] == "send_repair_prompt", decision
    committed_trace["loopx_turn_executions"].append(committed_turn_execution())
    decision = advance_skillsbench_typed_repair_controller(
        committed_trace,
        agent_round=5,
        scheduled_round=6,
        max_rounds=8,
        task_instruction_sent=True,
    )
    assert decision["action"] == "continue", decision

    inconsistent_trace = base_trace()
    failed_with_effects = failed_turn_execution()
    failed_with_effects["effects"] = {
        "state_written": True,
        "quota_spent": False,
    }
    inconsistent_trace["loopx_turn_executions"] = [failed_with_effects]
    decision = advance_skillsbench_typed_repair_controller(
        inconsistent_trace,
        agent_round=6,
        scheduled_round=7,
        max_rounds=8,
        task_instruction_sent=True,
    )
    assert decision["action"] == "stop", decision
    assert inconsistent_trace["product_mode_typed_repair_terminal_reason"] == (
        "failed_turn_transaction_has_durable_effects"
    )


def test_turn_blind_controller_consumes_recovery_receipts() -> None:
    trace = {
        "schema_version": "skillsbench_loopx_controller_trace_v0",
        "route": "loopx-turn-agent-cli",
        "round_rewards": [],
    }
    fake_user = types.ModuleType("benchflow.sandbox.user")
    fake_user.BaseUser = type("BaseUser", (), {})
    fake_user.RoundResult = type("RoundResult", (), {})
    fake_modules = {
        "benchflow": types.ModuleType("benchflow"),
        "benchflow.sandbox": types.ModuleType("benchflow.sandbox"),
        "benchflow.sandbox.user": fake_user,
    }
    round_result = types.SimpleNamespace(
        rewards={}, n_tool_calls=1, trajectory=[]
    )
    with patch.dict(sys.modules, fake_modules):
        with tempfile.TemporaryDirectory(prefix="turn-recovery-controller-") as tmp:
            trace_dir = Path(tmp)
            user = _build_blind_loop_user(
                route="loopx-turn-agent-cli",
                max_rounds=8,
                trace=trace,
                plan={
                    "route": "loopx-turn-agent-cli",
                    "host_local_acp_relay_trace_dir": str(trace_dir),
                    "runner_prerequisites": {},
                },
            )
            assert asyncio.run(user.run(0, "Fix the workbook.")) is not None
            write_failed_turn_trace(trace_dir, 1)
            repair_prompt = asyncio.run(
                user.run(1, "Fix the workbook.", round_result)
            )
            assert "later Turn receipt commits" in repair_prompt, repair_prompt
            assert trace["product_mode_typed_repair_pending"] is True, trace
            write_failed_turn_trace(trace_dir, 2)
            assert asyncio.run(
                user.run(2, "Fix the workbook.", round_result)
            ) is None
            assert trace["product_mode_typed_repair_terminal_reason"] == (
                "turn_repair_round_without_todo_or_committed_validation_delta"
            ), trace


def test_unchanged_frontier_has_typed_terminal_receipt() -> None:
    trace = base_trace()
    assert begin_skillsbench_typed_repair(
        trace,
        trigger_round=2,
        scheduled_round=3,
    )
    outcome = resolve_skillsbench_typed_repair(trace, agent_round=3)
    assert outcome["delta_observed"] is False, outcome
    receipt = record_skillsbench_typed_repair_terminal(
        trace,
        agent_round=3,
        reason="repair_round_without_todo_task_or_validation_delta",
    )
    assert receipt["status"] == "terminal", receipt
    assert receipt["repair_round_entered"] == 3, receipt
    assert receipt["repair_todo_identity_observed"] is False, receipt
    assert receipt["repair_task_or_validation_delta"] is False, receipt
    assert receipt["terminal_receipt_consistent"] is True, receipt
    assert receipt["raw_material_recorded"] is False, receipt


def test_goal_start_control_score_preserves_typed_repair_fields() -> None:
    score = build_goal_start_product_mode_control_score(
        {
            "interaction_counters": {
                "goal_start_product_mode": True,
                "product_mode_typed_repair_round_entered": 3,
                "product_mode_typed_repair_todo_identity_observed": True,
                "product_mode_typed_repair_task_or_validation_delta": False,
                "product_mode_typed_repair_terminal_receipt_consistent": True,
            }
        },
        runner_prerequisites={},
    )
    assert score["repair_round_entered"] == 3, score
    assert score["repair_todo_identity_observed"] is True, score
    assert score["repair_task_or_validation_delta"] is False, score
    assert score["terminal_receipt_consistent"] is True, score
    compact = compact_goal_start_product_mode_control_score(score)
    assert compact["repair_round_entered"] == 3, compact
    assert compact["repair_todo_identity_observed"] is True, compact
    assert compact["repair_task_or_validation_delta"] is False, compact
    assert compact["terminal_receipt_consistent"] is True, compact


def test_typed_repair_projection_survives_result_compaction() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-typed-repair-") as tmp:
        result_path = write_official_skillsbench_result(Path(tmp), reward=0.0)
        controller_trace = {
            "schema_version": "skillsbench_loopx_controller_trace_v0",
            "route": "loopx-goal-start-product-mode",
            "trace_publicness": "public_counts_only_no_task_text_no_verifier_output",
            "product_mode": True,
            "goal_start_product_mode": True,
            "agent_declared_done": True,
            "agent_declared_no_remaining_goals": True,
            "product_mode_typed_repair_required": True,
            "product_mode_typed_repair_policy_id": (
                "one_typed_repair_per_frontier_v0"
            ),
            "product_mode_typed_repair_round_entered": 3,
            "product_mode_typed_repair_todo_identity_observed": False,
            "product_mode_typed_repair_task_or_validation_delta": False,
            "product_mode_typed_repair_terminal": True,
            "product_mode_typed_repair_terminal_round": 3,
            "product_mode_typed_repair_terminal_reason": (
                "repair_round_without_todo_task_or_validation_delta"
            ),
            "product_mode_typed_repair_terminal_receipt_consistent": True,
            "raw_task_text_recorded": False,
            "raw_verifier_output_recorded": False,
            "raw_agent_trajectory_recorded": False,
        }
        compact = compact_benchmark_run(
            build_skillsbench_benchflow_result_benchmark_run(
                result_path,
                route="loopx-goal-start-product-mode",
                controller_trace=controller_trace,
            )
        )
        assert compact is not None
        counters = compact["interaction_counters"]
        assert counters["product_mode_typed_repair_required"] is True, counters
        assert counters["product_mode_typed_repair_round_entered"] == 3, counters
        assert counters["product_mode_typed_repair_terminal"] is True, counters
        assert counters["product_mode_typed_repair_terminal_reason"] == (
            "repair_round_without_todo_task_or_validation_delta"
        )
        round_trace = compact["round_reward_trace"]
        assert round_trace["product_mode_typed_repair_terminal"] is True, round_trace
        assert round_trace["product_mode_typed_repair_round_entered"] == 3, round_trace
        todo_flow = compact["post_run_debug_gate"]["todo_flow"]
        assert todo_flow["typed_repair_terminal"] is True, todo_flow
        assert todo_flow["typed_repair_terminal_receipt_consistent"] is True, todo_flow
        labels = compact["failure_attribution_labels"]
        assert "skillsbench_product_mode_typed_repair_terminal" in labels, labels
        assert "skillsbench_solver_exhausted_after_typed_repair" in labels, labels


if __name__ == "__main__":
    test_one_attempt_per_unchanged_frontier_and_reward_blind_prompt()
    test_open_todo_projection_fails_closed_when_public_history_is_saturated()
    test_todo_identity_or_task_validation_delta_allows_continuation()
    test_turn_recovery_requires_todo_or_committed_validation_delta()
    test_turn_recovery_controller_stops_or_continues_from_receipts()
    test_turn_blind_controller_consumes_recovery_receipts()
    test_unchanged_frontier_has_typed_terminal_receipt()
    test_goal_start_control_score_preserves_typed_repair_fields()
    test_typed_repair_projection_survives_result_compaction()
    print("skillsbench-typed-repair-smoke: ok")
