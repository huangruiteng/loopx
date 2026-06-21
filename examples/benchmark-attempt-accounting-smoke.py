#!/usr/bin/env python3
"""Smoke-test adapter-neutral benchmark attempt accounting."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_core import (  # noqa: E402
    BenchmarkFailureClass,
    canonical_lifecycle,
    build_benchmark_attempt_accounting,
    classify_benchmark_failure,
)


def main() -> None:
    runner_only = canonical_lifecycle(
        process_started=True,
        runner_accepted_args=True,
        job_root_materialized=False,
    )
    detached = build_benchmark_attempt_accounting(
        lifecycle=runner_only,
        failure_label="detached_worker_ended_without_job_root",
    )
    assert detached["failure_class"] == BenchmarkFailureClass.JOB_MATERIALIZATION_FAILED
    assert detached["launcher_attempt_countable"] is True
    assert detached["case_attempt_countable"] is False
    assert detached["solver_attempt_countable"] is False
    assert detached["verifier_attempt_countable"] is False
    assert detached["official_score_attempt_countable"] is False

    startup = build_benchmark_attempt_accounting(
        lifecycle=canonical_lifecycle(process_started=False),
        failure_label="process-start failed",
    )
    assert startup["failure_class"] == BenchmarkFailureClass.RUNNER_STARTUP_FAILED
    assert startup["launcher_attempt_countable"] is False
    assert startup["case_attempt_countable"] is False

    solver = build_benchmark_attempt_accounting(
        lifecycle=canonical_lifecycle(
            process_started=True,
            runner_accepted_args=True,
            job_root_materialized=True,
            trial_started=True,
            worker_started=True,
        ),
        failure_label="worker_ended_without_result",
    )
    assert solver["failure_class"] == BenchmarkFailureClass.SOLVER_FAILED
    assert solver["case_attempt_countable"] is True
    assert solver["solver_attempt_countable"] is True
    assert solver["verifier_attempt_countable"] is False

    verifier = build_benchmark_attempt_accounting(
        lifecycle=canonical_lifecycle(
            process_started=True,
            runner_accepted_args=True,
            job_root_materialized=True,
            trial_started=True,
            worker_started=True,
            result_written=True,
            verifier_scored=True,
        ),
        failure_label="verifier_timeout",
        official_score_attempted=True,
    )
    assert verifier["failure_class"] == BenchmarkFailureClass.VERIFIER_FAILED
    assert verifier["case_attempt_countable"] is True
    assert verifier["solver_attempt_countable"] is True
    assert verifier["verifier_attempt_countable"] is True
    assert verifier["official_score_attempt_countable"] is True

    assert (
        classify_benchmark_failure("official-score-missing")
        == BenchmarkFailureClass.OFFICIAL_SCORE_FAILED
    )

    print("benchmark attempt accounting smoke passed")


if __name__ == "__main__":
    main()
