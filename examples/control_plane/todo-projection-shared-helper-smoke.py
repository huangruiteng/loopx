#!/usr/bin/env python3
"""Smoke-test shared todo projection ordering across status and quota."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import (  # noqa: E402
    _claimed_visibility_items as quota_claimed_visibility_items,
    _first_executable_todo_item as quota_first_executable_todo_item,
    _todo_item_is_deferred as quota_todo_item_is_deferred,
    _todo_summary_monitor_items as quota_todo_summary_monitor_items,
    _todo_projection_sort_key as quota_todo_projection_sort_key,
    _todo_task_class as quota_todo_task_class,
    build_quota_should_run,
)
from loopx.control_plane.agents.agent_scope import (  # noqa: E402
    _todo_item_claimed_by_agent_or_unclaimed as agent_scope_todo_item_claimed_by_agent_or_unclaimed,
)
from loopx.status import (  # noqa: E402
    claimed_visibility_items as status_claimed_visibility_items,
    compact_todo_group,
    todo_item_is_deferred as status_todo_item_is_deferred,
    todo_projection_sort_key,
)
from loopx.todo_contract import (  # noqa: E402
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
)
from loopx.control_plane.todos.projection import (  # noqa: E402
    todo_claimed_visibility_items as shared_claimed_visibility_items,
    todo_item_claimed_by_agent_or_unclaimed as shared_todo_item_claimed_by_agent_or_unclaimed,
    todo_item_is_deferred as shared_todo_item_is_deferred,
    todo_projection_sort_key as shared_todo_projection_sort_key,
    todo_summary_first_executable_item as shared_first_executable_todo_item,
    todo_summary_monitor_items as shared_todo_summary_monitor_items,
)


GOAL_ID = "todo-projection-shared-helper-goal"
AGENT_ID = "codex-product-capability"


def todo(
    index: int,
    text: str,
    *,
    task_class: str,
    todo_id: str,
    **metadata: Any,
) -> dict[str, Any]:
    item = {
        "schema_version": "todo_item_v0",
        "todo_id": todo_id,
        "role": "agent",
        "source_section": "Agent Todo",
        "status": "open",
        "done": False,
        "index": index,
        "text": text,
        "task_class": task_class,
    }
    item.update(metadata)
    return item


def build_agent_todo_summary() -> dict[str, Any]:
    summary = compact_todo_group(
        [
            todo(
                4,
                "[P2] Continue low-risk canary cleanup after the core projection parity lands.",
                task_class=TODO_TASK_CLASS_ADVANCEMENT,
                todo_id="todo_advancement_p2",
            ),
            todo(
                5,
                "[P2] Monitor unscheduled public smoke signal after schedule metadata is added.",
                task_class=TODO_TASK_CLASS_MONITOR,
                todo_id="todo_monitor_unscheduled",
            ),
            todo(
                2,
                "[P0] Monitor public smoke signal and only write back if it changed.",
                task_class=TODO_TASK_CLASS_MONITOR,
                todo_id="todo_monitor_p0",
                next_due_at="2026-01-01T00:00:00+00:00",
            ),
            todo(
                3,
                "[P0] Extract todo projection helper for status and quota parity.",
                task_class=TODO_TASK_CLASS_ADVANCEMENT,
                todo_id="todo_advancement_p0",
                claimed_by=AGENT_ID,
            ),
            todo(
                1,
                "[P1] Add characterization before moving more control-plane code.",
                task_class=TODO_TASK_CLASS_ADVANCEMENT,
                todo_id="todo_advancement_p1",
            ),
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert summary is not None, summary
    return summary


def status_payload(agent_todos: dict[str, Any]) -> dict[str, Any]:
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "allowed_slots": 1440,
        "spent_slots": 0,
        "state": "eligible",
        "reason": "fixture eligible quota",
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "codex",
                    "severity": "info",
                    "source": "project_asset",
                    "quota": quota,
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "agent_todos": agent_todos,
                        "next_action": "Use the first executable advancement todo.",
                    },
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "quota": quota,
                    "latest_runs": [],
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", AGENT_ID],
                    },
                }
            ]
        },
    }


def assert_status_summary_lanes(summary: dict[str, Any]) -> None:
    assert [item["todo_id"] for item in summary["first_open_items"]] == [
        "todo_monitor_p0",
        "todo_advancement_p0",
        "todo_advancement_p1",
    ], summary
    assert [item["todo_id"] for item in summary["first_executable_items"]] == [
        "todo_advancement_p0",
        "todo_advancement_p1",
        "todo_advancement_p2",
    ], summary
    assert [item["todo_id"] for item in summary["monitor_due_items"]] == [
        "todo_monitor_p0",
    ], summary
    assert summary["monitor_due_count"] == 1, summary
    assert [item["todo_id"] for item in summary["monitor_schedule_gap_items"]] == [
        "todo_monitor_unscheduled",
    ], summary
    assert summary["monitor_schedule_gap_count"] == 1, summary


def assert_shared_ordering_parity(summary: dict[str, Any]) -> None:
    first_open = [item for item in summary["first_open_items"] if isinstance(item, dict)]
    assert [item["todo_id"] for item in sorted(first_open, key=todo_projection_sort_key)] == [
        "todo_monitor_p0",
        "todo_advancement_p0",
        "todo_advancement_p1",
    ], first_open
    assert [item["todo_id"] for item in sorted(first_open, key=quota_todo_projection_sort_key)] == [
        "todo_monitor_p0",
        "todo_advancement_p0",
        "todo_advancement_p1",
    ], first_open
    assert [item["todo_id"] for item in sorted(first_open, key=shared_todo_projection_sort_key)] == [
        "todo_monitor_p0",
        "todo_advancement_p0",
        "todo_advancement_p1",
    ], first_open
    embedded_priority = {
        "index": 9,
        "text": "Keep this text with embedded P0 wording but no bracket prefix.",
    }
    assert todo_projection_sort_key(embedded_priority) == (50, 9), embedded_priority
    assert quota_todo_projection_sort_key(embedded_priority) == (0, 9), embedded_priority


def assert_claimed_visibility_parity() -> None:
    items = [
        todo(
            1,
            "[P1] Claimed by A one.",
            task_class=TODO_TASK_CLASS_ADVANCEMENT,
            todo_id="todo_a1",
            claimed_by="agent-a",
        ),
        todo(
            2,
            "[P1] Claimed by A two.",
            task_class=TODO_TASK_CLASS_ADVANCEMENT,
            todo_id="todo_a2",
            claimed_by="agent-a",
        ),
        todo(
            3,
            "[P1] Claimed by B one.",
            task_class=TODO_TASK_CLASS_ADVANCEMENT,
            todo_id="todo_b1",
            claimed_by="agent-b",
        ),
        todo(
            4,
            "[P1] Unclaimed filler.",
            task_class=TODO_TASK_CLASS_ADVANCEMENT,
            todo_id="todo_unclaimed",
        ),
    ]
    for selector in (
        shared_claimed_visibility_items,
        status_claimed_visibility_items,
        quota_claimed_visibility_items,
    ):
        selected_two = selector(items, limit=2)
        assert [item["todo_id"] for item in selected_two] == ["todo_a1", "todo_b1"], selected_two
        selected_three = selector(items, limit=3)
        assert [item["todo_id"] for item in selected_three] == [
            "todo_a1",
            "todo_a2",
            "todo_b1",
        ], selected_three
    claimed_by_current = items[0]
    claimed_by_other = items[2]
    unclaimed = items[3]
    for predicate in (
        shared_todo_item_claimed_by_agent_or_unclaimed,
        agent_scope_todo_item_claimed_by_agent_or_unclaimed,
    ):
        assert predicate(claimed_by_current, agent_id="agent-a") is True, claimed_by_current
        assert predicate(claimed_by_other, agent_id="agent-a") is False, claimed_by_other
        assert predicate(unclaimed, agent_id="agent-a") is True, unclaimed


def assert_deferred_helper_parity() -> None:
    deferred = todo(
        6,
        "[P2] Resume after dependency lands.",
        task_class=TODO_TASK_CLASS_ADVANCEMENT,
        todo_id="todo_deferred",
        status="deferred",
    )
    open_item = todo(
        7,
        "[P2] Still executable.",
        task_class=TODO_TASK_CLASS_ADVANCEMENT,
        todo_id="todo_open",
    )
    for predicate in (
        shared_todo_item_is_deferred,
        status_todo_item_is_deferred,
        quota_todo_item_is_deferred,
    ):
        assert predicate(deferred) is True, deferred
        assert predicate(open_item) is False, open_item


def assert_monitor_item_collection_parity(summary: dict[str, Any]) -> None:
    # Preserve current lane-projection semantics: repeated references to the
    # same dict object are de-duplicated, while separate projected copies of the
    # same todo_id can appear across monitor summary lanes. This is not a
    # long-term identity contract; pin it before replacing it with stable lane
    # keys.
    expected_ids = [
        "todo_monitor_p0",
        "todo_monitor_p0",
        "todo_monitor_unscheduled",
        "todo_monitor_p0",
    ]
    for selector in (
        shared_todo_summary_monitor_items,
        quota_todo_summary_monitor_items,
    ):
        selected_ids = [item["todo_id"] for item in selector(summary)]
        assert selected_ids == expected_ids, selected_ids


def assert_first_executable_item_parity(summary: dict[str, Any]) -> None:
    for selector in (
        shared_first_executable_todo_item,
        quota_first_executable_todo_item,
    ):
        selected = selector(summary)
        assert isinstance(selected, dict), summary
        assert selected["todo_id"] == "todo_advancement_p0", selected


def assert_quota_uses_executable_advancement(summary: dict[str, Any]) -> None:
    payload = build_quota_should_run(
        status_payload(summary),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
    )
    quota_summary = payload["agent_todo_summary"]
    assert quota_summary["first_open_items"][0]["todo_id"] == "todo_advancement_p0", payload
    assert quota_summary["first_executable_items"][0]["todo_id"] == "todo_advancement_p0", payload
    assert quota_summary["monitor_open_items"][0]["todo_id"] == "todo_monitor_p0", payload
    assert quota_summary["monitor_schedule_gap_items"][0]["todo_id"] == (
        "todo_monitor_unscheduled"
    ), payload
    assert quota_summary["monitor_schedule_gap_count"] == 1, payload
    assert quota_todo_task_class(quota_summary["monitor_open_items"][0]) == TODO_TASK_CLASS_MONITOR
    assert quota_todo_task_class(
        quota_summary["first_executable_items"][0]
    ) == TODO_TASK_CLASS_ADVANCEMENT
    lane = payload["work_lane_contract"]
    assert lane["lane"] == "advancement_task", payload
    assert payload["agent_lane_next_action"]["todo_id"] == "todo_advancement_p0", payload


def main() -> int:
    summary = build_agent_todo_summary()
    assert_status_summary_lanes(summary)
    assert_shared_ordering_parity(summary)
    assert_claimed_visibility_parity()
    assert_deferred_helper_parity()
    assert_monitor_item_collection_parity(summary)
    assert_first_executable_item_parity(summary)
    assert_quota_uses_executable_advancement(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
