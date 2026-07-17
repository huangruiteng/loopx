#!/usr/bin/env python3
"""Smoke-test the issue-fix workflow as one end-to-end product path."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.acceptance_loop import (  # noqa: E402
    build_issue_fix_acceptance_fixture_packet,
    build_issue_fix_repo_branch_fixture_packet,
)
from loopx.capabilities.issue_fix.intake_surface import (  # noqa: E402
    build_content_ops_issue_fix_metadata_preview_packet,
)
from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.workflow_plan import (  # noqa: E402
    build_issue_fix_workflow_plan_packet,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"/tmp/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

FORBIDDEN_VALUES = [
    "raw issue body text that must stay gated",
    "full issue comment text that must stay gated",
    "raw provider response payload",
    "private repro log",
    "secret-value",
    "credential-value",
    str(ROOT),
]


def assert_public_safe(payload: dict[str, Any] | str) -> None:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    leaked = [value for value in FORBIDDEN_VALUES if value and value in text]
    assert not leaked, leaked
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"payload matched private pattern {pattern.pattern!r}")


def todo_by_action(plan: dict[str, Any], action_kind: str) -> dict[str, Any]:
    matches = [
        todo
        for todo in plan["ordered_loopx_todo_writeback_preview"]
        if todo.get("action_kind") == action_kind
    ]
    assert len(matches) == 1, (action_kind, matches)
    return matches[0]


def test_metadata_to_ordered_todos_and_gates() -> None:
    provider_payload = {
        "number": 123,
        "state": "open",
        "title": "Crash on public metadata route",
        "labels": [{"name": "bug"}, {"name": "needs-repro"}],
        "body": "raw issue body text that must stay gated",
        "comments": ["full issue comment text that must stay gated"],
        "raw": "raw provider response payload",
    }

    metadata = build_content_ops_issue_fix_metadata_preview_packet(
        url="https://github.com/huangruiteng/loopx/issues/123",
        provider_payload=provider_payload,
    )
    assert metadata["ok"] is True, metadata
    assert metadata["external_writes_performed"] is False, metadata
    assert metadata["todo_write_performed"] is False, metadata
    preview = metadata["github_metadata_preview"]
    assert preview["body_captured"] is False, preview
    assert preview["comment_bodies_captured"] is False, preview
    assert metadata["adapter_preview"]["gated_provider_fields_present"] == [
        "body",
        "comments",
        "raw",
    ], metadata

    intake = metadata["issue_fix_intake"]
    assert intake["first_screen"]["waiting_on"] == "agent", intake
    assert intake["first_screen"]["user_action_required"] is False, intake
    owner_gate = next(
        gate for gate in intake["gate_projections"] if gate["gate_id"] == "owner_triage_gate"
    )
    private_gate = next(
        gate
        for gate in intake["gate_projections"]
        if gate["gate_id"] == "private_repro_material_gate"
    )
    assert owner_gate["role"] == "owner", owner_gate
    assert owner_gate["action_required"] is False, owner_gate
    assert private_gate["role"] == "user", private_gate
    assert "private log read" in private_gate["blocks"], private_gate

    plan = build_issue_fix_workflow_plan_packet(
        url="https://github.com/huangruiteng/loopx/issues/123",
        provider_payload=provider_payload,
        validation_label="python3 examples/focused-smoke.py",
    )
    assert plan["ok"] is True, plan
    assert plan["todo_write_performed"] is False, plan
    assert [todo["planner_order"] for todo in plan["ordered_loopx_todo_writeback_preview"]] == [
        1,
        2,
        3,
    ], plan
    assert todo_by_action(plan, "issue_fix_public_metadata_classification")["role"] == "agent"
    assert todo_by_action(plan, "issue_fix_feasibility_decision")["priority"] == "P0"
    gated_read = todo_by_action(plan, "approve_github_issue_body_or_comment_read")
    assert gated_read["role"] == "user", gated_read
    assert gated_read["priority"] == "P0", gated_read
    assert gated_read["would_write"] is False, gated_read
    action_kinds = {
        todo["action_kind"] for todo in plan["ordered_loopx_todo_writeback_preview"]
    }
    assert "issue_fix_branch_validation" not in action_kinds, action_kinds
    assert "issue_fix_pr_lifecycle_monitor" not in action_kinds, action_kinds
    routes = {route["route"]: route for route in plan["resolution_route_candidates"]}
    assert set(routes) == {"fix_pr", "comment_only", "triage_only"}, routes
    assert routes["fix_pr"]["next_action_kind"] == "issue_fix_branch_validation"
    assert routes["comment_only"]["external_issue_comment_performed"] is False
    assert routes["comment_only"]["requires_user_gate_before_external_write"] is True
    checkpoint = plan["feasibility_checkpoint_plan"]
    assert checkpoint["selects_exactly_one_route"] is True, checkpoint
    assert checkpoint["writes_domain_state_by_default_with_goal_id"] is True
    post_pr = plan["post_pr_lifecycle_monitor_plan"]
    assert post_pr["schema_version"] == "issue_fix_post_pr_lifecycle_monitor_plan_v1"
    assert post_pr["creates_per_pr_continuous_monitor_todo"] is False, post_pr
    assert post_pr["monitor_scope"] == "lifecycle_state_bucket", post_pr
    assert post_pr["per_pr_material_actions_are_one_shot"] is True, post_pr
    assert post_pr["external_notification_granularity"] == "one_pr_per_message"
    assert "no_followup" in post_pr["decisions"], post_pr

    decision = build_issue_fix_feasibility_packet(
        url="https://github.com/huangruiteng/loopx/issues/123",
        reproduction_status="planned",
        reproduction_label="focused repro plan",
        scope_class="bounded",
        validation_label="python3 examples/focused-smoke.py",
    )
    assert decision["decision"]["route"] == "fix_pr", decision
    assert decision["transition"]["projected_todo"]["action_kind"] == (
        "issue_fix_confirm_reproduction"
    ), decision
    assert decision["external_writes_performed"] is False, decision

    review_preview = plan["review_packet_preview"]
    assert review_preview["ready"] is False, review_preview
    assert "validation_not_run" in review_preview["readiness_blockers"], review_preview
    assert review_preview["external_pr_created"] is False, review_preview
    assert review_preview["merge_performed"] is False, review_preview
    assert_public_safe(metadata)
    assert_public_safe(plan)
    assert_public_safe(decision)


def test_validation_and_review_packet_readiness() -> None:
    acceptance = build_issue_fix_acceptance_fixture_packet(
        url="https://github.com/huangruiteng/loopx/issues/123"
    )
    assert acceptance["ok"] is True, acceptance
    artifact = acceptance["validated_fix_artifact"]
    assert artifact["repro_before"]["passed"] is False, artifact
    assert artifact["patch"]["patch_applied"] is True, artifact
    assert artifact["patch"]["file"] == "calculator.py", artifact
    assert artifact["validation_after"]["passed"] is True, artifact
    assert artifact["review_packet"]["ready"] is True, artifact
    assert artifact["review_packet"]["external_issue_comment_performed"] is False, artifact
    assert artifact["review_packet"]["external_pr_created"] is False, artifact
    assert artifact["review_packet"]["merge_performed"] is False, artifact

    branch = build_issue_fix_repo_branch_fixture_packet(
        url="https://github.com/huangruiteng/loopx/issues/123"
    )
    assert branch["ok"] is True, branch
    branch_artifact = branch["validated_fix_artifact"]
    assert branch_artifact["repo_branch"]["branch_created"] is True, branch_artifact
    assert branch_artifact["repo_branch"]["issue_branch"] == (
        "codex/issue-123-public-metadata-fixture"
    )
    assert branch_artifact["validation_after"]["passed"] is True, branch_artifact
    assert branch_artifact["review_packet"]["ready"] is True, branch_artifact
    assert branch_artifact["review_packet"]["files_changed"] == ["calculator.py"]
    assert all(step["passed"] is True for step in branch_artifact["git_steps"])
    assert all(step["stdout_captured"] is False for step in branch_artifact["git_steps"])
    assert all(step["stderr_captured"] is False for step in branch_artifact["git_steps"])
    assert_public_safe(acceptance)
    assert_public_safe(branch)


def main() -> int:
    test_metadata_to_ordered_todos_and_gates()
    test_validation_and_review_packet_readiness()
    print("issue-fix-workflow-e2e-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
