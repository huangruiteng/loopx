from __future__ import annotations

import pytest

from loopx.control_plane.goals.goal_frontier import (
    acceptance_gaps_from_agent_vision,
    derive_goal_frontier_replan_obligation_from_summaries,
)


AGENT_ID = "fixture-agent"


def vision(state: str) -> dict[str, object]:
    return {
        "schema_version": "goal_vision_replan_contract_v0",
        "agent_id": AGENT_ID,
        "state": state,
        "vision_patch": {
            "vision_summary": "Complete one bounded stage.",
            "acceptance_summary": "Stage evidence is complete.",
        },
        "generated_at": "2026-07-12T00:00:00Z",
    }


@pytest.mark.parametrize("state", ["vision_closed", "closed", "satisfied"])
def test_active_goal_closed_stage_requires_successor_vision(state: str) -> None:
    gaps = acceptance_gaps_from_agent_vision(vision(state), goal_status="active")

    assert len(gaps) == 1
    assert gaps[0]["kind"] == "vision_successor_required"
    assert gaps[0]["advancement_policy"] == "repeat_until_closed"


@pytest.mark.parametrize(
    ("state", "goal_status"),
    [
        ("vision_closed", "completed"),
        ("retired", "active"),
        ("superseded", "active"),
        ("no_followup", "active"),
    ],
)
def test_terminal_goal_or_lane_closure_does_not_require_successor(
    state: str,
    goal_status: str,
) -> None:
    assert (
        acceptance_gaps_from_agent_vision(
            vision(state),
            goal_status=goal_status,
        )
        == []
    )


def test_successor_vision_replan_precedes_existing_advancement() -> None:
    gaps = acceptance_gaps_from_agent_vision(
        vision("vision_closed"),
        goal_status="active",
    )
    todo = {
        "todo_id": "todo_successor123",
        "status": "open",
        "task_class": "advancement_task",
        "claimed_by": AGENT_ID,
    }
    obligation = derive_goal_frontier_replan_obligation_from_summaries(
        user_todo_summary={"open_count": 0},
        agent_todo_summary={
            "open_count": 1,
            "current_agent_claimed_open_count": 1,
            "current_agent_claimed_advancement_count": 1,
            "unclaimed_open_count": 0,
            "executable_backlog_items": [todo],
        },
        work_lane_contract={"lane": "advancement_task", "must_attempt_work": True},
        agent_id=AGENT_ID,
        existing_replan_obligation=None,
        acceptance_gaps=gaps,
    )

    assert obligation is not None
    assert obligation["required"] is True
    assert obligation["triggers"][0]["kind"] == "vision_successor_required"
