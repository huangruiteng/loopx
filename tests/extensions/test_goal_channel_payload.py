from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.extensions.lark.goal_channel_contracts import (
    GOAL_CHANNEL_BINDING_SCHEMA_VERSION,
    read_goal_channel_binding,
    write_goal_channel_binding,
)
from loopx.extensions.lark.goal_channel_payload import (
    FROZEN_PAYLOAD_REQUEST_SCHEMA,
    deliver_goal_channel_payload,
    prepare_goal_channel_payload,
)
from loopx.extensions.lark.goal_channel_targets import add_lark_goal_channel_target
from loopx.status import parse_active_state_todos
from loopx.todos import complete_goal_todo


GOAL_ID = "goal-public-fixture"
AGENT_ID = "codex-public-delivery"
CHAT_ID = "oc_public_fixture"
APP_ID = "cli_public_fixture"
SCOPE = "public_claim:action:publish-public-fixture"


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "---\n"
        f"goal_id: {GOAL_ID}\n"
        "updated_at: 2026-09-12T00:00:00+00:00\n"
        "---\n\n"
        "## User Todo\n\n"
        "## Agent Todo\n",
        encoding="utf-8",
    )
    runtime_root = tmp_path / "runtime"
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir()
    registry_path.write_text(
        json.dumps(
            {
                "common_runtime_root": str(runtime_root),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": "ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "read_only_project_map_v0"},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [AGENT_ID],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    target_path = runtime_root / "goal-channel-targets.json"
    add_lark_goal_channel_target(
        target_path=target_path,
        target_name="public-route",
        chat_id=CHAT_ID,
        chat_name="Public Fixture",
        identity_mode="project_bot",
        sender_profile="project-reporter",
        sender_identity="bot",
        bot_app_id=APP_ID,
        bot_display_name="Project Reporter",
        cli_bin="lark-cli",
        execute=True,
    )
    binding_path = registry_path.parent / "goal-channel.json"
    _write_binding(binding_path)
    return registry_path, runtime_root, binding_path, target_path


def _write_binding(binding_path: Path, *, target_ref: str = "public-route") -> None:
    write_goal_channel_binding(
        binding_path,
        {
            "schema_version": GOAL_CHANNEL_BINDING_SCHEMA_VERSION,
            "bindings": {
                GOAL_ID: {
                    "goal_id": GOAL_ID,
                    "provider": "lark",
                    "enabled": True,
                    "target_ref": target_ref,
                    "channel": {},
                    "identity": {},
                }
            },
        },
    )


def _request(
    *, markdown: str = "Validated fact.\n\nRecommended next research step."
) -> dict[str, Any]:
    return {
        "schema_version": FROZEN_PAYLOAD_REQUEST_SCHEMA,
        "capability_id": "example-capability",
        "payload_ref": "example-result-v1",
        "title": "Public research result",
        "markdown": markdown,
        "footer": "LoopX verified result",
        "decision_scope": SCOPE,
        "public_safe": True,
    }


def _prepare_and_approve(
    registry_path: Path, runtime_root: Path, binding_path: Path, target_path: Path
) -> dict[str, Any]:
    prepared = prepare_goal_channel_payload(
        _request(),
        registry_path=registry_path,
        runtime_root=runtime_root,
        binding_path=binding_path,
        target_path=target_path,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        execute=True,
    )
    complete_goal_todo(
        registry_path=registry_path,
        runtime_root_arg=str(runtime_root),
        goal_id=GOAL_ID,
        todo_id=prepared["details"]["approval_todo_id"],
        role="user",
        decision_outcome="approve",
        evidence="owner approved the exact frozen public payload",
    )
    return prepared


def _runner(calls: list[list[str]]):
    sent_cards: dict[str, dict[str, Any]] = {}

    def run(
        args: list[str], _cwd: Path | None, _timeout: float | None
    ) -> dict[str, Any]:
        calls.append(args)
        if "auth" in args and "status" in args:
            payload = {
                "ok": True,
                "appId": APP_ID,
                "identities": {
                    "bot": {
                        "available": True,
                        "verified": True,
                        "appName": "Project Reporter",
                    }
                },
            }
        elif "chats" in args and "get" in args:
            payload = {"ok": True, "data": {"chat_id": CHAT_ID}}
        elif "+chat-members-list" in args:
            payload = {"ok": True, "data": {"bots": [{"app_id": APP_ID}]}}
        elif "+chat-messages-list" in args:
            payload = {
                "ok": True,
                "has_more": False,
                "messages": [
                    {
                        "message_id": message_id,
                        "chat_id": CHAT_ID,
                        "sender": {"sender_type": "app", "id": APP_ID},
                        "deleted": False,
                        "body": {"content": json.dumps(card)},
                    }
                    for message_id, card in sent_cards.items()
                ],
            }
        elif "+messages-send" in args:
            message_id = f"om_payload_fixture_{len(sent_cards) + 1}"
            sent_cards[message_id] = json.loads(args[args.index("--content") + 1])
            payload = {"ok": True, "data": {"message_id": message_id}}
        elif "+messages-mget" in args:
            message_id = args[args.index("--message-ids") + 1]
            payload = {
                "ok": True,
                "data": {
                    "items": [
                        {
                            "message_id": message_id,
                            "chat_id": CHAT_ID,
                            "sender": {"sender_type": "app", "id": APP_ID},
                            "body": {"content": json.dumps(sent_cards[message_id])},
                        }
                    ]
                },
            }
        else:  # pragma: no cover
            raise AssertionError(args)
        return {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""}

    return run


def test_prepare_creates_blocked_successor_and_exact_user_gate(tmp_path: Path) -> None:
    registry_path, runtime_root, binding_path, target_path = _fixture(tmp_path)
    result = prepare_goal_channel_payload(
        _request(),
        registry_path=registry_path,
        runtime_root=runtime_root,
        binding_path=binding_path,
        target_path=target_path,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        execute=True,
    )

    assert result["status"] == "approval_pending"
    state = registry_path.parent.parent / "ACTIVE_GOAL_STATE.md"
    parsed = parse_active_state_todos(
        state.read_text(encoding="utf-8"), item_limit=None
    )
    delivery = next(
        item
        for item in parsed["agent_todos"]["items"]
        if item["todo_id"] == result["details"]["delivery_todo_id"]
    )
    gate = next(
        item
        for item in parsed["user_todos"]["items"]
        if item["todo_id"] == result["details"]["approval_todo_id"]
    )
    assert delivery["status"] == "blocked"
    assert (
        delivery["required_decision_scopes"][0]["scope_key"] == "publish-public-fixture"
    )
    assert gate["unblocks_todo_id"] == delivery["todo_id"]
    assert gate["decision_scope"] == delivery["required_decision_scopes"][0]
    assert "Validated fact" not in state.read_text(encoding="utf-8")


def test_prepare_preview_has_no_durable_write(tmp_path: Path) -> None:
    registry_path, runtime_root, binding_path, target_path = _fixture(tmp_path)
    state = registry_path.parent.parent / "ACTIVE_GOAL_STATE.md"
    before = state.read_text(encoding="utf-8")

    result = prepare_goal_channel_payload(
        _request(),
        registry_path=registry_path,
        runtime_root=runtime_root,
        binding_path=binding_path,
        target_path=target_path,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        execute=False,
    )

    assert result["status"] == "pending_execution"
    assert state.read_text(encoding="utf-8") == before
    assert not (runtime_root / "goals" / GOAL_ID / "goal_channel_payloads").exists()


def test_delivery_fails_closed_before_exact_approval(tmp_path: Path) -> None:
    registry_path, runtime_root, binding_path, target_path = _fixture(tmp_path)
    prepared = prepare_goal_channel_payload(
        _request(),
        registry_path=registry_path,
        runtime_root=runtime_root,
        binding_path=binding_path,
        target_path=target_path,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        execute=True,
    )
    calls: list[list[str]] = []

    with pytest.raises(ValueError, match="lacks exact approval"):
        deliver_goal_channel_payload(
            receipt_id=prepared["receipt_id"],
            registry_path=registry_path,
            runtime_root=runtime_root,
            binding_path=binding_path,
            target_path=target_path,
            goal_id=GOAL_ID,
            execute=True,
            runner=_runner(calls),
        )

    assert calls == []


def test_approved_delivery_is_verified_and_exact_replay_is_deduped(
    tmp_path: Path,
) -> None:
    registry_path, runtime_root, binding_path, target_path = _fixture(tmp_path)
    prepared = _prepare_and_approve(
        registry_path, runtime_root, binding_path, target_path
    )
    calls: list[list[str]] = []
    runner = _runner(calls)

    first = deliver_goal_channel_payload(
        receipt_id=prepared["receipt_id"],
        registry_path=registry_path,
        runtime_root=runtime_root,
        binding_path=binding_path,
        target_path=target_path,
        goal_id=GOAL_ID,
        execute=True,
        runner=runner,
    )
    replay = deliver_goal_channel_payload(
        receipt_id=prepared["receipt_id"],
        registry_path=registry_path,
        runtime_root=runtime_root,
        binding_path=binding_path,
        target_path=target_path,
        goal_id=GOAL_ID,
        execute=True,
        runner=runner,
    )

    assert first["status"] == replay["status"] == "satisfied"
    assert first["external_write_performed"] is True
    assert replay["external_write_performed"] is False
    assert replay["details"]["semantic_dedupe_status"] == "existing_exact_message"
    assert len([args for args in calls if "+messages-send" in args]) == 1


def test_approved_payload_and_route_drift_fail_before_send(tmp_path: Path) -> None:
    registry_path, runtime_root, binding_path, target_path = _fixture(tmp_path)
    prepared = _prepare_and_approve(
        registry_path, runtime_root, binding_path, target_path
    )
    receipt_path = (
        runtime_root
        / "goals"
        / GOAL_ID
        / "goal_channel_payloads"
        / f"{prepared['receipt_id']}.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["card"]["header"]["title"]["content"] = "Changed after approval"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    calls: list[list[str]] = []
    with pytest.raises(ValueError, match="content drifted"):
        deliver_goal_channel_payload(
            receipt_id=prepared["receipt_id"],
            registry_path=registry_path,
            runtime_root=runtime_root,
            binding_path=binding_path,
            target_path=target_path,
            goal_id=GOAL_ID,
            execute=True,
            runner=_runner(calls),
        )
    assert calls == []

    receipt_path.unlink()
    prepared = _prepare_and_approve(
        registry_path, runtime_root, binding_path, target_path
    )
    binding = read_goal_channel_binding(binding_path)
    binding["bindings"][GOAL_ID]["enabled"] = False
    write_goal_channel_binding(binding_path, binding)
    with pytest.raises(ValueError, match="enabled Lark Goal Channel binding"):
        deliver_goal_channel_payload(
            receipt_id=prepared["receipt_id"],
            registry_path=registry_path,
            runtime_root=runtime_root,
            binding_path=binding_path,
            target_path=target_path,
            goal_id=GOAL_ID,
            execute=True,
            runner=_runner(calls),
        )
    assert calls == []


def test_prepare_rejects_non_public_scope_and_mentions(tmp_path: Path) -> None:
    registry_path, runtime_root, binding_path, target_path = _fixture(tmp_path)
    request = _request()
    request["decision_scope"] = "write_scope:action:publish-public-fixture"
    with pytest.raises(ValueError, match="public_claim:action"):
        prepare_goal_channel_payload(
            request,
            registry_path=registry_path,
            runtime_root=runtime_root,
            binding_path=binding_path,
            target_path=target_path,
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
        )
    with pytest.raises(ValueError, match="mention"):
        prepare_goal_channel_payload(
            _request(markdown='<at open_id="ou_public">Someone</at>'),
            registry_path=registry_path,
            runtime_root=runtime_root,
            binding_path=binding_path,
            target_path=target_path,
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
        )
