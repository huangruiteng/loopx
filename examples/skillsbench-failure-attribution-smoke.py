#!/usr/bin/env python3
"""Smoke public-safe SkillsBench setup-failure attribution."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench import (
    skillsbench_runner_error_attribution,
    skillsbench_runner_error_fingerprint,
)
from loopx.benchmark_adapters.skillsbench_failure_signals import (
    reconcile_skillsbench_setup_attribution,
    skillsbench_failure_dependency_classes,
)
from scripts.skillsbench_automation_loop import (
    _apply_host_local_acp_prereq_failure_attribution,
)


def test_pip_bootstrap_failure_attribution() -> None:
    error_text = (
        "Docker compose command failed. RUN pip3 install numpy==1.26.4. "
        "ERROR: Read timed out from files.pythonhosted.org. "
        "ERROR: No matching distribution found for numpy==1.26.4"
    )

    exception_type, attribution, labels = skillsbench_runner_error_attribution(
        error_text
    )
    assert exception_type == "skillsbench_docker_compose_pip_bootstrap_failure"
    assert attribution == "skillsbench_docker_compose_pip_bootstrap_failure"
    assert "skillsbench_python_package_bootstrap_failure" in labels, labels
    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert "pip_bootstrap_failure" in fingerprint["matched_patterns"], fingerprint


def test_injected_pip_retry_env_does_not_imply_network_failure() -> None:
    error_text = (
        "Docker compose command failed.\n"
        "ENV PIP_RETRIES=10\n"
        "RUN pip install transitleastsquares==1.32\n"
        "pip._vendor.packaging.requirements.InvalidRequirement: bad metadata"
    )

    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert fingerprint["pip_failure_subtype"] == "pip_internal_error", fingerprint
    assert fingerprint["failure_reason_codes"] == [], fingerprint


def test_line_local_pip_vendor_retry_remains_network_failure() -> None:
    error_text = (
        "Docker compose command failed. RUN pip install numpy==1.26.4.\n"
        "pip._vendor.urllib3 MaxRetryError from pypi.org: max retries exceeded"
    )

    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert fingerprint["pip_failure_subtype"] == (
        "package_index_network_failure"
    ), fingerprint
    assert fingerprint["terminal_failure_reason_codes"] == [
        "retry_exhausted",
        "pip_vendor_network",
    ], fingerprint
    assert fingerprint["terminal_failure_dependency_endpoints"] == [
        "pypi_primary"
    ], fingerprint
    assert fingerprint["retryability"] == "retryable", fingerprint


def test_task_skills_context_does_not_shadow_pip_failure() -> None:
    error_text = (
        "Docker compose command failed while task skills metadata references "
        "/app/skills. Dockerfile RUN pip install numpy did not complete "
        "successfully: externally-managed-environment."
    )

    exception_type, attribution, labels = skillsbench_runner_error_attribution(
        error_text
    )
    expected = "skillsbench_docker_compose_pip_bootstrap_failure"
    assert exception_type == expected
    assert attribution == expected
    assert "skillsbench_python_package_bootstrap_failure" in labels, labels


def test_docker_api_version_mismatch_attribution() -> None:
    error_text = (
        "Docker compose command failed. Error response from daemon: "
        "client version 1.52 is too new. Maximum supported API version is 1.43"
    )

    exception_type, attribution, labels = skillsbench_runner_error_attribution(
        error_text
    )
    expected = "skillsbench_docker_api_version_mismatch"
    assert exception_type == expected
    assert attribution == expected
    assert "skillsbench_docker_compose_setup_failure" in labels, labels
    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert "docker_api_version_mismatch" in fingerprint["matched_patterns"], fingerprint


def test_docker_compose_plugin_unavailable_attribution() -> None:
    error_text = (
        "Docker compose command failed. Stdout: unknown flag: --project-name\n"
        "Usage:  docker [OPTIONS] COMMAND\nRun 'docker --help' for more information"
    )

    exception_type, attribution, labels = skillsbench_runner_error_attribution(
        error_text
    )
    expected = "skillsbench_docker_compose_plugin_unavailable"
    assert exception_type == expected
    assert attribution == expected
    assert "skillsbench_docker_compose_setup_failure" in labels, labels
    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert "docker_compose_plugin_unavailable" in fingerprint["matched_patterns"], (
        fingerprint
    )


def test_injected_pip_lines_do_not_mask_later_build_failure() -> None:
    error_text = (
        "Docker compose command failed.\n"
        "ARG LOOPX_SKILLSBENCH_PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple\n"
        "RUN pip3 install numpy scipy\n"
        "ERROR: failed to solve: process /bin/sh -c curl artifact.example.invalid "
        "did not complete successfully: read timed out from artifact.example.invalid"
    )

    exception_type, attribution, labels = skillsbench_runner_error_attribution(
        error_text
    )
    assert exception_type == "skillsbench_docker_compose_image_build_failure"
    assert attribution == "skillsbench_docker_compose_image_build_failure"
    assert "skillsbench_python_package_bootstrap_failure" not in labels, labels
    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert "image_build" in fingerprint["matched_patterns"], fingerprint
    assert "network_failure" in fingerprint["matched_patterns"], fingerprint
    assert "pip_bootstrap_failure" not in fingerprint["matched_patterns"], fingerprint


def test_setup_attribution_reconciles_to_public_fingerprint() -> None:
    compact = {
        "score_failure_attribution": "skillsbench_docker_compose_apt_repository_failure",
        "failure_attribution_labels": [
            "skillsbench_docker_compose_apt_repository_failure",
            "skillsbench_docker_compose_setup_failure",
            "skillsbench_environment_setup_error",
        ],
        "runner_failure": {
            "exception_type": "skillsbench_docker_compose_apt_repository_failure",
            "failure_class": "skillsbench_docker_compose_apt_repository_failure",
        },
        "runner_failure_fingerprint": {
            "matched_patterns": [
                "docker_compose_command_failed",
                "network_failure",
                "image_build",
            ]
        },
        "attempt_accounting": {
            "failure_label": "skillsbench_docker_compose_apt_repository_failure",
            "failure_class": "job_materialization_failed",
        },
        "compose_setup_diagnostic": {
            "failure_class": "skillsbench_docker_compose_apt_repository_failure"
        },
    }

    assert reconcile_skillsbench_setup_attribution(compact) is True
    expected = "skillsbench_docker_compose_image_build_failure"
    assert compact["score_failure_attribution"] == expected, compact
    assert compact["runner_failure"]["failure_class"] == expected, compact
    assert compact["attempt_accounting"]["failure_label"] == expected, compact
    assert compact["compose_setup_diagnostic"]["failure_class"] == expected, compact
    assert "skillsbench_docker_compose_apt_repository_failure" not in compact[
        "failure_attribution_labels"
    ], compact


def test_supported_setup_attribution_is_unchanged() -> None:
    compact = {
        "score_failure_attribution": "skillsbench_docker_compose_apt_repository_failure",
        "runner_failure_fingerprint": {"matched_patterns": ["apt_failure"]},
    }
    assert reconcile_skillsbench_setup_attribution(compact) is False
    assert compact["score_failure_attribution"] == (
        "skillsbench_docker_compose_apt_repository_failure"
    )


def test_failure_dependency_classes_ignore_unrelated_dockerfile_lines() -> None:
    error_text = (
        "RUN apt-get update\n"
        "RUN pip3 install numpy\n"
        "ERROR: failed to solve: process /bin/sh -c micromamba install scipy "
        "from https://repo.anaconda.com did not complete successfully: "
        "connection timed out"
    )
    classes = skillsbench_failure_dependency_classes(error_text)
    assert classes == ["conda_package"], classes
    fingerprint = skillsbench_runner_error_fingerprint(error_text)
    assert fingerprint["failure_line_dependency_classes"] == classes, fingerprint
    assert "repo.anaconda.com" not in str(fingerprint), fingerprint


def _completed_score_compact(score: float, *, task_operations: int) -> dict:
    return {
        "official_score": score,
        "official_score_status": "completed",
        "validation": {
            "official_verifier_status": "completed",
            "official_verifier_validation_present": True,
        },
        "interaction_counters": {
            "remote_command_file_bridge_agent_task_facing_operation_count": (
                task_operations
            ),
        },
        "attempt_accounting": {"official_score_attempt_countable": True},
    }


def _codex_exec_failure_prerequisites() -> dict:
    return {
        "host_local_acp_codex_exec_failure_trace_present": True,
        "host_local_acp_codex_exec_failure_category": "codex_exec_exit_1",
    }


def test_postscore_transport_failure_preserves_countable_score() -> None:
    for score in (0.0, 0.6, 1.0):
        compact = _completed_score_compact(score, task_operations=2)
        assert (
            _apply_host_local_acp_prereq_failure_attribution(
                compact,
                _codex_exec_failure_prerequisites(),
            )
            is False
        ), compact
        assert compact["attempt_accounting"]["official_score_attempt_countable"]


def test_zero_activity_transport_failure_remains_uncountable() -> None:
    for score in (0.0, 1.0):
        compact = _completed_score_compact(score, task_operations=0)
        assert _apply_host_local_acp_prereq_failure_attribution(
            compact,
            _codex_exec_failure_prerequisites(),
        )
        assert (
            compact["attempt_accounting"]["official_score_attempt_countable"]
            is False
        )


def test_full_score_without_completed_verifier_evidence_is_uncountable() -> None:
    invalid_evidence = (
        {"validation": {}},
        {
            "validation": {
                "official_verifier_status": "incomplete",
                "official_verifier_validation_present": True,
            }
        },
        {"official_score_status": "missing"},
    )
    for updates in invalid_evidence:
        compact = _completed_score_compact(1.0, task_operations=2)
        compact.update(updates)
        assert _apply_host_local_acp_prereq_failure_attribution(
            compact,
            _codex_exec_failure_prerequisites(),
        ), compact
        assert (
            compact["attempt_accounting"]["official_score_attempt_countable"]
            is False
        ), compact


if __name__ == "__main__":
    test_pip_bootstrap_failure_attribution()
    test_injected_pip_retry_env_does_not_imply_network_failure()
    test_line_local_pip_vendor_retry_remains_network_failure()
    test_task_skills_context_does_not_shadow_pip_failure()
    test_docker_api_version_mismatch_attribution()
    test_docker_compose_plugin_unavailable_attribution()
    test_injected_pip_lines_do_not_mask_later_build_failure()
    test_setup_attribution_reconciles_to_public_fingerprint()
    test_supported_setup_attribution_is_unchanged()
    test_failure_dependency_classes_ignore_unrelated_dockerfile_lines()
    test_postscore_transport_failure_preserves_countable_score()
    test_zero_activity_transport_failure_remains_uncountable()
    test_full_score_without_completed_verifier_evidence_is_uncountable()
    print("skillsbench-failure-attribution-smoke: ok")
