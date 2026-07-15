from __future__ import annotations

from pathlib import Path

import pytest

from loopx.capabilities.explore.result_log import (
    append_explore_result_event,
    build_explore_finding_event,
    build_explore_node_event,
    build_explore_result_projection,
    load_explore_result_events_strict,
    validate_explore_result_event,
)
from loopx.capabilities.explore.source_history_reconcile import (
    reconcile_explore_source_history,
)


GOAL_ID = "source-history-fixture"


def _append(path: Path, *events: dict[str, object]) -> None:
    for event in events:
        append_explore_result_event(path, event)


def _projection_keys(path: Path) -> set[str]:
    events = load_explore_result_events_strict(path, goal_id=GOAL_ID)
    projection = build_explore_result_projection(
        events,
        goal_id=GOAL_ID,
        finding_limit=len(events),
        mermaid_node_limit=max(1, len(events)),
    )
    keys: set[str] = set()
    for table, id_key in (
        ("nodes", "node_id"),
        ("edges", "edge_id"),
        ("findings", "finding_id"),
    ):
        keys.update(f"{GOAL_ID}:{table}:{row[id_key]}" for row in projection[table])
    return keys


def test_event_validation_rejects_unknown_private_fields() -> None:
    event = build_explore_node_event(
        goal_id=GOAL_ID,
        node_id="node_one",
        title="Public fixture node",
    )
    event["raw_transcript"] = "must not cross the boundary"

    with pytest.raises(ValueError, match="not canonical"):
        validate_explore_result_event(event, expected_goal_id=GOAL_ID)


def test_reconcile_recovers_lost_results_and_classifies_stale_parent_edge(
    tmp_path: Path,
) -> None:
    canonical = tmp_path / "canonical.jsonl"
    candidate = tmp_path / "candidate.jsonl"
    parent_old = build_explore_node_event(
        goal_id=GOAL_ID,
        node_id="parent_old",
        title="Earlier parent",
        recorded_at="2026-01-01T00:00:00Z",
    )
    parent_new = build_explore_node_event(
        goal_id=GOAL_ID,
        node_id="parent_new",
        title="Current parent",
        recorded_at="2026-01-01T00:00:01Z",
    )
    child_old = build_explore_node_event(
        goal_id=GOAL_ID,
        node_id="child",
        title="Moved child",
        parent_id="parent_old",
        recorded_at="2026-01-01T00:00:02Z",
    )
    child_new = build_explore_node_event(
        goal_id=GOAL_ID,
        node_id="child",
        title="Moved child",
        parent_id="parent_new",
        recorded_at="2026-01-02T00:00:00Z",
    )
    lost_node = build_explore_node_event(
        goal_id=GOAL_ID,
        node_id="lost_node",
        title="Public-safe lost node",
        parent_id="parent_old",
        recorded_at="2026-01-01T00:00:03Z",
    )
    lost_finding = build_explore_finding_event(
        goal_id=GOAL_ID,
        finding_id="lost_finding",
        node_id="lost_node",
        title="Public-safe lost finding",
        recorded_at="2026-01-01T00:00:04Z",
    )
    _append(canonical, parent_old, parent_new, child_new)
    _append(
        candidate,
        parent_old,
        parent_new,
        child_old,
        lost_node,
        lost_finding,
    )
    registered = _projection_keys(canonical) | _projection_keys(candidate)

    preview = reconcile_explore_source_history(
        canonical_log_path=canonical,
        candidate_log_path=candidate,
        goal_id=GOAL_ID,
        registered_result_keys=registered,
    )

    assert preview["status"] == "would_reconcile_with_remote_orphans"
    assert preview["plan"]["selected_event_count"] == 2
    assert preview["plan"]["raw_history_copied"] is False
    assert preview["projection_reconciliation"]["recovered_lost_history_count"] == 3
    assert preview["projection_reconciliation"]["remaining_registered_result_count"] == 1
    assert preview["classification"]["stale_materialized_parent_edge_count"] == 1
    assert preview["classification"]["remote_deletion_performed"] is False
    assert len(load_explore_result_events_strict(canonical, goal_id=GOAL_ID)) == 3

    executed = reconcile_explore_source_history(
        canonical_log_path=canonical,
        candidate_log_path=candidate,
        goal_id=GOAL_ID,
        registered_result_keys=registered,
        execute=True,
    )

    assert executed["status"] == "reconciled_with_remote_orphans"
    assert executed["writeback"] == {
        "performed": True,
        "requested_event_count": 2,
        "appended_event_count": 2,
        "reused_event_count": 0,
        "readback_verified": True,
    }
    assert len(load_explore_result_events_strict(canonical, goal_id=GOAL_ID)) == 5

    repeated = reconcile_explore_source_history(
        canonical_log_path=canonical,
        candidate_log_path=candidate,
        goal_id=GOAL_ID,
        registered_result_keys=registered,
        execute=True,
    )

    assert repeated["status"] == "already_reconciled_with_remote_orphans"
    assert repeated["plan"]["selected_event_count"] == 0
    assert repeated["writeback"]["performed"] is False
    assert len(load_explore_result_events_strict(canonical, goal_id=GOAL_ID)) == 5
