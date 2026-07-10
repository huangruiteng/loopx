#!/usr/bin/env python3
"""Smoke-test issue-fix repository context and domain-state integration."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
    validate_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.repository_context import (  # noqa: E402
    ISSUE_FIX_REPOSITORY_CONTEXT_SCHEMA_VERSION,
    build_issue_fix_repository_context_packet,
)
from loopx.capabilities.issue_fix.workflow_plan import (  # noqa: E402
    build_issue_fix_workflow_plan_packet,
    validate_issue_fix_workflow_plan_packet,
)


URL = "https://github.com/volcengine/OpenViking/issues/2792"
FIXTURE = ROOT / "examples" / "fixtures" / "openviking-issue-fix-repository-context.public.json"


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    for forbidden in (
        "/Users/",
        "/private/tmp/",
        "raw issue body",
        "raw expert response",
        "credential-value",
    ):
        assert forbidden not in text, (forbidden, text)


def main() -> int:
    context_input = json.loads(FIXTURE.read_text(encoding="utf-8"))
    context = build_issue_fix_repository_context_packet(
        repo="volcengine/OpenViking",
        issue_ref="issue_2792",
        context_input=context_input,
    )
    assert context["ok"] is True, context
    assert context["schema_version"] == ISSUE_FIX_REPOSITORY_CONTEXT_SCHEMA_VERSION
    assert context["context_status"] == "grounded", context
    assert context["unresolved_required_aspects"] == [], context
    assert context["coverage"]["reproduction"]["status"] == "grounded", context
    assert context["coverage"]["validation"]["status"] == "grounded", context
    assert context["expert_consultation"]["answer_is_authority"] is False, context
    assert context["expert_consultation"]["external_write_authorized"] is False
    assert context["memory_projection"]["writeback_performed"] is False
    assert_public_safe(context)

    advisory_only = {
        "schema_version": "issue_fix_repository_context_input_v0",
        "repository_revision": "public-revision-1",
        "sources": [
            {
                "source_id": "expert-only",
                "source_kind": "external_expert",
                "reference": "expert:repository",
                "trust": "advisory",
                "freshness": "current",
                "supports": ["change_scope", "reproduction", "validation"],
                "consultation_state": "queried",
                "summary": "Compact expert conclusion awaiting repository verification.",
            }
        ],
    }
    advisory = build_issue_fix_repository_context_packet(
        repo="owner/repo",
        issue_ref="issue_123",
        context_input=advisory_only,
    )
    assert advisory["context_status"] == "ungrounded", advisory
    assert advisory["advisory_required_aspects"] == [
        "change_scope",
        "reproduction",
        "validation",
    ], advisory
    assert advisory["expert_consultation"]["next_action"] == (
        "verify_queried_answer_against_repository"
    ), advisory

    stale_policy = {
        "schema_version": "issue_fix_repository_context_input_v0",
        "repository_revision": "public-revision-2",
        "sources": [
            {
                "source_id": "stale-policy",
                "source_kind": "repository_policy",
                "reference": "CONTRIBUTING.md",
                "trust": "authoritative",
                "freshness": "stale",
                "supports": ["change_scope"],
            }
        ],
    }
    stale = build_issue_fix_repository_context_packet(
        repo="owner/repo",
        issue_ref="issue_123",
        context_input=stale_policy,
    )
    assert stale["coverage"]["change_scope"]["status"] == "advisory", stale
    assert "change_scope" in stale["unresolved_required_aspects"], stale

    workflow = build_issue_fix_workflow_plan_packet(
        url=URL,
        repository_context_input=context_input,
        validation_label="focused OpenViking test",
    )
    assert workflow["ok"] is True, workflow
    assert workflow["repository_context"]["context_status"] == "grounded", workflow
    assert "use the grounded repository context" in workflow["first_screen"][
        "next_safe_action"
    ], workflow
    actions = [
        row["action_kind"] for row in workflow["ordered_loopx_todo_writeback_preview"]
    ]
    assert actions == [
        "issue_fix_public_metadata_classification",
        "issue_fix_feasibility_decision",
    ], actions
    legacy_workflow = json.loads(json.dumps(workflow))
    legacy_workflow.pop("repository_context")
    assert validate_issue_fix_workflow_plan_packet(legacy_workflow)["ok"] is True

    feasibility = build_issue_fix_feasibility_packet(
        url=URL,
        reproduction_status="planned",
        reproduction_label="focused OpenViking repro plan",
        scope_class="bounded",
        validation_label="focused OpenViking test",
        repository_context_input=context_input,
    )
    assert feasibility["decision"]["route"] == "fix_pr", feasibility
    assert "repository_context_grounded" in feasibility["decision"]["reason_codes"]
    effect = feasibility["repository_context_effect"]
    assert effect["route_confidence"] == "grounded", effect
    assert effect["route_overridden"] is False, effect
    assert "openviking-vikingbot-readme" in effect["reproduction_evidence_refs"]
    assert "openviking-pr-agent-rules" in effect["validation_evidence_refs"]
    assert_public_safe(feasibility)
    legacy_feasibility = json.loads(json.dumps(feasibility))
    legacy_feasibility["observation"].pop("repository_context")
    legacy_feasibility.pop("repository_context_effect")
    assert validate_issue_fix_feasibility_packet(legacy_feasibility)["ok"] is True

    invalid = dict(context_input)
    invalid["sources"] = [dict(context_input["sources"][0], content="raw content")]
    try:
        build_issue_fix_repository_context_packet(
            repo="owner/repo",
            issue_ref="issue_123",
            context_input=invalid,
        )
    except ValueError as exc:
        assert "unsupported fields" in str(exc), exc
    else:
        raise AssertionError("raw source content field must be rejected")

    invalid_path = dict(context_input)
    invalid_path["sources"] = [
        dict(context_input["sources"][0], reference="/private/repository/context.md")
    ]
    try:
        build_issue_fix_repository_context_packet(
            repo="owner/repo",
            issue_ref="issue_123",
            context_input=invalid_path,
        )
    except ValueError as exc:
        assert "absolute" in str(exc), exc
    else:
        raise AssertionError("absolute source reference must be rejected")

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-context-") as tmpdir:
        project = Path(tmpdir)
        command = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "issue-fix",
            "feasibility",
            "--url",
            URL,
            "--reproduction-status",
            "planned",
            "--reproduction-label",
            "focused OpenViking repro plan",
            "--scope-class",
            "bounded",
            "--validation-label",
            "focused OpenViking test",
            "--repository-context-json",
            str(FIXTURE),
            "--goal-id",
            "openviking-pilot",
            "--project",
            str(project),
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        cli_packet = json.loads(result.stdout)
        assert cli_packet["domain_state_projection"]["write_performed"] is True
        ledger = (
            project
            / ".loopx"
            / "domain-state"
            / "openviking-pilot"
            / "issue_fix"
            / "feasibility.jsonl"
        )
        row = json.loads(ledger.read_text(encoding="utf-8").strip())
        persisted_context = row["observation"]["repository_context"]
        assert persisted_context["context_status"] == "grounded", row
        assert persisted_context["context_fingerprint"] == cli_packet["observation"][
            "repository_context"
        ]["context_fingerprint"]
        assert_public_safe(row)

    print("issue-fix-repository-context-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
