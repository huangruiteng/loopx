from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any


MAX_REASON_CHARS = 360
MAX_ACTION_CHARS = 420
MAX_TODO_CHARS = 240
TODO_ID_KEYS = ("todo_id", "id")
TODO_DONE_STATES = {"done", "completed", "complete", "closed", "resolved"}
DEFAULT_TRUNCATION_SUFFIX = "\n\n...truncated."


def compact_markdown(
    text: object,
    *,
    max_chars: int = 3600,
    suffix: str = DEFAULT_TRUNCATION_SUFFIX,
) -> str:
    value = str(text or "").replace("\r", "").replace("\\r\\n", "\n").replace("\\n", "\n").strip()
    if len(value) <= max_chars:
        return value
    if max_chars <= len(suffix):
        return suffix[-max_chars:]
    return value[: max_chars - len(suffix)].rstrip() + suffix


def compact_plain_text(text: object, *, max_chars: int = 72) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    return compact_markdown(value, max_chars=max_chars, suffix="...")


@dataclass(frozen=True)
class NotificationAction:
    action_id: str
    label: str
    style: str = "default"
    value: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload.get("value") is None:
            payload["value"] = {}
        return payload


@dataclass(frozen=True)
class ProgressNotification:
    todo_id: str
    goal_id: str
    stage: str
    title: str
    template: str
    markdown: str
    fingerprint: str
    done: bool = False
    priority: str = "normal"
    summary: str = ""
    actions: tuple[NotificationAction, ...] = ()
    key_event: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["actions"] = [action.to_dict() for action in self.actions]
        return payload


NotificationProjection = ProgressNotification


def build_acceptance_notification(
    *,
    todo_id: str,
    goal_id: str,
    request_text: str,
    agent_id: str | None = None,
) -> ProgressNotification:
    lines = [
        "**Accepted**",
        "",
        f"- Todo: `{_safe(todo_id)}`",
        f"- Goal: `{_safe(goal_id)}`",
    ]
    if agent_id:
        lines.append(f"- Agent: `{_safe(agent_id)}`")
    request = _text(request_text, MAX_ACTION_CHARS)
    if request:
        lines.extend(["", "**Request**", request])
    lines.extend(
        [
            "",
            "**Next updates**",
            "Progress cards are sent only when LoopX detects a stage change, a blocker, a user gate, or completion.",
        ]
    )
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="accepted",
        title="LoopX accepted",
        template="green",
        markdown="\n".join(lines),
        summary="已接收任务，后续只在阶段变化、阻塞、需要你确认或完成时提醒。",
    )


def build_bridge_error_notification(
    *,
    todo_id: str,
    goal_id: str,
    source: str,
    error: object,
) -> ProgressNotification:
    lines = [
        "**Bridge check failed**",
        "",
        f"- Todo: `{_safe(todo_id)}`",
        f"- Goal: `{_safe(goal_id)}`",
        f"- Source: `{_safe(source)}`",
        "",
        _text(error, MAX_REASON_CHARS) or "Unknown bridge error.",
    ]
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage=f"bridge_error:{source}",
        title="LoopX progress bridge blocked",
        template="red",
        markdown="\n".join(lines),
        priority="high",
        summary=f"进度桥接检查失败：{_text(error, 120) or source}。",
        key_event=True,
    )


