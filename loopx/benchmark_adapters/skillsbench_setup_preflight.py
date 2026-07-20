from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import Any

from .skillsbench_failure_signals import (
    skillsbench_runner_error_fingerprint,
    skillsbench_setup_failure_category,
)


SCHEMA_VERSION = "skillsbench_setup_only_public_preflight_v0"
COMPOSE_TYPED_CAUSE_SCHEMA_VERSION = "skillsbench_compose_typed_cause_v0"
_PATCH_SUFFIX = "_patch_applied"
_PUBLIC_TASK_STAGING_BOOL_FIELDS = (
    "staged",
    "apt_retry_patch_applied",
    "dockerfile_ubuntu_apt_mirror_patch_required",
    "dockerfile_ubuntu_apt_mirror_patch_applied",
    "dockerfile_ubuntu_apt_mirror_raw_url_recorded",
    "dockerfile_debian_apt_mirror_patch_required",
    "dockerfile_debian_apt_mirror_patch_applied",
    "dockerfile_debian_apt_mirror_raw_url_recorded",
    "dockerfile_pip_bootstrap_patch_required",
    "dockerfile_pip_bootstrap_patch_applied",
    "dockerfile_venv_pip_invocation_patch_required",
    "dockerfile_venv_pip_invocation_patch_applied",
    "dockerfile_gcr_mirror_patch_required",
    "dockerfile_gcr_mirror_patch_applied",
    "dockerfile_gcr_mirror_raw_prefix_recorded",
    "dockerfile_wget_gpg_key_retry_patch_required",
    "dockerfile_wget_gpg_key_retry_patch_applied",
    "dockerfile_network_download_retry_patch_required",
    "dockerfile_network_download_retry_patch_applied",
    "dockerfile_uv_bootstrap_mirror_patch_required",
    "dockerfile_uv_bootstrap_mirror_patch_applied",
    "dockerfile_apache_archive_mirror_patch_required",
    "dockerfile_apache_archive_mirror_patch_applied",
    "dockerfile_apache_archive_raw_url_recorded",
    "dockerfile_maven_mirror_patch_required",
    "dockerfile_maven_mirror_patch_applied",
    "dockerfile_maven_mirror_raw_url_recorded",
    "benchmark_egress_proxy_dockerfile_env_patch_required",
    "benchmark_egress_proxy_dockerfile_env_patch_applied",
    "benchmark_egress_proxy_dockerfile_env_raw_proxy_recorded",
    "verifier_uv_bootstrap_mirror_patch_required",
    "verifier_uv_bootstrap_mirror_patch_applied",
    "verifier_dependency_cache_required",
    "verifier_dependency_cache_env_patch_applied",
    "verifier_dependency_cache_raw_path_recorded",
)
_PUBLIC_TASK_STAGING_STRING_FIELDS = (
    "schema_version",
    "dockerfile_ubuntu_apt_mirror_host",
    "dockerfile_debian_apt_mirror_host",
    "dockerfile_pip_index_host",
    "dockerfile_uv_bootstrap_version",
    "dockerfile_uv_bootstrap_mirror_host",
    "dockerfile_apache_archive_mirror_host",
    "dockerfile_maven_mirror_host",
    "verifier_uv_bootstrap_version",
    "verifier_uv_bootstrap_mirror_host",
)


class SkillsBenchComposeCommandFailure(RuntimeError):
    """Carry only a bounded public fingerprint beyond the compose producer."""

    def __init__(self, fingerprint: Mapping[str, object]) -> None:
        super().__init__(
            "SkillsBench compose command failed with a bounded typed cause"
        )
        self.schema_version = COMPOSE_TYPED_CAUSE_SCHEMA_VERSION
        self.fingerprint = dict(fingerprint)


def skillsbench_compose_typed_fingerprint(
    exc: Exception,
) -> dict[str, object] | None:
    if not isinstance(exc, SkillsBenchComposeCommandFailure):
        return None
    if exc.schema_version != COMPOSE_TYPED_CAUSE_SCHEMA_VERSION:
        return None
    return dict(exc.fingerprint)


