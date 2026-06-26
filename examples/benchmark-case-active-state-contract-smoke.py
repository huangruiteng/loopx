#!/usr/bin/env python3
"""Smoke-test the shared benchmark case active-state contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    AGENTS_LAST_EXAM_BENCHMARK_ID,
    AGENTS_LAST_EXAM_CASE_GOAL_ID,
    AGENTS_LAST_EXAM_CASE_STATE_PATH,
    SKILLSBENCH_PRODUCT_MODE_CASE_GOAL_ID,
    SKILLSBENCH_PRODUCT_MODE_CASE_STATE_PATH,
    TERMINAL_BENCH_CASE_GOAL_ID,
    TERMINAL_BENCH_CASE_STATE_PATH,
    build_agents_last_exam_local_launch_packet,
    build_terminal_bench_case_state_init_contract,
    build_terminal_bench_loopx_access_packet_fixture,
)
from loopx.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS,
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    BENCHMARK_CASE_LIFECYCLE_SCHEMA_VERSION,
    BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID,
    BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS,
    BENCHMARK_CASE_LOOPX_TODO_ID,
    benchmark_case_active_state_init_contract,
    benchmark_case_active_state_path,
    benchmark_case_active_state_seed_text,
    benchmark_case_active_state_write_command,
    benchmark_case_arm_goal_id,
    benchmark_case_goal_id,
    benchmark_case_loopx_event_log_path,
    benchmark_case_loopx_install_command,
    benchmark_case_loopx_install_payload,
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
    assert contract["init_flow"] == "shared_loopx_benchmark_case_active_state"
    assert contract["status_field"] == "case_goal_state_init_status"
    assert set(BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS).issubset(
        set(contract["proof_fields"])
    )
    assert contract["surrogate_state_files_allowed"] is False
    assert contract["raw_task_text_required_for_init"] is False
    assert contract["local_paths_recorded"] is False
    rendered = json.dumps(contract, sort_keys=True)
    assert ".loopx-case-state.md" not in rendered
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


def test_seed_text_uses_real_loopx_active_state_shape() -> None:
    goal_id = benchmark_case_goal_id("terminal-bench")
    state_path = benchmark_case_active_state_path(goal_id)
    seed = benchmark_case_active_state_seed_text(
        benchmark_name="Terminal-Bench",
        goal_id=goal_id,
        task_id="public-task-id",
        route="loopx-product-mode",
        max_rounds=5,
        case_state_path=state_path,
    )
    assert "goal_id: terminal-bench-case" in seed
    assert f"schema_version: {BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION}" in seed
    assert state_path in seed
    assert "## Agent Todo" in seed
    assert "## Next Action" in seed
    assert ".loopx-case-state.md" not in seed
    assert "/Users/" not in seed


def test_seed_write_command_uses_canonical_path() -> None:
    goal_id = benchmark_case_goal_id("terminal-bench")
    state_path = benchmark_case_active_state_path(goal_id)
    seed = benchmark_case_active_state_seed_text(
        benchmark_name="Terminal-Bench",
        goal_id=goal_id,
        task_id="public-task-id",
        route="loopx-product-mode",
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
    assert ".loopx-case-state.md" not in command
    assert "/Users/" not in command


def test_case_loopx_install_payload_uses_official_product_lifecycle() -> None:
    payload = benchmark_case_loopx_install_payload(
        benchmark_id="swe-marathon",
        case_id="zstd-decoder",
        arm_id="loopx_prompt_polling_test",
        route="loopx-prompt-polling-test",
        max_rounds=5,
    )
    goal_id = "swe-marathon-zstd-decoder-loopx-prompt-polling-test-case"
    assert payload["benchmark_case_goal_id"] == goal_id
    assert payload["case_state_path"] == benchmark_case_active_state_path(goal_id)
    assert payload["case_cli_path"] == "/app/.local/bin/loopx"
    assert payload["case_registry_path"] == "/app/.loopx/registry.json"
    assert payload["case_runtime_root"] == "/app/.loopx/runtime"
    assert payload["case_rollout_event_log_path"] == benchmark_case_loopx_event_log_path(goal_id)
    assert payload["case_todo_id"] == BENCHMARK_CASE_LOOPX_TODO_ID
    assert payload["case_agent_id"] == "codex-benchmark-agent"
    assert payload["case_todo_seeded"] is True
    assert payload["case_todo_preclaimed"] is False
    assert payload["canonical_product_mode_lifecycle_driver"] is True
    assert payload["formal_treatment_semantics"] == "loopx-product-mode"
    assert payload["install_flow_required"] is True
    assert payload["prompt_driven_route_required"] is True
    assert payload["product_path_primary_route"] == "prompt_driven_case_local_loopx_cli"
    command = str(payload["command"])
    assert "/app/.local/bin/loopx" in command
    assert "install-from-github.sh" in command
    assert " bootstrap " in command
    assert " configure-goal " in command
    assert " todo add " in command
    assert " quota should-run " in command
    assert " todo claim " not in command
    assert "/Users/" not in command


def test_goal_start_product_mode_seeds_ranked_plan_before_todos() -> None:
    payload = benchmark_case_loopx_install_payload(
        benchmark_id="skillsbench",
        case_id="planning-granularity",
        arm_id="loopx_goal_start_product_mode",
        route="loopx-goal-start-product-mode",
        max_rounds=16,
        goal_start_product_mode=True,
    )
    assert payload["goal_start_product_mode"] is True
    assert payload["goal_start_plan_observed"] is True
    assert payload["planner_before_todo_write"] is True
    assert payload["planned_todo_count"] == 3
    assert payload["planned_p0_count"] == 1
    assert payload["planned_todo_ids"] == list(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS)
    assert payload["case_todo_id"] == BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID
    assert payload["selected_p0_todo_id"] == BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID
    assert payload["selected_todo_claimed"] is False
    assert payload["selected_todo_updated_before_solver"] is False
    assert payload["selected_todo_completed_before_spend"] is False
    assert payload["non_selected_todos_preserved_open_or_deferred"] is True
    command = str(payload["command"])
    assert " bootstrap-command-pack " in command
    assert " --goal-text " in command
    assert command.count(" todo add ") == 3
    assert command.index("bootstrap-command-pack") < command.index(" todo add ")
    for todo_id in BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS:
        assert todo_id in command
    assert "/Users/" not in command


def test_case_loopx_install_command_uses_real_loopx_lifecycle() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-case-install-") as tmp:
        root = Path(tmp)
        state_path = root / ".codex" / "goals" / "demo-case" / "ACTIVE_GOAL_STATE.md"
        cli_path = root / ".local" / "bin" / "loopx"
        registry_path = root / ".loopx" / "registry.json"
        runtime_root = root / ".loopx" / "runtime"
        goal_doc_path = root / ".loopx" / "LOOPX_CASE_GOAL.md"
        event_log_path = runtime_root / "goals" / "demo-case" / "rollout-event-log.jsonl"
        command = benchmark_case_loopx_install_command(
            benchmark_id="skillsbench",
            case_id="demo-case",
            route="loopx-product-mode",
            max_rounds=8,
            goal_id="demo-case",
            case_state_path=str(state_path),
            content="",
            case_cli_path=str(cli_path),
            case_registry_path=str(registry_path),
            case_runtime_root=str(runtime_root),
            case_goal_doc_path=str(goal_doc_path),
            case_project_root=str(root),
            case_home=str(root),
        )
        subprocess.run(
            ["bash", "-lc", command],
            check=True,
            capture_output=True,
            text=True,
        )
        assert state_path.exists()
        assert cli_path.exists()
        quota = subprocess.run(
            [
                str(cli_path),
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "quota",
                "should-run",
                "--goal-id",
                "demo-case",
                "--agent-id",
                "codex-benchmark-agent",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        quota_payload = json.loads(quota.stdout)
        assert quota_payload["should_run"] is True
        assert quota_payload["agent_lane_next_action"]["todo_id"] == BENCHMARK_CASE_LOOPX_TODO_ID
        claim = subprocess.run(
            [
                str(cli_path),
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "todo",
                "claim",
                "--goal-id",
                "demo-case",
                "--todo-id",
                BENCHMARK_CASE_LOOPX_TODO_ID,
                "--claimed-by",
                "codex-benchmark-agent",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        assert json.loads(claim.stdout)["status"] == "open"
        event_lines = event_log_path.read_text(encoding="utf-8").strip().splitlines()
        assert any('"event_kind": "todo_add"' in line or '"event_kind":"todo_add"' in line for line in event_lines)
        assert any('"event_kind": "quota_should_run"' in line or '"event_kind":"quota_should_run"' in line for line in event_lines)
        assert any('"event_kind": "todo_claim"' in line or '"event_kind":"todo_claim"' in line for line in event_lines)
        assert all("raw_task_text" not in line or "false" in line for line in event_lines)


def test_goal_start_install_command_seeds_three_ranked_todos() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-goal-start-install-") as tmp:
        root = Path(tmp)
        state_path = root / ".codex" / "goals" / "goal-start-case" / "ACTIVE_GOAL_STATE.md"
        cli_path = root / ".local" / "bin" / "loopx"
        registry_path = root / ".loopx" / "registry.json"
        runtime_root = root / ".loopx" / "runtime"
        goal_doc_path = root / ".loopx" / "LOOPX_CASE_GOAL.md"
        command = benchmark_case_loopx_install_command(
            benchmark_id="skillsbench",
            case_id="goal-start-case",
            route="loopx-goal-start-product-mode",
            max_rounds=16,
            goal_id="goal-start-case",
            case_state_path=str(state_path),
            content="",
            case_cli_path=str(cli_path),
            case_registry_path=str(registry_path),
            case_runtime_root=str(runtime_root),
            case_goal_doc_path=str(goal_doc_path),
            case_project_root=str(root),
            case_home=str(root),
            goal_start_product_mode=True,
        )
        subprocess.run(
            ["bash", "-lc", command],
            check=True,
            capture_output=True,
            text=True,
        )
        status = subprocess.run(
            [
                str(cli_path),
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "status",
                "--agent-id",
                "codex-benchmark-agent",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        status_payload = json.loads(status.stdout)
        items = status_payload["attention_queue"]["items"][0]["agent_todos"][
            "backlog_items"
        ]
        ids = {item["todo_id"] for item in items}
        assert set(BENCHMARK_CASE_LOOPX_GOAL_START_TODO_IDS).issubset(ids)
        assert status_payload["attention_queue"]["items"][0]["agent_lane_next_action"][
            "todo_id"
        ] == BENCHMARK_CASE_LOOPX_GOAL_START_SELECTED_TODO_ID


def test_case_loopx_install_command_uses_source_wrapper_without_local_installer() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-case-source-wrapper-") as tmp:
        root = Path(tmp)
        state_path = root / ".codex" / "goals" / "source-wrapper-case" / "ACTIVE_GOAL_STATE.md"
        cli_path = root / ".local" / "bin" / "loopx"
        registry_path = root / ".loopx" / "registry.json"
        runtime_root = root / ".loopx" / "runtime"
        goal_doc_path = root / ".loopx" / "LOOPX_CASE_GOAL.md"
        command = benchmark_case_loopx_install_command(
            benchmark_id="skillsbench",
            case_id="source-wrapper-case",
            route="loopx-product-mode",
            max_rounds=16,
            goal_id="source-wrapper-case",
            case_state_path=str(state_path),
            content="",
            case_cli_path=str(cli_path),
            case_registry_path=str(registry_path),
            case_runtime_root=str(runtime_root),
            case_goal_doc_path=str(goal_doc_path),
            case_project_root=str(root),
            case_home=str(root),
            case_loopx_source_path=str(REPO_ROOT),
        )
        assert "install-local.sh" not in command
        assert "python is missing" in command
        subprocess.run(
            ["sh", "-lc", command],
            check=True,
            capture_output=True,
            text=True,
        )
        assert cli_path.read_text(encoding="utf-8").startswith("#!/bin/sh\n")
        quota = subprocess.run(
            [
                str(cli_path),
                "--registry",
                str(registry_path),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "quota",
                "should-run",
                "--goal-id",
                "source-wrapper-case",
                "--agent-id",
                "codex-benchmark-agent",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        quota_payload = json.loads(quota.stdout)
        assert quota_payload["should_run"] is True
        assert quota_payload["agent_lane_next_action"]["todo_id"] == BENCHMARK_CASE_LOOPX_TODO_ID


def test_case_lifecycle_contract_is_per_case_arm() -> None:
    contract = benchmark_case_lifecycle_contract(
        benchmark_id="swe-marathon",
        case_id="find-network-alignments",
        arm_id="codex_loopx_treatment",
        max_rounds=5,
    )
    expected_goal_id = benchmark_case_arm_goal_id(
        benchmark_id="swe-marathon",
        case_id="find-network-alignments",
        arm_id="codex_loopx_treatment",
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
    fixture = build_terminal_bench_loopx_access_packet_fixture()
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
    test_seed_text_uses_real_loopx_active_state_shape()
    test_seed_write_command_uses_canonical_path()
    test_case_loopx_install_payload_uses_official_product_lifecycle()
    test_goal_start_product_mode_seeds_ranked_plan_before_todos()
    test_case_loopx_install_command_uses_real_loopx_lifecycle()
    test_goal_start_install_command_seeds_three_ranked_todos()
    test_case_loopx_install_command_uses_source_wrapper_without_local_installer()
    test_case_lifecycle_contract_is_per_case_arm()
    test_ale_launch_packet_reuses_shared_contract()
    test_terminal_bench_access_packet_fixture_reuses_shared_contract()
