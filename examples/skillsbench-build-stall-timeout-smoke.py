"""Smoke-test SkillsBench build/setup stall timeout policy."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.skillsbench_automation_loop import (
    build_plan,
    build_runner_failure_compact,
    parse_args,
)
from scripts.skillsbench_runner_constants import DEFAULT_BUILD_STALL_TIMEOUT_SEC


def assert_prerequisites_include(
    actual: dict[str, Any], expected: dict[str, Any]
) -> None:
    for key, value in expected.items():
        assert actual.get(key) == value, (key, actual)


def test_skillsbench_runner_failure_marks_build_stall_timeout() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-build-stall-") as tmp:
        default_args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "default-jobs"),
                "--job-name",
                "skillsbench-organize-messy-files-default-build-stall-fixture",
            ]
        )
        default_plan = build_plan(default_args)
        assert default_plan["build_stall_timeout_requested_sec"] == (
            DEFAULT_BUILD_STALL_TIMEOUT_SEC
        )
        assert default_plan["build_stall_timeout_sec"] == (
            DEFAULT_BUILD_STALL_TIMEOUT_SEC
        )
        assert default_plan["runner_prerequisites"][
            "benchflow_setup_stall_timeout_enabled"
        ] is True
        assert "benchflow_setup_stall_timeout_capped" not in default_plan[
            "runner_prerequisites"
        ]

        disabled_args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "disabled-jobs"),
                "--job-name",
                "skillsbench-organize-messy-files-disabled-build-stall-fixture",
                "--build-stall-timeout-sec",
                "0",
            ]
        )
        disabled_plan = build_plan(disabled_args)
        assert disabled_plan["build_stall_timeout_requested_sec"] == 0
        assert disabled_plan["build_stall_timeout_sec"] == 0
        assert disabled_plan["runner_prerequisites"][
            "benchflow_setup_stall_timeout_enabled"
        ] is False

        args = parse_args(
            [
                "--task-id",
                "organize-messy-files",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-organize-messy-files-build-stall-fixture",
                "--build-stall-timeout-sec",
                "60",
            ]
        )
        plan = build_plan(args)

        compact = build_runner_failure_compact(
            args,
            plan,
            asyncio.TimeoutError(
                "skillsbench docker compose build/setup stall timeout before agent lifecycle"
            ),
        )

        assert compact["first_blocker"] == (
            "skillsbench_docker_compose_build_stall_timeout"
        ), compact
        assert compact["score_failure_attribution"] == (
            "skillsbench_docker_compose_build_stall_timeout"
        ), compact
        assert "skillsbench_environment_setup_error" in compact[
            "failure_attribution_labels"
        ], compact
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "benchflow_run_stage": "build_or_setup_stall_before_agent",
                "benchflow_setup_stall_timeout_enabled": True,
                "benchflow_setup_stall_timeout_requested_sec": 60,
                "benchflow_setup_stall_timeout_sec": 60,
                "benchflow_setup_stall_timeout_triggered": True,
                "benchflow_setup_stall_before_agent_lifecycle": True,
                "benchflow_setup_stall_raw_logs_read": False,
            },
        )
        assert compact["compose_setup_diagnostic"]["status"] == (
            "compose_setup_blocked_before_agent_rounds"
        ), compact
        assert compact["compose_setup_diagnostic"][
            "case_attempt_budget_should_count"
        ] is False, compact
        assert compact["compose_setup_diagnostic"][
            "setup_stall_timeout_requested_sec"
        ] == 60, compact
        assert compact["compose_setup_diagnostic"]["setup_stall_timeout_sec"] == 60
        assert "setup_stall_timeout_capped" not in compact[
            "compose_setup_diagnostic"
        ]
        compact_text = json.dumps(compact, sort_keys=True)
        assert "skillsbench docker compose build/setup stall timeout" not in compact_text
        assert "/private/" not in compact_text


def test_skillsbench_runner_failure_honors_long_build_stall_timeout() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-build-stall-long-") as tmp:
        args = parse_args(
            [
                "--task-id",
                "flink-query",
                "--route",
                "loopx-product-mode",
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--job-name",
                "skillsbench-flink-query-build-stall-long-fixture",
                "--build-stall-timeout-sec",
                "7200",
            ]
        )
        plan = build_plan(args)
        assert plan["build_stall_timeout_requested_sec"] == 7200
        assert plan["build_stall_timeout_sec"] == 7200
        assert "benchflow_setup_stall_timeout_capped" not in plan[
            "runner_prerequisites"
        ]

        compact = build_runner_failure_compact(
            args,
            plan,
            asyncio.TimeoutError(
                "skillsbench docker compose build/setup stall timeout before agent lifecycle"
            ),
        )

        assert compact["first_blocker"] == (
            "skillsbench_docker_compose_build_stall_timeout"
        ), compact
        assert_prerequisites_include(
            compact["runner_prerequisites"],
            {
                "benchflow_setup_stall_timeout_enabled": True,
                "benchflow_setup_stall_timeout_requested_sec": 7200,
                "benchflow_setup_stall_timeout_sec": 7200,
                "benchflow_setup_stall_timeout_triggered": True,
                "benchflow_setup_stall_before_agent_lifecycle": True,
            },
        )
        assert compact["compose_setup_diagnostic"][
            "setup_stall_timeout_requested_sec"
        ] == 7200, compact
        assert compact["compose_setup_diagnostic"]["setup_stall_timeout_sec"] == 7200
        assert "setup_stall_timeout_capped" not in compact[
            "compose_setup_diagnostic"
        ]
        compact_text = json.dumps(compact, sort_keys=True)
        assert "skillsbench docker compose build/setup stall timeout" not in compact_text
        assert "/private/" not in compact_text


def main() -> None:
    test_skillsbench_runner_failure_marks_build_stall_timeout()
    test_skillsbench_runner_failure_honors_long_build_stall_timeout()


if __name__ == "__main__":
    main()