def install_skillsbench_compose_typed_cause_boundary(
    environment: Any,
) -> Callable[[], None] | None:
    """Type final build failures without changing BenchFlow's retry loop."""

    original_build = getattr(environment, "_run_docker_compose_build", None)
    if not callable(original_build):
        return None

    async def build_with_typed_cause(*args: Any, **kwargs: Any) -> Any:
        try:
            return await original_build(*args, **kwargs)
        except SkillsBenchComposeCommandFailure:
            raise
        except Exception as exc:
            fingerprint = skillsbench_runner_error_fingerprint(str(exc))
            raise SkillsBenchComposeCommandFailure(fingerprint) from None

    try:
        setattr(environment, "_run_docker_compose_build", build_with_typed_cause)
    except (AttributeError, TypeError):
        return None

    def restore() -> None:
        if (
            getattr(environment, "_run_docker_compose_build", None)
            is build_with_typed_cause
        ):
            setattr(environment, "_run_docker_compose_build", original_build)

    return restore


def _patch_hits(task_staging: Mapping[str, Any] | None) -> list[str]:
    staging = task_staging or {}
    return sorted(
        key.removesuffix(_PATCH_SUFFIX)
        for key, value in staging.items()
        if isinstance(key, str) and key.endswith(_PATCH_SUFFIX) and value is True
    )


def _public_task_staging(task_staging: Mapping[str, Any] | None) -> dict[str, Any]:
    staging = task_staging or {}
    public: dict[str, Any] = {}
    for field in _PUBLIC_TASK_STAGING_STRING_FIELDS:
        value = staging.get(field)
        if isinstance(value, str) and value:
            public[field] = value[:180]
    for field in _PUBLIC_TASK_STAGING_BOOL_FIELDS:
        value = staging.get(field)
        if isinstance(value, bool):
            public[field] = value
    return public


def _exit_category(exc: Exception, matched_patterns: set[str]) -> str:
    if (
        isinstance(exc, (asyncio.TimeoutError, TimeoutError))
        or "timeout" in matched_patterns
    ):
        return "timeout"
    if isinstance(exc, PermissionError) or "permission_denied" in matched_patterns:
        return "permission_denied"
    if {
        "docker_daemon_unavailable",
        "docker_api_version_mismatch",
        "docker_compose_plugin_unavailable",
    } & matched_patterns:
        return "runtime_unavailable"
    if {
        "docker_compose_command_failed",
        "image_build",
        "apt_failure",
        "pip_bootstrap_failure",
        "volume_mount_failure",
    } & matched_patterns:
        return "setup_command_failed"
    if isinstance(exc, FileNotFoundError) or "missing_file" in matched_patterns:
        return "missing_input"
    return "exception"


def _base_result(
    *,
    task_staging: Mapping[str, Any] | None,
    setup_preflight: Mapping[str, Any] | None,
) -> dict[str, Any]:
    setup = setup_preflight or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "stage": "rollout_create",
        "job_root_materialized": False,
        "environment_object_materialized": False,
        "environment_started": False,
        "agent_install_invoked": False,
        "agent_execution_invoked": False,
        "verifier_invoked": False,
        "dependency_classes": [],
        "terminal_dependency_classes": [],
        "failure_reason_codes": [],
        "terminal_failure_reason_codes": [],
        "apt_failure_subtype": "none",
        "dependency_endpoints": [],
        "terminal_dependency_endpoints": [],
        "retryability": "unknown",
        "failure_category": "none",
        "exit_category": "pending",
        "failure_cause_source": "none",
        "compose_typed_cause_boundary_installed": False,
        "compose_typed_cause_boundary_restored": False,
        "patch_hits": _patch_hits(task_staging),
        "task_staging": _public_task_staging(task_staging),
        "apt_setup_risk_detected": setup.get("apt_setup_risk_detected") is True,
        "dockerfile_pip_install_risk_detected": (
            setup.get("dockerfile_pip_install_risk_detected") is True
        ),
        "verifier_bootstrap_risk_detected": (
            setup.get("verifier_bootstrap_risk_detected") is True
        ),
        "cleanup_status": "not_started",
        "raw_error_recorded": False,
        "raw_logs_read": False,
        "raw_logs_recorded": False,
        "raw_command_output_recorded": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "raw_verifier_output_read": False,
        "host_paths_recorded": False,
        "secret_values_recorded": False,
    }


