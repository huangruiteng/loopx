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
QUESTION = "如何提升 KNN holdout metric?"


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
    assert preset["baseline_source"] == "preset_fixture_not_question_text", preset
    assert preset["question_text_supplies_baseline"] is False, preset
    assert preset["metric_name"] == "holdout_metric", preset
    assert preset["baseline_metric"] == 1.0, preset

    worker_loop = payload["worker_loop"]
    assert worker_loop["selected_actions"] == [
        "write_research_contract",
        "propose_hypothesis",
        "run_dev_eval",
        "summarize_evidence",
    ], worker_loop
    assert all(turn.get("dev_metric") is None for turn in worker_loop["turns"]), worker_loop
    assert all(turn.get("holdout_metric") is None for turn in worker_loop["turns"]), worker_loop

    collective = payload["collective_research_rounds"]
    assert collective["multi_round_research_verified"] is False, collective
    assert collective["holdout_improvement_count"] == 0, collective
    assert collective["dev_metric_sequence"] == [], collective
    assert collective["holdout_metric_sequence"] == [], collective

    tonight = payload["tonight_experience"]
    assert tonight["positive_result"] is False, tonight
    assert tonight["dev_metric"] is None, tonight
    assert tonight["holdout_metric"] is None, tonight
    assert payload["public_boundary"]["raw_logs_recorded"] is False, payload
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
