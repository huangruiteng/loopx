#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import delivery_signals as delivery_signal_read_model  # noqa: E402


PROFILE = {
    "outcome_floor": {
        "outcome_markers": ["merged", "validated"],
        "surface_only_hints": ["doc_only", "contract"],
    }
}


def _projection_scale(run: dict[str, object]) -> str:
    return delivery_signal_read_model.delivery_batch_scale_for_run(
        run,
        test_only_hints=status_module.DELIVERY_BATCH_SCALE_TEST_ONLY_CLASSIFICATION_HINTS,
        multi_surface_hints=status_module.DELIVERY_BATCH_SCALE_MULTI_SURFACE_CLASSIFICATION_HINTS,
        implementation_hints=status_module.DELIVERY_BATCH_SCALE_IMPLEMENTATION_CLASSIFICATION_HINTS,
    )


def _projection_outcome(run: dict[str, object], profile: dict[str, object] | None = None) -> str:
    return delivery_signal_read_model.delivery_outcome_for_run(
        run,
        profile,
        execution_profile_outcome_floor=status_module.execution_profile_outcome_floor,
    )


def _projection_outcome_floor_configured(profile: dict[str, object] | None) -> bool:
    return delivery_signal_read_model.outcome_floor_configured(
        profile,
        execution_profile_outcome_floor=status_module.execution_profile_outcome_floor,
    )


def _projection_outcome_gap_streak(runs: list[dict[str, object]], profile: dict[str, object] | None) -> int:
    return delivery_signal_read_model.outcome_gap_streak(
        runs,
        profile,
        delivery_outcome_for_run=_projection_outcome,
        outcome_floor_configured=_projection_outcome_floor_configured,
    )


def _projection_small_scale_streak(runs: list[dict[str, object]]) -> int:
    return delivery_signal_read_model.small_delivery_batch_scale_streak(
        runs,
        delivery_batch_scale_for_run=_projection_scale,
        small_delivery_batch_scales=status_module.SMALL_DELIVERY_BATCH_SCALES,
    )


def assert_delivery_signal_wrapper_parity() -> None:
    scale_cases = [
        {"delivery_batch_scale": "multi_surface", "classification": "ignored_smoke"},
        {"delivery_batch_scale": "future_scale", "classification": "ignored_smoke"},
        {"classification": "owner_handoff_consumer_test"},
        {"classification": "delivery_ranker_readiness_batch"},
        {"classification": "feedback_reranker_adapter_slice"},
        {"classification": "single_note"},
        {},
    ]
    for run in scale_cases:
        assert status_module.delivery_batch_scale_for_run(run) == _projection_scale(run), run

    outcome_cases = [
        ({"delivery_outcome": "outcome_progress", "classification": "ignored"}, PROFILE),
        ({"delivery_outcome": "future_outcome", "classification": "ignored"}, PROFILE),
        ({"classification": "adapter_validated"}, PROFILE),
        ({"classification": "doc_only_contract"}, PROFILE),
        ({"classification": "needs_real_outcome"}, PROFILE),
        ({"classification": "adapter_validated"}, None),
        ({}, PROFILE),
    ]
    for run, profile in outcome_cases:
        assert status_module.delivery_outcome_for_run(run, profile) == _projection_outcome(run, profile), run

    assert status_module.outcome_floor_configured(PROFILE) == _projection_outcome_floor_configured(PROFILE)
    assert status_module.outcome_floor_configured(None) == _projection_outcome_floor_configured(None)

    runs = [
        {"classification": "needs_real_outcome"},
        {"classification": "doc_only_contract"},
        {"classification": "adapter_validated"},
        {"classification": "needs_real_outcome"},
    ]
    assert status_module.outcome_gap_streak(runs, PROFILE) == _projection_outcome_gap_streak(runs, PROFILE)
    assert status_module.outcome_gap_streak(runs, None) == _projection_outcome_gap_streak(runs, None)

    small_runs = [
        {"classification": "single_note"},
        {"classification": "owner_handoff_consumer_test"},
        {"classification": "delivery_ranker_readiness_batch"},
    ]
    assert status_module.small_delivery_batch_scale_streak(small_runs) == _projection_small_scale_streak(
        small_runs
    )


def main() -> None:
    assert_delivery_signal_wrapper_parity()


if __name__ == "__main__":
    main()
