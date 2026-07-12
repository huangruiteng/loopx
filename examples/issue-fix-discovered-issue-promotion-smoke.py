#!/usr/bin/env python3
"""Smoke-test generic promotion of an agent-discovered defect to a public issue."""

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

from loopx.capabilities.issue_fix.discovered_issue_promotion import (  # noqa: E402
    ISSUE_FIX_DISCOVERED_ISSUE_PROMOTION_SCHEMA_VERSION,
    build_issue_fix_discovered_issue_promotion_packet,
)
from loopx.capabilities.issue_fix.feasibility import (  # noqa: E402
    build_issue_fix_feasibility_packet,
)
from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    upsert_issue_fix_feasibility_ledger_jsonl,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)


PRIVATE_PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/private/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def assert_public_safe(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in PRIVATE_PATTERNS:
        assert not pattern.search(text), pattern.pattern
    for forbidden in (
        "raw original PR body",
        "provider response payload",
        "private reproduction log",
    ):
        assert forbidden not in text


def context_input() -> dict[str, Any]:
    return {
        "schema_version": "issue_fix_repository_context_input_v0",
        "repository_revision": "a" * 40,
        "sources": [
            {
                "source_id": "policy",
                "source_kind": "repository_policy",
                "reference": "CONTRIBUTING.md",
                "trust": "authoritative",
                "freshness": "current",
                "supports": ["change_scope"],
                "summary": "Focused public fixes require a regression test.",
            },
            {
                "source_id": "repro",
                "source_kind": "source_code",
                "reference": "src/parser.py",
                "trust": "verified",
                "freshness": "current",
                "supports": ["reproduction"],
                "summary": "The current parser sends vector input to the wrong branch.",
            },
            {
                "source_id": "validation",
                "source_kind": "test_surface",
                "reference": "tests/test_parser.py",
                "trust": "verified",
                "freshness": "current",
                "supports": ["validation"],
                "summary": "The focused parser test covers the failing branch.",
            },
        ],
    }


def promotion_input(
    *, decision: str = "reuse_existing", include_pr: bool = True
) -> dict[str, Any]:
    canonical = (
        "https://github.com/example/public-repo/issues/42"
        if decision == "reuse_existing"
        else None
    )
    candidates = [canonical] if canonical else []
    return {
        "schema_version": "issue_fix_discovered_issue_promotion_input_v0",
        "repo": "example/public-repo",
        "source_issue_ref": "discovered-vector-input",
        "title": "Vector input reaches the raster-only parser",
        "problem_summary": "A public vector resource is routed to a raster-only parser and fails.",
        "reproduction_summary": "Run the focused parser fixture with a vector resource.",
        "expected_behavior": "Vector resources should use the text-capable parser path.",
        "validation_summary": "The focused parser regression should pass without provider errors.",
        "repository_revision": "a" * 40,
        "evidence_refs": ["src/parser.py", "tests/test_parser.py"],
        "duplicate_search": {
            "schema_version": "issue_fix_duplicate_search_evidence_v0",
            "searched_states": ["open", "closed"],
            "query_summary": "vector resource raster parser provider error",
            "candidate_issue_urls": candidates,
            "decision": decision,
            "canonical_issue_url": canonical,
        },
        "pr_url": (
            "https://github.com/example/public-repo/pull/99" if include_pr else None
        ),
    }


class FakeGitHub:
    def __init__(self, *, fail_edit: bool = False) -> None:
        self.linked = False
        self.write_count = 0
        self.last_pr_body = ""
        self.fail_edit = fail_edit

    def __call__(self, args: list[str]) -> dict[str, Any]:
        if args[1:3] == ["issue", "view"]:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "number": 42,
                        "state": "OPEN",
                        "title": "Vector input reaches the raster-only parser",
                        "url": "https://github.com/example/public-repo/issues/42",
                    }
                ),
                "stderr": "provider response payload",
            }
        if args[1:3] == ["pr", "view"]:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "body": (
                            self.last_pr_body or "Motivation\n\nraw original PR body"
                        ),
                        "closingIssuesReferences": (
                            [{"number": 42}] if self.linked else []
                        ),
                        "url": "https://github.com/example/public-repo/pull/99",
                    }
                ),
                "stderr": "",
            }
        if args[1:3] == ["pr", "edit"]:
            if self.fail_edit:
                return {"returncode": 1, "stdout": "", "stderr": "permission denied"}
            self.write_count += 1
            self.linked = True
            self.last_pr_body = args[args.index("--body") + 1]
            assert self.last_pr_body.endswith("Fixes #42")
            return {"returncode": 0, "stdout": "", "stderr": ""}
        raise AssertionError(args)


