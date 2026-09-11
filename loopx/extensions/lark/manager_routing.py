"""Addressed machine-manager conversations, including group-root messages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from pathlib import Path

from ...chat_manager import manager_channel
from ..external_connector_runtime import project_external_connector_status
from .goal_channel_contracts import bindings_for_goal
from .goal_channel_targets import goal_channel_target_for_name
from .goal_channel_transport import CHAT_ID_PATTERN, MESSAGE_ID_PATTERN
from .goal_topic_routing import is_event_addressed_to_bot


def has_manager_binding(payloads: Mapping[str, Any], target_ref: str) -> bool:
    return any(
        item.get("enabled") is True
        and item.get("target_ref") == target_ref
        and (item.get("routing") or {}).get("conversation_kind") == "manager"
        for goal_id, payload in payloads.items()
        if isinstance(payload, Mapping)
        for item in bindings_for_goal(payload, str(goal_id))
    )


def decide_manager_event(
    *,
    target_payload: Mapping[str, Any],
    binding_payloads: Mapping[str, Any],
    event: Mapping[str, Any],
) -> dict[str, Any] | None:
    """A manager receives addressed messages; exact worker Topics keep priority."""
    chat_id, message_id = (
        str(event.get("chat_id") or ""),
        str(event.get("message_id") or ""),
    )
    if not CHAT_ID_PATTERN.fullmatch(chat_id) or not MESSAGE_ID_PATTERN.fullmatch(
        message_id
    ):
        return None
    root = str(event.get("root_id") or "")
    candidates = []
    for goal_id, payload in binding_payloads.items():
        for binding in bindings_for_goal(payload, goal_id):
            if binding.get("enabled") is not True:
                continue
            target = (
                goal_channel_target_for_name(
                    target_payload, str(binding.get("target_ref") or "")
                )
                or {}
            )
            if (target.get("channel") or {}).get("chat_id") != chat_id:
                continue
            routing = binding.get("routing") or {}
            topic_root = str(
                (binding.get("topic") or {}).get("root_message_id")
                or (binding.get("channel") or {}).get("pinned_message_id")
                or ""
            )
            if routing.get("conversation_kind") != "manager":
                if root and root == topic_root:
                    return None
                continue
            candidates.append((goal_id, binding, target, routing, topic_root))
    if not candidates:
        return None

    def ignored(reason: str) -> dict[str, Any]:
        return {"matched": False, "reason": reason, "route": None}

    if len(candidates) != 1:
        return ignored("route_ambiguous")
    goal_id, binding, target, routing, topic_root = candidates[0]
    identity = target.get("identity") or {}
    if str(event.get("sender_id") or "") in {
        str(identity.get("bot_open_id") or "__unset__"),
        str(identity.get("bot_app_id") or "__unset__"),
    }:
        return ignored("self_message")
    if not is_event_addressed_to_bot(event, identity):
        return ignored("not_addressed")
    connector = binding.get("connector")
    if not _valid_manager_binding(goal_id, binding, routing):
        return ignored("invalid_routing_state")
    profile = str(identity.get("sender_profile") or "default")
    return {
        "matched": True,
        "reason": "matched",
        "route": {
            "goal_id": goal_id,
            "connection_id": binding["connection_id"],
            "agent_id": binding["agent_id"],
            "session_id": binding["session_id"],
            "conversation_kind": "manager",
            "executor_endpoint_id": routing.get("executor_endpoint_id") or "codex",
            "manager_channel_id": manager_channel(
                provider="lark", audience=f"{profile}\0{chat_id}"
            ),
            "app_ref": profile,
            "target_ref": binding["target_ref"],
            "message_id": message_id,
            "event_id": str(event.get("event_id") or message_id),
            "topic_root_message_id": topic_root,
            "capture_scope": "addressed_only",
            "ingress_mode": "session_queue",
            "reply_mode": "topic_reply",
            "connector": dict(connector),
        },
    }


def _valid_manager_binding(goal_id, binding, routing) -> bool:
    connector = binding.get("connector")
    try:
        status = project_external_connector_status(connector)
        return bool(
            routing.get("ingress_mode") == "session_queue"
            and binding.get("session_id")
            and status["goal_ref"] == goal_id
            and status["agent_ref"] == binding.get("agent_id")
            and status["ingress_policy"] == "session_queue"
            and connector.get("session_ref") == binding.get("session_id")
        )
    except (TypeError, ValueError, AttributeError):
        return False


def authorized_manager_goal_ids(
    snapshot: Mapping[str, Any], session: Mapping[str, Any], *, runtime_root: Path | None = None
) -> list[str]:
    """Resolve current external read authority; a session's old Goal is not a grant."""
    candidates = []
    targets = snapshot.get("target_payload") or {}
    for goal_id, payload in (snapshot.get("binding_payloads") or {}).items():
        for binding in bindings_for_goal(payload, goal_id):
            routing = binding.get("routing") or {}
            if (
                binding.get("enabled") is not True
                or routing.get("conversation_kind") != "manager"
            ):
                continue
            target = (
                goal_channel_target_for_name(
                    targets, str(binding.get("target_ref") or "")
                )
                or {}
            )
            if target.get("enabled") is not True:
                continue
            profile = str(
                (target.get("identity") or {}).get("sender_profile") or "default"
            )
            chat_id = str((target.get("channel") or {}).get("chat_id") or "")
            channel = manager_channel(provider="lark", audience=f"{profile}\0{chat_id}")
            if channel != session.get("channel_id") or not CHAT_ID_PATTERN.fullmatch(
                chat_id
            ):
                continue
            candidates.append((goal_id, binding, routing))
    if len(candidates) != 1:
        return []
    goal_id, binding, routing = candidates[0]
    if (
        binding.get("session_id") != session.get("session_id")
        or (routing.get("executor_endpoint_id") or "codex") != session.get("agent_id")
        or not _valid_manager_binding(goal_id, binding, routing)
    ):
        return []
    if runtime_root is not None:
        from ...capabilities.manager_context import evidence_goal_scope
        grant = evidence_goal_scope(runtime_root, str(session.get("channel_id") or ""))
        if grant is not None:
            return grant
    return [goal_id]
