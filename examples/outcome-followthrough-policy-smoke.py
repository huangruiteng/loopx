#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.outcome_followthrough import build_outcome_followthrough_hint


def assert_none(latest_run: dict[str, object] | None) -> None:
    assert build_outcome_followthrough_hint(latest_run) is None


def assert_hint(
    latest_run: dict[str, object],
    *,
    outcome: str | None,
    turn_kind: str,
) -> None:
    hint = build_outcome_followthrough_hint(latest_run)
    assert hint is not None
    assert hint == {
        "source": "post_handoff_latest_run",
        "required": True,
        "latest_classification": str(latest_run.get("classification") or "").strip(),
        "latest_delivery_outcome": outcome,
        "latest_delivery_turn_kind": turn_kind,
        "obligation": "advance_primary_outcome_or_write_blocker",
        "accepted_resolution_kinds": [
            "product_path_execution",
            "compact_evidence",
            "blocker_writeback",
        ],
        "spend_policy": (
            "do not spend for another contract/preparation-only slice; spend only "
            "after validated product-path evidence, benchmark/case evidence, or a "
            "precise blocker writeback"
        ),
    }


def main() -> None:
    assert_none(None)
    assert_none({})
    assert_none({"delivery_outcome": "primary_goal_outcome", "classification": "done"})
    assert_none(
        {
            "classification": "blocked by owner gate",
            "recommended_action": "cannot proceed until review",
        }
    )

    assert_hint(
        {"delivery_outcome": "surface_only", "classification": "policy smoke"},
        outcome="surface_only",
        turn_kind="contract_only_preparation",
    )
    assert_hint(
        {"delivery_outcome": "outcome_gap", "classification": "needs product evidence"},
        outcome="outcome_gap",
        turn_kind="outcome_gap",
    )
    assert_hint(
        {
            "outcome_followthrough_required": True,
            "classification": "blocked but explicitly requires followthrough",
        },
        outcome=None,
        turn_kind="blocker_writeback",
    )
    assert_hint(
        {"classification": "contract-only preparation"},
        outcome=None,
        turn_kind="contract_only_preparation",
    )
    print("outcome-followthrough-policy-smoke ok")


if __name__ == "__main__":
    main()
