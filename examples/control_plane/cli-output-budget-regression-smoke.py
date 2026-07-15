#!/usr/bin/env python3
"""Run the real agent-facing CLI output budget matrix from canary plans."""

from __future__ import annotations

import runpy
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEST_PATH = REPO_ROOT / "tests" / "control_plane" / "test_cli_output_budget.py"
DIFFERENTIAL_SMOKE = (
    REPO_ROOT
    / "examples"
    / "control_plane"
    / "cli-output-base-head-differential-smoke.py"
)


def _run_budget_checks() -> None:
    tests = runpy.run_path(str(TEST_PATH))
    tests["test_manifest_covers_the_declared_agent_facing_surface_set"]()
    with tempfile.TemporaryDirectory(prefix="loopx-cli-output-budget-") as temp_dir:
        root = Path(temp_dir)
        tests["test_real_cli_output_stays_inside_the_characterized_baseline"](
            root / "scenarios"
        )
        tests["test_collection_growth_and_bootstrap_duplication_are_explicit"](
            root / "growth"
        )
        tests["test_explicit_compact_and_detail_modes_are_characterized"](
            root / "mode-variants"
        )


def main() -> int:
    if not TEST_PATH.is_file():
        raise RuntimeError(
            f"missing CLI output budget test: {TEST_PATH.relative_to(REPO_ROOT)}"
        )
    _run_budget_checks()
    completed = subprocess.run(
        [sys.executable, str(DIFFERENTIAL_SMOKE.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "agent-facing CLI base/head differential failed\n"
            f"stdout:\n{completed.stdout[-3000:]}\n"
            f"stderr:\n{completed.stderr[-3000:]}"
        )
    print("cli-output-budget-regression-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
