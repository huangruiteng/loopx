from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Optional

from .contract import (
    TODO_RESUME_KIND_CAPACITY_AVAILABLE,
    TODO_RESUME_KIND_PR_MERGED,
    TODO_RESUME_KIND_TODO_DONE,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_ACTION,
    build_todo_id,
    normalize_required_capabilities,
    normalize_required_write_scopes,
    normalize_explore_result_node_refs,
    normalize_target_capabilities,
    normalize_todo_action_kind,
    normalize_todo_task_repository,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_continuation_policy,
    normalize_todo_decision_outcome,
    normalize_todo_decision_scope,
    normalize_todo_decision_scope_outcomes,
    normalize_todo_excluded_agents,
    normalize_todo_global_gate,
    normalize_todo_goal_bound,
    normalize_todo_id,
    normalize_todo_id_list,
    normalize_todo_no_followup,
    normalize_removed_todo_continuation_policy,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
    todo_done_for_status,
)
from .handoff_gate import build_todo_handoff_gate_states
from .handoff_note import attach_todo_handoff_note
from .projection import (
    todo_claimed_visibility_items as projection_todo_claimed_visibility_items,
    todo_item_is_actionable_open as projection_todo_item_is_actionable_open,
    todo_item_is_deferred as projection_todo_item_is_deferred,
    todo_item_is_due_monitor as projection_todo_item_is_due_monitor,
    todo_item_missing_monitor_schedule as projection_todo_item_missing_monitor_schedule,
    todo_item_task_class as projection_todo_item_task_class,
    todo_item_next_due_at as projection_todo_item_next_due_at,
    todo_item_expires_at as projection_todo_item_expires_at,
    todo_priority_parts as projection_todo_priority_parts,
    todo_priority_rank as projection_todo_priority_rank,
    todo_projection_sort_key as projection_todo_projection_sort_key,
)
from ..work_items.project_asset import build_project_asset_todo_summary
from .user_gate import open_user_gate_todo_items


MAX_STATUS_TODOS_PER_ROLE = 12
MAX_PROJECT_ASSET_TODO_ITEMS = 3
MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS = 8
MAX_TODO_VISIBILITY_LANE_ITEMS = 16
MAX_DEFERRED_TODO_VISIBILITY_ITEMS = 8
MAX_MONITOR_DUE_ITEMS = 1
MAX_DEPENDENCY_BLOCKERS = 4
MAX_COMPLETED_SUCCESSION_WARNING_ITEMS = 5

TODO_ITEM_SCHEMA_VERSION = "todo_item_v0"
TODO_SUCCESSION_WARNING_SCHEMA_VERSION = "todo_succession_warning_v0"
TODO_SOURCE_PROOF_SCHEMA_VERSION = "todo_source_proof_v0"
TODO_CLOSURE_INTENT_SCHEMA_VERSION = "todo_closure_intent_v0"
TODO_TERMINAL_CLOSURE_PROOF_SCHEMA_VERSION = "todo_terminal_closure_proof_v0"
TODO_ARCHIVE_STATE_ACTIVE = "active"
AttentionItemBuilder = Callable[..., dict[str, Any]]
GoalLifecycleFields = Callable[[dict[str, Any], Optional[dict[str, Any]]], dict[str, Any]]
PublicSafeText = Callable[..., Optional[str]]
TodoOpenCount = Callable[[Optional[dict[str, Any]]], int]
FirstOpenTodoText = Callable[[Optional[dict[str, Any]]], Optional[str]]


@dataclass(frozen=True)
class _TodoGroupLanes:
    open_items: list[dict[str, Any]]
    terminal_items: list[dict[str, Any]]
    deferred_items: list[dict[str, Any]]
    done_items: list[dict[str, Any]]
    projected_open_items: list[dict[str, Any]]
    projected_deferred_items: list[dict[str, Any]]
    budgeted_items: list[dict[str, Any]]
    claimed_open_items: list[dict[str, Any]]
    unclaimed_open_items: list[dict[str, Any]]
    executable_items: list[dict[str, Any]]
    resume_blocked_items: list[dict[str, Any]]
    monitor_items: list[dict[str, Any]]
    monitor_due_items: list[dict[str, Any]]
    monitor_schedule_gap_items: list[dict[str, Any]]
    claimed_advancement_items: list[dict[str, Any]]
    claimed_monitor_items: list[dict[str, Any]]
    active_next_action_items: list[dict[str, Any]]
    active_next_action_executable_items: list[dict[str, Any]]
GITHUB_PULL_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<repo>[^/]+/[^/]+)/pull/(?P<number>[0-9]+)(?:\b|/|#|\?)",
    re.IGNORECASE,
)
PR_REF_PATTERN = re.compile(
    r"(?:(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#|#|pr[-_\s]*)"
    r"(?P<number>[0-9]+)",
    re.IGNORECASE,
)
PR_MERGED_EVENT_KINDS = {
    "pr_merge",
    "pr_merged",
    "pull_request_merge",
    "pull_request_merged",
}


