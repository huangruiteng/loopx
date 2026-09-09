#!/usr/bin/env python3
"""Smoke-test structured delivery_turn_kind enum handling."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.delivery_history import project_delivery_history  # noqa: E402
from loopx.control_plane.work_items.delivery_outcome import (  # noqa: E402
    DELIVERY_TURN_KIND_CHOICES,
    DeliveryOutcome,
    DeliveryTurnKind,
    normalize_delivery_turn_kind,
    require_delivery_turn_kind,
)
from loopx.status import compact_post_handoff_run  # noqa: E402


def assert_enum_sets() -> None:
    assert DELIVERY_TURN_KIND_CHOICES == (
        "contract_only_preparation",
        "compact_evidence",
        "blocker_writeback",
        "product_path_execution",
        "outcome_gap",
        "unknown",
    )
    assert require_delivery_turn_kind("compact_evidence") == DeliveryTurnKind.COMPACT_EVIDENCE
    assert normalize_delivery_turn_kind("contract_v0_delivered") is None
    try:
        require_delivery_turn_kind("contract_v0_delivered")
    except ValueError as exc:
        assert "delivery_turn_kind must be one of:" in str(exc)
    else:
        raise AssertionError("invalid delivery turn kind accepted")


def assert_invalid_explicit_kind_does_not_fallback_to_classification() -> None:
    run = {
        "classification": "runner_contract_v0_delivered",
        "delivery_outcome": DeliveryOutcome.SURFACE_ONLY.value,
        "delivery_turn_kind": "contract_v0_delivered",
    }
    assert project_delivery_history([run])["runs"][0]["delivery_turn_kind"] == DeliveryTurnKind.UNKNOWN.value
    assert compact_post_handoff_run(run)["delivery_turn_kind"] == DeliveryTurnKind.UNKNOWN.value


def assert_inference_still_works_when_kind_is_absent() -> None:
    contract_run = {
        "classification": "runner_contract_v0_delivered",
        "delivery_outcome": DeliveryOutcome.SURFACE_ONLY.value,
    }
    assert (
        project_delivery_history([contract_run])["runs"][0]["delivery_turn_kind"]
        == DeliveryTurnKind.CONTRACT_ONLY_PREPARATION.value
    )
    assert (
        project_delivery_history([{"delivery_outcome": DeliveryOutcome.PRIMARY_GOAL_OUTCOME.value}])["runs"][0]["delivery_turn_kind"]
        == DeliveryTurnKind.PRODUCT_PATH_EXECUTION.value
    )


def main() -> int:
    assert_enum_sets()
    assert_invalid_explicit_kind_does_not_fallback_to_classification()
    assert_inference_still_works_when_kind_is_absent()
    print("delivery turn kind enum smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
