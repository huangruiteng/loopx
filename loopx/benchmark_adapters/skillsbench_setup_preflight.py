from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from .skillsbench_failure_signals import (
    skillsbench_runner_error_fingerprint,
    skillsbench_setup_failure_category,
)


SCHEMA_VERSION = "skillsbench_setup_only_public_preflight_v0"
_PATCH_SUFFIX = "_patch_applied"


def _patch_hits(task_staging: Mapping[str, Any] | None) -> list[str]:
    staging = task_staging or {}
    return sorted(
        key.removesuffix(_PATCH_SUFFIX)
        for key, value in staging.items()
        if isinstance(key, str) and key.endswith(_PATCH_SUFFIX) and value is True
    )


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
        "dependency_endpoints": [],
        "terminal_dependency_endpoints": [],
        "retryability": "unknown",
        "failure_category": "none",
        "exit_category": "pending",
        "patch_hits": _patch_hits(task_staging),
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
        fingerprint = skillsbench_runner_error_fingerprint(str(exc))
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
