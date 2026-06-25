#!/usr/bin/env python3
"""Smoke-test scheduler agent-lane capacity and developer commands."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "scheduler-agent-lane-smoke"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.scheduler import build_scheduler_plan  # noqa: E402


def todo(
    todo_id: str,
    text: str,
    *,
    claimed_by: str | None = None,
    write_scope: str | None = None,
) -> dict:
    item = {
        "todo_id": todo_id,
        "text": text,
        "status": "open",
        "done": False,
        "role": "agent",
        "task_class": "advancement_task",
        "safety_class": "local_write" if write_scope else "read_only",
    }
    if claimed_by:
        item["claimed_by"] = claimed_by
    if write_scope:
        item["required_write_scopes"] = [write_scope]
    return item


def payload(items: list[dict]) -> dict:
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "open_count": len(items),
        "first_executable_items": items,
        "executable_backlog_items": items,
        "items": items,
    }
    return {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "active",
                    "waiting_on": "codex",
                    "agent_todos": agent_todos,
                    "project_asset": {"agent_todos": agent_todos},
                }
            ]
        },
    }


def assert_same_claimed_agent_is_serialized() -> None:
    plan = build_scheduler_plan(
        payload(
            [
                todo("todo_dev_docs", "Update docs.", claimed_by="codex-devbox", write_scope="docs/**"),
                todo("todo_dev_src", "Update source.", claimed_by="codex-devbox", write_scope="loopx/scheduler.py"),
                todo("todo_side_ui", "Update UI.", claimed_by="codex-side-ui", write_scope="apps/dashboard/**"),
            ]
        ),
        goal_id=GOAL_ID,
        max_parallel=3,
    )
    assert [item["todo_id"] for item in plan["runnable_batch"]] == [
        "todo_dev_docs",
        "todo_side_ui",
    ], plan
    waiting = {item["todo_id"]: item for item in plan["waiting_candidates"]}
    assert waiting["todo_dev_src"]["reason_codes"] == ["agent_lane_capacity"], waiting
    assert waiting["todo_dev_src"]["conflicts_with"] == ["todo_dev_docs"], waiting


def assert_agent_scoped_plan_includes_claim_and_guard_commands() -> None:
    plan = build_scheduler_plan(
        payload(
            [
                todo("todo_unclaimed_docs", "Update docs.", write_scope="docs/**"),
                todo("todo_dev_read", "Inspect status.", claimed_by="codex-devbox"),
            ]
        ),
        goal_id=GOAL_ID,
        agent_id="codex-devbox",
        max_parallel=2,
    )
    commands = plan["developer_commands"]
    assert "--agent-id codex-devbox" in commands["scheduler_plan"], commands
    assert commands["quota_guard"] == (
        "loopx --format json quota should-run "
        "--goal-id scheduler-agent-lane-smoke --agent-id codex-devbox"
    ), commands
    assert plan["runnable_batch"][0]["claim_command"] == (
        "loopx todo claim --goal-id scheduler-agent-lane-smoke "
        "--todo-id todo_unclaimed_docs --claimed-by codex-devbox"
    ), plan


def main() -> int:
    assert_same_claimed_agent_is_serialized()
    assert_agent_scoped_plan_includes_claim_and_guard_commands()
    print("scheduler agent lane smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
