from __future__ import annotations

import shlex
from typing import Any

from .notification_projection import compact_markdown
from .todo_contract import normalize_todo_id


def build_scheduler_handoffs_payload(plan: dict[str, Any], *, todo_id: str | None = None) -> dict[str, Any]:
    dispatch = plan.get("dispatch_plan")
    raw_handoffs = dispatch.get("worker_handoffs") if isinstance(dispatch, dict) else []
    handoffs = [item for item in raw_handoffs or [] if isinstance(item, dict)]
    safe_todo_id = normalize_todo_id(todo_id) if todo_id else None
    if safe_todo_id:
        handoffs = [
            item
            for item in handoffs
            if str(item.get("todo_id") or item.get("candidate_key") or "").strip() == safe_todo_id
        ]
    return {
        "ok": bool(plan.get("ok")),
        "status_health_ok": bool(plan.get("status_health_ok")),
        "schema_version": "scheduler_worker_handoffs_v0",
        "mode": "handoffs",
        "goal_id": plan.get("goal_id"),
        "agent_id": plan.get("agent_id"),
        "todo_id": safe_todo_id,
        "source_plan_action": dispatch.get("action") if isinstance(dispatch, dict) else None,
        "handoff_count": len(handoffs),
        "worker_handoffs": handoffs,
        "developer_commands": plan.get("developer_commands"),
    }


def build_worker_handoffs(*, goal_id: str, runnable_batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    handoffs: list[dict[str, Any]] = []
    for item in runnable_batch:
        todo_id = str(item.get("todo_id") or item.get("candidate_key") or "").strip()
        if not todo_id:
            continue
        lane = str(item.get("agent_lane") or item.get("claimed_by") or "").strip()
        payload: dict[str, Any] = {
            "schema_version": "scheduler_worker_handoff_v0",
            "goal_id": goal_id or None,
            "todo_id": todo_id,
            "candidate_key": item.get("candidate_key"),
            "agent_lane": lane or None,
            "safety_class": item.get("safety_class"),
            "required_write_scopes": item.get("required_write_scopes") or [],
            "required_decision_scopes": item.get("required_decision_scopes") or [],
            "handoff_text": _worker_handoff_text(goal_id=goal_id, item=item, agent_lane=lane),
        }
        if goal_id:
            payload["complete_command_template"] = _todo_complete_template(goal_id=goal_id, todo_id=todo_id)
            payload["blocked_command_template"] = _todo_blocked_template(goal_id=goal_id, todo_id=todo_id)
        if goal_id and lane:
            payload["quota_guard_command"] = _shell_join(
                [
                    "loopx",
                    "--format",
                    "json",
                    "quota",
                    "should-run",
                    "--goal-id",
                    goal_id,
                    "--agent-id",
                    lane,
                ]
            )
            payload["status_command"] = _shell_join(["loopx", "--format", "json", "status", "--agent-id", lane])
        if item.get("claim_command"):
            payload["claim_command"] = item.get("claim_command")
        handoffs.append({key: value for key, value in payload.items() if value is not None})
    return handoffs


def render_scheduler_handoffs_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Scheduler Worker Handoffs",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- goal_id: `{payload.get('goal_id') or ''}`",
        f"- agent_id: `{payload.get('agent_id') or ''}`",
        f"- todo_id: `{payload.get('todo_id') or ''}`",
        f"- handoff_count: `{payload.get('handoff_count')}`",
    ]
    handoffs = payload.get("worker_handoffs")
    if isinstance(handoffs, list) and handoffs:
        for item in handoffs[:10]:
            if not isinstance(item, dict):
                continue
            todo_id = str(item.get("todo_id") or item.get("candidate_key") or "").strip()
            lane = str(item.get("agent_lane") or "").strip()
            lines.extend(["", f"## {todo_id}"])
            if lane:
                lines.append(f"- agent_lane: `{lane}`")
            if item.get("quota_guard_command"):
                lines.append(f"- quota_guard: `{item.get('quota_guard_command')}`")
            if item.get("status_command"):
                lines.append(f"- status: `{item.get('status_command')}`")
            if item.get("complete_command_template"):
                lines.append(f"- complete: `{item.get('complete_command_template')}`")
            if item.get("blocked_command_template"):
                lines.append(f"- blocked: `{item.get('blocked_command_template')}`")
            text = str(item.get("handoff_text") or "").strip()
            if text:
                lines.extend(["", "```text", text, "```"])
    return "\n".join(lines).rstrip() + "\n"


def _worker_handoff_text(*, goal_id: str, item: dict[str, Any], agent_lane: str) -> str:
    todo_id = str(item.get("todo_id") or item.get("candidate_key") or "").strip()
    lines = [
        "LoopX worker handoff",
        f"Goal: {goal_id or '<unknown>'}",
        f"Todo: {todo_id}",
    ]
    if agent_lane:
        lines.append(f"Agent lane: {agent_lane}")
    text = str(item.get("text") or "").strip()
    if text:
        lines.append(f"Task: {text}")
    safety_class = str(item.get("safety_class") or "").strip()
    if safety_class:
        lines.append(f"Safety: {safety_class}")
    write_scopes = item.get("required_write_scopes")
    if isinstance(write_scopes, list) and write_scopes:
        lines.append("Write scopes: " + ", ".join(str(scope) for scope in write_scopes))
    decision_scopes = item.get("required_decision_scopes")
    if isinstance(decision_scopes, list) and decision_scopes:
        lines.append(f"Decision scopes: {len(decision_scopes)} required")
    lines.append("Before work: run quota/status guard for this lane.")
    lines.append("After work: update or complete the todo with public-safe evidence.")
    return compact_markdown("\n".join(lines), max_chars=700, suffix="...")


def _todo_complete_template(*, goal_id: str, todo_id: str) -> str:
    return _shell_join(
        [
            "loopx",
            "todo",
            "complete",
            "--goal-id",
            goal_id,
            "--role",
            "agent",
            "--todo-id",
            todo_id,
            "--evidence",
            "<public-safe evidence>",
        ]
    )


def _todo_blocked_template(*, goal_id: str, todo_id: str) -> str:
    return _shell_join(
        [
            "loopx",
            "todo",
            "update",
            "--goal-id",
            goal_id,
            "--role",
            "agent",
            "--todo-id",
            todo_id,
            "--status",
            "blocked",
            "--reason",
            "<public-safe blocker>",
        ]
    )


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts if str(part))
