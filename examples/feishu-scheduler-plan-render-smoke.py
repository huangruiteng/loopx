#!/usr/bin/env python3
"""Smoke-test Feishu-friendly scheduler plan rendering."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark.scheduler_plan_reporter import render_scheduler_plan_chat_text  # noqa: E402


def assert_dispatch_plan_renders_operable_summary() -> None:
    plan_text = render_scheduler_plan_chat_text(
        {
            "schema_version": "scheduler_plan_v0",
            "goal_id": "goal",
            "agent_id": "agent",
            "dispatch_plan": {
                "schema_version": "scheduler_dispatch_plan_v0",
                "action": "run_parallel_batch",
                "parallelizable": True,
                "runnable_todo_ids": ["todo_docs", "todo_ui"],
                "waiting_reason_counts": {"agent_lane_capacity": 1},
                "agent_lanes": [
                    {
                        "agent_lane": "agent",
                        "runnable_todo_ids": ["todo_docs"],
                        "waiting_todo_ids": ["todo_later"],
                    }
                ],
                "worker_handoffs": [
                    {
                        "todo_id": "todo_docs",
                        "agent_lane": "agent",
                        "handoff_text": "LoopX worker handoff\nTodo: todo_docs",
                    }
                ],
                "developer_steps": [
                    {
                        "kind": "quota_guard",
                        "command": "loopx --format json quota should-run --goal-id goal --agent-id agent",
                        "required": True,
                    },
                    {
                        "kind": "claim_runnable",
                        "todo_id": "todo_docs",
                        "command": "loopx todo claim --goal-id goal --todo-id todo_docs --claimed-by agent",
                        "required": True,
                    },
                ],
            },
        }
    )
    assert "Scheduler plan: run_parallel_batch" in plan_text, plan_text
    assert "Runnable: todo_docs, todo_ui" in plan_text, plan_text
    assert "Waiting: agent_lane_capacity=1" in plan_text, plan_text
    assert "- agent: run=todo_docs; wait=todo_later" in plan_text, plan_text
    assert "Worker handoffs: todo_docs->agent" in plan_text, plan_text
    assert "claim_runnable todo_docs" in plan_text, plan_text


def assert_legacy_candidate_lists_still_render() -> None:
    plan_text = render_scheduler_plan_chat_text(
        {
            "schema_version": "scheduler_plan_v0",
            "mode": "plan",
            "runnable_batch": [{"todo_id": "todo_read"}],
            "waiting_candidates": [{"todo_id": "todo_write"}],
        }
    )
    assert "Scheduler plan: plan" in plan_text, plan_text
    assert "Runnable: todo_read" in plan_text, plan_text
    assert "Waiting todos: todo_write" in plan_text, plan_text


def main() -> int:
    assert_dispatch_plan_renders_operable_summary()
    assert_legacy_candidate_lists_still_render()
    print("feishu scheduler plan render smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
