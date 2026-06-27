from __future__ import annotations

from typing import Any

from .delivery_batch_scale import DeliveryBatchScale, normalize_delivery_batch_scale
from .delivery_outcome import (
    DeliveryOutcome,
    DeliveryTurnKind,
    normalize_delivery_outcome,
    normalize_delivery_turn_kind,
)
from .execution_profile import compact_execution_profile, execution_profile_threshold


LONG_TASK_CADENCE_SCHEMA_VERSION = "long_task_cadence_policy_v0"

CADENCE_PRESETS = frozenset({"ultra-long", "long", "medium", "short"})
DEFAULT_CADENCE_PRESET = "long"
DEFAULT_PRESET_SOURCE = "connected_autonomous_default"

RECOMMENDED_BATCH_GRANULARITY = {
    "ultra-long": "milestone",
    "long": "implementation_plus_validation_writeback",
    "medium": "multi_surface",
    "short": "single_surface",
}
NON_WIDENING_QUOTA_STATES = frozenset(
    {
        "blocked",
        "blocked_health",
        "focus_wait",
        "monitor_only",
        "operator_gate",
        "paused",
        "throttled",
        "user_gate",
        "waiting",
    }
)
SMALL_PROGRESS_GRANULARITIES = frozenset({"status_only", "single_surface"})
RUN_DURATION_MINUTE_FIELDS = ("turn_duration_minutes", "duration_minutes", "elapsed_minutes")
RUN_DURATION_SECOND_FIELDS = ("duration_s", "duration_seconds", "elapsed_s", "elapsed_seconds")
RUN_DURATION_MILLISECOND_FIELDS = ("duration_ms", "elapsed_ms")


def _positive_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _duration_minutes(run: dict[str, Any]) -> int | None:
    for field in RUN_DURATION_MINUTE_FIELDS:
        parsed = _positive_number(run.get(field))
        if parsed is not None:
            return max(1, round(parsed))
    for field in RUN_DURATION_SECOND_FIELDS:
        parsed = _positive_number(run.get(field))
        if parsed is not None:
            return max(1, round(parsed / 60))
    for field in RUN_DURATION_MILLISECOND_FIELDS:
        parsed = _positive_number(run.get(field))
        if parsed is not None:
            return max(1, round(parsed / 60000))
    return None


def _cadence_preset(profile: dict[str, Any]) -> tuple[str, str]:
    cadence = str(profile.get("cadence") or "").strip()
    if cadence in CADENCE_PRESETS:
        return cadence, "execution_profile.cadence"
    return DEFAULT_CADENCE_PRESET, DEFAULT_PRESET_SOURCE


def _progress_granularity(run: dict[str, Any] | None) -> str:
    if not isinstance(run, dict) or not run:
        return "status_only"

    outcome = normalize_delivery_outcome(run.get("delivery_outcome"))
    turn_kind = normalize_delivery_turn_kind(run.get("delivery_turn_kind"))
    scale = normalize_delivery_batch_scale(run.get("delivery_batch_scale"))

    if outcome == DeliveryOutcome.PRIMARY_GOAL_OUTCOME:
        return "milestone"
    if outcome == DeliveryOutcome.OUTCOME_PROGRESS:
        return "implementation_plus_validation"
    if turn_kind == DeliveryTurnKind.PRODUCT_PATH_EXECUTION:
        return "implementation_plus_validation"
    if scale == DeliveryBatchScale.IMPLEMENTATION:
        return "implementation_plus_validation"
    if scale == DeliveryBatchScale.MULTI_SURFACE or turn_kind == DeliveryTurnKind.COMPACT_EVIDENCE:
        return "multi_surface"
    if scale in {DeliveryBatchScale.TEST_ONLY, DeliveryBatchScale.SINGLE_SURFACE}:
        return "single_surface"
    if turn_kind == DeliveryTurnKind.CONTRACT_ONLY_PREPARATION:
        return "single_surface"
    return "status_only"


def _small_step_streak(runs: list[dict[str, Any]]) -> int:
    streak = 0
    for run in runs:
        turn_kind = normalize_delivery_turn_kind(run.get("delivery_turn_kind"))
        if turn_kind == DeliveryTurnKind.BLOCKER_WRITEBACK:
            break
        if _progress_granularity(run) not in SMALL_PROGRESS_GRANULARITIES:
            break
        streak += 1
    return streak


def _recent_runs(
    *,
    latest_runs: list[dict[str, Any]] | None,
    handoff_readiness: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    readiness = handoff_readiness if isinstance(handoff_readiness, dict) else {}
    compact_runs = (
        readiness.get("post_handoff_recent_runs")
        if isinstance(readiness.get("post_handoff_recent_runs"), list)
        else []
    )
    if compact_runs:
        return [run for run in compact_runs if isinstance(run, dict)]
    latest_run = readiness.get("post_handoff_latest_run")
    if isinstance(latest_run, dict) and latest_run:
        return [latest_run]
    runs = [run for run in latest_runs or [] if isinstance(run, dict)]
    if runs:
        return runs
    return []


def build_long_task_cadence_policy(
    *,
    execution_profile: dict[str, Any] | None = None,
    latest_runs: list[dict[str, Any]] | None = None,
    handoff_readiness: dict[str, Any] | None = None,
    quota_state: str | None = None,
    user_todo_open_count: int | None = None,
) -> dict[str, Any]:
    """Build a compact, public-safe cadence hint from existing control signals."""

    profile = compact_execution_profile(execution_profile)
    cadence_preset, preset_source = _cadence_preset(profile)
    runs = _recent_runs(latest_runs=latest_runs, handoff_readiness=handoff_readiness)
    latest_run = runs[0] if runs else {}
    threshold = execution_profile_threshold(profile)
    small_step_streak = _small_step_streak(runs)
    too_small = small_step_streak >= threshold
    normalized_quota_state = str(quota_state or "").strip()
    blocked_priority_fallback_visible = bool(user_todo_open_count and user_todo_open_count > 0)

    cadence: dict[str, Any] = {
        "schema_version": LONG_TASK_CADENCE_SCHEMA_VERSION,
        "cadence_preset": cadence_preset,
        "preset_source": preset_source,
        "progress_granularity": _progress_granularity(latest_run),
        "small_step_streak": small_step_streak,
        "too_small_heartbeat_batch": too_small,
        "recommended_batch_granularity": RECOMMENDED_BATCH_GRANULARITY[cadence_preset],
        "widen_next_turn": too_small
        and (
            not normalized_quota_state
            or normalized_quota_state not in NON_WIDENING_QUOTA_STATES
        ),
        "blocked_priority_fallback_visible": blocked_priority_fallback_visible,
    }
    duration = _duration_minutes(latest_run)
    if duration is not None:
        cadence["turn_duration_minutes"] = duration
    return cadence


def long_task_cadence_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    duration = value.get("turn_duration_minutes")
    duration_text = f" duration_min={duration}" if duration is not None else ""
    return (
        f"preset={value.get('cadence_preset')} "
        f"source={value.get('preset_source')} "
        f"granularity={value.get('progress_granularity')} "
        f"small_streak={value.get('small_step_streak')} "
        f"too_small={value.get('too_small_heartbeat_batch')} "
        f"widen_next={value.get('widen_next_turn')} "
        f"recommended={value.get('recommended_batch_granularity')} "
        f"blocked_priority_visible={value.get('blocked_priority_fallback_visible')}"
        f"{duration_text}"
    )
