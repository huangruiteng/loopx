#!/usr/bin/env python3
"""Run the focused benchmark-integrity pytest unit and CLI contract gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.qualification_profiles import (  # noqa: E402
    BENCHMARK_TOOLKIT_DEEP_TEST_PATHS,
)


def main() -> int:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *BENCHMARK_TOOLKIT_DEEP_TEST_PATHS,
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
