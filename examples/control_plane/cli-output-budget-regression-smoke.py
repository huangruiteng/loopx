#!/usr/bin/env python3
"""Run the real agent-facing CLI output budget matrix from canary plans."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = REPO_ROOT / "tests" / "control_plane" / "test_cli_output_budget.py"


def _pytest_command() -> list[str]:
    try:
        import pytest  # noqa: F401
    except Exception:
        uvx = shutil.which("uvx")
        if uvx:
            return [uvx, "--with", "pytest>=8,<9", "pytest"]
        raise RuntimeError(
            "cli-output-budget-regression-smoke requires pytest or uvx; "
            "qualification fails closed when neither runner is available"
        ) from None
    return [sys.executable, "-m", "pytest"]


def main() -> int:
    if not TEST_PATH.is_file():
        raise RuntimeError(f"missing CLI output budget test: {TEST_PATH.relative_to(REPO_ROOT)}")
    completed = subprocess.run(
        [*_pytest_command(), "-q", str(TEST_PATH.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "agent-facing CLI output qualification failed\n"
            f"stdout:\n{completed.stdout[-3000:]}\n"
            f"stderr:\n{completed.stderr[-3000:]}"
        )
    print("cli-output-budget-regression-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
