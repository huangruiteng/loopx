#!/usr/bin/env python3
"""Smoke-test issue-fix PR lifecycle projection and domain-state writeback."""

from __future__ import annotations

from datetime import datetime, timezone
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

from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    ISSUE_FIX_PR_LIFECYCLE_MONITOR_SCHEMA_VERSION,
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    default_issue_fix_domain_state_ledger_path,
    issue_fix_pr_lifecycle_ledger_key,
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

FORBIDDEN_VALUES = [
    "raw issue body text that must stay gated",
    "full issue comment text that must stay gated",
    "raw provider response payload",
    "private check log",
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


def assert_packet_shape(packet: dict[str, Any]) -> None:
    assert packet["ok"] is True, packet
    assert packet["schema_version"] == ISSUE_FIX_PR_LIFECYCLE_MONITOR_SCHEMA_VERSION
    assert packet["external_writes_performed"] is False
    assert packet["todo_write_performed"] is False
    assert packet["issue_body_captured"] is False
    assert packet["comment_bodies_captured"] is False
    assert packet["response_payloads_captured"] is False
    assert packet["raw_check_logs_captured"] is False
    assert packet["local_paths_captured"] is False
    assert packet["private_repo_state_read"] is False
    assert packet["observation"]["body_captured"] is False
    assert packet["observation"]["comment_bodies_captured"] is False
    assert packet["observation"]["log_output_captured"] is False
    assert packet["transition"]["would_write"] is False
    assert packet["transition"]["requires_execute_flag"] is True
    assert packet["domain_state_projection"]["domain_pack"] == "issue_fix"
    assert packet["domain_state_projection"]["path_recorded"] is False
    assert packet["validation"]["ok"] is True, packet
    assert_public_safe(packet)


def main() -> int:
    merged = build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/huangruiteng/loopx/pull/1715",
        provider_payload={
            "state": "MERGED",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "UNKNOWN",
            "statusCheckRollup": [{"name": "Full Public Smokes", "conclusion": "SUCCESS"}],
            "body": "raw issue body text that must stay gated",
            "comments": ["full issue comment text that must stay gated"],
            "raw": "raw provider response payload",
        },
    )
    assert_packet_shape(merged)
    assert merged["transition"]["decision"] == "no_followup", merged
    assert merged["transition"]["action_kind"] == "issue_fix_pr_merged_no_followup"
    assert merged["transition"]["terminal_state_precedence"] is True
    assert merged["writeback_contract"]["monitor_quiet_skip_allowed"] is False

    failing = build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/huangruiteng/loopx/pull/1715",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": "Full Public Smokes", "conclusion": "FAILURE"}],
            "check_log": "private check log",
        },
    )
    assert_packet_shape(failing)
    assert failing["transition"]["decision"] == "runnable_successor", failing
    assert failing["transition"]["action_kind"] == "issue_fix_ci_failure_replan"
    assert failing["first_screen"]["agent_can_continue"] is True

    requested = build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/huangruiteng/loopx/pull/1715",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "CHANGES_REQUESTED",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": "lint", "conclusion": "SUCCESS"}],
        },
    )
    assert_packet_shape(requested)
    assert requested["transition"]["decision"] == "runnable_successor", requested
    assert requested["transition"]["action_kind"] == "issue_fix_review_changes_replan"

    blocked_pending = build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/huangruiteng/loopx/pull/1715",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "BLOCKED",
            "statusCheckRollup": [{"name": "lint", "status": "IN_PROGRESS"}],
        },
    )
    assert_packet_shape(blocked_pending)
    assert blocked_pending["transition"]["decision"] == "monitor_continuation"
    assert blocked_pending["transition"]["action_kind"] == (
        "issue_fix_pr_checks_pending_monitor"
    )
    assert blocked_pending["transition"]["material_change"] is False

    stale = build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/huangruiteng/loopx/pull/1715",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [{"name": "lint", "conclusion": "SUCCESS"}],
        },
    )
    assert_packet_shape(stale)
    assert stale["transition"]["decision"] == "runnable_successor"
    assert stale["transition"]["action_kind"] == (
        "issue_fix_branch_or_merge_blocker_replan"
    )

    quiet = build_issue_fix_pr_lifecycle_monitor_packet(
        url="https://github.com/huangruiteng/loopx/pull/1715",
        issue_ref="issues_1700",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": "lint", "conclusion": "SUCCESS"}],
        },
    )
    assert_packet_shape(quiet)
    assert quiet["transition"]["decision"] == "monitor_continuation", quiet
    assert quiet["observation"]["issue_ref"] == "issues_1700", quiet
    assert quiet["transition"]["material_change"] is False
    assert quiet["writeback_contract"]["monitor_quiet_skip_allowed"] is True
    repo_ref = build_issue_fix_pr_lifecycle_monitor_packet(
        repo="huangruiteng/loopx",
        pr_ref="pull_1715",
        provider_payload={
            "state": "OPEN",
            "reviewDecision": "REVIEW_REQUIRED",
            "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [{"name": "lint", "conclusion": "SUCCESS"}],
        },
    )
    assert_packet_shape(repo_ref)
    assert repo_ref["observation"]["kind"] == "pull_request", repo_ref
    assert repo_ref["observation"]["pr_ref"] == "pull_1715", repo_ref

    with tempfile.TemporaryDirectory(prefix="loopx-issue-fix-pr-lifecycle-") as tmpdir:
        project = Path(tmpdir)
        ledger = default_issue_fix_domain_state_ledger_path(
            project=project,
            goal_id="example-goal",
        )
        key = issue_fix_pr_lifecycle_ledger_key(quiet)
        assert key == {"repo": "huangruiteng/loopx", "pr_ref": "pull_1715"}
        result = upsert_issue_fix_pr_lifecycle_ledger_jsonl(ledger, quiet)
        assert result["status"] == "inserted", result
        first_inode = ledger.stat().st_ino
        result = upsert_issue_fix_pr_lifecycle_ledger_jsonl(ledger, quiet)
        assert result["status"] == "unchanged", result
        assert result["write_performed"] is False, result
        assert ledger.stat().st_ino == first_inode
        assert quiet["domain_state_projection"]["write_performed"] is False, quiet
        assert quiet["domain_state_projection"]["write_skipped_reason"] == (
            "observation_fingerprint_unchanged"
        ), quiet
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1, rows
        assert rows[0]["domain_state_key"] == key, rows
        assert_public_safe(rows[0])

        metadata_path = project / "pr.json"
        metadata_path.write_text(
            json.dumps(
                {
                    "state": "OPEN",
                    "reviewDecision": "REVIEW_REQUIRED",
                    "mergeStateStatus": "CLEAN",
                    "statusCheckRollup": [{"name": "lint", "conclusion": "SUCCESS"}],
                }
            ),
            encoding="utf-8",
        )
        invoked_after = datetime.now(timezone.utc).replace(microsecond=0)
        cli_result = run_cli(
            [
                "issue-fix",
                "pr-lifecycle",
                "--url",
                "https://github.com/huangruiteng/loopx/pull/1715",
                "--metadata-json",
                str(metadata_path),
                "--issue-ref",
                "issues_1700",
                "--goal-id",
                "example-goal",
                "--project",
                str(project),
            ]
        )
        cli_packet = json.loads(cli_result.stdout)
        completed_before = datetime.now(timezone.utc).replace(microsecond=0)
        assert_packet_shape(cli_packet)
        cli_generated_at = datetime.fromisoformat(
            str(cli_packet["generated_at"]).replace("Z", "+00:00")
        )
        assert invoked_after <= cli_generated_at <= completed_before, cli_packet
        assert cli_packet["generated_at"] != "2026-06-23T00:00:00Z", cli_packet
        assert cli_packet["domain_state_projection"]["write_performed"] is False
        write_result = cli_packet["domain_state_projection"]["write_result"]
        assert write_result["status"] == "unchanged", write_result
        assert write_result["write_performed"] is False, write_result
        assert ledger.stat().st_ino == first_inode
        assert write_result["path_recorded"] is False, write_result
        persisted_rows = [
            json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()
        ]
        assert len(persisted_rows) == 1, persisted_rows
        persisted_projection = persisted_rows[0]["domain_state_projection"]
        assert persisted_projection["write_performed"] is True, persisted_rows[0]
        assert "write_result" not in persisted_projection, persisted_rows[0]
        assert_public_safe(cli_packet)

        explicit_time = "2026-06-23T00:00:00Z"
        explicit_result = run_cli(
            [
                "issue-fix",
                "pr-lifecycle",
                "--url",
                "https://github.com/huangruiteng/loopx/pull/1715",
                "--metadata-json",
                str(metadata_path),
                "--generated-at",
                explicit_time,
                "--no-write-domain-state",
            ]
        )
        explicit_packet = json.loads(explicit_result.stdout)
        assert explicit_packet["generated_at"] == explicit_time, explicit_packet

        material_result = upsert_issue_fix_pr_lifecycle_ledger_jsonl(ledger, failing)
        assert material_result["status"] == "updated", material_result
        assert material_result["write_performed"] is True, material_result
        assert failing["domain_state_projection"]["write_performed"] is True, failing
        assert ledger.stat().st_ino != first_inode

    print("issue-fix-pr-lifecycle-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
