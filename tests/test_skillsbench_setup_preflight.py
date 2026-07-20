from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from loopx.benchmark_adapters.skillsbench_codex_runtime import preflight_required
from loopx.benchmark_adapters.skillsbench_failure_signals import (
    skillsbench_runner_error_fingerprint,
)
from loopx.benchmark_adapters.skillsbench_setup_preflight import (
    SkillsBenchComposeCommandFailure,
    install_skillsbench_compose_typed_cause_boundary,
    run_setup_only_public_preflight,
)
from loopx.status import compact_benchmark_run
from scripts.skillsbench_automation_loop import (
    build_compose_setup_diagnostic,
    build_plan,
    parse_args,
)


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
                "dockerfile_debian_apt_mirror_patch_required": True,
                "dockerfile_debian_apt_mirror_patch_applied": True,
                "dockerfile_debian_apt_mirror_host": "mirror.example",
                "dockerfile_debian_apt_mirror_raw_url_recorded": False,
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
        "dockerfile_debian_apt_mirror",
        "dockerfile_pip_bootstrap",
    ]
    assert result["task_staging"] == {
        "apt_retry_patch_applied": True,
        "dockerfile_debian_apt_mirror_patch_required": True,
        "dockerfile_debian_apt_mirror_patch_applied": True,
        "dockerfile_debian_apt_mirror_host": "mirror.example",
        "dockerfile_debian_apt_mirror_raw_url_recorded": False,
        "dockerfile_pip_bootstrap_patch_applied": True,
    }
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


def test_compose_producer_emits_only_bounded_typed_cause() -> None:
    raw_failure = (
        "Docker compose command failed for environment private-case. "
        "Command: docker compose --project-directory /private/job build. "
        "Stdout: apt-get update failed to fetch package index: Temporary "
        "failure resolving 'archive.example.invalid'."
    )

    class FakeComposeEnvironment:
        def __init__(self) -> None:
            self.command_attempts = 0
            self.build_received_raw_failure = False

        async def _run_docker_compose_command(self) -> None:
            self.command_attempts += 1
            raise RuntimeError(raw_failure)

        async def _run_docker_compose_build(self) -> None:
            for attempt in range(2):
                try:
                    await self._run_docker_compose_command()
                except RuntimeError as exc:
                    self.build_received_raw_failure = raw_failure in str(exc)
                    if attempt == 0:
                        continue
                    raise

    environment = FakeComposeEnvironment()
    restore = install_skillsbench_compose_typed_cause_boundary(environment)
    assert restore is not None

    async def invoke() -> None:
        await environment._run_docker_compose_build()

    with pytest.raises(SkillsBenchComposeCommandFailure) as error:
        asyncio.run(invoke())

    typed = error.value
    serialized = json.dumps(typed.fingerprint, sort_keys=True)
    assert typed.schema_version == "skillsbench_compose_typed_cause_v0"
    assert typed.fingerprint["apt_failure_subtype"] == "dns_resolution"
    assert typed.fingerprint["retryability"] == "retryable"
    assert typed.fingerprint["has_host_paths"] is True
    assert typed.fingerprint["has_secret_like_tokens"] is False
    assert environment.command_attempts == 2
    assert environment.build_received_raw_failure is True
    assert raw_failure not in str(typed)
    assert "/private/job" not in serialized
    assert "archive.example.invalid" not in serialized
    assert typed.__cause__ is None

    restore()
    with pytest.raises(RuntimeError, match="Docker compose command failed"):
        asyncio.run(invoke())
    assert environment.command_attempts == 4


def test_setup_only_preflight_consumes_compose_producer_typed_cause() -> None:
    raw_failure = (
        "Docker compose command failed. apt-get update failed to fetch index: "
        "GPG error: repository is not signed at /private/job"
    )

    class FakeComposeEnvironment:
        async def _run_docker_compose_build(self) -> None:
            raise RuntimeError(raw_failure)

    class FakeComposeRollout:
        last_created: "FakeComposeRollout | None" = None

        def __init__(self) -> None:
            self._rollout_dir: object | None = None
            self.env: FakeComposeEnvironment | None = None

        @classmethod
        async def create(cls, _config: Any) -> "FakeComposeRollout":
            instance = cls()
            cls.last_created = instance
            return instance

        async def setup(self) -> None:
            self._rollout_dir = object()
            self.env = FakeComposeEnvironment()

        async def start(self) -> None:
            assert self.env is not None
            await self.env._run_docker_compose_build()

        async def cleanup(self) -> None:
            return None

    result = asyncio.run(
        run_setup_only_public_preflight(
            rollout_type=FakeComposeRollout,
            config=object(),
            stage_timeout_sec=1,
        )
    )

    assert result["status"] == "failed"
    assert result["failure_stage"] == "environment_start"
    assert result["failure_cause_source"] == "compose_producer_typed_cause"
    assert result["failure_category"] == (
        "skillsbench_docker_compose_apt_repository_failure"
    )
    assert result["apt_failure_subtype"] == "unsigned_repository"
    assert result["terminal_failure_reason_codes"] == [
        "apt_fetch_failed",
        "apt_unsigned_repository",
        "apt_signature_or_gpg",
    ]
    assert result["compose_typed_cause_boundary_installed"] is True
    assert result["compose_typed_cause_boundary_restored"] is True
    assert result["raw_logs_read"] is False
    assert result["raw_logs_recorded"] is False
    assert result["raw_command_output_recorded"] is False
    serialized = json.dumps(result, sort_keys=True)
    assert raw_failure not in serialized
    assert "/private/job" not in serialized


