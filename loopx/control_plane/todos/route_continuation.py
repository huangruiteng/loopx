from __future__ import annotations

from typing import Any

from .contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_required_write_scopes,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_excluded_agents,
    normalize_todo_required_decision_scopes,
    normalize_todo_task_class,
)
from .handoff_gate import todo_summary_handoff_gates
from .projection import todo_projection_sort_key


TODO_ROUTE_CONTINUATION_SELECTION_POLICY = (
    "quota may wake the current peer for route continuation replan "
    "candidates claimed by that agent or unclaimed; other-agent route "
    "candidates remain diagnostic visibility"
)


def _todo_task_class(item: dict[str, Any]) -> str:
    text = " ".join(
        str(value or "")
        for value in (item.get("title"), item.get("text"))
        if str(value or "").strip()
    )
    return normalize_todo_task_class(
        item.get("task_class"),
        text=text,
        action_kind=item.get("action_kind"),
    )


def _compact_route_continuation_item(
    item: dict[str, Any],
    *,
    text: str,
) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "index": item.get("index"),
        "text": text,
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
        "required_write_scopes",
        "required_capabilities",
        "target_capabilities",
        "decision_scope",
        "required_decision_scopes",
        "claimed_by",
        "blocks_agent",
        "excluded_agents",
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
        "route_continuation_replan_required",
        "route_continuation_reason",
        "route_id",
        "route_key",
        "completed_at",
        "updated_at",
        "superseded_by",
    ):
        if item.get(key) is not None:
            compact[key] = item.get(key)
    required_write_scopes = normalize_required_write_scopes(compact.get("required_write_scopes"))
    if required_write_scopes:
        compact["required_write_scopes"] = required_write_scopes
    else:
        compact.pop("required_write_scopes", None)
    decision_scope = normalize_todo_decision_scope(compact.get("decision_scope"))
    if decision_scope:
        compact["decision_scope"] = decision_scope
    else:
        compact.pop("decision_scope", None)
    required_decision_scopes = normalize_todo_required_decision_scopes(
        compact.get("required_decision_scopes")
    )
    if required_decision_scopes:
        compact["required_decision_scopes"] = required_decision_scopes
    else:
        compact.pop("required_decision_scopes", None)
    compact["task_class"] = _todo_task_class(compact)
    return compact


def todo_summary_route_continuation_candidates(
    value: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    source_items: list[dict[str, Any]] = []
    for key in (
        "route_continuation_replan_candidates",
        "route_continuation_candidates",
    ):
        raw_items = value.get(key) if isinstance(value.get(key), list) else []
        source_items.extend(item for item in raw_items if isinstance(item, dict))

    source_items.extend(
        item
        for item in todo_summary_handoff_gates(value)
        if isinstance(item, dict)
        and item.get("route_continuation_replan_required") is True
    )
    if not source_items:
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in source_items:
        if item.get("route_continuation_replan_required") is False:
            continue
        task_class = item.get("task_class")
        if task_class is not None and _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        text = str(
            item.get("text")
            or item.get("title")
            or item.get("recommended_action")
            or item.get("route_continuation_reason")
            or ""
        ).strip()
        identity = str(
            item.get("todo_id")
            or item.get("route_id")
            or item.get("route_key")
            or item.get("index")
            or text
        )
        if not identity or identity in seen:
            continue
        seen.add(identity)
        compact = _compact_route_continuation_item(item, text=text)
        compact["route_continuation_replan_required"] = True
        if item.get("route_continuation_reason") is not None:
            compact["route_continuation_reason"] = item.get("route_continuation_reason")
        if item.get("route_id") is not None:
            compact["route_id"] = item.get("route_id")
        if item.get("route_key") is not None:
            compact["route_key"] = item.get("route_key")
        candidates.append(compact)
    return sorted(candidates, key=todo_projection_sort_key)


def route_continuation_candidate_matches_agent(
    item: dict[str, Any],
    *,
    agent_id: str,
) -> bool:
    if agent_id in normalize_todo_excluded_agents(item.get("excluded_agents")):
        return False
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    return not claimed_by or claimed_by == agent_id


def _agent_filtered_route_continuation_items(
    items: list[dict[str, Any]],
    *,
    agent_id: str | None,
    claim: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in items:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claim == "current":
            if not agent_id or not route_continuation_candidate_matches_agent(
                item,
                agent_id=agent_id,
            ):
                continue
        elif claim == "unclaimed":
            if claimed_by:
                continue
        elif claim == "other":
            if not agent_id:
                continue
            if route_continuation_candidate_matches_agent(item, agent_id=agent_id):
                continue
        selected.append(item)
    return selected


def build_todo_route_continuation_lanes(
    value: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
    item_limit: int,
) -> dict[str, Any]:
    candidates = todo_summary_route_continuation_candidates(value)
    if not candidates:
        return {}
    lanes: dict[str, Any] = {
        "route_continuation_replan_count": len(candidates),
        "route_continuation_replan_candidates": candidates[:item_limit],
    }
    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id:
        current_agent_candidates = _agent_filtered_route_continuation_items(
            candidates,
            agent_id=agent_id,
            claim="current",
        )
        unclaimed_candidates = _agent_filtered_route_continuation_items(
            candidates,
            agent_id=agent_id,
            claim="unclaimed",
        )
        other_agent_candidates = _agent_filtered_route_continuation_items(
            candidates,
            agent_id=agent_id,
            claim="other",
        )
        lanes.update(
            {
                "current_agent_route_continuation_replan_candidates": (
                    current_agent_candidates[:item_limit]
                ),
                "unclaimed_route_continuation_replan_candidates": (
                    unclaimed_candidates[:item_limit]
                ),
                "other_agent_route_continuation_replan_candidates": (
                    other_agent_candidates[:item_limit]
                ),
                "current_agent_route_continuation_replan_count": len(
                    current_agent_candidates
                ),
                "unclaimed_route_continuation_replan_count": len(unclaimed_candidates),
                "other_agent_route_continuation_replan_count": len(other_agent_candidates),
                "route_continuation_replan_selection_policy": (
                    TODO_ROUTE_CONTINUATION_SELECTION_POLICY
                ),
            }
        )
    return lanes
