"""Writer rejection and tolerant historical readback use the same TS rules."""
from copy import deepcopy

import pytest

from loopx.control_plane.work_items.delivery_history import require_consistent_delivery_claim
from loopx.history import write_reserved_run_artifacts
from loopx.state_refresh import refresh_state_run
from loopx.status import compact_post_handoff_run


@pytest.mark.parametrize("record", [
    {"delivery_outcome": "outcome_progress", "delivery_turn_kind": "contract_only_preparation"},
    {"delivery_outcome": "primary_goal_outcome", "delivery_turn_kind": "blocker_writeback"},
    {"delivery_outcome": "primary_goal_outcome", "outcome_followthrough_required": True},
])
def test_historical_conflict_is_visible_and_new_write_has_no_artifacts(tmp_path, record):
    before = deepcopy(record)
    compact = compact_post_handoff_run(record)
    assert compact["delivery_outcome"] == "unknown"
    assert compact["delivery_claim_conflicts"]
    with pytest.raises(ValueError, match="contradictory delivery claim"):
        write_reserved_run_artifacts(runs_dir=tmp_path, generated_at="2026-09-09T00:00:00Z",
            record=record, index_record={}, payload={}, render_markdown=lambda _: "unused")
    assert list(tmp_path.iterdir()) == []
    assert record == before


def test_refresh_rejects_primary_blocker_before_loading_registry_or_mutating_state(tmp_path):
    with pytest.raises(ValueError, match="primary_outcome_with_blocker"):
        refresh_state_run(registry_path=tmp_path / "absent-registry.json", goal_id="delivery",
            runtime_root_override=None, project=None, state_file=None, recommended_action=None,
            dry_run=False,
            classification="synthetic_delivery", delivery_outcome="primary_goal_outcome",
            todo_id="todo_delivery", progress_observation={
                "schema_version": "typed_progress_observation_v0", "result_class": "blocked",
                "work_item_id": "todo_delivery", "blocker_id": "blocker-a", "evidence_ids": ["evidence-a"],
            })
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("overrides, error", [
    ({"delivery_outcome": "unsupported_outcome", "progress_observation": {"schema_version": "bad"}},
     "delivery_outcome must be one of"),
    ({"delivery_batch_scale": "unsupported_scale", "delivery_outcome": "unsupported_outcome"},
     "delivery_batch_scale must be one of"),
    ({"agent_lane": "lane-a", "delivery_outcome": "unsupported_outcome"},
     "--agent-lane requires --agent-id"),
    ({"delivery_outcome": "primary_goal_outcome", "progress_observation": {"schema_version": "bad"}},
     "progress observation must use"),
])
def test_refresh_validates_fields_in_order_before_cross_field_rules_or_io(tmp_path, dry_run, overrides, error):
    # An absent registry also proves that malformed input is rejected before
    # opening the store or creating its write lock, in both execution modes.
    with pytest.raises(ValueError, match=error):
        refresh_state_run(
            registry_path=tmp_path / "absent-registry.json", runtime_root_override=None,
            goal_id="delivery", project=None, state_file=None, recommended_action=None,
            classification="synthetic_delivery", dry_run=dry_run, **overrides,
        )
    assert list(tmp_path.iterdir()) == []


def test_valid_partial_progress_and_unspecified_delivery_remain_legal():
    for record in ({}, {"delivery_outcome": "outcome_progress", "delivery_turn_kind": "product_path_execution"},
        {"delivery_outcome": "outcome_gap", "delivery_turn_kind": "blocker_writeback"}):
        require_consistent_delivery_claim(record)