class FakeGitHubCreate:
    def __init__(self) -> None:
        self.created_body = ""

    def __call__(self, args: list[str]) -> dict[str, Any]:
        if args[1:3] == ["issue", "create"]:
            self.created_body = args[args.index("--body") + 1]
            return {
                "returncode": 0,
                "stdout": "https://github.com/example/public-repo/issues/43\n",
                "stderr": "",
            }
        if args[1:3] == ["issue", "view"]:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "number": 43,
                        "state": "OPEN",
                        "title": "Vector input reaches the raster-only parser",
                        "url": "https://github.com/example/public-repo/issues/43",
                    }
                ),
                "stderr": "",
            }
        raise AssertionError(args)


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    preview = build_issue_fix_discovered_issue_promotion_packet(
        promotion_input=promotion_input(decision="no_equivalent_found"),
        execute=False,
    )
    assert preview["ok"] is True
    assert preview["dry_run"] is True
    assert preview["planned_action"] == "create_public_issue"
    assert preview["external_reads_performed"] is False
    assert preview["external_writes_performed"] is False
    assert_public_safe(preview)

    with tempfile.TemporaryDirectory(prefix="loopx-discovered-promotion-") as tmp:
        root = Path(tmp)
        feasibility_path = root / "feasibility.jsonl"
        lifecycle_path = root / "pr-lifecycle.jsonl"
        promotion_path = root / "promotion.json"
        promotion_path.write_text(
            json.dumps(promotion_input(), sort_keys=True), encoding="utf-8"
        )
        cli_preview = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "issue-fix",
                "promote-discovered-issue",
                "--promotion-json",
                str(promotion_path),
                "--goal-id",
                "fixture-goal",
                "--project",
                str(root),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        cli_payload = json.loads(cli_preview.stdout)
        assert cli_payload["schema_version"] == (
            ISSUE_FIX_DISCOVERED_ISSUE_PROMOTION_SCHEMA_VERSION
        )
        assert cli_payload["dry_run"] is True
        assert_public_safe(cli_payload)
        source = build_issue_fix_feasibility_packet(
            repo="example/public-repo",
            issue_ref="discovered-vector-input",
            reproduction_status="confirmed",
            scope_class="bounded",
            reproduction_label="focused vector parser fixture fails",
            validation_label="focused parser regression",
            repository_context_input=context_input(),
            boundary_authority_scopes=["publish"],
            boundary_authority_resolved=True,
        )
        upsert_issue_fix_feasibility_ledger_jsonl(feasibility_path, source)
        lifecycle = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/example/public-repo/pull/99",
            issue_ref="discovered-vector-input",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "CLEAN",
                "statusCheckRollup": [{"name": "tests", "conclusion": "SUCCESS"}],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(lifecycle_path, lifecycle)

        github = FakeGitHub()
        promoted = build_issue_fix_discovered_issue_promotion_packet(
            promotion_input=promotion_input(),
            boundary_authority_scopes=["write", "publish"],
            boundary_authority_resolved=True,
            execute=True,
            feasibility_ledger_path=feasibility_path,
            pr_lifecycle_ledger_path=lifecycle_path,
            runner=github,
            generated_at="2026-07-12T00:00:00Z",
        )
        assert (
            promoted["schema_version"]
            == ISSUE_FIX_DISCOVERED_ISSUE_PROMOTION_SCHEMA_VERSION
        )
        assert promoted["issue"]["reused"] is True
        assert promoted["issue"]["created"] is False
        assert promoted["pr_closing_reference"]["verified"] is True
        assert promoted["pr_closing_reference"]["write_performed"] is True
        assert promoted["domain_state_reconciliation"]["duplicate_rows_remaining"] == 0
        assert github.write_count == 1
        feasibility_rows = read_rows(feasibility_path)
        assert len(feasibility_rows) == 1
        observation = feasibility_rows[0]["observation"]
        assert observation["issue_ref"] == "issues_42"
        assert observation["repository_context"]["repository_revision"] == "a" * 40
        assert feasibility_rows[0]["promotion_lineage"]["source_issue_ref"] == (
            "discovered-vector-input"
        )
        lifecycle_rows = read_rows(lifecycle_path)
        assert len(lifecycle_rows) == 1
        assert lifecycle_rows[0]["observation"]["issue_ref"] == "issues_42"
        assert_public_safe(promoted)

        retry = build_issue_fix_discovered_issue_promotion_packet(
            promotion_input=promotion_input(),
            boundary_authority_scopes=["publish"],
            boundary_authority_resolved=True,
            execute=True,
            feasibility_ledger_path=feasibility_path,
            pr_lifecycle_ledger_path=lifecycle_path,
            runner=github,
            generated_at="2026-07-12T00:05:00Z",
        )
        assert retry["external_writes_performed"] is False, retry
        assert retry["pr_closing_reference"]["write_performed"] is False
        assert retry["domain_state_reconciliation"]["write_performed"] is False
        assert len(read_rows(feasibility_path)) == 1
        assert github.write_count == 1
        assert_public_safe(retry)

        read_only = build_issue_fix_discovered_issue_promotion_packet(
            promotion_input=promotion_input(),
            boundary_authority_scopes=["publish"],
            boundary_authority_resolved=True,
            execute=True,
            feasibility_ledger_path=feasibility_path,
            pr_lifecycle_ledger_path=lifecycle_path,
            write_domain_state=False,
            runner=github,
        )
        assert read_only["ok"] is True
        assert read_only["external_writes_performed"] is False
        assert read_only["domain_state_reconciliation"]["write_performed"] is False

        failed_github = FakeGitHub(fail_edit=True)
        blocked_pr = build_issue_fix_discovered_issue_promotion_packet(
            promotion_input=promotion_input(),
            boundary_authority_scopes=["publish"],
            boundary_authority_resolved=True,
            execute=True,
            feasibility_ledger_path=feasibility_path,
            pr_lifecycle_ledger_path=lifecycle_path,
            runner=failed_github,
        )
        assert blocked_pr["ok"] is False
        assert blocked_pr["blocker"]["reason_code"] == (
            "pr_closing_reference_unverified"
        )
        assert blocked_pr["issue"]["url"].endswith("/issues/42")
        assert (
            blocked_pr["domain_state_reconciliation"]["canonical_row_retained"] is True
        )
        assert_public_safe(blocked_pr)

        blocked = False
        try:
            build_issue_fix_discovered_issue_promotion_packet(
                promotion_input=promotion_input(),
                boundary_authority_scopes=["write"],
                boundary_authority_resolved=True,
                execute=True,
                feasibility_ledger_path=feasibility_path,
                pr_lifecycle_ledger_path=lifecycle_path,
                runner=github,
            )
        except ValueError as exc:
            blocked = "publish authority" in str(exc)
        assert blocked

    with tempfile.TemporaryDirectory(prefix="loopx-discovered-create-") as tmp:
        feasibility_path = Path(tmp) / "feasibility.jsonl"
        source = build_issue_fix_feasibility_packet(
            repo="example/public-repo",
            issue_ref="discovered-vector-input",
            reproduction_status="confirmed",
            scope_class="bounded",
            reproduction_label="focused vector parser fixture fails",
            validation_label="focused parser regression",
            repository_context_input=context_input(),
        )
        upsert_issue_fix_feasibility_ledger_jsonl(feasibility_path, source)
        github_create = FakeGitHubCreate()
        created = build_issue_fix_discovered_issue_promotion_packet(
            promotion_input=promotion_input(
                decision="no_equivalent_found", include_pr=False
            ),
            boundary_authority_scopes=["publish"],
            boundary_authority_resolved=True,
            execute=True,
            feasibility_ledger_path=feasibility_path,
            runner=github_create,
        )
        assert created["issue"]["created"] is True
        assert created["external_writes_performed"] is True
        assert "## Problem" in github_create.created_body
        assert "## Reproduction" in github_create.created_body
        assert "Observed at revision" in github_create.created_body
        assert read_rows(feasibility_path)[0]["observation"]["issue_ref"] == "issues_43"
        assert_public_safe(created)

    print("issue-fix-discovered-issue-promotion-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
