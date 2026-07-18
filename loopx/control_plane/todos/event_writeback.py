from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ...event_sourced_state import (
    AppendOnlyStateEventStore,
    TODO_ADDED,
    TODO_CLAIMED,
    TODO_COMPLETED,
    make_state_event,
)
from ...history import load_registry
from ..goals.active_state_event_projection import (
    active_state_event_projection_fields,
    state_event_log_candidates,
)
from ..goals.path_resolution import resolve_goal_local_path
from .active_state_todo_parser import parse_active_state_todos
from .contract import (
    TODO_CONTINUATION_POLICY_VALUES,
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    build_todo_id,
    merge_todo_id_lists,
    normalize_todo_claimed_by,
    normalize_todo_bound_agent,
    normalize_todo_continuation_policy,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    todo_done_for_status,
)
from .text import (
    TODO_PRIORITY_PREFIX_PATTERN,
    inherit_todo_priority,
    normalize_new_todo,
    todo_priority_prefix,
)


TODO_SECTION_HEADINGS = {
    "user": "User Todo / Owner Review Reading Queue",
    "agent": "Agent Todo",
}


def _registry_goal(registry_path: Path, goal_id: str) -> dict[str, Any] | None:
    registry = load_registry(registry_path)
    for goal in registry.get("goals") or []:
        if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
            return goal
    return None


def event_projection_todo_context(
    *,
    registry_path: Path,
    goal_id: str,
    state_path: Path,
    todo_id: str,
    role: str | None,
) -> dict[str, Any] | None:
    goal = _registry_goal(registry_path, goal_id)
    if not goal:
        return None
    fields = active_state_event_projection_fields(
        goal,
        state_path=state_path,
        resolve_goal_local_path=resolve_goal_local_path,
        parse_active_state_todos=parse_active_state_todos,
        item_limit=None,
    )
    if not fields.get("state_event_projection"):
        return None
    normalized_todo_id = normalize_todo_id(todo_id)
    if not normalized_todo_id:
        return None
    roles = [role] if role else ["user", "agent"]
    matched_role: str | None = None
    matched_item: dict[str, Any] | None = None
    for item_role in roles:
        if item_role not in TODO_SECTION_HEADINGS:
            continue
        summary = fields.get(f"{item_role}_todos")
        items = summary.get("items") if isinstance(summary, dict) else []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            if normalize_todo_id(item.get("todo_id")) == normalized_todo_id:
                matched_role = item_role
                matched_item = dict(item)
                break
        if matched_item:
            break
    if not matched_item or matched_role is None:
        return None
    event_log_path = next(
        (
            path
            for path in state_event_log_candidates(
                goal,
                state_path=state_path,
                resolve_goal_local_path=resolve_goal_local_path,
            )
            if path.exists()
        ),
        None,
    )
    if event_log_path is None:
        return None
    return {
        "goal": goal,
        "fields": fields,
        "event_log_path": event_log_path,
        "role": matched_role,
        "item": matched_item,
    }


def _todo_write_event_id(
    *,
    goal_id: str,
    todo_id: str,
    action: str,
    updated_at: str,
    text: str | None = None,
) -> str:
    digest = hashlib.sha1(
        "|".join([goal_id, todo_id, action, updated_at, str(text or "")]).encode("utf-8")
    ).hexdigest()[:16]
    return f"todo-write-{action}-{digest}"


