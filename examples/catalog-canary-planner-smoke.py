#!/usr/bin/env python3
"""Smoke-test catalog-informed canary profile planning."""

from __future__ import annotations

import json
import os
import shutil
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
from loopx.cli_commands.canary import collect_git_diff_changed_files  # noqa: E402


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
        "install-update",
        "control-plane-refactor",
        "status-read-path",
        "review-packet-read-path",
        "event-sourced-read-path",
        "cli-command-contract",
        "todo-lifecycle",
        "monitor-scheduler",
        "state-write-correctness",
        "product-entry-workflows",
        "cross-runtime-impl-review-demo",
        "host-command-entry",
        "runtime-connector-catalog",
        "frontstage-rollout",
        "auto-research-demo",
        "catalog-canary-contract",
        "benchmark-adapter-readiness",
    } <= domain_profile_ids, payload
    domain_profiles = {profile["id"]: profile for profile in payload["domain_profiles"]}
    state_write_commands = [
        check["command"] for check in domain_profiles["state-write-correctness"]["checks"]
    ]
    assert "python3 examples/todo-write-correctness-smoke.py" in state_write_commands


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
    assert payload["suggested_check_count"] == len(payload["suggested_checks"]), payload
    assert payload["commands"] == [
        check["command"] for check in payload["suggested_checks"]
    ], payload
    assert payload["suggested_checks"][0]["source"] == "domain_profile", payload
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
    release_profiles = {profile["id"]: profile for profile in release_payload["domain_profiles"]}
    release_profile_ids = set(release_profiles)
    assert "release-promotion" in release_profile_ids, release_payload
    assert "install-update" in release_profile_ids, release_payload
    release_commands = [
        check["command"] for check in release_profiles["release-promotion"]["checks"]
    ]
    assert "python3 examples/canary-promotion-readiness-boundary-smoke.py" in release_commands

    install_payload = build_catalog_canary_plan(
        changed_files=["scripts/install-local.sh", "loopx/self_update.py"],
        surfaces=["install update rollback"],
    )
    install_profiles = {profile["id"]: profile for profile in install_payload["domain_profiles"]}
    assert "install-update" in install_profiles, install_payload
    install_profile = install_profiles["install-update"]
    install_commands = [check["command"] for check in install_profile["checks"]]
    assert "python3 examples/install-local-smoke.py" in install_commands, install_profile
    assert "python3 examples/loopx-update-smoke.py" in install_commands, install_profile
    assert all(check["tier"] == "default" for check in install_profile["checks"]), install_profile
    assert install_profile["deep_checks_available"] is True, install_profile

    refactor_payload = build_catalog_canary_plan(
        changed_files=["loopx/quota.py", "loopx/status.py"],
        surfaces=["control-plane refactor scheduler hint"],
    )
    refactor_profile_ids = {profile["id"] for profile in refactor_payload["domain_profiles"]}
    assert "control-plane-refactor" in refactor_profile_ids, refactor_payload

    work_lane_policy_payload = build_catalog_canary_plan(
        changed_files=["loopx/policies/monitor_todo.py"],
        surfaces=["resume_when resume_ready work-lane policy seam"],
        max_checks_per_profile=4,
    )
    work_lane_profiles = {
        profile["id"]: profile for profile in work_lane_policy_payload["domain_profiles"]
    }
    assert "control-plane-refactor" in work_lane_profiles, work_lane_policy_payload
    work_lane_commands = [
        check["command"] for check in work_lane_profiles["control-plane-refactor"]["checks"]
    ]
    assert "python3 examples/quota-resume-gated-open-todo-smoke.py" in work_lane_commands, (
        work_lane_profiles["control-plane-refactor"]
    )
    assert "python3 examples/quota-cleared-blocker-successor-gate-smoke.py" in work_lane_commands, (
        work_lane_profiles["control-plane-refactor"]
    )
    assert all(
        check["tier"] == "default"
        for check in work_lane_profiles["control-plane-refactor"]["checks"]
    ), work_lane_profiles["control-plane-refactor"]

    status_payload = build_catalog_canary_plan(
        changed_files=["loopx/status.py"],
        surfaces=["status --goal-id read-path"],
    )
    status_profiles = {profile["id"]: profile for profile in status_payload["domain_profiles"]}
    assert "status-read-path" in status_profiles, status_payload
    status_commands = [check["command"] for check in status_profiles["status-read-path"]["checks"]]
    assert "python3 examples/status-goal-filter-smoke.py" in status_commands, status_payload
    assert all(check["tier"] == "default" for check in status_profiles["status-read-path"]["checks"]), status_payload

    review_packet_payload = build_catalog_canary_plan(
        changed_files=["loopx/review_packet.py", "loopx/cli_commands/status.py"],
        surfaces=["review-packet handoff-only operator packet read-path"],
    )
    review_packet_profiles = {
        profile["id"]: profile for profile in review_packet_payload["domain_profiles"]
    }
    assert "review-packet-read-path" in review_packet_profiles, review_packet_payload
    review_packet_profile = review_packet_profiles["review-packet-read-path"]
    review_packet_commands = [check["command"] for check in review_packet_profile["checks"]]
    assert "python3 examples/review-packet-cli-smoke.py" in review_packet_commands, review_packet_profile
    assert "python3 examples/review-packet-smoke.py" in review_packet_commands, review_packet_profile
    assert all(check["tier"] == "default" for check in review_packet_profile["checks"]), review_packet_profile
    assert review_packet_profile["deep_checks_available"] is True, review_packet_profile
    assert review_packet_profile["deep_checks_included"] is False, review_packet_profile

    event_read_payload = build_catalog_canary_plan(
        changed_files=["loopx/event_sourced_state.py", "loopx/rollout_event_log.py"],
        surfaces=["event projection downstream read event-store read-path"],
    )
    event_read_profiles = {
        profile["id"]: profile for profile in event_read_payload["domain_profiles"]
    }
    assert "event-sourced-read-path" in event_read_profiles, event_read_payload
    event_read_profile = event_read_profiles["event-sourced-read-path"]
    event_read_commands = [check["command"] for check in event_read_profile["checks"]]
    assert "python3 examples/event-sourced-state-api-smoke.py" in event_read_commands, event_read_profile
    assert "python3 examples/event-sourced-status-read-path-smoke.py" in event_read_commands, event_read_profile
    assert "python3 examples/event-sourced-downstream-read-path-smoke.py" in event_read_commands, event_read_profile
    assert all(check["tier"] == "default" for check in event_read_profile["checks"]), event_read_profile
    assert event_read_profile["deep_checks_available"] is True, event_read_profile
    assert event_read_profile["deep_checks_included"] is False, event_read_profile

    cli_payload = build_catalog_canary_plan(
        changed_files=["loopx/cli.py", "loopx/cli_commands/version.py"],
        surfaces=["cli command modularization"],
    )
    cli_profile_ids = {profile["id"] for profile in cli_payload["domain_profiles"]}
    assert "cli-command-contract" in cli_profile_ids, cli_payload
    cli_profile = next(profile for profile in cli_payload["domain_profiles"] if profile["id"] == "cli-command-contract")
    commands = [check["command"] for check in cli_profile["checks"]]
    assert "python3 examples/cli-version-command-modularization-smoke.py" in commands, cli_profile

    todo_payload = build_catalog_canary_plan(
        changed_files=["loopx/todos.py", "loopx/todo_contract.py"],
        surfaces=["todo lifecycle todo claim todo list"],
    )
    todo_profiles = {profile["id"]: profile for profile in todo_payload["domain_profiles"]}
    assert "todo-lifecycle" in todo_profiles, todo_payload
    todo_profile = todo_profiles["todo-lifecycle"]
    todo_commands = [check["command"] for check in todo_profile["checks"]]
    assert "python3 examples/todo-lifecycle-cli-smoke.py" in todo_commands, todo_profile
    assert all(check["tier"] == "default" for check in todo_profile["checks"]), todo_profile
    assert todo_profile["deep_checks_available"] is True, todo_profile

    product_entry_payload = build_catalog_canary_plan(
        changed_files=[
            "README.md",
            "docs/capabilities/issue-fix/README.md",
            "docs/update-notes/README.md",
            "loopx/capabilities/content_ops/surface.py",
            "scripts/update_notes_release_job.py",
        ],
        surfaces=["product-entry issue-fix content-ops update-note cross-runtime demo"],
        max_checks_per_profile=4,
    )
    product_entry_profiles = {
        profile["id"]: profile for profile in product_entry_payload["domain_profiles"]
    }
    assert "product-entry-workflows" in product_entry_profiles, product_entry_payload
    assert "install-update" not in product_entry_profiles, product_entry_payload
    product_entry_profile = product_entry_profiles["product-entry-workflows"]
    product_entry_commands = [check["command"] for check in product_entry_profile["checks"]]
    assert "python3 examples/issue-fix-workflow-contract-smoke.py" in product_entry_commands, product_entry_profile
    assert "python3 examples/content-ops-issue-fix-intake-smoke.py" in product_entry_commands, product_entry_profile
    assert "python3 examples/readme-demo-surface-smoke.py" in product_entry_commands, product_entry_profile
    assert "python3 examples/update-notes-archive-smoke.py" in product_entry_commands, product_entry_profile
    assert all(check["tier"] == "default" for check in product_entry_profile["checks"]), product_entry_profile
    assert product_entry_profile["deep_checks_available"] is True, product_entry_profile
    assert product_entry_profile["deep_checks_included"] is False, product_entry_profile

    cross_runtime_payload = build_catalog_canary_plan(
        changed_files=[
            "loopx/capabilities/cross_runtime/impl_review.py",
            "loopx/cli_commands/starter.py",
            "docs/product/cross-runtime-impl-review-demo.md",
        ],
        surfaces=[
            "loopx demo impl-review claude implements codex reviews "
            "cross_runtime_impl_review_demo_packet_v0"
        ],
        max_checks_per_profile=3,
    )
    cross_runtime_profiles = {
        profile["id"]: profile for profile in cross_runtime_payload["domain_profiles"]
    }
    assert "cross-runtime-impl-review-demo" in cross_runtime_profiles, cross_runtime_payload
    cross_runtime_profile = cross_runtime_profiles["cross-runtime-impl-review-demo"]
    cross_runtime_commands = [check["command"] for check in cross_runtime_profile["checks"]]
    assert (
        "python3 examples/cross-runtime-impl-review-demo-smoke.py" in cross_runtime_commands
    ), cross_runtime_profile
    assert "python3 examples/readme-demo-surface-smoke.py" in cross_runtime_commands
    assert all(check["tier"] == "default" for check in cross_runtime_profile["checks"])
    assert cross_runtime_profile["deep_checks_available"] is False, cross_runtime_profile
    assert cross_runtime_profile["deep_checks_included"] is False, cross_runtime_profile

    host_command_payload = build_catalog_canary_plan(
        changed_files=[
            "loopx/cli_commands/slash_commands.py",
            "docs/reference/protocols/codex-app-host-command-registry-v0.md",
            "docs/reference/protocols/global-manager-command-v0.md",
        ],
        surfaces=["slash-commands /loopx-global-summary host command registry"],
        max_checks_per_profile=3,
    )
    host_command_profiles = {
        profile["id"]: profile for profile in host_command_payload["domain_profiles"]
    }
    assert "host-command-entry" in host_command_profiles, host_command_payload
    host_command_profile = host_command_profiles["host-command-entry"]
    host_command_commands = [check["command"] for check in host_command_profile["checks"]]
    assert "python3 examples/slash-command-catalog-smoke.py" in host_command_commands
    assert "python3 examples/codex-app-host-command-registry-smoke.py" in host_command_commands
    assert "python3 examples/global-manager-command-protocol-smoke.py" in host_command_commands
    assert all(check["tier"] == "default" for check in host_command_profile["checks"])
    assert host_command_profile["deep_checks_available"] is False, host_command_profile
    assert host_command_profile["deep_checks_included"] is False, host_command_profile

    runtime_connector_payload = build_catalog_canary_plan(
        changed_files=["docs/runtime-connector-catalog.md"],
        surfaces=[
            "runtime connector catalog codex app heartbeat codex cli tui "
            "claude code loop worker bridge scheduler_hint scoped identity"
        ],
        max_checks_per_profile=4,
    )
    runtime_connector_profiles = {
        profile["id"]: profile for profile in runtime_connector_payload["domain_profiles"]
    }
    assert "runtime-connector-catalog" in runtime_connector_profiles, runtime_connector_payload
    runtime_connector_profile = runtime_connector_profiles["runtime-connector-catalog"]
    runtime_connector_commands = [
        check["command"] for check in runtime_connector_profile["checks"]
    ]
    assert "python3 examples/heartbeat-prompt-smoke.py" in runtime_connector_commands
    assert (
        "python3 examples/codex-cli-tui-bootstrap-smoke-bundle-smoke.py"
        in runtime_connector_commands
    )
    assert "python3 examples/claude-goalmode-lifecycle-smoke.py" in runtime_connector_commands
    assert "python3 examples/worker-bridge-install-contract-smoke.py" in runtime_connector_commands
    assert all(check["tier"] == "default" for check in runtime_connector_profile["checks"])
    assert runtime_connector_profile["deep_checks_available"] is True, runtime_connector_profile
    assert runtime_connector_profile["deep_checks_included"] is False, runtime_connector_profile

    auto_research_payload = build_catalog_canary_plan(
        changed_files=["loopx/capabilities/auto_research/core.py"],
        surfaces=["auto-research demo frontier visible launcher"],
    )
    auto_research_profiles = {
        profile["id"]: profile for profile in auto_research_payload["domain_profiles"]
    }
    assert "auto-research-demo" in auto_research_profiles, auto_research_payload
    auto_research_profile = auto_research_profiles["auto-research-demo"]
    auto_research_commands = [check["command"] for check in auto_research_profile["checks"]]
    assert (
        "python3 examples/auto-research-minimal-kernel-smoke.py"
        in auto_research_commands
    ), auto_research_profile
    assert (
        "python3 examples/decentralized-auto-research-frontier-smoke.py" in auto_research_commands
    ), auto_research_profile
    assert all(check["tier"] == "default" for check in auto_research_profile["checks"]), auto_research_profile
    assert auto_research_profile["deep_checks_available"] is True, auto_research_profile


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


