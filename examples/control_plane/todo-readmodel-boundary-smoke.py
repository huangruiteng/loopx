#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module  # noqa: E402
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


def main() -> None:
    assert_wrapper_parity()
    assert_dependency_blocker_parity()


if __name__ == "__main__":
    main()
