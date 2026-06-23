from __future__ import annotations

from enum import Enum
from typing import Any


class DeliveryOutcome(str, Enum):
    """Structured machine signal for what a delivery run actually advanced."""

    SURFACE_ONLY = "surface_only"
    OUTCOME_GAP = "outcome_gap"
    OUTCOME_PROGRESS = "outcome_progress"
    PRIMARY_GOAL_OUTCOME = "primary_goal_outcome"


class DeliveryTurnKind(str, Enum):
    """Compact public-safe classification for why a delivery turn counts."""

    CONTRACT_ONLY_PREPARATION = "contract_only_preparation"
    COMPACT_EVIDENCE = "compact_evidence"
    BLOCKER_WRITEBACK = "blocker_writeback"
    PRODUCT_PATH_EXECUTION = "product_path_execution"
    OUTCOME_GAP = "outcome_gap"
    UNKNOWN = "unknown"


DELIVERY_OUTCOME_CHOICES = tuple(outcome.value for outcome in DeliveryOutcome)
DELIVERY_TURN_KIND_CHOICES = tuple(kind.value for kind in DeliveryTurnKind)
DELIVERY_OUTCOME_UNKNOWN = "unknown"
DELIVERY_OUTCOME_NOT_CONFIGURED = "not_configured"

ACCOUNTABLE_DELIVERY_OUTCOMES = frozenset(
    {
        DeliveryOutcome.OUTCOME_PROGRESS,
        DeliveryOutcome.PRIMARY_GOAL_OUTCOME,
    }
)
FOLLOWTHROUGH_REQUIRED_DELIVERY_OUTCOMES = frozenset(
    {
        DeliveryOutcome.SURFACE_ONLY,
        DeliveryOutcome.OUTCOME_GAP,
    }
)
PROGRESS_DELIVERY_OUTCOMES = ACCOUNTABLE_DELIVERY_OUTCOMES


def normalize_delivery_outcome(value: Any) -> DeliveryOutcome | None:
    if isinstance(value, DeliveryOutcome):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return DeliveryOutcome(text)
    except ValueError:
        return None


def require_delivery_outcome(value: Any) -> DeliveryOutcome:
    outcome = normalize_delivery_outcome(value)
    if outcome is None:
        raise ValueError("delivery_outcome must be one of: " + ", ".join(DELIVERY_OUTCOME_CHOICES))
    return outcome


def delivery_outcome_value(value: Any) -> str | None:
    outcome = normalize_delivery_outcome(value)
    return outcome.value if outcome else None


def normalize_delivery_turn_kind(value: Any) -> DeliveryTurnKind | None:
    if isinstance(value, DeliveryTurnKind):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return DeliveryTurnKind(text)
    except ValueError:
        return None


def require_delivery_turn_kind(value: Any) -> DeliveryTurnKind:
    kind = normalize_delivery_turn_kind(value)
    if kind is None:
        raise ValueError("delivery_turn_kind must be one of: " + ", ".join(DELIVERY_TURN_KIND_CHOICES))
    return kind


def delivery_turn_kind_for_run(
    run: dict[str, Any],
    *,
    delivery_outcome: Any = None,
) -> str:
    """Classify the latest turn without relying on free-form classification text alone."""

    raw_explicit = str(run.get("delivery_turn_kind") or "").strip()
    if raw_explicit:
        explicit = normalize_delivery_turn_kind(raw_explicit)
        return explicit.value if explicit else DeliveryTurnKind.UNKNOWN.value

    outcome = normalize_delivery_outcome(
        delivery_outcome if delivery_outcome is not None else run.get("delivery_outcome")
    )
    classification = str(run.get("classification") or "").strip().lower()
    health_check = str(run.get("health_check") or "").strip().lower()
    recommended_action = str(run.get("recommended_action") or "").strip().lower()
    searchable = " ".join(part for part in (classification, health_check, recommended_action) if part)

    if outcome == DeliveryOutcome.PRIMARY_GOAL_OUTCOME:
        return DeliveryTurnKind.PRODUCT_PATH_EXECUTION.value

    evidence_keys = (
        "benchmark_run_summary",
        "benchmark_result_summary",
        "benchmark_comparison_summary",
        "benchmark_learning_ledger_summary",
        "benchmark_experiment_report_summary",
        "active_user_assisted_pilot_summary",
        "benchmark_run",
        "benchmark_result",
        "benchmark_comparison",
        "benchmark_learning_ledger",
        "benchmark_experiment_report",
        "case_result",
        "compact_evidence",
    )
    if outcome == DeliveryOutcome.OUTCOME_PROGRESS or any(run.get(key) for key in evidence_keys):
        return DeliveryTurnKind.COMPACT_EVIDENCE.value

    if any(hint in searchable for hint in ("blocker", "blocked", "cannot proceed", "can't proceed")):
        return DeliveryTurnKind.BLOCKER_WRITEBACK.value

    if outcome == DeliveryOutcome.SURFACE_ONLY or any(
        hint in classification
        for hint in (
            "contract",
            "prep",
            "preparation",
            "protocol",
            "policy",
            "surface",
            "smoke",
            "setup",
        )
    ):
        return DeliveryTurnKind.CONTRACT_ONLY_PREPARATION.value

    if outcome == DeliveryOutcome.OUTCOME_GAP:
        return DeliveryTurnKind.OUTCOME_GAP.value

    return DeliveryTurnKind.UNKNOWN.value
