from __future__ import annotations

import re
from typing import Any

from .agent_scope_frontier import (
    AGENT_LANE_FRONTIER_HINT_SCHEMA_VERSION,
    AgentLaneFrontierHintDecision,
    AgentScopeFrontierAction,
    agent_scope_frontier_action as _agent_scope_frontier_action,
    build_agent_scope_frontier_payload,
)
from ..todos.decision_scope import todo_gate_relation, todo_gate_relation_blocks_agent
from ..work_items.work_lane import (
    work_lane_contract_is_due_monitor_attempt,
    work_lane_contract_requires_current_agent_attempt,
)
from ..todos.contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_blocks_agent,
    normalize_todo_bound_agent,
    normalize_todo_claimed_by,
    normalize_todo_excluded_agents,
    normalize_todo_global_gate,
    normalize_todo_id,
    normalize_todo_status,
    normalize_todo_task_class,
)
from ..todos.handoff_gate import HandoffGateState
from ..todos.deferred_resume import todo_summary_blocked_successor_items
from ..todos.projection import (
    todo_item_claimed_by_agent_or_unclaimed,
    todo_item_excludes_agent,
    todo_item_is_actionable_open,
    todo_item_is_deferred,
    todo_item_task_class,
    todo_projection_sort_key,
)
from ..todos.summary_item import compact_todo_summary_item
from ..todos.user_gate import (
    open_todo_count as _open_todo_count,
    open_user_gate_todo_items as _open_user_gate_todo_items,
)

_ACTION_SCOPE_STOPWORDS = {
    "a",
    "an",
    "and",
    "approve",
    "approved",
    "approval",
    "before",
    "blocked",
    "continue",
    "decide",
    "decision",
    "for",
    "from",
    "gate",
    "gated",
    "goal",
    "harness",
    "internal",
    "material",
    "next",
    "open",
    "owner",
    "p0",
    "p1",
    "p2",
    "p3",
    "provide",
    "read",
    "registered",
    "safe",
    "should",
    "sync",
    "the",
    "todo",
    "until",
    "user",
    "whether",
    "with",
}


def _agent_identity_has_scoped_lane(agent_identity: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(agent_identity, dict)
        and normalize_todo_claimed_by(agent_identity.get("agent_id"))
    )


def _todo_task_class(item: dict[str, Any]) -> str:
    return todo_item_task_class(item)


def _todo_projection_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    return todo_projection_sort_key(item)


def _monitor_debt_projection_sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
    priority, *remainder = _todo_projection_sort_key(item)
    advancement_first = 0 if _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT else 1
    return (priority, advancement_first, *remainder)


def _todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    return todo_item_is_actionable_open(item)


def agent_scope_item_claimed_by(item: dict[str, Any]) -> str | None:
    return normalize_todo_claimed_by(item.get("claimed_by"))


def agent_scope_item_blocks_agent(item: dict[str, Any]) -> str | None:
    return normalize_todo_blocks_agent(item.get("blocks_agent"))


def agent_scope_item_bound_agent(item: dict[str, Any]) -> str | None:
    return normalize_todo_bound_agent(item.get("bound_agent"))


def agent_scope_item_excluded_agents(item: dict[str, Any]) -> list[str]:
    return normalize_todo_excluded_agents(item.get("excluded_agents"))


def agent_scope_item_claimed_by_agent_or_unclaimed(
    item: dict[str, Any],
    *,
    agent_id: str | None,
) -> bool:
    return todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)


def agent_scope_item_matches_agent_or_unclaimed(
    item: dict[str, Any],
    *,
    agent_id: str | None,
) -> bool:
    normalized_agent_id = normalize_todo_claimed_by(agent_id)
    if not normalized_agent_id:
        return True
    if todo_item_excludes_agent(item, agent_id=normalized_agent_id):
        return False
    return agent_scope_item_claimed_by_agent_or_unclaimed(
        item,
        agent_id=normalized_agent_id,
    )


def agent_scope_count_advancement_items(
    items: Any,
    *,
    claimed_by: str | None = None,
) -> int:
    if not isinstance(items, list):
        return 0
    normalized_claimed_by = (
        "__unclaimed__"
        if claimed_by == "__unclaimed__"
        else normalize_todo_claimed_by(claimed_by)
        if claimed_by is not None
        else None
    )
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        item_claimed_by = agent_scope_item_claimed_by(item)
        if normalized_claimed_by == "__unclaimed__":
            if item_claimed_by:
                continue
        elif normalized_claimed_by is not None and item_claimed_by != normalized_claimed_by:
            continue
        count += 1
    return count


def _protocol_action_text(value: Any, *, limit: int = 220) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _action_scope_tokens_from_text(text: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            text.lower().replace("_", " ").replace("-", " "),
        )
        if len(token) > 1 and token not in _ACTION_SCOPE_STOPWORDS
    }


def _todo_action_kind_tokens(item: dict[str, Any]) -> set[str]:
    return _action_scope_tokens_from_text(str(item.get("action_kind") or ""))


def _todo_action_scope_tokens(item: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value or "")
        for value in (item.get("action_kind"), item.get("title"), item.get("text"))
        if str(value or "").strip()
    )
    return _action_scope_tokens_from_text(text)


def _todo_gate_relation(gate: dict[str, Any], agent_item: dict[str, Any]) -> dict[str, Any] | None:
    return todo_gate_relation(gate, agent_item)


