#!/usr/bin/env python3
"""Smoke-test the issue-fix workflow planner CLI."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.workflow_plan import (  # noqa: E402
    ISSUE_FIX_WORKFLOW_PLAN_PACKET_SCHEMA_VERSION,
    build_issue_fix_workflow_plan_packet,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

FORBIDDEN_VALUES = [
    "raw issue body text that must stay gated",
    "full issue comment text that must stay gated",
    "raw provider response payload",
    "secret-value",
    "credential-value",
]


def assert_public_safe(payload: dict[str, Any] | str) -> None:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"payload matched private pattern {pattern.pattern!r}")
    leaked = [value for value in FORBIDDEN_VALUES if value in text]
    assert not leaked, leaked


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def assert_workflow_shape(payload: dict[str, Any]) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == ISSUE_FIX_WORKFLOW_PLAN_PACKET_SCHEMA_VERSION
    assert payload["mode"] == "issue-fix-workflow-plan"
    assert payload["external_writes_performed"] is False
    assert payload["todo_write_performed"] is False
    assert payload["local_paths_captured"] is False
    assert payload["private_repo_state_read"] is False
    assert payload["destructive_git_used"] is False
    assert payload["issue_body_captured"] is False
    assert payload["comment_bodies_captured"] is False

    first_screen = payload["first_screen"]
    assert first_screen["waiting_on"] == "agent", first_screen
    assert first_screen["user_action_required"] is False, first_screen
    assert first_screen["agent_can_continue"] is True, first_screen

    todos = payload["ordered_loopx_todo_writeback_preview"]
    assert len(todos) >= 2, todos
    assert [todo["planner_order"] for todo in todos] == sorted(
        todo["planner_order"] for todo in todos
    )
    assert [todo["action_kind"] for todo in todos[:2]] == [
        "issue_fix_public_metadata_classification",
        "issue_fix_feasibility_decision",
    ]
    assert not any(
        todo["action_kind"] == "issue_fix_branch_validation" for todo in todos
    ), todos
    assert [todo["priority"] for todo in todos[:2]] == ["P0", "P0"]
    assert all(todo["would_write"] is False for todo in todos)
    assert all(todo["requires_execute_flag"] is True for todo in todos)

    routes = {route["route"]: route for route in payload["resolution_route_candidates"]}
    assert set(routes) == {"fix_pr", "comment_only", "triage_only"}, routes
    assert routes["fix_pr"]["next_action_kind"] == "issue_fix_branch_validation"
    assert routes["comment_only"]["requires_user_gate_before_external_write"] is True
    feasibility = payload["feasibility_checkpoint_plan"]
    assert feasibility["selects_exactly_one_route"] is True, feasibility
    assert feasibility["routes"] == ["fix_pr", "comment_only", "triage_only"]
    assert feasibility["writes_domain_state_by_default_with_goal_id"] is True
    assert feasibility["persists_repository_context_with_feasibility"] is True
    assert "--repository-context-json" in feasibility["command_preview"]
    assert feasibility["writes_loopx_todo"] is False
    post_pr = payload["post_pr_lifecycle_monitor_plan"]
    assert post_pr["schema_version"] == "issue_fix_post_pr_lifecycle_monitor_plan_v1"
    assert post_pr["creates_per_pr_continuous_monitor_todo"] is False, post_pr
    assert post_pr["monitor_scope"] == "lifecycle_state_bucket", post_pr
    assert post_pr["materializes_nonempty_buckets_only"] is True, post_pr
    assert post_pr["terminal_members_removed"] is True, post_pr
    assert post_pr["per_pr_material_actions_are_one_shot"] is True, post_pr
    assert post_pr["external_notification_granularity"] == "one_pr_per_message"
    assert "runnable_successor" in post_pr["decisions"], post_pr

    review = payload["review_packet_preview"]
    assert review["schema_version"] == "issue_fix_pr_review_packet_v0", review
    assert review["ready"] is False, review
    assert review["external_issue_comment_performed"] is False, review
    assert review["external_pr_created"] is False, review
    assert review["merge_performed"] is False, review
    assert "validation_not_run" in review["readiness_blockers"], review
    description = review["pr_description_contract"]
    assert description["schema_version"] == "issue_fix_pr_description_contract_v0"
    assert description["builder_contract"] == {
        "schema_version": "issue_fix_pr_description_build_v0",
        "surface": "issue_fix.pr_description",
        "default_enabled": False,
        "explicit_dependency_injection": True,
        "provider_call_budget": 1,
        "fail_open_preserves_base_description": True,
        "applied_preferences_require_compact_receipt": True,
    }
    assert description["source_contract"] == "pr_review_five_block_template_v0"
    assert [section["label"] for section in description["sections"]] == [
        "动机",
        "改动思路",
        "关键代码或伪代码",
        "具体改动",
        "修复后复现",
        "验证",
        "对主干的风险与未覆盖",
        "关联 Issue",
    ]
    assert description["sections"][2]["applicability"] == "code_changes"
    assert description["sections"][4]["accepted_surfaces"] == [
        "repository_cli",
        "focused_code_or_test",
    ]
    assert description["infographic_policy"] == {
        "required": False,
        "allowed_when": "complex_change",
        "must_not_replace_textual_evidence": True,
    }
    assert description["issue_reference_policy"] == {
        "schema_version": "issue_fix_pr_issue_reference_policy_v0",
        "default_closing_keyword": "Fixes",
        "partial_fix_prefix": "Related to",
        "closing_requires_default_branch": True,
        "full_syntax_required_per_issue": True,
        "applied_after_semantic_preferences": True,
        "verification_surface": "closingIssuesReferences",
    }
    assert description["review_only_section_excluded"] == "我的整体评价"
    assert description["requires_current_diff_evidence"] is True

    validation = payload["validation"]
    assert validation["ok"] is True, validation
    assert validation["todo_preview_count"] == len(todos), validation
    assert_public_safe(payload)


def main() -> int:
    packet = build_issue_fix_workflow_plan_packet(
        url="https://github.com/huangruiteng/loopx/issues/123",
        validation_label="python3 examples/focused-smoke.py",
    )
    assert_workflow_shape(packet)
    assert packet["branch_plan"]["status"] == "needs_approved_repo_context", packet
    assert (
        "approved_repo_context_missing"
        in packet["review_packet_preview"]["readiness_blockers"]
    )

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-plan-") as tmpdir:
        tmp = Path(tmpdir)
        metadata_path = tmp / "metadata.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "number": 123,
                    "state": "open",
                    "title": "Crash on workflow planner",
                    "labels": [{"name": "bug"}, {"name": "needs-repro"}],
                    "body": "raw issue body text that must stay gated",
                    "comments": ["full issue comment text that must stay gated"],
                    "raw": "raw provider response payload",
                }
            ),
            encoding="utf-8",
        )
        result = run_cli(
            [
                "issue-fix",
                "workflow-plan",
                "--url",
                "https://github.com/huangruiteng/loopx/issues/123",
                "--metadata-json",
                str(metadata_path),
                "--repo-path",
                str(tmp / "approved-repo-not-read-in-dry-run"),
                "--base-branch",
                "main",
                "--validation-label",
                "python3 examples/focused-smoke.py",
            ]
        )
    cli_packet = json.loads(result.stdout)
    assert_workflow_shape(cli_packet)
    assert cli_packet["branch_plan"]["status"] == "approved_repo_dry_run", cli_packet
    assert cli_packet["branch_plan"]["repo_path_captured"] is False, cli_packet
    assert cli_packet["branch_plan"]["private_repo_state_read"] is False, cli_packet
    gated = [
        todo
        for todo in cli_packet["ordered_loopx_todo_writeback_preview"]
        if todo["action_kind"] == "approve_github_issue_body_or_comment_read"
    ]
    assert len(gated) == 1, cli_packet
    assert gated[0]["role"] == "user", gated
    assert gated[0]["priority"] == "P0", gated
    assert gated[0]["would_write"] is False, gated
    assert_public_safe(result.stdout)

    markdown = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "issue-fix",
            "workflow-plan",
            "--url",
            "https://github.com/huangruiteng/loopx/issues/123",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    assert "# LoopX Issue Fix Workflow Plan" in markdown, markdown
    assert "Ordered Todo Writeback Preview" in markdown, markdown
    assert "Feasibility Checkpoint" in markdown, markdown
    assert "Resolution Routes" in markdown, markdown
    assert "Post-PR Lifecycle Monitor" in markdown, markdown
    assert "PR Review Packet Preview" in markdown, markdown
    assert "issue_fix_pr_state_<state_bucket>_monitor" in markdown, markdown
    assert "creates_per_pr_continuous_monitor_todo: `False`" in markdown, markdown
    assert_public_safe(markdown)

    print("issue-fix-workflow-plan-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
