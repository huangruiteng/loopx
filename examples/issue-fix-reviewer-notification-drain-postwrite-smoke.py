#!/usr/bin/env python3
"""Ensure grouped drain writeback and semantic dedupe are restart safe."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.pr_lifecycle import (  # noqa: E402
    build_issue_fix_pr_lifecycle_monitor_packet,
)
from loopx.capabilities.issue_fix.reviewer_notification import (  # noqa: E402
    reviewer_notification_idempotency_key,
)
from loopx.domain_packs.issue_fix import (  # noqa: E402
    persist_issue_fix_reviewer_notification_state,
    upsert_issue_fix_pr_lifecycle_ledger_jsonl,
)
from examples.issue_fix_reviewer_notification_test_support import (  # noqa: E402
    drain_issue_fix_reviewer_notification_queue,
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
            "bot_display_name": "Fixture Review Bot",
            "destination_id": "oc_fixture_destination",
            "reviewer_identities": {
                "@map-owner": {
                    "member_id": "ou_fixture_member",
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

        semantic_ledger = path / "semantic-pr-lifecycle.jsonl"
        semantic_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/106",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(semantic_ledger, semantic_row)
        semantic_key = reviewer_notification_idempotency_key(
            repo="owner/repo",
            pr_number=106,
            sink_kind="lark_chat",
            sink_instance_key=sink["sink_instance_key"],
            reviewer_handles=["@map-owner"],
        )
        persist_issue_fix_reviewer_notification_state(
            semantic_ledger,
            semantic_row,
            receipts=[],
            queued_receipts=[
                {
                    "schema_version": (
                        "issue_fix_reviewer_notification_queue_receipt_v1"
                    ),
                    "idempotency_key": semantic_key,
                    "sink_kind": "lark_chat",
                    "reviewer_handles": ["@map-owner"],
                    "message_summary": "修复已有群消息被重复发送的问题",
                    "summary_policy_status": "reward_memory_verified",
                    "queued_at": "2026-07-17T18:00:00Z",
                    "not_before": "2026-07-18T01:00:00Z",
                    "timezone": "Asia/Shanghai",
                    "allowed_local_time": {"start": "09:00", "end": "21:00"},
                    "status": "queued",
                }
            ],
        )

        def semantic_metadata_loader(
            *, repo: str, number: int, runner: Any = None
        ) -> tuple[dict[str, Any], None]:
            assert repo == "owner/repo" and number in {106, 109}
            return {
                "author_handle": "@author-f",
                "reviewed_by": [],
                "requested_reviewers": ["@map-owner"],
                "comment_notified_reviewers": [],
                "state": "OPEN",
                "review_decision": "REVIEW_REQUIRED",
                "state_bucket": "review_required",
                "is_draft": False,
                "linked_issue_refs": ["#96"],
            }, None

        def no_lark_write(_args: list[str]) -> dict[str, Any]:
            raise AssertionError("semantic inbox dedupe must prevent a Lark write")

        semantic_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=semantic_ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
            runner=no_lark_write,
            metadata_loader=semantic_metadata_loader,
            semantic_history_matcher=lambda permalink, sink: permalink.endswith(
                "/pull/106"
            ),
        )
        assert semantic_drain["ok"] is True, semantic_drain
        assert semantic_drain["external_writes_performed"] is False
        assert semantic_drain["items"][0]["semantic_history_status"] == "matched"
        semantic_stored = json.loads(
            semantic_ledger.read_text(encoding="utf-8").splitlines()[0]
        )
        assert semantic_stored["reviewer_notification_queue"] == []
        assert semantic_key in semantic_stored["reviewer_notification_receipts"]

        scoped_ledger = path / "scoped-semantic-pr-lifecycle.jsonl"
        scoped_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/109",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(scoped_ledger, scoped_row)
        second_sink = {**sink, "sink_instance_key": "fixture-review-lane-b"}
        scoped_queue = [
            {
                "schema_version": "issue_fix_reviewer_notification_queue_receipt_v1",
                "idempotency_key": reviewer_notification_idempotency_key(
                    repo="owner/repo",
                    pr_number=109,
                    sink_kind="lark_chat",
                    sink_instance_key=current_sink["sink_instance_key"],
                    reviewer_handles=["@map-owner"],
                ),
                "sink_kind": "lark_chat",
                "reviewer_handles": ["@map-owner"],
                "message_summary": "仅对已有消息的群做精确去重",
                "summary_policy_status": "reward_memory_verified",
                "queued_at": "2026-07-17T18:00:00Z",
                "not_before": "2026-07-18T01:00:00Z",
                "timezone": "Asia/Shanghai",
                "allowed_local_time": {"start": "09:00", "end": "21:00"},
                "status": "queued",
            }
            for current_sink in (sink, second_sink)
        ]
        persist_issue_fix_reviewer_notification_state(
            scoped_ledger,
            scoped_row,
            receipts=[],
            queued_receipts=scoped_queue,
        )
        scoped_writes: list[str] = []

        def scoped_adapter(**kwargs: Any) -> dict[str, Any]:
            instance_key = str(kwargs["sink"]["sink_instance_key"]).strip()
            key = reviewer_notification_idempotency_key(
                repo="owner/repo",
                pr_number=int(kwargs["pr_number"]),
                sink_kind="lark_chat",
                sink_instance_key=instance_key,
                reviewer_handles=["@map-owner"],
            )
            already_notified = key in kwargs["receipts"]
            if not already_notified:
                scoped_writes.append(instance_key)
            return {
                **unverified_adapter(**kwargs),
                "ok": True,
                "status": (
                    "already_notified" if already_notified else "sent_verified"
                ),
                "idempotency_key": key,
                "external_write_performed": not already_notified,
                "notification_verified": True,
            }

        scoped_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=scoped_ledger,
            sinks_input={**sinks_input, "sinks": [sink, second_sink]},
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
            metadata_loader=semantic_metadata_loader,
            semantic_history_matcher=lambda permalink, current_sink: (
                str(current_sink["sink_instance_key"]).strip()
                == "fixture-review-lane"
            ),
            sink_adapters={"lark_chat": scoped_adapter},
        )
        assert scoped_drain["status"] == "drained_verified", scoped_drain
        assert scoped_writes == ["fixture-review-lane-b"], scoped_writes
        scoped_stored = json.loads(
            scoped_ledger.read_text(encoding="utf-8").splitlines()[0]
        )
        assert scoped_stored["reviewer_notification_queue"] == []
        assert len(scoped_stored["reviewer_notification_receipts"]) == 2

        mixed_ledger = path / "mixed-reviewers-pr-lifecycle.jsonl"
        mixed_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/107",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(mixed_ledger, mixed_row)
        mixed_receipt = {
            "schema_version": "issue_fix_reviewer_notification_queue_receipt_v1",
            "idempotency_key": reviewer_notification_idempotency_key(
                repo="owner/repo",
                pr_number=107,
                sink_kind="lark_chat",
                sink_instance_key=sink["sink_instance_key"],
                reviewer_handles=["@map-owner", "@removed-owner"],
            ),
            "sink_kind": "lark_chat",
            "reviewer_handles": ["@map-owner", "@removed-owner"],
            "message_summary": "取消已评审或已移除 reviewer 的过期提醒",
            "summary_policy_status": "reward_memory_verified",
            "queued_at": "2026-07-17T18:00:00Z",
            "not_before": "2026-07-18T01:00:00Z",
            "timezone": "Asia/Shanghai",
            "allowed_local_time": {"start": "09:00", "end": "21:00"},
            "status": "queued",
        }
        persist_issue_fix_reviewer_notification_state(
            mixed_ledger,
            mixed_row,
            receipts=[],
            queued_receipts=[mixed_receipt],
        )

        def mixed_metadata_loader(
            *, repo: str, number: int
        ) -> tuple[dict[str, Any], None]:
            assert (repo, number) == ("owner/repo", 107)
            return {
                "author_handle": "@author-g",
                "reviewed_by": ["@map-owner"],
                "requested_reviewers": [],
                "comment_notified_reviewers": ["@map-owner"],
                "state": "OPEN",
                "review_decision": "REVIEW_REQUIRED",
                "state_bucket": "review_required",
                "is_draft": False,
                "linked_issue_refs": [],
            }, None

        mixed_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=mixed_ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
            metadata_loader=mixed_metadata_loader,
        )
        assert mixed_drain["status"] == "cancelled_stale", mixed_drain
        assert mixed_drain["items"][0]["cancellation_reason"] == (
            "all_queued_reviewers_already_covered_or_inactive"
        )

        failed_ledger = path / "failed-send-pr-lifecycle.jsonl"
        failed_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/112",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(failed_ledger, failed_row)
        failed_key = reviewer_notification_idempotency_key(
            repo="owner/repo",
            pr_number=112,
            sink_kind="lark_chat",
            sink_instance_key=sink["sink_instance_key"],
            reviewer_handles=["@map-owner"],
        )
        failed_receipt = {
            **mixed_receipt,
            "idempotency_key": failed_key,
            "reviewer_handles": ["@map-owner"],
        }
        persist_issue_fix_reviewer_notification_state(
            failed_ledger,
            failed_row,
            receipts=[],
            queued_receipts=[failed_receipt],
        )

        def failed_metadata_loader(
            *, repo: str, number: int
        ) -> tuple[dict[str, Any], None]:
            assert (repo, number) == ("owner/repo", 112)
            return {
                "author_handle": "@author-i",
                "reviewed_by": [],
                "requested_reviewers": ["@map-owner"],
                "comment_notified_reviewers": [],
                "state": "OPEN",
                "review_decision": "REVIEW_REQUIRED",
                "state_bucket": "review_required",
                "is_draft": False,
                "linked_issue_refs": [],
            }, None

        due_preview = drain_issue_fix_reviewer_notification_queue(
            ledger_path=failed_ledger,
            sinks_input=sinks_input,
            execute=False,
            delivery_observed_at="2026-07-18T01:01:00Z",
        )
        assert due_preview["status"] == "preview_due", due_preview
        assert due_preview["remaining_due_pr_count"] == 0
        assert due_preview["has_more_due"] is False
        failed_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=failed_ledger,
            sinks_input={
                **sinks_input,
                "sinks": [{**sink, "destination_id": "invalid destination"}],
            },
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
            metadata_loader=failed_metadata_loader,
        )
        assert failed_drain["status"] == "blocked", failed_drain
        assert failed_drain["external_writes_performed"] is False
        failed_stored = json.loads(
            failed_ledger.read_text(encoding="utf-8").splitlines()[0]
        )
        assert failed_stored["reviewer_notification_queue"] == [failed_receipt]

        with patch(
            "loopx.capabilities.issue_fix.reviewer_notification_drain."
            "persist_issue_fix_reviewer_notification_state",
            side_effect=OSError("fixture writeback failure"),
        ):
            failed_writeback = drain_issue_fix_reviewer_notification_queue(
                ledger_path=failed_ledger,
                sinks_input=sinks_input,
                execute=True,
                delivery_observed_at="2026-07-18T01:01:00Z",
                metadata_loader=failed_metadata_loader,
                sink_adapters={"lark_chat": scoped_adapter},
            )
        assert failed_writeback["status"] == "blocked", failed_writeback
        assert failed_writeback["external_writes_performed"] is True
        assert failed_writeback["items"][0]["external_write_performed"] is True
        assert failed_writeback["remaining_due_pr_count"] == 1
        assert failed_writeback["has_more_due"] is True

        malformed_row = json.loads(
            failed_ledger.read_text(encoding="utf-8").splitlines()[0]
        )
        malformed_row["reviewer_notification_queue"][0]["not_before"] = (
            "not-a-timestamp"
        )
        healthy_ledger = path / "healthy-due-pr-lifecycle.jsonl"
        healthy_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/114",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        persist_issue_fix_reviewer_notification_state(
            healthy_ledger,
            healthy_row,
            receipts=[],
            queued_receipts=[
                {
                    **failed_receipt,
                    "idempotency_key": reviewer_notification_idempotency_key(
                        repo="owner/repo",
                        pr_number=114,
                        sink_kind="lark_chat",
                        sink_instance_key=sink["sink_instance_key"],
                        reviewer_handles=["@map-owner"],
                    ),
                }
            ],
        )
        failed_ledger.write_text(
            json.dumps(malformed_row, sort_keys=True)
            + "\n"
            + healthy_ledger.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        malformed_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=failed_ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
        )
        assert malformed_drain["status"] == "blocked", malformed_drain
        assert malformed_drain["blocker"] == (
            "reviewer_notification_queue_not_before_invalid"
        )
        assert malformed_drain["invalid_queue_receipt_count"] == 1
        assert malformed_drain["due_pr_count"] == 1
        assert malformed_drain["remaining_due_pr_count"] == 2
        assert malformed_drain["has_more_due"] is True
        assert malformed_drain["external_reads_performed"] is False
        assert malformed_drain["external_writes_performed"] is False

        correction_ledger = path / "maintainer-correction-pr-lifecycle.jsonl"
        correction_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/113",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
            maintainer_correction_input={
                "schema_version": "issue_fix_maintainer_correction_input_v0",
                "correction_kind": "semantic_ambiguity",
                "source_kind": "maintainer_comment",
                "source_ref": "https://github.com/owner/repo/pull/113#issuecomment-1",
                "summary": "需要确认队列失败后是立即重试还是等待下一窗口。",
                "user_question": "失败发送应立即重试，还是保持到下一发送窗口？",
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(
            correction_ledger, correction_row
        )
        correction_receipt = {
            **mixed_receipt,
            "idempotency_key": reviewer_notification_idempotency_key(
                repo="owner/repo",
                pr_number=113,
                sink_kind="lark_chat",
                sink_instance_key=sink["sink_instance_key"],
                reviewer_handles=["@map-owner"],
            ),
            "reviewer_handles": ["@map-owner"],
        }
        persist_issue_fix_reviewer_notification_state(
            correction_ledger,
            correction_row,
            receipts=[],
            queued_receipts=[correction_receipt],
        )
        fresh_lifecycle = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/113",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )

        def correction_metadata_loader(
            *, repo: str, number: int
        ) -> tuple[dict[str, Any], None]:
            assert (repo, number) == ("owner/repo", 113)
            return {
                "author_handle": "@author-j",
                "reviewed_by": [],
                "requested_reviewers": ["@map-owner"],
                "comment_notified_reviewers": [],
                "state": "OPEN",
                "review_decision": "REVIEW_REQUIRED",
                "state_bucket": "review_required",
                "is_draft": False,
                "linked_issue_refs": [],
                "_lifecycle_packet": fresh_lifecycle,
            }, None

        correction_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=correction_ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
            metadata_loader=correction_metadata_loader,
            sink_adapters={"lark_chat": scoped_adapter},
        )
        assert correction_drain["status"] == "drained_verified", correction_drain
        correction_stored = json.loads(
            correction_ledger.read_text(encoding="utf-8").splitlines()[0]
        )
        assert correction_stored["transition"]["action_kind"] == (
            "clarify_issue_fix_maintainer_correction"
        )
        assert correction_stored["grouped_monitor_projection"] == (
            correction_row["grouped_monitor_projection"]
        )
        assert correction_stored["first_screen"] == correction_row["first_screen"]

        preview_ledger = path / "preview-blocked-pr-lifecycle.jsonl"
        preview_row = build_issue_fix_pr_lifecycle_monitor_packet(
            url="https://github.com/owner/repo/pull/108",
            provider_payload={
                "state": "OPEN",
                "reviewDecision": "REVIEW_REQUIRED",
                "mergeStateStatus": "BLOCKED",
                "statusCheckRollup": [],
            },
        )
        upsert_issue_fix_pr_lifecycle_ledger_jsonl(preview_ledger, preview_row)
        preview_key = reviewer_notification_idempotency_key(
            repo="owner/repo",
            pr_number=108,
            sink_kind="lark_chat",
            sink_instance_key=sink["sink_instance_key"],
            reviewer_handles=["@map-owner"],
        )
        persist_issue_fix_reviewer_notification_state(
            preview_ledger,
            preview_row,
            receipts=[],
            queued_receipts=[
                {
                    **mixed_receipt,
                    "idempotency_key": preview_key,
                    "reviewer_handles": ["@map-owner"],
                    "allowed_local_time": {"start": "09:00", "end": "09:00"},
                }
            ],
        )
        preview = drain_issue_fix_reviewer_notification_queue(
            ledger_path=preview_ledger,
            sinks_input=sinks_input,
            execute=False,
            delivery_observed_at="2026-07-18T01:01:00Z",
        )
        assert preview["status"] == "preview_blocked", preview
        assert preview["blocked_pr_count"] == 1, preview
        assert preview["remaining_due_pr_count"] == 1, preview
        assert preview["has_more_due"] is True, preview
        assert reviewer_notification_idempotency_key(
            repo="owner/repo",
            pr_number=108,
            sink_kind=" lark_chat ",
            sink_instance_key=" fixture-review-lane ",
            reviewer_handles=["@map-owner"],
        ) == reviewer_notification_idempotency_key(
            repo="owner/repo",
            pr_number=108,
            sink_kind="lark_chat",
            sink_instance_key="fixture-review-lane",
            reviewer_handles=["@map-owner"],
        )

        limit_ledger = path / "limit-pr-lifecycle.jsonl"
        for number in (110, 111):
            limit_row = build_issue_fix_pr_lifecycle_monitor_packet(
                url=f"https://github.com/owner/repo/pull/{number}",
                provider_payload={
                    "state": "OPEN",
                    "reviewDecision": "REVIEW_REQUIRED",
                    "mergeStateStatus": "BLOCKED",
                    "statusCheckRollup": [],
                },
            )
            upsert_issue_fix_pr_lifecycle_ledger_jsonl(limit_ledger, limit_row)
            persist_issue_fix_reviewer_notification_state(
                limit_ledger,
                limit_row,
                receipts=[],
                queued_receipts=[
                    {
                        **mixed_receipt,
                        "idempotency_key": reviewer_notification_idempotency_key(
                            repo="owner/repo",
                            pr_number=number,
                            sink_kind="lark_chat",
                            sink_instance_key=sink["sink_instance_key"],
                            reviewer_handles=["@map-owner"],
                        ),
                        "reviewer_handles": ["@map-owner"],
                    }
                ],
            )

        def limit_metadata_loader(
            *, repo: str, number: int
        ) -> tuple[dict[str, Any], None]:
            assert repo == "owner/repo" and number in {110, 111}
            return {
                "author_handle": "@author-h",
                "reviewed_by": [],
                "requested_reviewers": ["@map-owner"],
                "comment_notified_reviewers": [],
                "state": "OPEN",
                "review_decision": "REVIEW_REQUIRED",
                "state_bucket": "review_required",
                "is_draft": False,
                "linked_issue_refs": [],
            }, None

        limit_drain = drain_issue_fix_reviewer_notification_queue(
            ledger_path=limit_ledger,
            sinks_input=sinks_input,
            execute=True,
            delivery_observed_at="2026-07-18T01:01:00Z",
            limit=1,
            metadata_loader=limit_metadata_loader,
            sink_adapters={"lark_chat": scoped_adapter},
        )
        assert limit_drain["status"] == "partial_drain", limit_drain
        assert limit_drain["remaining_due_pr_count"] == 1, limit_drain
        assert limit_drain["has_more_due"] is True, limit_drain

    print("issue-fix-reviewer-notification-drain-postwrite-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
