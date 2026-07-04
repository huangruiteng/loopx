#!/usr/bin/env python3
"""Smoke-test the shared benchmark_core adapter contract."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import build_benchmark_lifecycle_state  # noqa: E402
from loopx.benchmark_adapters.agents_last_exam import (  # noqa: E402
    AGENTS_LAST_EXAM_CASE_STATE_PATH,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    build_agents_last_exam_local_launch_packet,
    build_agents_last_exam_local_preflight,
)
from loopx.benchmark_adapters.terminal_bench import (  # noqa: E402
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_DEFAULT_TASK,
    build_terminal_bench_private_runner_launch,
    build_terminal_bench_loopx_access_packet,
)
from loopx.benchmark_core import (  # noqa: E402
    AdapterClassification,
    BenchmarkAdapter,
    BenchmarkRequest,
    IngestResult,
    LaunchResult,
    LedgerUpdate,
    Observation,
    PreflightResult,
    RunHandle,
    build_round_artifact_restore_plan,
    compact_round_artifact_snapshots,
    canonical_lifecycle,
    load_json_object,
    optional_float,
    summarize_round_rewards,
)


class FixtureAdapter:
    id = "fixture"

    def preflight(self, request: BenchmarkRequest) -> PreflightResult:
        return PreflightResult(ok=bool(request.case_id), payload={"ready": True})

    def launch(self, request: BenchmarkRequest) -> LaunchResult:
        return LaunchResult(
            process_started=True,
            handle=RunHandle(run_id="fixture-run", external_id=request.case_id),
        )

    def observe(self, handle: RunHandle) -> Observation:
        return Observation(
            lifecycle=canonical_lifecycle(
                process_started=True,
                runner_accepted_args=True,
                job_root_materialized=True,
            )
        )

    def ingest(self, artifact: str) -> IngestResult:
        return IngestResult(
            benchmark_run={
                "schema_version": "benchmark_run_v0",
                "benchmark_id": "fixture@v0",
                "task_id": artifact,
                "official_score": 1.0,
            }
        )

    def classify(self, run: IngestResult) -> AdapterClassification:
        return AdapterClassification(
            decision="passed",
            payload={"score": run.benchmark_run["official_score"]},
        )

    def ledger(self, run: IngestResult) -> LedgerUpdate:
        return LedgerUpdate(written=True, payload={"case_id": run.benchmark_run["task_id"]})


def assert_adapter(adapter: BenchmarkAdapter) -> None:
    request = BenchmarkRequest(
        benchmark_id="fixture@v0",
        case_id="case-a",
        route="product-mode",
        max_rounds=5,
    )
    assert adapter.preflight(request).ok is True
    launch = adapter.launch(request)
    assert launch.process_started is True
    assert launch.handle is not None
    observed = adapter.observe(launch.handle)
    assert observed.lifecycle["current_phase"] == "job_root_materialized", observed
    assert observed.lifecycle["entered_benchmark_case"] is True, observed
    run = adapter.ingest("case-a")
    assert adapter.ledger(run).written is True


def test_process_started_is_not_case_entry() -> None:
    lifecycle = canonical_lifecycle(process_started=True)
    assert lifecycle["current_phase"] == "process_started", lifecycle
    assert lifecycle["entered_benchmark_case"] is False, lifecycle
    assert lifecycle["case_attempt_countable"] is False, lifecycle
    assert lifecycle["next_required_phase"] == "runner_accepted_args", lifecycle


def test_existing_lifecycle_builder_projects_canonical_state() -> None:
    state = build_benchmark_lifecycle_state(
        preflight={"schema_version": "fixture_preflight_v0", "ready": True},
        launch={"schema_version": "fixture_launch_v0", "process_started": True},
        post_launch_materialization={
            "schema_version": "fixture_post_launch_v0",
            "ready_for_launch_state": True,
            "ready_for_compact_result_ingest": False,
        },
    )
    canonical = state["canonical_lifecycle"]
    assert canonical["current_phase"] == "job_root_materialized", state
    assert canonical["entered_benchmark_case"] is True, state
    assert state["gates"]["launch_state_countable"] is True, state


def test_round_reward_summary_prefers_best_score() -> None:
    summary = summarize_round_rewards(
        [
            {"agent_round": 1, "reward": 0.25},
            {"agent_round": 2, "reward": 1.0, "passed": True},
            {"agent_round": 3, "reward": 0.0},
        ]
    )
    assert summary["first_success_round"] == 2, summary
    assert summary["best_reward_round"] == 2, summary
    assert summary["best_round_reward"] == 1.0, summary
    assert summary["final_round"] == 3, summary
    assert summary["final_round_reward"] == 0.0, summary
    assert summary["best_round_is_final"] is False, summary


def test_best_round_restore_plan_uses_public_snapshot_handle() -> None:
    plan = build_round_artifact_restore_plan(
        round_rewards=[
            {"agent_round": 1, "reward": 0.25},
            {"agent_round": 2, "reward": 1.0, "passed": True},
            {"agent_round": 3, "reward": 0.0},
        ],
        round_artifact_snapshots=[
            {"agent_round": 1, "snapshot_ref": "round-1-compact-snapshot"},
            {"agent_round": 2, "snapshot_ref": "round-2-compact-snapshot"},
            {"agent_round": 3, "snapshot_ref": "round-3-compact-snapshot"},
        ],
    )
    assert plan["schema_version"] == "benchmark_round_artifact_restore_plan_v0", plan
    assert plan["selected_round"] == 2, plan
    assert plan["selected_reward"] == 1.0, plan
    assert plan["best_round_is_final"] is False, plan
    assert plan["restore_required"] is True, plan
    assert plan["executable_final_selection"] is True, plan
    assert plan["blocked_reason"] == "", plan
    assert plan["restore_plan"] == {
        "action": "restore_best_round_snapshot_before_final_scoring",
        "snapshot_ref": "round-2-compact-snapshot",
        "agent_round": 2,
    }, plan
    assert plan["boundary"]["raw_snapshot_paths_recorded"] is False, plan


def test_best_round_restore_plan_blocks_without_snapshot() -> None:
    plan = build_round_artifact_restore_plan(
        round_rewards=[
            {"agent_round": 1, "reward": 0.25},
            {"agent_round": 2, "reward": 1.0, "passed": True},
            {"agent_round": 3, "reward": 0.0},
        ],
        round_artifact_snapshots=[
            {"agent_round": 1, "snapshot_ref": "round-1-compact-snapshot"},
            {"agent_round": 3, "snapshot_ref": "round-3-compact-snapshot"},
            {"agent_round": 2, "snapshot_ref": "/private/raw/round-2"},
        ],
    )
    assert plan["selected_round"] == 2, plan
    assert plan["executable_final_selection"] is False, plan
    assert plan["blocked_reason"] == "missing_snapshot_for_best_round", plan
    assert plan["restore_plan"] == {
        "action": "capture_per_round_snapshot_before_using_best_score_policy"
    }, plan
    snapshots = compact_round_artifact_snapshots(
        [{"agent_round": 2, "snapshot_ref": "/private/raw/round-2"}]
    )
    assert snapshots == [], snapshots


def test_best_round_restore_plan_keeps_final_when_best_is_final() -> None:
    plan = build_round_artifact_restore_plan(
        round_rewards=[
            {"agent_round": 1, "reward": 0.25},
            {"agent_round": 2, "reward": 1.0, "passed": True},
        ],
        round_artifact_snapshots=[],
    )
    assert plan["selected_round"] == 2, plan
    assert plan["final_round"] == 2, plan
    assert plan["best_round_is_final"] is True, plan
    assert plan["restore_required"] is False, plan
    assert plan["executable_final_selection"] is True, plan
    assert plan["restore_plan"] == {"action": "keep_final_workspace"}, plan


def test_benchmark_adapter_modules_own_public_config() -> None:
    assert TERMINAL_BENCH_DEFAULT_DATASET == "terminal-bench@2.0"
    assert TERMINAL_BENCH_DEFAULT_TASK == "build-cython-ext"
    assert AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE.startswith("agentslastexam/")
    assert AGENTS_LAST_EXAM_CASE_STATE_PATH.endswith("/ACTIVE_GOAL_STATE.md")


def test_benchmark_adapter_modules_own_helper_surfaces() -> None:
    assert (
        build_terminal_bench_private_runner_launch.__module__
        == "loopx.benchmark_adapters.terminal_bench"
    )
    assert (
        build_terminal_bench_loopx_access_packet.__module__
        == "loopx.benchmark_adapters.terminal_bench"
    )
    assert (
        build_agents_last_exam_local_preflight.__module__
        == "loopx.benchmark_adapters.agents_last_exam"
    )
    assert (
        build_agents_last_exam_local_launch_packet.__module__
        == "loopx.benchmark_adapters.agents_last_exam"
    )
    assert load_json_object.__module__ == "loopx.benchmark_core.io"
    assert optional_float.__module__ == "loopx.benchmark_core.io"


def test_benchmark_facade_has_no_shadowed_top_level_definitions() -> None:
    import ast

    source = (REPO_ROOT / "loopx" / "benchmark.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    seen: set[str] = set()
    duplicates: list[str] = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in seen:
                duplicates.append(node.name)
            seen.add(node.name)
    assert duplicates == []


def test_adapter_rollout_matrix_records_current_migration_order() -> None:
    doc = (
        REPO_ROOT
        / "docs"
        / "research"
        / "long-horizon-agent-benchmarks"
        / "benchmark-core-adapter-contract-v0.md"
    ).read_text(encoding="utf-8")
    assert "## Adapter Rollout Matrix" in doc
    assert "| Terminal-Bench | `loopx.benchmark_adapters.terminal_bench` | First migration target." in doc
    assert "`run_permission_policy_v0`, and `benchmark_attempt_accounting_v0` adoption" in doc
    assert "Goal-start `/loopx` raw/new mapping remains blocked on transport monitor `todo_45357c108d81`" in doc
    assert "no solver output and no new-arm compact artifact" in doc
    assert "| SWE-Marathon | no dedicated adapter yet |" in doc
    assert "Deferred: create the adapter only after a second SWE-Marathon route" in doc
    assert "do not add SWE-specific conventions to `benchmark_core`" in doc
    assert "Keep SkillsBench goal-start matrix rows blocked until compact transport" in doc


def main() -> int:
    assert_adapter(FixtureAdapter())
    test_process_started_is_not_case_entry()
    test_existing_lifecycle_builder_projects_canonical_state()
    test_round_reward_summary_prefers_best_score()
    test_best_round_restore_plan_uses_public_snapshot_handle()
    test_best_round_restore_plan_blocks_without_snapshot()
    test_best_round_restore_plan_keeps_final_when_best_is_final()
    test_benchmark_adapter_modules_own_public_config()
    test_benchmark_adapter_modules_own_helper_surfaces()
    test_benchmark_facade_has_no_shadowed_top_level_definitions()
    test_adapter_rollout_matrix_records_current_migration_order()
    print("benchmark-core-adapter-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
