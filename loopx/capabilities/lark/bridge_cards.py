from __future__ import annotations

from typing import Any

from ...notification_projection import ProgressNotification
from .message_card import build_lark_markdown_reply_card


def card_for_notification(notification: ProgressNotification, *, item: dict[str, Any] | None = None) -> dict[str, Any]:
    body = notification.markdown
    if notification.summary:
        body = f"**摘要**\n{notification.summary}\n\n{notification.markdown}"
    context = bridge_context_markdown(item)
    if context:
        body = f"{body}\n\n{context}"
    return build_lark_markdown_reply_card(
        body,
        title=notification.title,
        template=notification.template,
        footer=f"LoopX {notification.stage} | {notification.fingerprint}",
        actions=tuple(action.to_dict() for action in notification.actions),
    )


def bridge_context_markdown(item: dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""
    request_lane = str(item.get("request_lane") or "").strip()
    agent_id = str(item.get("agent_id") or "").strip()
    if not request_lane:
        return ""
    lines = [
        "**Bridge context**",
        f"- Progress lane: `{request_lane}`",
    ]
    if agent_id and agent_id != request_lane:
        lines.append(f"- Bridge agent: `{agent_id}`")
    lines.append("- Polling: status and quota are checked against this lane.")
    return "\n".join(lines)
