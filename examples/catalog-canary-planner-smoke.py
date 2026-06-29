#!/usr/bin/env python3
"""Smoke-test catalog-informed canary profile planning."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
CATALOG = REPO_ROOT / "docs" / "interaction-pattern-catalog.md"

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
    domain_profile_ids = {profile["id"] for profile in payload["domain_profiles"]}
    assert {
        "pr-review-and-merge",
        "release-promotion",
        "control-plane-refactor",
        "monitor-scheduler",
        "state-write-correctness",
        "frontstage-rollout",
        "benchmark-adapter-readiness",
    } <= domain_profile_ids, payload


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
    domain_profiles = {profile["id"]: profile for profile in payload["domain_profiles"]}
    assert "control-plane-refactor" in domain_profiles, payload
    assert "monitor-scheduler" in domain_profiles, payload
    for profile in domain_profiles.values():
        assert all(check["tier"] == "default" for check in profile["checks"]), profile
        assert profile["deep_checks_available"] is True, profile
        assert profile["deep_checks_included"] is False, profile
    assert payload["executes_checks"] is False, payload


def assert_catalog_documents_selection_rules() -> None:
    catalog = CATALOG.read_text(encoding="utf-8")
    for snippet in [
        "Use this selection order for ordinary PR, release, and refactor review:",
        "Start from changed files and touched surfaces, not from the PR title.",
        "PR review or self-merge workflow",
        "Release or install promotion",
        "Control-plane refactor",
        "Keep default profiles on fixture-level or dry-run checks.",
        "When hot-path and cold-path surfaces both changed",
        "Existing-contract-first rule: canary planning should consume current public\nruntime/status surfaces",
        "`quota should-run`, `status`, `review-packet`, `loopx check`, current smoke\nfixtures, `loopx canary plan` output, and fixture-level `loopx canary run`\nchecks as the first evidence layer",
        "`loopx canary run` must stay no-write by\ndefault",
        "not write promotion evidence, create runtime contracts, poll external targets,\nor run deep/browser checks",
        "stop at\na review packet first",
        "owner review before implementation",
    ]:
        assert snippet in catalog, snippet


def assert_pr_release_and_refactor_profiles_select() -> None:
    pr_payload = build_catalog_canary_plan(
        changed_files=["loopx/pr_review.py", "skills/loopx-pr-review/SKILL.md"],
        surfaces=["pr-review public PR metadata"],
    )
    pr_profile_ids = {profile["id"] for profile in pr_payload["domain_profiles"]}
    assert "pr-review-and-merge" in pr_profile_ids, pr_payload

    release_payload = build_catalog_canary_plan(
        changed_files=["docs/product/release-readiness.md"],
        surfaces=["release promotion install update"],
    )
    release_profile_ids = {profile["id"] for profile in release_payload["domain_profiles"]}
    assert "release-promotion" in release_profile_ids, release_payload

    refactor_payload = build_catalog_canary_plan(
        changed_files=["loopx/quota.py", "loopx/status.py"],
        surfaces=["control-plane refactor scheduler hint"],
    )
    refactor_profile_ids = {profile["id"] for profile in refactor_payload["domain_profiles"]}
    assert "control-plane-refactor" in refactor_profile_ids, refactor_payload


def assert_explicit_profile_can_include_deep_checks() -> None:
    payload = build_catalog_canary_plan(
        profiles=["benchmark-adapter-readiness"],
        include_deep_checks=True,
        max_checks_per_profile=3,
    )
    assert payload["profile_count"] == 0, payload
    assert payload["domain_profile_count"] == 1, payload
    profile = payload["domain_profiles"][0]
    assert profile["id"] == "benchmark-adapter-readiness", profile
    assert profile["deep_checks_included"] is True, profile
    assert any(check["tier"] == "deep" for check in profile["checks"]), profile
    assert "existing public runtime/status contracts first" in payload["note"], payload
    assert "owner-review necessity/risk packet" in payload["note"], payload


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
    assert any(profile["id"] == "monitor-scheduler" for profile in payload["domain_profiles"]), payload


def main() -> int:
    assert_profiles_come_from_catalog_matrix()
    assert_catalog_documents_selection_rules()
    assert_plan_selects_minimal_profiles_from_changed_surfaces()
    assert_pr_release_and_refactor_profiles_select()
    assert_explicit_profile_can_include_deep_checks()
    assert_cli_json_plan_is_dry_run()
    print("catalog-canary-planner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
