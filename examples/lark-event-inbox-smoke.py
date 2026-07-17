#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.capabilities.lark.event_inbox import (  # noqa: E402
    acknowledge_lark_event_inbox,
    ingest_lark_event_inbox,
    inspect_lark_event_inbox,
    lark_event_inbox_contains_text,
    project_lark_event_inbox_urgency,
)
from loopx.capabilities.lark.inbox_reply import reply_lark_event_inbox  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as raw:
        project = Path(raw)
        inbox = project / ".loopx" / "inbox" / "team-feedback"
        config = project / ".loopx" / "config" / "lark-event-inbox.json"
        inbox.mkdir(parents=True)
        config.parent.mkdir(parents=True)
        config.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": ".loopx/inbox/team-feedback",
                }
            ),
            encoding="utf-8",
        )
        event = {
            "schema_version": "lark_event_inbox_event_v0",
            "event_id": "evt-review-1",
            "message_id": "om_review_1",
            "create_time": "2026-07-12T10:00:00Z",
            "content": "@LoopX Bot please record this feedback for the owning domain",
        }
        (inbox / "evt-review-1.json").write_text(json.dumps(event), encoding="utf-8")
        (inbox / "duplicate.json").write_text(
            json.dumps({**event, "event_id": "evt-review-1-retry"}),
            encoding="utf-8",
        )
        (inbox / "invalid.json").write_text("{}", encoding="utf-8")

        pending = inspect_lark_event_inbox(
            project=project,
            config_path=config,
        )
        assert pending["pending_count"] == 1, pending
        assert pending["invalid_count"] == 1, pending
        assert pending["items"][0]["message_id"] == "om_review_1", pending
        assert pending["thread_complete"] is False, pending
        assert "thread replies" in pending["coverage_warning"], pending

        config.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": ".loopx/inbox/team-feedback",
                    "capture_scope": "configured_chat_all",
                }
            ),
            encoding="utf-8",
        )
        pending = inspect_lark_event_inbox(project=project, config_path=config)
        assert pending["thread_complete"] is True, pending
        assert lark_event_inbox_contains_text(
            project=project,
            config_path=config,
            text="record this feedback",
        ) is True
        assert lark_event_inbox_contains_text(
            project=project,
            config_path=config,
            text="https://github.com/owner/repo/pull/404",
        ) is False

        imported = ingest_lark_event_inbox(
            project=project,
            config_path=config,
            events=[
                {
                    "schema_version": "lark_event_inbox_event_v0",
                    "event_id": "evt-thread-reply-2",
                    "message_id": "om_review_2",
                    "create_time": "2026-07-12T10:01:00Z",
                    "content": "A thread reply without a direct bot mention",
                },
                event,
                {"schema_version": "wrong"},
            ],
            execute=True,
        )
        assert imported["accepted_count"] == 1, imported
        assert imported["duplicate_count"] == 1, imported
        assert imported["invalid_count"] == 1, imported
        assert (
            inspect_lark_event_inbox(
                project=project,
                config_path=config,
            )["pending_count"]
            == 2
        )

        preview = acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_1"],
        )
        assert preview["write_performed"] is False, preview

        written = acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_1"],
            execute=True,
        )
        assert written["write_performed"] is True, written
        assert (
            inspect_lark_event_inbox(
                project=project,
                config_path=config,
            )["pending_count"]
            == 1
        )

        acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_2"],
            execute=True,
        )

        repeated = acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=["om_review_1"],
            execute=True,
        )
        assert repeated["write_performed"] is False, repeated

        processed = json.loads((inbox / "processed.json").read_text(encoding="utf-8"))
        assert processed["schema_version"] == "lark_event_inbox_processed_v0"

        config.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": ".loopx/inbox/team-feedback",
                    "capture_scope": "configured_chat_all",
                    "reply": {
                        "enabled": True,
                        "sender_profile": "project-review-bot",
                        "sender_identity": "bot",
                        "bot_display_name": "Project Review Bot",
                        "chat_id": "oc_project_review",
                    },
                }
            ),
            encoding="utf-8",
        )

        urgency_events = [
            {
                "schema_version": "lark_event_inbox_event_v0",
                "event_id": "evt-direct-question",
                "message_id": "om_direct_question",
                "create_time": "2026-07-12T10:02:00Z",
                "content": "@Project Review Bot 结论呢？",
            },
            {
                "schema_version": "lark_event_inbox_event_v0",
                "event_id": "evt-ordinary-chat",
                "message_id": "om_ordinary_chat",
                "create_time": "2026-07-12T10:03:00Z",
                "content": "Project Review Bot 这个普通项目问题为什么会这样？",
            },
            {
                "schema_version": "lark_event_inbox_event_v0",
                "event_id": "evt-reply-to-bot",
                "message_id": "om_reply_to_bot",
                "parent_id": "om_bot_parent",
                "create_time": "2026-07-12T10:04:00Z",
                "content": "收到，继续按这个方向处理",
                "reply_context_verified": True,
                "reply_to_bot": True,
            },
            {
                "schema_version": "lark_event_inbox_event_v0",
                "event_id": "evt-reply-to-human",
                "message_id": "om_reply_to_human",
                "parent_id": "om_human_parent",
                "create_time": "2026-07-12T10:05:00Z",
                "content": "这是回复群成员，不是回复机器人",
                "reply_context_verified": True,
                "reply_to_bot": False,
            },
        ]
        ingest_lark_event_inbox(
            project=project,
            config_path=config,
            events=urgency_events,
            execute=True,
        )
        urgency = project_lark_event_inbox_urgency(
            project=project,
            config_path=config,
            now=datetime(2026, 7, 12, 10, 12, tzinfo=timezone.utc),
        )
        assert urgency["pending_count"] == 4, urgency
        assert urgency["direct_question_count"] == 1, urgency
        assert urgency["direct_mention_count"] == 0, urgency
        assert urgency["reply_to_bot_count"] == 1, urgency
        assert urgency["attention_required_count"] == 2, urgency
        assert urgency["reply_due"] is True, urgency
        assert urgency["oldest_pending_age_seconds"] == 600, urgency
        assert urgency["local_private_content_returned"] is False, urgency
        assert "items" not in urgency, urgency
        acknowledge_lark_event_inbox(
            project=project,
            config_path=config,
            message_ids=[
                "om_direct_question",
                "om_ordinary_chat",
                "om_reply_to_bot",
                "om_reply_to_human",
            ],
            execute=True,
        )

        calls: list[list[str]] = []

        def successful_runner(args):
            calls.append(list(args))
            if args[3:6] == ["auth", "status", "--verify"]:
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "identities": {
                                "bot": {
                                    "available": True,
                                    "verified": True,
                                    "appName": "Project Review Bot",
                                }
                            }
                        }
                    ),
                    "stderr": "",
                }
            if args[3:6] == ["im", "chats", "get"]:
                return {"returncode": 0, "stdout": "{}", "stderr": ""}
            if "+messages-reply" in args:
                return {
                    "returncode": 0,
                    "stdout": json.dumps({"message_id": "om_reply_1"}),
                    "stderr": "",
                }
            if "+messages-mget" in args:
                return {
                    "returncode": 0,
                    "stdout": json.dumps(
                        {
                            "items": [
                                {
                                    "message_id": "om_reply_1",
                                    "content": "已记录并修正。",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    "stderr": "",
                }
            raise AssertionError(args)

        replied = reply_lark_event_inbox(
            project=project,
            config_path=config,
            message_id="om_review_2",
            text="已记录并修正。",
            execute=True,
            runner=successful_runner,
        )
        assert replied["status"] == "sent_verified", replied
        assert replied["sender_identity_verified"] is True, replied
        assert replied["sender_chat_membership_verified"] is True, replied
        assert replied["private_sender_profile_captured"] is False, replied
        assert calls and all(
            call[:3] == ["lark-cli", "--profile", "project-review-bot"]
            for call in calls
        ), calls
        assert any("+messages-reply" in call for call in calls), calls
        reply_call = next(call for call in calls if "+messages-reply" in call)
        assert reply_call[reply_call.index("--message-id") + 1] == "om_review_2"
        assert "--reply-in-thread" in reply_call
        assert all(
            "--as" in call and call[call.index("--as") + 1] == "bot"
            for call in calls[1:]
        ), calls

        def mention_runner(*, readback_open_id: str):
            def run(args):
                if args[3:6] == ["auth", "status", "--verify"]:
                    return successful_runner(args)
                if args[3:6] == ["im", "chats", "get"]:
                    return {"returncode": 0, "stdout": "{}", "stderr": ""}
                if "+messages-reply" in args:
                    return {
                        "returncode": 0,
                        "stdout": json.dumps({"message_id": "om_reply_mention"}),
                        "stderr": "",
                    }
                if "+messages-mget" in args:
                    return {
                        "returncode": 0,
                        "stdout": json.dumps(
                            {
                                "items": [
                                    {
                                        "message_id": "om_reply_mention",
                                        "body": {
                                            "content": json.dumps(
                                                {"text": "@_user_1 已记录并修正。"},
                                                ensure_ascii=False,
                                            )
                                        },
                                        "mentions": [
                                            {
                                                "key": "@_user_1",
                                                "id": {
                                                    "open_id": readback_open_id,
                                                    "user_id": "fixture-user-id",
                                                },
                                                "name": "Reviewer",
                                            }
                                        ],
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        ),
                        "stderr": "",
                    }
                raise AssertionError(args)

            return run

        mention_reply = (
            '<at user_id="ou_reviewer_fixture">Reviewer</at> 已记录并修正。'
        )
        normalized_mention = reply_lark_event_inbox(
            project=project,
            config_path=config,
            message_id="om_review_2",
            text=mention_reply,
            execute=True,
            runner=mention_runner(readback_open_id="ou_reviewer_fixture"),
        )
        assert normalized_mention["status"] == "sent_verified", normalized_mention

        wrong_mention = reply_lark_event_inbox(
            project=project,
            config_path=config,
            message_id="om_review_2",
            text=mention_reply,
            execute=True,
            runner=mention_runner(readback_open_id="ou_different_fixture"),
        )
        assert wrong_mention["status"] == "sent_unverified", wrong_mention
        assert wrong_mention["blocker"] == "lark_inbox_reply_not_verified", (
            wrong_mention
        )

        membership_calls: list[list[str]] = []

        def missing_membership_runner(args):
            membership_calls.append(list(args))
            if args[3:6] == ["auth", "status", "--verify"]:
                return successful_runner(args)
            if args[3:6] == ["im", "chats", "get"]:
                return {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "bot is not in the chat",
                }
            raise AssertionError("send must not run after membership failure")

        blocked = reply_lark_event_inbox(
            project=project,
            config_path=config,
            message_id="om_review_2",
            text="不会发送",
            execute=True,
            runner=missing_membership_runner,
        )
        assert blocked["status"] == "gate_required", blocked
        assert blocked["blocker"] == "lark_inbox_reply_sender_not_in_configured_chat", (
            blocked
        )
        assert not any("+messages-reply" in call for call in membership_calls), (
            membership_calls
        )

        try:
            reply_lark_event_inbox(
                project=project,
                config_path=config,
                message_id="om_not_captured",
                text="不应发送",
                execute=True,
                runner=lambda args: (_ for _ in ()).throw(AssertionError(args)),
            )
        except ValueError as exc:
            assert "not captured" in str(exc)
        else:
            raise AssertionError("reply must stay bound to a captured inbox message")

        registry = project / ".loopx" / "registry.json"
        registry.write_text(
            json.dumps(
                {
                    "goals": [
                        {
                            "id": "lark-inbox-fixture",
                            "repo": str(project),
                            "control_plane": {
                                "lark_event_inbox": {
                                    "enabled": True,
                                    "config_path": ".loopx/config/lark-event-inbox.json",
                                }
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        discovered = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--format",
                "json",
                "lark-inbox",
                "drain",
                "--goal-id",
                "lark-inbox-fixture",
                "--project",
                str(project),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert discovered.returncode == 0, discovered.stderr
        discovered_payload = json.loads(discovered.stdout)
        assert discovered_payload["configured"] is True, discovered_payload
        assert discovered_payload["pending_count"] == 0, discovered_payload

        shared_registry = project / "registry.global.json"
        shared_registry.write_text(
            json.dumps(
                {
                    "registry_role": "global-local",
                    "common_runtime_root": str(project / "shared-runtime"),
                    "goals": [
                        {
                            "id": "lark-inbox-fixture",
                            "repo": str(project),
                            "source_registry": str(registry),
                            "control_plane": {
                                "lark_event_inbox": {
                                    "enabled": True,
                                    "config_path": (
                                        ".loopx/config/lark-event-inbox.json"
                                    ),
                                }
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        linked_worktree = project / "linked-worktree"
        linked_worktree.mkdir()
        routed = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(shared_registry),
                "--format",
                "json",
                "lark-inbox",
                "drain",
                "--goal-id",
                "lark-inbox-fixture",
            ],
            cwd=linked_worktree,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        assert routed.returncode == 0, routed.stderr
        routed_payload = json.loads(routed.stdout)
        assert routed_payload["configured"] is True, routed_payload
        assert routed_payload["pending_count"] == 0, routed_payload

        reply_preview = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--registry",
                str(registry),
                "--format",
                "json",
                "lark-inbox",
                "reply",
                "--goal-id",
                "lark-inbox-fixture",
                "--project",
                str(project),
                "--message-id",
                "om_review_2",
                "--text",
                "已记录并修正。",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert reply_preview.returncode == 0, reply_preview.stderr
        reply_preview_payload = json.loads(reply_preview.stdout)
        assert reply_preview_payload["status"] == "preview_ready", reply_preview_payload
        assert reply_preview_payload["private_sender_profile_captured"] is False
        assert "project-review-bot" not in reply_preview.stdout

        outside = project / ".loopx" / "config" / "outside.json"
        outside.write_text(
            json.dumps(
                {
                    "schema_version": "lark_event_inbox_config_v0",
                    "enabled": True,
                    "inbox_dir": "../outside",
                }
            ),
            encoding="utf-8",
        )
        try:
            inspect_lark_event_inbox(project=project, config_path=outside)
        except ValueError as exc:
            assert ".loopx/inbox" in str(exc)
        else:
            raise AssertionError("unsafe inbox path must fail closed")

    print("lark-event-inbox-smoke: ok")


if __name__ == "__main__":
    main()
