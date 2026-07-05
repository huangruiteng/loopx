#!/usr/bin/env python3
"""Smoke-test runtime freshness warnings shared by quota and review packets."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.runtime.decision_freshness import (  # noqa: E402
    DECISION_FRESHNESS_WARNING_ITEM_LIMIT,
    decision_freshness_warning,
)
from loopx.control_plane.runtime.promotion_readiness import (  # noqa: E402
    promotion_readiness_warning,
)
from loopx.review_packet import decision_freshness_packet_lines  # noqa: E402


TARGET_GOAL = "loopx-meta"
OTHER_GOAL = "other-goal"


def decision_item(index: int, *, goal_id: str, requires_rebase: bool = True) -> dict:
    return {
        "goal_id": goal_id,
        "decision_kind": f"human_reward_{index}",
        "freshness_state": "stale_rebase_required" if requires_rebase else "fresh",
        "decision_at": f"2026-01-0{index}T00:00:00+00:00",
        "classification": "human_reward",
        "age_days": 10 + index,
        "newer_event_count_7d": index,
        "requires_decision_point_rebase": requires_rebase,
        "reason": "decision older than freshness window; rebase at decision point",
    }


def assert_decision_freshness_warning() -> None:
    status_payload = {
        "decision_freshness_summary": {
            "source": "run_history",
            "window_days": 7,
            "summary": {
                "rebase_required_count": 6,
                "stale_count": 4,
            },
            "items": [
                decision_item(1, goal_id=TARGET_GOAL),
                decision_item(2, goal_id=OTHER_GOAL),
                decision_item(3, goal_id=TARGET_GOAL, requires_rebase=False),
                decision_item(4, goal_id=TARGET_GOAL),
                decision_item(5, goal_id=TARGET_GOAL),
                decision_item(6, goal_id=TARGET_GOAL),
            ],
        }
    }

    warning = decision_freshness_warning(status_payload, goal_id=TARGET_GOAL)
    assert warning is not None, warning
    assert warning["source"] == "run_history", warning
    assert warning["window_days"] == 7, warning
    assert warning["rebase_required_count"] == 4, warning
    assert warning["global_rebase_required_count"] == 6, warning
    assert warning["global_stale_count"] == 4, warning
    assert len(warning["items"]) == DECISION_FRESHNESS_WARNING_ITEM_LIMIT, warning
    assert {item["goal_id"] for item in warning["items"]} == {TARGET_GOAL}, warning
    assert [item["decision_kind"] for item in warning["items"]] == [
        "human_reward_1",
        "human_reward_4",
        "human_reward_5",
    ], warning
    assert "rebase required" in warning["message"], warning

    packet_warning = decision_freshness_warning(
        status_payload,
        goal_id=TARGET_GOAL,
        message="旧 reward/gate 决策复用前需重新对齐。",
    )
    packet_lines = decision_freshness_packet_lines(packet_warning)
    assert "【决策 freshness 警告】" in "\n".join(packet_lines), packet_lines
    assert "旧 reward/gate 决策复用前需重新对齐。" in "\n".join(packet_lines), packet_lines

    assert decision_freshness_warning(status_payload, goal_id="fresh-only-goal") is None
    assert decision_freshness_warning({"decision_freshness_summary": {"items": []}}, goal_id=TARGET_GOAL) is None


def assert_promotion_readiness_warning() -> None:
    fresh_status = {
        "promotion_readiness_summary": {
            "available": True,
            "source": "run_history",
            "freshness_status": "fresh",
            "requires_readiness_run": False,
            "freshness_window_hours": 24,
        }
    }
    assert promotion_readiness_warning(fresh_status) is None

    stale_status = {
        "promotion_readiness_summary": {
            "available": True,
            "source": "run_history_full_scan",
            "freshness_status": "stale",
            "requires_readiness_run": True,
            "freshness_window_hours": 24,
            "age_hours": 31.5,
            "sample_run_count": 2,
            "goal_id": TARGET_GOAL,
            "generated_at": "2026-01-01T00:00:00+00:00",
            "classification": "canary_promotion_readiness_smoke_group",
            "json_exists": True,
            "markdown_exists": True,
            "reason": "latest canary promotion readiness run is stale",
        }
    }
    warning = promotion_readiness_warning(stale_status)
    assert warning is not None, warning
    assert warning["source"] == "run_history_full_scan", warning
    assert warning["freshness_status"] == "stale", warning
    assert warning["requires_readiness_run"] is True, warning
    assert warning["goal_id"] == TARGET_GOAL, warning
    assert warning["json_exists"] is True, warning
    assert "promotion readiness evidence" in warning["message"], warning

    missing_status = {
        "promotion_readiness_summary": {
            "available": False,
            "source": "run_history",
            "freshness_status": "unknown",
            "requires_readiness_run": True,
            "reason": "no canary promotion readiness run found in sampled history",
        }
    }
    missing_warning = promotion_readiness_warning(missing_status)
    assert missing_warning is not None, missing_warning
    assert missing_warning["available"] is False, missing_warning
    assert missing_warning["reason"] == "no canary promotion readiness run found in sampled history"


def main() -> int:
    assert_decision_freshness_warning()
    assert_promotion_readiness_warning()
    print("runtime-freshness-warning-readmodel-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
