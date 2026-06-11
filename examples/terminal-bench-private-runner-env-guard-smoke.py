#!/usr/bin/env python3
"""Smoke-test private Terminal-Bench runner auth env guardrails."""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import (  # noqa: E402
    build_terminal_bench_managed_harbor_command,
    build_terminal_bench_private_runner_env,
    build_terminal_bench_private_runner_launch,
    build_terminal_bench_task_material_readiness,
    normalize_terminal_bench_private_runner_invocation,
    resolve_terminal_bench_runner_binary,
    summarize_terminal_bench_post_launch_materialization,
    summarize_terminal_bench_private_runner_launch,
)
from goal_harness.status import compact_benchmark_run  # noqa: E402


def expect_raises(callable_obj, needle: str) -> None:
    try:
        callable_obj()
    except ValueError as exc:
        assert needle in str(exc), str(exc)
        return
    raise AssertionError(f"expected ValueError containing {needle!r}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="goal-harness-task-material-") as tmp:
        dataset = Path(tmp) / "terminal-bench-local"
        good_task = dataset / "good-task"
        good_task.mkdir(parents=True)
        (good_task / "task.toml").write_text('version = "1.0"\n', encoding="utf-8")
        (good_task / "instruction.md").write_text("fixture instruction\n", encoding="utf-8")
        bad_task = dataset / "bad-task"
        bad_task.mkdir(parents=True)
        (bad_task / "task.toml").write_text('version = "1.0"\n', encoding="utf-8")

        good_material = build_terminal_bench_task_material_readiness(
            dataset=str(dataset),
            task_id="good-task",
        )
        assert good_material["checked"] is True, good_material
        assert good_material["ready"] is True, good_material
        assert good_material["status"] == "ready", good_material
        assert good_material["raw_paths_recorded"] is False, good_material

        bad_material = build_terminal_bench_task_material_readiness(
            dataset=str(dataset),
            task_id="bad-task",
        )
        assert bad_material["checked"] is True, bad_material
        assert bad_material["ready"] is False, bad_material
        assert bad_material["first_blocker"] == "task_material_missing_instruction_md", bad_material

        bad_launch = build_terminal_bench_private_runner_launch(
            dataset=str(dataset),
            task_id="bad-task",
            jobs_dir="<private-jobs-dir>",
            job_name="terminal_bench_bad_material_env_guard_smoke",
            goal_harness_mode="codex_goal_harness",
            goal_harness_goal_id="goal-harness-meta",
            goal_harness_cli_bridge_enabled=True,
        )
        assert bad_launch["first_blocker"] == "task_material_missing_instruction_md", bad_launch
        assert bad_launch["ready"] is False, bad_launch
        bad_summary = summarize_terminal_bench_private_runner_launch(bad_launch)
        assert bad_summary["task_material_readiness_checked"] is True, bad_summary
        assert bad_summary["task_material_ready_required"] is False, bad_summary
        assert bad_summary["task_material_ready"] is False, bad_summary
        assert bad_summary["task_material_first_blocker"] == "task_material_missing_instruction_md", bad_summary
        assert bad_summary["raw_paths_recorded"] is False, bad_summary

        strict_unknown_launch = build_terminal_bench_private_runner_launch(
            dataset=str(dataset),
            task_id="missing-task",
            jobs_dir="<private-jobs-dir>",
            job_name="terminal_bench_missing_material_env_guard_smoke",
            goal_harness_mode="codex_goal_harness",
            goal_harness_goal_id="goal-harness-meta",
            goal_harness_cli_bridge_enabled=True,
            require_task_material_ready=True,
        )
        assert (
            strict_unknown_launch["first_blocker"]
            == "task_material_not_cached_or_not_locally_resolved"
        ), strict_unknown_launch
        assert strict_unknown_launch["ready"] is False, strict_unknown_launch
        strict_unknown_summary = summarize_terminal_bench_private_runner_launch(
            strict_unknown_launch
        )
        assert strict_unknown_summary["task_material_readiness_checked"] is False, strict_unknown_summary
        assert strict_unknown_summary["task_material_ready_required"] is True, strict_unknown_summary
        assert strict_unknown_summary["task_material_ready"] is None, strict_unknown_summary
        assert (
            strict_unknown_summary["task_material_readiness_status"]
            == "not_cached_or_not_locally_resolved"
        ), strict_unknown_summary
        assert strict_unknown_summary["raw_paths_recorded"] is False, strict_unknown_summary

    previous = os.environ.get("CODEX_FORCE_AUTH_JSON")
    os.environ["CODEX_FORCE_AUTH_JSON"] = "****"
    try:
        env = build_terminal_bench_private_runner_env()
    finally:
        if previous is None:
            os.environ.pop("CODEX_FORCE_AUTH_JSON", None)
        else:
            os.environ["CODEX_FORCE_AUTH_JSON"] = previous

    assert env.get("CODEX_FORCE_AUTH_JSON") != "****", env.get("CODEX_FORCE_AUTH_JSON")

    replay = normalize_terminal_bench_private_runner_invocation(
        [
            "uvx",
            "harbor",
            "run",
            "--agent-env",
            "CODEX_FORCE_AUTH_JSON=****",
        ]
    )
    assert "CODEX_FORCE_AUTH_JSON=true" in replay, replay
    assert "CODEX_FORCE_AUTH_JSON=****" not in replay, replay

    expect_raises(
        lambda: normalize_terminal_bench_private_runner_invocation(
            ["uvx", "--agent-env", "OPENAI_API_KEY=****"]
        ),
        "OPENAI_API_KEY",
    )
    expect_raises(
        lambda: normalize_terminal_bench_private_runner_invocation(
            ["uvx", "--agent-env", "CODEX_FORCE_AUTH_JSON=sk-placeholder"]
        ),
        "CODEX_FORCE_AUTH_JSON",
    )

    generated = build_terminal_bench_managed_harbor_command(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_env_guard_smoke",
        goal_harness_mode="codex_goal_harness",
        goal_harness_goal_id="goal-harness-meta",
        goal_harness_cli_bridge_enabled=True,
        agent_timeout_multiplier=4,
    )
    assert "CODEX_FORCE_AUTH_JSON=true" in generated, generated
    assert "CODEX_FORCE_AUTH_JSON=****" not in generated, generated

    baseline_generated = build_terminal_bench_managed_harbor_command(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_hardened_baseline_env_guard_smoke",
        goal_harness_mode="hardened_codex_baseline",
        goal_harness_ablation_mode="hardened_codex_baseline",
        goal_harness_access_packet_mode="none",
        goal_harness_cli_bridge_enabled=False,
        agent_timeout_multiplier=4,
    )
    assert "--agent-import-path" in baseline_generated, baseline_generated
    assert "goal_harness_mode=hardened_codex_baseline" in baseline_generated, baseline_generated
    assert "goal_harness_access_packet_mode=none" in baseline_generated, baseline_generated
    assert "goal_harness_cli_bridge_enabled=true" not in baseline_generated, baseline_generated
    assert "--mounts" not in baseline_generated, baseline_generated
    assert "CODEX_FORCE_AUTH_JSON=true" in baseline_generated, baseline_generated

    launch = build_terminal_bench_private_runner_launch(
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_env_guard_smoke",
        goal_harness_mode="codex_goal_harness",
        goal_harness_goal_id="goal-harness-meta",
        goal_harness_cli_bridge_enabled=True,
        agent_timeout_multiplier=4,
    )
    assert launch["schema_version"] == "terminal_bench_private_runner_launch_v0", launch
    assert launch["uses_private_runner_env"] is True, launch
    assert launch["argv"][0] == resolve_terminal_bench_runner_binary("uvx"), launch["argv"]
    assert launch["env"]["PATH"] == env["PATH"], launch["env"]["PATH"]
    for expected_path in ("~/.local/bin", "/opt/homebrew/bin", "/usr/local/bin"):
        expected_path = str(Path(expected_path).expanduser())
        assert expected_path in launch["env"]["PATH"], launch["env"]["PATH"]
    assert launch["env"].get("CODEX_FORCE_AUTH_JSON") != "****", launch["env"].get("CODEX_FORCE_AUTH_JSON")
    assert launch["preflight_surface"]["boundary"]["no_upload"] is True, launch
    assert launch["ready"] == (
        launch["first_blocker"] == "ready_for_private_managed_no_upload_pilot_review"
    ), launch
    summary = summarize_terminal_bench_private_runner_launch(launch)
    assert summary["ready"] == launch["ready"], summary
    assert summary["first_blocker"] == launch["first_blocker"], summary
    assert summary["task_material_ready_required"] is False, summary
    assert summary["no_upload_boundary"] is True, summary
    assert summary["submit_eligible"] is False, summary
    assert summary["agent_name"] == "", summary
    assert summary["agent_import_path_present"] is True, summary
    assert summary["goal_harness_agent_kwargs_present"] is True, summary
    assert summary["goal_harness_worker_bridge_requested"] is True, summary

    missing_materialization = summarize_terminal_bench_post_launch_materialization(
        "<private-jobs-dir>",
        job_name="terminal_bench_env_guard_smoke",
    )
    assert missing_materialization["checked"] is False, missing_materialization
    assert missing_materialization["ready_for_launch_state"] is False, missing_materialization
    assert missing_materialization["first_blocker"] == "jobs_dir_placeholder", missing_materialization
    assert missing_materialization["raw_paths_recorded"] is False, missing_materialization

    with tempfile.TemporaryDirectory(prefix="goal-harness-post-launch-") as tmp:
        jobs_dir = Path(tmp) / "jobs"
        job_root = jobs_dir / "terminal_bench_env_guard_smoke"
        job_root.mkdir(parents=True)
        job_root_pollable = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
        )
        assert job_root_pollable["jobs_dir_present"] is True, job_root_pollable
        assert job_root_pollable["job_root_present"] is True, job_root_pollable
        assert job_root_pollable["job_lock_present"] is False, job_root_pollable
        assert job_root_pollable["ready_for_launch_state"] is False, job_root_pollable
        assert job_root_pollable["first_blocker"] == "job_lock_missing", job_root_pollable

        blocked_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "benchmark",
                "summarize-post-launch",
                "terminal-bench",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "terminal_bench_env_guard_smoke",
                "--require-ready-for-launch-state",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert blocked_cli.returncode == 1, blocked_cli.stdout + blocked_cli.stderr
        blocked_payload = json.loads(blocked_cli.stdout)
        assert blocked_payload["ok"] is False, blocked_payload
        assert blocked_payload["first_blocker"] == "job_lock_missing", blocked_payload
        assert str(jobs_dir) not in blocked_cli.stdout, blocked_cli.stdout

        (job_root / "lock.json").write_text("{}\n", encoding="utf-8")
        job_root_pollable = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
        )
        assert job_root_pollable["job_lock_present"] is True, job_root_pollable
        assert job_root_pollable["ready_for_launch_state"] is True, job_root_pollable
        assert job_root_pollable["ready_for_compact_result_ingest"] is False, job_root_pollable
        assert job_root_pollable["first_blocker"] == "ready_for_compact_polling", job_root_pollable
        assert job_root_pollable["raw_logs_read"] is False, job_root_pollable
        ready_cli = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "benchmark",
                "summarize-post-launch",
                "terminal-bench",
                "--jobs-dir",
                str(jobs_dir),
                "--job-name",
                "terminal_bench_env_guard_smoke",
                "--require-ready-for-launch-state",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ready_cli.returncode == 0, ready_cli.stdout + ready_cli.stderr
        ready_payload = json.loads(ready_cli.stdout)
        assert ready_payload["ok"] is True, ready_payload
        assert ready_payload["ready_for_launch_state"] is True, ready_payload
        assert ready_payload["raw_paths_recorded"] is False, ready_payload
        assert str(jobs_dir) not in ready_cli.stdout, ready_cli.stdout

        (job_root / "result.json").write_text("{}\n", encoding="utf-8")
        trial_root = job_root / "good-task__trial"
        trial_root.mkdir()
        (trial_root / "result.json").write_text("{}\n", encoding="utf-8")
        job_root_complete = summarize_terminal_bench_post_launch_materialization(
            jobs_dir,
            job_name="terminal_bench_env_guard_smoke",
        )
        assert job_root_complete["ready_for_launch_state"] is True, job_root_complete
        assert job_root_complete["ready_for_compact_result_ingest"] is True, job_root_complete
        assert job_root_complete["trial_result_present_count"] == 1, job_root_complete
        assert job_root_complete["first_blocker"] == "ready_for_compact_result_ingest", job_root_complete

        summary_with_materialization = summarize_terminal_bench_private_runner_launch(
            launch,
            post_launch_materialization=job_root_complete,
        )
        nested = summary_with_materialization["post_launch_materialization"]
        assert nested["schema_version"] == "terminal_bench_post_launch_materialization_v0", nested
        assert nested["ready_for_launch_state"] is True, nested
        assert nested["raw_paths_recorded"] is False, nested
        compact = compact_benchmark_run(
            {
                "schema_version": "benchmark_run_v0",
                "private_runner_launch_summary": summary_with_materialization,
            }
        )
        compact_nested = compact["private_runner_launch_summary"][
            "post_launch_materialization"
        ]
        assert compact_nested["ready_for_launch_state"] is True, compact_nested
        assert compact_nested["raw_paths_recorded"] is False, compact_nested

    baseline_launch = build_terminal_bench_private_runner_launch(
        mode="hardened-codex",
        jobs_dir="<private-jobs-dir>",
        job_name="terminal_bench_hardened_baseline_env_guard_smoke",
        agent_timeout_multiplier=4,
    )
    assert baseline_launch["argv"][0] == resolve_terminal_bench_runner_binary("uvx"), baseline_launch["argv"]
    assert "--agent-import-path" in baseline_launch["argv"], baseline_launch["argv"]
    assert "goal_harness_mode=hardened_codex_baseline" in baseline_launch["argv"], baseline_launch["argv"]
    assert "--mounts" not in baseline_launch["argv"], baseline_launch["argv"]
    baseline_summary = summarize_terminal_bench_private_runner_launch(baseline_launch)
    assert baseline_summary["ready"] == baseline_launch["ready"], baseline_summary
    assert baseline_summary["first_blocker"] == baseline_launch["first_blocker"], baseline_summary
    assert baseline_summary["no_upload_boundary"] is True, baseline_summary
    assert baseline_summary["submit_eligible"] is False, baseline_summary
    assert baseline_summary["agent_import_path_present"] is True, baseline_summary
    assert baseline_summary["goal_harness_agent_kwargs_present"] is True, baseline_summary
    assert baseline_summary["goal_harness_worker_bridge_requested"] is False, baseline_summary

    expect_raises(
        lambda: build_terminal_bench_managed_harbor_command(
            goal_harness_mode="goal_harness_managed_codex",
            goal_harness_cli_bridge_enabled=True,
        ),
        "codex_goal_harness",
    )


if __name__ == "__main__":
    main()
