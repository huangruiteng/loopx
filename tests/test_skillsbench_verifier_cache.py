from __future__ import annotations

import stat
import tempfile
from pathlib import Path

import pytest

from loopx.benchmark_adapters import skillsbench_verifier_cache as cache
from loopx.benchmark_adapters.skillsbench_verifier_bootstrap import (
    apply_skillsbench_verifier_bootstrap_missing_score_attribution,
)
from scripts.skillsbench_automation_loop import parse_args, stage_task_for_sandbox


def test_dependency_cache_preparation_is_private_and_non_root() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root, metadata = cache.prepare_dependency_cache(
            Path(tmp) / "cache",
            requested=True,
            sandbox_user="agent",
        )

        assert root is not None
        assert metadata["verifier_dependency_cache_ready"] is True
        assert metadata["verifier_dependency_cache_raw_path_recorded"] is False
        assert metadata["verifier_dependency_cache_solver_write_access"] is False
        assert metadata["verifier_dependency_cache_scoring_material_cached"] is False
        assert cache.dependency_cache_mount(root) == [
            {
                "type": "bind",
                "source": str(root),
                "target": cache.VERIFIER_DEPENDENCY_CACHE_TARGET,
                "read_only": False,
            }
        ]
        for path in set(cache.VERIFIER_DEPENDENCY_CACHE_ENV.values()):
            relative = Path(path).relative_to(
                cache.VERIFIER_DEPENDENCY_CACHE_TARGET
            )
            assert (root / relative).is_dir()


def test_dependency_cache_rejects_root_solver() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="non-root sandbox user"):
            cache.prepare_dependency_cache(
                Path(tmp) / "cache",
                requested=True,
                sandbox_user="root",
            )


def test_dependency_cache_defaults_on_without_public_path() -> None:
    args = parse_args([])

    assert args.verifier_dependency_cache_mode == "shared"
    assert args.verifier_dependency_cache_root


def test_verifier_cache_patch_is_idempotent_and_preserves_executable_bit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        verifier = Path(tmp) / "test.sh"
        verifier.write_text("#!/bin/sh\nuvx pytest\n", encoding="utf-8")
        verifier.chmod(0o755)

        first = cache.patch_verifier_dependency_cache_env(verifier, enabled=True)
        second = cache.patch_verifier_dependency_cache_env(verifier, enabled=True)
        text = verifier.read_text(encoding="utf-8")

        assert first["verifier_dependency_cache_env_patch_applied"] is True
        assert second["verifier_dependency_cache_env_patch_applied"] is True
        assert text.count(cache.VERIFIER_DEPENDENCY_CACHE_BEGIN) == 1
        assert "export UV_CACHE_DIR=" in text
        assert "export PLAYWRIGHT_BROWSERS_PATH=" in text
        assert stat.S_IMODE(verifier.stat().st_mode) == 0o755


def test_task_staging_patches_only_bootstrap_risk_verifiers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = root / "tasks" / "cache-case"
        environment = task / "environment"
        tests = task / "tests"
        environment.mkdir(parents=True)
        tests.mkdir(parents=True)
        (environment / "Dockerfile").write_text(
            "FROM python:3.12-slim\n",
            encoding="utf-8",
        )
        (task / "task.toml").write_text("version = \"1.1\"\n", encoding="utf-8")
        verifier = tests / "test.sh"
        verifier.write_text("#!/bin/sh\nuvx pytest\n", encoding="utf-8")
        verifier.chmod(0o755)

        staged, metadata = stage_task_for_sandbox(
            task_path=task,
            jobs_dir=root / "jobs",
            job_name="cache-case-run",
            sandbox="docker",
            verifier_dependency_cache_enabled=True,
        )

        assert metadata["verifier_bootstrap_risk_detected"] is True
        assert metadata["verifier_bootstrap_risk_categories"] == ["uv_bootstrap"]
        assert metadata["verifier_dependency_cache_required"] is True
        assert metadata["verifier_dependency_cache_env_patch_applied"] is True
        staged_verifier = staged / "tests" / "test.sh"
        assert cache.VERIFIER_DEPENDENCY_CACHE_BEGIN in staged_verifier.read_text(
            encoding="utf-8"
        )


def test_final_timeout_with_bootstrap_risk_gets_precise_attribution() -> None:
    compact = {
        "official_score_status": "missing",
        "official_score": None,
        "official_task_score": {
            "kind": "skillsbench_verifier_reward",
            "passed": False,
        },
        "score_failure_attribution": "skillsbench_final_verifier_timeout",
        "failure_attribution_labels": [
            "skillsbench_final_verifier_timeout",
            "skillsbench_verifier_timeout",
            "skillsbench_runner_error",
        ],
        "attempt_accounting": {
            "failure_class": "official_score_failed",
            "failure_label": "skillsbench_runner_error",
        },
    }

    changed = apply_skillsbench_verifier_bootstrap_missing_score_attribution(
        compact,
        task_staging={
            "verifier_bootstrap_risk_detected": True,
            "verifier_uv_bootstrap_risk_detected": True,
            "verifier_dependency_cache_required": True,
            "verifier_dependency_cache_env_patch_applied": True,
        },
    )

    assert changed is True
    assert (
        compact["score_failure_attribution"]
        == "verifier_dependency_bootstrap_timeout"
    )
    assert compact["official_task_score"]["value"] is None
    assert compact["attempt_accounting"]["failure_class"] == "verifier_bootstrap_failed"
    assert compact["verifier_bootstrap_diagnostic"]["status"] == (
        "verifier_dependency_bootstrap_timed_out"
    )
