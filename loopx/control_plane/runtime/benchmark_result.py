from __future__ import annotations

from typing import Any

from .public_safety import (
    compact_numeric_map,
    public_safe_compact_list,
    public_safe_compact_text,
)

BENCHMARK_RESULT_SCHEMA_VERSION = "benchmark_result_v0"
CONTROL_PLANE_SCORE_COMPONENTS = (
    "restartability",
    "stale_state_avoidance",
    "evidence_discipline",
    "boundary_safety",
    "writeback_quality",
    "gate_compliance",
    "failure_attribution",
    "overhead",
)
MAX_BENCHMARK_RESULT_LIST_ITEMS = 5


def _benchmark_result_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_result")
    if (
        isinstance(nested, dict)
        and nested.get("schema_version") == BENCHMARK_RESULT_SCHEMA_VERSION
    ):
        return nested
    if run.get("schema_version") == BENCHMARK_RESULT_SCHEMA_VERSION:
        return run
    return None


def _compact_score_layer(value: Any, *, include_schema: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    if include_schema:
        schema = public_safe_compact_text(value.get("schema_version"), limit=80)
        if schema:
            compact["schema_version"] = schema
    for field in ("kind", "aggregation"):
        text = public_safe_compact_text(value.get(field), limit=80)
        if text:
            compact[field] = text
    if isinstance(value.get("passed"), bool):
        compact["passed"] = value["passed"]
    score_value = value.get("value")
    if isinstance(score_value, (int, float)) and not isinstance(score_value, bool):
        compact["value"] = score_value
    return compact


def _compact_control_plane_score(value: Any) -> dict[str, Any]:
    compact = _compact_score_layer(value, include_schema=True)
    if not isinstance(value, dict):
        return compact
    components = (
        value.get("components") if isinstance(value.get("components"), dict) else {}
    )
    compact_components: dict[str, Any] = {}
    for component in CONTROL_PLANE_SCORE_COMPONENTS:
        score = components.get(component)
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            compact_components[component] = score
    if compact_components:
        compact["components"] = compact_components
        compact["component_order"] = list(compact_components)
    return compact


def compact_benchmark_result(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_result_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_RESULT_SCHEMA_VERSION}
    for field in (
        "task_id",
        "scenario_id",
        "worker_mode",
        "harness_identity",
        "worker_surface",
        "terminal_state",
        "trace_publicness",
    ):
        value = public_safe_compact_text(source.get(field), limit=120)
        if value:
            compact[field] = value

    official_score = _compact_score_layer(source.get("official_task_score"))
    if official_score:
        compact["official_task_score"] = official_score
    control_score = _compact_control_plane_score(source.get("control_plane_score"))
    if control_score:
        compact["control_plane_score"] = control_score

    counts = compact_numeric_map(
        source,
        keys=(
            "step_count",
            "wall_time_ms",
            "validation_pass_count",
            "validation_fail_count",
            "changed_file_count",
            "forbidden_access_count",
            "stale_state_error_count",
            "writeback_count",
            "spend_count",
            "spend_before_validation_count",
            "goal_tick_phase_coverage",
        ),
    )
    if counts:
        compact["counts"] = counts

    for field in (
        "open_todo_preserved",
        "archive_hygiene_passed",
        "queue_contract_passed",
        "state_reconstructable",
    ):
        if isinstance(source.get(field), bool):
            compact[field] = source[field]

    labels = public_safe_compact_list(
        source.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_RESULT_LIST_ITEMS,
    )
    if labels:
        compact["failure_attribution_labels"] = labels

    if set(compact) == {"schema_version"}:
        return None
    return compact