def normalize_todo_text(text: str, *, limit: int = 500) -> str:
    compact = " ".join(str(text or "").strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def todo_archive_state(item: dict[str, Any]) -> str:
    value = str(item.get("archive_state") or TODO_ARCHIVE_STATE_ACTIVE).strip()
    return value or TODO_ARCHIVE_STATE_ACTIVE


def active_state_todo_attention_item(
    goal: dict[str, Any],
    fields: dict[str, Any],
    current_run: dict[str, Any] | None,
    *,
    public_safe_compact_text: PublicSafeText,
    first_open_todo_text: FirstOpenTodoText,
    todo_summary_open_count: TodoOpenCount,
    goal_lifecycle_fields: GoalLifecycleFields,
    attention_item: AttentionItemBuilder,
) -> dict[str, Any] | None:
    """Surface active-state todos even when the latest run classification is passive."""

    user_todos = fields.get("user_todos") if isinstance(fields.get("user_todos"), dict) else None
    agent_todos = fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None
    active_next_action = public_safe_compact_text(
        fields.get("active_state_next_action"),
        limit=320,
    )
    user_gate_items = open_user_gate_todo_items(user_todos)
    user_gate_action = public_safe_compact_text(
        user_gate_items[0].get("text") if user_gate_items else None,
        limit=320,
    )
    user_action = public_safe_compact_text(first_open_todo_text(user_todos), limit=320)
    agent_action = public_safe_compact_text(first_open_todo_text(agent_todos), limit=320)
    agent_has_open = bool(agent_action or todo_summary_open_count(agent_todos) > 0)
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)
    goal_id = str(goal.get("id") or "unknown-goal")

    if user_gate_action or user_gate_items:
        return attention_item(
            goal_id=goal_id,
            status="active_state_user_gate",
            waiting_on="controller",
            severity="action",
            recommended_action=(
                user_gate_action
                or active_next_action
                or "resolve the open user_gate todo from the active goal state"
            ),
            source="active_state",
            **lifecycle_fields,
        )

    if user_action or todo_summary_open_count(user_todos) > 0:
        user_items = [
            item
            for item in (user_todos.get("first_open_items") if user_todos else []) or []
            if isinstance(item, dict) and item.get("done") is not True
        ]
        explicit_user_actions_only = bool(user_items) and all(
            str(item.get("task_class") or "").strip()
            and projection_todo_item_task_class(item) == TODO_TASK_CLASS_USER_ACTION
            for item in user_items
        )
        if not explicit_user_actions_only:
            return attention_item(
                goal_id=goal_id,
                status="active_state_user_todo",
                waiting_on="controller",
                severity="action",
                recommended_action=(
                    user_action
                    or active_next_action
                    or "resolve the open user todo from the active goal state"
                ),
                source="active_state",
                **lifecycle_fields,
            )

    if agent_has_open:
        return attention_item(
            goal_id=goal_id,
            status="active_state_agent_todo",
            waiting_on="codex",
            severity="action",
            recommended_action=(
                agent_action
                or active_next_action
                or "run the open agent todo from the active goal state"
            ),
            source="active_state",
            **lifecycle_fields,
        )

    projection_gap = fields.get("state_projection_gap")
    if isinstance(projection_gap, dict):
        return attention_item(
            goal_id=goal_id,
            status="state_projection_gap",
            waiting_on="codex",
            severity="action",
            recommended_action=str(
                projection_gap.get("recommended_action")
                or "expand the active-state Next Action into parseable todos"
            ),
            source="active_state",
            **lifecycle_fields,
        )

    return None


def sync_connected_attention_action_from_todos(
    item: dict[str, Any],
    *,
    first_open_todo_text: FirstOpenTodoText,
) -> None:
    if item.get("status") != "connected_without_run":
        return
    agent_lane_action = (
        item.get("agent_lane_next_action")
        if isinstance(item.get("agent_lane_next_action"), dict)
        else None
    )
    if agent_lane_action is None and isinstance(item.get("project_asset"), dict):
        project_asset = item["project_asset"]
        agent_lane_action = (
            project_asset.get("agent_lane_next_action")
            if isinstance(project_asset.get("agent_lane_next_action"), dict)
            else None
        )
    agent_action = normalize_todo_text(agent_lane_action.get("text")) if agent_lane_action else None
    if not agent_action:
        agent_action = first_open_todo_text(
            item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None
        )
    if not agent_action:
        return
    item["recommended_action"] = agent_action
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        project_asset["next_action"] = agent_action


def todo_priority_parts(text: str) -> tuple[str | None, str]:
    return projection_todo_priority_parts(text)