def _user_gate_blocks_agent_item(gate: dict[str, Any], agent_item: dict[str, Any]) -> bool:
    if normalize_todo_global_gate(gate.get("global_gate")):
        return True
    relation = _todo_gate_relation(gate, agent_item)
    if relation:
        return todo_gate_relation_blocks_agent(relation)

    gate_action_tokens = _todo_action_kind_tokens(gate)
    agent_action_tokens = _todo_action_kind_tokens(agent_item)
    if gate_action_tokens and agent_action_tokens:
        return bool(gate_action_tokens & agent_action_tokens)
    if agent_action_tokens:
        return False

    gate_tokens = _todo_action_scope_tokens(gate)
    agent_tokens = _todo_action_scope_tokens(agent_item)
    if not gate_tokens or not agent_tokens:
        return False
    if gate_action_tokens:
        return len(gate_action_tokens & agent_tokens) >= 2
    return len(gate_tokens & agent_tokens) >= 3


def _todo_item_claimed_by_agent_or_unclaimed(item: dict[str, Any], *, agent_id: str) -> bool:
    return agent_scope_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)


def _agent_scope_selectable_todo_item(
    item: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
) -> bool:
    if not isinstance(agent_identity, dict):
        return True
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return True
    if todo_item_excludes_agent(item, agent_id=agent_id):
        return False
    return _todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)


