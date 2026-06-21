#!/usr/bin/env python3
"""Smoke-test benchmark attempt-to-learning gate."""

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

from loopx.benchmark import (  # noqa: E402
    build_benchmark_attempt_learning_gate,
    build_benchmark_learning_ledger,
)
from loopx.status import (  # noqa: E402
    compact_benchmark_learning_ledger,
    compact_benchmark_run,
)


def comparison(
    delta: float,
    *,
    comparison_id: str = "attempt-learning-fixture",
    failure_labels: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "terminal-bench@2.0/attempt-learning-fixture",
        "comparison_id": comparison_id,
        "benchmark_id": "terminal-bench@2.0",
        "baseline_scenario_id": "hardened-codex",
        "treatment_scenario_id": "codex-loopx",
        "official_task_score_delta": delta,
        "control_plane_score_delta": 0.0,
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": False,
            "raw_trace_excluded": True,
        },
    }
    if failure_labels:
        payload["failure_attribution_labels"] = failure_labels
    return payload


def benchmark_run(
    mode: str = "codex-loopx",
    score: float = 0.0,
    *,
    first_blocker: str = "pre_worker_agent_setup_failed",
    failure_labels: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": f"terminal-bench-2-0-attempt-learning-{mode}",
        "mode": mode,
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_task_score": {
            "kind": "terminal_bench_verifier_reward",
            "value": score,
            "passed": score >= 1,
        },
        "failure_attribution_labels": failure_labels
        if failure_labels is not None
        else ["treatment_pre_worker_agent_setup_failed"],
        "read_boundary": {
            "compact_only": True,
            "raw_artifacts_read": False,
            "task_text_read": False,
            "local_paths_recorded": False,
        },
        "trials": [
            {
                "task_id": "public-fixture-task",
                "trial_name": "attempt-learning-fixture",
            }
        ],
        "private_raw_path": "/tmp/private/raw/trajectory.json",
    }
    if first_blocker:
        payload["first_blocker"] = first_blocker
    return payload


def compact_run(payload: dict[str, Any]) -> dict[str, Any]:
    compact = compact_benchmark_run(payload)
    assert compact is not None, payload
    return compact


def compact_ledger(payload: dict[str, Any]) -> dict[str, Any]:
    compact = compact_benchmark_learning_ledger(payload)
    assert compact is not None, payload
    return compact


def actionable_ledger() -> dict[str, Any]:
    return build_benchmark_learning_ledger(
        comparison(
            -1.0,
            failure_labels=["treatment_pre_worker_agent_setup_failed"],
        ),
        benchmark_runs=[
            benchmark_run("hardened-codex", 1.0, first_blocker="", failure_labels=[]),
            benchmark_run(),
        ],
    )


def no_signal_ledger() -> dict[str, Any]:
    return build_benchmark_learning_ledger(
        comparison(0.0, comparison_id="no-signal"),
        benchmark_runs=[
            benchmark_run("hardened-codex", 1.0, first_blocker="", failure_labels=[]),
            benchmark_run(
                "codex-loopx",
                1.0,
                first_blocker="",
                failure_labels=[],
            ),
        ],
    )


def assert_no_private_surface(text: str) -> None:
    for forbidden in ("/tmp/private", "private_raw_path", "trajectory.json"):
        assert forbidden not in text, text


def test_missing_learning_row_blocks_budget_count() -> None:
    payload = build_benchmark_attempt_learning_gate(compact_run(benchmark_run()))

    assert payload["schema_version"] == "benchmark_attempt_learning_gate_v0", payload
    assert payload["countable_attempt"] is True, payload
    assert payload["learning_row_present"] is False, payload
    assert payload["budget_count_allowed"] is False, payload
    assert payload["classification"] == "benchmark_attempt_learning_row_missing", payload
    assert (
        payload["next_required_action"]
        == "build_compact_benchmark_learning_ledger_before_repeat_or_new_candidate"
    ), payload
    assert "adapter_startup_argument_contract" in payload["repair_candidates"], payload
    assert_no_private_surface(json.dumps(payload, sort_keys=True))


