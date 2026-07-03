#!/usr/bin/env python3
"""Smoke-test KNN-style auto-research continuation through role-declared todos."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loopx.capabilities.auto_research.demo_e2e import run_auto_research_demo_e2e  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.global.json"
        runtime_root = temp / "runtime"
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )

        payload = run_auto_research_demo_e2e(
            agent_id="auto-research-operator",
            goal_id="loopx-auto-research-demo-knn-continuation-smoke",
            tracking_goal_id=None,
            objective=(
                "Can a simple KNN baseline improve through multi-agent auto research "
                "without leaking holdout claims?"
            ),
            output_dir="auto_research_lightweight_kernel",
            execute=True,
            run_worker_loop=True,
            worker_loop_rounds=4,
            launch_visible=False,
            keep_workspace=False,
            registry_path=registry,
            runtime_root_arg=str(runtime_root),
            session_name="loopx-ar-knn-continuation-smoke",
            cli_bin="loopx",
            codex_bin="codex",
            tmux_bin="tmux",
            reasoning_effort="high",
            live_evidence_path=None,
            append_evidence=lambda _packet: {},
        )

    worker_loop = payload["worker_loop"]
    actions = worker_loop["selected_actions"]
    assert "run_dev_eval" in actions, actions
    assert "run_holdout_eval" in actions, actions
    assert "write_evaluation_summary" in actions, actions
    assert worker_loop["executed_turn_count"] >= 6, worker_loop
    holdout_turns = [
        turn
        for turn in worker_loop["turns"]
        if turn.get("selected_action") == "run_holdout_eval"
    ]
    assert holdout_turns, worker_loop
    assert holdout_turns[0]["holdout_metric"] == 4.5, holdout_turns
    assert holdout_turns[0]["live_evidence_written"] is True, holdout_turns
    tonight = payload["tonight_experience"]
    assert tonight["coordination_pattern"] == "decentralized_state_a2a", tonight
    assert tonight["dev_metric"] == 4.0, tonight
    assert tonight["holdout_metric"] == 4.5, tonight
    assert tonight["positive_result"] is True, tonight
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
