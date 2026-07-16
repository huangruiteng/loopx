from __future__ import annotations

from typing import Any

from ...state_projection import actions_are_projection_aligned
from ..todos.contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    normalize_todo_status,
    normalize_todo_task_class,
)
from ..todos.handoff_gate import HandoffGateState


GOAL_ROUTE_HINT_SCHEMA_VERSION = "goal_route_hint_v0"
GOAL_ROUTE_HINT_ITEM_LIMIT = 3


def _compact_text(value: Any, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _int_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _is_actionable_advancement(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("done") is True:
        return False
    status = normalize_todo_status(item.get("status"))
    if status and status != TODO_STATUS_OPEN:
        return False
    return (
        normalize_todo_task_class(
            item.get("task_class"),
            text=str(item.get("text") or ""),
            action_kind=item.get("action_kind"),
        )
        == TODO_TASK_CLASS_ADVANCEMENT
    )


def _compact_todo(item: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_actionable_advancement(item):
        return None
    text = _compact_text(item.get("text"), limit=220)
    if not text:
        return None
    payload: dict[str, Any] = {}
    for key, normalizer in (
        ("todo_id", normalize_todo_id),
        ("claimed_by", normalize_todo_claimed_by),
        ("blocks_agent", normalize_todo_blocks_agent),
        ("unblocks_todo_id", normalize_todo_id),
    ):
        normalized = normalizer(item.get(key))
        if normalized:
            payload[key] = normalized
    excluded_agents = normalize_todo_excluded_agents(item.get("excluded_agents"))
    if excluded_agents:
        payload["excluded_agents"] = excluded_agents
    for key in ("priority", "action_kind"):
        if item.get(key) is not None:
            payload[key] = item.get(key)
    if not payload.get("todo_id"):
        payload["text"] = _compact_text(text, limit=120)
    return payload


def _todo_items(
    items: Any,
    *,
    agent_id: str,
    claim: str,
    limit: int = GOAL_ROUTE_HINT_ITEM_LIMIT,
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claim == "current" and claimed_by != agent_id:
            continue
        if claim == "other" and (not claimed_by or claimed_by == agent_id):
            continue
        if claim == "unclaimed" and claimed_by:
            continue
        compact = _compact_todo(item)
        if not compact:
            continue
        identity = str(compact.get("todo_id") or compact.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(compact)
        if len(selected) >= limit:
            break
    return selected


def _count_advancement_items(items: Any, *, agent_id: str | None = None, claim: str | None = None) -> int:
    if not isinstance(items, list):
        return 0
    count = 0
    for item in items:
        if not isinstance(item, dict) or not _is_actionable_advancement(item):
            continue
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claim == "unclaimed" and claimed_by:
            continue
        if claim == "other" and (not claimed_by or claimed_by == agent_id):
            continue
        if claim == "current" and claimed_by != agent_id:
            continue
        count += 1
    return count


def _current_action(agent_lane_next_action: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(agent_lane_next_action, dict):
        return None
    action: dict[str, Any] = {}
    todo_id = normalize_todo_id(agent_lane_next_action.get("todo_id"))
    if todo_id:
        action["todo_id"] = todo_id
    for key in ("selected_by", "confidence", "source"):
        if agent_lane_next_action.get(key) is not None:
            action[key] = agent_lane_next_action.get(key)
    if not action.get("todo_id"):
        text = _compact_text(agent_lane_next_action.get("text"), limit=120)
        if not text:
            return None
        action["text"] = text
    if agent_lane_next_action.get("claim_required_before_work") is True:
        action["claim_required_before_work"] = True
    return action


def _blocking_handoff_gates(agent_todo_summary: dict[str, Any], *, agent_id: str) -> list[dict[str, Any]]:
    gates = agent_todo_summary.get("current_agent_handoff_gates")
    if not isinstance(gates, list):
        gates = agent_todo_summary.get("handoff_gates")
    if not isinstance(gates, list):
        return []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in gates:
        if not isinstance(item, dict):
            continue
        if agent_id not in normalize_todo_excluded_agents(item.get("excluded_agents")):
            continue
        if item.get("gate_state") != HandoffGateState.BLOCKING.value:
            continue
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        compact: dict[str, Any] = {}
        for key, normalizer in (
            ("todo_id", normalize_todo_id),
            ("claimed_by", normalize_todo_claimed_by),
            ("unblocks_todo_id", normalize_todo_id),
        ):
            normalized = normalizer(item.get(key))
            if normalized:
                compact[key] = normalized
        excluded_agents = normalize_todo_excluded_agents(item.get("excluded_agents"))
        if excluded_agents:
            compact["excluded_agents"] = excluded_agents
        if item.get("gate_state") is not None:
            compact["gate_state"] = item.get("gate_state")
        selected.append(compact)
        if len(selected) >= GOAL_ROUTE_HINT_ITEM_LIMIT:
            break
    return selected


def build_goal_route_hint(
    *,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_lane_next_action: dict[str, Any] | None,
    agent_scope_frontier: dict[str, Any] | None,
    agent_lane_frontier_hint: dict[str, Any] | None,
    active_state_next_action: Any,
    latest_run_recommended_action: Any,
    selected_recommended_action: Any,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict):
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return None
    agent_summary = agent_todo_summary if isinstance(agent_todo_summary, dict) else {}
    current_action = _current_action(agent_lane_next_action)
    other_agent_actions = _todo_items(
        agent_summary.get("claimed_advancement_open_items"),
        agent_id=agent_id,
        claim="other",
    )
    if not other_agent_actions:
        other_agent_actions = _todo_items(
            agent_summary.get("claimed_by_others_items"),
            agent_id=agent_id,
            claim="other",
        )
    executable_items = agent_summary.get("executable_backlog_items")
    unclaimed_source = (
        executable_items
        if isinstance(executable_items, list)
        else agent_summary.get("unclaimed_priority_open_items")
    )
    unclaimed_actions = _todo_items(
        unclaimed_source,
        agent_id=agent_id,
        claim="unclaimed",
    )
    blocking_handoff_gates = _blocking_handoff_gates(agent_summary, agent_id=agent_id)
    current_count = _int_count(agent_summary.get("current_agent_claimed_advancement_count"))
    unclaimed_count = _count_advancement_items(
        unclaimed_source,
        agent_id=agent_id,
        claim="unclaimed",
    )
    other_count = _int_count(agent_summary.get("claimed_advancement_open_count"))
    if not other_count:
        other_count = _count_advancement_items(
            agent_summary.get("claimed_advancement_open_items"),
            agent_id=agent_id,
            claim="other",
        )
    else:
        other_count = max(0, other_count - current_count)
    other_count = max(other_count, len(other_agent_actions))

    route_decision = "durable_goal_route"
    reason = "no agent-lane override is needed; preserve durable goal Next Action"
    if current_action:
        if current_action.get("claim_required_before_work") is True:
            route_decision = "claim_then_run_current_agent"
            reason = "quota selected an unclaimed in-scope todo for this agent lane"
        else:
            route_decision = "run_current_agent_lane"
            reason = "quota selected a runnable current-agent lane todo"
    elif isinstance(agent_scope_frontier, dict):
        route_decision = str(
            agent_scope_frontier.get("effective_action")
            or agent_scope_frontier.get("action")
            or "agent_scope_frontier"
        )
        reason = str(agent_scope_frontier.get("reason") or "agent-scope frontier blocks delivery")
    elif blocking_handoff_gates or other_agent_actions:
        route_decision = "wait_or_reassign_other_agent_lane"
        reason = "visible advancement work is owned by another agent lane"
    elif unclaimed_actions:
        route_decision = "claim_unowned_in_scope"
        reason = "unclaimed advancement work is available to the current agent lane"

    active_text = _compact_text(active_state_next_action, limit=260)
    selected_text = _compact_text(selected_recommended_action, limit=260)
    latest_text = _compact_text(latest_run_recommended_action, limit=260)
    hint: dict[str, Any] = {
        "schema_version": GOAL_ROUTE_HINT_SCHEMA_VERSION,
        "kind": "agent_lane_synthesis",
        "agent_id": agent_id,
        "agent_model": "peer_v1",
        "route_decision": route_decision,
        "reason": reason,
        "preserves_goal_next_action": True,
        "goal_next_action_mutation": "none",
        "counts": {
            "current_agent_claimed_advancement_count": current_count,
            "unclaimed_advancement_count": unclaimed_count,
            "other_agent_claimed_advancement_count": other_count,
            "blocking_handoff_gate_count": len(blocking_handoff_gates),
        },
        "selected_action_differs_from_durable": bool(
            active_text
            and selected_text
            and not actions_are_projection_aligned(active_text, selected_text)
        ),
        "has_durable_next_action": bool(active_text),
        "has_latest_run_recommended_action": bool(latest_text),
    }
    if current_action:
        hint["current_agent_next_action"] = current_action
    if other_agent_actions:
        hint["other_agent_next_actions"] = other_agent_actions
    if unclaimed_actions:
        hint["unclaimed_next_actions"] = unclaimed_actions
    if blocking_handoff_gates:
        hint["blocking_handoff_gates"] = blocking_handoff_gates
    if isinstance(agent_lane_frontier_hint, dict):
        hint["frontier_hint"] = {
            key: agent_lane_frontier_hint[key]
            for key in (
                "decision",
                "source",
                "reason_code",
                "target_todo_id",
                "quiet_noop_allowed",
            )
            if agent_lane_frontier_hint.get(key) is not None
        }
    return hint
