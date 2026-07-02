#!/usr/bin/env python3
"""Smoke-test recursive smoke-suite discovery under examples subdirectories."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.runner import build_canary_smoke_suite_run  # noqa: E402


SCRIPT = "examples/canary/smoke-suite-subdir-discovery-smoke.py"


def assert_selector(selector: str) -> None:
    payload = build_canary_smoke_suite_run(
        suite="default-public",
        scripts=[selector],
        execute=False,
    )
    assert payload["ok"] is True, payload
    assert payload["warning_count"] == 0, payload
    assert payload["selected_check_count"] == 1, payload
    assert payload["selected_checks"][0]["normalized"]["script"] == SCRIPT, payload


def main() -> int:
    assert_selector(SCRIPT)
    assert_selector("canary/smoke-suite-subdir-discovery-smoke.py")
    assert_selector("smoke-suite-subdir-discovery-smoke.py")
    print("smoke-suite-subdir-discovery-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
