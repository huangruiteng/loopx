#!/usr/bin/env python3
"""Smoke-test the fail-closed event-store promotion boundary."""

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


def main() -> int:
    bridge = build_event_store_migration_bridge(
        goal_id="event-store-migration-bridge-smoke",
        event_read_path_ready=True,
        active_state_projection_ready=True,
        dual_read_parity_clean=True,
        event_projection_head_matches_store=True,
        rollback_plan_recorded=True,
        idempotency_conflicts_clean=True,
        public_boundary_clean=True,
        bounded_canary_passed=True,
    )
    assert bridge["source_of_truth"] == MARKDOWN_ACTIVE_STATE_SOURCE, bridge
    assert bridge["candidate_source"] == EVENT_PROJECTION_SOURCE, bridge
    assert bridge["stage"] == "promotion_candidate", bridge
    assert bridge["promotion_candidate"] is True, bridge
    assert bridge["promotion_allowed"] is False, bridge
    assert bridge["rollback"]["fallback_source"] == MARKDOWN_ACTIVE_STATE_SOURCE, bridge
    print("event-store-migration-bridge-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
