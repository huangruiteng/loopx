from __future__ import annotations

import pytest

from loopx.control_plane.runtime.event_store_migration_bridge import (
    EVENT_PROJECTION_SOURCE,
    MARKDOWN_ACTIVE_STATE_SOURCE,
    build_event_store_migration_bridge,
)


GOAL_ID = "event-store-migration-bridge-fixture"


def test_bridge_fails_closed_before_event_read_path() -> None:
    bridge = build_event_store_migration_bridge(
        goal_id=GOAL_ID,
        event_read_path_ready=False,
        active_state_projection_ready=False,
    )

    assert bridge["schema_version"] == "event_store_migration_bridge_v0"
    assert bridge["source_of_truth"] == MARKDOWN_ACTIVE_STATE_SOURCE
    assert bridge["candidate_source"] == EVENT_PROJECTION_SOURCE
    assert bridge["stage"] == "wait_for_event_read_path"
    assert bridge["promotion_allowed"] is False
    assert bridge["promotion_candidate"] is False
    assert bridge["dual_read"]["enabled"] is False
    assert bridge["canary"]["ready"] is False
    assert bridge["rollback"]["fallback_source"] == MARKDOWN_ACTIVE_STATE_SOURCE
    assert bridge["missing_for_shadow"] == [
        "event_read_path_ready",
        "active_state_projection_ready",
    ]
    assert "bounded_canary_passed" in bridge["missing_for_promotion"]


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

    assert bridge["stage"] == "dual_read_shadow"
    assert bridge["dual_read"]["enabled"] is True
    assert bridge["dual_read"]["failure_policy"] == (
        "prefer_markdown_and_record_parity_delta"
    )
    assert bridge["promotion_allowed"] is False
    assert bridge["canary"]["ready"] is False
    assert bridge["missing_for_canary"] == [
        "dual_read_parity_clean",
        "event_projection_head_matches_store",
        "rollback_plan_recorded",
        "idempotency_conflicts_clean",
        "public_boundary_clean",
    ]


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

    assert bridge["stage"] == "bounded_canary"
    assert bridge["promotion_candidate"] is False
    assert bridge["promotion_allowed"] is False
    assert bridge["missing_for_canary"] == []
    assert bridge["missing_for_promotion"] == ["bounded_canary_passed"]
    assert bridge["canary"]["ready"] is True
    assert bridge["canary"]["scope"] == {
        "max_goals": 2,
        "duration_minutes": 45,
        "write_path": "disabled",
        "read_preference": MARKDOWN_ACTIVE_STATE_SOURCE,
    }
    assert bridge["evidence_refs"] == ["event-projection-parity-smoke"]


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

    assert bridge["stage"] == "promotion_candidate"
    assert bridge["promotion_candidate"] is True
    assert bridge["promotion_allowed"] is False
    assert bridge["missing_for_promotion"] == []
    assert "explicit reviewed write-path change" in bridge["next_action"]
    assert bridge["rollback"]["recorded"] is True
    assert bridge["canary"]["passed"] is True


@pytest.mark.parametrize("goal_id", ["", "  "])
def test_bridge_requires_a_goal_id(goal_id: str) -> None:
    with pytest.raises(ValueError, match="goal_id is required"):
        build_event_store_migration_bridge(
            goal_id=goal_id,
            event_read_path_ready=False,
        )


def test_bridge_normalizes_bounded_canary_inputs() -> None:
    bridge = build_event_store_migration_bridge(
        goal_id="  fixture   goal  ",
        event_read_path_ready=False,
        canary_goal_limit=0,
        canary_duration_minutes=0,
        evidence_refs=[" parity   packet ", "", "  "],
    )

    assert bridge["goal_id"] == "fixture goal"
    assert bridge["canary"]["scope"]["max_goals"] == 1
    assert bridge["canary"]["scope"]["duration_minutes"] == 1
    assert bridge["evidence_refs"] == ["parity packet"]
