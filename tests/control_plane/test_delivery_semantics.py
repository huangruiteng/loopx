"""Narrative edits cannot grant progress, blockers, or delivery obligations."""

from copy import deepcopy

import pytest

from loopx.control_plane.work_items.delivery_history import project_delivery_history
from loopx.control_plane.work_items.work_lane_context import outcome_followthrough_hint
from loopx.status import compact_post_handoff_run


# Test adapters retain the independently characterized assertions after retiring
# the single-field production readers. Production projects the selected batch.
def delivery_turn_kind_for_run(run):
    return project_delivery_history([run])["runs"][0]["delivery_turn_kind"]


def delivery_batch_scale_for_run(run):
    return project_delivery_history([run])["runs"][0]["delivery_batch_scale"]


def delivery_outcome_for_run(run, profile=None):
    return project_delivery_history([run], outcome_floor_configured=bool(profile))["runs"][0]["delivery_outcome"]


def outcome_gap_streak(runs, profile=None):
    return project_delivery_history(runs, outcome_floor_configured=bool(profile))["outcome_gap_streak"]


def small_delivery_batch_scale_streak(runs):
    return project_delivery_history(runs)["small_scale_streak"]


def build_outcome_followthrough_hint(run):
    return outcome_followthrough_hint({"handoff_readiness": {"post_handoff_latest_run": run}})


PROFILE = {
    "outcome_floor": {
        "outcome_markers": ["merged", "validated"],
        "surface_only_hints": ["contract", "protocol"],
    }
}
NARRATIVES = (
    "",
    "unblocked after dependency update",
    "implemented network protocol parser",
    "contract validated and merged",
    "owner_handoff_consumer_test",
    "cross_benchmark_implementation_batch",
    "not blocked; no preparation needed",
    "网络协议实现完成，阻塞已解除",
)


@pytest.mark.parametrize("narrative", NARRATIVES)
@pytest.mark.parametrize("with_evidence", (False, True))
def test_untyped_history_has_no_delivery_authority(narrative: str, with_evidence: bool) -> None:
    run = {
        "classification": narrative,
        "health_check": narrative,
        "recommended_action": narrative,
    }
    if with_evidence:
        # Presence alone is not a validated result.
        run.update({"compact_evidence": {"summary": narrative}, "case_result": {"summary": narrative}})
    original = deepcopy(run)
    assert delivery_turn_kind_for_run(run) == "unknown"
    assert delivery_batch_scale_for_run(run) == "unknown"
    assert delivery_outcome_for_run(run, PROFILE) == "unknown"
    assert build_outcome_followthrough_hint(run) is None
    compact = compact_post_handoff_run(run, PROFILE)
    assert compact["classification"] == narrative
    assert compact["delivery_turn_kind"] == "unknown"
    assert build_outcome_followthrough_hint(compact) is None
    assert outcome_gap_streak([run] * 4, PROFILE) == 0
    assert small_delivery_batch_scale_streak([run] * 4) == 0
    assert run == original


@pytest.mark.parametrize("narrative", NARRATIVES)
@pytest.mark.parametrize(("outcome", "kind", "required"), (
    ("surface_only", "contract_only_preparation", True),
    ("outcome_gap", "outcome_gap", True),
    ("outcome_progress", "compact_evidence", False),
    ("primary_goal_outcome", "product_path_execution", False),
))
def test_explicit_outcomes_ignore_narrative(
    narrative: str, outcome: str, kind: str, required: bool,
) -> None:
    run = {
        "classification": narrative,
        "health_check": narrative,
        "recommended_action": narrative,
        "delivery_outcome": outcome,
        "delivery_batch_scale": "implementation",
    }
    assert delivery_turn_kind_for_run(run) == kind
    assert delivery_outcome_for_run(run, PROFILE) == outcome
    assert delivery_batch_scale_for_run(run) == "implementation"
    hint = build_outcome_followthrough_hint(run)
    assert (hint is not None) is required
    if hint:
        assert hint["required"] is True
        assert hint["latest_delivery_turn_kind"] == kind


def test_invalid_explicit_fields_are_unknown_without_narrative_recovery() -> None:
    run = {
        "classification": "contract validated implementation batch blocked",
        "delivery_outcome": "future_outcome",
        "delivery_turn_kind": "future_kind",
        "delivery_batch_scale": "future_scale",
    }
    assert delivery_outcome_for_run(run, PROFILE) == "unknown"
    assert delivery_turn_kind_for_run(run) == "unknown"
    assert delivery_batch_scale_for_run(run) == "unknown"
    assert build_outcome_followthrough_hint(run) is None


