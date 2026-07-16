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
@pytest.mark.parametrize("goal_status", ["active", "active-read-only"])
def test_active_goal_closed_stage_requires_successor_vision(
    state: str,
    goal_status: str,
) -> None:
    gaps = acceptance_gaps_from_agent_vision(vision(state), goal_status=goal_status)

    assert len(gaps) == 1
    assert gaps[0]["kind"] == "vision_successor_required"
    assert gaps[0]["advancement_policy"] == "repeat_until_closed"


@pytest.mark.parametrize(
    ("state", "goal_status"),
    [
        ("vision_closed", "completed"),
        ("retired", "active"),
        ("retired_or_superseded", "active"),
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


@pytest.mark.parametrize("ready_deferred_count", [0, 2])
def test_successor_vision_replan_precedes_existing_work(
    ready_deferred_count: int,
) -> None:
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
            "current_agent_deferred_resume_count": ready_deferred_count,
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


def test_user_gate_still_precedes_successor_vision_replan() -> None:
    gaps = acceptance_gaps_from_agent_vision(
        vision("vision_closed"),
        goal_status="active",
    )
    obligation = derive_goal_frontier_replan_obligation_from_summaries(
        user_todo_summary={"open_count": 1},
        agent_todo_summary={"open_count": 0},
        work_lane_contract={"lane": "advancement_task", "must_attempt_work": True},
        agent_id=AGENT_ID,
        existing_replan_obligation=None,
        acceptance_gaps=gaps,
    )

    assert obligation is None


def test_other_agent_work_does_not_satisfy_scoped_repeat_vision() -> None:
    active_vision = vision("vision_active")
    active_vision["vision_patch"]["advancement_policy"] = "repeat_until_closed"
    gaps = acceptance_gaps_from_agent_vision(active_vision, goal_status="active")
    other_agent_todo = {
        "todo_id": "todo_other_agent",
        "status": "open",
        "task_class": "advancement_task",
        "claimed_by": "fixture-other-agent",
    }

    obligation = derive_goal_frontier_replan_obligation_from_summaries(
        user_todo_summary={"open_count": 0},
        agent_todo_summary={
            "open_count": 1,
            "claimed_advancement_open_count": 1,
            "current_agent_claimed_advancement_count": 0,
            "unclaimed_priority_open_items": [],
            "executable_backlog_items": [],
            "claim_scope": {"other_agent_claimed_items": [other_agent_todo]},
        },
        work_lane_contract=None,
        agent_id=AGENT_ID,
        existing_replan_obligation=None,
        acceptance_gaps=gaps,
    )

    assert obligation is not None
    assert obligation["agent_id"] == AGENT_ID
    assert obligation["triggers"][0]["kind"] == "vision_acceptance_gap"
    assert obligation["todo_actions"][0]["action"] == "add"
