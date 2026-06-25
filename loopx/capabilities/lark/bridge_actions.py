from __future__ import annotations

from typing import Any


def todo_commands_for_action(
    *,
    action_id: str,
    goal_id: str,
    todo_id: str,
    user_todo_id: str,
    actor_id: str = "",
    decision_scope: dict[str, Any] | None = None,
) -> tuple[list[list[str]], str]:
    actor_note = f"Feishu actor={actor_id or 'unknown'}"
    scope = decision_scope if isinstance(decision_scope, dict) else {}
    scope_note = ""
    if scope:
        scope_note = (
            f" scope={scope.get('kind') or 'unknown'}/"
            f"{scope.get('granularity') or 'unknown'}/"
            f"{scope.get('scope_key') or 'unknown'}"
        )
    audit_note = f"{actor_note}{scope_note}."
    if action_id == "approve_continue" and user_todo_id:
        return [
            [
                "complete",
                "--goal-id",
                goal_id,
                "--role",
                "user",
                "--todo-id",
                user_todo_id,
                "--evidence",
                f"Feishu button approved continuing the LoopX task. {audit_note}",
            ]
        ], "已记录：批准继续。LoopX 下一轮会重新读取 gate 状态。"
    if action_id == "reject" and user_todo_id:
        return [
            [
                "update",
                "--goal-id",
                goal_id,
                "--role",
                "user",
                "--todo-id",
                user_todo_id,
                "--status",
                "blocked",
                "--reason",
                f"Feishu button rejected this gate. {audit_note}",
            ]
        ], "已记录：拒绝该 gate。"
    if action_id == "need_more_info" and user_todo_id:
        return [
            [
                "update",
                "--goal-id",
                goal_id,
                "--role",
                "user",
                "--todo-id",
                user_todo_id,
                "--note",
                f"Feishu button requested more information before deciding. {audit_note}",
            ]
        ], "已记录：需要更多信息。"
    if action_id == "pause_task" and todo_id:
        return [
            [
                "update",
                "--goal-id",
                goal_id,
                "--role",
                "agent",
                "--todo-id",
                todo_id,
                "--status",
                "deferred",
                "--reason",
                f"Feishu button paused this task. {audit_note}",
            ]
        ], "已记录：暂停任务。"
    if action_id == "cancel_task" and todo_id:
        return [
            [
                "update",
                "--goal-id",
                goal_id,
                "--role",
                "agent",
                "--todo-id",
                todo_id,
                "--status",
                "deferred",
                "--reason",
                f"Feishu button cancelled this task. {audit_note}",
            ]
        ], "已记录：取消任务，已把对应 agent todo 置为 deferred。"
    return [], f"未能识别或缺少 todo id，未写回 LoopX：{action_id or 'unknown'}"