def test_unknown_history_breaks_consecutive_evidence_streaks() -> None:
    gap = {"delivery_outcome": "surface_only", "delivery_batch_scale": "test_only"}
    unknown = {"classification": "protocol_smoke"}
    assert outcome_gap_streak([gap, gap], PROFILE) == 2
    assert outcome_gap_streak([gap, unknown, gap], PROFILE) == 1
    assert small_delivery_batch_scale_streak([gap, gap]) == 2
    assert small_delivery_batch_scale_streak([gap, unknown, gap]) == 1


def test_scoped_blocker_observation_survives_compaction() -> None:
    run = {
        "classification": "ordinary observation",
        "delivery_outcome": "outcome_gap",
        "todo_id": "todo-a",
        "progress_observation": {
            "schema_version": "typed_progress_observation_v0",
            "result_class": "blocked",
            "work_item_id": "todo-a",
            "blocker_id": "blocker-a",
            "evidence_ids": ["evidence-a"],
        },
    }
    assert delivery_turn_kind_for_run(run) == "blocker_writeback"
    compact = compact_post_handoff_run(run, PROFILE)
    assert compact["delivery_turn_kind"] == "blocker_writeback"
    assert build_outcome_followthrough_hint(compact) is None
    for patch in ({"work_item_id": "other"}, {"evidence_ids": []}, {"blocker_id": ""}):
        malformed = deepcopy(run)
        malformed["progress_observation"].update(patch)
        assert delivery_turn_kind_for_run(malformed) == "outcome_gap"
        assert build_outcome_followthrough_hint(malformed)["required"] is True


def test_explicit_legacy_blocker_and_explicit_obligation_remain_readable() -> None:
    run = {"delivery_turn_kind": "blocker_writeback", "delivery_outcome": "outcome_gap"}
    assert build_outcome_followthrough_hint(run) is None
    run["outcome_followthrough_required"] = True
    assert build_outcome_followthrough_hint(run)["required"] is True


@pytest.mark.parametrize("required", (False, None, 0, 1, "true", [], {}))
def test_followthrough_requires_literal_true_not_truthy_metadata(required) -> None:
    assert build_outcome_followthrough_hint({"outcome_followthrough_required": required}) is None


def test_contradictory_primary_claim_is_diagnostic_and_unknown_kind_does_not_recover() -> None:
    contradictory = {
        "delivery_outcome": "primary_goal_outcome", "outcome_followthrough_required": True,
    }
    assert build_outcome_followthrough_hint(contradictory) is None
    compact = compact_post_handoff_run(contradictory)
    assert compact["delivery_outcome"] == "unknown"
    assert compact["delivery_claim_conflicts"] == ["primary_outcome_with_followthrough"]
    assert delivery_turn_kind_for_run({
        "delivery_outcome": "primary_goal_outcome", "delivery_turn_kind": "future_kind",
    }) == "unknown"


@pytest.mark.parametrize("scale", ("single_segment", "bounded_segment", " single_surface "))
def test_legacy_scale_aliases_keep_small_batch_meaning(scale) -> None:
    run = {"delivery_batch_scale": scale, "delivery_outcome": "surface_only"}
    assert delivery_batch_scale_for_run(run) == "single_surface"
    assert small_delivery_batch_scale_streak([run, run]) == 2
    assert outcome_gap_streak([run, run], None) == 0


@pytest.mark.parametrize("binding", (
    {"replan_obligation_id": "replan-a"},
    {"todo_id": "todo-a", "replan_obligation_id": "replan-a"},
    {},
))
def test_blocker_binding_is_exactly_one_todo_or_replan(binding) -> None:
    run = {**binding, "delivery_outcome": "outcome_gap", "progress_observation": {
        "schema_version": "typed_progress_observation_v0", "result_class": "blocked",
        "work_item_id": "replan-a", "blocker_id": "blocker-a", "evidence_ids": ["evidence-a"],
    }}
    expected = "blocker_writeback" if len(binding) == 1 else "outcome_gap"
    assert delivery_turn_kind_for_run(run) == expected


@pytest.mark.parametrize("invalid_id", ("bad id", " ", "x" * 129))
def test_invalid_identifier_pair_cannot_prove_blocker_attribution(invalid_id) -> None:
    from loopx.control_plane.work_items.delivery_outcome import qualifies_turn_scoped_blocker_settlement

    observation = {"schema_version": "typed_progress_observation_v0", "result_class": "blocked",
                   "work_item_id": invalid_id, "blocker_id": "blocker-a", "evidence_ids": ["evidence-a"]}
    assert not qualifies_turn_scoped_blocker_settlement("outcome_gap", observation, work_item_id=invalid_id)
    run = {"delivery_outcome": "outcome_gap", "todo_id": invalid_id, "progress_observation": observation}
    assert delivery_turn_kind_for_run(run) == "outcome_gap"
    assert build_outcome_followthrough_hint(run)["required"] is True