def _append_event_projected_successor(
    *,
    store: AppendOnlyStateEventStore,
    goal_id: str,
    role: str,
    text: str,
    updated_at: str,
    fields: dict[str, Any],
    task_class: str | None,
    action_kind: str | None,
    continuation_policy: str | None,
    claimed_by: str | None,
    dry_run: bool,
    bound_agent: str | None = None,
    goal_bound: bool | None = None,
    blocks_agent: str | None = None,
    excluded_agents: list[str] | None = None,
    unblocks_todo_id: str | None = None,
) -> dict[str, Any]:
    section = TODO_SECTION_HEADINGS[role]
    summary = fields.get(f"{role}_todos")
    items = summary.get("items") if isinstance(summary, dict) else []
    index = len(items if isinstance(items, list) else []) + 1
    todo_text = normalize_new_todo(text)
    todo_id = build_todo_id(
        role=role,
        source_section=section,
        index=index,
        text=todo_text,
    )
    title = re.sub(TODO_PRIORITY_PREFIX_PATTERN, "", todo_text).strip()
    payload: dict[str, Any] = {
        "role": role,
        "priority": todo_priority_prefix(todo_text) or "P2",
        "title": title,
        "planner_order": index,
        "updated_at": updated_at,
    }
    if task_class:
        payload["task_class"] = task_class
    if action_kind:
        payload["action_kind"] = action_kind
    normalized_continuation_policy = normalize_todo_continuation_policy(
        continuation_policy
    )
    if continuation_policy and not normalized_continuation_policy:
        raise ValueError(
            "todo continuation_policy must be one of: "
            + ", ".join(sorted(TODO_CONTINUATION_POLICY_VALUES))
        )
    effective_continuation_policy = normalized_continuation_policy
    if effective_continuation_policy:
        payload["continuation_policy"] = effective_continuation_policy
    if blocks_agent:
        payload["blocks_agent"] = blocks_agent
    if bound_agent:
        payload["bound_agent"] = normalize_todo_bound_agent(bound_agent)
    if goal_bound is not None:
        payload["goal_bound"] = goal_bound
    normalized_excluded_agents = normalize_todo_excluded_agents(excluded_agents)
    if claimed_by in normalized_excluded_agents:
        raise ValueError(
            f"claimed_by={claimed_by!r} cannot also appear in excluded_agents"
        )
    if normalized_excluded_agents:
        payload["excluded_agents"] = normalized_excluded_agents
    if unblocks_todo_id:
        payload["unblocks_todo_id"] = unblocks_todo_id
    added_event = make_state_event(
        event_id=_todo_write_event_id(
            goal_id=goal_id,
            todo_id=todo_id,
            action="add",
            updated_at=updated_at,
            text=todo_text,
        ),
        goal_id=goal_id,
        event_type=TODO_ADDED,
        refs={"todo_id": todo_id},
        payload=payload,
        recorded_at=updated_at,
        producer="loopx.todo.complete",
    )
    claimed_event: dict[str, Any] | None = None
    if claimed_by:
        claimed_event = make_state_event(
            event_id=_todo_write_event_id(
                goal_id=goal_id,
                todo_id=todo_id,
                action="claim",
                updated_at=updated_at,
                text=claimed_by,
            ),
            goal_id=goal_id,
            event_type=TODO_CLAIMED,
            refs={"todo_id": todo_id},
            payload={"claimed_by": claimed_by},
            recorded_at=updated_at,
            producer="loopx.todo.complete",
        )
    if not dry_run:
        store.append(added_event)
        if claimed_event:
            store.append(claimed_event)
    return {
        "added": True,
        "already_exists": False,
        "metadata_updated": False,
        "role": role,
        "section": section,
        "todo": todo_text,
        "todo_id": todo_id,
        "task_class": task_class,
        "action_kind": action_kind,
        "continuation_policy": effective_continuation_policy,
        "claimed_by": claimed_by,
        "bound_agent": bound_agent,
        "goal_bound": goal_bound,
        "blocks_agent": blocks_agent,
        "excluded_agents": normalized_excluded_agents,
        "unblocks_todo_id": unblocks_todo_id,
        "updated_at": updated_at,
        "source": "event_log",
    }


