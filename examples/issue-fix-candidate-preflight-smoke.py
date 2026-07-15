#!/usr/bin/env python3
"""Smoke-test deterministic prior-work dedupe before Issue Fix planning."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.candidate_preflight import (  # noqa: E402
    build_issue_fix_candidate_preflight_packet,
)
from loopx.capabilities.issue_fix.workflow_plan import (  # noqa: E402
    build_issue_fix_workflow_plan_packet,
)


def fixture() -> dict[str, object]:
    return {
        "schema_version": "issue_fix_candidate_preflight_input_v0",
        "domain_state": {
            "repo": "volcengine/OpenViking",
            "issue_ref": "issues_3005",
            "route": "comment_only",
            "status": "open",
        },
        "numeric_pr_evidence": [],
        "semantic_pr_evidence": [
            {
                "repo": "volcengine/OpenViking",
                "pr_ref": "pull_2999",
                "state": "OPEN",
                "url": "https://github.com/volcengine/OpenViking/pull/2999",
                "related_issue_refs": ["#3005"],
                "relation": "implementation",
                "current_revision_verified": True,
            }
        ],
        "agentic_recall_receipt": {
            "status": "completed_no_influence",
            "call_count": 2,
            "max_calls": 2,
        },
    }


def assert_reuse(packet: dict[str, object]) -> None:
    assert packet["ok"] is True, packet
    decision = packet["decision"]
    assert decision["route"] == "reuse_existing_pr", decision
    assert decision["candidate_runnable"] is False, decision
    assert decision["existing_pr_refs"] == ["pull_2999"], decision
    evidence = packet["evidence"]
    assert evidence["domain_state_matched"] is True, evidence
    assert evidence["numeric_pr_matches"] == [], evidence
    assert len(evidence["semantic_pr_matches"]) == 1, evidence
    recall = packet["agentic_recall"]
    assert recall == {
        "receipt_status": "completed_no_influence",
        "call_count": 2,
        "max_calls": 2,
        "action": "preserve_existing_receipt",
        "provider_calls_performed": 0,
        "raw_memory_captured": False,
    }, recall
    assert packet["external_reads_performed"] is False, packet
    assert packet["external_writes_performed"] is False, packet


def main() -> int:
    generated_at = "2026-07-15T00:00:00Z"
    preflight = build_issue_fix_candidate_preflight_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        input_payload=fixture(),
        generated_at=generated_at,
    )
    assert_reuse(preflight)

    plan = build_issue_fix_workflow_plan_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        candidate_preflight_input=fixture(),
        generated_at=generated_at,
    )
    assert plan["ok"] is True, plan
    assert plan["candidate_fix_workflow_allowed"] is False, plan
    assert_reuse(plan["candidate_preflight"])
    todos = plan["ordered_loopx_todo_writeback_preview"]
    assert [todo["action_kind"] for todo in todos] == [
        "issue_fix_reuse_existing_pr"
    ], todos
    assert "agentic recall" in todos[0]["text"], todos
    assert plan["first_screen"]["top_agent_todo"] == todos[0], plan

    gated_non_proceed = build_issue_fix_workflow_plan_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        provider_payload={
            "number": 3005,
            "state": "open",
            "title": "Existing implementation candidate",
            "body": "body remains behind the provider-content gate",
            "comments": ["comment remains behind the provider-content gate"],
        },
        candidate_preflight_input=fixture(),
        generated_at=generated_at,
    )
    gated_non_proceed_todos = gated_non_proceed[
        "ordered_loopx_todo_writeback_preview"
    ]
    assert [todo["action_kind"] for todo in gated_non_proceed_todos] == [
        "issue_fix_reuse_existing_pr"
    ], gated_non_proceed_todos
    assert gated_non_proceed["first_screen"]["top_gate"] is None, gated_non_proceed

    merged_and_open = fixture()
    merged_and_open["domain_state"] = None
    merged_and_open["numeric_pr_evidence"] = [
        {
            "repo": "volcengine/OpenViking",
            "pr_ref": "pull_2998",
            "state": "MERGED",
            "url": "https://github.com/volcengine/OpenViking/pull/2998",
            "closing_issue_refs": ["#3005"],
        }
    ]
    terminal_implementation = build_issue_fix_candidate_preflight_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        input_payload=merged_and_open,
        generated_at=generated_at,
    )
    assert terminal_implementation["decision"]["route"] == "skip", (
        terminal_implementation
    )
    assert terminal_implementation["decision"]["reason_codes"] == [
        "merged_implementation_pr"
    ], terminal_implementation

    unverified = fixture()
    unverified["domain_state"] = None
    unverified["semantic_pr_evidence"][0]["current_revision_verified"] = False
    fail_open = build_issue_fix_candidate_preflight_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        input_payload=unverified,
        generated_at=generated_at,
    )
    assert fail_open["decision"]["route"] == "proceed", fail_open
    assert fail_open["decision"]["candidate_runnable"] is True, fail_open

    terminal = fixture()
    terminal["domain_state"]["status"] = "resolved"
    skipped = build_issue_fix_candidate_preflight_packet(
        repo="volcengine/OpenViking",
        issue_ref="#3005",
        input_payload=terminal,
        generated_at=generated_at,
    )
    assert skipped["decision"]["route"] == "skip", skipped

    with tempfile.TemporaryDirectory(prefix="loopx-candidate-preflight-") as raw:
        path = Path(raw) / "preflight.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "issue-fix",
                "workflow-plan",
                "--repo",
                "volcengine/OpenViking",
                "--issue-ref",
                "#3005",
                "--candidate-preflight-json",
                str(path),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    cli = json.loads(result.stdout)
    assert cli["ok"] is True, cli
    assert cli["candidate_fix_workflow_allowed"] is False, cli
    assert_reuse(cli["candidate_preflight"])
    print("issue-fix-candidate-preflight-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
