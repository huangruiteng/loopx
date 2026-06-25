from __future__ import annotations

from typing import Any

from ...notification_projection import ProgressNotification
from .message_card import build_lark_markdown_reply_card, compact_markdown


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
        actions=tuple(action.to_dict() for action in notification.actions) + bridge_context_actions(item),
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
    scheduler_summary = str(item.get("scheduler_summary") or "").strip()
    if scheduler_summary:
        lines.extend(["", "**Initial scheduler snapshot**", compact_markdown(scheduler_summary, max_chars=700)])
    return "\n".join(lines)


def bridge_context_actions(item: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(item, dict) or not str(item.get("request_lane") or "").strip():
        return ()
    base_value = {
        "source": "loopx_feishu_progress_bridge",
        "todo_id": str(item.get("todo_id") or ""),
        "goal_id": str(item.get("goal_id") or ""),
    }
    return (
        {
            "action_id": "show_next_batch",
            "label": "下一批",
            "value": base_value,
        },
        {
            "action_id": "show_progress_now",
            "label": "刷新进度",
            "value": base_value,
        },
        {
            "action_id": "show_handoffs",
            "label": "交接步骤",
            "value": base_value,
        },
    )
