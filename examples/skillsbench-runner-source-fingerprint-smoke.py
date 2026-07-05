#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.skillsbench_automation_loop as skillsbench_loop  # noqa: E402
from scripts.skillsbench_automation_loop import build_plan, parse_args  # noqa: E402


def repo_head() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_expected_head_match_is_public_safe() -> None:
    head = repo_head()
    args = parse_args(
        [
            "--route",
            "codex-cli-goal-baseline",
            "--expected-loopx-git-head",
            head[:12],
        ]
    )
    plan = build_plan(args)
    fingerprint = plan["loopx_runner_source_fingerprint"]
    assert fingerprint["status"] == "matched_expected", fingerprint
    assert fingerprint["matches_expected"] is True, fingerprint
    public = skillsbench_loop._public_runner_prerequisites(
        plan["runner_prerequisites"]
    )
    assert public["loopx_runner_source_git_head"] == head
    assert public["loopx_runner_source_matches_expected"] is True
    assert public["loopx_runner_source_path_recorded"] is False
    assert public["loopx_runner_source_raw_git_output_recorded"] is False


def test_expected_head_mismatch_fails_before_benchflow() -> None:
    args = parse_args(
        [
            "--route",
            "codex-cli-goal-baseline",
            "--expected-loopx-git-head",
            "0" * 40,
        ]
    )
    plan = build_plan(args)
    assert plan["runner_prerequisites"]["loopx_runner_source_first_blocker"] == (
        "loopx_runner_source_git_head_mismatch"
    )
    config = skillsbench_loop._public_runner_config(plan)
    assert config["loopx_runner_source_fingerprint_status"] == (
        "mismatched_expected"
    )
    assert config["loopx_runner_source_matches_expected"] is False
    try:
        asyncio.run(skillsbench_loop.run_benchflow_case(args, plan))
    except RuntimeError as exc:
        assert "loopx_runner_source_git_head_mismatch" in str(exc)
    else:
        raise AssertionError("stale source should fail before BenchFlow import")
    assert plan["runner_prerequisites"]["benchflow_run_stage"] == (
        "runner_source_fingerprint_check"
    )


def main() -> None:
    test_expected_head_match_is_public_safe()
    test_expected_head_mismatch_fails_before_benchflow()
    print("skillsbench-runner-source-fingerprint-smoke: ok")


if __name__ == "__main__":
    main()
