from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any


def recovery_cli_actions(
    payload: Mapping[str, Any],
    *,
    command_prefix: str,
    goal_id: str,
    lifecycle_actor_args: str,
    typed_quota_guard: str,
    turn_instance_id: str | None,
) -> list[str]:
    """Render the bounded typed closeout repair outside the main dispatcher."""

    recovery = payload.get("unsettled_host_turn_recovery")
    recovery = recovery if isinstance(recovery, Mapping) else {}
    prior_todo_id = str(recovery.get("binding_id") or "<prior-todo-id>")
    current_turn_arg = (
        f" --turn-instance-id {shlex.quote(turn_instance_id)}"
        if turn_instance_id
        else " --turn-instance-id <current-turn-id>"
    )
    return [
        (
            "inspect unsettled_host_turn_recovery and supply a typed host "
            "observation; never infer external state from Todo prose"
        ),
        (
            f"{command_prefix} todo update --goal-id {goal_id} --todo-id "
            f"{shlex.quote(prior_todo_id)}{lifecycle_actor_args} --status open "
            "--resume-when monitor_changed:<monitor-todo-id> "
            "--successor-todo-id <independent-successor-todo-id>"
        ),
        (
            f"{typed_quota_guard}{current_turn_arg} "
            "--todo-id <independent-successor-todo-id>"
        ),
    ]
