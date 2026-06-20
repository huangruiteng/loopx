from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from .lifecycle import (
    BenchmarkLifecyclePhase,
    canonical_lifecycle,
)


BENCHMARK_ATTEMPT_ACCOUNTING_SCHEMA_VERSION = "benchmark_attempt_accounting_v0"


class BenchmarkAttemptPhase(str, Enum):
    LAUNCHER = "launcher"
    CASE = "case"
    SOLVER = "solver"
    VERIFIER = "verifier"
    OFFICIAL_SCORE = "official_score"


class BenchmarkFailureClass(str, Enum):
    NONE = "none"
    RUNNER_STARTUP_FAILED = "runner_startup_failed"
    JOB_MATERIALIZATION_FAILED = "job_materialization_failed"
    SOLVER_FAILED = "solver_failed"
    VERIFIER_FAILED = "verifier_failed"
    OFFICIAL_SCORE_FAILED = "official_score_failed"
    UNKNOWN_FAILED = "unknown_failed"


FAILURE_CLASS_LABELS = {
    BenchmarkFailureClass.RUNNER_STARTUP_FAILED.value: (
        "runner_startup_failed",
        "process_start_failed",
        "runner_argument_rejected",
        "runner_accept_args_failed",
    ),
    BenchmarkFailureClass.JOB_MATERIALIZATION_FAILED.value: (
        "job_materialization_failed",
        "job_root_missing",
        "job_root_not_materialized",
        "job_materialization_timeout",
        "detached_worker_ended_without_job_root",
    ),
    BenchmarkFailureClass.SOLVER_FAILED.value: (
        "solver_failed",
        "agent_failed",
        "worker_failed",
        "worker_ended_without_result",
        "result_missing",
        "result_finalization_failed",
    ),
    BenchmarkFailureClass.VERIFIER_FAILED.value: (
        "verifier_failed",
        "verifier_timeout",
        "verifier_error",
        "oracle_failed",
        "official_verifier_failed",
    ),
    BenchmarkFailureClass.OFFICIAL_SCORE_FAILED.value: (
        "official_score_failed",
        "official_score_missing",
        "official_score_error",
        "scorer_failed",
        "score_ingest_failed",
    ),
}


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _coerce_lifecycle(lifecycle: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(lifecycle, Mapping):
        return canonical_lifecycle()
    if lifecycle.get("schema_version"):
        return dict(lifecycle)
    return canonical_lifecycle(**lifecycle)


def classify_benchmark_failure(
    failure_label: str | None,
    *,
    lifecycle: Mapping[str, Any] | None = None,
    default: BenchmarkFailureClass = BenchmarkFailureClass.UNKNOWN_FAILED,
) -> BenchmarkFailureClass:
    """Return an adapter-neutral failure class for compact benchmark ledgers."""

    label = _normalize(failure_label)
    if not label:
        return BenchmarkFailureClass.NONE
    for failure_class, aliases in FAILURE_CLASS_LABELS.items():
        if label == failure_class or label in aliases:
            return BenchmarkFailureClass(failure_class)

    lifecycle_projection = _coerce_lifecycle(lifecycle)
    phase = lifecycle_projection.get("current_phase", BenchmarkLifecyclePhase.NOT_STARTED.value)
    phase_ready = lifecycle_projection.get("phase_ready") or {}
    if not phase_ready.get(BenchmarkLifecyclePhase.PROCESS_STARTED.value):
        return BenchmarkFailureClass.RUNNER_STARTUP_FAILED
    if phase in {
        BenchmarkLifecyclePhase.PROCESS_STARTED.value,
        BenchmarkLifecyclePhase.RUNNER_ACCEPTED_ARGS.value,
    }:
        return BenchmarkFailureClass.JOB_MATERIALIZATION_FAILED
    return default


def build_benchmark_attempt_accounting(
    *,
    lifecycle: Mapping[str, Any] | None = None,
    failure_label: str | None = None,
    failure_class: BenchmarkFailureClass | str | None = None,
    solver_attempted: bool | None = None,
    verifier_attempted: bool | None = None,
    official_score_attempted: bool = False,
) -> dict[str, Any]:
    """Build compact, adapter-neutral attempt accounting.

    Launcher/materialization failures are recorded as launcher attempts, but
    they do not consume case/solver/verifier/official-score attempt budgets.
    """

    lifecycle_projection = _coerce_lifecycle(lifecycle)
    phase_ready = lifecycle_projection.get("phase_ready") or {}
    launcher_attempted = any(
        bool(phase_ready.get(phase.value))
        for phase in (
            BenchmarkLifecyclePhase.PROCESS_STARTED,
            BenchmarkLifecyclePhase.RUNNER_ACCEPTED_ARGS,
        )
    )
    case_attempted = bool(lifecycle_projection.get("entered_benchmark_case"))
    solver_seen = any(
        bool(phase_ready.get(phase.value))
        for phase in (
            BenchmarkLifecyclePhase.WORKER_STARTED,
            BenchmarkLifecyclePhase.RESULT_WRITTEN,
            BenchmarkLifecyclePhase.VERIFIER_SCORED,
        )
    )
    verifier_seen = bool(phase_ready.get(BenchmarkLifecyclePhase.VERIFIER_SCORED.value))
    solver_attempted_value = solver_seen if solver_attempted is None else bool(solver_attempted)
    verifier_attempted_value = verifier_seen if verifier_attempted is None else bool(verifier_attempted)

    if failure_class is None:
        normalized_failure_class = classify_benchmark_failure(
            failure_label, lifecycle=lifecycle_projection
        )
    else:
        normalized_failure_class = BenchmarkFailureClass(_normalize(failure_class))

    attempts = {
        BenchmarkAttemptPhase.LAUNCHER.value: {
            "attempted": launcher_attempted,
            "countable": launcher_attempted,
        },
        BenchmarkAttemptPhase.CASE.value: {
            "attempted": case_attempted,
            "countable": case_attempted,
        },
        BenchmarkAttemptPhase.SOLVER.value: {
            "attempted": solver_attempted_value,
            "countable": solver_attempted_value,
        },
        BenchmarkAttemptPhase.VERIFIER.value: {
            "attempted": verifier_attempted_value,
            "countable": verifier_attempted_value,
        },
        BenchmarkAttemptPhase.OFFICIAL_SCORE.value: {
            "attempted": bool(official_score_attempted),
            "countable": bool(official_score_attempted),
        },
    }
    return {
        "schema_version": BENCHMARK_ATTEMPT_ACCOUNTING_SCHEMA_VERSION,
        "lifecycle_phase": lifecycle_projection.get("current_phase"),
        "failure_label": str(failure_label or ""),
        "failure_class": normalized_failure_class.value,
        "attempts": attempts,
        "launcher_attempt_countable": attempts[BenchmarkAttemptPhase.LAUNCHER.value][
            "countable"
        ],
        "case_attempt_countable": attempts[BenchmarkAttemptPhase.CASE.value]["countable"],
        "solver_attempt_countable": attempts[BenchmarkAttemptPhase.SOLVER.value][
            "countable"
        ],
        "verifier_attempt_countable": attempts[BenchmarkAttemptPhase.VERIFIER.value][
            "countable"
        ],
        "official_score_attempt_countable": attempts[
            BenchmarkAttemptPhase.OFFICIAL_SCORE.value
        ]["countable"],
    }
