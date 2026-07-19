from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ...agent_registry import (
    load_goal_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
)
from ..agents.runtime_model import agent_runtime_model_for_goal
from .contract import (
    TodoContinuationPolicy,
    normalize_todo_claimed_by,
    normalize_todo_continuation_policy,
    require_todo_excluded_agents,
    resolve_todo_continuation_policy,
)


@dataclass(frozen=True)
class LinkedSuccessor:
    todo_id: str
    role: str | None = None
    status: str | None = None
    task_class: str | None = None
    action_kind: str | None = None
    continuation_policy: str | None = None
    claimed_by: str | None = None


@dataclass(frozen=True)
class CompletionPolicy:
    effective_claimed_by: str | None
    registered_agents: list[str]
    effective_next_claimed_by: str | None
    effective_next_excluded_agents: list[str]
    self_merged: bool
    linked_successor_id: str | None = None


def linked_successor_from_todo(todo: Mapping[str, Any]) -> LinkedSuccessor:
    return LinkedSuccessor(
        todo_id=str(todo.get("todo_id") or ""),
        role=str(todo.get("role") or "").strip() or None,
        status=str(todo.get("status") or "").strip() or None,
        task_class=str(todo.get("task_class") or "").strip() or None,
        action_kind=str(todo.get("action_kind") or "").strip() or None,
        continuation_policy=normalize_todo_continuation_policy(
            todo.get("continuation_policy")
        ),
        claimed_by=normalize_todo_claimed_by(todo.get("claimed_by")),
    )


def _first_open_agent_successor(
    successors: Iterable[LinkedSuccessor],
) -> str | None:
    return next(
        (
            successor.todo_id
            for successor in successors
            if successor.role == "agent"
            and successor.todo_id
            and (not successor.status or successor.status == "open")
        ),
        None,
    )


def resolve_completion_policy(
    *,
    registry_path: Path,
    goal_id: str,
    claimed_by: str | None = None,
    next_claimed_by: str | None = None,
    next_agent_todo: str | None = None,
    next_action_kind: str | None = None,
    next_continuation_policy: str | None = None,
    next_excluded_agents: Iterable[str] = (),
    self_merged: bool = False,
    evidence: str | None = None,
    no_followup: bool = False,
    linked_successors: Iterable[LinkedSuccessor] = (),
    completion_todo: Mapping[str, Any] | None = None,
) -> CompletionPolicy:
    del no_followup, completion_todo
    effective_claimed_by = (
        require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=claimed_by,
        )
        if claimed_by
        else None
    )
    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    agent_runtime_model_for_goal(load_goal_from_registry(registry_path, goal_id))
    effective_next_claimed_by = (
        require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=next_claimed_by,
            field="next_claimed_by",
        )
        if next_claimed_by
        else None
    )
    effective_next_excluded_agents = sorted(
        require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=agent_id,
            field="next_excluded_agents",
        )
        for agent_id in require_todo_excluded_agents(
            next_excluded_agents,
            field="next_excluded_agents",
        )
    )
    if self_merged and not str(evidence or "").strip():
        raise ValueError(
            "--self-merged requires --evidence with the merge, commit, and "
            "validation summary"
        )
    next_policy = resolve_todo_continuation_policy(
        next_continuation_policy,
        action_kind=next_action_kind,
    )
    if (
        next_agent_todo
        and not effective_next_claimed_by
        and next_policy == TodoContinuationPolicy.SAME_AGENT_NON_DELIVERY
    ):
        effective_next_claimed_by = effective_claimed_by
    if effective_next_claimed_by in effective_next_excluded_agents:
        raise ValueError(
            f"next_claimed_by={effective_next_claimed_by!r} cannot also appear in "
            "next_excluded_agents"
        )
    if effective_next_claimed_by and not next_agent_todo:
        raise ValueError("--next-claimed-by requires --next-agent-todo")
    if effective_next_excluded_agents and not next_agent_todo:
        raise ValueError("--next-excluded-agent requires --next-agent-todo")
    return CompletionPolicy(
        effective_claimed_by=effective_claimed_by,
        registered_agents=registered_agents,
        effective_next_claimed_by=effective_next_claimed_by,
        effective_next_excluded_agents=effective_next_excluded_agents,
        self_merged=bool(self_merged),
        linked_successor_id=_first_open_agent_successor(linked_successors),
    )
