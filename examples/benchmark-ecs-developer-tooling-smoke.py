#!/usr/bin/env python3
"""Smoke-test public ECS benchmark workflow developer tooling."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_json(args: list[str]) -> dict:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bootstrap = run_json(
            [
                "scripts/benchmark_ecs_bootstrap.py",
                "--workspace",
                str(tmp_path / "goal-harness-bench"),
                "--min-free-gib",
                "0",
                "--require",
                "python3",
                "--require",
                "git",
                "--optional",
                "docker",
                "--create-dirs",
            ]
        )
        assert bootstrap["schema_version"] == "benchmark_ecs_bootstrap_probe_v0"
        assert bootstrap["ready"] is True, bootstrap
        assert bootstrap["workspace"]["path_recorded"] is False
        assert bootstrap["boundary"]["raw_logs_read"] is False
        assert (tmp_path / "goal-harness-bench" / "sources").is_dir()

        launch = run_json(
            [
                "scripts/terminal_bench_no_upload_smoke.py",
                "--task-id",
                "hello-world",
                "--jobs-dir",
                str(tmp_path / "jobs"),
                "--run-root",
                str(tmp_path / "run"),
            ]
        )
        assert launch["schema_version"] == "terminal_bench_worker_materialization_probe_launch_v0"
        assert launch["dry_run"] is True
        assert launch["boundary"]["no_upload"] is True
        assert launch["boundary"]["raw_logs_read"] is False
        assert launch["developer_entrypoint"]["public_safe"] is True

        post_launch_path = tmp_path / "post_launch.public.json"
        post_launch_path.write_text(
            json.dumps(
                {
                    "schema_version": "terminal_bench_post_launch_materialization_v0",
                    "ready_for_compact_result_ingest": False,
                    "ready_for_compact_failure_marker": True,
                    "compact_failure_class": "detached_worker_ended_without_jobs_dir",
                    "first_blocker": "detached_worker_ended_without_jobs_dir",
                    "trial_result_present_count": 0,
                    "raw_logs_read": False,
                    "raw_task_text_read": False,
                    "trajectory_read": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        reduced = run_json(
            [
                "scripts/terminal_bench_compose_startup_reducer.py",
                "--post-launch-json",
                str(post_launch_path),
            ]
        )
        assert reduced["schema_version"] == "terminal_bench_compose_startup_reducer_v0"
        assert reduced["compose_startup_blocker"] is True
        assert reduced["next_action"] == "repair_terminal_bench_compose_startup"
        assert reduced["boundary"]["raw_logs_read"] is False
        assert reduced["boundary"]["private_paths_recorded"] is False

        skillsbench_prewarm = run_json(
            [
                "scripts/skillsbench_verifier_prewarm_plan.py",
                "--task-id",
                "hello-world",
            ]
        )
        assert (
            skillsbench_prewarm["schema_version"]
            == "skillsbench_verifier_dependency_prewarm_plan_v0"
        )
        assert skillsbench_prewarm["ready"] is True
        assert (
            skillsbench_prewarm["prewarm_blocker_label"]
            == "skillsbench_verifier_dependency_prewarm_required"
        )
        assert skillsbench_prewarm["oracle_sanity_contract"]["no_upload"] is True
        assert skillsbench_prewarm["oracle_sanity_contract"]["expected_reward"] == 1.0
        assert (
            "upstream_task_truth"
            in skillsbench_prewarm["prewarm_scope"]["forbidden"]
        )
        assert "uvx" in skillsbench_prewarm["dependency_contract"]["required_tools"]
        assert skillsbench_prewarm["boundary"]["raw_logs_recorded"] is False
        assert skillsbench_prewarm["boundary"]["remote_paths_recorded"] is False

    print("benchmark-ecs-developer-tooling-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
