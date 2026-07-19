#!/usr/bin/env python3
"""Smoke-check compact path deltas survive the goal-vision read path."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.control_plane.goals.goal_frontier import (  # noqa: E402
    latest_agent_vision_from_runs,
)
from loopx.control_plane.goals.goal_vision import (  # noqa: E402
    compact_goal_vision_packet,
    normalize_goal_vision_packet,
)
from loopx.control_plane.runtime.shared_runtime_refresh_projection import (  # noqa: E402
    build_shared_runtime_projection,
)


GOAL_ID = "fixture-goal"
AGENT_ID = "fixture-agent"


def packet() -> dict[str, object]:
    return {
        "agent_id": AGENT_ID,
        "state": "vision_drift_detected",
        "vision_patch": {
            "vision_summary": "Route one bounded successor from verified evidence.",
            "acceptance_summary": "The successor falsifies or confirms the new path.",
            "replan_trigger_summary": "The prior monitor-only path made no progress.",
        },
        "path_delta": {
            "outcome": "replan",
            "prior_assumption": "The monitor lane would produce acceptance evidence.",
            "observed_reality": "Two bounded polls produced no material transition.",
            "retained": ["Keep the verified monitor target."],
            "changed": ["Create one runnable advancement successor."],
            "stopped": ["Stop treating future polling as completion evidence."],
            "unresolved_questions": ["Can the successor falsify the new path?"],
            "reentry_condition": "Resume waiting after successor evidence lands.",
            "evidence_refs": ["evidence:monitor-poll-02", "todo:successor-01"],
        },
    }


def main() -> int:
    normalized = normalize_goal_vision_packet(
        packet(), goal_id=GOAL_ID, agent_id=AGENT_ID
    )
    path_delta = normalized["path_delta"]
    assert path_delta["schema_version"] == "goal_path_delta_v0", path_delta
    assert path_delta["outcome"] == "replan", path_delta
    assert normalized["vision_budget"]["total_usage"] <= 1200, normalized

    compact = compact_goal_vision_packet(normalized)
    assert compact is not None, normalized
    assert compact["path_delta"] == path_delta, compact

    record = {
        "generated_at": "2026-07-20T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "autonomous_replan_recorded",
        "agent_id": AGENT_ID,
        "agent_vision": normalized,
        "state": {"sha256_16": "0123456789abcdef", "frontmatter": {}},
    }
    shared, _ = build_shared_runtime_projection(record=record)
    assert shared["agent_vision"]["path_delta"] == path_delta, shared

    latest = latest_agent_vision_from_runs(
        [shared], goal_id=GOAL_ID, agent_id=AGENT_ID
    )
    assert latest is not None, shared
    assert latest["path_delta"] == path_delta, latest

    invalid = packet()
    invalid["path_delta"] = {"outcome": "replan"}
    try:
        normalize_goal_vision_packet(invalid, goal_id=GOAL_ID, agent_id=AGENT_ID)
    except ValueError as exc:
        assert "requires prior_assumption and observed_reality" in str(exc), exc
    else:
        raise AssertionError("incomplete path delta should fail")

    missing_disposition = packet()
    missing_disposition["path_delta"] = {
        "outcome": "wait",
        "prior_assumption": "A dependency would become available.",
        "observed_reality": "The dependency remains unavailable.",
    }
    try:
        normalize_goal_vision_packet(
            missing_disposition, goal_id=GOAL_ID, agent_id=AGENT_ID
        )
    except ValueError as exc:
        assert "requires at least one retained, changed, or stopped item" in str(exc), exc
    else:
        raise AssertionError("path delta without a disposition should fail")

    over_item_limit = packet()
    over_item_limit["path_delta"]["retained"] = ["item"] * 4
    try:
        normalize_goal_vision_packet(
            over_item_limit, goal_id=GOAL_ID, agent_id=AGENT_ID
        )
    except ValueError as exc:
        assert "path_delta.retained has 4 items; limit is 3" in str(exc), exc
    else:
        raise AssertionError("over-item path delta should fail")

    print("goal-vision-path-delta-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