def structured_todo_item(
    item: dict[str, Any],
    *,
    role: str | None,
    source_section: str | None,
    archive_state: str = "active",
) -> dict[str, Any]:
    text = normalize_todo_text(str(item.get("text") or ""))
    priority, title = todo_priority_parts(text)
    index = item.get("index")
    explicit_status = normalize_todo_status(item.get("status"))
    status = explicit_status or ("done" if item.get("done") else "open")
    done = todo_done_for_status(status) if explicit_status else bool(item.get("done"))
    todo_id = item.get("todo_id") or build_todo_id(
        role=role,
        source_section=source_section,
        index=index,
        text=text,
    )
    normalized = dict(item)
    normalized.update(
        {
            "schema_version": TODO_ITEM_SCHEMA_VERSION,
            "todo_id": todo_id,
            "role": role,
            "status": status,
            "done": done,
            "archive_state": archive_state,
            "source_section": source_section,
            "text": text,
            "task_class": normalize_todo_task_class(
                item.get("task_class"),
                text=text,
                action_kind=item.get("action_kind"),
            ),
        }
    )
    action_kind = normalize_todo_action_kind(item.get("action_kind"))
    if action_kind:
        normalized["action_kind"] = action_kind
    task_repository = normalize_todo_task_repository(item.get("task_repository"))
    if task_repository:
        normalized["task_repository"] = task_repository
    continuation_policy = normalize_todo_continuation_policy(
        item.get("continuation_policy")
    )
    if continuation_policy:
        normalized["continuation_policy"] = continuation_policy
    removed_continuation_policy = normalize_removed_todo_continuation_policy(
        item.get("removed_continuation_policy")
    )
    if removed_continuation_policy:
        normalized["removed_continuation_policy"] = removed_continuation_policy
    required_write_scopes = normalize_required_write_scopes(item.get("required_write_scopes"))
    if required_write_scopes:
        normalized["required_write_scopes"] = required_write_scopes
    required_capabilities = normalize_required_capabilities(item.get("required_capabilities"))
    if required_capabilities:
        normalized["required_capabilities"] = required_capabilities
    target_capabilities = normalize_target_capabilities(item.get("target_capabilities"))
    if target_capabilities:
        normalized["target_capabilities"] = target_capabilities
    explore_result_node_refs = normalize_explore_result_node_refs(
        item.get("explore_result_node_refs")
    )
    if explore_result_node_refs:
        normalized["explore_result_node_refs"] = explore_result_node_refs
    decision_scope = normalize_todo_decision_scope(item.get("decision_scope"))
    if decision_scope:
        normalized["decision_scope"] = decision_scope
    required_decision_scopes = normalize_todo_required_decision_scopes(
        item.get("required_decision_scopes")
    )
    if required_decision_scopes:
        normalized["required_decision_scopes"] = required_decision_scopes
    decision_outcome = normalize_todo_decision_outcome(item.get("decision_outcome"))
    if decision_outcome:
        normalized["decision_outcome"] = decision_outcome
    decision_scope_outcomes = normalize_todo_decision_scope_outcomes(
        item.get("decision_scope_outcomes")
    )
    if decision_scope_outcomes:
        normalized["decision_scope_outcomes"] = decision_scope_outcomes
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    if claimed_by:
        normalized["claimed_by"] = claimed_by
    bound_agent = normalize_todo_bound_agent(item.get("bound_agent"))
    if bound_agent:
        normalized["bound_agent"] = bound_agent
    goal_bound = normalize_todo_goal_bound(item.get("goal_bound"))
    if goal_bound is not None:
        normalized["goal_bound"] = goal_bound
    blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
    if blocks_agent:
        normalized["blocks_agent"] = blocks_agent
    excluded_agents = normalize_todo_excluded_agents(item.get("excluded_agents"))
    if excluded_agents:
        normalized["excluded_agents"] = excluded_agents
    global_gate = normalize_todo_global_gate(item.get("global_gate"))
    if global_gate is not None:
        normalized["global_gate"] = global_gate
    unblocks_todo_id = normalize_todo_id(item.get("unblocks_todo_id"))
    if unblocks_todo_id:
        normalized["unblocks_todo_id"] = unblocks_todo_id
    resume_when = normalize_todo_resume_when(item.get("resume_when"))
    if resume_when:
        normalized["resume_when"] = resume_when
    no_followup = normalize_todo_no_followup(item.get("no_followup"))
    if no_followup is not None:
        normalized["no_followup"] = no_followup
    if priority:
        normalized["priority"] = priority
        normalized["title"] = normalize_todo_text(title)
    return normalized


def compact_todo_item(item: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "index": item.get("index"),
        "done": bool(item.get("done")),
        "text": item.get("text"),
    }
    for key in (
        "schema_version",
        "todo_id",
        "role",
        "status",
        "priority",
        "title",
        "archive_state",
        "source_section",
        "task_class",
        "action_kind",
        "task_repository",
        "continuation_policy",
        "removed_continuation_policy",
        "required_write_scopes",
        "required_capabilities",
        "target_capabilities",
        "explore_result_node_refs",
        "decision_scope",
        "required_decision_scopes",
        "decision_outcome",
        "decision_scope_outcomes",
        "claimed_by",
        "bound_agent",
        "goal_bound",
        "blocks_agent",
        "excluded_agents",
        "global_gate",
        "unblocks_todo_id",
        "resume_when",
        "resume_condition",
        "resume_ready",
        "no_followup",
        "successor_todo_ids",
        "target_key",
        "cadence",
        "next_due_at",
        "expires_at",
        "last_checked_at",
        "result_hash",
        "consecutive_no_change",
        "material_change",
        "max_no_change_before_replan",
        "note",
        "evidence",
        "reason",
        "completed_at",
        "updated_at",
        "superseded_by",
    ):
        if item.get(key) is not None:
            compact[key] = item.get(key)
    attach_todo_handoff_note(compact)
    return compact


def compact_active_next_action_todo_item(item: dict[str, Any]) -> dict[str, Any]:
    compact = compact_todo_item(item)
    for key in (
        "note",
        "evidence",
        "reason",
        "completed_at",
        "updated_at",
        "superseded_by",
    ):
        compact.pop(key, None)
    return compact


