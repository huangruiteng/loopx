from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from .progress_result import (
    PROGRESS_OBSERVATION_SCHEMA_VERSION,
    ProgressResultClass,
    normalize_progress_identifier,
)


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

MATERIAL_DELIVERY_OUTCOMES = frozenset(
    {
        DeliveryOutcome.OUTCOME_GAP,
        DeliveryOutcome.OUTCOME_PROGRESS,
        DeliveryOutcome.PRIMARY_GOAL_OUTCOME,
    }
)
ACCOUNTABLE_DELIVERY_OUTCOMES = frozenset(
    {
        DeliveryOutcome.OUTCOME_PROGRESS,
        DeliveryOutcome.PRIMARY_GOAL_OUTCOME,
    }
)
PROGRESS_DELIVERY_OUTCOMES = ACCOUNTABLE_DELIVERY_OUTCOMES


def qualifies_turn_scoped_blocker_settlement(
    delivery_outcome: Any,
    progress_observation: Mapping[str, Any] | None,
    *,
    work_item_id: str | None = None,
    replan_obligation_id: str | None = None,
) -> bool:
    """Return whether an outcome gap is a typed, attributable blocker receipt.

    ``outcome_gap`` remains outside the progress outcomes: it can settle one
    exact Turn only when the same writeback carries a blocked observation with
    a stable blocker, evidence, and matching Todo or replan-obligation identity.
    """

    if (
        normalize_delivery_outcome(delivery_outcome) != DeliveryOutcome.OUTCOME_GAP
        or not isinstance(progress_observation, Mapping)
        or progress_observation.get("schema_version")
        != PROGRESS_OBSERVATION_SCHEMA_VERSION
        or not isinstance(progress_observation.get("evidence_ids"), list)
        or bool(work_item_id) == bool(replan_obligation_id)
    ):
        return False
    observation = dict(progress_observation)
    normalized_work_item_id = normalize_progress_identifier(
        work_item_id or replan_obligation_id
    )
    if (
        normalized_work_item_id is None
        or observation.get("result_class") != ProgressResultClass.BLOCKED.value
        or normalize_progress_identifier(observation.get("blocker_id")) is None
        or normalize_progress_identifier(observation.get("work_item_id"))
        != normalized_work_item_id
    ):
        return False
    evidence_ids = observation.get("evidence_ids")
    return isinstance(evidence_ids, list) and bool(evidence_ids) and all(
        normalize_progress_identifier(evidence_id) is not None
        for evidence_id in evidence_ids
    )


def qualifies_turn_scoped_settlement(
    delivery_outcome: Any,
    progress_observation: Mapping[str, Any] | None,
    *,
    work_item_id: str | None = None,
    replan_obligation_id: str | None = None,
) -> bool:
    """Return whether one delivery record may satisfy a Turn settlement."""

    normalized = normalize_delivery_outcome(delivery_outcome)
    return normalized in ACCOUNTABLE_DELIVERY_OUTCOMES or (
        qualifies_turn_scoped_blocker_settlement(
            normalized,
            progress_observation,
            work_item_id=work_item_id,
            replan_obligation_id=replan_obligation_id,
        )
    )


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