@pytest.mark.parametrize(
    (
        "message",
        "terminal_dependency_classes",
        "failure_reason_codes",
        "apt_failure_subtype",
        "retryability",
    ),
    [
        (
            "Docker compose command failed. ERROR: failed to solve: process "
            "/bin/sh -c apt-get install missing-package did not complete "
            "successfully: unable to locate package missing-package",
            ["system_package"],
            ["apt_package_unavailable"],
            "package_unavailable",
            "non_retryable",
        ),
        (
            "Docker compose command failed. ERROR: failed to solve: process "
            "/bin/sh -c pip3 install numpy did not complete successfully: "
            "read timed out for pypi.org; max retries exceeded",
            ["python_package"],
            ["connection_timeout", "retry_exhausted"],
            "none",
            "retryable",
        ),
        (
            "Docker compose command failed: invalid mount config for type "
            "bind: bind source path does not exist",
            [],
            ["missing_file"],
            "none",
            "non_retryable",
        ),
    ],
)
def test_setup_only_preflight_projects_terminal_failure_signals(
    message: str,
    terminal_dependency_classes: list[str],
    failure_reason_codes: list[str],
    apt_failure_subtype: str,
    retryability: str,
) -> None:
    FakeRollout.failure_stage = "environment_start"
    FakeRollout.failure = RuntimeError(message)

    result = run_preflight()

    assert result["terminal_dependency_classes"] == terminal_dependency_classes
    assert result["failure_reason_codes"] == failure_reason_codes
    assert result["terminal_failure_reason_codes"] == failure_reason_codes
    assert result["apt_failure_subtype"] == apt_failure_subtype
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


@pytest.mark.parametrize(
    ("message", "subtype", "retryability"),
    [
        (
            "apt-get update: failed to fetch package index: Temporary failure "
            "resolving 'archive.example.invalid'",
            "dns_resolution",
            "retryable",
        ),
        (
            "apt update failed to fetch index: Certificate verification failed",
            "tls_or_certificate",
            "non_retryable",
        ),
        (
            "apt-get update: GPG error: repository is not signed",
            "unsigned_repository",
            "unknown",
        ),
        (
            "apt-get update: NO_PUBKEY ABC123",
            "missing_public_key",
            "unknown",
        ),
        (
            "apt-get update: At least one invalid signature was encountered",
            "invalid_signature",
            "unknown",
        ),
        (
            "apt-get update: failed to fetch index: File has unexpected size",
            "hash_or_size_mismatch",
            "unknown",
        ),
        (
            "apt-get update: failed to fetch index: Network is unreachable",
            "network_unreachable",
            "retryable",
        ),
        (
            "apt-get update: failed to fetch package index",
            "fetch_failed_unclassified",
            "unknown",
        ),
    ],
)
def test_apt_failure_subtype_is_public_safe_and_specific(
    message: str,
    subtype: str,
    retryability: str,
) -> None:
    fingerprint = skillsbench_runner_error_fingerprint(message)

    assert fingerprint["apt_failure_subtype"] == subtype
    assert fingerprint["retryability"] == retryability
    assert message not in json.dumps(fingerprint, sort_keys=True)
    assert fingerprint["raw_error_recorded"] is False


def test_compose_diagnostic_ignores_incidental_volume_for_terminal_apt() -> None:
    message = (
        "Docker compose command failed while preparing a named volume. "
        "failed to solve: Dockerfile RUN apt-get update; "
        "failed to fetch package index"
    )
    source = {
        "schema_version": "benchmark_run_v0",
        "benchmark": "skillsbench",
        "task_id": "synthetic-setup",
        "route": "loopx-turn-agent-cli",
        "score_failure_attribution": (
            "skillsbench_docker_compose_apt_repository_failure"
        ),
        "failure_attribution_labels": [
            "skillsbench_docker_compose_apt_repository_failure",
            "skillsbench_docker_compose_setup_failure",
            "skillsbench_environment_setup_error",
        ],
        "official_score_status": "missing",
        "runner_failure_fingerprint": skillsbench_runner_error_fingerprint(message),
    }

    compact = compact_benchmark_run(source)

    assert compact is not None
    fingerprint = compact["runner_failure_fingerprint"]
    assert "volume_mount_failure" not in fingerprint["matched_patterns"]
    assert "apt_failure" in fingerprint["matched_patterns"]
    assert fingerprint["terminal_failure_dependency_classes"] == [
        "system_package"
    ]
    assert fingerprint["terminal_failure_reason_codes"] == ["apt_fetch_failed"]
    assert fingerprint["apt_failure_subtype"] == "fetch_failed_unclassified"
    assert fingerprint["retryability"] == "unknown"

    diagnostic = build_compose_setup_diagnostic(
        compact,
        {"route": "loopx-turn-agent-cli"},
    )
    assert diagnostic["volume_mount_failure"] is False
    assert diagnostic["apt_repository_failure"] is True
    assert diagnostic["primary_setup_failure_category"] == (
        "system_package_repository"
    )
    assert diagnostic["next_diagnostic_action"] == (
        "repair_system_package_repository_setup_before_product_treatment"
    )

    reduced = compact_benchmark_run(
        {**compact, "compose_setup_diagnostic": diagnostic}
    )
    assert reduced is not None
    reduced_diagnostic = reduced["compose_setup_diagnostic"]
    assert reduced_diagnostic["primary_setup_failure_category"] == (
        "system_package_repository"
    )
    assert reduced_diagnostic["terminal_failure_dependency_classes"] == [
        "system_package"
    ]
    assert reduced_diagnostic["apt_failure_subtype"] == (
        "fetch_failed_unclassified"
    )
    assert message not in json.dumps(reduced, sort_keys=True)


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
