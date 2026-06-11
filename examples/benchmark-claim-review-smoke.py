#!/usr/bin/env python3
"""Smoke-test compact benchmark claim review."""

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

from goal_harness.benchmark import build_benchmark_claim_review  # noqa: E402


def comparison(delta: float, *, comparison_id: str = "fixture-pair") -> dict[str, Any]:
    return {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "terminal-bench@2.0/db-wal-recovery",
        "comparison_id": comparison_id,
        "benchmark_id": "terminal-bench@2.0",
        "baseline_scenario_id": "hardened-codex",
        "treatment_scenario_id": "codex-goal-harness",
        "official_task_score_delta": delta,
        "control_plane_score_delta": 0.75,
        "both_success": delta == 0,
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "assisted_collaboration_claim_allowed": True,
            "raw_trace_excluded": True,
        },
    }


def benchmark_run(
    mode: str,
    score: float,
    *,
    worker_calls: int = 0,
    attribution: str = "none",
    labels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": f"terminal-bench-2-0-db-wal-recovery-{mode}",
        "mode": mode,
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_task_score": {
            "kind": "terminal_bench_verifier_reward",
            "value": score,
            "passed": score >= 1,
        },
        "worker_goal_harness_cli_call_total": worker_calls,
        "worker_benchmark_run_schema_ok_count": 1 if worker_calls else 0,
        "score_failure_attribution": attribution,
        "failure_attribution_labels": labels or [],
        "active_user_observation": {
            "observed_after_worker_start": worker_calls > 0,
        },
        "read_boundary": {
            "raw_artifacts_read": False,
            "task_text_read": False,
        },
    }


def test_candidate_with_baseline_attribution_caveat() -> None:
    baseline = benchmark_run(
        "hardened-codex",
        0.0,
        attribution="verifier_platform_probe_failure",
        labels=["verifier_platform_probe_failure"],
    )
    treatment = benchmark_run("codex-goal-harness", 1.0, worker_calls=4)
    payload = build_benchmark_claim_review(
        comparison(1.0),
        benchmark_runs=[baseline, treatment],
    )
    decision = payload["decision"]

    assert payload["schema_version"] == "benchmark_claim_review_v0", payload
    assert payload["official_task_score_delta"] == 1.0, payload
    assert payload["treatment_worker_evidence"]["present"] is True, payload
    assert payload["baseline_score_failure_attribution"] == "verifier_platform_probe_failure", payload
    assert "baseline_failure_attribution_caveat" in decision["blockers"], payload
    assert decision["validation_enhancement_candidate"] is True, payload
    assert decision["clean_validation_enhancement"] is False, payload
    assert decision["claim_strength"] == "candidate_score_recovery_needs_attribution_review", payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload


def test_loop_validation_without_score_uplift() -> None:
    baseline = benchmark_run("hardened-codex", 1.0)
    treatment = benchmark_run("codex-goal-harness", 1.0, worker_calls=3)
    payload = build_benchmark_claim_review(
        comparison(0.0, comparison_id="no-delta-pair"),
        benchmark_runs=[baseline, treatment],
    )
    decision = payload["decision"]

    assert decision["claim_strength"] == "loop_validation_no_score_uplift", payload
    assert decision["validation_enhancement_candidate"] is False, payload
    assert "no_positive_official_task_score_delta" in decision["blockers"], payload


def test_cli_review_claim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        comparison_path = root / "paired_comparison.compact.json"
        baseline_path = root / "baseline.compact.json"
        treatment_path = root / "treatment.compact.json"
        comparison_path.write_text(json.dumps(comparison(1.0)), encoding="utf-8")
        baseline_path.write_text(
            json.dumps(
                benchmark_run(
                    "hardened-codex",
                    0.0,
                    attribution="verifier_platform_probe_failure",
                    labels=["verifier_platform_probe_failure"],
                )
            ),
            encoding="utf-8",
        )
        treatment_path.write_text(
            json.dumps(benchmark_run("codex-goal-harness", 1.0, worker_calls=4)),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "benchmark",
                "review-claim",
                "--benchmark-comparison-json",
                str(comparison_path),
                "--benchmark-run-json",
                str(baseline_path),
                "--benchmark-run-json",
                str(treatment_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["decision"]["claim_strength"] == "candidate_score_recovery_needs_attribution_review", payload
        assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
        assert str(root) not in result.stdout, result.stdout


def main() -> int:
    test_candidate_with_baseline_attribution_caveat()
    test_loop_validation_without_score_uplift()
    test_cli_review_claim()
    print("benchmark-claim-review-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