def assert_explicit_catalog_profile_id_selects_family_profile() -> None:
    payload = build_catalog_canary_plan(
        profiles=["state-and-boundary"],
        max_checks_per_family=4,
    )
    assert payload["profile_count"] == 1, payload
    assert payload["domain_profile_count"] == 0, payload
    profile = payload["profiles"][0]
    assert profile["id"] == "state-and-boundary", profile
    assert profile["family"] == "State And Boundary", profile
    assert profile["selection_reasons"] == [
        "selected because this catalog profile was explicitly requested",
    ], profile
    assert "python3 examples/todo-contract-smoke.py" in payload["commands"], payload
    assert all(
        check["source"] == "catalog_family"
        for check in payload["suggested_checks"]
    ), payload


def assert_catalog_canary_selects_own_profile_not_benchmark() -> None:
    payload = build_catalog_canary_plan(
        changed_files=["loopx/canary/planner.py", "loopx/canary/runner.py"],
        surfaces=["catalog canary runner"],
    )
    domain_profiles = {profile["id"]: profile for profile in payload["domain_profiles"]}
    assert "catalog-canary-contract" in domain_profiles, payload
    assert "benchmark-adapter-readiness" not in domain_profiles, payload
    commands = payload["commands"]
    assert "python3 examples/catalog-canary-planner-smoke.py" in commands, payload
    assert "python3 examples/catalog-canary-run-e2e-smoke.py" in commands, payload


