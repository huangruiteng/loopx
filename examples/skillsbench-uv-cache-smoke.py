#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.benchmark_adapters import skillsbench_uv_cache as uv_cache  # noqa: E402
from scripts import skillsbench_automation_loop as runner  # noqa: E402


def test_staged_dockerfile_prefers_host_uv_binary_cache() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-uv-cache-smoke-") as tmp:
        root = Path(tmp)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        fake_uv = fake_bin / "uv"
        fake_uvx = fake_bin / "uvx"
        fake_uv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_uvx.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_uv.chmod(0o755)
        fake_uvx.chmod(0o755)

        task = root / "tasks" / "pddl-tpp-planning"
        dockerfile = task / "environment" / "Dockerfile"
        dockerfile.parent.mkdir(parents=True)
        dockerfile.write_text(
            "FROM python:3.12-slim\n"
            "RUN curl -LsSf https://astral.sh/uv/0.9.22/install.sh | sh && \\\n"
            "    install -m 0755 ${HOME}/.local/bin/uv /usr/local/bin/uv && \\\n"
            "    install -m 0755 ${HOME}/.local/bin/uvx /usr/local/bin/uvx\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")

        original_candidates = uv_cache.host_uv_binary_cache_candidates
        try:
            uv_cache.host_uv_binary_cache_candidates = lambda: {
                "uv": fake_uv,
                "uvx": fake_uvx,
            }
            staged_path, metadata = runner.stage_task_for_sandbox(
                task_path=task,
                jobs_dir=root / "jobs",
                job_name="pddl-tpp-planning-goal",
                sandbox="docker",
                include_task_skills=False,
            )
        finally:
            uv_cache.host_uv_binary_cache_candidates = original_candidates

        assert metadata["dockerfile_uv_binary_cache_context_created"] is True
        assert metadata["dockerfile_uv_binary_cache_available"] is True
        assert metadata["dockerfile_uv_binary_cache_binary_count"] == 2
        assert metadata["dockerfile_uv_binary_cache_has_uv"] is True
        assert metadata["dockerfile_uv_binary_cache_has_uvx"] is True
        assert metadata["dockerfile_uv_binary_cache_dockerfile_patch_applied"] is True
        assert metadata["dockerfile_uv_binary_cache_raw_path_recorded"] is False

        cache_dir = staged_path / "environment" / "loopx_uv_cache"
        assert (cache_dir / "uv").exists()
        assert (cache_dir / "uvx").exists()
        staged_text = (staged_path / "environment" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert uv_cache.DOCKER_UV_BINARY_CACHE_BEGIN in staged_text
        assert "COPY loopx_uv_cache/ /opt/loopx_uv_cache/" in staged_text
        assert "uv --version >/dev/null 2>&1" in staged_text
        assert "python3 -m pip install ${loopx_pip_break_system_packages}" in staged_text


if __name__ == "__main__":
    test_staged_dockerfile_prefers_host_uv_binary_cache()
    print("skillsbench-uv-cache-smoke: ok")
