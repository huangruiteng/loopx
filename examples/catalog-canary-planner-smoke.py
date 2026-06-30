#!/usr/bin/env python3
"""Smoke-test catalog-informed canary profile planning."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
CATALOG = REPO_ROOT / "docs" / "interaction-pattern-catalog.md"

from loopx.canary.planner import (  # noqa: E402
    build_catalog_canary_coverage_audit,
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
        "status-read-path",
        "cli-command-contract",
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

    status_payload = build_catalog_canary_plan(
        changed_files=["loopx/status.py"],
        surfaces=["status --goal-id read-path"],
    )
    status_profiles = {profile["id"]: profile for profile in status_payload["domain_profiles"]}
    assert "status-read-path" in status_profiles, status_payload
    status_commands = [check["command"] for check in status_profiles["status-read-path"]["checks"]]
    assert "python3 examples/status-goal-filter-smoke.py" in status_commands, status_payload
    assert all(check["tier"] == "default" for check in status_profiles["status-read-path"]["checks"]), status_payload

    cli_payload = build_catalog_canary_plan(
        changed_files=["loopx/cli.py", "loopx/cli_commands/version.py"],
        surfaces=["cli command modularization"],
    )
    cli_profile_ids = {profile["id"] for profile in cli_payload["domain_profiles"]}
    assert "cli-command-contract" in cli_profile_ids, cli_payload
    cli_profile = next(profile for profile in cli_payload["domain_profiles"] if profile["id"] == "cli-command-contract")
    commands = [check["command"] for check in cli_profile["checks"]]
    assert "python3 examples/cli-version-command-modularization-smoke.py" in commands, cli_profile


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


def assert_coverage_audit_tracks_p0_p1_patterns() -> None:
    payload = build_catalog_canary_coverage_audit()
    assert payload["ok"] is True, payload
    assert payload["dry_run"] is True, payload
    assert payload["executes_checks"] is False, payload
    assert payload["priorities"] == ["P0", "P1"], payload
    assert payload["required_pattern_count"] >= 20, payload
    assert payload["missing_count"] == 0, payload
    assert payload["invalid_exception_count"] == 0, payload
    covered_ids = {row["pattern_id"] for row in payload["covered_patterns"]}
    assert {"IP-001", "IP-004", "IP-024", "IP-029"} <= covered_ids, payload


def assert_coverage_audit_reports_matrix_drift(tmp_dir: Path) -> None:
    catalog_text = CATALOG.read_text(encoding="utf-8")
    drift_text = catalog_text.replace(
        "| Planning Governance | IP-010, IP-013, IP-018, IP-024 |",
        "| Planning Governance | IP-010, IP-013, IP-018 |",
        1,
    )
    drift_catalog = tmp_dir / "catalog-drift.md"
    drift_catalog.write_text(drift_text, encoding="utf-8")
    payload = build_catalog_canary_coverage_audit(catalog_path=drift_catalog)
    assert payload["ok"] is False, payload
    assert payload["missing_count"] == 1, payload
    assert payload["missing_patterns"][0]["pattern_id"] == "IP-024", payload

    excepted_catalog = tmp_dir / "catalog-deferred.md"
    excepted_catalog.write_text(
        drift_text
        + "\n\n"
        "## Canary Coverage Exceptions\n\n"
        "| Pattern ID | Canary Coverage Status | Rationale | Owner |\n"
        "| --- | --- | --- | --- |\n"
        "| IP-024 | deferred | waits for a repair-delta profile owner before default canary coverage | codex-main-control |\n",
        encoding="utf-8",
    )
    excepted_payload = build_catalog_canary_coverage_audit(catalog_path=excepted_catalog)
    assert excepted_payload["ok"] is True, excepted_payload
    assert excepted_payload["missing_count"] == 0, excepted_payload
    assert excepted_payload["excepted_count"] == 1, excepted_payload
    assert excepted_payload["excepted_patterns"][0]["pattern_id"] == "IP-024", excepted_payload


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


def assert_cli_json_coverage_audit_is_dry_run() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "coverage-audit",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert payload["dry_run"] is True, payload
    assert payload["executes_checks"] is False, payload
    assert payload["drift_count"] == 0, payload


def main() -> int:
    assert_profiles_come_from_catalog_matrix()
    assert_catalog_documents_selection_rules()
    assert_plan_selects_minimal_profiles_from_changed_surfaces()
    assert_pr_release_and_refactor_profiles_select()
    assert_explicit_profile_can_include_deep_checks()
    assert_coverage_audit_tracks_p0_p1_patterns()
    with tempfile.TemporaryDirectory(prefix="loopx-catalog-canary-smoke-") as tmp:
        tmp_dir = Path(tmp)
        assert_coverage_audit_reports_matrix_drift(tmp_dir)
    assert_cli_json_plan_is_dry_run()
    assert_cli_json_coverage_audit_is_dry_run()
    print("catalog-canary-planner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