def build_progress_notification(
    *,
    todo_id: str,
    goal_id: str,
    status_payload: dict[str, Any] | None,
    quota_payload: dict[str, Any] | None,
    request_text: str | None = None,
) -> ProgressNotification:
    status_payload = status_payload if isinstance(status_payload, dict) else {}
    quota_payload = quota_payload if isinstance(quota_payload, dict) else {}
    queue_item = _attention_item(status_payload, goal_id=goal_id)
    todo_entry = _find_todo_entry(status_payload, todo_id=todo_id) or _find_todo_entry(
        quota_payload,
        todo_id=todo_id,
    )
    if _todo_is_done(todo_entry):
        return _done_notification(
            todo_id=todo_id,
            goal_id=goal_id,
            quota_payload=quota_payload,
            status_payload=status_payload,
            request_text=request_text,
        )
    if _requires_user_action(quota_payload):
        return _user_action_notification(
            todo_id=todo_id,
            goal_id=goal_id,
            quota_payload=quota_payload,
            request_text=request_text,
        )
    if _quota_is_blocked(quota_payload):
        return _blocked_notification(
            todo_id=todo_id,
            goal_id=goal_id,
            quota_payload=quota_payload,
            queue_item=queue_item,
            request_text=request_text,
        )
    if _quota_is_running(quota_payload):
        return _running_notification(
            todo_id=todo_id,
            goal_id=goal_id,
            quota_payload=quota_payload,
            request_text=request_text,
        )
    latest_run = _latest_run(status_payload, goal_id=goal_id)
    if latest_run:
        return _run_progress_notification(
            todo_id=todo_id,
            goal_id=goal_id,
            latest_run=latest_run,
            status_payload=status_payload,
            request_text=request_text,
        )
    return _waiting_notification(
        todo_id=todo_id,
        goal_id=goal_id,
        quota_payload=quota_payload,
        queue_item=queue_item,
        request_text=request_text,
    )


def should_emit_notification(
    notification: ProgressNotification,
    *,
    previous_fingerprint: str | None,
) -> bool:
    return bool(notification.fingerprint and notification.fingerprint != previous_fingerprint)


def _user_action_notification(
    *,
    todo_id: str,
    goal_id: str,
    quota_payload: dict[str, Any],
    request_text: str | None,
) -> ProgressNotification:
    reason = _user_reason(quota_payload) or _first_text(
        quota_payload.get("reason"),
        quota_payload.get("recommended_action"),
    )
    lines = _base_lines(
        heading="User action needed",
        todo_id=todo_id,
        goal_id=goal_id,
        request_text=request_text,
    )
    if reason:
        lines.extend(["", "**Why**", _text(reason, MAX_REASON_CHARS)])
    user_todos = quota_payload.get("user_todo_summary")
    todo_lines = _todo_lines(user_todos)
    if todo_lines:
        lines.extend(["", "**Open user items**", *todo_lines])
    operator_question = _text(quota_payload.get("operator_question"), MAX_ACTION_CHARS)
    gate_prompt = _text(quota_payload.get("gate_prompt"), MAX_ACTION_CHARS)
    if operator_question or gate_prompt:
        lines.extend(["", "**Question**", operator_question or gate_prompt])
    recommended = _text(quota_payload.get("recommended_action"), MAX_ACTION_CHARS)
    if recommended:
        lines.extend(["", "**Recommended action**", recommended])
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="user_action",
        title="LoopX needs input",
        template="red",
        markdown="\n".join(lines),
        priority="high",
        summary=_human_summary(
            current="任务需要你确认后才能继续。",
            next_step=recommended or operator_question or gate_prompt or reason,
        ),
        actions=_gate_actions(todo_id=todo_id, goal_id=goal_id, quota_payload=quota_payload),
        key_event=True,
    )


