from __future__ import annotations

from typing import Any

import pytest

from loopx.control_plane.goals.goal_vision import normalize_goal_vision_packet
from loopx.control_plane.work_items.autonomous_replan_ack import (
    compact_autonomous_replan_ack,
)
from loopx.control_plane.work_items.progress_observation import (
    semantic_delta_from_writeback,
)
from loopx.status import compact_run


FRESH_VISION_PATH_OUTCOME = "fresh_vision_path_outcome"
GOAL_ID = "goal-replan-3338"
AGENT_ID = "codex-replan-agent"


def _validated_agent_vision(path_outcome: str) -> dict[str, Any]:
    return normalize_goal_vision_packet(
        {
            "agent_id": AGENT_ID,
            "state": "active",
            "vision_patch": {
                "acceptance_summary": "Keep the bounded path decision auditable."
            },
            "path_delta": {
                "schema_version": "goal_path_delta_v0",
                "outcome": path_outcome,
                "prior_assumption": "The current path remains sufficient.",
                "observed_reality": "The latest evidence supports this disposition.",
                "retained": ["Keep the validated evidence boundary."],
                "evidence_refs": ["evidence:replan-3338"],
            },
        },
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )


def _accepted_ack_run(
    *,
    path_outcome: str | None,
    satisfying_outcomes: list[str] | None = None,
    outcomes: list[str] | None = None,
    semantic_delta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_satisfying_outcomes = (
        satisfying_outcomes
        if satisfying_outcomes is not None
        else [FRESH_VISION_PATH_OUTCOME]
    )
    resolved_outcomes = outcomes if outcomes is not None else resolved_satisfying_outcomes
    resolved_semantic_delta = semantic_delta or {
        "schema_version": "replan_semantic_delta_v0",
        "accepted": True,
        "outcomes": resolved_outcomes,
        "satisfying_outcomes": resolved_satisfying_outcomes,
        "required_any_of": resolved_satisfying_outcomes,
        "obligation_id": "replan-3338",
    }
    run: dict[str, Any] = {
        "classification": "bounded_replan_progress",
        "generated_at": "2026-08-19T12:00:00+08:00",
        "agent_id": AGENT_ID,
        "autonomous_replan_ack": {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "refresh_state_semantic_delta",
            "semantic_delta": resolved_semantic_delta,
        },
    }
    if path_outcome is not None:
        if path_outcome == "unexpected":
            run["agent_vision"] = {
                "schema_version": "goal_vision_replan_contract_v0",
                "agent_id": AGENT_ID,
                "path_delta": {"outcome": path_outcome},
            }
        else:
            run["agent_vision"] = _validated_agent_vision(path_outcome)
    return run


@pytest.mark.parametrize("path_disposition", ["continue", "no_change", "replan"])
def test_compact_ack_projects_validated_path_disposition(
    path_disposition: str,
) -> None:
    semantic_delta = semantic_delta_from_writeback(
        obligation={
            "obligation_id": "replan-3338",
            "satisfying_semantic_outcomes": ["new_surface"],
        },
        progress_observation={
            "schema_version": "typed_progress_observation_v0",
            "work_item_id": "todo-replan-3338",
            "surface_id": "surface-new",
            "result_class": "advanced",
            "evidence_ids": ["evidence:new-surface"],
        },
        agent_vision=_validated_agent_vision(path_disposition),
    )

    assert semantic_delta["accepted"] is True
    assert semantic_delta["outcomes"] == [
        "new_surface",
        FRESH_VISION_PATH_OUTCOME,
    ]
    assert semantic_delta["satisfying_outcomes"] == ["new_surface"]
    compact = compact_autonomous_replan_ack(
        _accepted_ack_run(
            path_outcome=path_disposition,
            semantic_delta=semantic_delta,
        )
    )

    assert compact is not None
    assert compact["path_disposition"] == path_disposition
    assert compact["semantic_delta"]["satisfying_outcomes"] == ["new_surface"]
    assert "path_disposition" not in compact["semantic_delta"]


@pytest.mark.parametrize(
    ("path_outcome", "satisfying_outcomes"),
    [
        (None, [FRESH_VISION_PATH_OUTCOME]),
        ("wait", [FRESH_VISION_PATH_OUTCOME]),
        ("unexpected", [FRESH_VISION_PATH_OUTCOME]),
        ("replan", ["new_concrete_blocker"]),
    ],
)
def test_compact_ack_does_not_invent_path_disposition(
    path_outcome: str | None,
    satisfying_outcomes: list[str],
) -> None:
    compact = compact_autonomous_replan_ack(
        _accepted_ack_run(
            path_outcome=path_outcome,
            satisfying_outcomes=satisfying_outcomes,
        )
    )

    assert compact is not None
    assert "path_disposition" not in compact


def test_compact_run_exposes_path_disposition_to_status_consumers() -> None:
    compact = compact_run(_accepted_ack_run(path_outcome="replan"))

    assert compact["autonomous_replan_ack"]["path_disposition"] == "replan"


def test_long_chain_trigger_checkpoint_survives_ack_compaction() -> None:
    frontier_revision = "todo_frontier_revision_v0:0123456789abcdef01234567"
    semantic_delta = semantic_delta_from_writeback(
        obligation={
            "obligation_id": "replan-3338",
            "satisfying_semantic_outcomes": ["new_surface"],
            "triggers": [
                {
                    "kind": "long_todo_chain",
                    "frontier_revision": frontier_revision,
                    "frontier_revision_complete": True,
                }
            ],
        },
        progress_observation={
            "schema_version": "typed_progress_observation_v0",
            "work_item_id": "todo-replan-3338",
            "surface_id": "surface-new",
            "result_class": "advanced",
            "evidence_ids": ["evidence:new-surface"],
        },
    )

    compact = compact_autonomous_replan_ack(
        _accepted_ack_run(path_outcome=None, semantic_delta=semantic_delta)
    )

    assert compact is not None
    assert compact["semantic_delta"]["trigger_checkpoints"] == [
        {"kind": "long_todo_chain", "frontier_revision": frontier_revision}
    ]
