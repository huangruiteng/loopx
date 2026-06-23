#!/usr/bin/env python3
"""Smoke-test structured delivery_batch_scale enum enforcement."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.delivery_batch_scale import (  # noqa: E402
    DELIVERY_BATCH_SCALE_CHOICES,
    SMALL_DELIVERY_BATCH_SCALES,
    UNKNOWN_DELIVERY_BATCH_SCALE,
    DeliveryBatchScale,
    normalize_delivery_batch_scale,
    require_delivery_batch_scale,
)
from loopx.history import append_benchmark_run  # noqa: E402
from loopx.state_refresh import refresh_state_run  # noqa: E402
from loopx.status import delivery_batch_scale_for_run  # noqa: E402


GOAL_ID = "delivery-batch-scale-enum-fixture"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = Path(".codex/goals") / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    (project / state_file).parent.mkdir(parents=True, exist_ok=True)
    (project / state_file).write_text(
        "---\n"
        "status: active\n"
        "---\n\n"
        "# Delivery Batch Scale Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Advance one bounded implementation batch.\n\n"
        "## Next Action\n\n"
        "- Advance one bounded implementation batch.\n",
        encoding="utf-8",
    )
    registry_path = project / ".loopx" / "registry.json"
    write_json(
        registry_path,
        {
            "schema_version": 1,
            "common_runtime_root": str(runtime),
            "goals": [
                {
                    "id": GOAL_ID,
                    "domain": "enum-fixture",
                    "status": "active",
                    "repo": str(project),
                    "state_file": str(state_file),
                    "adapter": {"kind": "harness_self_improvement", "status": "connected"},
                    "quota": {"compute": 1.0, "window_hours": 24},
                }
            ],
        },
    )
    return registry_path, runtime


def assert_enum_sets() -> None:
    assert DELIVERY_BATCH_SCALE_CHOICES == (
        "test_only",
        "single_surface",
        "multi_surface",
        "implementation",
    )
    assert require_delivery_batch_scale("multi_surface") == DeliveryBatchScale.MULTI_SURFACE
    assert normalize_delivery_batch_scale("unknown") is None
    assert SMALL_DELIVERY_BATCH_SCALES == {
        DeliveryBatchScale.TEST_ONLY,
        DeliveryBatchScale.SINGLE_SURFACE,
    }
    try:
        require_delivery_batch_scale("implementation_plus_validation")
    except ValueError as exc:
        assert "delivery_batch_scale must be one of:" in str(exc)
    else:
        raise AssertionError("invalid delivery batch scale accepted")


def assert_refresh_state_enforces_enum(registry_path: Path) -> None:
    payload = refresh_state_run(
        registry_path=registry_path,
        runtime_root_override=None,
        goal_id=GOAL_ID,
        project=None,
        state_file=None,
        classification="enum_fixture_progress",
        recommended_action="Advance one bounded implementation batch.",
        delivery_batch_scale=DeliveryBatchScale.IMPLEMENTATION.value,
        dry_run=True,
        sync_global=False,
    )
    assert payload["delivery_batch_scale"] == DeliveryBatchScale.IMPLEMENTATION.value, payload

    try:
        refresh_state_run(
            registry_path=registry_path,
            runtime_root_override=None,
            goal_id=GOAL_ID,
            project=None,
            state_file=None,
            classification="enum_fixture_invalid",
            recommended_action="Advance one bounded implementation batch.",
            delivery_batch_scale="implementation_plus_validation",
            dry_run=True,
            sync_global=False,
        )
    except ValueError as exc:
        assert "delivery_batch_scale must be one of:" in str(exc)
    else:
        raise AssertionError("refresh-state accepted invalid delivery batch scale")

    cli_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            "refresh-state",
            "--goal-id",
            GOAL_ID,
            "--delivery-batch-scale",
            "implementation_plus_validation",
            "--dry-run",
            "--no-global-sync",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert cli_result.returncode != 0, cli_result.stdout
    assert "invalid choice" in cli_result.stderr, cli_result.stderr


def assert_history_enforces_enum(registry_path: Path) -> None:
    compact_run = {
        "schema_version": "benchmark_run_v0",
        "benchmark": {"id": "fixture"},
        "case": {"id": "fixture-case"},
    }
    payload = append_benchmark_run(
        registry_path=registry_path,
        runtime_root_override=None,
        goal_id=GOAL_ID,
        benchmark_run=compact_run,
        delivery_batch_scale=DeliveryBatchScale.MULTI_SURFACE.value,
        dry_run=True,
    )
    assert payload["delivery_batch_scale"] == DeliveryBatchScale.MULTI_SURFACE.value, payload

    try:
        append_benchmark_run(
            registry_path=registry_path,
            runtime_root_override=None,
            goal_id=GOAL_ID,
            benchmark_run=compact_run,
            delivery_batch_scale="batch_plus_raw_logs",
            dry_run=True,
        )
    except ValueError as exc:
        assert "delivery_batch_scale must be one of:" in str(exc)
    else:
        raise AssertionError("history append accepted invalid delivery batch scale")


def assert_status_uses_enum_not_raw_value() -> None:
    assert (
        delivery_batch_scale_for_run(
            {
                "classification": "runner_batch_fixture",
                "delivery_batch_scale": DeliveryBatchScale.MULTI_SURFACE.value,
            }
        )
        == DeliveryBatchScale.MULTI_SURFACE.value
    )
    assert (
        delivery_batch_scale_for_run(
            {
                "classification": "runner_batch_fixture",
                "delivery_batch_scale": "batch_plus_raw_logs",
            }
        )
        == UNKNOWN_DELIVERY_BATCH_SCALE
    )
    assert (
        delivery_batch_scale_for_run({"classification": "owner_handoff_consumer_test"})
        == DeliveryBatchScale.TEST_ONLY.value
    )


def main() -> int:
    assert_enum_sets()
    with tempfile.TemporaryDirectory(prefix="delivery-batch-scale-enum-") as tmp:
        registry_path, _runtime = write_fixture(Path(tmp))
        assert_refresh_state_enforces_enum(registry_path)
        assert_history_enforces_enum(registry_path)
    assert_status_uses_enum_not_raw_value()
    print("delivery batch scale enum smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
