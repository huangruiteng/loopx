from __future__ import annotations

from typing import Any


def render_turn_envelope_markdown(payload: dict[str, Any]) -> str:
    action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
    user = payload.get("user") if isinstance(payload.get("user"), dict) else {}
    writeback = payload.get("writeback") if isinstance(payload.get("writeback"), dict) else {}
    scheduler = payload.get("scheduler") if isinstance(payload.get("scheduler"), dict) else {}
    compaction = payload.get("compaction") if isinstance(payload.get("compaction"), dict) else {}
    lines = [
        "# LoopX Turn Envelope",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- agent_id: `{payload.get('agent_id')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- should_run: `{payload.get('should_run')}`",
        f"- effective_action: `{payload.get('effective_action')}`",
        f"- action: {action.get('primary_action') or action.get('recommended_action') or ''}",
        f"- user_action_required: `{user.get('action_required')}`",
        f"- spend_policy: {writeback.get('spend_policy') or ''}",
        f"- scheduler: `{scheduler.get('action')}`",
        f"- envelope_bytes: `{compaction.get('envelope_json_bytes')}`",
        f"- within_budget: `{compaction.get('within_budget')}`",
    ]
    return "\n".join(lines)
