#!/usr/bin/env python3
"""The public status batch preserves typed streaks and unknown boundaries."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from loopx.status import project_post_handoff_history  # noqa: E402


def main() -> None:
    profile = {"outcome_floor": {"outcome_markers": ["validated"]}}
    runs = [
        {"delivery_outcome": "surface_only", "delivery_batch_scale": "single_segment"},
        {"classification": "contract validated implementation"},
        {"delivery_outcome": "outcome_gap", "delivery_batch_scale": "test_only"},
    ]
    result = project_post_handoff_history(runs, profile)
    assert result["post_handoff_small_scale_streak"] == 1
    assert result["post_handoff_outcome_gap_streak"] == 1
    assert result["post_handoff_latest_run"]["delivery_batch_scale"] == "single_surface"
    assert result["post_handoff_recent_runs"][1]["delivery_outcome"] == "unknown"
    no_floor = project_post_handoff_history([{}])
    assert "post_handoff_outcome_gap_streak" not in no_floor
    assert "delivery_outcome" not in no_floor["post_handoff_latest_run"]
    assert no_floor["post_handoff_latest_run"]["delivery_turn_kind"] == "unknown"
    print("delivery-signals-readmodel-smoke ok")


if __name__ == "__main__":
    main()
