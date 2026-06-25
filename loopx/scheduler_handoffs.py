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
        quota_guard_command = _quota_guard_command(goal_id=goal_id, agent_lane=lane)
        status_command = _status_command(agent_lane=lane)
        complete_command = _todo_complete_template(goal_id=goal_id, todo_id=todo_id) if goal_id else ""
        blocked_command = _todo_blocked_template(goal_id=goal_id, todo_id=todo_id) if goal_id else ""
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
            "start_steps": _start_steps(
                item=item,
                quota_guard_command=quota_guard_command,
                status_command=status_command,
            ),
            "closeout_steps": _closeout_steps(
                complete_command=complete_command,
                blocked_command=blocked_command,
            ),
        }
        if complete_command:
            payload["complete_command_template"] = complete_command
        if blocked_command:
            payload["blocked_command_template"] = blocked_command
        if quota_guard_command:
            payload["quota_guard_command"] = quota_guard_command
        if status_command:
            payload["status_command"] = status_command
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
            _append_steps(lines, "Start steps", item.get("start_steps"))
            _append_steps(lines, "Closeout steps", item.get("closeout_steps"))
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


def _start_steps(
    *,
    item: dict[str, Any],
    quota_guard_command: str,
    status_command: str,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    claim_command = str(item.get("claim_command") or "").strip()
    if claim_command:
        steps.append(
            {
                "kind": "claim_todo",
                "required": True,
                "command": claim_command,
                "reason": "bind the unclaimed todo to this worker lane before starting",
            }
        )
    if quota_guard_command:
        steps.append(
            {
                "kind": "quota_guard",
                "required": True,
                "command": quota_guard_command,
                "reason": "confirm this goal or lane may spend compute now",
            }
        )
    if status_command:
        steps.append(
            {
                "kind": "status_check",
                "required": True,
                "command": status_command,
                "reason": "refresh blockers and gates before doing work",
            }
        )
    write_scopes = item.get("required_write_scopes")
    if isinstance(write_scopes, list) and write_scopes:
        steps.append(
            {
                "kind": "workspace_isolation",
                "required": True,
                "summary": "use an isolated worktree or branch and stay within required_write_scopes",
            }
        )
    else:
        steps.append(
            {
                "kind": "read_only_scope",
                "required": True,
                "summary": "do not mutate project state except for the final todo closeout",
            }
        )
    return steps


def _closeout_steps(*, complete_command: str, blocked_command: str) -> list[dict[str, Any]]:
    steps = [
        {
            "kind": "focused_validation",
            "required": True,
            "summary": "run the smallest relevant validation and capture public-safe evidence",
        }
    ]
    if complete_command:
        steps.append(
            {
                "kind": "complete_todo",
                "required": True,
                "command_template": complete_command,
            }
        )
    if blocked_command:
        steps.append(
            {
                "kind": "report_blocker",
                "required": True,
                "command_template": blocked_command,
            }
        )
    return steps


def _append_steps(lines: list[str], heading: str, value: Any) -> None:
    if not isinstance(value, list) or not value:
        return
    lines.append(f"- {heading}:")
    for step in value[:6]:
        if not isinstance(step, dict):
            continue
        kind = str(step.get("kind") or "").strip()
        command = str(step.get("command") or step.get("command_template") or "").strip()
        summary = str(step.get("summary") or step.get("reason") or "").strip()
        suffix = f": `{command}`" if command else f": {summary}" if summary else ""
        lines.append(f"  - {kind}{suffix}")


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


def _quota_guard_command(*, goal_id: str, agent_lane: str) -> str:
    if not goal_id:
        return ""
    command = ["loopx", "--format", "json", "quota", "should-run", "--goal-id", goal_id]
    if agent_lane:
        command.extend(["--agent-id", agent_lane])
    return _shell_join(command)


def _status_command(*, agent_lane: str) -> str:
    command = ["loopx", "--format", "json", "status"]
    if agent_lane:
        command.extend(["--agent-id", agent_lane])
    return _shell_join(command)


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts if str(part))
