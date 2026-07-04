#!/usr/bin/env python3
"""Smoke-test the event-store migration bridge promotion gates."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.runtime.event_store_migration_bridge import (  # noqa: E402
    EVENT_PROJECTION_SOURCE,
    MARKDOWN_ACTIVE_STATE_SOURCE,
    build_event_store_migration_bridge,
)


GOAL_ID = "event-store-migration-bridge-fixture"


def test_fail_closed_before_event_read_path() -> None:
    bridge = build_event_store_migration_bridge(
        goal_id=GOAL_ID,
        event_read_path_ready=False,
        active_state_projection_ready=False,
    )
    assert bridge["schema_version"] == "event_store_migration_bridge_v0", bridge
    assert bridge["source_of_truth"] == MARKDOWN_ACTIVE_STATE_SOURCE, bridge
    assert bridge["candidate_source"] == EVENT_PROJECTION_SOURCE, bridge
    assert bridge["stage"] == "wait_for_event_read_path", bridge
    assert bridge["promotion_allowed"] is False, bridge
    assert bridge["promotion_candidate"] is False, bridge
    assert bridge["dual_read"]["enabled"] is False, bridge
    assert bridge["canary"]["ready"] is False, bridge
    assert bridge["rollback"]["fallback_source"] == MARKDOWN_ACTIVE_STATE_SOURCE, bridge
    assert bridge["missing_for_shadow"] == [
        "event_read_path_ready",
        "active_state_projection_ready",
    ], bridge
    assert "bounded_canary_passed" in bridge["missing_for_promotion"], bridge


def test_shadow_mode_requires_parity_and_rollback() -> None:
    bridge = build_event_store_migration_bridge(
        goal_id=GOAL_ID,
        event_read_path_ready=True,
        active_state_projection_ready=True,
        dual_read_parity_clean=False,
        rollback_plan_recorded=False,
        idempotency_conflicts_clean=False,
        public_boundary_clean=False,
    )
    assert bridge["stage"] == "dual_read_shadow", bridge
    assert bridge["dual_read"]["enabled"] is True, bridge
    assert bridge["dual_read"]["failure_policy"] == "prefer_markdown_and_record_parity_delta", bridge
    assert bridge["promotion_allowed"] is False, bridge
    assert bridge["canary"]["ready"] is False, bridge
    assert bridge["missing_for_canary"] == [
        "dual_read_parity_clean",
        "event_projection_head_matches_store",
        "rollback_plan_recorded",
        "idempotency_conflicts_clean",
        "public_boundary_clean",
    ], bridge


def test_canary_ready_does_not_promote_automatically() -> None:
    bridge = build_event_store_migration_bridge(
        goal_id=GOAL_ID,
        event_read_path_ready=True,
        active_state_projection_ready=True,
        dual_read_parity_clean=True,
        event_projection_head_matches_store=True,
        rollback_plan_recorded=True,
        idempotency_conflicts_clean=True,
        public_boundary_clean=True,
        bounded_canary_passed=False,
        canary_goal_limit=2,
        canary_duration_minutes=45,
        evidence_refs=["event-projection-parity-smoke"],
    )
    assert bridge["stage"] == "bounded_canary", bridge
    assert bridge["promotion_candidate"] is False, bridge
    assert bridge["promotion_allowed"] is False, bridge
    assert bridge["missing_for_canary"] == [], bridge
    assert bridge["missing_for_promotion"] == ["bounded_canary_passed"], bridge
    assert bridge["canary"]["ready"] is True, bridge
    assert bridge["canary"]["scope"] == {
        "max_goals": 2,
        "duration_minutes": 45,
        "write_path": "disabled",
        "read_preference": MARKDOWN_ACTIVE_STATE_SOURCE,
    }, bridge
    assert bridge["evidence_refs"] == ["event-projection-parity-smoke"], bridge


def test_promotion_candidate_still_requires_reviewed_write_path_change() -> None:
    bridge = build_event_store_migration_bridge(
        goal_id=GOAL_ID,
        event_read_path_ready=True,
        active_state_projection_ready=True,
        dual_read_parity_clean=True,
        event_projection_head_matches_store=True,
        rollback_plan_recorded=True,
        idempotency_conflicts_clean=True,
        public_boundary_clean=True,
        bounded_canary_passed=True,
    )
    assert bridge["stage"] == "promotion_candidate", bridge
    assert bridge["promotion_candidate"] is True, bridge
    assert bridge["promotion_allowed"] is False, bridge
    assert bridge["missing_for_promotion"] == [], bridge
    assert "explicit reviewed write-path change" in bridge["next_action"], bridge
    assert bridge["rollback"]["recorded"] is True, bridge
    assert bridge["canary"]["passed"] is True, bridge


def main() -> int:
    test_fail_closed_before_event_read_path()
    test_shadow_mode_requires_parity_and_rollback()
    test_canary_ready_does_not_promote_automatically()
    test_promotion_candidate_still_requires_reviewed_write_path_change()
    print("event-store-migration-bridge-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
