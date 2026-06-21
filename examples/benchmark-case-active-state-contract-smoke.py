#!/usr/bin/env python3
"""Smoke-test the shared benchmark case active-state contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import (  # noqa: E402
    AGENTS_LAST_EXAM_BENCHMARK_ID,
    AGENTS_LAST_EXAM_CASE_GOAL_ID,
    AGENTS_LAST_EXAM_CASE_STATE_PATH,
    SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID,
    SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH,
    TERMINAL_BENCH_CASE_GOAL_ID,
    TERMINAL_BENCH_CASE_STATE_PATH,
    build_agents_last_exam_local_launch_packet,
    build_terminal_bench_case_state_init_contract,
    build_terminal_bench_goal_harness_access_packet_fixture,
)
from goal_harness.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS,
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LIFECYCLE_SCHEMA_VERSION,
    benchmark_case_active_state_init_contract,
    benchmark_case_active_state_path,
    benchmark_case_active_state_seed_text,
    benchmark_case_active_state_write_command,
    benchmark_case_arm_goal_id,
    benchmark_case_goal_id,
    benchmark_case_lifecycle_contract,
    render_benchmark_case_lifecycle_contract_lines,
)


def assert_contract_shape(contract: dict[str, object], expected_path: str) -> None:
    assert contract["schema_version"] == BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
    assert contract["case_state_path"] == expected_path
    assert expected_path.startswith("/app/.codex/goals/")
    assert expected_path.endswith("/ACTIVE_GOAL_STATE.md")
    assert contract["init_required_before_worker"] is True
    assert contract["initialized_by_launch_packet"] is False
    assert contract["init_stage"] == "before_codex_worker_start"
    assert contract["init_flow"] == "shared_goal_harness_benchmark_case_active_state"
    assert contract["status_field"] == "case_goal_state_init_status"
    assert set(BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS).issubset(
        set(contract["proof_fields"])
    )
    assert contract["surrogate_state_files_allowed"] is False
    assert contract["raw_task_text_required_for_init"] is False
    assert contract["local_paths_recorded"] is False
    rendered = json.dumps(contract, sort_keys=True)
    assert ".goal-harness-case-state.md" not in rendered
    assert "/Users/" not in rendered


def test_shared_contract_for_current_benchmark_routes() -> None:
    cases = [
        (
            "skillsbench",
            SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID,
            SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH,
        ),
        ("terminal-bench", TERMINAL_BENCH_CASE_GOAL_ID, TERMINAL_BENCH_CASE_STATE_PATH),
        (
            AGENTS_LAST_EXAM_BENCHMARK_ID,
            AGENTS_LAST_EXAM_CASE_GOAL_ID,
            AGENTS_LAST_EXAM_CASE_STATE_PATH,
        ),
    ]
    for benchmark_id, goal_id, state_path in cases:
        contract = benchmark_case_active_state_init_contract(
            benchmark_id=benchmark_id,
            goal_id=goal_id,
            case_state_path=state_path,
        )
        assert contract["benchmark_case_goal_id"] == goal_id
        assert_contract_shape(contract, state_path)


def test_seed_text_uses_real_goal_harness_active_state_shape() -> None:
    goal_id = benchmark_case_goal_id("terminal-bench")
    state_path = benchmark_case_active_state_path(goal_id)
    seed = benchmark_case_active_state_seed_text(
        benchmark_name="Terminal-Bench",
        goal_id=goal_id,
        task_id="public-task-id",
        route="goal-harness-product-mode",
        max_rounds=5,
        case_state_path=state_path,
    )
    assert "goal_id: terminal-bench-case" in seed
    assert f"schema_version: {BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION}" in seed
    assert state_path in seed
    assert "## Agent Todo" in seed
    assert "## Next Action" in seed
    assert ".goal-harness-case-state.md" not in seed
    assert "/Users/" not in seed


def test_seed_write_command_uses_canonical_path() -> None:
    goal_id = benchmark_case_goal_id("terminal-bench")
    state_path = benchmark_case_active_state_path(goal_id)
    seed = benchmark_case_active_state_seed_text(
        benchmark_name="Terminal-Bench",
        goal_id=goal_id,
        task_id="public-task-id",
        route="goal-harness-product-mode",
        max_rounds=5,
        case_state_path=state_path,
    )
    command = benchmark_case_active_state_write_command(
        case_state_path=state_path,
        content=seed,
    )
    assert state_path in command
    assert "mktemp" in command
    assert "mv" in command
    assert ".goal-harness-case-state.md" not in command
    assert "/Users/" not in command


def test_case_lifecycle_contract_is_per_case_arm() -> None:
    contract = benchmark_case_lifecycle_contract(
        benchmark_id="swe-marathon",
        case_id="find-network-alignments",
        arm_id="codex_goal_harness_treatment",
        max_rounds=5,
    )
    expected_goal_id = benchmark_case_arm_goal_id(
        benchmark_id="swe-marathon",
        case_id="find-network-alignments",
        arm_id="codex_goal_harness_treatment",
    )
    assert contract["schema_version"] == BENCHMARK_CASE_LIFECYCLE_SCHEMA_VERSION
    assert contract["case_isolation_scope"] == "per_benchmark_case_arm"
    assert contract["benchmark_case_goal_id"] == expected_goal_id
    assert contract["case_state_path"] == benchmark_case_active_state_path(expected_goal_id)
    assert contract["source_of_truth"] == "case_active_state_and_rollout_event_log"
    assert "quota_should_run" in contract["required_lifecycle_steps"]
    assert "todo_claim_or_update" in contract["required_lifecycle_steps"]
    assert "refresh_state" in contract["required_lifecycle_steps"]
    assert "quota_spend" in contract["required_lifecycle_steps"]
    assert "compact_case_result" in contract["required_rollout_event_kinds"]
    assert contract["runner_internal_prompt_polling_only_allowed"] is False
    assert contract["surrogate_state_files_allowed"] is False
    lines = render_benchmark_case_lifecycle_contract_lines(contract)
    rendered = "\n".join(lines)
    assert "benchmark_case_lifecycle_contract:" in rendered
    assert "case_isolation_scope: per_benchmark_case_arm" in rendered
    assert "/app/.codex/goals/" in rendered
    assert "/Users/" not in rendered


def test_ale_launch_packet_reuses_shared_contract() -> None:
    packet = build_agents_last_exam_local_launch_packet(
        source_root=None,
        experiment_spec_relative_path=None,
    )
    expected = benchmark_case_active_state_init_contract(
        benchmark_id=AGENTS_LAST_EXAM_BENCHMARK_ID,
        goal_id=AGENTS_LAST_EXAM_CASE_GOAL_ID,
        case_state_path=AGENTS_LAST_EXAM_CASE_STATE_PATH,
    )
    assert packet["case_state_init_contract"] == expected


def test_terminal_bench_access_packet_fixture_reuses_shared_contract() -> None:
    fixture = build_terminal_bench_goal_harness_access_packet_fixture()
    expected = build_terminal_bench_case_state_init_contract()
    access_packet = fixture["access_packet"]
    counters = fixture["interaction_counters"]
    assert access_packet["case_state_init_contract"] == expected
    assert_contract_shape(
        access_packet["case_state_init_contract"], TERMINAL_BENCH_CASE_STATE_PATH
    )
    preview = access_packet["packet_public_preview"]
    assert TERMINAL_BENCH_CASE_STATE_PATH in preview
    assert "case_goal_state_init_required_before_worker: true" in preview
    assert counters["case_goal_state_init_required"] is True
    assert counters["case_goal_state_initialized_before_agent"] is False
    assert counters["case_goal_state_init_status"] == "fixture_contract_only"
    assert counters["case_goal_state_path"] == TERMINAL_BENCH_CASE_STATE_PATH


if __name__ == "__main__":
    test_shared_contract_for_current_benchmark_routes()
    test_seed_text_uses_real_goal_harness_active_state_shape()
    test_seed_write_command_uses_canonical_path()
    test_case_lifecycle_contract_is_per_case_arm()
    test_ale_launch_packet_reuses_shared_contract()
    test_terminal_bench_access_packet_fixture_reuses_shared_contract()
