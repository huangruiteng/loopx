#!/usr/bin/env python3
"""Smoke-test SkillsBench product-mode live lifecycle counter gating."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.skillsbench_automation_loop import (  # noqa: E402
    _merge_round_result_trajectory_lifecycle_summary,
    _product_mode_depth_gate_satisfied,
)


class FakeRoundResult:
    trajectory = [
        {
            "type": "tool_call",
            "title": "/app/.local/bin/loopx quota should-run --goal-id case --agent-id codex-benchmark-agent",
            "status": "completed",
        },
        {
            "type": "tool_call",
            "title": "/app/.local/bin/loopx todo update --goal-id case --todo-id todo_case --status open",
            "status": "completed",
        },
    ]


def main() -> None:
    trace = {"loopx_state_reads": 0, "loopx_state_writes": 0}
    assert not _product_mode_depth_gate_satisfied(trace)
    _merge_round_result_trajectory_lifecycle_summary(FakeRoundResult(), trace)
    assert trace["round_result_trajectory_lifecycle_summary_present"] is True
    assert trace["round_result_loopx_cli_state_read_count"] == 1
    assert trace["round_result_loopx_cli_state_write_count"] == 1
    assert _product_mode_depth_gate_satisfied(trace)


if __name__ == "__main__":
    main()