def todo_item_task_class(item: dict[str, Any]) -> str:
    return projection_todo_item_task_class(item, task_text_keys=("text",))


def todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    return projection_todo_item_is_actionable_open(item)


def todo_item_next_due_at(item: dict[str, Any]):
    return projection_todo_item_next_due_at(item)


def todo_item_expires_at(item: dict[str, Any]):
    return projection_todo_item_expires_at(item)


def todo_item_is_due_monitor(item: dict[str, Any], *, now=None) -> bool:
    return projection_todo_item_is_due_monitor(item, now=now, task_text_keys=("text",))


def todo_item_missing_monitor_schedule(item: dict[str, Any], *, now=None) -> bool:
    return projection_todo_item_missing_monitor_schedule(item, now=now, task_text_keys=("text",))


def todo_priority_rank(priority: Any) -> int:
    return projection_todo_priority_rank(priority)


def todo_projection_sort_key(item: dict[str, Any]) -> tuple[int, int]:
    return projection_todo_projection_sort_key(item, text_mode="prefix")


def claimed_visibility_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return projection_todo_claimed_visibility_items(items, limit=limit)


def todo_item_is_deferred(item: dict[str, Any]) -> bool:
    return projection_todo_item_is_deferred(item)


def open_todo_items(
    todos: dict[str, Any] | None,
    *,
    limit: int = MAX_PROJECT_ASSET_TODO_ITEMS,
    text_limit: int = 220,
    source_keys: tuple[str, ...] = ("first_open_items", "items"),
) -> list[dict[str, Any]]:
    if not isinstance(todos, dict):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()
    for source_key in source_keys:
        source_items = todos.get(source_key)
        if not isinstance(source_items, list):
            continue
        for item in source_items:
            if not isinstance(item, dict) or item.get("done"):
                continue
            text = normalize_todo_text(str(item.get("text") or ""), limit=text_limit)
            if not text:
                continue
            key = (item.get("index"), text)
            if key in seen:
                continue
            seen.add(key)
            compact = compact_todo_item(item)
            compact["done"] = False
            compact["text"] = text
            result.append(compact)
            if len(result) >= limit:
                return sorted(result, key=todo_projection_sort_key)
    return sorted(result, key=todo_projection_sort_key)


def todo_lane_items(
    todos: dict[str, Any] | None,
    lane: str,
    *,
    limit: int = MAX_STATUS_TODOS_PER_ROLE,
    text_limit: int = 220,
) -> list[dict[str, Any]]:
    return open_todo_items(
        todos,
        limit=limit,
        text_limit=text_limit,
        source_keys=(lane,),
    )


def first_open_todo_text(
    todos: dict[str, Any] | None,
    *,
    item_limit: int = 220,
) -> str | None:
    items = open_todo_items(todos, limit=1, text_limit=item_limit)
    if not items:
        return None
    return str(items[0].get("text") or "") or None


def first_open_todo_item(
    todos: dict[str, Any] | None,
    *,
    item_limit: int = MAX_PROJECT_ASSET_TODO_ITEMS,
    text_limit: int = 220,
) -> dict[str, Any] | None:
    for todo in open_todo_items(todos, limit=item_limit, text_limit=text_limit):
        if not isinstance(todo, dict) or todo.get("done"):
            continue
        return todo
    return None


def project_asset_todo_summary(
    todos: dict[str, Any] | None,
    *,
    role: str | None = None,
    item_limit: int = MAX_PROJECT_ASSET_TODO_ITEMS,
    deferred_item_limit: int = MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
    advancement_task_class: str = TODO_TASK_CLASS_ADVANCEMENT,
) -> dict[str, Any] | None:
    return build_project_asset_todo_summary(
        todos,
        role=role,
        item_limit=item_limit,
        deferred_item_limit=deferred_item_limit,
        advancement_task_class=advancement_task_class,
        open_todo_items=lambda value, **kwargs: open_todo_items(
            value,
            limit=kwargs.get("limit", item_limit),
            text_limit=kwargs.get("text_limit", 220),
            source_keys=kwargs.get("source_keys", ("first_open_items", "items")),
        ),
        compact_todo_item=compact_todo_item,
        todo_lane_items=lambda value, lane, **kwargs: todo_lane_items(
            value,
            lane,
            limit=kwargs.get("limit", MAX_STATUS_TODOS_PER_ROLE),
            text_limit=kwargs.get("text_limit", 220),
        ),
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        todo_item_task_class=todo_item_task_class,
    )


def dependency_blocker_summary(
    items: list[dict[str, Any]],
    *,
    current_goal_id: str,
    limit: int = MAX_DEPENDENCY_BLOCKERS,
) -> dict[str, Any] | None:
    blockers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "")
        if not goal_id or goal_id == current_goal_id:
            continue
        user_todos = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else {}
        for todo in user_todos.get("items") or []:
            if not isinstance(todo, dict) or todo.get("done"):
                continue
            text = normalize_todo_text(str(todo.get("text") or ""), limit=220)
            if not text:
                continue
            blockers.append(
                {
                    "goal_id": goal_id,
                    "status": item.get("status"),
                    "waiting_on": item.get("waiting_on"),
                    "severity": item.get("severity"),
                    "index": todo.get("index"),
                    "text": text,
                    "source": "user_todos",
                }
            )
    if not blockers:
        return None
    return {
        "source": "attention_queue.user_todos",
        "open_count": len(blockers),
        "items": blockers[:limit],
    }


