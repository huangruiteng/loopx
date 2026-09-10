"""Local Agent inbox configuration owned by a Lark Goal Topic."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .goal_channel_contracts import operation_packet
from .private_json import write_private_json_atomic


def _agent_inbox_config(
    *,
    goal: Mapping[str, Any],
    agent_id: str,
    app_ref: str,
    chat_id: str,
    bot_display_name: str,
    capture_scope: str,
    topic_root_message_id: str | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    project = Path(str(goal.get("repo") or "")).expanduser().resolve()
    if not project.is_dir():
        raise ValueError("Goal repository is unavailable for Agent-scoped inbox setup")
    digest = hashlib.sha256(
        f"{goal.get('id')}\0{agent_id}\0{app_ref}\0{chat_id}".encode()
    ).hexdigest()[:20]
    config_ref = f".loopx/config/lark-goal-topics/{digest}.json"
    config_path = project / config_ref
    payload = {
        "schema_version": "lark_event_inbox_config_v0",
        "enabled": True,
        "inbox_dir": f".loopx/inbox/lark-goal-topics/{digest}",
        # Goal Topic routing applies this same scope before ingestion. Keeping
        # the local inbox declaration identical prevents an addressed-only
        # stream from being projected as thread-complete.
        "capture_scope": capture_scope,
        **(
            {"topic_root_message_id": topic_root_message_id}
            if topic_root_message_id
            else {}
        ),
        "reply": {
            "enabled": True,
            "sender_profile": app_ref,
            "sender_identity": "bot",
            "bot_display_name": bot_display_name,
            "chat_id": chat_id,
        },
    }
    return config_path, config_ref, payload


def _write_agent_inbox_config(
    *,
    config_path: Path,
    config_ref: str,
    payload: Mapping[str, Any],
) -> str:
    write_private_json_atomic(config_path, payload)
    return config_ref


def agent_inbox_binding_conflict_packet(
    *,
    goal: Mapping[str, Any],
    goal_id: str,
    agent_id: str,
    intended_config_path: Path,
    execute: bool,
) -> dict[str, Any] | None:
    """Reject a Topic that would silently replace an active Agent read route."""

    control_plane = goal.get("control_plane")
    control_plane = control_plane if isinstance(control_plane, Mapping) else {}
    agent_inboxes = control_plane.get("lark_event_inboxes")
    agent_inboxes = agent_inboxes if isinstance(agent_inboxes, Mapping) else {}
    current_inbox = agent_inboxes.get(agent_id)
    if not isinstance(current_inbox, Mapping):
        current_inbox = control_plane.get("lark_event_inbox")
    if (
        not isinstance(current_inbox, Mapping)
        or current_inbox.get("enabled") is not True
    ):
        return None
    current_ref = str(current_inbox.get("config_path") or "").strip()
    project = Path(str(goal["repo"])).expanduser().resolve()
    if (
        not current_ref
        or (project / current_ref).resolve() == intended_config_path.resolve()
    ):
        return None
    # A Topic is not authority to replace an existing read route. In particular,
    # a collector may cover several independent chats. Reject before effects.
    return operation_packet(
        ok=False,
        goal_id=goal_id,
        operation="connect_topic",
        execute=execute,
        status="blocked",
        blocker="agent_inbox_binding_conflict",
        public_summary=(
            "the Agent already consumes a different inbox; reconcile its routes "
            "explicitly before connecting this Topic"
        ),
    )
