#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
from loopx.projections import autonomous_candidates as autonomous_read_model  # noqa: E402
from loopx.projections import global_registry_shadow as global_registry_shadow_read_model  # noqa: E402
from loopx.projections import todo_summary as todo_read_model  # noqa: E402


def fixture_todos() -> dict:
    return {
        "first_open_items": [
            {
                "index": 2,
                "done": False,
                "text": "[P2] Run focused canary smoke",
                "task_class": "advancement_task",
                "claimed_by": "codex-product-capability",
            },
            {
                "index": 1,
                "done": False,
                "text": "[P1] Monitor quiet transition",
                "task_class": "continuous_monitor",
                "target_key": "monitor-gap",
            },
        ],
        "items": [
            {
                "index": 2,
                "done": False,
                "text": "[P2] Run focused canary smoke",
                "task_class": "advancement_task",
                "claimed_by": "codex-product-capability",
            },
            {
                "index": 3,
                "done": True,
                "text": "[P3] Completed old slice",
            },
            {
                "index": 4,
                "done": False,
                "text": "  [P2]   Refactor todo read model   ",
                "task_class": "advancement_task",
            },
        ],
        "monitor_open_items": [
            {
                "index": 1,
                "done": False,
                "text": "[P1] Monitor quiet transition",
                "task_class": "continuous_monitor",
            }
        ],
    }


def assert_wrapper_parity() -> None:
    todos = fixture_todos()

    assert status_module.open_todo_items(todos) == todo_read_model.open_todo_items(
        todos,
        limit=status_module.MAX_PROJECT_ASSET_TODO_ITEMS,
        text_limit=220,
    )
    assert status_module.todo_lane_items(todos, "monitor_open_items") == todo_read_model.todo_lane_items(
        todos,
        "monitor_open_items",
        limit=status_module.MAX_STATUS_TODOS_PER_ROLE,
        text_limit=220,
    )
    assert status_module.first_open_todo_text(todos) == todo_read_model.first_open_todo_text(
        todos,
        item_limit=220,
    )
    assert status_module.first_open_todo_item(todos) == todo_read_model.first_open_todo_item(
        todos,
        item_limit=status_module.MAX_PROJECT_ASSET_TODO_ITEMS,
        text_limit=220,
    )
    assert status_module.project_asset_todo_summary(
        todos,
        role="agent",
    ) == todo_read_model.project_asset_todo_summary(
        todos,
        role="agent",
        item_limit=status_module.MAX_PROJECT_ASSET_TODO_ITEMS,
        deferred_item_limit=status_module.MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
        advancement_task_class=status_module.TODO_TASK_CLASS_ADVANCEMENT,
    )


def assert_dependency_blocker_parity() -> None:
    items = [
        {
            "goal_id": "current",
            "status": "active",
            "waiting_on": "codex",
        },
        {
            "goal_id": "dependency",
            "status": "blocked",
            "waiting_on": "controller",
            "severity": "action",
            "user_todos": {
                "items": [
                    {
                        "index": 5,
                        "done": False,
                        "text": "Approve rollout gate",
                    },
                    {
                        "index": 6,
                        "done": True,
                        "text": "Old approval",
                    },
                ]
            },
        },
    ]
    assert status_module.dependency_blocker_summary(
        items,
        current_goal_id="current",
    ) == todo_read_model.dependency_blocker_summary(
        items,
        current_goal_id="current",
        limit=status_module.MAX_DEPENDENCY_BLOCKERS,
    )

    status_items = deepcopy(items)
    direct_items = deepcopy(items)
    status_module.attach_dependency_blockers(status_items)
    todo_read_model.attach_dependency_blockers(
        direct_items,
        limit=status_module.MAX_DEPENDENCY_BLOCKERS,
    )
    assert status_items == direct_items


def assert_autonomous_candidate_parity() -> None:
    items = [
        {
            "goal_id": "goal-b",
            "status": "active",
            "waiting_on": "codex",
            "quota": {"state": "eligible"},
            "agent_todos": fixture_todos(),
        },
        {
            "goal_id": "goal-a",
            "status": "watching",
            "waiting_on": status_module.MONITOR_SIGNAL_WAITING_ON,
            "quota": {"state": "eligible"},
            "agent_todos": fixture_todos(),
        },
        {
            "goal_id": "goal-c",
            "status": "blocked",
            "waiting_on": "controller",
            "quota": {"state": "eligible"},
            "agent_todos": fixture_todos(),
        },
    ]
    assert status_module.autonomous_backlog_candidates(items) == autonomous_read_model.autonomous_backlog_candidates(
        items,
        open_todo_items=status_module.open_todo_items,
        todo_item_is_actionable_open=status_module.todo_item_is_actionable_open,
        normalize_todo_text=status_module.normalize_todo_text,
        advancement_task_class=status_module.TODO_TASK_CLASS_ADVANCEMENT,
        limit=status_module.MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
    )
    assert status_module.autonomous_monitor_candidates(items) == autonomous_read_model.autonomous_monitor_candidates(
        items,
        open_todo_items=status_module.open_todo_items,
        todo_item_is_actionable_open=status_module.todo_item_is_actionable_open,
        normalize_todo_text=status_module.normalize_todo_text,
        monitor_task_class=status_module.TODO_TASK_CLASS_MONITOR,
        monitor_signal_waiting_on=status_module.MONITOR_SIGNAL_WAITING_ON,
        limit=status_module.MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
    )


def assert_global_registry_shadow_parity() -> None:
    finding = {
        "kind": "state_shadow",
        "severity": "warning",
        "message": "registry points at stale projection",
        "recommended_action": "refresh the public-safe state projection",
    }
    assert status_module.compact_global_registry_shadow_finding(
        finding
    ) == global_registry_shadow_read_model.compact_global_registry_shadow_finding(finding)

    status_item = {"project_asset": {"goal_id": "loopx-meta"}}
    direct_item = deepcopy(status_item)
    status_module.attach_global_registry_shadow_finding(status_item, finding)
    global_registry_shadow_read_model.attach_global_registry_shadow_finding(direct_item, finding)
    assert status_item == direct_item


def main() -> None:
    assert_wrapper_parity()
    assert_dependency_blocker_parity()
    assert_autonomous_candidate_parity()
    assert_global_registry_shadow_parity()


if __name__ == "__main__":
    main()
