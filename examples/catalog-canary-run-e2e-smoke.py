#!/usr/bin/env python3
"""Smoke-test catalog-informed canary execution without writeback."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.runner import (  # noqa: E402
    build_catalog_canary_run,
    normalize_canary_command,
)


def assert_release_readiness_gets_no_write_argument() -> None:
    normalized = normalize_canary_command("python3 examples/canary-promotion-readiness-smoke.py")
    assert normalized["ok"] is True, normalized
    assert "--no-write-evidence" in normalized["argv"], normalized
    assert normalized["injected_args"] == ["--no-write-evidence"], normalized


def assert_preview_does_not_execute_or_write() -> None:
    payload = build_catalog_canary_run(
        profiles=["release-promotion"],
        max_checks_per_profile=1,
        check_limit=1,
        execute=False,
    )
    assert payload["ok"] is True, payload
    assert payload["dry_run"] is True, payload
    assert payload["executes_checks"] is False, payload
    assert payload["writes_evidence"] is False, payload
    assert payload["creates_runtime_contract"] is False, payload
    assert payload["selected_check_count"] == 1, payload
    selected = payload["selected_checks"][0]
    assert selected["normalized"]["ok"] is True, selected
    assert "--no-write-evidence" in selected["normalized"]["argv"], selected


def assert_profile_fixture_executes() -> None:
    payload = build_catalog_canary_run(
        profiles=["control-plane-refactor"],
        max_checks_per_profile=1,
        check_limit=1,
        execute=True,
        timeout_seconds=60,
    )
    assert payload["ok"] is True, payload
    assert payload["dry_run"] is False, payload
    assert payload["executes_checks"] is True, payload
    assert payload["writes_evidence"] is False, payload
    assert payload["executed_check_count"] == 1, payload
    result = payload["selected_checks"][0]
    assert result["status"] == "passed", result
    assert result["profile_id"] == "control-plane-refactor", result


def assert_cli_run_executes_catalog_selected_check() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "run",
            "--changed-file",
            "loopx/quota.py",
            "--surface",
            "scheduler hint",
            "--max-checks-per-family",
            "1",
            "--max-checks-per-profile",
            "1",
            "--check-limit",
            "1",
            "--timeout-seconds",
            "60",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True, payload
    assert payload["executes_checks"] is True, payload
    assert payload["writes_evidence"] is False, payload
    assert payload["selected_check_count"] == 1, payload
    assert payload["selected_checks"][0]["status"] == "passed", payload


def main() -> int:
    assert_release_readiness_gets_no_write_argument()
    assert_preview_does_not_execute_or_write()
    assert_profile_fixture_executes()
    assert_cli_run_executes_catalog_selected_check()
    print("catalog-canary-run-e2e-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
