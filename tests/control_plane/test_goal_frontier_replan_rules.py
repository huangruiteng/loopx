from __future__ import annotations

from dataclasses import replace

import pytest

from loopx.control_plane.goals.goal_frontier import (
    derive_goal_frontier_replan_obligation_from_summaries,
)
from loopx.control_plane.goals.goal_frontier_replan_rules import (
    GOAL_FRONTIER_REPLAN_RULE_ORDER,
    GoalFrontierReplanFacts,
    GoalFrontierReplanRule,
    select_goal_frontier_replan_rule,
)


@pytest.mark.parametrize(
    ("overrides", "expected_rule", "derives_obligation"),
    [
        (
            {"existing_replan_required": True, "blocking_handoff_gate_count": 1},
            GoalFrontierReplanRule.EXISTING_OBLIGATION,
            False,
        ),
        (
            {"blocking_handoff_gate_count": 1, "acceptance_gap_count": 1},
            GoalFrontierReplanRule.BLOCKING_HANDOFF_GATE,
            False,
        ),
        (
            {"ready_deferred_successor_count": 1},
            GoalFrontierReplanRule.READY_DEFERRED_SUCCESSOR,
            False,
        ),
        (
            {"user_open_count": 1, "acceptance_gap_count": 1},
            GoalFrontierReplanRule.OPEN_USER_TODO,
            False,
        ),
        (
            {"succession_gap_count": 1, "acceptance_gap_count": 1},
            GoalFrontierReplanRule.TODO_SUCCESSION_GAP,
            True,
        ),
        (
            {"acceptance_gap_count": 1},
            GoalFrontierReplanRule.VISION_ACCEPTANCE_GAP,
            True,
        ),
        (
            {
                "long_todo_chain_triggered": True,
                "selectable_frontier_advancement": 15,
            },
            GoalFrontierReplanRule.LONG_TODO_CHAIN,
            True,
        ),
        (
            {
                "long_todo_chain_triggered": True,
                "long_todo_chain_acknowledged": True,
                "selectable_frontier_advancement": 15,
            },
            GoalFrontierReplanRule.LONG_TODO_CHAIN_ACKNOWLEDGED,
            False,
        ),
        (
            {
                "watch_lane_continuation_acknowledged": True,
                "monitor_only_lane": True,
                "monitor_count": 1,
            },
            GoalFrontierReplanRule.WATCH_LANE_CONTINUATION_ACKNOWLEDGED,
            False,
        ),
        ({}, GoalFrontierReplanRule.NOT_MONITOR_ONLY, False),
        (
            {"monitor_only_lane": True},
            GoalFrontierReplanRule.NO_OPEN_MONITOR,
            False,
        ),
        (
            {
                "monitor_only_lane": True,
                "monitor_count": 1,
                "agent_advancement_count": 1,
                "total_frontier_advancement": 1,
            },
            GoalFrontierReplanRule.ADVANCEMENT_REMAINS,
            False,
        ),
        (
            {"monitor_only_lane": True, "monitor_count": 1},
            GoalFrontierReplanRule.MONITOR_FRONTIER_EXHAUSTED,
            True,
        ),
    ],
)
def test_goal_frontier_replan_decision_table(
    overrides: dict[str, object],
    expected_rule: GoalFrontierReplanRule,
    derives_obligation: bool,
) -> None:
    facts = replace(GoalFrontierReplanFacts(), **overrides)

    decision = select_goal_frontier_replan_rule(facts)

    assert decision.rule is expected_rule
    assert decision.derives_obligation is derives_obligation
    assert decision.to_payload()["rule_index"] == GOAL_FRONTIER_REPLAN_RULE_ORDER.index(
        expected_rule
    )


def _repeat_vision_gap() -> list[dict[str, object]]:
    return [
        {
            "kind": "vision_acceptance_gap",
            "acceptance_summary": "This agent must keep advancing its own stage.",
            "replan_trigger_summary": "No runnable work satisfies this agent's stage.",
            "advancement_policy": "repeat_until_closed",
        }
    ]


def _advancement(todo_id: str, claimed_by: str) -> dict[str, object]:
    return {
        "todo_id": todo_id,
        "status": "open",
        "task_class": "advancement_task",
        "claimed_by": claimed_by,
    }


@pytest.mark.parametrize("other_agent_count", [1, 2, 8])
def test_other_agent_backlog_size_cannot_satisfy_scoped_vision_gap(
    other_agent_count: int,
) -> None:
    other_items = [
        _advancement(f"todo_peer_{index}", f"peer-{index}")
        for index in range(other_agent_count)
    ]

    obligation = derive_goal_frontier_replan_obligation_from_summaries(
        user_todo_summary={"open_count": 0},
        agent_todo_summary={
            "open_count": other_agent_count,
            "claimed_advancement_open_count": other_agent_count,
            "current_agent_claimed_advancement_count": 0,
            "unclaimed_priority_open_items": [],
            "executable_backlog_items": [],
            "claim_scope": {"other_agent_claimed_items": other_items},
        },
        work_lane_contract=None,
        agent_id="current-agent",
        existing_replan_obligation=None,
        acceptance_gaps=_repeat_vision_gap(),
    )

    assert obligation is not None
    assert obligation["agent_id"] == "current-agent"
    assert obligation["triggers"][0]["kind"] == "vision_acceptance_gap"


def test_current_agent_advancement_satisfies_scoped_vision_frontier() -> None:
    current_item = _advancement("todo_current", "current-agent")

    obligation = derive_goal_frontier_replan_obligation_from_summaries(
        user_todo_summary={"open_count": 0},
        agent_todo_summary={
            "open_count": 1,
            "claimed_advancement_open_count": 1,
            "current_agent_claimed_advancement_count": 1,
            "unclaimed_priority_open_items": [],
            "executable_backlog_items": [current_item],
            "claim_scope": {"other_agent_claimed_items": []},
        },
        work_lane_contract={"lane": "advancement_task", "must_attempt_work": True},
        agent_id="current-agent",
        existing_replan_obligation=None,
        acceptance_gaps=_repeat_vision_gap(),
    )

    assert obligation is None