def complete_event_projected_goal_todo(
    *,
    goal_id: str,
    context: dict[str, Any],
    evidence: str | None,
    note: str | None,
    no_followup: bool,
    successor_todo_ids: list[str] | None,
    claimed_by: str | None,
    clear_claim: bool,
    next_agent_todo: str | None,
    next_user_todo: str | None,
    next_claimed_by: str | None,
    next_task_class: str | None,
    next_action_kind: str | None,
    next_continuation_policy: str | None,
    self_merged: bool,
    next_excluded_agents: list[str],
    registered_agents: list[str],
    updated_at: str,
    dry_run: bool,
) -> dict[str, Any]:
    item = dict(context["item"])
    role = str(context["role"])
    todo_id = normalize_todo_id(item.get("todo_id"))
    if not todo_id:
        raise ValueError("event-projected todo has no stable todo_id")
    if clear_claim and item.get("claimed_by"):
        item.pop("claimed_by", None)
    effective_claimed_by = claimed_by or normalize_todo_claimed_by(item.get("claimed_by"))
    store = AppendOnlyStateEventStore(Path(context["event_log_path"]))
    already_done = todo_done_for_status(str(item.get("status") or TODO_STATUS_OPEN))
    next_unblocks_todo_id = todo_id if next_agent_todo else None
    next_user_blocks_agent = effective_claimed_by
    if next_user_todo and len(registered_agents) > 1:
        if not next_user_blocks_agent:
            raise ValueError(
                "multi-agent --next-user-todo requires a completing --claimed-by "
                "agent so the user_gate can be scoped"
            )

    next_results: list[dict[str, Any]] = []
    if next_agent_todo:
        next_results.append(
            _append_event_projected_successor(
                store=store,
                goal_id=goal_id,
                role="agent",
                text=inherit_todo_priority(next_agent_todo, str(item.get("text") or "")),
                updated_at=updated_at,
                fields=context["fields"],
                task_class=next_task_class or "advancement_task",
                action_kind=next_action_kind,
                continuation_policy=next_continuation_policy,
                claimed_by=next_claimed_by,
                excluded_agents=next_excluded_agents,
                unblocks_todo_id=next_unblocks_todo_id,
                dry_run=dry_run,
            )
        )
    if next_user_todo:
        next_results.append(
            _append_event_projected_successor(
                store=store,
                goal_id=goal_id,
                role="user",
                text=inherit_todo_priority(next_user_todo, str(item.get("text") or "")),
                updated_at=updated_at,
                fields=context["fields"],
                task_class="user_gate",
                action_kind="gate",
                continuation_policy=None,
                claimed_by=None,
                bound_agent=next_user_blocks_agent,
                blocks_agent=next_user_blocks_agent,
                unblocks_todo_id=None,
                dry_run=dry_run,
            )
        )

    normalized_successor_todo_ids = merge_todo_id_lists(
        successor_todo_ids,
        [item.get("todo_id") for item in next_results],
    )
    completion_payload: dict[str, Any] = {
        "completed_at": updated_at,
        "updated_at": updated_at,
    }
    if evidence:
        completion_payload["evidence"] = evidence
    if note:
        completion_payload["note"] = note
    if no_followup:
        completion_payload["no_followup"] = "true"
    if normalized_successor_todo_ids:
        completion_payload["successor_todo_ids"] = normalized_successor_todo_ids
    completion_event = make_state_event(
        event_id=_todo_write_event_id(
            goal_id=goal_id,
            todo_id=todo_id,
            action="complete",
            updated_at=updated_at,
            text=evidence or note,
        ),
        goal_id=goal_id,
        event_type=TODO_COMPLETED,
        refs={"todo_id": todo_id},
        payload=completion_payload,
        recorded_at=updated_at,
        producer="loopx.todo.complete",
    )
    if not already_done and not dry_run:
        store.append(completion_event)

    result = {
        "ok": True,
        "dry_run": dry_run,
        "completed": True,
        "goal_id": goal_id,
        "role": role,
        "section": TODO_SECTION_HEADINGS[role],
        "todo": item.get("text") or item.get("title"),
        "todo_id": todo_id,
        "status": TODO_STATUS_DONE,
        "status_changed": not already_done,
        "text_changed": False,
        "metadata_updated": not already_done,
        "changed": (not already_done) or bool(next_results),
        "claimed_by": normalize_todo_claimed_by(effective_claimed_by),
        "task_class": item.get("task_class"),
        "action_kind": item.get("action_kind"),
        "continuation_policy": item.get("continuation_policy"),
        "successor_todo_ids": normalized_successor_todo_ids,
        "next_todos": next_results,
        "state_file": str(context.get("state_file") or ""),
        "project": str(context.get("project") or "") or None,
        "updated_at": updated_at,
        "source": "event_log",
    }
    result["self_merged"] = self_merged
    return result
