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
    assert len(todos) >= 5, todos
    assert [todo["planner_order"] for todo in todos] == sorted(
        todo["planner_order"] for todo in todos
    )
    assert [todo["action_kind"] for todo in todos[:4]] == [
        "issue_fix_public_metadata_classification",
        "issue_fix_repro_and_route",
        "issue_fix_branch_validation",
        "issue_fix_pr_review_packet",
    ]
    assert [todo["priority"] for todo in todos[:3]] == ["P0", "P0", "P0"]
    assert all(todo["would_write"] is False for todo in todos)
    assert all(todo["requires_execute_flag"] is True for todo in todos)

    review = payload["review_packet_preview"]
    assert review["schema_version"] == "issue_fix_pr_review_packet_v0", review
    assert review["ready"] is False, review
    assert review["external_issue_comment_performed"] is False, review
    assert review["external_pr_created"] is False, review
    assert review["merge_performed"] is False, review
    assert "validation_not_run" in review["readiness_blockers"], review

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
    assert "approved_repo_context_missing" in packet["review_packet_preview"][
        "readiness_blockers"
    ]

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
    assert "issue_fix_pr_review_packet" in markdown, markdown
    assert_public_safe(markdown)

    print("issue-fix-workflow-plan-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
