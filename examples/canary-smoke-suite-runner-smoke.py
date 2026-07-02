#!/usr/bin/env python3
"""Smoke-test the canary smoke-suite runner contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.runner import build_canary_smoke_suite_run  # noqa: E402


def assert_default_public_preview_excludes_grouped_smokes() -> None:
    payload = build_canary_smoke_suite_run(
        suite="default-public",
        execute=False,
        limit=20,
    )
    assert payload["ok"] is True, payload
    assert payload["dry_run"] is True, payload
    commands = [check["command"] for check in payload["selected_checks"]]
    assert commands, payload
    assert all("canary-promotion-readiness-smoke.py" not in item for item in commands), payload
    assert all("dashboard-demo-readiness-smoke.py" not in item for item in commands), payload


def assert_full_public_preview_injects_safe_group_args() -> None:
    payload = build_canary_smoke_suite_run(
        suite="full-public",
        scripts=[
            "examples/canary-promotion-readiness-smoke.py",
            "dashboard-demo-readiness-smoke.py",
        ],
        execute=False,
    )
    assert payload["ok"] is True, payload
    by_script = {
        check["normalized"]["script"]: check["normalized"]
        for check in payload["selected_checks"]
    }
    assert "--no-write-evidence" in by_script["examples/canary-promotion-readiness-smoke.py"]["argv"], payload
    assert "--skip-browser" in by_script["examples/dashboard-demo-readiness-smoke.py"]["argv"], payload


def assert_module_preview_selects_matching_scripts() -> None:
    payload = build_canary_smoke_suite_run(
        suite="default-public",
        modules=["quota"],
        execute=False,
        limit=10,
    )
    assert payload["ok"] is True, payload
    assert payload["selected_check_count"] > 0, payload
    commands = [check["command"] for check in payload["selected_checks"]]
    assert all("quota" in command for command in commands), payload


def assert_catalog_profile_preview_is_supported() -> None:
    payload = build_canary_smoke_suite_run(
        suite="catalog-plan",
        profiles=["repo-architecture-budget"],
        execute=False,
    )
    assert payload["ok"] is True, payload
    assert payload["selected_check_count"] == 1, payload
    assert payload["selected_checks"][0]["command"] == "python3 examples/repo-python-line-budget-smoke.py", payload
    assert payload["catalog_plan"]["planned_check_count"] == 1, payload


def assert_cli_json_preview_works() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "smoke-suite",
            "--suite",
            "default-public",
            "--module",
            "canary",
            "--limit",
            "2",
            "--no-execute",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "canary_smoke_suite_run_v0", payload
    assert payload["selected_check_count"] == 2, payload
    assert payload["executes_checks"] is False, payload


def main() -> int:
    assert_default_public_preview_excludes_grouped_smokes()
    assert_full_public_preview_injects_safe_group_args()
    assert_module_preview_selects_matching_scripts()
    assert_catalog_profile_preview_is_supported()
    assert_cli_json_preview_works()
    print("canary-smoke-suite-runner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
