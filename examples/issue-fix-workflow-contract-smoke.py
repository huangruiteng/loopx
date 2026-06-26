#!/usr/bin/env python3
"""Smoke-test the public issue-fix workflow contract."""

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
    ISSUE_FIX_CALLER_REPO_BRANCH_PACKET_SCHEMA_VERSION,
    ISSUE_FIX_VALIDATED_FIX_ARTIFACT_SCHEMA_VERSION,
    build_issue_fix_caller_repo_branch_packet,
)
from loopx.capabilities.issue_fix.intake_surface import (  # noqa: E402
    CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION,
    CONTENT_OPS_ISSUE_FIX_METADATA_PREVIEW_PACKET_SCHEMA_VERSION,
    ISSUE_FIX_INTAKE_SCHEMA_VERSION,
    build_content_ops_issue_fix_intake_packet,
    build_content_ops_issue_fix_metadata_preview_packet,
)
from loopx.capabilities.issue_fix.metadata_preview import (  # noqa: E402
    GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION,
)


DOC = ROOT / "docs/capabilities/issue-fix/protocols/issue-fix-workflow-contract-v0.md"
README = ROOT / "docs/capabilities/issue-fix/README.md"

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
    "private repro log",
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


def assert_ordered(text: str, markers: list[str]) -> None:
    offset = -1
    for marker in markers:
        found = text.find(marker)
        assert found > offset, f"{marker!r} missing or out of order"
        offset = found


def main() -> int:
    doc = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    assert doc.startswith("# issue_fix_workflow_contract_v0")
    assert "issue-fix-workflow-contract-v0.md" in readme
    assert "python3 examples/issue-fix-workflow-contract-smoke.py" in readme
    assert_ordered(
        doc,
        [
            "**Metadata preview:**",
            "**Intake classification:**",
            "**Workflow plan:**",
            "**LoopX todo writeback:**",
            "**Caller repo branch:**",
            "**Validation:**",
            "**PR review packet:**",
            "**Gate handling:**",
        ],
    )
    for schema in (
        GITHUB_ISSUE_METADATA_PREVIEW_SCHEMA_VERSION,
        CONTENT_OPS_ISSUE_FIX_METADATA_PREVIEW_PACKET_SCHEMA_VERSION,
        CONTENT_OPS_ISSUE_FIX_INTAKE_PACKET_SCHEMA_VERSION,
        ISSUE_FIX_INTAKE_SCHEMA_VERSION,
        "issue_fix_workflow_plan_packet_v0",
        "loopx_todo_writeback_preview_v0",
        ISSUE_FIX_CALLER_REPO_BRANCH_PACKET_SCHEMA_VERSION,
        ISSUE_FIX_VALIDATED_FIX_ARTIFACT_SCHEMA_VERSION,
        "issue_fix_pr_review_packet_v0",
    ):
        assert schema in doc, schema
    for boundary in (
        "issue_body_captured: false",
        "comment_bodies_captured: false",
        "local_paths_captured: false",
        "external_writes_performed: false",
        "destructive_git_used: false",
    ):
        assert boundary in doc, boundary

    provider_payload = {
        "number": 123,
        "state": "open",
        "title": "Crash on metadata adapter preview",
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
    assert metadata["github_metadata_preview"]["body_captured"] is False, metadata
    assert metadata["github_metadata_preview"]["comment_bodies_captured"] is False
    assert metadata["github_metadata_preview"]["gated_provider_fields_present"] == [
        "body",
        "comments",
        "raw",
    ]
    previews = metadata["adapter_preview"]["candidate_loopx_todo_writeback_preview"]
    assert [preview["role"] for preview in previews] == ["agent", "user"], previews
    assert all(preview["would_write"] is False for preview in previews), previews
    assert_public_safe(metadata)

    intake = build_content_ops_issue_fix_intake_packet(
        repo="huangruiteng/loopx",
        issue_ref="issue_123",
    )
    assert intake["ok"] is True, intake
    issue_intake = intake["issue_fix_intake"]
    assert issue_intake["first_screen"]["waiting_on"] == "agent", issue_intake
    assert issue_intake["first_screen"]["user_action_required"] is False, issue_intake
    assert len(issue_intake["agent_todo_candidates"]) >= 3, issue_intake
    assert {gate["gate_id"] for gate in issue_intake["gate_projections"]} == {
        "owner_triage_gate",
        "private_repro_material_gate",
    }
    assert_public_safe(intake)

    dry_run = build_issue_fix_caller_repo_branch_packet(
        repo_path="/not/read/in/dry/run",
        url="https://github.com/huangruiteng/loopx/issues/123",
        base_branch="main",
        validation_label="python test_calculator.py",
        execute=False,
    )
    assert dry_run["ok"] is True, dry_run
    assert dry_run["dry_run"] is True, dry_run
    assert dry_run["private_repo_state_read"] is False, dry_run
    assert dry_run["local_paths_captured"] is False, dry_run
    assert dry_run["review_packet"]["ready"] is False, dry_run
    assert dry_run["review_packet"]["external_pr_created"] is False, dry_run
    assert dry_run["review_packet"]["merge_performed"] is False, dry_run
    assert_public_safe(dry_run)

    print("issue-fix-workflow-contract-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