def _blocked_notification(
    *,
    todo_id: str,
    goal_id: str,
    quota_payload: dict[str, Any],
    queue_item: dict[str, Any],
    request_text: str | None,
) -> ProgressNotification:
    lines = _base_lines(
        heading="Blocked or waiting",
        todo_id=todo_id,
        goal_id=goal_id,
        request_text=request_text,
    )
    parts = _kv_parts(
        {
            "status": quota_payload.get("status") or queue_item.get("status"),
            "state": quota_payload.get("state"),
            "waiting_on": quota_payload.get("waiting_on") or queue_item.get("waiting_on"),
            "decision": quota_payload.get("decision"),
        }
    )
    if parts:
        lines.extend(["", "**State**", " ".join(parts)])
    reason = _first_text(
        quota_payload.get("reason"),
        quota_payload.get("open_todo_notify_reason"),
        quota_payload.get("recommended_action"),
        queue_item.get("recommended_action"),
    )
    if reason:
        lines.extend(["", "**Reason**", _text(reason, MAX_REASON_CHARS)])
    todo_lines = _todo_lines(quota_payload.get("user_todo_summary")) or _todo_lines(
        queue_item.get("user_todos")
    )
    if todo_lines:
        lines.extend(["", "**Open user items**", *todo_lines])
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="blocked",
        title="LoopX is waiting",
        template="orange",
        markdown="\n".join(lines),
        summary=_human_summary(
            current="任务正在等待或被阻塞。",
            risk=reason,
            next_step="处理阻塞后 LoopX 会继续推进。",
        ),
        key_event=True,
    )


def _running_notification(
    *,
    todo_id: str,
    goal_id: str,
    quota_payload: dict[str, Any],
    request_text: str | None,
) -> ProgressNotification:
    lines = _base_lines(
        heading="In progress",
        todo_id=todo_id,
        goal_id=goal_id,
        request_text=request_text,
    )
    interaction = quota_payload.get("interaction_contract")
    agent_channel = interaction.get("agent_channel") if isinstance(interaction, dict) else {}
    heartbeat = quota_payload.get("heartbeat_recommendation")
    heartbeat = heartbeat if isinstance(heartbeat, dict) else {}
    execution = quota_payload.get("execution_obligation")
    execution = execution if isinstance(execution, dict) else {}
    parts = _kv_parts(
        {
            "decision": quota_payload.get("decision"),
            "action": quota_payload.get("effective_action"),
            "mode": heartbeat.get("recommended_mode"),
            "primary": agent_channel.get("primary_action") if isinstance(agent_channel, dict) else None,
        }
    )
    if parts:
        lines.extend(["", "**Current stage**", " ".join(parts)])
    recommended = _text(quota_payload.get("recommended_action"), MAX_ACTION_CHARS)
    if recommended:
        lines.extend(["", "**Working on**", recommended])
    obligation = _first_text(execution.get("contract_obligation"), execution.get("reason"))
    if obligation:
        lines.extend(["", "**Execution contract**", _text(obligation, MAX_REASON_CHARS)])
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="running",
        title="LoopX in progress",
        template="blue",
        markdown="\n".join(lines),
        summary=_human_summary(
            current="任务正在执行。",
            next_step=recommended or obligation,
        ),
    )


def _run_progress_notification(
    *,
    todo_id: str,
    goal_id: str,
    latest_run: dict[str, Any],
    status_payload: dict[str, Any],
    request_text: str | None,
) -> ProgressNotification:
    lines = _base_lines(
        heading="Progress recorded",
        todo_id=todo_id,
        goal_id=goal_id,
        request_text=request_text,
    )
    parts = _kv_parts(
        {
            "run": latest_run.get("generated_at") or latest_run.get("id"),
            "status": latest_run.get("status"),
            "classification": latest_run.get("classification")
            or latest_run.get("event_kind"),
            "result": latest_run.get("result_code"),
        }
    )
    if parts:
        lines.extend(["", "**Latest run**", " ".join(parts)])
    summary = _first_text(
        latest_run.get("summary"),
        latest_run.get("recommended_action"),
        latest_run.get("next_action"),
        latest_run.get("action"),
    )
    if summary:
        lines.extend(["", "**Update**", _text(summary, MAX_ACTION_CHARS)])
    ledger = status_payload.get("event_ledger_summary")
    if isinstance(ledger, dict):
        ledger_parts = _kv_parts(
            {
                "events": ledger.get("event_count"),
                "latest": ledger.get("latest_event_at"),
            }
        )
        if ledger_parts:
            lines.extend(["", "**Ledger**", " ".join(ledger_parts)])
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="progress",
        title="LoopX progress update",
        template="blue",
        markdown="\n".join(lines),
        summary=_human_summary(
            current="任务已有阶段性进展。",
            done=summary,
            next_step=latest_run.get("next_action") or latest_run.get("recommended_action"),
        ),
    )


