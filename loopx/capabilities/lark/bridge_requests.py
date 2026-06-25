from __future__ import annotations

import hashlib

from .message_card import compact_markdown
from ...todo_contract import normalize_todo_claimed_by


def normalize_feishu_request_text(text: str, *, max_chars: int = 700) -> str:
    return " ".join(compact_markdown(text, max_chars=max_chars, suffix="...").split())


def feishu_request_lane(*, agent_id: str, message_id: str, request_text: str) -> str:
    base = normalize_todo_claimed_by(agent_id) or "codex-agent"
    digest = hashlib.sha256(f"{message_id}\n{request_text}".encode("utf-8")).hexdigest()[:10]
    trimmed_base = base[:65].rstrip("-._:@") or "codex-agent"
    return f"{trimmed_base}-req-{digest}"


def build_feishu_request_todo_args(
    *,
    request_text: str,
    message_id: str,
    goal_id: str,
    agent_id: str,
) -> tuple[list[str], str, str]:
    clean = normalize_feishu_request_text(request_text)
    if not clean:
        raise ValueError("Write a task after /ask.")
    lane = feishu_request_lane(agent_id=agent_id, message_id=message_id, request_text=clean)
    todo_text = (
        "Triage the Feishu bot request, report progress, and ask for a gate "
        f"before writes or external actions. Reply to message_id={message_id} when done. "
        f"Request: {clean}"
    )
    return [
        "todo",
        "add",
        "--goal-id",
        goal_id,
        "--role",
        "agent",
        "--text",
        todo_text,
        "--task-class",
        "advancement_task",
        "--action-kind",
        "feishu_user_request",
        "--safety-class",
        "read_only",
        "--claimed-by",
        lane,
    ], clean, lane
