#!/usr/bin/env python3
"""Smoke-test structured delivery_outcome enum enforcement."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.delivery_outcome import (  # noqa: E402
    ACCOUNTABLE_DELIVERY_OUTCOMES,
    DELIVERY_OUTCOME_CHOICES,
    DELIVERY_OUTCOME_UNKNOWN,
    DeliveryOutcome,
    FOLLOWTHROUGH_REQUIRED_DELIVERY_OUTCOMES,
    normalize_delivery_outcome,
    require_delivery_outcome,
)
from loopx.history import append_benchmark_run  # noqa: E402
from loopx.state_refresh import refresh_state_run  # noqa: E402
from loopx.status import delivery_outcome_for_run  # noqa: E402


GOAL_ID = "delivery-outcome-enum-fixture"


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
        "# Delivery Outcome Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] Advance primary result evidence.\n\n"
        "## Next Action\n\n"
        "- Advance primary result evidence.\n",
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
    assert DELIVERY_OUTCOME_CHOICES == (
        "surface_only",
        "outcome_gap",
        "outcome_progress",
        "primary_goal_outcome",
    )
    assert require_delivery_outcome("surface_only") == DeliveryOutcome.SURFACE_ONLY
    assert normalize_delivery_outcome("unknown") is None
    assert ACCOUNTABLE_DELIVERY_OUTCOMES == {
        DeliveryOutcome.OUTCOME_PROGRESS,
        DeliveryOutcome.PRIMARY_GOAL_OUTCOME,
    }
    assert FOLLOWTHROUGH_REQUIRED_DELIVERY_OUTCOMES == {
        DeliveryOutcome.SURFACE_ONLY,
        DeliveryOutcome.OUTCOME_GAP,
    }
    try:
        require_delivery_outcome("contract_v0_delivered")
    except ValueError as exc:
        assert "delivery_outcome must be one of:" in str(exc)
    else:
        raise AssertionError("invalid delivery outcome accepted")


def assert_refresh_state_enforces_enum(registry_path: Path) -> None:
    payload = refresh_state_run(
        registry_path=registry_path,
        runtime_root_override=None,
        goal_id=GOAL_ID,
        project=None,
        state_file=None,
        classification="enum_fixture_progress",
        recommended_action="Advance primary result evidence.",
        delivery_outcome=DeliveryOutcome.OUTCOME_PROGRESS.value,
        dry_run=True,
        sync_global=False,
    )
    assert payload["delivery_outcome"] == DeliveryOutcome.OUTCOME_PROGRESS.value, payload

    try:
        refresh_state_run(
            registry_path=registry_path,
            runtime_root_override=None,
            goal_id=GOAL_ID,
            project=None,
            state_file=None,
            classification="enum_fixture_invalid",
            recommended_action="Advance primary result evidence.",
            delivery_outcome="contract_v0_delivered",
            dry_run=True,
            sync_global=False,
        )
    except ValueError as exc:
        assert "delivery_outcome must be one of:" in str(exc)
    else:
        raise AssertionError("refresh-state accepted invalid delivery outcome")

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
            "--delivery-outcome",
            "contract_v0_delivered",
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
        delivery_outcome=DeliveryOutcome.PRIMARY_GOAL_OUTCOME.value,
        dry_run=True,
    )
    assert payload["delivery_outcome"] == DeliveryOutcome.PRIMARY_GOAL_OUTCOME.value, payload

    try:
        append_benchmark_run(
            registry_path=registry_path,
            runtime_root_override=None,
            goal_id=GOAL_ID,
            benchmark_run=compact_run,
            delivery_outcome="runner_contract_v0_delivered",
            dry_run=True,
        )
    except ValueError as exc:
        assert "delivery_outcome must be one of:" in str(exc)
    else:
        raise AssertionError("history append accepted invalid delivery outcome")


def assert_status_uses_enum_not_classification() -> None:
    assert (
        delivery_outcome_for_run(
            {
                "classification": "runner_contract_v0_delivered",
                "delivery_outcome": DeliveryOutcome.OUTCOME_PROGRESS.value,
            }
        )
        == DeliveryOutcome.OUTCOME_PROGRESS.value
    )
    assert (
        delivery_outcome_for_run(
            {
                "classification": "runner_contract_v0_delivered",
                "delivery_outcome": "contract_v0_delivered",
            }
        )
        == DELIVERY_OUTCOME_UNKNOWN
    )


def main() -> int:
    assert_enum_sets()
    with tempfile.TemporaryDirectory(prefix="delivery-outcome-enum-") as tmp:
        registry_path, _runtime = write_fixture(Path(tmp))
        assert_refresh_state_enforces_enum(registry_path)
        assert_history_enforces_enum(registry_path)
    assert_status_uses_enum_not_classification()
    print("delivery outcome enum smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