def _waiting_notification(
    *,
    todo_id: str,
    goal_id: str,
    quota_payload: dict[str, Any],
    queue_item: dict[str, Any],
    request_text: str | None,
) -> ProgressNotification:
    lines = _base_lines(
        heading="Observed",
        todo_id=todo_id,
        goal_id=goal_id,
        request_text=request_text,
    )
    parts = _kv_parts(
        {
            "status": quota_payload.get("status") or queue_item.get("status"),
            "state": quota_payload.get("state"),
            "waiting_on": quota_payload.get("waiting_on") or queue_item.get("waiting_on"),
            "decision": quota_payload.get("decision"),
        }
    )
    if parts:
        lines.extend(["", "**State**", " ".join(parts)])
    reason = _first_text(
        quota_payload.get("reason"),
        quota_payload.get("recommended_action"),
        queue_item.get("recommended_action"),
    )
    if reason:
        lines.extend(["", "**Next**", _text(reason, MAX_ACTION_CHARS)])
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="observed",
        title="LoopX progress observed",
        template="blue",
        markdown="\n".join(lines),
        summary=_human_summary(
            current="任务状态已观测。",
            next_step=reason,
        ),
    )


def _done_notification(
    *,
    todo_id: str,
    goal_id: str,
    quota_payload: dict[str, Any],
    status_payload: dict[str, Any],
    request_text: str | None,
) -> ProgressNotification:
    lines = _base_lines(
        heading="Done",
        todo_id=todo_id,
        goal_id=goal_id,
        request_text=request_text,
    )
    latest_run = _latest_run(status_payload, goal_id=goal_id)
    summary = _first_text(
        quota_payload.get("recommended_action"),
        latest_run.get("summary") if isinstance(latest_run, dict) else None,
        latest_run.get("recommended_action") if isinstance(latest_run, dict) else None,
    )
    if summary:
        lines.extend(["", "**Result**", _text(summary, MAX_ACTION_CHARS)])
    return _notification(
        todo_id=todo_id,
        goal_id=goal_id,
        stage="done",
        title="LoopX done",
        template="green",
        markdown="\n".join(lines),
        done=True,
        summary=_human_summary(current="任务已完成。", done=summary),
        key_event=True,
    )


