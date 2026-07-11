from __future__ import annotations

from typing import Any


def render_turn_envelope_markdown(payload: dict[str, Any]) -> str:
    action_value = payload.get("action")
    user_value = payload.get("user")
    writeback_value = payload.get("writeback")
    scheduler_value = payload.get("scheduler")
    compaction_value = payload.get("compaction")
    action = action_value if isinstance(action_value, dict) else {}
    user = user_value if isinstance(user_value, dict) else {}
    writeback = writeback_value if isinstance(writeback_value, dict) else {}
    scheduler = scheduler_value if isinstance(scheduler_value, dict) else {}
    compaction = compaction_value if isinstance(compaction_value, dict) else {}
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