def _agent_scope_filter_user_gate_items(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(agent_identity, dict):
        return open_items, [], None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return open_items, [], None

    current_agent_items: list[dict[str, Any]] = []
    other_agent_scoped_items: list[dict[str, Any]] = []
    for item in open_items:
        if normalize_todo_global_gate(item.get("global_gate")):
            current_agent_items.append(item)
            continue
        blocks_agent = agent_scope_item_blocks_agent(item)
        if blocks_agent:
            if blocks_agent != agent_id:
                other_agent_scoped_items.append(item)
                continue
            current_agent_items.append(item)
            continue
        claimed_by = agent_scope_item_claimed_by(item)
        if claimed_by and claimed_by != agent_id:
            other_agent_scoped_items.append(item)
            continue
        current_agent_items.append(item)
    if not other_agent_scoped_items:
        return open_items, [], None

    return (
        current_agent_items,
        other_agent_scoped_items,
        {
            "schema_version": "agent_scoped_user_gate_filter_v0",
            "agent_id": agent_id,
            "policy": (
                "user todos scoped to another agent by blocks_agent or claimed_by "
                "remain visible but do not block this agent's quota lane"
            ),
            "current_agent_blocking_open_count": len(current_agent_items),
            "other_agent_scoped_open_count": len(other_agent_scoped_items),
        },
    )


def _agent_scope_filter_user_action_items(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(agent_identity, dict):
        return open_items, [], None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return open_items, [], None

    current_agent_items: list[dict[str, Any]] = []
    other_agent_items: list[dict[str, Any]] = []
    for item in open_items:
        # claimed_by is a read-only compatibility fallback for user actions
        # written before bound_agent became a first-class routing relation.
        bound_agent = agent_scope_item_bound_agent(item) or agent_scope_item_claimed_by(item)
        if bound_agent and bound_agent != agent_id:
            other_agent_items.append(item)
            continue
        current_agent_items.append(item)
    if not other_agent_items:
        return open_items, [], None
    return (
        current_agent_items,
        other_agent_items,
        {
            "schema_version": "agent_scoped_user_action_filter_v0",
            "agent_id": agent_id,
            "policy": (
                "user actions bound to another agent remain diagnostic-only and "
                "must not enter this agent's reminder channel"
            ),
            "current_agent_user_action_open_count": len(current_agent_items),
            "other_agent_bound_user_action_open_count": len(other_agent_items),
        },
    )


def _scoped_user_gate_fallback(
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    *,
    capability_gate: dict[str, Any] | None = None,
    allow_unrelated_gate: bool = False,
    monitor_debt_backoff_active: bool = False,
) -> dict[str, Any] | None:
    gates = _open_user_gate_todo_items(user_todo_summary)
    if not gates or not isinstance(agent_todo_summary, dict):
        return None

    due_monitor_candidates = (
        agent_todo_summary.get("monitor_due_items")
        if isinstance(agent_todo_summary.get("monitor_due_items"), list)
        else []
    )
    ready_deferred_candidates = (
        agent_todo_summary.get("deferred_resume_candidates")
        if isinstance(agent_todo_summary.get("deferred_resume_candidates"), list)
        else []
    )

    # An empty capability projection is authoritative for advancement work.
    # Due monitors are projected separately from advancement candidates and are
    # already current-agent scoped, due, and capability-runnable here.
    capability_candidates = (
        capability_gate.get("runnable_candidates")
        if isinstance(capability_gate, dict)
        else None
    )
    if isinstance(capability_candidates, list):
        executable_items = [
            *due_monitor_candidates,
            *capability_candidates,
            *ready_deferred_candidates,
        ]
    else:
        advancement_items = (
            agent_todo_summary.get("executable_backlog_items")
            if isinstance(agent_todo_summary.get("executable_backlog_items"), list)
            else agent_todo_summary.get("first_executable_items")
            if isinstance(agent_todo_summary.get("first_executable_items"), list)
            else []
        )
        executable_items = [
            *due_monitor_candidates,
            *advancement_items,
            *ready_deferred_candidates,
        ]
    executable_items = [item for item in executable_items if isinstance(item, dict)]
    deduped_executable_items: list[dict[str, Any]] = []
    seen_todo_ids: set[str] = set()
    for item in executable_items:
        todo_id = normalize_todo_id(item.get("todo_id"))
        if todo_id and todo_id in seen_todo_ids:
            continue
        if todo_id:
            seen_todo_ids.add(todo_id)
        deduped_executable_items.append(item)
    executable_items = sorted(
        deduped_executable_items,
        key=(
            _monitor_debt_projection_sort_key
            if monitor_debt_backoff_active
            else _todo_projection_sort_key
        ),
    )
    claim_scope = (
        agent_todo_summary.get("claim_scope")
        if isinstance(agent_todo_summary.get("claim_scope"), dict)
        else None
    )
    if claim_scope:
        agent_id = normalize_todo_claimed_by(claim_scope.get("agent_id"))
        executable_items = [
            item
            for item in executable_items
            if agent_scope_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
        ]
    blocked_items: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    blocking_gate: dict[str, Any] | None = None
    for item in executable_items:
        matching_gate = next(
            (gate for gate in gates if _user_gate_blocks_agent_item(gate, item)),
            None,
        )
        if matching_gate:
            blocking_gate = blocking_gate or matching_gate
            text = str(item.get("text") or "").strip()
            blocked_item = compact_todo_summary_item(item, text=text)
            relation = _todo_gate_relation(matching_gate, item)
            if relation:
                blocked_item["todo_gate_relation"] = relation
            blocked_items.append(blocked_item)
            continue
        if selected is None:
            selected = item

    if selected is None:
        return None
    if not blocking_gate and not allow_unrelated_gate:
        return None

    selected_text = str(selected.get("text") or "").strip()
    gate_to_surface = blocking_gate or gates[0]
    selected_item = compact_todo_summary_item(selected, text=selected_text)
    selected_is_deferred_replan = (
        todo_item_is_deferred(selected) and selected.get("resume_ready") is True
    )
    if selected_is_deferred_replan:
        selected_item["fallback_kind"] = "deferred_successor_replan"
    selected_relation = _todo_gate_relation(gate_to_surface, selected)
    if selected_relation:
        selected_item["todo_gate_relation"] = selected_relation
    gate_text = str(gate_to_surface.get("text") or "").strip()
    reason = (
        "an open user_gate blocks a scoped agent todo, but a non-dependent "
        "executable fallback remains available"
        if blocking_gate
        else (
            "an open user_gate blocks a different action scope, but the ready "
            "deferred successor can be replanned independently"
            if selected_is_deferred_replan
            else "an open user_gate blocks a different action scope, but the selected "
            "executable agent todo is non-dependent and safe to advance"
        )
    )
    return {
        "schema_version": "scoped_user_gate_fallback_v0",
        "kind": "scoped_user_gate_fallback",
        "notify_user": True,
        "requires_user_action": True,
        "reason": reason,
        "blocked_user_gate": compact_todo_summary_item(gate_to_surface, text=gate_text),
        "blocked_agent_items": blocked_items[:3],
        "selected_executable": selected_item,
        "recommended_action": (
            "Notify the user about the scoped gate; then reopen, supersede, or "
            "record a no-follow-up rationale for the selected ready deferred "
            "successor, spending only after validated writeback."
            if selected_is_deferred_replan
            else "Notify the user about the scoped gate; then execute the selected "
            "non-gated fallback and spend only after validated writeback."
        ),
    }


def _first_executable_todo_text(agent_todo_summary: dict[str, Any] | None) -> str | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    items = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        text = _protocol_action_text(item.get("text"), limit=320)
        if text:
            return text
    return None


def _first_monitor_todo_text(agent_todo_summary: dict[str, Any] | None) -> str | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    for key in ("monitor_due_items", "monitor_open_items"):
        items = agent_todo_summary.get(key) if isinstance(agent_todo_summary.get(key), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not _todo_item_is_actionable_open(item):
                continue
            if _todo_task_class(item) != TODO_TASK_CLASS_MONITOR:
                continue
            text = _protocol_action_text(item.get("text"), limit=320)
            if text:
                return text
    return None


def _agent_scoped_user_todo_override(
    *,
    state: str,
    item: dict[str, Any],
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if state != "operator_gate":
        return None
    if not isinstance(agent_identity, dict):
        return None
    if not isinstance(user_todo_summary, dict):
        return None
    if _open_todo_count(user_todo_summary) > 0:
        return None
    other_gate_count = _open_todo_count(
        {"open_count": user_todo_summary.get("other_agent_scoped_open_count")}
    )
    if item.get("operator_question") or item.get("missing_gates"):
        return None
    selected_action = _first_executable_todo_text(agent_todo_summary)
    if not selected_action:
        selected_action = _first_monitor_todo_text(agent_todo_summary)
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if other_gate_count > 0:
        if not selected_action:
            return None
        return {
            "schema_version": "agent_scoped_user_gate_override_v0",
            "kind": "agent_scoped_user_gate_override",
            "agent_id": agent_id,
            "from_state": "operator_gate",
            "to_state": "eligible",
            "other_agent_scoped_open_count": other_gate_count,
            "selected_action": selected_action,
            "reason": (
                "the open user gate is scoped to another agent via blocks_agent or "
                "claimed_by; this agent still has an executable in-scope todo"
            ),
        }
    other_action_count = _open_todo_count(
        {
            "open_count": user_todo_summary.get(
                "other_agent_bound_user_action_open_count"
            )
        }
    )
    if other_action_count <= 0:
        return None
    result: dict[str, Any] = {
        "schema_version": "agent_scoped_user_action_override_v0",
        "kind": "agent_scoped_user_action_override",
        "agent_id": agent_id,
        "from_state": "operator_gate",
        "to_state": "eligible" if selected_action else "waiting",
        "other_agent_bound_user_action_open_count": other_action_count,
        "reason": (
            "the only open user actions are bound to another agent; they remain "
            "diagnostic-only for this lane and cannot create an operator gate"
        ),
        "quota_patch": {
            "safe_bypass_allowed": False,
            "safe_bypass_kind": None,
            "blocked_action_scope": None,
        },
        "item_patch": {
            "status": "active_state_agent_todo" if selected_action else "agent_scope_wait",
            "waiting_on": "codex" if selected_action else "agent_scope",
            "recommended_action": (
                selected_action or "wait for work or a user action bound to this agent"
            ),
        },
    }
    if selected_action:
        result["selected_action"] = selected_action
    return result


def _count_advancement_items(items: Any, *, claimed_by: str | None = None) -> int:
    return agent_scope_count_advancement_items(items, claimed_by=claimed_by)


def _selectable_unclaimed_advancement_count(
    agent_todo_summary: dict[str, Any],
) -> int:
    executable_items = agent_todo_summary.get("executable_backlog_items")
    source_items = (
        executable_items
        if isinstance(executable_items, list)
        else agent_todo_summary.get("unclaimed_priority_open_items")
    )
    return _count_advancement_items(source_items, claimed_by="__unclaimed__")


def _first_compact_todo_id(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        todo_id = normalize_todo_id(item.get("todo_id"))
        if todo_id:
            return todo_id
    return None


def _agent_lane_frontier_hint(
    *,
    goal_id: str,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_lane_next_action: dict[str, Any] | None,
    agent_scope_frontier: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not _agent_identity_has_scoped_lane(agent_identity):
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return None

    def build_hint(
        decision: AgentLaneFrontierHintDecision,
        *,
        source: str,
        reason_code: str,
        target_todo_id: str | None = None,
        quiet_noop_allowed: bool,
        next_cli_action: str | None = None,
    ) -> dict[str, Any]:
        hint: dict[str, Any] = {
            "schema_version": AGENT_LANE_FRONTIER_HINT_SCHEMA_VERSION,
            "decision": decision.value,
            "agent_id": agent_id,
            "agent_model": "peer_v1",
            "source": source,
            "reason_code": reason_code,
            "quiet_noop_allowed": quiet_noop_allowed,
            "uses_structured_frontier": True,
        }
        if target_todo_id:
            hint["target_todo_id"] = target_todo_id
        if next_cli_action:
            hint["next_cli_action"] = next_cli_action
        return hint

    if isinstance(agent_lane_next_action, dict):
        selected_by = str(agent_lane_next_action.get("selected_by") or "")
        claim_required = agent_lane_next_action.get("claim_required_before_work") is True
        target_todo_id = normalize_todo_id(agent_lane_next_action.get("todo_id"))
        if selected_by == "unclaimed_todo" or claim_required:
            action = None
            if target_todo_id:
                action = (
                    f"loopx todo claim --goal-id {goal_id} --todo-id {target_todo_id} "
                    f"--claimed-by {agent_id} --agent-id {agent_id}"
                )
            return build_hint(
                AgentLaneFrontierHintDecision.CLAIM_UNOWNED_IN_SCOPE,
                source="agent_lane_next_action",
                reason_code="unclaimed_advancement_selected",
                target_todo_id=target_todo_id,
                quiet_noop_allowed=False,
                next_cli_action=action,
            )

    if work_lane_contract_is_due_monitor_attempt(work_lane_contract):
        return None
    if work_lane_contract_requires_current_agent_attempt(work_lane_contract):
        return None

    frontier = agent_scope_frontier if isinstance(agent_scope_frontier, dict) else {}
    frontier_action = _agent_scope_frontier_action(frontier.get("action"))
    if frontier_action == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED:
        cleared_todo_id = _first_compact_todo_id(
            frontier.get("cleared_without_successor_handoff_gates")
        )
        if cleared_todo_id:
            return build_hint(
                AgentLaneFrontierHintDecision.RECORD_NO_FOLLOWUP,
                source="agent_scope_frontier",
                reason_code="cleared_handoff_without_successor",
                target_todo_id=cleared_todo_id,
                quiet_noop_allowed=False,
                next_cli_action=(
                    f"loopx todo complete --goal-id {goal_id} --todo-id {cleared_todo_id} "
                    f"--agent-id {agent_id} --no-follow-up "
                    "--evidence '<public-safe rationale>'"
                ),
            )
        monitor_candidates = (
            frontier.get("monitor_blocked_resume_candidates")
            if isinstance(frontier.get("monitor_blocked_resume_candidates"), list)
            else []
        )
        monitor_candidate = (
            monitor_candidates[0]
            if monitor_candidates and isinstance(monitor_candidates[0], dict)
            else {}
        )
        monitor_blocker_id = normalize_todo_id(
            monitor_candidate.get("blocking_monitor_todo_id")
        )
        if monitor_candidate:
            target_todo_id = normalize_todo_id(monitor_candidate.get("todo_id"))
            return build_hint(
                AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
                source="agent_scope_frontier",
                reason_code="resume_blocked_by_open_monitor",
                target_todo_id=target_todo_id or monitor_blocker_id,
                quiet_noop_allowed=False,
                next_cli_action=(
                    f"loopx todo complete --goal-id {goal_id} --todo-id {monitor_blocker_id} "
                    f"--agent-id {agent_id} --evidence '<validated gate evidence>'"
                    if monitor_blocker_id
                    else None
                ),
            )
        deferred_todo_id = _first_compact_todo_id(frontier.get("deferred_resume_candidates"))
        route_todo_id = _first_compact_todo_id(
            frontier.get("route_continuation_replan_candidates")
        )
        route_candidates = (
            frontier.get("route_continuation_replan_candidates")
            if isinstance(frontier.get("route_continuation_replan_candidates"), list)
            else []
        )
        route_candidate = (
            route_candidates[0]
            if route_candidates and isinstance(route_candidates[0], dict)
            else {}
        )
        route_target = (
            route_todo_id
            or normalize_todo_id(route_candidate.get("route_id"))
            or normalize_todo_id(route_candidate.get("route_key"))
        )
        if route_candidate:
            return build_hint(
                AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
                source="agent_scope_frontier",
                reason_code="route_continuation_replan_required",
                target_todo_id=route_target,
                quiet_noop_allowed=False,
                next_cli_action=(
                    f"loopx todo add --goal-id {goal_id} --role agent "
                    "--text '<public-safe route continuation advancement todo>'"
                ),
            )
        return build_hint(
            AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
            source="agent_scope_frontier",
            reason_code="successor_replan_required",
            target_todo_id=deferred_todo_id,
            quiet_noop_allowed=False,
        )

    if frontier_action in {
        AgentScopeFrontierAction.AGENT_SCOPE_WAIT,
        AgentScopeFrontierAction.REASSIGNMENT_REQUIRED,
    }:
        blocked_successor_todo_id = _first_compact_todo_id(
            frontier.get("blocked_successor_wait_candidates")
        )
        if blocked_successor_todo_id:
            return build_hint(
                AgentLaneFrontierHintDecision.QUIET_NOOP_BLOCKER,
                source="agent_scope_frontier",
                reason_code="blocked_successor_resume_pending",
                target_todo_id=blocked_successor_todo_id,
                quiet_noop_allowed=True,
            )
        blocker_todo_id = _first_compact_todo_id(frontier.get("blocking_handoff_gates"))
        if not blocker_todo_id:
            blocker_todo_id = _first_compact_todo_id(frontier.get("other_agent_claimed_items"))
        if blocker_todo_id:
            return build_hint(
                AgentLaneFrontierHintDecision.QUIET_NOOP_BLOCKER,
                source="agent_scope_frontier",
                reason_code="blocked_by_other_agent_frontier",
                target_todo_id=blocker_todo_id,
                quiet_noop_allowed=True,
            )
        return build_hint(
            AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
            source="agent_scope_frontier",
            reason_code="no_current_agent_advancement_todo",
            quiet_noop_allowed=True,
        )

    if frontier_action == AgentScopeFrontierAction.AGENT_SCOPE_EXHAUSTED:
        return build_hint(
            AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
            source="agent_scope_frontier",
            reason_code="agent_scope_exhausted",
            quiet_noop_allowed=True,
        )

    if not isinstance(agent_todo_summary, dict):
        return None
    current_advancement_count = int(
        agent_todo_summary.get("current_agent_claimed_advancement_count") or 0
    )
    current_monitor_count = int(agent_todo_summary.get("current_agent_claimed_monitor_count") or 0)
    unclaimed_count = _selectable_unclaimed_advancement_count(agent_todo_summary)
    lane = str(work_lane_contract.get("lane") or "") if isinstance(work_lane_contract, dict) else ""
    if current_advancement_count == 0 and unclaimed_count == 0 and current_monitor_count > 0:
        return build_hint(
            AgentLaneFrontierHintDecision.QUIET_NOOP_BLOCKER,
            source="agent_todo_summary",
            reason_code="only_current_agent_monitor_work_remains",
            quiet_noop_allowed=lane != TODO_TASK_CLASS_ADVANCEMENT,
        )
    return None


def _agent_scope_deferred_resume_candidates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in (
        "current_agent_deferred_resume_candidates",
        "unclaimed_deferred_resume_candidates",
    ):
        value = agent_todo_summary.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    if not candidates:
        value = agent_todo_summary.get("deferred_resume_candidates")
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                if not agent_scope_item_claimed_by_agent_or_unclaimed(
                    item,
                    agent_id=agent_id,
                ):
                    continue
                candidates.append(item)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        if todo_item_excludes_agent(item, agent_id=agent_id):
            continue
        if item.get("resume_ready") is not True:
            continue
        if not todo_item_is_deferred(item):
            continue
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(compact_todo_summary_item(item, text=str(item.get("text") or "").strip()))
    return sorted(unique, key=_todo_projection_sort_key)


def _agent_scope_monitor_blocked_resume_candidates(
    agent_todo_summary: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(agent_todo_summary, dict):
        return []
    candidates: list[dict[str, Any]] = []
    if agent_id:
        for key in (
            "current_agent_monitor_blocked_resume_candidates",
            "unclaimed_monitor_blocked_resume_candidates",
        ):
            value = agent_todo_summary.get(key)
            if isinstance(value, list):
                candidates.extend(item for item in value if isinstance(item, dict))
    else:
        value = agent_todo_summary.get("monitor_blocked_resume_candidates")
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        if todo_item_excludes_agent(item, agent_id=agent_id):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        if item.get("resume_ready") is not False:
            continue
        condition = item.get("resume_condition") if isinstance(item.get("resume_condition"), dict) else {}
        if normalize_todo_status(condition.get("target_status")) != TODO_STATUS_OPEN:
            continue
        target_todo_id = normalize_todo_id(
            item.get("blocking_monitor_todo_id")
            or condition.get("target_todo_id")
            or condition.get("target")
        )
        target_task_class = normalize_todo_task_class(
            condition.get("target_task_class"),
            text="",
        )
        if target_task_class != TODO_TASK_CLASS_MONITOR and not target_todo_id:
            continue
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        compact = compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        if target_todo_id:
            compact["blocking_monitor_todo_id"] = target_todo_id
        unique.append(compact)
    return sorted(unique, key=_todo_projection_sort_key)


def _agent_scope_cleared_without_successor_handoff_gates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    unique = _agent_scope_handoff_gates_by_state(
        agent_todo_summary,
        agent_id=agent_id,
        gate_state=HandoffGateState.CLEARED_WITHOUT_SUCCESSOR.value,
        preferred_key="current_agent_cleared_without_successor_handoff_gates",
    )
    return sorted(
        unique,
        key=lambda item: (
            -int(item.get("index") or 0),
            str(item.get("todo_id") or ""),
        ),
    )


def _agent_scope_handoff_gates_by_state(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str | None,
    gate_state: str,
    preferred_key: str,
) -> list[dict[str, Any]]:
    if not agent_id:
        return []
    gates = agent_todo_summary.get(preferred_key)
    if not isinstance(gates, list):
        gates = agent_todo_summary.get("handoff_gates")
    if not isinstance(gates, list):
        return []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in gates:
        if not isinstance(item, dict):
            continue
        if agent_id not in agent_scope_item_excluded_agents(item):
            continue
        if item.get("gate_state") != gate_state:
            continue
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        compact = dict(item)
        compact["text"] = str(item.get("text") or "").strip()
        selected.append(compact)
    return selected


def agent_scope_blocking_handoff_gates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str | None,
) -> list[dict[str, Any]]:
    selected = _agent_scope_handoff_gates_by_state(
        agent_todo_summary,
        agent_id=agent_id,
        gate_state=HandoffGateState.BLOCKING.value,
        preferred_key="current_agent_handoff_gates",
    )
    return sorted(selected, key=_todo_projection_sort_key)


def _agent_scope_blocking_handoff_gates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    return agent_scope_blocking_handoff_gates(agent_todo_summary, agent_id=agent_id)


def _route_continuation_candidate_matches_agent(
    item: dict[str, Any],
    *,
    agent_id: str,
) -> bool:
    return agent_scope_item_matches_agent_or_unclaimed(item, agent_id=agent_id)


def _agent_scope_route_continuation_replan_candidates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in (
        "current_agent_route_continuation_replan_candidates",
        "unclaimed_route_continuation_replan_candidates",
    ):
        value = agent_todo_summary.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    if not candidates:
        value = agent_todo_summary.get("route_continuation_replan_candidates")
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                if not _route_continuation_candidate_matches_agent(item, agent_id=agent_id):
                    continue
                candidates.append(item)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        if not _route_continuation_candidate_matches_agent(
            item,
            agent_id=agent_id,
        ):
            continue
        if item.get("route_continuation_replan_required") is False:
            continue
        identity = str(
            item.get("todo_id")
            or item.get("route_id")
            or item.get("route_key")
            or item.get("index")
            or item.get("text")
            or ""
        )
        if not identity or identity in seen:
            continue
        seen.add(identity)
        compact = compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        compact["route_continuation_replan_required"] = True
        if item.get("route_continuation_reason") is not None:
            compact["route_continuation_reason"] = item.get("route_continuation_reason")
        if item.get("route_id") is not None:
            compact["route_id"] = item.get("route_id")
        if item.get("route_key") is not None:
            compact["route_key"] = item.get("route_key")
        unique.append(compact)
    return sorted(unique, key=_todo_projection_sort_key)


def _agent_scope_no_candidate_frontier(
    *,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_lane_next_action: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    candidate_should_run: bool,
) -> dict[str, Any] | None:
    if not candidate_should_run:
        return None
    if not _agent_identity_has_scoped_lane(agent_identity):
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id or not isinstance(agent_todo_summary, dict):
        return None
    agent_label = "agent"
    if work_lane_contract_is_due_monitor_attempt(work_lane_contract):
        return None
    if isinstance(agent_lane_next_action, dict):
        deferred_resume_candidates = _agent_scope_deferred_resume_candidates(
            agent_todo_summary,
            agent_id=agent_id,
        )
        if deferred_resume_candidates:
            first_candidate = deferred_resume_candidates[0]
            if _todo_projection_sort_key(first_candidate)[0] < _todo_projection_sort_key(
                agent_lane_next_action
            )[0]:
                candidate_todo_id = (
                    str(first_candidate.get("todo_id") or "").strip() or "<todo_id>"
                )
                selected_todo_id = (
                    str(agent_lane_next_action.get("todo_id") or "").strip()
                    or "<open_todo_id>"
                )
                return build_agent_scope_frontier_payload(
                    agent_id=agent_id,
                    action=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED,
                    quiet_noop_allowed=False,
                    spend_policy=(
                        "spend once after validated priority successor replan/todo writeback"
                    ),
                    reason=(
                        f"ready deferred successor {candidate_todo_id} has higher priority "
                        f"than selected open advancement {selected_todo_id}; its lifecycle "
                        "must be resolved before lower-priority delivery"
                    ),
                    recommended_action=(
                        "Run a bounded successor replan before lower-priority delivery: "
                        f"reopen, supersede, or record a no-follow-up rationale for "
                        f"{candidate_todo_id}."
                    ),
                    requires_replan=True,
                    candidate_counts={
                        "deferred_resume_candidate_count": len(
                            deferred_resume_candidates
                        ),
                        "preempted_open_candidate_count": 1,
                    },
                    extra_fields={
                        "deferred_resume_candidates": deferred_resume_candidates[:3],
                        "preempted_open_candidate": compact_todo_summary_item(
                            agent_lane_next_action,
                            text=str(agent_lane_next_action.get("text") or "").strip(),
                        ),
                        "priority_preemption": True,
                    },
                )
        return None
    if work_lane_contract_requires_current_agent_attempt(work_lane_contract):
        return None
    has_advancement_contract = (
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("lane") == TODO_TASK_CLASS_ADVANCEMENT
        and work_lane_contract.get("must_attempt_work") is True
    )

    current_agent_count = int(agent_todo_summary.get("current_agent_claimed_advancement_count") or 0)
    current_agent_count = max(
        current_agent_count,
        _count_advancement_items(
            agent_todo_summary.get("current_agent_claimed_advancement_items"),
            claimed_by=agent_id,
        ),
    )
    unclaimed_count = _selectable_unclaimed_advancement_count(agent_todo_summary)
    executable_items = agent_todo_summary.get("executable_backlog_items")
    if isinstance(executable_items, list):
        current_agent_count = max(
            current_agent_count,
            _count_advancement_items(executable_items, claimed_by=agent_id),
        )
        unclaimed_count = _count_advancement_items(
            executable_items,
            claimed_by="__unclaimed__",
        )
    if current_agent_count > 0 or unclaimed_count > 0:
        return None

    monitor_blocked_resume_candidates = _agent_scope_monitor_blocked_resume_candidates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if monitor_blocked_resume_candidates:
        first_candidate = monitor_blocked_resume_candidates[0]
        candidate_todo_id = str(first_candidate.get("todo_id") or "").strip() or "<todo_id>"
        monitor_todo_id = (
            str(first_candidate.get("blocking_monitor_todo_id") or "").strip()
            or "<monitor_todo_id>"
        )
        reason = (
            f"current {agent_label} {agent_id} has advancement todo {candidate_todo_id} "
            f"gated by open continuous_monitor {monitor_todo_id}; a standing monitor "
            "cannot be the todo_done prerequisite for autonomous continuation"
        )
        recommended_action = (
            "Run a bounded gate-model repair before quiet wait: close/supersede "
            f"{monitor_todo_id} after validated evidence, or rewrite {candidate_todo_id} "
            "to use a non-blocking monitor contract before delivery."
        )
        return build_agent_scope_frontier_payload(
            agent_id=agent_id,
            action=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED,
            quiet_noop_allowed=False,
            spend_policy="spend once after validated standing-monitor gate repair/todo writeback",
            reason=reason,
            recommended_action=recommended_action,
            requires_replan=True,
            candidate_counts={
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "monitor_blocked_resume_candidate_count": len(monitor_blocked_resume_candidates),
            },
            extra_fields={
                "monitor_blocked_resume_candidates": monitor_blocked_resume_candidates[:3],
            },
        )

    deferred_resume_candidates = _agent_scope_deferred_resume_candidates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if deferred_resume_candidates:
        first_candidate = deferred_resume_candidates[0]
        candidate_todo_id = str(first_candidate.get("todo_id") or "").strip() or "<todo_id>"
        reason = (
            f"current {agent_label} {agent_id} has no open current/unclaimed "
            "advancement candidate, but a deferred successor resume condition is satisfied"
        )
        recommended_action = (
            "Run a bounded successor replan before delivery: reopen, supersede, "
            f"or record a no-follow-up rationale for {candidate_todo_id}."
        )
        return build_agent_scope_frontier_payload(
            agent_id=agent_id,
            action=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED,
            quiet_noop_allowed=False,
            spend_policy="spend once after validated successor replan/todo writeback",
            reason=reason,
            recommended_action=recommended_action,
            requires_replan=True,
            candidate_counts={
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "deferred_resume_candidate_count": len(deferred_resume_candidates),
            },
            extra_fields={"deferred_resume_candidates": deferred_resume_candidates[:3]},
        )

    blocked_successor_wait_candidates = todo_summary_blocked_successor_items(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if blocked_successor_wait_candidates:
        first_candidate = blocked_successor_wait_candidates[0]
        candidate_todo_id = (
            str(first_candidate.get("todo_id") or "").strip() or "<todo_id>"
        )
        resume_when = str(first_candidate.get("resume_when") or "").strip()
        return build_agent_scope_frontier_payload(
            agent_id=agent_id,
            action=AgentScopeFrontierAction.AGENT_SCOPE_WAIT,
            quiet_noop_allowed=True,
            spend_policy=(
                "no quota spend while an exact successor resume condition is pending"
            ),
            reason=(
                f"current {agent_label} {agent_id} has exact blocked successor "
                f"{candidate_todo_id} waiting on {resume_when}; another successor "
                "replan would duplicate the existing route"
            ),
            recommended_action=(
                f"Keep {agent_id} active but quiet until {resume_when} becomes ready; "
                "then resume ordinary todo/deferred-successor routing automatically."
            ),
            requires_replan=False,
            candidate_counts={
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "blocked_successor_wait_count": len(
                    blocked_successor_wait_candidates
                ),
            },
            extra_fields={
                "blocked_successor_wait_candidates": (
                    blocked_successor_wait_candidates[:3]
                ),
            },
        )

    route_continuation_replan_candidates = _agent_scope_route_continuation_replan_candidates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if route_continuation_replan_candidates:
        first_candidate = route_continuation_replan_candidates[0]
        route_label = (
            str(
                first_candidate.get("route_id")
                or first_candidate.get("route_key")
                or first_candidate.get("todo_id")
                or ""
            ).strip()
            or "<route>"
        )
        reason = (
            f"current {agent_label} {agent_id} has no open current/unclaimed "
            "advancement candidate, but the route continuation projection "
            f"requires a successor replan for {route_label}"
        )
        recommended_action = (
            "Run a bounded route continuation replan before quiet wait: create or "
            f"claim the next concrete {agent_id}/unclaimed advancement todo for "
            f"{route_label}, or record an explicit no-follow-up rationale."
        )
        return build_agent_scope_frontier_payload(
            agent_id=agent_id,
            action=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED,
            quiet_noop_allowed=False,
            spend_policy="spend once after validated route continuation replan/todo writeback",
            reason=reason,
            recommended_action=recommended_action,
            requires_replan=True,
            candidate_counts={
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "route_continuation_replan_candidate_count": len(
                    route_continuation_replan_candidates
                ),
            },
            extra_fields={
                "route_continuation_replan_candidates": route_continuation_replan_candidates[:3],
            },
        )

    blocking_handoff_gates = _agent_scope_blocking_handoff_gates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if blocking_handoff_gates:
        blocking_handoff_claimants = sorted(
            {
                claimed_by
                for item in blocking_handoff_gates
                for claimed_by in [agent_scope_item_claimed_by(item)]
                if claimed_by
            }
        )
        owner = ", ".join(blocking_handoff_claimants) or "the owning agent"
        reason = (
            f"current {agent_label} {agent_id} has no current/unclaimed advancement "
            f"candidate; blocking handoff work is claimed by {owner}"
        )
        recommended_action = (
            f"Keep {agent_id} active but quiet: wait for {owner} to finish the "
            "blocking handoff, reassign it, or create a concrete current-agent/"
            "unclaimed advancement todo before delivery."
        )
        return build_agent_scope_frontier_payload(
            agent_id=agent_id,
            action=AgentScopeFrontierAction.AGENT_SCOPE_WAIT,
            quiet_noop_allowed=True,
            spend_policy="no quota spend while the current agent has no in-scope runnable candidate",
            reason=reason,
            recommended_action=recommended_action,
            candidate_counts={
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "blocking_handoff_gate_count": len(blocking_handoff_gates),
            },
            extra_fields={
                "other_claimants": blocking_handoff_claimants,
                "blocking_handoff_claimants": blocking_handoff_claimants,
                "blocking_handoff_gates": blocking_handoff_gates[:3],
            },
        )

    cleared_handoff_gates = _agent_scope_cleared_without_successor_handoff_gates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if cleared_handoff_gates:
        first_item = cleared_handoff_gates[0]
        blocker_todo_id = str(first_item.get("todo_id") or "").strip() or "<todo_id>"
        unblocks_todo_id = normalize_todo_id(first_item.get("unblocks_todo_id"))
        target_text = (
            f" for unblocked todo {unblocks_todo_id}"
            if unblocks_todo_id
            else ""
        )
        reason = (
            f"current {agent_label} {agent_id} has no open current/unclaimed "
            f"advancement candidate, but blocking handoff {blocker_todo_id}"
            f"{target_text} is already done without a projected successor"
        )
        recommended_action = (
            "Run a bounded successor replan before quiet wait: reopen or supersede "
            f"{blocker_todo_id} into a concrete {agent_id}/unclaimed advancement todo, "
            "or record an explicit no-follow-up rationale."
        )
        return build_agent_scope_frontier_payload(
            agent_id=agent_id,
            action=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED,
            quiet_noop_allowed=False,
            spend_policy="spend once after validated successor replan/todo writeback",
            reason=reason,
            recommended_action=recommended_action,
            requires_replan=True,
            candidate_counts={
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "cleared_without_successor_handoff_count": len(cleared_handoff_gates),
            },
            extra_fields={
                "cleared_without_successor_handoff_gates": cleared_handoff_gates[:3],
            },
        )

    claimed_advancement_items = (
        agent_todo_summary.get("claimed_advancement_open_items")
        if isinstance(agent_todo_summary.get("claimed_advancement_open_items"), list)
        else []
    )
    other_advancement_items = [
        item
        for item in claimed_advancement_items
        if isinstance(item, dict)
        and _todo_item_is_actionable_open(item)
        and _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
        and agent_scope_item_claimed_by(item) not in {None, "", agent_id}
    ]
    other_claimants = sorted(
        {
            claimed_by
            for item in other_advancement_items
            for claimed_by in [agent_scope_item_claimed_by(item)]
            if claimed_by
        }
    )
    blocking_handoff_items = [
        item
        for item in other_advancement_items
        if agent_id in agent_scope_item_excluded_agents(item)
    ]
    blocking_handoff_claimants = sorted(
        {
            claimed_by
            for item in blocking_handoff_items
            for claimed_by in [agent_scope_item_claimed_by(item)]
            if claimed_by
        }
    )
    claim_scope = (
        agent_todo_summary.get("claim_scope")
        if isinstance(agent_todo_summary.get("claim_scope"), dict)
        else {}
    )
    if not has_advancement_contract and not other_advancement_items:
        return None
    if other_advancement_items:
        if blocking_handoff_claimants:
            action = AgentScopeFrontierAction.AGENT_SCOPE_WAIT
            owner = ", ".join(blocking_handoff_claimants)
            reason = (
                f"current {agent_label} {agent_id} has no current/unclaimed advancement "
                f"candidate; blocking handoff work is claimed by {owner}"
            )
            recommended_action = (
                f"Keep {agent_id} active but quiet: wait for {owner} to finish the "
                "blocking handoff, reassign it, or create a concrete current-agent/"
                "unclaimed advancement todo before delivery."
            )
        else:
            action = AgentScopeFrontierAction.REASSIGNMENT_REQUIRED
            owner = ", ".join(other_claimants) or "the owning agent"
            reason = (
                f"current {agent_label} {agent_id} has no current/unclaimed advancement "
                f"candidate; visible advancement work is claimed by {owner}"
            )
            recommended_action = (
                f"Keep {agent_id} active but quiet: wait for {owner} to finish, "
                "reassign, or create a concrete current-agent/unclaimed advancement "
                "todo before delivery."
            )
    else:
        action = AgentScopeFrontierAction.AGENT_SCOPE_EXHAUSTED
        reason = (
            f"current {agent_label} {agent_id} has no projected current/unclaimed "
            "advancement candidate despite a goal-level advancement lane"
        )
        recommended_action = (
            f"Keep {agent_id} active but quiet until LoopX projects a concrete "
            "current-agent or unclaimed advancement todo, or another peer transfers work."
        )

    return build_agent_scope_frontier_payload(
        agent_id=agent_id,
        action=action,
        quiet_noop_allowed=True,
        spend_policy="no quota spend while the current agent has no in-scope runnable candidate",
        reason=reason,
        recommended_action=recommended_action,
        candidate_counts={
            "current_agent_claimed_advancement_count": current_agent_count,
            "unclaimed_advancement_count": unclaimed_count,
            "other_agent_claimed_advancement_count": len(other_advancement_items),
            "other_agent_claimed_open_count": int(
                claim_scope.get("other_agent_claimed_open_count") or 0
            ),
        },
        extra_fields={
            "other_claimants": other_claimants,
            "blocking_handoff_claimants": blocking_handoff_claimants,
            "other_agent_claimed_items": [
                compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
                for item in other_advancement_items[:3]
            ],
        },
    )
