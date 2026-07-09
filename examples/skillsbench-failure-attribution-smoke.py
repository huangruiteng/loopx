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


if __name__ == "__main__":
    test_pip_bootstrap_failure_attribution()
    test_injected_pip_lines_do_not_mask_later_build_failure()
    print("skillsbench-failure-attribution-smoke: ok")
