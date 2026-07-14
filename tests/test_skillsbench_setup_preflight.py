from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from loopx.benchmark_adapters.skillsbench_codex_runtime import preflight_required
from loopx.benchmark_adapters.skillsbench_setup_preflight import (
    run_setup_only_public_preflight,
)
from scripts.skillsbench_automation_loop import build_plan, parse_args


class FakeRollout:
    failure_stage = ""
    failure: Exception | None = None
    events: list[str] = []

    def __init__(self) -> None:
        self._rollout_dir: object | None = None
        self.env: object | None = None

    @classmethod
    async def create(cls, _config: Any) -> "FakeRollout":
        cls.events.append("create")
        if cls.failure_stage == "rollout_create" and cls.failure is not None:
            raise cls.failure
        return cls()

    async def setup(self) -> None:
        self.events.append("setup")
        if self.failure_stage == "rollout_setup" and self.failure is not None:
            raise self.failure
        self._rollout_dir = object()
        self.env = object()

    async def start(self) -> None:
        self.events.append("start")
        if self.failure_stage == "environment_start" and self.failure is not None:
            raise self.failure

    async def cleanup(self) -> None:
        self.events.append("cleanup")
        if self.failure_stage == "cleanup" and self.failure is not None:
            raise self.failure


@pytest.fixture(autouse=True)
def reset_fake_rollout() -> None:
    FakeRollout.failure_stage = ""
    FakeRollout.failure = None
    FakeRollout.events = []


def run_preflight() -> dict[str, Any]:
    return asyncio.run(
        run_setup_only_public_preflight(
            rollout_type=FakeRollout,
            config=object(),
            task_staging={
                "apt_retry_patch_applied": True,
                "dockerfile_pip_bootstrap_patch_applied": True,
                "unrelated": "/private/should-not-project",
            },
            setup_preflight={
                "apt_setup_risk_detected": True,
                "dockerfile_pip_install_risk_detected": True,
                "verifier_bootstrap_risk_detected": False,
            },
            stage_timeout_sec=1,
        )
    )


def test_setup_only_preflight_stops_before_agent_and_verifier() -> None:
    result = run_preflight()

    assert result["status"] == "passed"
    assert result["stage"] == "environment_ready_before_agent"
    assert result["job_root_materialized"] is True
    assert result["environment_object_materialized"] is True
    assert result["environment_started"] is True
    assert result["agent_install_invoked"] is False
    assert result["agent_execution_invoked"] is False
    assert result["verifier_invoked"] is False
    assert result["patch_hits"] == [
        "apt_retry",
        "dockerfile_pip_bootstrap",
    ]
    assert FakeRollout.events == ["create", "setup", "start", "cleanup"]
    serialized = json.dumps(result, sort_keys=True)
    assert "/private/" not in serialized
    assert "should-not-project" not in serialized


def test_setup_only_runner_mode_bypasses_formal_round_budget() -> None:
    args = parse_args(
        [
            "--task-id",
            "flink-query",
            "--route",
            "loopx-goal-start-product-mode",
            "--setup-only-public-preflight",
            "--max-rounds",
            "1",
        ]
    )

    plan = build_plan(args)
    assert args.setup_only_public_preflight is True
    assert plan["setup_only_public_preflight"] is True
    assert plan["setup_only_public_preflight_json"].endswith(
        "setup_only_preflight.public.json"
    )


def test_launcher_syncs_setup_only_public_artifact() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "skillsbench-launch-goal-xhigh.sh"
    ).read_text(encoding="utf-8")

    assert (
        '--remote-public-artifact-glob "${job_name}*/setup_only_preflight.public.json"'
        in source
    )
    closeout_guard = 'if [[ "$setup_only_public_preflight" != "1" ]]; then'
    assert closeout_guard in source
    assert source.index(closeout_guard) < source.index("--local-run-ledger-path")


def test_setup_only_mode_does_not_require_host_codex_preflight() -> None:
    args = parse_args(
        [
            "--task-id",
            "flink-query",
            "--route",
            "loopx-goal-start-product-mode",
            "--setup-only-public-preflight",
            "--host-local-acp-launch",
        ]
    )

    assert preflight_required(args) is False
    plan = build_plan(args)
    assert plan["codex_api_egress_preflight"]["status"] == "not_required"


