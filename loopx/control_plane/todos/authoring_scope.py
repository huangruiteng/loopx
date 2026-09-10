"""Fact transport for TS authoring scope. Permission and commit stay with callers."""
from typing import Any

from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from .contract import (
    normalize_todo_blocks_agent, normalize_todo_bound_agent,
    normalize_todo_global_gate, normalize_todo_goal_bound,
)


def todo_authoring_facts(source: dict[str, Any]) -> dict[str, Any]:
    facts = {key: source.get(key) for key in ("status", "task_class", "resume_when", "excluded_agents")}
    facts.update({"blocks_agent": normalize_todo_blocks_agent(source.get("blocks_agent")),
        "bound_agent": normalize_todo_bound_agent(source.get("bound_agent")),
        "global_gate": normalize_todo_global_gate(source.get("global_gate")),
        "goal_bound": normalize_todo_goal_bound(source.get("goal_bound"))})
    return facts


def plan_todo_authoring_scope(
    *, command: str, role: str, intent: dict[str, Any],
    registered_agents: list[str], goal_id: str, todo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts = todo_authoring_facts(todo or {})
    try:
        result = effect_runtime_result("todo.authoring_scope.plan", {
            "schema_version": "todo_authoring_scope_request_v0", "command": command,
            "role": role, "todo": facts, "intent": intent,
            "registered_agents": registered_agents, "goal_id": goal_id,
        })
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, dict) or result.get("schema_version") != "todo_authoring_scope_result_v0":
        raise RuntimeError("TypeScript Todo authoring scope result shape mismatch")
    return result


def require_user_todo_task_class(
    *, role: str, task_class: str | None, blocks_agent: str | None = None,
    global_gate: bool | None = None,
) -> None:
    # Early syntactic check used by create and the Markdown import codec.
    plan_todo_authoring_scope(command="class", role=role, intent={
        "task_class": task_class, "blocks_agent": blocks_agent, "global_gate": global_gate,
    }, registered_agents=[], goal_id="")
