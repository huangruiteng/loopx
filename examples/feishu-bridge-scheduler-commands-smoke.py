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
from loopx.capabilities.lark.bridge_requests import (  # noqa: E402
    build_feishu_request_todo_args,
    feishu_request_lane,
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
        agent_id="",
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
            ],
            45,
        )
    ], calls


def assert_feishu_request_todos_get_stable_parallel_lanes() -> None:
    first_args, first_text, first_lane = build_feishu_request_todo_args(
        request_text="write the docs",
        message_id="om_first",
        goal_id="goal",
        agent_id="codex-devbox",
    )
    second_args, _, second_lane = build_feishu_request_todo_args(
        request_text="write the docs",
        message_id="om_second",
        goal_id="goal",
        agent_id="codex-devbox",
    )
    repeated_lane = feishu_request_lane(
        agent_id="codex-devbox",
        message_id="om_first",
        request_text=first_text,
    )
    assert first_lane == repeated_lane, (first_lane, repeated_lane)
    assert first_lane.startswith("codex-devbox-req-"), first_lane
    assert second_lane.startswith("codex-devbox-req-"), second_lane
    assert first_lane != second_lane, (first_lane, second_lane)
    assert first_args[-2:] == ["--claimed-by", first_lane], first_args
    assert "--safety-class" in first_args and "read_only" in first_args, first_args
    assert "before writes or external actions" in first_args[first_args.index("--text") + 1], first_args


def main() -> int:
    assert_help_exposes_next_batch_command()
    assert_scheduler_plan_command_is_stable()
    assert_scheduler_next_batch_command_is_stable()
    assert_feishu_request_todos_get_stable_parallel_lanes()
    print("feishu bridge scheduler commands smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
