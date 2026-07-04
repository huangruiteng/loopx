from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..todos.contract import normalize_todo_claimed_by

QUOTA_MONITOR_TARGET_SCHEMA_VERSION = "quota_monitor_target_v0"


def monitor_target_summary(value: Any, *, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def monitor_target_agent_id(decision: dict[str, Any]) -> str | None:
    agent_identity = (
        decision.get("agent_identity")
        if isinstance(decision.get("agent_identity"), dict)
        else {}
    )
    return normalize_todo_claimed_by(agent_identity.get("agent_id"))


def build_quota_monitor_target(
    decision: dict[str, Any],
    *,
    monitor_mode: str,
) -> dict[str, Any]:
    action_summary = monitor_target_summary(
        decision.get("recommended_action") or decision.get("reason") or "",
        limit=160,
    )
    agent_id = monitor_target_agent_id(decision) or ""
    parts = {
        "goal_id": str(decision.get("goal_id") or ""),
        "agent_id": agent_id,
        "monitor_mode": str(monitor_mode or ""),
        "effective_action": str(decision.get("effective_action") or ""),
        "action_summary": action_summary,
    }
    target_id = hashlib.sha256(
        json.dumps(parts, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    target: dict[str, Any] = {
        "schema_version": QUOTA_MONITOR_TARGET_SCHEMA_VERSION,
        "target_id": target_id,
        "monitor_mode": parts["monitor_mode"],
        "effective_action": parts["effective_action"],
        "action_summary": action_summary,
    }
    if agent_id:
        target["agent_id"] = agent_id
    return target
