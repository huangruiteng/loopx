#!/usr/bin/env python3
"""Smoke-test provider-neutral reviewer notification sinks."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.issue_fix.reviewer_notification import (  # noqa: E402
    ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION,
    ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_RESULT_SCHEMA_VERSION,
    build_issue_fix_reviewer_notification_sinks_result,
    with_reviewer_notification_state,
)


PRIVATE_PATTERNS = (
    re.compile(r"oc_[A-Za-z0-9_-]+"),
    re.compile(r"ou_[A-Za-z0-9_-]+"),
    re.compile(r"cli-private-profile"),
    re.compile(r"fixture-reader-profile"),
    re.compile(r"fixture-sender-profile"),
)


class FakeSinkRunner:
    def __init__(
        self,
        *,
        send_returncode: int = 0,
        verify_returncode: int = 0,
        include_message_content: bool = True,
        bot_name: str = "Project Review Bot",
        reader_verified: bool = True,
        include_member: bool = True,
        member_id: str = "ou_private_member",
        search_returncode: int = 0,
        search_hit: bool = False,
    ) -> None:
        self.send_returncode = send_returncode
        self.verify_returncode = verify_returncode
        self.include_message_content = include_message_content
        self.bot_name = bot_name
        self.reader_verified = reader_verified
        self.include_member = include_member
        self.member_id = member_id
        self.search_returncode = search_returncode
        self.search_hit = search_hit
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> dict[str, Any]:
        command = list(args)
        self.calls.append(command)
        if command[-4:] == ["auth", "status", "--verify", "--json"]:
            profile = command[2]
            if profile == "fixture-reader-profile":
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "identities": {
                                "user": {
                                    "available": self.reader_verified,
                                    "verified": self.reader_verified,
                                }
                            }
                        }
                    ),
                    "stderr": "",
                }
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "identities": {
                            "bot": {
                                "available": True,
                                "verified": True,
                                "appName": self.bot_name,
                            }
                        }
                    }
                ),
                "stderr": "",
            }
        if "chat.members" in command and "get" in command:
            return {
                "returncode": 0,
                "stdout": json.dumps(
                    {
                        "items": [
                            {"member_id": self.member_id}
                            if self.include_member
                            else {"member_id": "ou_someone_else"}
                        ]
                    }
                ),
                "stderr": "",
            }
        if "+messages-search" in command:
            query = command[command.index("--query") + 1]
            return {
                "returncode": self.search_returncode,
                "stdout": (
                    json.dumps(
                        {
                            "items": [
                                {"body": {"content": query}}
                                if self.search_hit
                                else {"body": {"content": "another PR"}}
                            ]
                        }
                    )
                    if self.search_returncode == 0
                    else ""
                ),
                "stderr": (
                    "missing scope search:message"
                    if self.search_returncode
                    else ""
                ),
            }
        if "+messages-send" in command:
            return {
                "returncode": self.send_returncode,
                "stdout": (
                    json.dumps({"data": {"message_id": "om_fixture_message"}})
                    if self.send_returncode == 0
                    else ""
                ),
                "stderr": (
                    "missing scope or bot is not in chat"
                    if self.send_returncode
                    else ""
                ),
            }
        if "+messages-mget" in command:
            send_call = next(call for call in self.calls if "+messages-send" in call)
            content = send_call[send_call.index("--content") + 1]
            text = content if self.include_message_content else "missing"
            return {
                "returncode": self.verify_returncode,
                "stdout": json.dumps(
                    {
                        "items": [
                            {
                                "message_id": "om_fixture_message",
                                "body": {"content": text},
                            }
                        ]
                    }
                ),
                "stderr": "readback failed" if self.verify_returncode else "",
            }
        raise AssertionError(command)


def fixture(
    *,
    reviewer: str = "@service-owner",
    explicit_profiles: bool = False,
) -> dict[str, Any]:
    sink: dict[str, Any] = {
        "sink_kind": "lark_chat",
        "sink_instance_key": "fixture-review-lane",
        "identity_scope": "project_dedicated",
        "bot_profile": "cli-private-profile",
        "bot_display_name": "Project Review Bot",
        "destination_id": "oc_private_destination",
        "reviewer_identities": {
            reviewer: {
                "member_id": "ou_private_member",
                "display_name": "Service Owner",
            }
        },
    }
    if explicit_profiles:
        sink.pop("bot_profile")
        sink.update(
            {
                "reader_profile": "fixture-reader-profile",
                "reader_identity": "user",
                "sender_profile": "fixture-sender-profile",
                "sender_identity": "bot",
            }
        )
    return {
        "schema_version": ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION,
        "receipts": [],
        "sinks": [sink],
    }


def reviewer_artifact_application() -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": (
            "issue_fix_reviewer_artifact_reward_memory_application_v0"
        ),
        "surface_id": "reviewer_artifact.summary",
        "reviewer_artifact": {
            "schema_version": "issue_fix_reviewer_artifact_v0",
            "repo": "owner/repo",
            "pr_ref": "#42",
            "permalink": "https://github.com/owner/repo/pull/42",
            "source_title": "fix: reject file URI for consistency check",
            "summary": "修复文件 URI 校验，并补充一致性回归测试",
        },
        "application": {
            "status": "applied",
            "receipt": {
                "schema_version": "reward_memory_application_receipt_v0",
                "application_id": "issue-fix:reviewer-artifact:owner/repo:42",
                "artifact_ref": "github:owner/repo#pr-42",
                "corpus_id": "reviewer_summary_policy",
                "surface_id": "reviewer_artifact.summary",
                "mode": "function_boundary",
                "outcome": "applied",
                "memory_ref_digests": ["0123456789abcdef"],
                "reasoning_summary": "当前 PR 已核验，摘要覆盖改动与验证。",
                "current_artifact_verified": True,
                "result_readback_verified": True,
                "model_reasoning_preserved": True,
                "grants_new_action_authority": False,
                "external_writes_performed": False,
                "raw_content_captured": False,
            },
        },
    }


def reviewer_notification_policy_application() -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": (
            "issue_fix_reviewer_notification_reward_memory_application_v0"
        ),
        "surface_id": "reviewer_notification.before_send",
        "decision": {
            "schema_version": "issue_fix_reviewer_notification_before_send_v0",
            "repo": "owner/repo",
            "pr_ref": "#42",
            "permalink": "https://github.com/owner/repo/pull/42",
            "delivery_policy": {
                "timezone": "Asia/Shanghai",
                "allowed_local_time": {"start": "09:00", "end": "21:00"},
                "outside_window": "queue_without_send",
            },
            "policy_source": "reward_memory",
            "policy_digest": "0123456789abcdef",
        },
        "application": {
            "status": "applied",
            "receipt": {
                "schema_version": "reward_memory_application_receipt_v0",
                "application_id": (
                    "issue-fix:reviewer-notification:owner/repo:42"
                ),
                "artifact_ref": "github:owner/repo#pr-42",
                "corpus_id": "reviewer_notification_delivery_policy",
                "surface_id": "reviewer_notification.before_send",
                "mode": "function_boundary",
                "outcome": "applied",
                "memory_ref_digests": ["0123456789abcdef"],
                "reasoning_summary": (
                    "Applied the active reviewer delivery policy."
                ),
                "current_artifact_verified": True,
                "result_readback_verified": True,
                "model_reasoning_preserved": True,
                "grants_new_action_authority": False,
                "external_writes_performed": False,
                "raw_content_captured": False,
            },
        },
    }


def assert_public_safe(packet: dict[str, Any]) -> None:
    text = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for pattern in PRIVATE_PATTERNS:
        assert not pattern.search(text), pattern.pattern
    assert packet["private_destination_captured"] is False
    assert packet["private_member_ids_captured"] is False
    assert packet["private_bot_profile_captured"] is False
    assert packet["raw_provider_payload_captured"] is False


def fake_provider_adapter(**kwargs: Any) -> dict[str, Any]:
    assert kwargs["execute"] is False
    assert kwargs["runner"] is not None
    return {
        "ok": True,
        "schema_version": "issue_fix_reviewer_notification_sink_result_v0",
        "sink_kind": "fixture_channel",
        "status": "preview_ready",
        "reviewer_handles": list(kwargs["reviewer_handles"]),
        "resolved_reviewer_count": len(kwargs["reviewer_handles"]),
        "idempotency_key": None,
        "identity_scope": "project_dedicated",
        "external_write_authority_asserted": False,
        "external_write_performed": False,
        "verification_performed": False,
        "notification_verified": False,
        "bot_identity_verified": False,
        "private_destination_captured": False,
        "private_member_ids_captured": False,
        "private_bot_profile_captured": False,
        "raw_provider_payload_captured": False,
    }


def main() -> int:
    provider_neutral = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input={
            "schema_version": ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_INPUT_SCHEMA_VERSION,
            "receipts": [],
            "sinks": [{"sink_kind": "fixture_channel"}],
        },
        execute=False,
        runner=FakeSinkRunner(),
        sink_adapters={"fixture_channel": fake_provider_adapter},
    )
    assert provider_neutral["ok"] is True, provider_neutral
    assert provider_neutral["status"] == "preview_ready"
    assert provider_neutral["results"][0]["sink_kind"] == "fixture_channel"
    assert_public_safe(provider_neutral)

    preview_runner = FakeSinkRunner()
    preview = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        execute=False,
        runner=preview_runner,
    )
    assert preview["schema_version"] == (
        ISSUE_FIX_REVIEWER_NOTIFICATION_SINKS_RESULT_SCHEMA_VERSION
    )
    assert preview["ok"] is True, preview
    assert preview["status"] == "preview_ready"
    assert preview["external_writes_performed"] is False
    assert preview_runner.calls == []
    assert_public_safe(preview)

    missing_memory_runner = FakeSinkRunner()
    missing_memory = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        reviewer_artifact_required=True,
        execute=True,
        runner=missing_memory_runner,
    )
    assert missing_memory["ok"] is False
    assert missing_memory["blocker"] == (
        "reward_memory_reviewer_artifact_unverified"
    )
    assert missing_memory["external_writes_performed"] is False
    assert missing_memory_runner.calls == []

    replayed_application = reviewer_artifact_application()
    replayed_application["reviewer_artifact"]["pr_ref"] = "#41"
    replay_runner = FakeSinkRunner()
    replayed = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        reviewer_artifact_application=replayed_application,
        reviewer_artifact_required=True,
        execute=True,
        runner=replay_runner,
    )
    assert replayed["ok"] is False
    assert replayed["reward_memory_reviewer_artifact_gate"]["reason_codes"] == [
        "current_artifact_identity_mismatch"
    ]
    assert replay_runner.calls == []

    gated_runner = FakeSinkRunner()
    gated = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        pr_title="fix: reject file URI for consistency check",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        reviewer_artifact_application=reviewer_artifact_application(),
        reviewer_artifact_required=True,
        execute=True,
        runner=gated_runner,
    )
    assert gated["status"] == "sent_verified", gated
    send_call = next(call for call in gated_runner.calls if "+messages-send" in call)
    sent_content = send_call[send_call.index("--content") + 1]
    assert "修复文件 URI 校验" in sent_content
    assert gated["reward_memory_reviewer_artifact_gate"]["passed"] is True
    assert_public_safe(gated)

    memory_window_runner = FakeSinkRunner()
    memory_window = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        reviewer_notification_policy_application=(
            reviewer_notification_policy_application()
        ),
        execute=True,
        delivery_observed_at="2026-07-10T14:30:00Z",
        runner=memory_window_runner,
    )
    assert memory_window["ok"] is True, memory_window
    assert memory_window["status"] == "queued_until_window"
    assert memory_window["delivery_policy_source"] == "reward_memory"
    assert memory_window["reward_memory_before_send_status"] == "applied"
    assert memory_window["external_writes_performed"] is False
    assert memory_window_runner.calls == []
    assert_public_safe(memory_window)

    outside_window_config = fixture()
    outside_window_config["delivery_policy"] = {
        "timezone": "Asia/Shanghai",
        "allowed_local_time": {"start": "09:00", "end": "21:00"},
        "outside_window": "queue_without_send",
    }
    outside_window_runner = FakeSinkRunner()
    queued = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=outside_window_config,
        execute=True,
        delivery_observed_at="2026-07-10T14:30:00Z",
        runner=outside_window_runner,
    )
    assert queued["ok"] is True, queued
    assert queued["status"] == "queued_until_window"
    assert queued["external_writes_performed"] is False
    assert queued["notification_verified"] is False
    assert queued["queued_receipts"][0]["not_before"] == (
        "2026-07-11T01:00:00Z"
    )
    assert outside_window_runner.calls == []
    assert_public_safe(queued)

    queued_retry_config = with_reviewer_notification_state(
        outside_window_config,
        (),
        queued["queued_receipts"],
    )
    queued_retry_runner = FakeSinkRunner()
    queued_retry = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=queued_retry_config,
        execute=True,
        delivery_observed_at="2026-07-10T14:35:00Z",
        runner=queued_retry_runner,
    )
    assert queued_retry["ok"] is True, queued_retry
    assert queued_retry["status"] == "already_queued"
    assert queued_retry["queued_receipts"] == queued["queued_receipts"]
    assert queued_retry_runner.calls == []
    assert_public_safe(queued_retry)

    failed_queued_retry_runner = FakeSinkRunner(send_returncode=1)
    failed_queued_retry = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=queued_retry_config,
        execute=True,
        delivery_observed_at="2026-07-10T02:30:00Z",
        runner=failed_queued_retry_runner,
    )
    assert failed_queued_retry["ok"] is False, failed_queued_retry
    assert failed_queued_retry["external_writes_performed"] is False
    assert failed_queued_retry["queued_receipts"] == queued["queued_receipts"]
    assert_public_safe(failed_queued_retry)

    inside_window_runner = FakeSinkRunner()
    inside_window = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=outside_window_config,
        execute=True,
        delivery_observed_at="2026-07-10T02:30:00Z",
        runner=inside_window_runner,
    )
    assert inside_window["status"] == "sent_verified", inside_window
    assert len(inside_window_runner.calls) == 3

    overnight_config = fixture()
    overnight_config["delivery_policy"] = {
        "timezone": "Asia/Shanghai",
        "allowed_local_time": {"start": "21:00", "end": "09:00"},
        "outside_window": "queue_without_send",
    }
    overnight_runner = FakeSinkRunner()
    overnight = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=overnight_config,
        execute=True,
        delivery_observed_at="2026-07-10T15:30:00Z",
        runner=overnight_runner,
    )
    assert overnight["status"] == "sent_verified", overnight
    assert len(overnight_runner.calls) == 3

    invalid_window_config = fixture()
    invalid_window_config["delivery_policy"] = {
        "timezone": "Asia/Shanghai",
        "allowed_local_time": {"start": "9am", "end": "21:00"},
        "outside_window": "queue_without_send",
    }
    invalid_window_runner = FakeSinkRunner()
    invalid_window = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=invalid_window_config,
        execute=True,
        delivery_observed_at="2026-07-10T14:30:00Z",
        runner=invalid_window_runner,
    )
    assert invalid_window["ok"] is False
    assert invalid_window["blocker"] == (
        "reviewer_notification_delivery_policy_invalid"
    )
    assert invalid_window_runner.calls == []
    assert_public_safe(invalid_window)

    runner = FakeSinkRunner()
    sent = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        pr_title="fix: reject file URI for consistency check",
        linked_issue_refs=["#40"],
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        execute=True,
        runner=runner,
    )
    assert sent["ok"] is True, sent
    assert sent["status"] == "sent_verified"
    assert sent["external_writes_performed"] is True
    assert sent["notification_verified"] is True
    assert len(runner.calls) == 3
    send = runner.calls[1]
    assert send[:3] == ["lark-cli", "--profile", "cli-private-profile"]
    assert send[send.index("--as") + 1] == "bot"
    assert send[send.index("--chat-id") + 1] == "oc_private_destination"
    provider_key = send[send.index("--idempotency-key") + 1]
    assert provider_key.startswith("loopx-")
    assert len(provider_key) <= 50
    content = send[send.index("--content") + 1]
    assert "ou_private_member" in content
    assert (
        "https://github.com/owner/repo/pull/42" in content
    )
    assert "请帮忙 review PR #42（修复 #40）" in content
    assert "reject file URI for consistency check" in content
    assert "loopx-reviewer-notification" not in content
    receipt = sent["receipts"][0]
    assert re.fullmatch(r"sha256:[a-f0-9]{64}", receipt)
    assert provider_key != receipt
    assert_public_safe(sent)

    explicit_runner = FakeSinkRunner()
    explicit = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(explicit_profiles=True),
        execute=True,
        runner=explicit_runner,
    )
    assert explicit["ok"] is True, explicit
    assert explicit["results"][0]["reader_identity_verified"] is True
    assert len(explicit_runner.calls) == 7, explicit_runner.calls
    assert explicit["results"][0]["semantic_dedupe_status"] == (
        "configured_chat_no_match"
    )
    explicit_send = next(
        call for call in explicit_runner.calls if "+messages-send" in call
    )
    assert explicit_send[:3] == [
        "lark-cli",
        "--profile",
        "fixture-sender-profile",
    ]
    member_read = next(
        call for call in explicit_runner.calls if "chat.members" in call
    )
    assert member_read[:3] == [
        "lark-cli",
        "--profile",
        "fixture-reader-profile",
    ]
    assert member_read[member_read.index("--as") + 1] == "user"
    sender_member_read = next(
        call
        for call in explicit_runner.calls
        if "chat.members" in call and call[call.index("--as") + 1] == "bot"
    )
    assert sender_member_read[:3] == [
        "lark-cli",
        "--profile",
        "fixture-sender-profile",
    ]
    assert_public_safe(explicit)

    remote_duplicate_runner = FakeSinkRunner(search_hit=True)
    remote_duplicate = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(explicit_profiles=True),
        execute=True,
        runner=remote_duplicate_runner,
    )
    assert remote_duplicate["status"] == "already_notified", remote_duplicate
    assert remote_duplicate["results"][0]["semantic_dedupe_status"] == (
        "configured_chat_match"
    )
    assert not any(
        "+messages-send" in call for call in remote_duplicate_runner.calls
    )

    permission_fallback_runner = FakeSinkRunner(search_returncode=1)
    permission_fallback = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(explicit_profiles=True),
        execute=True,
        runner=permission_fallback_runner,
    )
    assert permission_fallback["status"] == "sent_verified", permission_fallback
    assert permission_fallback["results"][0]["semantic_dedupe_status"] == (
        "permission_fallback"
    )
    assert any(
        "+messages-send" in call for call in permission_fallback_runner.calls
    )

    inbox_history = fixture(explicit_profiles=True)
    inbox_history["_semantic_history_pr_refs"] = [
        "https://github.com/owner/repo/pull/42"
    ]
    inbox_history_runner = FakeSinkRunner(search_returncode=1)
    inbox_duplicate = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=inbox_history,
        execute=True,
        runner=inbox_history_runner,
    )
    assert inbox_duplicate["status"] == "already_notified", inbox_duplicate
    assert inbox_duplicate["semantic_history_evidence_applied"] is True
    assert inbox_duplicate["results"][0]["semantic_dedupe_status"] == (
        "persisted_evidence_match"
    )
    assert inbox_history_runner.calls == []

    missing_member = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(explicit_profiles=True),
        execute=True,
        runner=FakeSinkRunner(include_member=False),
    )
    assert missing_member["ok"] is False, missing_member
    assert missing_member["blocker"] == "reviewer_notification_identity_unresolved"
    assert missing_member["external_writes_performed"] is False
    assert_public_safe(missing_member)

    substring_member = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(explicit_profiles=True),
        execute=True,
        runner=FakeSinkRunner(member_id="ou_private_member_suffix"),
    )
    assert substring_member["ok"] is False, substring_member
    assert substring_member["blocker"] == (
        "reviewer_notification_identity_unresolved"
    )
    assert substring_member["external_writes_performed"] is False
    assert_public_safe(substring_member)

    retry_input = fixture()
    retry_input["receipts"] = [receipt]
    retry_runner = FakeSinkRunner()
    retry = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=retry_input,
        execute=True,
        runner=retry_runner,
    )
    assert retry["ok"] is True, retry
    assert retry["status"] == "already_notified"
    assert retry["external_writes_performed"] is False
    assert retry_runner.calls == []
    assert_public_safe(retry)

    unresolved = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@unmapped-owner"],
        sinks_input=fixture(),
        execute=True,
        runner=FakeSinkRunner(),
    )
    assert unresolved["ok"] is False
    assert unresolved["status"] == "gate_required"
    assert unresolved["blocker"] == "reviewer_notification_identity_unresolved"
    assert unresolved["external_writes_performed"] is False
    assert_public_safe(unresolved)

    author = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@service-owner",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        execute=True,
        runner=FakeSinkRunner(),
    )
    assert author["ok"] is False
    assert author["blocker"] == "reviewer_notification_author_exclusion_failed"
    assert_public_safe(author)

    shared_identity = fixture()
    shared_identity["sinks"][0]["identity_scope"] = "shared"
    identity_gate = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=shared_identity,
        execute=True,
        runner=FakeSinkRunner(),
    )
    assert identity_gate["ok"] is False
    assert identity_gate["blocker"] == "dedicated_bot_identity_required"
    assert_public_safe(identity_gate)

    wrong_bot = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        execute=True,
        runner=FakeSinkRunner(bot_name="Unrelated Shared Bot"),
    )
    assert wrong_bot["ok"] is False
    assert wrong_bot["blocker"] == "dedicated_bot_identity_mismatch"
    assert wrong_bot["external_writes_performed"] is False
    assert_public_safe(wrong_bot)

    permission = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        execute=True,
        runner=FakeSinkRunner(send_returncode=1),
    )
    assert permission["ok"] is False
    assert permission["blocker"] == "lark_bot_group_access_required"
    assert permission["external_writes_performed"] is False
    assert_public_safe(permission)

    not_verified = build_issue_fix_reviewer_notification_sinks_result(
        repo="owner/repo",
        pr_number=42,
        pr_url="https://github.com/owner/repo/pull/42",
        author_handle="@current-author",
        reviewer_handles=["@service-owner"],
        sinks_input=fixture(),
        execute=True,
        runner=FakeSinkRunner(include_message_content=False),
    )
    assert not_verified["ok"] is False
    assert not_verified["blocker"] == "lark_notification_not_verified"
    assert not_verified["external_writes_performed"] is True
    assert_public_safe(not_verified)

    print("issue-fix-reviewer-notification-sink-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