async def run_setup_only_public_preflight(
    *,
    rollout_type: Any,
    config: Any,
    task_staging: Mapping[str, Any] | None = None,
    setup_preflight: Mapping[str, Any] | None = None,
    stage_timeout_sec: float,
    cleanup_timeout_sec: float = 30.0,
) -> dict[str, Any]:
    """Materialize a BenchFlow environment without installing or running an agent."""

    result = _base_result(
        task_staging=task_staging,
        setup_preflight=setup_preflight,
    )
    stage_timeout_sec = max(1.0, stage_timeout_sec)
    cleanup_timeout_sec = max(1.0, cleanup_timeout_sec)
    rollout: Any | None = None
    restore_compose_boundary: Callable[[], None] | None = None
    failed = False
    try:
        rollout = await asyncio.wait_for(
            rollout_type.create(config),
            timeout=stage_timeout_sec,
        )
        result["stage"] = "rollout_setup"
        await asyncio.wait_for(rollout.setup(), timeout=stage_timeout_sec)
        result["job_root_materialized"] = (
            getattr(rollout, "_rollout_dir", None) is not None
        )
        result["environment_object_materialized"] = (
            getattr(rollout, "env", None) is not None
        )

        restore_compose_boundary = install_skillsbench_compose_typed_cause_boundary(
            getattr(rollout, "env", None)
        )
        result["compose_typed_cause_boundary_installed"] = (
            restore_compose_boundary is not None
        )

        result["stage"] = "environment_start"
        await asyncio.wait_for(rollout.start(), timeout=stage_timeout_sec)
        result["environment_started"] = True
        result["status"] = "passed"
        result["stage"] = "environment_ready_before_agent"
        result["exit_category"] = "passed"
    except Exception as exc:
        failed = True
        if rollout is not None:
            result["job_root_materialized"] = (
                getattr(rollout, "_rollout_dir", None) is not None
            )
            result["environment_object_materialized"] = (
                getattr(rollout, "env", None) is not None
            )
        typed_fingerprint = skillsbench_compose_typed_fingerprint(exc)
        if typed_fingerprint is None:
            fingerprint = skillsbench_runner_error_fingerprint(str(exc))
            result["failure_cause_source"] = "exception_text_fingerprint"
        else:
            fingerprint = typed_fingerprint
            result["failure_cause_source"] = "compose_producer_typed_cause"
        matched_patterns = {
            str(item)
            for item in fingerprint.get("matched_patterns", [])
            if isinstance(item, str)
        }
        result["status"] = "failed"
        result["failure_stage"] = result["stage"]
        result["failure_category"] = skillsbench_setup_failure_category(fingerprint)
        result["exit_category"] = _exit_category(exc, matched_patterns)
        result["dependency_classes"] = [
            str(item)
            for item in fingerprint.get("failure_line_dependency_classes", [])
            if isinstance(item, str)
        ]
        result["terminal_dependency_classes"] = [
            str(item)
            for item in fingerprint.get("terminal_failure_dependency_classes", [])
            if isinstance(item, str)
        ]
        result["failure_reason_codes"] = [
            str(item)
            for item in fingerprint.get("failure_reason_codes", [])
            if isinstance(item, str)
        ]
        result["terminal_failure_reason_codes"] = [
            str(item)
            for item in fingerprint.get("terminal_failure_reason_codes", [])
            if isinstance(item, str)
        ]
        result["apt_failure_subtype"] = str(
            fingerprint.get("apt_failure_subtype") or "none"
        )
        result["dependency_endpoints"] = [
            str(item)
            for item in fingerprint.get("failure_dependency_endpoints", [])
            if isinstance(item, str)
        ]
        result["terminal_dependency_endpoints"] = [
            str(item)
            for item in fingerprint.get("terminal_failure_dependency_endpoints", [])
            if isinstance(item, str)
        ]
        result["retryability"] = str(fingerprint.get("retryability") or "unknown")
        result["fingerprint_patterns"] = sorted(matched_patterns)
        result["fingerprint_confidence"] = str(
            fingerprint.get("fingerprint_confidence")
            or "coarse_public_safe_pattern_match"
        )
    finally:
        if restore_compose_boundary is not None:
            restore_compose_boundary()
            result["compose_typed_cause_boundary_restored"] = True
        if rollout is not None:
            try:
                await asyncio.wait_for(
                    rollout.cleanup(),
                    timeout=cleanup_timeout_sec,
                )
                result["cleanup_status"] = "completed"
            except Exception:
                result["cleanup_status"] = "failed"
                if not failed:
                    result["status"] = "failed"
                    result["failure_stage"] = "cleanup"
                    result["failure_category"] = "skillsbench_setup_cleanup_failure"
                    result["exit_category"] = "cleanup_failed"
        else:
            result["cleanup_status"] = "not_required"
    return result