def attach_dependency_blockers(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_DEPENDENCY_BLOCKERS,
) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "")
        if not goal_id:
            continue
        blockers = dependency_blocker_summary(items, current_goal_id=goal_id, limit=limit)
        if blockers:
            item["dependency_blockers"] = blockers


def normalized_pr_ref_parts(value: Any) -> dict[str, Any] | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    pull_url_match = GITHUB_PULL_URL_PATTERN.match(candidate)
    if pull_url_match:
        return {
            "repo": pull_url_match.group("repo"),
            "number": int(pull_url_match.group("number")),
            "normalized": f"{pull_url_match.group('repo')}#{pull_url_match.group('number')}",
        }
    match = PR_REF_PATTERN.match(candidate)
    if not match:
        return None
    repo = match.group("repo")
    number = int(match.group("number"))
    normalized = f"{repo}#{number}" if repo else f"#{number}"
    return {"repo": repo, "number": number, "normalized": normalized}


def rollout_event_pr_refs(event: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    code_refs = event.get("code_refs") if isinstance(event.get("code_refs"), dict) else {}
    for value in (code_refs.get("pr_ref"), event.get("pr_ref")):
        parsed = normalized_pr_ref_parts(value)
        if parsed:
            refs.append(parsed)
    source_refs = event.get("source_refs")
    if isinstance(source_refs, list):
        for source_ref in source_refs:
            if not isinstance(source_ref, dict):
                continue
            if str(source_ref.get("kind") or "").strip().lower() not in {"pull_request", "pr"}:
                continue
            parsed = normalized_pr_ref_parts(source_ref.get("ref"))
            if parsed:
                refs.append(parsed)
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str | None, int]] = set()
    for ref in refs:
        key = (ref.get("repo"), int(ref.get("number") or 0))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique


def _github_pr_repo_from_task_repository(value: Any) -> str | None:
    repository = normalize_todo_task_repository(value)
    prefix = "git:github.com/"
    if not repository or not repository.casefold().startswith(prefix):
        return None
    path = repository[len(prefix) :].strip("/")
    if len(path.split("/")) != 2:
        return None
    return path.casefold()


def pr_merged_condition(
    target: str,
    rollout_events: list[dict[str, Any]],
    *,
    task_repository: Any = None,
) -> dict[str, Any]:
    condition: dict[str, Any] = {
        "pr_number": None,
        "pr_repo": None,
        "source": "rollout_event_log",
    }
    target_ref = normalized_pr_ref_parts(target)
    if not target_ref:
        condition["invalid_target"] = True
        return condition
    condition["pr_number"] = target_ref["number"]
    target_repo = target_ref.get("repo")
    if target_repo:
        condition["pr_repo"] = target_repo
        condition["repository_binding_source"] = "qualified_resume_when"
    else:
        target_repo = _github_pr_repo_from_task_repository(task_repository)
        if target_repo:
            condition["pr_repo"] = target_repo
            condition["repository_binding_source"] = "task_repository"
        else:
            candidate_pr_refs = sorted(
                {
                    str(event_ref.get("normalized") or "")
                    for event in rollout_events
                    if isinstance(event, dict)
                    and str(event.get("event_kind") or "").strip().lower()
                    in PR_MERGED_EVENT_KINDS
                    for event_ref in rollout_event_pr_refs(event)
                    if int(event_ref.get("number") or 0) == int(target_ref["number"])
                    and event_ref.get("repo")
                }
            )
            condition.update(
                {
                    "repository_binding_state": "ambiguous",
                    "repository_binding_reason": (
                        "task_repository_missing"
                        if not normalize_todo_task_repository(task_repository)
                        else "task_repository_not_github"
                    ),
                    "candidate_pr_refs": candidate_pr_refs[:8],
                }
            )
            return condition
    for event in rollout_events:
        if not isinstance(event, dict):
            continue
        if str(event.get("event_kind") or "").strip().lower() not in PR_MERGED_EVENT_KINDS:
            continue
        for event_ref in rollout_event_pr_refs(event):
            if int(event_ref.get("number") or 0) != int(target_ref["number"]):
                continue
            if event_ref.get("repo") != target_repo:
                continue
            condition.update(
                {
                    "satisfied": True,
                    "matched_event_id": event.get("event_id"),
                    "matched_event_kind": event.get("event_kind"),
                    "matched_pr_ref": event_ref.get("normalized"),
                    "matched_event_at": event.get("recorded_at"),
                }
            )
            return condition
    return condition


