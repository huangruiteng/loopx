#!/usr/bin/env python3
"""Smoke-test the KNN preset does not imply fake continuation metrics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION = "如何提升 KNN 精确近邻检索速度?"


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        registry = temp / "registry.global.json"
        runtime_root = temp / "runtime"
        workspace = temp / "workspace"
        workspace.mkdir()
        registry.write_text(
            json.dumps({"common_runtime_root": str(runtime_root), "goals": []}),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime_root),
                "--format",
                "json",
                "auto-research",
                "start",
                QUESTION,
                "--preset",
                "knn-demo",
                "--language",
                "zh",
                "--execute",
                "--headless",
                "--worker-loop-rounds",
                "1",
            ],
            cwd=workspace,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"knn preset start failed rc={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        payload = json.loads(result.stdout)

    preset = payload["preset_context"]
    assert preset["preset_id"] == "knn-demo", preset
    assert preset["baseline_source"] == "generated_knn_benchmark_workspace", preset
    assert preset["question_text_supplies_baseline"] is False, preset
    assert preset["metric_name"] == "speedup", preset
    assert preset["baseline_metric"] == 1.0, preset
    assert preset["editable_scope"] == ["solution.py"], preset
    assert preset["protected_scope"] == ["task.py", "eval.py", "eval.sh"], preset
    assert preset["dev_eval_command"] == "bash eval.sh dev", preset
    assert preset["holdout_eval_command"] == "bash eval.sh test", preset

    worker_loop = payload["worker_loop"]
    assert worker_loop["selected_actions"] == [
        "write_research_contract",
        "propose_hypothesis",
        "run_dev_eval",
    ], worker_loop
    evaluator_turn = next(
        turn for turn in worker_loop["turns"] if turn["agent_id"] == "evaluator-promoter"
    )
    assert evaluator_turn["mode"] == "no_action", worker_loop
    assert evaluator_turn["selected_action"] is None, worker_loop
    assert all(turn.get("dev_metric") is None for turn in worker_loop["turns"]), worker_loop
    assert all(turn.get("holdout_metric") is None for turn in worker_loop["turns"]), worker_loop

    collective = payload["collective_research_rounds"]
    assert collective["multi_round_research_verified"] is False, collective
    assert collective["holdout_improvement_count"] == 0, collective
    assert collective["dev_metric_sequence"] == [], collective
    assert collective["holdout_metric_sequence"] == [], collective

    tonight = payload["tonight_experience"]
    assert tonight["positive_result"] is False, tonight
    assert tonight["ready"] is False, tonight
    assert tonight["positive_result_basis"] == "requires_visible_lane_authored_evidence", tonight
    assert tonight["dev_metric"] is None, tonight
    assert tonight["holdout_metric"] is None, tonight
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
