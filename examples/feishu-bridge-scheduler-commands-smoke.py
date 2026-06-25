#!/usr/bin/env python3
"""Smoke-test Feishu bridge scheduler command helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark.bridge_commands import (  # noqa: E402
    bridge_help_text,
    loopx_scheduler_next_batch_text,
    loopx_scheduler_plan_text,
)


def assert_help_exposes_next_batch_command() -> None:
    text = bridge_help_text()
    assert "/plan - show safe parallel scheduler plan" in text, text
    assert "/next - show next dispatchable scheduler batch" in text, text


def assert_scheduler_plan_command_is_stable() -> None:
    calls: list[tuple[list[str], float]] = []

    def fake_run_json(args: list[str], *, timeout: float) -> dict[str, Any]:
        calls.append((args, timeout))
        return {
            "schema_version": "scheduler_plan_v0",
            "goal_id": "goal",
            "agent_id": "agent",
            "dispatch_plan": {
                "action": "run_single_candidate",
                "runnable_todo_ids": ["todo_docs"],
            },
        }

    text = loopx_scheduler_plan_text(
        run_json=fake_run_json,
        loopx_bin="loopx",
        registry="registry.json",
        goal_id="goal",
        agent_id="agent",
        max_chars=1200,
    )
    assert "Scheduler plan: run_single_candidate" in text, text
    assert calls == [
        (
            [
                "loopx",
                "--registry",
                "registry.json",
                "scheduler",
                "plan",
                "--format",
                "json",
                "--goal-id",
                "goal",
                "--agent-id",
                "agent",
            ],
            45,
        )
    ], calls


def assert_scheduler_next_batch_command_is_stable() -> None:
    calls: list[tuple[list[str], float]] = []

    def fake_run_json(args: list[str], *, timeout: float) -> dict[str, Any]:
        calls.append((args, timeout))
        return {
            "schema_version": "scheduler_next_batch_v0",
            "goal_id": "goal",
            "agent_id": "agent",
            "ready_to_dispatch": True,
            "dispatch_mode": "parallel_batch",
            "batch_size": 2,
            "worker_slots": [
                {"todo_id": "todo_docs", "agent_lane": "agent-a"},
                {"todo_id": "todo_view", "agent_lane": "agent-b"},
            ],
        }

    text = loopx_scheduler_next_batch_text(
        run_json=fake_run_json,
        loopx_bin="loopx",
        registry="registry.json",
        goal_id="goal",
        agent_id="agent",
        max_chars=1200,
    )
    assert "Next batch: parallel_batch" in text, text
    assert "Workers: todo_docs->agent-a, todo_view->agent-b" in text, text
    assert calls == [
        (
            [
                "loopx",
                "--registry",
                "registry.json",
                "scheduler",
                "next-batch",
                "--format",
                "json",
                "--goal-id",
                "goal",
                "--agent-id",
                "agent",
            ],
            45,
        )
    ], calls


def main() -> int:
    assert_help_exposes_next_batch_command()
    assert_scheduler_plan_command_is_stable()
    assert_scheduler_next_batch_command_is_stable()
    print("feishu bridge scheduler commands smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