def test_environment_setup_attempt_routes_to_environment_contract() -> None:
    run = benchmark_run(
        first_blocker="environment_setup_failed_before_worker",
        failure_labels=["environment_setup_failed_before_worker"],
    )
    payload = build_benchmark_attempt_learning_gate(compact_run(run))

    assert payload["classification"] == "benchmark_attempt_learning_row_missing", payload
    assert "benchmark_environment_setup_contract" in payload["repair_candidates"], payload
    assert "adapter_startup_argument_contract" not in payload["repair_candidates"], payload
    assert_no_private_surface(json.dumps(payload, sort_keys=True))


def test_actionable_learning_row_allows_budget_count() -> None:
    payload = build_benchmark_attempt_learning_gate(
        compact_run(benchmark_run()),
        benchmark_learning_ledger=compact_ledger(actionable_ledger()),
    )

    assert payload["classification"] == "benchmark_attempt_learning_ready", payload
    assert payload["learning_row_present"] is True, payload
    assert payload["learning_row_actionable"] is True, payload
    assert payload["budget_count_allowed"] is True, payload
    assert (
        payload["next_required_action"]
        == "repair_or_validate_adapter_startup_argument_contract"
    ), payload
    assert payload["new_candidate_allowed"] is False, payload


def test_nonactionable_learning_row_still_blocks_budget_count() -> None:
    payload = build_benchmark_attempt_learning_gate(
        compact_run(
            benchmark_run(
                "codex-loopx",
                1.0,
                first_blocker="",
                failure_labels=[],
            )
        ),
        benchmark_learning_ledger=compact_ledger(no_signal_ledger()),
    )

    assert payload["classification"] == "benchmark_attempt_learning_row_nonactionable", payload
    assert payload["learning_row_present"] is True, payload
    assert payload["learning_row_actionable"] is False, payload
    assert payload["budget_count_allowed"] is False, payload
    assert (
        payload["next_required_action"]
        == "stop_without_spend_or_add_named_repair_caveat_before_repeat"
    ), payload


def test_cli_attempt_learning_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_path = root / "run.compact.json"
        ledger_path = root / "ledger.compact.json"
        no_signal_path = root / "no-signal-ledger.compact.json"
        run_path.write_text(json.dumps(benchmark_run()), encoding="utf-8")
        ledger_path.write_text(json.dumps(actionable_ledger()), encoding="utf-8")
        no_signal_path.write_text(json.dumps(no_signal_ledger()), encoding="utf-8")

        missing = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "attempt-learning-gate",
                "--benchmark-run-json",
                str(run_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert missing.returncode == 1, missing.stdout
        missing_payload = json.loads(missing.stdout)
        assert missing_payload["ok"] is False, missing_payload
        assert (
            missing_payload["classification"]
            == "benchmark_attempt_learning_row_missing"
        ), missing_payload
        assert str(root) not in missing.stdout, missing.stdout
        assert_no_private_surface(missing.stdout)

        ready = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "attempt-learning-gate",
                "--benchmark-run-json",
                str(run_path),
                "--benchmark-learning-ledger-json",
                str(ledger_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        ready_payload = json.loads(ready.stdout)
        assert ready_payload["ok"] is True, ready_payload
        assert ready_payload["budget_count_allowed"] is True, ready_payload
        assert str(root) not in ready.stdout, ready.stdout
        assert_no_private_surface(ready.stdout)

        nonactionable = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "attempt-learning-gate",
                "--benchmark-run-json",
                str(run_path),
                "--benchmark-learning-ledger-json",
                str(no_signal_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert nonactionable.returncode == 1, nonactionable.stdout
        nonactionable_payload = json.loads(nonactionable.stdout)
        assert (
            nonactionable_payload["classification"]
            == "benchmark_attempt_learning_row_nonactionable"
        ), nonactionable_payload
        assert str(root) not in nonactionable.stdout, nonactionable.stdout
        assert_no_private_surface(nonactionable.stdout)


def main() -> int:
    test_missing_learning_row_blocks_budget_count()
    test_environment_setup_attempt_routes_to_environment_contract()
    test_actionable_learning_row_allows_budget_count()
    test_nonactionable_learning_row_still_blocks_budget_count()
    test_cli_attempt_learning_gate()
    print("benchmark-attempt-learning-gate-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
