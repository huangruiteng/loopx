from __future__ import annotations

import json
from pathlib import Path

from loopx.control_plane.todos.todo_semantics import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    todo_item_claimed_by_agent_or_unclaimed,
    todo_item_is_due_monitor,
    todo_item_task_class,
)
from loopx.control_plane.todos.todo_summary import todo_item_task_class as summary_task_class


FIXTURE = Path(__file__).parents[1] / "fixtures/control_plane/coordination_production_scale_v0.json"


def test_summary_and_projection_share_title_aware_task_classification() -> None:
    item = {"title": "Observe dependency health", "text": "", "status": "open"}
    assert todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    assert summary_task_class(item) == TODO_TASK_CLASS_MONITOR
    assert todo_item_is_due_monitor(
        {**item, "next_due_at": "2025-01-01T00:00:00Z"},
        now=__import__("datetime").datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )


def test_exclusion_is_part_of_selectability_not_claim_ownership() -> None:
    item = {"task_class": TODO_TASK_CLASS_ADVANCEMENT, "status": "open", "excluded_agents": ["agent-a"]}
    assert not todo_item_claimed_by_agent_or_unclaimed(item, agent_id="agent-a")
    assert todo_item_claimed_by_agent_or_unclaimed(item, agent_id="agent-b")


def test_complex_fixture_declares_cross_rfc_semantic_edges() -> None:
    cases = json.loads(FIXTURE.read_text())["semantic_cases"]
    assert cases["global_gate_without_goal_binding"]["global_gate"] is True
    assert cases["global_gate_without_goal_binding"]["goal_bound"] is False
    assert cases["expired_lease"]["lease_epoch"] == 7
    assert cases["excluded_unclaimed_advancement"]["claimed_by"] is None
