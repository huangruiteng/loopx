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
    ) -> None:
        self.send_returncode = send_returncode
        self.verify_returncode = verify_returncode
        self.include_message_content = include_message_content
        self.bot_name = bot_name
        self.reader_verified = reader_verified
        self.include_member = include_member
        self.member_id = member_id
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
    assert len(explicit_runner.calls) == 6, explicit_runner.calls
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
