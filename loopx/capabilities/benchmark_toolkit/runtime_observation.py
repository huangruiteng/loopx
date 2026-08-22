"""Compact, provider-neutral runtime observation for benchmark monitors."""

from __future__ import annotations

from enum import Enum
from typing import Any

BENCHMARK_RUNTIME_OBSERVATION_SCHEMA_VERSION = "benchmark_runtime_observation_v0"


class BenchmarkJobReceiptState(str, Enum):
    """Whether the provider bound runtime evidence to exactly one admitted job."""

    RESOLVED = "resolved"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


class BenchmarkRunnerOwnerState(str, Enum):
    """Liveness of the exact runner owner after provider-defined startup grace."""

    ALIVE = "alive"
    ABSENT_AFTER_GRACE = "absent_after_grace"
    UNKNOWN = "unknown"


class BenchmarkRuntimeClassification(str, Enum):
    """Public-safe monitor classification for one admitted run."""

    NOT_ADMITTED = "not_admitted"
    RUNNING_QUALIFIED = "running_qualified"
    TERMINAL_PENDING_RECONCILE = "terminal_pending_reconcile"
    RUNNER_INVALID_PENDING_RECONCILE = "runner_invalid_pending_reconcile"
    RUNTIME_AUTHORITY_UNRESOLVED = "runtime_authority_unresolved"
    RUNNER_LOST_PENDING_RECONCILE = "runner_lost_pending_reconcile"
    STARTUP_OR_LIVENESS_UNRESOLVED = "startup_or_liveness_unresolved"


class BenchmarkRuntimeTransition(str, Enum):
    """Provider-owned next transition; this reducer never performs it."""

    NONE = "none"
    WRITE_TERMINAL_THEN_RELEASE = "write_terminal_then_release"
    WRITE_RUNNER_INVALID_THEN_RELEASE = "write_runner_invalid_then_release"
    REPAIR_RUNTIME_AUTHORITY = "repair_runtime_authority"
    REOBSERVE_AFTER_STARTUP_GRACE = "reobserve_after_startup_grace"


def _coerce_enum(value: str | Enum, enum_type: type[Enum], *, field: str) -> Enum:
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"invalid_{field}") from exc


def build_benchmark_runtime_observation(
    *,
    admission_active: bool,
    job_receipt_state: str | BenchmarkJobReceiptState,
    runner_owner_state: str | BenchmarkRunnerOwnerState,
    terminal_result_present: bool = False,
    typed_fatal_runner_error: bool = False,
) -> dict[str, Any]:
    """Reduce provider facts without treating the admission ledger as liveness.

    The caller owns process discovery, startup-grace policy, terminal writes, and
    slot release.  This helper only classifies compact facts and never records a
    run identity, process argument, path, or raw error.
    """

    receipt = _coerce_enum(
        job_receipt_state,
        BenchmarkJobReceiptState,
        field="job_receipt_state",
    )
    owner = _coerce_enum(
        runner_owner_state,
        BenchmarkRunnerOwnerState,
        field="runner_owner_state",
    )

    if not admission_active:
        classification = BenchmarkRuntimeClassification.NOT_ADMITTED
        transition = BenchmarkRuntimeTransition.NONE
        reconciliation_required = False
    elif terminal_result_present:
        classification = BenchmarkRuntimeClassification.TERMINAL_PENDING_RECONCILE
        transition = BenchmarkRuntimeTransition.WRITE_TERMINAL_THEN_RELEASE
        reconciliation_required = True
    elif typed_fatal_runner_error:
        classification = BenchmarkRuntimeClassification.RUNNER_INVALID_PENDING_RECONCILE
        transition = BenchmarkRuntimeTransition.WRITE_RUNNER_INVALID_THEN_RELEASE
        reconciliation_required = True
    elif receipt is not BenchmarkJobReceiptState.RESOLVED:
        classification = BenchmarkRuntimeClassification.RUNTIME_AUTHORITY_UNRESOLVED
        transition = BenchmarkRuntimeTransition.REPAIR_RUNTIME_AUTHORITY
        reconciliation_required = False
    elif owner is BenchmarkRunnerOwnerState.ALIVE:
        classification = BenchmarkRuntimeClassification.RUNNING_QUALIFIED
        transition = BenchmarkRuntimeTransition.NONE
        reconciliation_required = False
    elif owner is BenchmarkRunnerOwnerState.ABSENT_AFTER_GRACE:
        classification = BenchmarkRuntimeClassification.RUNNER_LOST_PENDING_RECONCILE
        transition = BenchmarkRuntimeTransition.WRITE_RUNNER_INVALID_THEN_RELEASE
        reconciliation_required = True
    else:
        classification = BenchmarkRuntimeClassification.STARTUP_OR_LIVENESS_UNRESOLVED
        transition = BenchmarkRuntimeTransition.REOBSERVE_AFTER_STARTUP_GRACE
        reconciliation_required = False

    healthy_active = classification is BenchmarkRuntimeClassification.RUNNING_QUALIFIED
    return {
        "schema_version": BENCHMARK_RUNTIME_OBSERVATION_SCHEMA_VERSION,
        "classification": classification.value,
        "healthy_active": healthy_active,
        "admission_active": bool(admission_active),
        "job_receipt_state": receipt.value,
        "runner_owner_state": owner.value,
        "terminal_result_present": bool(terminal_result_present),
        "typed_fatal_runner_error": bool(typed_fatal_runner_error),
        "ledger_occupancy_sufficient": False,
        "exact_runtime_authority_required": True,
        "reconciliation_required": reconciliation_required,
        "recommended_transition": transition.value,
        "public_boundary": {
            "run_identity_recorded": False,
            "process_arguments_recorded": False,
            "raw_error_recorded": False,
            "path_recorded": False,
        },
        "write_performed": False,
    }
