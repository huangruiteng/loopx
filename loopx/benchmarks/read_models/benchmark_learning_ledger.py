from __future__ import annotations

from typing import Any

from .benchmark_comparison import compact_comparison_delta
from ...control_plane.runtime.public_safety import (
    public_safe_compact_list,
    public_safe_compact_text,
)

BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION = "benchmark_learning_ledger_v0"
MAX_BENCHMARK_LEARNING_LEDGER_LIST_ITEMS = 5


def _benchmark_learning_ledger_source(
    run: dict[str, Any],
) -> dict[str, Any] | None:
    nested = run.get("benchmark_learning_ledger")
    if (
        isinstance(nested, dict)
        and nested.get("schema_version") == BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION
    ):
        return nested
    if run.get("schema_version") == BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION:
        return run
    return None


def compact_benchmark_learning_ledger(
    run: dict[str, Any],
) -> dict[str, Any] | None:
    source = _benchmark_learning_ledger_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {
        "schema_version": BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION
    }
    for field in ("task_id", "comparison_id", "learning_status", "claim_strength"):
        value = public_safe_compact_text(source.get(field), limit=180)
        if value:
            compact[field] = value

    for field in ("official_task_score_delta", "control_plane_score_delta"):
        delta = compact_comparison_delta(source.get(field))
        if delta is not None:
            compact[field] = delta

    for field in ("repair_candidates", "claim_blockers"):
        values = public_safe_compact_list(
            source.get(field), limit=MAX_BENCHMARK_LEARNING_LEDGER_LIST_ITEMS
        )
        if values:
            compact[field] = values

    lifecycle_gate = source.get("lifecycle_gate")
    if isinstance(lifecycle_gate, dict):
        compact_gate: dict[str, Any] = {}
        for field in ("budget_count_allowed", "blocked_reason"):
            value = lifecycle_gate.get(field)
            if isinstance(value, bool):
                compact_gate[field] = value
            elif field == "blocked_reason":
                text = public_safe_compact_text(value, limit=160)
                if text:
                    compact_gate[field] = text
        if compact_gate:
            compact["lifecycle_gate"] = compact_gate

    learning_gate = source.get("learning_quota_gate")
    if isinstance(learning_gate, dict):
        compact_learning_gate: dict[str, Any] = {}
        for field in (
            "actionable_learning_present",
            "spend_allowed",
            "blocked_reason",
        ):
            value = learning_gate.get(field)
            if isinstance(value, bool):
                compact_learning_gate[field] = value
            elif field == "blocked_reason":
                text = public_safe_compact_text(value, limit=160)
                if text:
                    compact_learning_gate[field] = text
        reasons = public_safe_compact_list(
            learning_gate.get("actionable_reasons"),
            limit=MAX_BENCHMARK_LEARNING_LEDGER_LIST_ITEMS,
        )
        if reasons:
            compact_learning_gate["actionable_reasons"] = reasons
        if compact_learning_gate:
            compact["learning_quota_gate"] = compact_learning_gate

    overhead = source.get("overhead")
    if isinstance(overhead, dict):
        compact_overhead: dict[str, Any] = {}
        for field in ("cost_delta_usd", "wall_time_delta_seconds_or_ms"):
            delta = compact_comparison_delta(overhead.get(field))
            if delta is not None:
                compact_overhead[field] = delta
        label = public_safe_compact_text(overhead.get("label"), limit=120)
        if label:
            compact_overhead["label"] = label
        if compact_overhead:
            compact["overhead"] = compact_overhead

    routing = source.get("routing")
    if isinstance(routing, dict):
        compact_routing: dict[str, Any] = {}
        for field in ("repeat_allowed", "new_candidate_allowed"):
            if isinstance(routing.get(field), bool):
                compact_routing[field] = routing[field]
        next_action = public_safe_compact_text(
            routing.get("next_allowed_action"), limit=180
        )
        if next_action:
            compact_routing["next_allowed_action"] = next_action
        if compact_routing:
            compact["routing"] = compact_routing

    read_boundary = source.get("read_boundary")
    if isinstance(read_boundary, dict):
        compact_boundary: dict[str, bool] = {}
        for field in (
            "compact_only",
            "raw_artifacts_read",
            "task_text_read",
            "local_paths_recorded",
        ):
            if isinstance(read_boundary.get(field), bool):
                compact_boundary[field] = read_boundary[field]
        if compact_boundary:
            compact["read_boundary"] = compact_boundary

    if set(compact) == {"schema_version"}:
        return None
    return compact
