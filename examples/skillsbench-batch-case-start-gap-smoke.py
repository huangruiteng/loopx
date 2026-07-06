#!/usr/bin/env python3
"""Smoke-test SkillsBench batch case start pacing."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import skillsbench_automation_loop as runner


def _assert_batch_case_start_gap_is_enforced() -> None:
    starts: list[tuple[str, float]] = []
    original_async_main = runner.async_main
    original_build_plan = runner.build_plan

    async def fake_async_main(
        args: Any,
        *,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        starts.append((str(args.task_id), time.monotonic()))
        await asyncio.sleep(0)
        return {
            "ok": True,
            "task_id": str(args.task_id),
            "launch_plan": plan or {},
        }

    try:
        runner.async_main = fake_async_main
        runner.build_plan = lambda args: {"task_id": str(args.task_id)}
        args = runner.parse_args(
            [
                "--task-ids",
                "case-a,case-b,case-c",
                "--parallel-cases",
                "1",
                "--batch-case-start-gap-sec",
                "0.05",
            ]
        )
        payload = asyncio.run(runner.async_batch_main(args))
    finally:
        runner.async_main = original_async_main
        runner.build_plan = original_build_plan

    assert payload["ok"] is True, payload
    assert payload["case_start_gap_sec"] == 0.05, payload
    assert [task_id for task_id, _started_at in starts] == [
        "case-a",
        "case-b",
        "case-c",
    ], starts
    deltas = [
        starts[index][1] - starts[index - 1][1]
        for index in range(1, len(starts))
    ]
    assert all(delta >= 0.04 for delta in deltas), deltas
    assert [result["batch_case_start_gap_sec"] for result in payload["results"]] == [
        0.05,
        0.05,
        0.05,
    ], payload["results"]
    assert (
        payload["results"][0]["batch_case_start_wait_sec"] == 0.0
    ), payload["results"]
    assert all(
        result["batch_case_start_wait_sec"] > 0
        for result in payload["results"][1:]
    ), payload["results"]


def _assert_start_gap_round_trips_to_child_cli() -> None:
    args = runner.parse_args(
        [
            "--task-ids",
            "case-a,case-b",
            "--parallel-cases",
            "2",
            "--batch-case-start-gap-sec",
            "12.5",
        ]
    )
    case_args = runner._clone_args_for_batch_case(
        args,
        task_id="case-a",
        index=0,
        total=2,
        run_group_id="batch-gap-smoke",
    )
    cli = runner._batch_case_args_to_cli(case_args)
    gap_index = cli.index("--batch-case-start-gap-sec")
    assert cli[gap_index + 1] == "12.5", cli
    parallel_index = cli.index("--parallel-cases")
    assert cli[parallel_index + 1] == "1", cli


def main() -> int:
    _assert_batch_case_start_gap_is_enforced()
    _assert_start_gap_round_trips_to_child_cli()
    print("skillsbench batch case start gap smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