def _notification(
    *,
    todo_id: str,
    goal_id: str,
    stage: str,
    title: str,
    template: str,
    markdown: str,
    done: bool = False,
    priority: str = "normal",
    summary: str = "",
    actions: tuple[NotificationAction, ...] = (),
    key_event: bool = False,
) -> ProgressNotification:
    compact = compact_markdown(markdown, max_chars=3000)
    compact_summary = compact_plain_text(summary, max_chars=280)
    fingerprint_source = {
        "todo_id": str(todo_id or ""),
        "goal_id": str(goal_id or ""),
        "stage": stage,
        "markdown": compact,
        "summary": compact_summary,
        "actions": [action.to_dict() for action in actions],
        "done": done,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return ProgressNotification(
        todo_id=str(todo_id or ""),
        goal_id=str(goal_id or ""),
        stage=stage,
        title=compact_plain_text(title, max_chars=72),
        template=template,
        markdown=compact,
        fingerprint=fingerprint,
        done=done,
        priority=priority,
        summary=compact_summary,
        actions=actions,
        key_event=key_event,
    )


def _base_lines(
    *,
    heading: str,
    todo_id: str,
    goal_id: str,
    request_text: str | None,
) -> list[str]:
    lines = [
        f"**{heading}**",
        "",
        f"- Todo: `{_safe(todo_id)}`",
        f"- Goal: `{_safe(goal_id)}`",
    ]
    request = _text(request_text, MAX_ACTION_CHARS)
    if request:
        lines.extend(["", "**Request**", request])
    return lines


def _human_summary(
    *,
    current: str,
    done: object = None,
    next_step: object = None,
    risk: object = None,
) -> str:
    parts = [current]
    done_text = _text(done, 140)
    next_text = _text(next_step, 140)
    risk_text = _text(risk, 140)
    if done_text:
        parts.append(f"已完成：{done_text}")
    if next_text:
        parts.append(f"下一步：{next_text}")
    if risk_text:
        parts.append(f"风险/阻塞：{risk_text}")
    return " ".join(parts)


def _gate_actions(
    *,
    todo_id: str,
    goal_id: str,
    quota_payload: dict[str, Any],
) -> tuple[NotificationAction, ...]:
    user_todo_id = _first_user_todo_id(quota_payload.get("user_todo_summary"))
    base_value = {
        "source": "loopx_feishu_progress_bridge",
        "todo_id": str(todo_id or ""),
        "goal_id": str(goal_id or ""),
        "user_todo_id": user_todo_id,
    }
    return (
        NotificationAction(
            action_id="approve_continue",
            label="批准继续",
            style="primary",
            value={**base_value, "decision": "approve_continue"},
        ),
        NotificationAction(
            action_id="reject",
            label="拒绝",
            style="danger",
            value={**base_value, "decision": "reject"},
        ),
        NotificationAction(
            action_id="need_more_info",
            label="需要更多信息",
            value={**base_value, "decision": "need_more_info"},
        ),
        NotificationAction(
            action_id="pause_task",
            label="暂停任务",
            value={**base_value, "decision": "pause_task"},
        ),
        NotificationAction(
            action_id="cancel_task",
            label="取消任务",
            style="danger",
            value={**base_value, "decision": "cancel_task"},
        ),
    )


def _requires_user_action(payload: dict[str, Any]) -> bool:
    if payload.get("requires_user_action") is True:
        return True
    if any(
        payload.get(key) is True
        for key in (
            "notify_user_on_gate",
            "notify_user_on_open_todo",
            "notify_user_on_capability_gate",
        )
    ):
        return True
    interaction = payload.get("interaction_contract")
    if isinstance(interaction, dict):
        user_channel = interaction.get("user_channel")
        if isinstance(user_channel, dict):
            return bool(user_channel.get("action_required"))
    return str(payload.get("state") or "") == "operator_gate"


def _quota_is_blocked(payload: dict[str, Any]) -> bool:
    state = str(payload.get("state") or "")
    decision = str(payload.get("decision") or "")
    status = str(payload.get("status") or "")
    if state in {"blocked_health", "focus_wait", "waiting", "operator_gate", "throttled"}:
        return True
    if decision in {"skip", "workspace_guard", "automation_prompt_upgrade"} and payload.get("should_run") is not True:
        return True
    return "blocked" in status or "failed" in status


def _quota_is_running(payload: dict[str, Any]) -> bool:
    if payload.get("should_run") is True:
        return True
    interaction = payload.get("interaction_contract")
    if isinstance(interaction, dict):
        agent_channel = interaction.get("agent_channel")
        if isinstance(agent_channel, dict) and agent_channel.get("must_attempt") is True:
            return True
    return str(payload.get("decision") or "") in {
        "run",
        "observe",
        "safe_bypass_recovery",
        "self_repair",
        "repair_bridge",
    }


def _user_reason(payload: dict[str, Any]) -> str:
    interaction = payload.get("interaction_contract")
    if isinstance(interaction, dict):
        user_channel = interaction.get("user_channel")
        if isinstance(user_channel, dict):
            reason = _text(user_channel.get("reason"), MAX_REASON_CHARS)
            if reason:
                return reason
    return _first_text(
        payload.get("open_todo_notify_reason"),
        payload.get("gate_prompt"),
        payload.get("operator_question"),
        payload.get("reason"),
    )


def _attention_item(status_payload: dict[str, Any], *, goal_id: str) -> dict[str, Any]:
    queue = status_payload.get("attention_queue")
    if not isinstance(queue, dict):
        return {}
    items = queue.get("items")
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id:
            return item
    return {}


def _latest_run(status_payload: dict[str, Any], *, goal_id: str) -> dict[str, Any]:
    run_history = status_payload.get("run_history")
    if not isinstance(run_history, dict):
        return {}
    goals = run_history.get("goals")
    if not isinstance(goals, list):
        return {}
    for goal in goals:
        if not isinstance(goal, dict) or str(goal.get("goal_id") or "") != goal_id:
            continue
        for key in ("latest_runs", "runs", "items"):
            runs = goal.get(key)
            if isinstance(runs, list):
                for run in runs:
                    if isinstance(run, dict):
                        return run
        if isinstance(goal.get("latest_run"), dict):
            return goal["latest_run"]
    return {}


def _find_todo_entry(payload: Any, *, todo_id: str) -> dict[str, Any]:
    if not todo_id:
        return {}
    if isinstance(payload, dict):
        if any(str(payload.get(key) or "") == todo_id for key in TODO_ID_KEYS):
            return payload
        for value in payload.values():
            found = _find_todo_entry(value, todo_id=todo_id)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_todo_entry(item, todo_id=todo_id)
            if found:
                return found
    return {}


def _todo_is_done(todo: dict[str, Any]) -> bool:
    if not isinstance(todo, dict) or not todo:
        return False
    if todo.get("done") is True or todo.get("closed") is True:
        return True
    status = str(todo.get("status") or todo.get("state") or "").strip().lower()
    return status in TODO_DONE_STATES


def _todo_lines(summary: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(summary, dict):
        return []
    items: list[dict[str, Any]] = []
    for key in (
        "gate_open_items",
        "current_agent_claimed_open_items",
        "first_open_items",
        "items",
        "open_items",
    ):
        raw_items = summary.get(key)
        if isinstance(raw_items, list):
            items.extend(item for item in raw_items if isinstance(item, dict))
    lines: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _first_text(
            item.get("text"),
            item.get("title"),
            item.get("summary"),
            item.get("recommended_action"),
        )
        if not text:
            continue
        todo_id = str(item.get("todo_id") or "").strip()
        prefix = f"`{_safe(todo_id)}` " if todo_id else ""
        line = f"- {prefix}{_text(text, MAX_TODO_CHARS)}"
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
        if len(lines) >= limit:
            break
    if lines:
        return lines
    next_text = _text(summary.get("next"), MAX_TODO_CHARS)
    return [f"- {next_text}"] if next_text else []


def _first_user_todo_id(summary: Any) -> str:
    if not isinstance(summary, dict):
        return ""
    for key in (
        "gate_open_items",
        "current_agent_claimed_open_items",
        "first_open_items",
        "items",
        "open_items",
    ):
        raw_items = summary.get(key)
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if isinstance(item, dict) and item.get("todo_id"):
                return str(item.get("todo_id") or "")
    return ""


def _kv_parts(values: dict[str, Any]) -> list[str]:
    parts = []
    for key, value in values.items():
        text = _text(value, 80)
        if text:
            parts.append(f"{key}=`{_safe(text)}`")
    return parts


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value, MAX_ACTION_CHARS)
        if text:
            return text
    return ""


def _text(value: object, limit: int) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = re.sub(r"\s+", " ", str(value).replace("\r", " ")).strip()
    if not text:
        return ""
    return compact_markdown(text, max_chars=limit, suffix="...")


def _safe(value: object) -> str:
    return str(value or "").replace("`", "'")
