#!/usr/bin/env python3
"""Smoke-test compact benchmark lifecycle-state routing."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import (  # noqa: E402
    build_benchmark_claim_review,
    build_benchmark_learning_ledger,
    build_benchmark_lifecycle_state,
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preflight_ready() -> dict[str, Any]:
    return {
        "schema_version": "benchmark_preflight_fixture_v0",
        "ready": True,
        "first_blocker": "ready_for_private_managed_no_upload_pilot_review",
    }


def launch_started(root: Path) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_launch_fixture_v0",
        "process_started": True,
        "pid": 12345,
        "private_job_dir": str(root / "private" / "jobs"),
    }


def materialization_missing() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_post_launch_materialization_v0",
        "checked": True,
        "ready_for_launch_state": False,
        "ready_for_compact_result_ingest": False,
        "first_blocker": "job_root_missing",
        "jobs_dir_present": True,
        "job_root_present": False,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
    }


def materialization_ready() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_post_launch_materialization_v0",
        "checked": True,
        "ready_for_launch_state": True,
        "ready_for_compact_result_ingest": True,
        "first_blocker": "ready_for_compact_result_ingest",
        "jobs_dir_present": True,
        "job_root_present": True,
        "job_lock_present": True,
        "job_result_present": True,
        "trial_result_present_count": 1,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
    }


def benchmark_run(
    mode: str,
    score: float,
    *,
    failure_labels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": f"terminal-bench-2-0-compact-fixture-{mode}",
        "mode": mode,
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_task_score": {
            "kind": "terminal_bench_verifier_reward",
            "value": score,
            "passed": score >= 1,
        },
        "failure_attribution_labels": failure_labels or [],
        "read_boundary": {
            "raw_artifacts_read": False,
            "task_text_read": False,
        },
    }


def comparison() -> dict[str, Any]:
    return {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "terminal-bench@2.0/compact-fixture",
        "comparison_id": "lifecycle-startup-failure",
        "benchmark_id": "terminal-bench@2.0",
        "baseline_scenario_id": "hardened-codex",
        "treatment_scenario_id": "codex-goal-harness",
        "official_task_score_delta": -1.0,
        "control_plane_score_delta": 0.0,
        "failure_attribution_labels": ["treatment_pre_worker_agent_setup_failed"],
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "raw_trace_excluded": True,
        },
    }


def assert_no_private_surface(payload: dict[str, Any] | str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        "private/jobs",
        "private_job_dir",
        "OPENAI" + "_API_KEY",
        "auth.json",
        "trajectory.json",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def test_launched_process_without_materialization_is_not_countable() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-lifecycle-state-") as tmp:
        payload = build_benchmark_lifecycle_state(
            preflight=preflight_ready(),
            launch=launch_started(Path(tmp)),
            post_launch_materialization=materialization_missing(),
        )
    assert payload["current_phase"] == "launched_process", payload
    assert payload["first_blocker"] == "post_launch_materialization_missing", payload
    assert payload["gates"]["launch_state_countable"] is False, payload
    assert payload["gates"]["compact_result_ingest_allowed"] is False, payload
    assert payload["gates"]["budget_count_allowed"] is False, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
    assert_no_private_surface(payload)


def test_budget_count_requires_compact_ledger_gate() -> None:
    baseline = benchmark_run("hardened-codex", 1.0)
    treatment = benchmark_run(
        "codex-goal-harness",
        0.0,
        failure_labels=["treatment_pre_worker_agent_setup_failed"],
    )
    paired = comparison()
    claim_review = build_benchmark_claim_review(
        paired,
        benchmark_runs=[baseline, treatment],
    )
    ledger = build_benchmark_learning_ledger(
        paired,
        benchmark_runs=[baseline, treatment],
    )
    without_ledger = build_benchmark_lifecycle_state(
        preflight=preflight_ready(),
        launch={"schema_version": "benchmark_launch_fixture_v0", "process_started": True},
        post_launch_materialization=materialization_ready(),
        benchmark_run=treatment,
        benchmark_comparison=paired,
        claim_review=claim_review,
    )
    assert without_ledger["first_blocker"] == "benchmark_learning_ledger_missing", without_ledger
    assert without_ledger["gates"]["budget_count_allowed"] is False, without_ledger

    with_ledger = build_benchmark_lifecycle_state(
        preflight=preflight_ready(),
        launch={"schema_version": "benchmark_launch_fixture_v0", "process_started": True},
        post_launch_materialization=materialization_ready(),
        benchmark_run=treatment,
        benchmark_comparison=paired,
        claim_review=claim_review,
        learning_ledger=ledger,
    )
    assert with_ledger["current_phase"] == "budget_counted", with_ledger
    assert with_ledger["first_blocker"] == "ready_for_budget_count", with_ledger
    assert with_ledger["gates"]["budget_count_allowed"] is True, with_ledger
    assert with_ledger["gates"]["new_candidate_allowed"] is False, with_ledger
    assert_no_private_surface(with_ledger)


def test_cli_lifecycle_state_budget_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-lifecycle-state-cli-") as tmp:
        root = Path(tmp)
        preflight_path = root / "preflight.json"
        launch_path = root / "launch.json"
        missing_path = root / "post_launch_missing.json"
        ready_path = root / "post_launch_ready.json"
        run_path = root / "run.json"
        comparison_path = root / "comparison.json"
        claim_path = root / "claim_review.json"
        ledger_path = root / "ledger.json"

        baseline = benchmark_run("hardened-codex", 1.0)
        treatment = benchmark_run(
            "codex-goal-harness",
            0.0,
            failure_labels=["treatment_pre_worker_agent_setup_failed"],
        )
        paired = comparison()
        claim_review = build_benchmark_claim_review(
            paired,
            benchmark_runs=[baseline, treatment],
        )
        ledger = build_benchmark_learning_ledger(
            paired,
            benchmark_runs=[baseline, treatment],
        )

        write_json(preflight_path, preflight_ready())
        write_json(launch_path, launch_started(root))
        write_json(missing_path, materialization_missing())
        write_json(ready_path, materialization_ready())
        write_json(run_path, treatment)
        write_json(comparison_path, paired)
        write_json(claim_path, claim_review)
        write_json(ledger_path, ledger)

        blocked = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "benchmark",
                "lifecycle-state",
                "--preflight-json",
                str(preflight_path),
                "--launch-json",
                str(launch_path),
                "--post-launch-json",
                str(missing_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        blocked_payload = json.loads(blocked.stdout)
        assert blocked.returncode == 1, blocked.stdout
        assert blocked_payload["ok"] is False, blocked_payload
        assert blocked_payload["first_blocker"] == "post_launch_materialization_missing", blocked_payload
        assert blocked_payload["gates"]["budget_count_allowed"] is False, blocked_payload
        assert_no_private_surface(blocked.stdout)

        allowed = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "benchmark",
                "lifecycle-state",
                "--preflight-json",
                str(preflight_path),
                "--launch-json",
                str(launch_path),
                "--post-launch-json",
                str(ready_path),
                "--benchmark-run-json",
                str(run_path),
                "--benchmark-comparison-json",
                str(comparison_path),
                "--claim-review-json",
                str(claim_path),
                "--benchmark-learning-ledger-json",
                str(ledger_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        allowed_payload = json.loads(allowed.stdout)
        assert allowed_payload["ok"] is True, allowed_payload
        assert allowed_payload["current_phase"] == "budget_counted", allowed_payload
        assert allowed_payload["gates"]["budget_count_allowed"] is True, allowed_payload
        assert_no_private_surface(allowed.stdout)


def main() -> int:
    test_launched_process_without_materialization_is_not_countable()
    test_budget_count_requires_compact_ledger_gate()
    test_cli_lifecycle_state_budget_gate()
    print("benchmark-lifecycle-state-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
