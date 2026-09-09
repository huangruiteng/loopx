#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.work_lane_context import outcome_followthrough_hint  # noqa: E402


def build_outcome_followthrough_hint(run):
    return outcome_followthrough_hint({"handoff_readiness": {"post_handoff_latest_run": run}})


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
    assert isinstance(hint["spend_policy"], str) and hint["spend_policy"].strip()
    assert {key: value for key, value in hint.items() if key != "spend_policy"} == {
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
        turn_kind="unknown",
    )
    assert_hint(
        {"classification": "done", "delivery_turn_kind": "contract_only_preparation"},
        outcome=None,
        turn_kind="contract_only_preparation",
    )
    # Diagnostic prose must not create or suppress a machine obligation.
    assert_none({"classification": "contract-only preparation"})
    assert_none({"classification": "needs product evidence"})
    assert_none({"delivery_turn_kind": "blocker_writeback"})
    assert_hint(
        {"delivery_outcome": "surface_only", "classification": "done"},
        outcome="surface_only",
        turn_kind="contract_only_preparation",
    )
    print("outcome-followthrough-policy-smoke ok")


if __name__ == "__main__":
    main()