def apply_resume_conditions(
    items: list[dict[str, Any]],
    *,
    resume_source_items: list[dict[str, Any]] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
) -> None:
    by_id: dict[str, dict[str, Any]] = {}
    for source_item in [*(resume_source_items or []), *items]:
        todo_id = normalize_todo_id(source_item.get("todo_id"))
        if todo_id:
            by_id[todo_id] = source_item
    for item in items:
        resume_when = normalize_todo_resume_when(item.get("resume_when"))
        if not resume_when:
            continue
        condition: dict[str, Any] = {
            "schema_version": "todo_resume_condition_v0",
            "resume_when": resume_when,
            "satisfied": False,
        }
        kind, separator, target = resume_when.partition(":")
        condition["kind"] = kind
        if separator:
            condition["target"] = target
        if kind == TODO_RESUME_KIND_TODO_DONE and target:
            target_item = by_id.get(target)
            condition["target_todo_id"] = target
            condition["target_status"] = (
                normalize_todo_status(target_item.get("status"))
                if isinstance(target_item, dict)
                else None
            )
            if isinstance(target_item, dict):
                condition["target_archive_state"] = target_item.get("archive_state")
                condition["target_source_section"] = target_item.get("source_section")
                condition["target_task_class"] = todo_item_task_class(target_item)
                target_claimed_by = normalize_todo_claimed_by(target_item.get("claimed_by"))
                if target_claimed_by:
                    condition["target_claimed_by"] = target_claimed_by
            condition["satisfied"] = condition["target_status"] == "done"
        elif kind == TODO_RESUME_KIND_PR_MERGED and target:
            condition.update(
                pr_merged_condition(
                    target,
                    rollout_events or [],
                    task_repository=item.get("task_repository"),
                )
            )
        elif kind == TODO_RESUME_KIND_CAPACITY_AVAILABLE and target:
            condition.update(
                {
                    "provider": "runtime_available_capabilities",
                    "provider_required": True,
                    "capability": target,
                }
            )
        else:
            condition["unsupported"] = True
        item["resume_condition"] = condition
        item["resume_ready"] = bool(condition.get("satisfied"))


def active_next_action_todo_ids(value: Any) -> set[str]:
    todo_ids: set[str] = set()
    for match in re.findall(r"\btodo_[A-Za-z0-9_-]+\b", str(value or "")):
        todo_id = normalize_todo_id(match)
        if todo_id:
            todo_ids.add(todo_id)
    return todo_ids


def _normalized_todo_id_list(value: Any) -> list[str]:
    return normalize_todo_id_list(value)


def todo_successor_todo_ids(
    item: dict[str, Any],
    *,
    items: list[dict[str, Any]],
) -> list[str]:
    successor_ids = _normalized_todo_id_list(item.get("successor_todo_ids"))
    superseded_by = normalize_todo_id(item.get("superseded_by"))
    if superseded_by and superseded_by not in successor_ids:
        successor_ids.append(superseded_by)

    source_todo_id = normalize_todo_id(item.get("todo_id"))
    if not source_todo_id:
        return successor_ids

    for candidate in items:
        if not isinstance(candidate, dict):
            continue
        candidate_id = normalize_todo_id(candidate.get("todo_id"))
        if not candidate_id or candidate_id == source_todo_id:
            continue
        if todo_item_task_class(candidate) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        resume_when = normalize_todo_resume_when(candidate.get("resume_when")) or ""
        resume_kind, separator, resume_target = resume_when.partition(":")
        candidate_unblocks = normalize_todo_id(candidate.get("unblocks_todo_id"))
        if candidate_unblocks != source_todo_id and not (
            separator
            and resume_kind == TODO_RESUME_KIND_TODO_DONE
            and normalize_todo_id(resume_target) == source_todo_id
        ):
            continue
        if candidate_id not in successor_ids:
            successor_ids.append(candidate_id)
    return successor_ids


def todo_item_is_succession_tracked_completion(item: dict[str, Any]) -> bool:
    if todo_archive_state(item) != TODO_ARCHIVE_STATE_ACTIVE:
        return False
    if not item.get("done"):
        return False
    if todo_item_is_deferred(item):
        return False
    if todo_item_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
        return False
    return any(
        item.get(key) is not None
        for key in (
            "action_kind",
            "task_repository",
            "continuation_policy",
            "claimed_by",
            "completed_at",
            "updated_at",
            "required_write_scopes",
            "required_capabilities",
            "target_capabilities",
            "explore_result_node_refs",
            "decision_scope",
            "required_decision_scopes",
            "unblocks_todo_id",
            "resume_when",
            "blocks_agent",
            "excluded_agents",
            "global_gate",
        )
    )


def _completed_succession_sort_key(item: dict[str, Any]) -> tuple[str, int]:
    try:
        index = int(item.get("index"))
    except (TypeError, ValueError):
        index = 0
    timestamp = str(item.get("updated_at") or item.get("completed_at") or "")
    return (timestamp, index)


