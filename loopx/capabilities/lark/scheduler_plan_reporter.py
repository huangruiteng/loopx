from __future__ import annotations

from typing import Any

from .message_card import compact_markdown


def render_scheduler_plan_chat_text(payload: dict[str, Any], *, max_chars: int = 1800) -> str:
    if not isinstance(payload, dict):
        return "Scheduler plan: unavailable"
    dispatch = payload.get("dispatch_plan")
    if not isinstance(dispatch, dict):
        dispatch = {}
    action = str(dispatch.get("action") or payload.get("mode") or "plan").strip()
    lines = [f"Scheduler plan: {action}"]
    goal_id = str(payload.get("goal_id") or dispatch.get("goal_id") or "").strip()
    agent_id = str(payload.get("agent_id") or dispatch.get("agent_id") or "").strip()
    if goal_id or agent_id:
        scope_parts = [
            part
            for part in (
                f"goal={goal_id}" if goal_id else "",
                f"agent={agent_id}" if agent_id else "",
            )
            if part
        ]
        lines.append("Scope: " + " ".join(scope_parts))
    if "parallelizable" in dispatch:
        lines.append(f"Parallelizable: {bool(dispatch.get('parallelizable'))}")

    runnable_ids = _scheduler_ids(dispatch.get("runnable_todo_ids")) or _candidate_ids(payload.get("runnable_batch"))
    waiting_ids = _scheduler_ids(dispatch.get("waiting_todo_ids")) or _candidate_ids(payload.get("waiting_candidates"))
    blocked_ids = _scheduler_ids(dispatch.get("blocked_todo_ids")) or _candidate_ids(payload.get("blocked_candidates"))
    if runnable_ids:
        lines.append(f"Runnable: {', '.join(runnable_ids)}")
    if waiting_ids:
        lines.append(f"Waiting todos: {', '.join(waiting_ids)}")
    if blocked_ids:
        lines.append(f"Blocked todos: {', '.join(blocked_ids)}")

    waiting_counts = _reason_count_text(dispatch.get("waiting_reason_counts"))
    blocked_counts = _reason_count_text(dispatch.get("blocked_reason_counts"))
    if waiting_counts:
        lines.append(f"Waiting: {waiting_counts}")
    if blocked_counts:
        lines.append(f"Blocked: {blocked_counts}")

    lane_lines = _scheduler_lane_lines(dispatch.get("agent_lanes"))
    if lane_lines:
        lines.append("Lanes:")
        lines.extend(lane_lines)
    handoff_text = _worker_handoff_summary(dispatch.get("worker_handoffs"))
    if handoff_text:
        lines.append(f"Worker handoffs: {handoff_text}")
    step_lines = _scheduler_step_lines(dispatch.get("developer_steps"))
    if step_lines:
        lines.append("Next steps:")
        lines.extend(step_lines)
    if not runnable_ids and not waiting_ids and not blocked_ids:
        lines.append("No runnable, waiting, or blocked scheduler candidates were reported.")
    return compact_markdown("\n".join(lines), max_chars=max_chars, suffix="...")


def render_scheduler_next_batch_chat_text(payload: dict[str, Any], *, max_chars: int = 1800) -> str:
    if not isinstance(payload, dict):
        return "Next batch: unavailable"
    dispatch_mode = str(payload.get("dispatch_mode") or payload.get("dispatch_action") or "idle").strip()
    lines = [f"Next batch: {dispatch_mode}"]
    goal_id = str(payload.get("goal_id") or "").strip()
    agent_id = str(payload.get("agent_id") or "").strip()
    if goal_id or agent_id:
        scope_parts = [
            part
            for part in (
                f"goal={goal_id}" if goal_id else "",
                f"agent={agent_id}" if agent_id else "",
            )
            if part
        ]
        lines.append("Scope: " + " ".join(scope_parts))
    lines.append(f"Dispatchable: {bool(payload.get('ready_to_dispatch'))}")
    if payload.get("batch_size") is not None:
        lines.append(f"Batch size: {payload.get('batch_size')}")
    worker_text = _worker_slot_summary(payload.get("worker_slots"))
    if worker_text:
        lines.append(f"Workers: {worker_text}")
    waiting_counts = _reason_count_text(payload.get("waiting_reason_counts"))
    blocked_counts = _reason_count_text(payload.get("blocked_reason_counts"))
    if waiting_counts:
        lines.append(f"Waiting: {waiting_counts}")
    if blocked_counts:
        lines.append(f"Blocked: {blocked_counts}")
    claim_commands = _command_lines("claim", payload.get("claim_commands"), limit=3)
    if claim_commands:
        lines.append("Claims:")
        lines.extend(claim_commands)
    quota_guard = str(payload.get("quota_guard_command") or "").strip()
    if quota_guard:
        lines.append(f"Quota guard: {quota_guard}")
    if not worker_text and not waiting_counts and not blocked_counts:
        lines.append("No dispatchable, waiting, or blocked scheduler candidates were reported.")
    return compact_markdown("\n".join(lines), max_chars=max_chars, suffix="...")


