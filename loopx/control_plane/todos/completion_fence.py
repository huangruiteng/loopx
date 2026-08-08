from __future__ import annotations

from typing import Any

from .contract import TODO_STATUS_DONE


def completed_todo_replay(
    *,
    todo: dict[str, Any],
    goal_id: str,
    todo_id: str,
    completion_turn_key: str | None,
    mutation_authority: dict[str, Any],
    state_file: str,
    project: str | None,
    dry_run: bool,
) -> dict[str, Any] | None:
    """Return the terminal-idempotent receipt for an already completed Todo."""

    if str(todo.get("status") or "") != TODO_STATUS_DONE:
        return None
    existing_turn_key = str(todo.get("completion_turn_key") or "")
    if completion_turn_key and completion_turn_key != existing_turn_key:
        raise ValueError(
            "todo is already completed under a different completion_turn_key"
        )
    return {
        "ok": True,
        "dry_run": dry_run,
        "completed": True,
        "idempotent_replay": True,
        "changed": False,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "status": TODO_STATUS_DONE,
        "mutation_authority": mutation_authority,
        "state_file": state_file,
        "project": project,
    }
