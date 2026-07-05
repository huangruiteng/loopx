#!/usr/bin/env python3
"""Smoke-test Review Packet handoff delivery-contract state transitions."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.handoff.delivery_contract import (  # noqa: E402
    handoff_delivery_contract,
    handoff_delivery_contract_summary,
)


def build_item(*, small_streak: int, outcome_gap_streak: int) -> dict:
    return {
        "project_asset": {
            "execution_profile": {
                "minimum_scale": "implementation",
                "must_include": [
                    "implementation_artifact",
                    "targeted_validation",
                    "state_writeback",
                ],
                "degradation_policy": {
                    "small_scale_streak_threshold": 3,
                },
                "outcome_floor": {
                    "surface_streak_threshold": 2,
                    "must_advance": ["ranker_or_cross_domain_evidence"],
                    "avoid": ["queue_only_update"],
                },
            }
        },
        "handoff_readiness": {
            "post_handoff_small_scale_streak": small_streak,
            "post_handoff_outcome_gap_streak": outcome_gap_streak,
            "post_handoff_recent_runs": [
                {"delivery_batch_scale": "test_only"},
                {"delivery_batch_scale": "single_surface"},
                {"delivery_batch_scale": "implementation"},
            ],
        },
    }


def assert_below_threshold_is_quiet() -> None:
    assert handoff_delivery_contract(build_item(small_streak=2, outcome_gap_streak=1)) is None


def assert_small_scale_contract() -> None:
    contract = handoff_delivery_contract(build_item(small_streak=3, outcome_gap_streak=1))
    assert contract is not None
    assert contract["mode"] == "expand_after_repeated_small_delivery", contract
    assert contract["minimum_scale"] == "implementation", contract
    assert contract["must_include"] == [
        "implementation_artifact",
        "targeted_validation",
        "state_writeback",
    ], contract
    assert contract["recent_scales"] == ["test_only", "single_surface", "implementation"], contract
    summary = handoff_delivery_contract_summary(contract)
    assert summary and "至少 implementation" in summary, summary
    assert "targeted validation、state writeback" in summary, summary
    assert "不 spend" in summary, summary


def assert_outcome_floor_contract() -> None:
    contract = handoff_delivery_contract(build_item(small_streak=1, outcome_gap_streak=2))
    assert contract is not None
    assert contract["mode"] == "expand_after_surface_progress_loop", contract
    assert contract["post_handoff_outcome_gap_streak"] == 2, contract
    assert contract["outcome_gap_streak_threshold"] == 2, contract
    summary = handoff_delivery_contract_summary(contract)
    assert summary and "ranker or cross domain evidence" in summary, summary
    assert "queue only update" in summary, summary
    assert "禁止 isolated test/surface-only propagation" in summary, summary


def main() -> None:
    assert_below_threshold_is_quiet()
    assert_small_scale_contract()
    assert_outcome_floor_contract()


if __name__ == "__main__":
    main()
