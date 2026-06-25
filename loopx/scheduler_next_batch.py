from __future__ import annotations

from typing import Any


SCHEDULER_NEXT_BATCH_SCHEMA_VERSION = "scheduler_next_batch_v0"


def build_scheduler_next_batch_payload(plan: dict[str, Any]) -> dict[str, Any]:
    dispatch = plan.get("dispatch_plan")
    if not isinstance(dispatch, dict):
        dispatch = {}
    handoffs = [item for item in dispatch.get("worker_handoffs") or [] if isinstance(item, dict)]
    runnable_ids = _ids(dispatch.get("runnable_todo_ids")) or _candidate_ids(plan.get("runnable_batch"))
    waiting_ids = _ids(dispatch.get("waiting_todo_ids")) or _candidate_ids(plan.get("waiting_candidates"))
    blocked_ids = _ids(dispatch.get("blocked_todo_ids")) or _candidate_ids(plan.get("blocked_candidates"))
    worker_slots = [_worker_slot(index, item) for index, item in enumerate(handoffs, start=1)]
    worker_slots = [item for item in worker_slots if item]
    return {
        "ok": bool(plan.get("ok")),
        "status_health_ok": bool(plan.get("status_health_ok")),
        "schema_version": SCHEDULER_NEXT_BATCH_SCHEMA_VERSION,
        "mode": "next_batch",
        "goal_id": plan.get("goal_id"),
        "agent_id": plan.get("agent_id"),
        "max_parallel": plan.get("max_parallel"),
        "ready_to_dispatch": bool(worker_slots),
        "dispatch_action": dispatch.get("action") or "idle",
        "dispatch_mode": _dispatch_mode(len(worker_slots), dispatch.get("action")),
        "parallelizable": len(worker_slots) > 1,
        "batch_size": len(worker_slots),
        "runnable_todo_ids": runnable_ids,
        "waiting_todo_ids": waiting_ids,
        "blocked_todo_ids": blocked_ids,
        "waiting_count": plan.get("waiting_count", len(waiting_ids)),
        "blocked_count": plan.get("blocked_count", len(blocked_ids)),
        "waiting_reason_counts": dispatch.get("waiting_reason_counts") or {},
        "blocked_reason_counts": dispatch.get("blocked_reason_counts") or {},
        "quota_guard_command": _string_command((plan.get("developer_commands") or {}).get("quota_guard")),
        "status_command": _string_command((plan.get("developer_commands") or {}).get("status")),
        "claim_commands": _claim_commands(plan.get("developer_commands")),
        "worker_slots": worker_slots,
        "developer_steps": dispatch.get("developer_steps") or [],
    }


def render_scheduler_next_batch_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Scheduler Next Batch",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- goal_id: `{payload.get('goal_id') or ''}`",
        f"- agent_id: `{payload.get('agent_id') or ''}`",
        f"- ready_to_dispatch: `{payload.get('ready_to_dispatch')}`",
        f"- dispatch_mode: `{payload.get('dispatch_mode') or ''}`",
        f"- batch_size: `{payload.get('batch_size')}`",
    ]
    _append_reason_counts(lines, "waiting", payload.get("waiting_reason_counts"))
    _append_reason_counts(lines, "blocked", payload.get("blocked_reason_counts"))
    quota_guard = _string_command(payload.get("quota_guard_command"))
    if quota_guard:
        lines.append(f"- quota_guard: `{quota_guard}`")
    worker_slots = payload.get("worker_slots")
    if isinstance(worker_slots, list) and worker_slots:
        lines.extend(["", "## Worker slots"])
        for item in worker_slots[:10]:
            if not isinstance(item, dict):
                continue
            todo_id = str(item.get("todo_id") or "").strip()
            lane = str(item.get("agent_lane") or "").strip()
            heading = todo_id
            if lane:
                heading = f"{heading} -> {lane}" if heading else lane
            lines.extend(["", f"### {heading}"])
            for key in (
                "quota_guard_command",
                "status_command",
                "claim_command",
                "complete_command_template",
                "blocked_command_template",
            ):
                value = _string_command(item.get(key))
                if value:
                    lines.append(f"- {key}: `{value}`")
            handoff_text = str(item.get("handoff_text") or "").strip()
            if handoff_text:
                lines.extend(["", "```text", handoff_text, "```"])
    return "\n".join(lines).rstrip() + "\n"


def _worker_slot(index: int, handoff: dict[str, Any]) -> dict[str, Any]:
    todo_id = str(handoff.get("todo_id") or handoff.get("candidate_key") or "").strip()
    if not todo_id:
        return {}
    keys = (
        "schema_version",
        "goal_id",
        "todo_id",
        "candidate_key",
        "agent_lane",
        "safety_class",
        "required_write_scopes",
        "required_decision_scopes",
        "claim_command",
        "quota_guard_command",
        "status_command",
        "complete_command_template",
        "blocked_command_template",
        "handoff_text",
    )
    slot = {"slot_index": index}
    slot.update({key: handoff.get(key) for key in keys if handoff.get(key) is not None})
    return slot


def _dispatch_mode(worker_count: int, action: Any) -> str:
    if worker_count > 1:
        return "parallel_batch"
    if worker_count == 1:
        return "single_worker"
    clean_action = str(action or "").strip()
    if clean_action == "wait_for_user":
        return "waiting_for_user"
    if clean_action in {"wait_for_lane_or_limit", "blocked", "idle"}:
        return clean_action
    return "not_dispatchable"


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _candidate_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        todo_id = str(item.get("todo_id") or item.get("candidate_key") or "").strip()
        if todo_id:
            ids.append(todo_id)
    return ids


def _claim_commands(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    raw = value.get("claim_runnable")
    if not isinstance(raw, list):
        return []
    return [_string_command(item) for item in raw if _string_command(item)]


def _append_reason_counts(lines: list[str], label: str, value: Any) -> None:
    if not isinstance(value, dict) or not value:
        return
    text = ",".join(f"{key}={count}" for key, count in sorted(value.items()))
    lines.append(f"- {label}_reason_counts: `{text}`")


def _string_command(value: Any) -> str:
    return str(value or "").strip()
