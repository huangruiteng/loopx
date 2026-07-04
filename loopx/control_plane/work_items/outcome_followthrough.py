from __future__ import annotations

from typing import Any

from .delivery_outcome import (
    DeliveryOutcome,
    DeliveryTurnKind,
    FOLLOWTHROUGH_REQUIRED_DELIVERY_OUTCOMES,
    delivery_turn_kind_for_run,
    normalize_delivery_outcome,
)


def build_outcome_followthrough_hint(
    latest_run: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Build the follow-through obligation for a post-handoff latest run.

    The helper intentionally preserves the quota payload shape. It only moves
    the policy decision out of the quota builder so future rule changes can be
    tested without touching the broader status/quota extraction path.
    """

    if not isinstance(latest_run, dict) or not latest_run:
        return None

    explicit_required = latest_run.get("outcome_followthrough_required") is True
    delivery_outcome = normalize_delivery_outcome(latest_run.get("delivery_outcome"))
    delivery_turn_kind = delivery_turn_kind_for_run(
        latest_run,
        delivery_outcome=delivery_outcome,
    )
    if delivery_outcome == DeliveryOutcome.PRIMARY_GOAL_OUTCOME:
        return None
    if (
        not explicit_required
        and delivery_turn_kind == DeliveryTurnKind.BLOCKER_WRITEBACK.value
    ):
        return None

    classification = str(latest_run.get("classification") or "").strip()
    kind_requires_followthrough = (
        delivery_turn_kind == DeliveryTurnKind.CONTRACT_ONLY_PREPARATION.value
    )
    if (
        not explicit_required
        and delivery_outcome not in FOLLOWTHROUGH_REQUIRED_DELIVERY_OUTCOMES
        and not kind_requires_followthrough
    ):
        return None

    return {
        "source": "post_handoff_latest_run",
        "required": True,
        "latest_classification": classification,
        "latest_delivery_outcome": delivery_outcome.value if delivery_outcome else None,
        "latest_delivery_turn_kind": delivery_turn_kind,
        "obligation": "advance_primary_outcome_or_write_blocker",
        "accepted_resolution_kinds": [
            DeliveryTurnKind.PRODUCT_PATH_EXECUTION.value,
            DeliveryTurnKind.COMPACT_EVIDENCE.value,
            DeliveryTurnKind.BLOCKER_WRITEBACK.value,
        ],
        "spend_policy": (
            "do not spend for another contract/preparation-only slice; spend only "
            "after validated product-path evidence, benchmark/case evidence, or a "
            "precise blocker writeback"
        ),
    }
