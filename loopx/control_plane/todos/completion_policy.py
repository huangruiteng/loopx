from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from ...agent_registry import (
    load_goal_from_registry,
    primary_agent_id_from_registry,
    registered_agent_ids_from_registry,
    require_registered_agent_id,
    side_agent_handoff_agent_id_from_registry,
)
from .contract import (
    TODO_TASK_CLASS_MONITOR,
    TodoContinuationPolicy,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_continuation_policy,
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
    primary_agent: str | None
    registered_agents: list[str]
    handoff_agent: str | None
    effective_next_claimed_by: str | None
    side_agent_completion: bool
    side_agent_self_merged: bool
    linked_handoff_successor_id: str | None = None


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


def _linked_handoff_successor_id(
    *,
    successors: Iterable[LinkedSuccessor],
    handoff_agent: str | None,
    completing_agent: str | None,
) -> str | None:
    if not handoff_agent or not completing_agent:
        return None
    for successor in successors:
        if successor.role != "agent":
            continue
        if successor.status and successor.status != "open":
            continue
        if successor.claimed_by != handoff_agent:
            continue
        if successor.claimed_by == completing_agent:
            continue
        if successor.todo_id:
            return successor.todo_id
    return None


def _linked_same_agent_non_delivery_successor_id(
    *,
    successors: Iterable[LinkedSuccessor],
    completing_agent: str | None,
) -> str | None:
    if not completing_agent:
        return None
    for successor in successors:
        if successor.role != "agent":
            continue
        if successor.status and successor.status != "open":
            continue
        if successor.claimed_by != completing_agent:
            continue
        if resolve_todo_continuation_policy(
            successor.continuation_policy,
            action_kind=successor.action_kind,
        ) == TodoContinuationPolicy.PRIMARY_REVIEW:
            continue
        if successor.todo_id:
            return successor.todo_id
    return None


def _allows_same_agent_non_delivery_continuation(
    *,
    completion_todo: Mapping[str, Any] | None,
    completing_agent: str | None,
    evidence: str | None,
) -> bool:
    if not completion_todo or not completing_agent or not str(evidence or "").strip():
        return False
    if resolve_todo_continuation_policy(
        completion_todo.get("continuation_policy"),
        action_kind=completion_todo.get("action_kind"),
    ) != TodoContinuationPolicy.SAME_AGENT_NON_DELIVERY:
        return False
    if completion_todo.get("required_write_scopes"):
        return False
    blocked_agent = normalize_todo_blocks_agent(completion_todo.get("blocks_agent"))
    return bool(blocked_agent and blocked_agent != completing_agent)


def _allows_side_agent_monitor_no_followup(
    *,
    completion_todo: Mapping[str, Any] | None,
    evidence: str | None,
    no_followup: bool,
) -> bool:
    if not completion_todo or not no_followup or not str(evidence or "").strip():
        return False
    if str(completion_todo.get("task_class") or "").strip() != TODO_TASK_CLASS_MONITOR:
        return False
    return not bool(completion_todo.get("required_write_scopes"))


def _goal_allows_role_workflow_successors(registry_path: Path, goal_id: str) -> bool:
    goal = load_goal_from_registry(registry_path, goal_id)
    if not isinstance(goal, dict):
        return False
    adapter = goal.get("adapter")
    adapter_kind = adapter.get("kind") if isinstance(adapter, dict) else None
    return (
        str(goal.get("domain") or "").strip() == "auto-research-demo"
        or str(adapter_kind or "").strip() == "auto_research_demo_local_queue"
    )


def _linked_role_workflow_successor_id(
    *,
    successors: Iterable[LinkedSuccessor],
    registered_agents: Iterable[str],
    completing_agent: str | None,
) -> str | None:
    if not completing_agent:
        return None
    registered_agent_set = set(registered_agents)
    if not registered_agent_set:
        return None
    for successor in successors:
        if successor.role != "agent":
            continue
        if successor.status and successor.status != "open":
            continue
        if not successor.todo_id or not successor.claimed_by:
            continue
        if successor.claimed_by == completing_agent:
            continue
        if successor.claimed_by not in registered_agent_set:
            continue
        if resolve_todo_continuation_policy(
            successor.continuation_policy,
            action_kind=successor.action_kind,
        ) == TodoContinuationPolicy.PRIMARY_REVIEW:
            continue
        return successor.todo_id
    return None


def resolve_completion_policy(
    *,
    registry_path: Path,
    goal_id: str,
    claimed_by: str | None = None,
    next_claimed_by: str | None = None,
    next_agent_todo: str | None = None,
    next_action_kind: str | None = None,
    next_continuation_policy: str | None = None,
    side_agent_self_merged: bool = False,
    evidence: str | None = None,
    no_followup: bool = False,
    linked_successors: Iterable[LinkedSuccessor] = (),
    completion_todo: Mapping[str, Any] | None = None,
) -> CompletionPolicy:
    linked_successor_items = list(linked_successors)
    effective_claimed_by = (
        require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=claimed_by,
        )
        if claimed_by
        else None
    )
    primary_agent = primary_agent_id_from_registry(registry_path, goal_id)
    registered_agents = registered_agent_ids_from_registry(registry_path, goal_id)
    configured_handoff_agent = side_agent_handoff_agent_id_from_registry(
        registry_path,
        goal_id,
        agent_id=effective_claimed_by,
    )
    handoff_agent = configured_handoff_agent or primary_agent
    if configured_handoff_agent:
        handoff_agent = require_registered_agent_id(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=configured_handoff_agent,
            field="side_agent_handoff_agent",
        )
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
    if effective_claimed_by and not primary_agent:
        raise ValueError(
            "todo complete with --claimed-by requires coordination.primary_agent "
            "so LoopX can distinguish the primary agent from side agents"
        )

    side_agent_completion = bool(
        effective_claimed_by and primary_agent and effective_claimed_by != primary_agent
    )
    linked_handoff_successor_id = _linked_handoff_successor_id(
        successors=linked_successor_items,
        handoff_agent=handoff_agent,
        completing_agent=effective_claimed_by,
    )
    same_agent_non_delivery_candidate = bool(
        side_agent_completion
        and handoff_agent == effective_claimed_by
        and not next_agent_todo
        and _allows_same_agent_non_delivery_continuation(
            completion_todo=completion_todo,
            completing_agent=effective_claimed_by,
            evidence=evidence,
        )
    )
    if same_agent_non_delivery_candidate and not linked_handoff_successor_id:
        linked_handoff_successor_id = _linked_same_agent_non_delivery_successor_id(
            successors=linked_successor_items,
            completing_agent=effective_claimed_by,
        )
    same_agent_non_delivery_continuation = bool(
        same_agent_non_delivery_candidate and linked_handoff_successor_id
    )
    side_agent_monitor_no_followup = bool(
        side_agent_completion
        and not next_agent_todo
        and _allows_side_agent_monitor_no_followup(
            completion_todo=completion_todo,
            evidence=evidence,
            no_followup=no_followup,
        )
    )
    if (
        side_agent_completion
        and not linked_handoff_successor_id
        and _goal_allows_role_workflow_successors(registry_path, goal_id)
    ):
        linked_handoff_successor_id = _linked_role_workflow_successor_id(
            successors=linked_successor_items,
            registered_agents=registered_agents,
            completing_agent=effective_claimed_by,
        )
    explicit_primary_review_handoff = bool(
        side_agent_completion
        and next_agent_todo
        and not side_agent_self_merged
        and primary_agent
        and effective_next_claimed_by == primary_agent
        and resolve_todo_continuation_policy(
            next_continuation_policy,
            action_kind=next_action_kind,
        ) == TodoContinuationPolicy.PRIMARY_REVIEW
    )

    if side_agent_completion:
        if side_agent_self_merged and not evidence:
            raise ValueError(
                "--side-agent-self-merged requires --evidence with a public-safe "
                "self-merge, commit, and validation summary"
            )
        if (
            not side_agent_self_merged
            and not next_agent_todo
            and not linked_handoff_successor_id
            and not side_agent_monitor_no_followup
        ):
            raise ValueError(
                f"side-agent completion by {effective_claimed_by!r} requires "
                "--next-agent-todo for independent handoff, verification, and merge; "
                "--successor-todo-id pointing at an open agent successor claimed by "
                f"handoff_agent={handoff_agent!r} or an allowed role-workflow agent; "
                "--side-agent-self-merged with --evidence for a small validated self-merge; "
                "or an evidence-backed non-delivery continuous_monitor with --no-follow-up"
            )
        if (
            not side_agent_self_merged
            and handoff_agent == effective_claimed_by
            and not same_agent_non_delivery_continuation
            and not side_agent_monitor_no_followup
            and not explicit_primary_review_handoff
        ):
            raise ValueError(
                "side-agent handoff todo cannot be claimed by the completing side agent; "
                "use --side-agent-self-merged with --evidence for same-agent delivery, "
                "configure side_agent_handoff_agent to another registered agent, or close "
                "an evidence-backed same-agent non-delivery gate with "
                "continuation_policy=same_agent_non_delivery and --successor-todo-id pointing "
                "at an existing same-agent successor"
            )
        if (
            not side_agent_self_merged
            and effective_next_claimed_by
            and effective_next_claimed_by != handoff_agent
            and not explicit_primary_review_handoff
        ):
            raise ValueError(
                f"side-agent completion handoff todo must be claimed_by handoff_agent={handoff_agent!r}"
            )
        if next_agent_todo and not side_agent_self_merged and not effective_next_claimed_by:
            effective_next_claimed_by = handoff_agent
    if effective_next_claimed_by and not next_agent_todo:
        raise ValueError("--next-claimed-by requires --next-agent-todo")

    return CompletionPolicy(
        effective_claimed_by=effective_claimed_by,
        primary_agent=primary_agent,
        registered_agents=registered_agents,
        handoff_agent=handoff_agent,
        effective_next_claimed_by=effective_next_claimed_by,
        side_agent_completion=side_agent_completion,
        side_agent_self_merged=bool(side_agent_completion and side_agent_self_merged),
        linked_handoff_successor_id=linked_handoff_successor_id,
    )