def completed_without_successor_items(
    done_items: list[dict[str, Any]],
    *,
    all_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gap_items: list[dict[str, Any]] = []
    for item in done_items:
        if not todo_item_is_succession_tracked_completion(item):
            continue
        if normalize_todo_no_followup(item.get("no_followup")) is True:
            continue
        if todo_successor_todo_ids(item, items=all_items):
            continue
        compact = compact_todo_item(item)
        for key in ("note", "evidence", "reason"):
            compact.pop(key, None)
        compact["succession_tracked"] = True
        compact["recommended_action"] = (
            "record no_followup=true or add/link a successor todo"
        )
        gap_items.append(compact)
    return sorted(gap_items, key=_completed_succession_sort_key, reverse=True)


def _structured_todo_group_items(
    items: list[dict[str, Any]],
    *,
    source_section: str | None,
    role: str | None,
) -> list[dict[str, Any]]:
    return [
        structured_todo_item(
            item,
            role=role,
            source_section=source_section,
            archive_state=todo_archive_state(item),
        )
        if isinstance(item, dict)
        else item
        for item in items
    ]


def _structured_resume_source_items(
    items: list[dict[str, Any]] | None,
    *,
    source_section: str | None,
) -> list[dict[str, Any]]:
    return [
        structured_todo_item(
            item,
            role=item.get("role") if isinstance(item.get("role"), str) else None,
            source_section=(
                item.get("source_section")
                if isinstance(item.get("source_section"), str)
                else source_section
            ),
            archive_state=(
                str(item.get("archive_state"))
                if item.get("archive_state") is not None
                else TODO_ARCHIVE_STATE_ACTIVE
            ),
        )
        for item in (items or [])
        if isinstance(item, dict)
    ]


def _todo_group_lanes(
    items: list[dict[str, Any]],
    *,
    preferred_todo_ids: set[str] | None,
) -> _TodoGroupLanes:
    open_items = [item for item in items if not item.get("done")]
    terminal_items = [item for item in items if item.get("done")]
    deferred_items = [item for item in terminal_items if todo_item_is_deferred(item)]
    done_items = [item for item in terminal_items if not todo_item_is_deferred(item)]
    projected_open_items = sorted(open_items, key=todo_projection_sort_key)
    projected_deferred_items = sorted(deferred_items, key=todo_projection_sort_key)
    budgeted_items = [
        *projected_open_items,
        *projected_deferred_items,
        *done_items,
    ]
    claimed_open_items = [item for item in projected_open_items if item.get("claimed_by")]
    unclaimed_open_items = [item for item in projected_open_items if not item.get("claimed_by")]
    executable_items = [
        item
        for item in projected_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    resume_blocked_items = [
        item
        for item in projected_open_items
        if normalize_todo_resume_when(item.get("resume_when"))
        if item.get("resume_ready") is False
    ]
    monitor_items = [
        item
        for item in projected_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_due_items = [item for item in monitor_items if todo_item_is_due_monitor(item)]
    monitor_schedule_gap_items = [
        item
        for item in monitor_items
        if todo_item_missing_monitor_schedule(item)
    ]
    claimed_advancement_items = [
        item
        for item in claimed_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    claimed_monitor_items = [
        item
        for item in claimed_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    preferred_ids = {
        todo_id
        for todo_id in (preferred_todo_ids or set())
        if normalize_todo_id(todo_id)
    }
    active_next_action_items = [
        item
        for item in projected_open_items
        if normalize_todo_id(item.get("todo_id")) in preferred_ids
    ]
    active_next_action_executable_items = [
        item
        for item in executable_items
        if normalize_todo_id(item.get("todo_id")) in preferred_ids
    ]
    return _TodoGroupLanes(
        open_items=open_items,
        terminal_items=terminal_items,
        deferred_items=deferred_items,
        done_items=done_items,
        projected_open_items=projected_open_items,
        projected_deferred_items=projected_deferred_items,
        budgeted_items=budgeted_items,
        claimed_open_items=claimed_open_items,
        unclaimed_open_items=unclaimed_open_items,
        executable_items=executable_items,
        resume_blocked_items=resume_blocked_items,
        monitor_items=monitor_items,
        monitor_due_items=monitor_due_items,
        monitor_schedule_gap_items=monitor_schedule_gap_items,
        claimed_advancement_items=claimed_advancement_items,
        claimed_monitor_items=claimed_monitor_items,
        active_next_action_items=active_next_action_items,
        active_next_action_executable_items=active_next_action_executable_items,
    )


def compact_todo_group(
    items: list[dict[str, Any]],
    *,
    source_section: str | None,
    role: str | None = None,
    preferred_todo_ids: set[str] | None = None,
    resume_source_items: list[dict[str, Any]] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
    item_limit: int | None = MAX_STATUS_TODOS_PER_ROLE,
) -> dict[str, Any] | None:
    if not items:
        return None
    items = _structured_todo_group_items(
        items,
        source_section=source_section,
        role=role,
    )
    apply_resume_conditions(
        items,
        resume_source_items=_structured_resume_source_items(
            resume_source_items,
            source_section=source_section,
        ),
        rollout_events=rollout_events,
    )
    lanes = _todo_group_lanes(items, preferred_todo_ids=preferred_todo_ids)
    source_valid = role in {"user", "agent"} and bool(str(source_section or "").strip())
    no_followup_items = [
        item
        for item in items
        if todo_done_for_status(item.get("status"))
        and normalize_todo_no_followup(item.get("no_followup")) is True
    ]
    successor_gap_items = completed_without_successor_items(
        lanes.done_items,
        all_items=items,
    )
    handoff_gates = build_todo_handoff_gate_states(items)
    route_replan_required = any(
        item.get("route_continuation_replan_required") is True
        for item in [*items, *handoff_gates]
    )
    summary = {
        "schema_version": "todo_summary_v0",
        "source_section": source_section,
        "total_count": len(items),
        "open_count": len(lanes.open_items),
        "done_count": len(lanes.terminal_items),
        "deferred_count": len(lanes.deferred_items),
        "first_open_items": [
            compact_todo_item(item) for item in lanes.projected_open_items[:3]
        ],
        "first_executable_items": [
            compact_todo_item(item) for item in lanes.executable_items[:3]
        ],
        "monitor_open_items": [
            compact_todo_item(item) for item in lanes.monitor_items
        ],
        "monitor_due_count": len(lanes.monitor_due_items),
        "monitor_due_items": [
            compact_todo_item(item)
            for item in lanes.monitor_due_items[:MAX_MONITOR_DUE_ITEMS]
        ],
        "monitor_schedule_gap_count": len(lanes.monitor_schedule_gap_items),
        "monitor_schedule_gap_items": [
            compact_todo_item(item)
            for item in lanes.monitor_schedule_gap_items[:MAX_MONITOR_DUE_ITEMS]
        ],
        "unclaimed_priority_open_items": [
            compact_todo_item(item)
            for item in lanes.unclaimed_open_items[:MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS]
        ],
        "claimed_open_items": [
            compact_todo_item(item)
            for item in claimed_visibility_items(
                lanes.claimed_open_items,
                limit=MAX_TODO_VISIBILITY_LANE_ITEMS,
            )
        ],
        "claimed_advancement_open_items": [
            compact_todo_item(item)
            for item in claimed_visibility_items(
                lanes.claimed_advancement_items,
                limit=MAX_TODO_VISIBILITY_LANE_ITEMS,
            )
        ],
        "claimed_monitor_open_items": [
            compact_todo_item(item)
            for item in claimed_visibility_items(
                lanes.claimed_monitor_items,
                limit=MAX_TODO_VISIBILITY_LANE_ITEMS,
            )
        ],
        "backlog_items": [
            compact_todo_item(item)
            for item in lanes.projected_open_items[:MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS]
        ],
        "executable_backlog_items": [
            compact_todo_item(item)
            for item in lanes.executable_items[:MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS]
        ],
        "deferred_items": [
            compact_todo_item(item)
            for item in lanes.projected_deferred_items[:MAX_DEFERRED_TODO_VISIBILITY_ITEMS]
        ],
        "deferred_resume_candidates": [
            compact_todo_item(item)
            for item in lanes.projected_deferred_items
            if item.get("resume_ready") is True
        ][:MAX_DEFERRED_TODO_VISIBILITY_ITEMS],
        "items": lanes.budgeted_items if item_limit is None else lanes.budgeted_items[:item_limit],
    }
    if not lanes.open_items and not lanes.deferred_items:
        summary["source_proof"] = {
            "schema_version": TODO_SOURCE_PROOF_SCHEMA_VERSION,
            "role": role,
            "item_count": len(items),
            "derived": source_valid,
        }
    if (
        source_valid
        and len(lanes.done_items) == len(items)
        and not lanes.monitor_items
        and not successor_gap_items
        and not route_replan_required
    ):
        summary["terminal_closure_proof"] = {
            "schema_version": TODO_TERMINAL_CLOSURE_PROOF_SCHEMA_VERSION,
            "role": role,
            "source_section": source_section,
            "item_count": len(items),
            "all_todos_done": True,
            "monitor_open_count": 0,
            "successor_gap_count": 0,
            "route_replan_count": 0,
            "no_followup_count": len(no_followup_items),
            "derived": True,
        }
    if no_followup_items:
        summary["closure_intent"] = {
            "schema_version": TODO_CLOSURE_INTENT_SCHEMA_VERSION,
            "kind": "no_followup",
            "derived": True,
            "count": len(no_followup_items),
        }
    if lanes.resume_blocked_items:
        summary["resume_blocked_count"] = len(lanes.resume_blocked_items)
        summary["resume_blocked_items"] = [
            compact_todo_item(item)
            for item in lanes.resume_blocked_items[:MAX_DEFERRED_TODO_VISIBILITY_ITEMS]
        ]
    if handoff_gates:
        summary["handoff_gates"] = handoff_gates
    if successor_gap_items:
        compact_gap_items = successor_gap_items[:MAX_COMPLETED_SUCCESSION_WARNING_ITEMS]
        summary["completed_without_successor_count"] = len(successor_gap_items)
        summary["completed_without_successor_items"] = compact_gap_items
        summary["todo_succession_warning"] = {
            "schema_version": TODO_SUCCESSION_WARNING_SCHEMA_VERSION,
            "reason_code": "completed_advancement_without_successor",
            "count": len(successor_gap_items),
            "items": compact_gap_items,
            "recommended_action": (
                "record no_followup=true on completed tracked work, "
                "or add/link a successor todo before closing the slice"
            ),
        }
    if lanes.active_next_action_items:
        summary["active_next_action_items"] = [
            compact_active_next_action_todo_item(item)
            for item in lanes.active_next_action_items
        ]
    if lanes.active_next_action_executable_items:
        summary["active_next_action_executable_items"] = [
            compact_active_next_action_todo_item(item)
            for item in lanes.active_next_action_executable_items
        ]
    if lanes.claimed_open_items:
        summary["claimed_open_count"] = len(lanes.claimed_open_items)
        summary["unclaimed_open_count"] = len(lanes.open_items) - len(lanes.claimed_open_items)
        summary["claimed_advancement_open_count"] = len(lanes.claimed_advancement_items)
        summary["claimed_monitor_open_count"] = len(lanes.claimed_monitor_items)
    return summary
