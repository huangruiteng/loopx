#!/usr/bin/env python3
"""Smoke-test catalog-informed canary profile planning."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.canary.planner import (  # noqa: E402
    build_catalog_canary_plan,
    build_catalog_canary_profiles,
)


def assert_profiles_come_from_catalog_matrix() -> None:
    payload = build_catalog_canary_profiles()
    assert payload["ok"] is True, payload
    assert payload["dry_run"] is True, payload
    assert payload["executes_checks"] is False, payload
    families = {profile["family"] for profile in payload["profiles"]}
    assert {
        "Work Routing",
        "Human Decision",
        "State And Boundary",
        "Evidence Lifecycle",
        "Planning Governance",
    } <= families, payload
    work_routing = next(profile for profile in payload["profiles"] if profile["family"] == "Work Routing")
    assert "IP-001" in work_routing["pattern_ids"], work_routing
    assert work_routing["candidate_checks"], work_routing
    assert all("command" in check and "reason" in check for check in work_routing["candidate_checks"])


def assert_plan_selects_minimal_profiles_from_changed_surfaces() -> None:
    payload = build_catalog_canary_plan(
        changed_files=["loopx/quota.py", "loopx/status.py"],
        surfaces=["scheduler hint", "quota should-run"],
        max_checks_per_family=2,
    )
    families = [profile["family"] for profile in payload["profiles"]]
    assert "Work Routing" in families, payload
    assert "State And Boundary" in families, payload
    assert "Evidence Lifecycle" not in families, payload
    for profile in payload["profiles"]:
        assert len(profile["candidate_checks"]) <= 2, profile
        assert profile["selection_reasons"], profile
    assert payload["executes_checks"] is False, payload


def assert_cli_json_plan_is_dry_run() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "plan",
            "--changed-file",
            "loopx/quota.py",
            "--surface",
            "scheduler hint",
            "--max-checks-per-family",
            "1",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert payload["dry_run"] is True, payload
    assert payload["executes_checks"] is False, payload
    assert payload["profile_count"] >= 1, payload
    work_routing = next(profile for profile in payload["profiles"] if profile["family"] == "Work Routing")
    assert len(work_routing["candidate_checks"]) == 1, work_routing


def main() -> int:
    assert_profiles_come_from_catalog_matrix()
    assert_plan_selects_minimal_profiles_from_changed_surfaces()
    assert_cli_json_plan_is_dry_run()
    print("catalog-canary-planner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
