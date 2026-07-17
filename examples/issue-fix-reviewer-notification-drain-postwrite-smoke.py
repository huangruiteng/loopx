#!/usr/bin/env python3
"""Ensure an unverified external write is never retried automatically."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.capabilities.issue_fix.reviewer_notification import (  # noqa: E402
    reviewer_notification_idempotency_key,
)
from loopx.capabilities.issue_fix.reviewer_notification_drain import (  # noqa: E402
    drain_issue_fix_reviewer_notification_queue,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    persist_issue_fix_reviewer_notification_state,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-reviewer-postwrite-") as raw_path:
        path = Path(raw_path)
        ledger = path / ".loopx/domain-state/drain/pr-lifecycle.jsonl"
        sink = {
            "sink_kind": "lark_chat",
            "sink_instance_key": "fixture-review-lane",
            "identity_scope": "project_dedicated",
            "reader_profile": "fixture-reader-profile",
            "reader_identity": "user",
            "sender_profile": "fixture-sender-profile",
            "sender_identity": "bot",
            "destination_id": "fixture-destination",
            "reviewer_identities": {
                "@map-owner": {
                    "member_id": "fixture-member",
                    "display_name": "Map Owner",
                }
            },
        }
        sinks_input = {
            "schema_version": "issue_fix_reviewer_notification_sinks_input_v0",
            "receipts": [],
            "sinks": [sink],
        }
        row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/105",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(ledger, row)
        key = reviewer_notification_idempotency_key(
            repo="owner/repo",
            pr_number=105,
            sink_kind="lark_chat",
            sink_instance_key=sink["sink_instance_key"],
            reviewer_handles=["@map-owner"],
        )
        persist_issue_fix_reviewer_notification_state(
            ledger,
            row,
            receipts=[],
            queued_receipts=[
                {
                    "schema_version": (
                        "issue_fix_reviewer_notification_queue_receipt_v1"
                    ),
                    "idempotency_key": key,
                    "sink_kind": "lark_chat",
                    "reviewer_handles": ["@map-owner"],
                    "message_summary": "修复发送后验证失败造成重复提醒的问题",
                    "summary_policy_status": "sink_config",
                    "queued_at": "2026-07-20T00:00:00Z",
                    "not_before": "2026-07-20T01:00:00Z",
                    "timezone": "Asia/Shanghai",
                    "allowed_local_time": {"start": "09:00", "end": "21:00"},
                    "status": "queued",
                }
            ],
        )

        def metadata_loader(
            *, repo: str, number: int
        ) -> tuple[dict[str, Any], None]:
            assert (repo, number) == ("owner/repo", 105)
            return {
                "author_handle": "@author-e",
                "reviewed_by": [],
                "requested_reviewers": ["@map-owner"],
                "comment_notified_reviewers": [],
                "state": "OPEN",
                "review_decision": "REVIEW_REQUIRED",
                "state_bucket": "review_required",
                "is_draft": False,
                "linked_issue_refs": ["#95"],
            }, None

        def unverified_adapter(**kwargs: Any) -> dict[str, Any]:
            return {
                "ok": False,
                "schema_version": "issue_fix_reviewer_notification_sink_result_v0",
                "sink_kind": "lark_chat",
                "status": "sent_unverified",
                "reviewer_handles": list(kwargs["reviewer_handles"]),
                "resolved_reviewer_count": len(kwargs["reviewer_handles"]),
                "idempotency_key": key,
                "identity_scope": "project_dedicated",
                "external_write_authority_asserted": True,
                "external_write_performed": True,
                "verification_performed": True,
                "notification_verified": False,
                "bot_identity_verified": True,
                "reader_identity_verified": True,
                "private_destination_captured": False,
                "private_member_ids_captured": False,
                "private_bot_profile_captured": False,
                "raw_provider_payload_captured": False,
                "blocker": "lark_notification_not_verified",
            }

        first = drain_issue_fix_reviewer_notification_queue(
            ledger_path=ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-20T01:01:00Z",
            metadata_loader=metadata_loader,
            sink_adapters={"lark_chat": unverified_adapter},
        )
        assert first["status"] == "blocked", first
        assert first["external_writes_performed"] is True
        second = drain_issue_fix_reviewer_notification_queue(
            ledger_path=ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-20T01:02:00Z",
            metadata_loader=metadata_loader,
            sink_adapters={"lark_chat": unverified_adapter},
        )
        assert second["status"] == "no_due_notifications", second

    print("issue-fix-reviewer-notification-drain-postwrite-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