def assert_install_update_does_not_select_release_promotion() -> None:
    payload = build_catalog_canary_plan(
        changed_files=["loopx/doctor.py", "examples/install-local-smoke.py"],
        max_checks_per_profile=3,
    )
    domain_profiles = {profile["id"]: profile for profile in payload["domain_profiles"]}
    assert "install-update" in domain_profiles, payload
    assert "release-promotion" not in domain_profiles, payload
    commands = payload["commands"]
    assert "python3 examples/install-local-smoke.py" in commands, payload
    assert "python3 examples/loopx-update-smoke.py" in commands, payload
    assert all("canary-promotion-readiness-smoke.py" not in command for command in commands), payload


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _make_git_diff_selector_repo(tmp_dir: Path) -> tuple[Path, str]:
    repo = tmp_dir / "selector-repo"
    repo.mkdir()
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "loopx-smoke@example.invalid")
    _run_git(repo, "config", "user.name", "LoopX Smoke")

    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-m", "base")
    base_ref = _run_git(repo, "rev-parse", "HEAD").stdout.strip()

    committed_path = repo / "loopx" / "canary" / "planner.py"
    committed_path.parent.mkdir(parents=True)
    committed_path.write_text("# committed canary planner change\n", encoding="utf-8")
    _run_git(repo, "add", "loopx/canary/planner.py")
    _run_git(repo, "commit", "-m", "committed canary planner")

    unstaged_path = repo / "examples" / "catalog-canary-planner-smoke.py"
    unstaged_path.parent.mkdir(parents=True)
    unstaged_path.write_text("# tracked catalog canary smoke change\n", encoding="utf-8")
    _run_git(repo, "add", "examples/catalog-canary-planner-smoke.py")
    _run_git(repo, "commit", "-m", "tracked catalog canary smoke")

    staged_path = repo / "loopx" / "cli_commands" / "canary.py"
    staged_path.parent.mkdir(parents=True)
    staged_path.write_text("# staged cli canary change\n", encoding="utf-8")
    _run_git(repo, "add", "loopx/cli_commands/canary.py")

    unstaged_path.write_text("# unstaged catalog canary smoke change\n", encoding="utf-8")

    untracked_path = repo / "docs" / "new-catalog-canary-note.md"
    untracked_path.parent.mkdir(parents=True)
    untracked_path.write_text("# untracked catalog canary note\n", encoding="utf-8")
    return repo, base_ref


