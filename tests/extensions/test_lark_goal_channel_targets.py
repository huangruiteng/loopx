from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.cli import build_parser
from loopx.cli_commands import goal_channel as goal_channel_cli
from loopx.extensions.lark.goal_channel import (
    GOAL_CHANNEL_BINDING_SCHEMA_VERSION,
    add_lark_goal_channel_target,
    list_goal_channel_targets,
)
from loopx.extensions.lark.goal_channel_contracts import binding_for_goal


GOAL_ID = "goal-public-fixture"
CHAT_ID = "oc_public_fixture"
CONTROL_MESSAGE_ID = "om_control_public_fixture"


def _provider_target() -> dict[str, Any]:
    return {
        "name": "loopx-dev",
        "provider": "lark",
        "enabled": True,
        "channel": {
            "chat_id": CHAT_ID,
            "chat_name": "LoopX Development",
        },
        "identity": {
            "mode": "local_user",
            "sender_profile": "",
            "sender_identity": "bot",
            "bot_app_id": "cli_public_fixture",
            "bot_display_name": "",
            "cli_bin": "lark-cli",
        },
    }


def _assert_public_packet(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "oc_" not in serialized
    assert "om_" not in serialized
    assert "cli_public_fixture" not in serialized
    assert str(Path.home()) not in serialized


def test_shared_target_store_is_local_private_and_lists_only_public_names(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "runtime" / "goal-channel-targets.json"

    preview = add_lark_goal_channel_target(
        target_path=target_path,
        target_name="loopx-dev",
        chat_id=CHAT_ID,
        chat_name="LoopX Development",
        bot_app_id="cli_public_fixture",
    )
    assert preview["ok"] is True
    assert preview["status"] == "preview_ready"
    assert not target_path.exists()

    configured = add_lark_goal_channel_target(
        target_path=target_path,
        target_name="loopx-dev",
        chat_id=CHAT_ID,
        chat_name="LoopX Development",
        bot_app_id="cli_public_fixture",
        execute=True,
    )
    assert configured["ok"] is True
    assert configured["status"] == "configured"
    assert target_path.stat().st_mode & 0o777 == 0o600

    listed = list_goal_channel_targets(target_path=target_path)
    assert listed["details"] == {
        "target_count": 1,
        "items": [{"target_name": "loopx-dev", "provider": "lark", "enabled": True}],
    }
    _assert_public_packet(configured)
    _assert_public_packet(listed)


def test_binding_resolves_shared_target_without_merging_goal_local_state() -> None:
    payload = {
        "schema_version": GOAL_CHANNEL_BINDING_SCHEMA_VERSION,
        "bindings": {
            GOAL_ID: {
                "goal_id": GOAL_ID,
                "provider": "lark",
                "target_ref": "loopx-dev",
                "enabled": True,
                "channel": {"pinned_message_id": CONTROL_MESSAGE_ID},
                "identity": {},
                "kanban": {"base_url": "https://example.invalid/base/goal"},
                "receipts": {"goal-local-receipt": {"kind": "control_message"}},
            }
        },
    }
    changed_target = _provider_target()
    changed_target["channel"] = {
        "chat_id": "oc_updated_public_fixture",
        "chat_name": "Updated shared group",
    }

    resolved = binding_for_goal(
        payload,
        GOAL_ID,
        provider_target=changed_target,
    )

    assert resolved is not None
    assert resolved["channel"] == {
        "chat_id": "oc_updated_public_fixture",
        "chat_name": "Updated shared group",
        "pinned_message_id": CONTROL_MESSAGE_ID,
    }
    assert resolved["identity"] == changed_target["identity"]
    assert resolved["receipts"] == payload["bindings"][GOAL_ID]["receipts"]


def test_shared_target_cli_parses_add_setup_and_bounded_attach() -> None:
    parser = build_parser()
    target = parser.parse_args(
        [
            "goal-channel",
            "target",
            "add",
            "--name",
            "loopx-dev",
            "--chat-id",
            CHAT_ID,
            "--bot-app-id",
            "cli_public_fixture",
        ]
    )
    setup = parser.parse_args(
        ["goal-channel", "setup", "--goal-id", GOAL_ID, "--target", "loopx-dev"]
    )
    attach = parser.parse_args(
        [
            "goal-channel",
            "attach",
            "--target",
            "loopx-dev",
            "--goal-id",
            GOAL_ID,
            "--goal-id",
            "goal-second-public-fixture",
        ]
    )
    prepare = parser.parse_args(
        [
            "goal-channel",
            "prepare-payload",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            "codex-public-delivery",
            "--request-json",
            "payload.json",
        ]
    )
    deliver = parser.parse_args(
        [
            "goal-channel",
            "deliver-payload",
            "--goal-id",
            GOAL_ID,
            "--receipt-id",
            "gcp_0123456789abcdef01234567",
        ]
    )

    assert target.goal_channel_target_command == "add"
    assert setup.target == "loopx-dev"
    assert attach.goal_id == [GOAL_ID, "goal-second-public-fixture"]
    assert prepare.agent_id == "codex-public-delivery"
    assert prepare.request_json == "payload.json"
    assert deliver.receipt_id == "gcp_0123456789abcdef01234567"

    bounded = goal_channel_cli._attach_goals(
        registry={},
        registry_path=Path("registry.json"),
        goal_ids=[f"goal-{index}" for index in range(9)],
        target_name="loopx-dev",
        provider_target=_provider_target(),
        execute=True,
    )
    assert bounded["ok"] is False
    assert bounded["blocker"] == "bounded_batch_exceeded"


def test_effectful_attach_stops_after_first_failed_goal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []
    monkeypatch.setattr(
        goal_channel_cli,
        "_source_context",
        lambda **kwargs: (
            {"goals": []},
            tmp_path / ".loopx" / "registry.json",
            tmp_path / ".loopx" / "goal-channel.json",
            tmp_path / "runtime",
        ),
    )

    def setup(**kwargs: Any) -> dict[str, Any]:
        goal_id = str(kwargs["goal_id"])
        attempted.append(goal_id)
        ok = goal_id != "goal-fail"
        return {
            "ok": ok,
            "status": "configured" if ok else "failed",
            "blocker": None if ok else "provider_api_failed",
            "external_write_performed": ok,
            "readback_verified": ok,
        }

    monkeypatch.setattr(goal_channel_cli, "setup_lark_goal_channel", setup)

    result = goal_channel_cli._attach_goals(
        registry={},
        registry_path=tmp_path / "registry.json",
        goal_ids=["goal-ok", "goal-fail", "goal-never-attempted"],
        target_name="loopx-dev",
        provider_target=_provider_target(),
        execute=True,
    )

    assert result["ok"] is False
    assert result["details"]["completed_count"] == 2
    assert result["external_write_performed"] is True
    assert attempted == ["goal-ok", "goal-fail"]
