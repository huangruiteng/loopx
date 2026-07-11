from __future__ import annotations

from typing import Any

from .public_safety import public_safe_compact_text

WORKER_BRIDGE_INGEST_HEALTH_SCHEMA_VERSION = "worker_bridge_ingest_health_note_v0"
_BENCHMARK_RUN_SCHEMA_VERSION = "benchmark_run_v0"


def compact_environment_setup_failure_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "surface",
        "failure_kind",
        "diagnostic_granularity",
        "exception_type",
        "timeout_signal",
        "resource_signal",
        "environment_setup_duration_tier",
        "next_probe",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "environment_setup_present",
        "environment_setup_started",
        "environment_setup_finished",
        "agent_setup_started",
        "agent_execution_started",
        "worker_trace_present",
        "worker_benchmark_run_present",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    seconds = value.get("environment_setup_duration_seconds")
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
        compact["environment_setup_duration_seconds"] = seconds
    return compact


def worker_bridge_ingest_health_note(
    benchmark_run: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Derive a compact agent-facing health note for worker-written run ingest."""

    if not isinstance(benchmark_run, dict):
        return None
    outcome = benchmark_run.get("worker_bridge_outcome")
    if not isinstance(outcome, dict):
        return None

    verified = bool(outcome.get("worker_bridge_verified"))
    runner_status = public_safe_compact_text(
        outcome.get("runner_return_status"),
        limit=120,
    )
    official_status = public_safe_compact_text(
        outcome.get("official_score_status"),
        limit=120,
    )
    bridge_surface = public_safe_compact_text(outcome.get("bridge_surface"), limit=120)
    trace_publicness = public_safe_compact_text(
        outcome.get("trace_publicness") or benchmark_run.get("trace_publicness"),
        limit=120,
    )
    materialization_status = public_safe_compact_text(
        outcome.get("worker_bridge_materialization_status")
        or benchmark_run.get("worker_bridge_materialization_status"),
        limit=120,
    )
    materialization_blocker = public_safe_compact_text(
        outcome.get("worker_bridge_materialization_blocker")
        or benchmark_run.get("worker_bridge_materialization_blocker")
        or benchmark_run.get("first_blocker"),
        limit=120,
    )
    failure_attribution = public_safe_compact_text(
        outcome.get("worker_bridge_failure_attribution")
        or benchmark_run.get("worker_bridge_failure_attribution"),
        limit=120,
    )
    cli_total = outcome.get("worker_loopx_cli_call_total")
    required_total = outcome.get("required_worker_loopx_cli_call_total_min")
    if isinstance(cli_total, bool) or not isinstance(cli_total, int):
        cli_total = 0
    if isinstance(required_total, bool) or not isinstance(required_total, int):
        required_total = 1

    validation = (
        benchmark_run.get("validation")
        if isinstance(benchmark_run.get("validation"), dict)
        else {}
    )
    validation_all_passed = validation.get("all_passed")
    if not isinstance(validation_all_passed, bool):
        validation_all_passed = None
    env_context = compact_environment_setup_failure_context(
        outcome.get("environment_setup_failure_context")
        or benchmark_run.get("environment_setup_failure_context")
    )

    if materialization_status == "environment_setup_failed_before_worker":
        health_state = "environment_setup_failed_before_worker"
        evidence_layer = "not_ready"
        next_action = "diagnose benchmark environment setup before worker startup"
    elif materialization_status == "pre_worker_setup_failed":
        health_state = (
            materialization_blocker
            or "pre_worker_agent_setup_failed_before_bridge_checkpoint"
        )
        evidence_layer = "not_ready"
        next_action = "repair Codex agent setup/launcher before another run"
    elif materialization_status == "pre_worker_startup_blocker_recorded":
        health_state = materialization_blocker or "pre_worker_startup_blocker_recorded"
        evidence_layer = "compact_startup_blocker"
        next_action = "repair recorded worker startup blocker before another run"
    elif materialization_status == "runtime_exception_before_checkpoint":
        health_state = "worker_runtime_exception_before_bridge_checkpoint"
        evidence_layer = "not_ready"
        next_action = "diagnose compact worker runtime failure before another run"
    elif materialization_status == "not_materialized":
        health_state = "worker_bridge_not_materialized"
        evidence_layer = "not_ready"
        next_action = "repair launcher or worker startup bridge materialization before another run"
    elif not verified:
        health_state = "worker_bridge_evidence_incomplete"
        evidence_layer = "not_ready"
        next_action = "repair worker bridge compact evidence before another run"
    elif runner_status == "completed" and official_status == "completed":
        health_state = "official_score_ingested"
        evidence_layer = "official_sample_score"
        next_action = "compare against the selected baseline under no-upload policy"
    elif runner_status.startswith("interrupted"):
        health_state = "runner_return_blocked_after_worker_bridge"
        evidence_layer = "worker_bridge_verified_runner_blocker"
        next_action = "close runner return or record an explicit runner-return blocker"
    else:
        health_state = "worker_bridge_verified_pending_runner_return"
        evidence_layer = "worker_bridge_ingest_only"
        next_action = "finish runner return or append the pending-runner blocker"

    note: dict[str, Any] = {
        "schema_version": WORKER_BRIDGE_INGEST_HEALTH_SCHEMA_VERSION,
        "source_schema_version": _BENCHMARK_RUN_SCHEMA_VERSION,
        "health_state": health_state,
        "evidence_layer": evidence_layer,
        "worker_bridge_verified": verified,
        "runner_return_status": runner_status or "unknown",
        "official_score_status": official_status or "unknown",
        "worker_loopx_cli_call_total": cli_total,
        "required_worker_loopx_cli_call_total_min": required_total,
        "worker_bridge_materialization_status": materialization_status or "unknown",
        "worker_bridge_materialization_blocker": materialization_blocker or "none",
        "worker_bridge_failure_attribution": failure_attribution or "none",
        "validation_all_passed": validation_all_passed,
        "next_action": next_action,
        "may_claim": [
            "worker bridge ingest health from compact benchmark_run_v0",
        ],
        "must_not_claim": [
            "leaderboard uplift",
            "official reward complete without official score status completed",
            "raw trace public",
        ],
    }
    if bridge_surface:
        note["bridge_surface"] = bridge_surface
    if trace_publicness:
        note["trace_publicness"] = trace_publicness
    if env_context:
        note["environment_setup_failure_context"] = env_context
    return note