def assert_git_diff_selector_covers_pr_and_worktree_changes(tmp_dir: Path) -> None:
    repo, base_ref = _make_git_diff_selector_repo(tmp_dir)
    assert _run_git(repo, "diff", "--name-only", "--cached").stdout.splitlines() == [
        "loopx/cli_commands/canary.py",
    ]
    assert _run_git(repo, "diff", "--name-only").stdout.splitlines() == [
        "examples/catalog-canary-planner-smoke.py",
    ]
    assert _run_git(repo, "ls-files", "--others", "--exclude-standard").stdout.splitlines() == [
        "docs/new-catalog-canary-note.md",
    ]
    selector = collect_git_diff_changed_files(repo_root=repo, base_ref=base_ref)
    assert selector["ok"] is True, selector
    assert selector["successful_sources"] == ["base", "staged", "unstaged", "untracked"], selector
    assert selector["changed_files"] == [
        "examples/catalog-canary-planner-smoke.py",
        "loopx/canary/planner.py",
        "loopx/cli_commands/canary.py",
        "docs/new-catalog-canary-note.md",
    ], selector

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "plan",
            "--from-git-diff",
            "--git-diff-base",
            base_ref,
        ],
        cwd=repo,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert payload["selector_sources"]["git_diff"]["changed_file_count"] == 4, payload
    assert payload["selection_inputs"]["changed_files"] == selector["changed_files"], payload
    domain_profile_ids = {profile["id"] for profile in payload["domain_profiles"]}
    assert "catalog-canary-contract" in domain_profile_ids, payload
    assert "benchmark-adapter-readiness" not in domain_profile_ids, payload
    assert "python3 examples/catalog-canary-planner-smoke.py" in payload["commands"], payload


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
    assert payload["suggested_check_count"] == len(payload["commands"]), payload
    assert payload["commands"], payload
    assert all(check["command"] in payload["commands"] for check in payload["suggested_checks"]), payload
    work_routing = next(profile for profile in payload["profiles"] if profile["family"] == "Work Routing")
    assert len(work_routing["candidate_checks"]) == 1, work_routing
    assert any(profile["id"] == "monitor-scheduler" for profile in payload["domain_profiles"]), payload


def assert_cli_profile_accepts_catalog_profile_id() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "canary",
            "plan",
            "--profile",
            "state-and-boundary",
            "--max-checks-per-family",
            "1",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    payload = json.loads(completed.stdout)
    assert payload["profile_count"] == 1, payload
    assert payload["domain_profile_count"] == 0, payload
    assert payload["profiles"][0]["id"] == "state-and-boundary", payload
    assert payload["commands"] == ["python3 examples/todo-contract-smoke.py"], payload


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
    assert_explicit_catalog_profile_id_selects_family_profile()
    assert_catalog_canary_selects_own_profile_not_benchmark()
    assert_install_update_does_not_select_release_promotion()
    assert_coverage_audit_tracks_p0_p1_patterns()
    tmp = tempfile.mkdtemp(prefix="loopx-catalog-canary-smoke-")
    try:
        tmp_dir = Path(tmp)
        assert_coverage_audit_reports_matrix_drift(tmp_dir)
        assert_git_diff_selector_covers_pr_and_worktree_changes(tmp_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert_cli_json_plan_is_dry_run()
    assert_cli_profile_accepts_catalog_profile_id()
    assert_cli_json_coverage_audit_is_dry_run()
    print("catalog-canary-planner-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
