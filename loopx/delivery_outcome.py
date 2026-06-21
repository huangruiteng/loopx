from __future__ import annotations

from enum import Enum
from typing import Any


class DeliveryOutcome(str, Enum):
    """Structured machine signal for what a delivery run actually advanced."""

    SURFACE_ONLY = "surface_only"
    OUTCOME_GAP = "outcome_gap"
    OUTCOME_PROGRESS = "outcome_progress"
    PRIMARY_GOAL_OUTCOME = "primary_goal_outcome"


DELIVERY_OUTCOME_CHOICES = tuple(outcome.value for outcome in DeliveryOutcome)
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
