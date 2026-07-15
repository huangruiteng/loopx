#!/usr/bin/env python3
"""Smoke-test route-scoped Python staging for the SkillsBench LoopX CLI."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.skillsbench_automation_loop import (
    DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN,
    _public_task_staging,
    patch_dockerfile_loopx_case_python_runtime,
    stage_task_for_sandbox,
)


RUNNER = REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"


def _write_task(root: Path, dockerfile_text: str) -> Path:
    task = root / "task"
    environment = task / "environment"
    environment.mkdir(parents=True)
    (environment / "Dockerfile").write_text(dockerfile_text, encoding="utf-8")
    (task / "task.toml").write_text("[task]\n", encoding="utf-8")
    return task


def _assert_final_stage_patch_is_idempotent() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-case-python-patch-") as temp:
        dockerfile = Path(temp) / "Dockerfile"
        dockerfile.write_text(
            "FROM alpine:3.20 AS build\n"
            "RUN echo build\n"
            "FROM debian:bookworm-slim\n"
            "RUN echo final\n",
            encoding="utf-8",
        )
        assert patch_dockerfile_loopx_case_python_runtime(dockerfile) is True
        assert patch_dockerfile_loopx_case_python_runtime(dockerfile) is False
        text = dockerfile.read_text(encoding="utf-8")
        assert text.count(DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN) == 1, text
        marker = text.index(DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN)
        assert marker > text.index("FROM debian:bookworm-slim"), text
        assert marker < text.index("RUN echo final"), text
        for package_manager in ("apt-get", "apk", "microdnf", "dnf", "yum"):
            assert f"command -v {package_manager}" in text, text
        assert "command -v python3" in text, text


def _assert_final_scratch_stage_is_not_mutated() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-case-python-scratch-") as temp:
        dockerfile = Path(temp) / "Dockerfile"
        original = "FROM python:3.12 AS build\nFROM scratch\nCOPY --from=build /out /out\n"
        dockerfile.write_text(original, encoding="utf-8")
        assert patch_dockerfile_loopx_case_python_runtime(dockerfile) is False
        assert dockerfile.read_text(encoding="utf-8") == original


def _assert_staging_is_route_scoped_and_public() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-case-python-stage-") as temp:
        root = Path(temp)
        task = _write_task(root, "FROM debian:bookworm-slim\nRUN echo ready\n")
        original = (task / "environment" / "Dockerfile").read_text(encoding="utf-8")

        product_task, product_metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="product",
            sandbox="docker",
            loopx_case_runtime_required=True,
        )
        product_text = (product_task / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert product_metadata["loopx_case_python_runtime_patch_required"] is True
        assert product_metadata["loopx_case_python_runtime_patch_applied"] is True
        assert DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN in product_text
        assert (task / "environment" / "Dockerfile").read_text(encoding="utf-8") == original

        baseline_task, baseline_metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="baseline",
            sandbox="docker",
            loopx_case_runtime_required=False,
        )
        baseline_text = (baseline_task / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert baseline_metadata["loopx_case_python_runtime_patch_required"] is False
        assert baseline_metadata["loopx_case_python_runtime_patch_applied"] is False
        assert DOCKER_LOOPX_CASE_PYTHON_RUNTIME_BEGIN not in baseline_text

        public = _public_task_staging(product_metadata)
        assert public["loopx_case_python_runtime_patch_required"] is True, public
        assert public["loopx_case_python_runtime_patch_applied"] is True, public


def _assert_product_route_wiring() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert (
        "loopx_case_runtime_required=_is_loopx_product_mode_route(args.route)"
        in source
    )


def main() -> int:
    _assert_final_stage_patch_is_idempotent()
    _assert_final_scratch_stage_is_not_mutated()
    _assert_staging_is_route_scoped_and_public()
    _assert_product_route_wiring()
    print("skillsbench-loopx-case-python-runtime-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
