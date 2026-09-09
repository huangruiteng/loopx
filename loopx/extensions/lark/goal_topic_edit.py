"""Resolve an existing Lark route without changing recipient or provider scope."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...agent_registry import registered_agent_ids_for_goal
from ...control_plane.goals.configure_goal_service import (
    configure_goal_with_global_sync,
)
from .goal_channel_contracts import (
    binding_for_goal,
    bindings_for_goal,
    read_goal_channel_binding,
)
from .goal_channel_targets import (
    goal_channel_target_for_name,
    read_goal_channel_targets,
)


@dataclass(frozen=True)
class ExistingGoalTopic:
    binding: dict[str, Any]
    app_ref: str
    chat_id: str
    chat_name: str
    agent_id: str | None
    capture_scope: str | None


def resolve_existing_goal_topic(
    *,
    goal: Mapping[str, Any],
    goal_id: str,
    binding_path: Path,
    target_path: Path,
    connection_id: str,
    app_ref: str,
    chat_id: str,
    agent_id: str | None,
    capture_scope: str | None,
) -> ExistingGoalTopic:
    """Caller holds the Goal binding mutation lock through validation and save."""
    editing = binding_for_goal(
        read_goal_channel_binding(binding_path),
        goal_id,
        connection_id=connection_id,
    )
    if not editing or editing.get("provider") != "lark" or not editing.get("enabled"):
        raise ValueError(
            "connection_id must name an enabled Lark connection for this Goal"
        )
    target = goal_channel_target_for_name(
        read_goal_channel_targets(target_path), str(editing.get("target_ref") or "")
    )
    if not target:
        raise ValueError("the existing connection target is unavailable")
    identity = target.get("identity") or {}
    channel = target.get("channel") or {}
    stored_app = str(identity.get("sender_profile") or "default")
    stored_chat = str(channel.get("chat_id") or "")
    if (app_ref and app_ref != stored_app) or (chat_id and chat_id != stored_chat):
        raise ValueError(
            "editing preserves the connection App and group; create a new connection to move it"
        )
    app_ref, chat_id = stored_app, stored_chat
    chat_name = str(channel.get("chat_name") or editing.get("target_ref") or "")
    stored_agent = str(editing.get("agent_id") or "")
    if stored_agent and agent_id and agent_id != stored_agent:
        raise ValueError("editing cannot reassign an existing Agent connection")
    agent_id = agent_id or stored_agent or None
    if not agent_id:
        agents = registered_agent_ids_for_goal(goal)
        if len(agents) == 1:
            agent_id = next(iter(agents))
    old_routing = editing.get("routing") or {}
    stored_scope = str(
        old_routing.get("capture_scope")
        or (
            "configured_chat_all"
            if old_routing.get("incoming_mode") == "all"
            else "addressed_only"
        )
    )
    if old_routing.get("ingress_mode", "direct_session") == "direct_session":
        if capture_scope and capture_scope != stored_scope:
            raise ValueError(
                "upgrading a legacy connection must preserve its capture scope"
            )
        capture_scope = stored_scope
    for sibling in bindings_for_goal(read_goal_channel_binding(binding_path), goal_id):
        if (
            sibling.get("connection_id") != connection_id
            and agent_id
            and sibling.get("agent_id") == agent_id
            and sibling.get("enabled")
        ):
            raise ValueError(
                "the Agent already has another enabled connection for this Goal"
            )
    return ExistingGoalTopic(
        editing, app_ref, chat_id, chat_name, agent_id, capture_scope
    )


def resolve_conversation_policy(
    *,
    editing: Mapping[str, Any] | None,
    conversation_kind: str | None,
    executor_endpoint_id: str | None,
    ingress_mode: str | None,
) -> tuple[str, str | None, str | None]:
    from .goal_channel_transport import SAFE_PROFILE_PATTERN

    prior = (editing or {}).get("routing") or {}
    kind = conversation_kind or prior.get("conversation_kind") or "goal"
    if kind not in {"goal", "manager"}:
        raise ValueError("conversation_kind must be goal or manager")
    if kind == "manager":
        endpoint = executor_endpoint_id or prior.get("executor_endpoint_id") or "codex"
        if not SAFE_PROFILE_PATTERN.fullmatch(endpoint):
            raise ValueError("executor_endpoint_id must be a safe endpoint reference")
        if ingress_mode and ingress_mode != "session_queue":
            raise ValueError(
                "the machine manager uses synchronous session_queue delivery"
            )
        return kind, endpoint, "session_queue"
    return kind, None, ingress_mode


def _unregister_async_inbox(
    *, removed: Mapping[str, Any] | None, registry_path: Path | None, goal_id: str
) -> tuple[dict[str, Any] | None, str]:
    routing = removed.get("routing") if isinstance(removed, Mapping) else None
    routing = routing if isinstance(routing, Mapping) else {}
    agent_id = str(removed.get("agent_id") or "").strip() if removed else ""
    if routing.get("ingress_mode") != "async_inbox" or not agent_id:
        return None, agent_id
    if registry_path is None:
        error = "source registry path is required to unregister the Agent inbox"
        return {"ok": False, "error": error}, agent_id
    try:
        return configure_goal_with_global_sync(
            registry_path=registry_path,
            goal_id=goal_id,
            runtime_root_override=None,
            execute=True,
            lark_event_inbox_agent_id=agent_id,
            clear_lark_event_inbox_config=True,
        ), agent_id
    except (OSError, ValueError, TimeoutError) as exc:
        # The binding removal already landed; report the cleanup failure as a
        # failed packet instead of raising past the caller mid-disconnect.
        return {"ok": False, "error": str(exc)}, agent_id
