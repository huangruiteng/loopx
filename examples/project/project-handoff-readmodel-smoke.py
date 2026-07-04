#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import project_handoff as project_handoff_read_model  # noqa: E402


PROFILE = {
    "outcome_floor": {
        "outcome_markers": ["validated"],
        "surface_only_hints": ["doc_only"],
    }
}


def _projection_state(
    *,
    ready: bool,
    project_asset: dict[str, object],
    latest_runs: list[dict[str, object]] | None,
) -> dict[str, object]:
    return project_handoff_read_model.project_asset_handoff_state(
        ready=ready,
        project_asset=project_asset,
        latest_runs=latest_runs,
        compact_execution_profile=status_module.compact_execution_profile,
        parse_timestamp=status_module.parse_timestamp,
        is_handoff_ready_run=status_module.is_handoff_ready_run,
        is_custom_post_handoff_work_run=status_module.is_custom_post_handoff_work_run,
        is_status_neutral_run=status_module.is_status_neutral_run,
        compact_post_handoff_run=status_module.compact_post_handoff_run,
        small_delivery_batch_scale_streak=status_module.small_delivery_batch_scale_streak,
        outcome_floor_configured=status_module.outcome_floor_configured,
        outcome_gap_streak=status_module.outcome_gap_streak,
    )


def _projection_readiness(
    item: dict[str, object],
    *,
    latest_runs: list[dict[str, object]] | None,
) -> dict[str, object] | None:
    return project_handoff_read_model.project_asset_handoff_readiness(
        item,
        latest_runs=latest_runs,
        project_asset_handoff_check_projection=status_module.project_asset_handoff_check_projection,
        handoff_budget_contract=status_module.handoff_budget_contract,
        project_asset_handoff_state=status_module.project_asset_handoff_state,
    )


def assert_project_handoff_wrapper_parity() -> None:
    latest_runs = [
        {
            "generated_at": "2026-07-04T00:03:00+00:00",
            "classification": "doc_only_contract",
        },
        {
            "generated_at": "2026-07-04T00:02:00+00:00",
            "classification": "adapter_validated",
        },
        {
            "generated_at": "2026-07-04T00:01:00+00:00",
            "classification": "handoff_ready",
        },
        {
            "generated_at": "not-a-date",
            "classification": "ignored_bad_timestamp",
        },
    ]
    project_asset = {"execution_profile": PROFILE}
    assert status_module.project_asset_handoff_state(
        ready=False,
        project_asset=project_asset,
        latest_runs=latest_runs,
    ) == _projection_state(
        ready=False,
        project_asset=project_asset,
        latest_runs=latest_runs,
    )

    ready_runs = [
        {
            "generated_at": "2026-07-04T00:05:00+00:00",
            "classification": "custom_small_note",
        },
        {
            "generated_at": "2026-07-04T00:04:00+00:00",
            "classification": "feedback_reranker_adapter_slice",
        },
    ]
    ready_asset = {"execution_profile": PROFILE}
    assert status_module.project_asset_handoff_state(
        ready=True,
        project_asset=ready_asset,
        latest_runs=ready_runs,
    ) == _projection_state(
        ready=True,
        project_asset=ready_asset,
        latest_runs=ready_runs,
    )

    validation_asset = {
        "execution_profile": PROFILE,
        "latest_validation": {
            "generated_at": "2026-07-04T00:06:00+00:00",
            "classification": "adapter_validated",
        },
    }
    assert status_module.project_asset_handoff_state(
        ready=True,
        project_asset=validation_asset,
        latest_runs=[],
    ) == _projection_state(
        ready=True,
        project_asset=validation_asset,
        latest_runs=[],
    )


def assert_project_handoff_readiness_wrapper_parity() -> None:
    latest_runs = [
        {
            "generated_at": "2026-07-04T00:08:00+00:00",
            "classification": "controller_adapter_validated",
        }
    ]
    item = {
        "goal_id": "loopx-demo",
        "waiting_on": "codex",
        "recommended_action": "continue the current control-plane slice",
        "project_asset": {
            "next_action": "continue the current control-plane slice",
            "stop_condition": "stop before private material",
            "quota": {"state": "eligible"},
            "execution_profile": PROFILE,
        },
    }
    assert status_module.project_asset_handoff_readiness(
        item,
        latest_runs=latest_runs,
    ) == _projection_readiness(
        item,
        latest_runs=latest_runs,
    )

    missing_asset = {"goal_id": "loopx-demo"}
    assert status_module.project_asset_handoff_readiness(
        missing_asset,
        latest_runs=latest_runs,
    ) == _projection_readiness(
        missing_asset,
        latest_runs=latest_runs,
    )

    incomplete_item = {
        "goal_id": "loopx-demo",
        "waiting_on": "codex",
        "project_asset": {
            "quota": {"state": "eligible"},
            "execution_profile": PROFILE,
        },
    }
    assert status_module.project_asset_handoff_readiness(
        incomplete_item,
        latest_runs=[],
    ) == _projection_readiness(
        incomplete_item,
        latest_runs=[],
    )


def main() -> None:
    assert_project_handoff_wrapper_parity()
    assert_project_handoff_readiness_wrapper_parity()


if __name__ == "__main__":
    main()