def render_scheduler_handoffs_chat_text(payload: dict[str, Any], *, max_chars: int = 1800) -> str:
    if not isinstance(payload, dict):
        return "Worker handoffs: unavailable"
    handoffs = payload.get("worker_handoffs")
    if not isinstance(handoffs, list):
        handoffs = []
    count = payload.get("handoff_count")
    if count is None:
        count = len(handoffs)
    lines = [f"Worker handoffs: {count}"]
    goal_id = str(payload.get("goal_id") or "").strip()
    agent_id = str(payload.get("agent_id") or "").strip()
    todo_id = str(payload.get("todo_id") or "").strip()
    scope_parts = [
        part
        for part in (
            f"goal={goal_id}" if goal_id else "",
            f"agent={agent_id}" if agent_id else "",
            f"todo={todo_id}" if todo_id else "",
        )
        if part
    ]
    if scope_parts:
        lines.append("Scope: " + " ".join(scope_parts))
    action = str(payload.get("source_plan_action") or "").strip()
    if action:
        lines.append(f"Source action: {action}")
    if not handoffs:
        lines.append("No dispatchable worker handoffs were reported.")
        return compact_markdown("\n".join(lines), max_chars=max_chars, suffix="...")
    for handoff in handoffs[:4]:
        if not isinstance(handoff, dict):
            continue
        heading = _handoff_heading(handoff)
        if heading:
            lines.append(heading)
        safety = str(handoff.get("safety_class") or "").strip()
        write_scopes = _scheduler_ids(handoff.get("required_write_scopes"))
        if safety or write_scopes:
            details = [
                part
                for part in (
                    f"safety={safety}" if safety else "",
                    "write=" + ",".join(write_scopes) if write_scopes else "",
                )
                if part
            ]
            lines.append("  " + " ".join(details))
        start_lines = _handoff_step_lines(handoff.get("start_steps"), limit=4)
        if start_lines:
            lines.append("  Start:")
            lines.extend("  " + line for line in start_lines)
        closeout_lines = _handoff_step_lines(handoff.get("closeout_steps"), limit=3)
        if closeout_lines:
            lines.append("  Closeout:")
            lines.extend("  " + line for line in closeout_lines)
    return compact_markdown("\n".join(lines), max_chars=max_chars, suffix="...")


def _scheduler_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value[:8] if str(item or "").strip()]


def _candidate_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        todo_id = str(item.get("todo_id") or item.get("candidate_key") or "").strip()
        if todo_id:
            ids.append(todo_id)
    return ids


def _reason_count_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts = []
    for key, count in sorted(value.items()):
        clean_key = str(key or "").strip()
        if clean_key:
            parts.append(f"{clean_key}={count}")
    return ", ".join(parts)


def _scheduler_lane_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for lane in value[:4]:
        if not isinstance(lane, dict):
            continue
        name = str(lane.get("agent_lane") or "unassigned").strip()
        runnable = _scheduler_ids(lane.get("runnable_todo_ids"))
        waiting = _scheduler_ids(lane.get("waiting_todo_ids"))
        blocked = _scheduler_ids(lane.get("blocked_todo_ids"))
        details = []
        if runnable:
            details.append("run=" + ",".join(runnable))
        if waiting:
            details.append("wait=" + ",".join(waiting))
        if blocked:
            details.append("block=" + ",".join(blocked))
        if details:
            lines.append(f"- {name}: {'; '.join(details)}")
    return lines


def _scheduler_step_lines(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for step in value[:5]:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "").strip()
        command = str(step.get("command") or "").strip()
        if not kind or not command:
            continue
        todo_id = str(step.get("todo_id") or "").strip()
        label = f"{kind} {todo_id}".strip()
        lines.append(f"- {label}: {command}")
    return lines


def _worker_handoff_summary(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for handoff in value[:6]:
        if not isinstance(handoff, dict):
            continue
        todo_id = str(handoff.get("todo_id") or handoff.get("candidate_key") or "").strip()
        if not todo_id:
            continue
        lane = str(handoff.get("agent_lane") or "").strip()
        parts.append(f"{todo_id}->{lane}" if lane else todo_id)
    return ", ".join(parts)


def _worker_slot_summary(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for slot in value[:6]:
        if not isinstance(slot, dict):
            continue
        todo_id = str(slot.get("todo_id") or slot.get("candidate_key") or "").strip()
        if not todo_id:
            continue
        lane = str(slot.get("agent_lane") or "").strip()
        parts.append(f"{todo_id}->{lane}" if lane else todo_id)
    return ", ".join(parts)


def _handoff_heading(value: dict[str, Any]) -> str:
    todo_id = str(value.get("todo_id") or value.get("candidate_key") or "").strip()
    if not todo_id:
        return ""
    lane = str(value.get("agent_lane") or "").strip()
    return f"- {todo_id}->{lane}" if lane else f"- {todo_id}"


def _handoff_step_lines(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for step in value[:limit]:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "").strip()
        command = str(step.get("command") or step.get("command_template") or "").strip()
        summary = str(step.get("summary") or step.get("reason") or "").strip()
        if not kind:
            continue
        if command:
            lines.append(f"- {kind}: {command}")
        elif summary:
            lines.append(f"- {kind}: {summary}")
        else:
            lines.append(f"- {kind}")
    return lines


def _command_lines(label: str, value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    lines: list[str] = []
    for item in value[:limit]:
        command = str(item or "").strip()
        if command:
            lines.append(f"- {label}: {command}")
    return lines
