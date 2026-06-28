#!/usr/bin/env python3
"""Smoke-test SkillsBench canonical task-source preflight."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_ledger import load_benchmark_run_ledger  # noqa: E402
from scripts.skillsbench_automation_loop import (  # noqa: E402
    build_plan,
    main as skillsbench_automation_loop_main,
    parse_args,
)


def _write_task(root: Path, relative: str) -> None:
    task = root / relative
    dockerfile = task / "environment" / "Dockerfile"
    dockerfile.parent.mkdir(parents=True, exist_ok=True)
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    (task / "task.toml").write_text('version = "1.1"\n', encoding="utf-8")


def test_sanity_task_source_fails_before_runner_spend() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-task-source-") as tmp:
        root = Path(tmp)
        skillsbench_root = root / "skillsbench"
        _write_task(skillsbench_root, "experiments/sanity-tasks/hello-world")
        _write_task(skillsbench_root, "tasks/citation-check")
        _write_task(skillsbench_root, "tasks/powerlifting-coef-calc")

        jobs = root / "jobs"
        ledger = root / "ledger.json"
        args = [
            "--task-id",
            "hello-world",
            "--route",
            "raw-codex-autonomous-max5",
            "--skillsbench-root",
            str(skillsbench_root),
            "--jobs-dir",
            str(jobs),
            "--job-name",
            "skillsbench-hello-world-task-source-preflight",
            "--run-group-id",
            "skillsbench-hello-world-task-source-preflight",
            "--ledger-path",
            str(ledger),
            "--update-ledger",
        ]
        plan = build_plan(parse_args(args))
        preflight = plan["task_setup_preflight"]
        assert preflight["status"] == "task_missing_from_canonical_tasks", preflight
        assert preflight["canonical_task_present"] is False, preflight
        assert preflight["alternate_source_kind"] == "experiments_sanity_tasks", (
            preflight
        )
        assert preflight["task_source_path_recorded"] is False, preflight
        assert preflight["task_source_content_recorded"] is False, preflight
        assert preflight["nearest_canonical_task_ids"] == [
            "citation-check",
            "powerlifting-coef-calc",
        ], preflight

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = skillsbench_automation_loop_main(args)

        assert rc == 0, stderr.getvalue()
        compact_path = (
            jobs
            / "skillsbench-hello-world-task-source-preflight"
            / "hello-world__raw_codex_autonomous_max5"
            / "benchmark_run.compact.json"
        )
        compact = json.loads(compact_path.read_text(encoding="utf-8"))
        assert compact["first_blocker"] == "skillsbench_task_source_preflight_blocked"
        assert compact["score_failure_attribution"] == (
            "skillsbench_task_source_preflight_blocked"
        )
        assert compact["task_setup_preflight"]["status"] == (
            "task_missing_from_canonical_tasks"
        )
        assert compact["task_setup_preflight"]["alternate_source_kind"] == (
            "experiments_sanity_tasks"
        )
        assert compact["validation"]["no_raw_task_text_read"] is True, compact

        update = load_benchmark_run_ledger(ledger)
        case = update["benchmarks"]["skillsbench@1.1"]["cases"]["hello-world"]
        assert case["latest_decision"]["decision"] == (
            "baseline_task_source_preflight_selection_required"
        ), case
        assert case["runs"][0]["repair_class"] == (
            "skillsbench_task_source_preflight_selection"
        )


if __name__ == "__main__":
    test_sanity_task_source_fails_before_runner_spend()
    print("skillsbench-task-source-preflight-smoke ok")
