from __future__ import annotations

from pathlib import Path

from ...agent_registry import registered_agent_ids_from_registry
from .contract import TODO_TASK_CLASS_USER_ACTION, TODO_TASK_CLASS_USER_GATE


USER_TODO_TASK_CLASSES = {
    TODO_TASK_CLASS_USER_ACTION,
    TODO_TASK_CLASS_USER_GATE,
}


def require_user_todo_task_class(
    *,
    role: str,
    task_class: str | None,
    blocks_agent: str | None = None,
    global_gate: bool | None = None,
) -> None:
    if role != "user":
        if task_class in USER_TODO_TASK_CLASSES:
            raise ValueError(
                "user_action and user_gate task_class are only valid for --role user"
            )
        return
    normalized = str(task_class or "").strip()
    if normalized not in USER_TODO_TASK_CLASSES:
        raise ValueError(
            "user todo requires explicit --task-class user_gate or user_action; "
            "use user_gate for blocking owner/controller decisions and user_action "
            "for non-blocking user-visible todos"
        )
    if normalized == TODO_TASK_CLASS_USER_ACTION and (blocks_agent or global_gate):
        raise ValueError(
            "user_action is non-blocking and cannot set blocks_agent or global_gate; "
            "use --task-class user_gate for blocking decisions"
        )


def require_user_gate_scope(
    *,
    registry_path: Path,
    goal_id: str,
    role: str,
    task_class: str | None,
    blocks_agent: str | None,
    global_gate: bool | None,
) -> None:
    if role != "user" or task_class != TODO_TASK_CLASS_USER_GATE:
        return
    if global_gate and blocks_agent:
        raise ValueError(
            "user_gate cannot set both blocks_agent and global_gate=true; "
            "use blocks_agent for one registered agent or global_gate=true for a goal-wide gate"
        )
    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    if len(registered_agents) <= 1:
        return
    if blocks_agent or global_gate is True:
        return
    raise ValueError(
        "multi-agent user_gate requires an explicit scope: pass --blocks-agent "
        "<registered-agent> (or --agent-id <registered-agent> for authoring) "
        "when the gate blocks one lane, or pass --global-gate when it genuinely "
        "blocks every registered agent"
    )


def require_user_todo_binding(
    *,
    registry_path: Path,
    goal_id: str,
    role: str,
    task_class: str | None,
    bound_agent: str | None,
    goal_bound: bool | None,
    blocks_agent: str | None,
    global_gate: bool | None,
) -> None:
    if role != "user":
        if bound_agent or goal_bound:
            raise ValueError("bound_agent and goal_bound are only valid for user todos")
        return
    if bound_agent and goal_bound:
        raise ValueError(
            "user todo cannot set both bound_agent and goal_bound=true; bind the "
            "continuation to one agent lane or explicitly to the whole goal"
        )
    if task_class == TODO_TASK_CLASS_USER_GATE:
        if global_gate and (bound_agent or goal_bound is not True):
            raise ValueError(
                "a goal-wide user_gate must use goal_bound=true and cannot bind "
                "its continuation to one agent"
            )
        if blocks_agent and (
            goal_bound or not bound_agent or bound_agent != blocks_agent
        ):
            raise ValueError(
                "an agent-scoped user_gate must bind to the same agent named by "
                "blocks_agent"
            )
    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    if len(registered_agents) <= 1:
        return
    if bound_agent or goal_bound is True:
        return
    raise ValueError(
        "multi-agent user todo requires an explicit binding: pass --bound-agent "
        "<registered-agent> (or --agent-id <registered-agent> for authoring), "
        "or pass --goal-bound for an intentionally goal-wide user todo"
    )


def resolve_user_gate_global_gate_update(
    *,
    role: str,
    task_class: str | None,
    existing_global_gate: bool | None,
    global_gate: bool,
    clear_global_gate: bool,
) -> bool | None:
    if global_gate and clear_global_gate:
        raise ValueError(
            "todo update accepts either global_gate or clear_global_gate, not both"
        )
    if (global_gate or clear_global_gate) and not (
        role == "user" and task_class == TODO_TASK_CLASS_USER_GATE
    ):
        field = "clear_global_gate" if clear_global_gate else "global_gate"
        raise ValueError(f"{field} is only valid for user_gate todos")
    if clear_global_gate:
        return None
    return True if global_gate else existing_global_gate
