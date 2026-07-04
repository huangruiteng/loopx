from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..delivery_batch_scale import UNKNOWN_DELIVERY_BATCH_SCALE, DeliveryBatchScale, normalize_delivery_batch_scale
from ..delivery_outcome import (
    DELIVERY_OUTCOME_NOT_CONFIGURED,
    DELIVERY_OUTCOME_UNKNOWN,
    PROGRESS_DELIVERY_OUTCOMES,
    DeliveryOutcome,
    normalize_delivery_outcome,
)


def delivery_batch_scale_for_run(
    run: dict[str, Any],
    *,
    test_only_hints: tuple[str, ...],
    multi_surface_hints: tuple[str, ...],
    implementation_hints: tuple[str, ...],
) -> str:
    explicit = normalize_delivery_batch_scale(run.get("delivery_batch_scale"))
    if explicit:
        return explicit.value
    if str(run.get("delivery_batch_scale") or "").strip():
        return UNKNOWN_DELIVERY_BATCH_SCALE
    classification = str(run.get("classification") or "")
    if not classification:
        return UNKNOWN_DELIVERY_BATCH_SCALE
    normalized = classification.lower()
    if any(hint in normalized for hint in test_only_hints):
        return DeliveryBatchScale.TEST_ONLY.value
    if any(hint in normalized for hint in multi_surface_hints):
        return DeliveryBatchScale.MULTI_SURFACE.value
    if any(hint in normalized for hint in implementation_hints):
        return DeliveryBatchScale.IMPLEMENTATION.value
    return DeliveryBatchScale.SINGLE_SURFACE.value


def classification_contains_any(classification: str, hints: list[Any]) -> bool:
    normalized = classification.lower()
    return any(str(hint or "").strip().lower() in normalized for hint in hints if str(hint or "").strip())


def delivery_outcome_for_run(
    run: dict[str, Any],
    profile: dict[str, Any] | None = None,
    *,
    execution_profile_outcome_floor: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> str:
    explicit = normalize_delivery_outcome(run.get("delivery_outcome"))
    if explicit:
        return explicit.value
    if str(run.get("delivery_outcome") or "").strip():
        return DELIVERY_OUTCOME_UNKNOWN
    classification = str(run.get("classification") or "")
    if not classification:
        return DELIVERY_OUTCOME_UNKNOWN
    floor = execution_profile_outcome_floor(profile)
    outcome_markers = floor.get("outcome_markers") if isinstance(floor.get("outcome_markers"), list) else []
    surface_hints = floor.get("surface_only_hints") if isinstance(floor.get("surface_only_hints"), list) else []
    if not outcome_markers and not surface_hints:
        return DELIVERY_OUTCOME_NOT_CONFIGURED
    marker_hit = classification_contains_any(classification, outcome_markers)
    surface_hit = classification_contains_any(classification, surface_hints)
    if surface_hit:
        return DeliveryOutcome.SURFACE_ONLY.value
    if marker_hit:
        return DeliveryOutcome.OUTCOME_PROGRESS.value
    return DeliveryOutcome.OUTCOME_GAP.value


def outcome_floor_configured(
    profile: dict[str, Any] | None,
    *,
    execution_profile_outcome_floor: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> bool:
    floor = execution_profile_outcome_floor(profile)
    return bool(floor.get("outcome_markers") or floor.get("surface_only_hints"))


def outcome_gap_streak(
    runs: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
    *,
    delivery_outcome_for_run: Callable[[dict[str, Any], dict[str, Any] | None], str],
    outcome_floor_configured: Callable[[dict[str, Any] | None], bool],
) -> int:
    if not outcome_floor_configured(profile):
        return 0
    streak = 0
    for run in runs:
        outcome = delivery_outcome_for_run(run, profile)
        normalized = normalize_delivery_outcome(outcome)
        if normalized in PROGRESS_DELIVERY_OUTCOMES or outcome == DELIVERY_OUTCOME_NOT_CONFIGURED:
            break
        streak += 1
    return streak


def small_delivery_batch_scale_streak(
    runs: list[dict[str, Any]],
    *,
    delivery_batch_scale_for_run: Callable[[dict[str, Any]], str],
    small_delivery_batch_scales: set[str],
) -> int:
    streak = 0
    for run in runs:
        if delivery_batch_scale_for_run(run) not in small_delivery_batch_scales:
            break
        streak += 1
    return streak