@pytest.mark.parametrize(
    ("message", "category", "dependency_classes"),
    [
        (
            "Docker compose command failed. ERROR: failed to solve: process "
            "/bin/sh -c apt-get update did not complete successfully: "
            "failed to fetch package index",
            "skillsbench_docker_compose_apt_repository_failure",
            ["system_package"],
        ),
        (
            "Docker compose command failed. ERROR: failed to solve: process "
            "/bin/sh -c pip3 install numpy did not complete successfully: "
            "max retries exceeded for pypi.org",
            "skillsbench_docker_compose_pip_bootstrap_failure",
            ["python_package"],
        ),
        (
            "Docker compose command failed: invalid mount config for type "
            "bind: bind source path does not exist",
            "skillsbench_docker_compose_volume_mount_failure",
            [],
        ),
    ],
)
def test_setup_only_preflight_classifies_public_setup_failures(
    message: str,
    category: str,
    dependency_classes: list[str],
) -> None:
    FakeRollout.failure_stage = "environment_start"
    FakeRollout.failure = RuntimeError(message)

    result = run_preflight()

    assert result["status"] == "failed"
    assert result["failure_stage"] == "environment_start"
    assert result["failure_category"] == category
    assert result["dependency_classes"] == dependency_classes
    assert result["exit_category"] == "setup_command_failed"
    assert result["cleanup_status"] == "completed"
    serialized = json.dumps(result, sort_keys=True)
    assert message not in serialized
    assert result["raw_error_recorded"] is False
    assert result["raw_logs_read"] is False


@pytest.mark.parametrize(
    (
        "message",
        "terminal_dependency_classes",
        "failure_reason_codes",
        "retryability",
    ),
    [
        (
            "Docker compose command failed. ERROR: failed to solve: process "
            "/bin/sh -c apt-get install missing-package did not complete "
            "successfully: unable to locate package missing-package",
            ["system_package"],
            ["apt_package_unavailable"],
            "non_retryable",
        ),
        (
            "Docker compose command failed. ERROR: failed to solve: process "
            "/bin/sh -c pip3 install numpy did not complete successfully: "
            "read timed out for pypi.org; max retries exceeded",
            ["python_package"],
            ["connection_timeout", "retry_exhausted"],
            "retryable",
        ),
        (
            "Docker compose command failed: invalid mount config for type "
            "bind: bind source path does not exist",
            [],
            ["missing_file"],
            "non_retryable",
        ),
    ],
)
def test_setup_only_preflight_projects_terminal_failure_signals(
    message: str,
    terminal_dependency_classes: list[str],
    failure_reason_codes: list[str],
    retryability: str,
) -> None:
    FakeRollout.failure_stage = "environment_start"
    FakeRollout.failure = RuntimeError(message)

    result = run_preflight()

    assert result["terminal_dependency_classes"] == terminal_dependency_classes
    assert result["failure_reason_codes"] == failure_reason_codes
    assert result["terminal_failure_reason_codes"] == failure_reason_codes
    assert result["retryability"] == retryability
    assert message not in json.dumps(result, sort_keys=True)


def test_setup_only_preflight_separates_terminal_reason_and_endpoint() -> None:
    FakeRollout.failure_stage = "environment_start"
    FakeRollout.failure = RuntimeError(
        "failed to fetch https://archive.ubuntu.com/package-index\n"
        "failed to solve: process /bin/sh -c apt-get update && wget "
        "https://archive.apache.org/dist/tool.tgz did not complete successfully"
    )

    result = run_preflight()

    assert result["terminal_dependency_classes"] == [
        "system_package",
        "http_download",
    ]
    assert result["terminal_failure_reason_codes"] == ["apt_fetch_failed"]
    assert result["dependency_endpoints"] == [
        "ubuntu_repository",
        "apache_archive",
    ]
    assert result["terminal_dependency_endpoints"] == ["apache_archive"]
    assert result["raw_error_recorded"] is False


def test_setup_only_preflight_classifies_ubuntu_mirror_without_raw_url() -> None:
    FakeRollout.failure_stage = "environment_start"
    FakeRollout.failure = RuntimeError(
        "failed to fetch https://repo.huaweicloud.com/ubuntu/package-index"
    )

    result = run_preflight()

    assert result["terminal_dependency_endpoints"] == ["ubuntu_repository_mirror"]
    assert result["terminal_failure_reason_codes"] == ["apt_fetch_failed"]
    assert "huaweicloud" not in json.dumps(result, sort_keys=True)


def test_setup_only_preflight_reports_cleanup_failure_without_raw_error() -> None:
    FakeRollout.failure_stage = "cleanup"
    FakeRollout.failure = RuntimeError("secret cleanup detail /private/job")

    result = run_preflight()

    assert result["status"] == "failed"
    assert result["failure_stage"] == "cleanup"
    assert result["failure_category"] == "skillsbench_setup_cleanup_failure"
    assert result["exit_category"] == "cleanup_failed"
    assert result["cleanup_status"] == "failed"
    assert "secret cleanup detail" not in json.dumps(result, sort_keys=True)
