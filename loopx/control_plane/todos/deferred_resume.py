from __future__ import annotations

from typing import Any

from .contract import (
    TODO_RESUME_KIND_CAPACITY_AVAILABLE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_required_capabilities,
    normalize_required_write_scopes,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
)
from .projection import todo_item_is_deferred, todo_projection_sort_key


TODO_DEFERRED_RESUME_SELECTION_POLICY = (
    "quota may wake the current side-agent only for ready deferred todos "
    "claimed by that agent or unclaimed; other-agent deferred todos remain "
    "diagnostic visibility"
)
TODO_MONITOR_BLOCKED_RESUME_SELECTION_POLICY = (
    "open advancement todos gated by todo_done:<continuous_monitor> must "
    "project as successor replan/state repair instead of quiet monitor wait"
)


def resolve_capacity_resume_summary(
    value: Any,
    *,
    available_capabilities: Any,
) -> Any:
    """Resolve capacity-backed deferred todos from the quota host capability set."""
    if not isinstance(value, dict):
        return value
    available = set(normalize_required_capabilities(available_capabilities))
    resolved = dict(value)
    deferred_items = todo_summary_deferred_items(value, "deferred_items")
    for item in deferred_items:
        resume_when = normalize_todo_resume_when(item.get("resume_when")) or ""
        kind, separator, target = resume_when.partition(":")
        if kind != TODO_RESUME_KIND_CAPACITY_AVAILABLE or not separator or not target:
            continue
        satisfied = target in available
        condition = (
            dict(item.get("resume_condition"))
            if isinstance(item.get("resume_condition"), dict)
            else {}
        )
        condition.update(
            {
                "schema_version": "todo_resume_condition_v0",
                "resume_when": resume_when,
                "kind": kind,
                "target": target,
                "capability": target,
                "provider": "runtime_available_capabilities",
                "provider_required": False,
                "satisfied": satisfied,
            }
        )
        condition.pop("unsupported", None)
        item["resume_condition"] = condition
        item["resume_ready"] = satisfied
    resolved["deferred_items"] = deferred_items
    resolved["deferred_resume_candidates"] = [
        item for item in deferred_items if item.get("resume_ready") is True
    ]
    return resolved


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


def _compact_deferred_resume_item(
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
        "continuation_policy",
        "required_write_scopes",
        "required_capabilities",
        "target_capabilities",
        "decision_scope",
        "required_decision_scopes",
        "claimed_by",
        "blocks_agent",
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


def todo_summary_deferred_items(
    value: dict[str, Any],
    key: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    source_items = value.get(key) if isinstance(value.get(key), list) else []
    if not source_items and key == "deferred_items":
        source_items = [
            item
            for item in value.get("items", [])
            if isinstance(item, dict) and todo_item_is_deferred(item)
        ]
    items: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        compact = _compact_deferred_resume_item(item, text=text)
        resume_when = normalize_todo_resume_when(item.get("resume_when"))
        if resume_when:
            compact["resume_when"] = resume_when
        if item.get("resume_condition") is not None:
            compact["resume_condition"] = item.get("resume_condition")
        if item.get("resume_ready") is not None:
            compact["resume_ready"] = bool(item.get("resume_ready"))
        if todo_item_is_deferred(compact):
            items.append(compact)
    return sorted(items, key=todo_projection_sort_key)


def _dedupe_todo_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, Any]] = set()
    for item in items:
        todo_id = normalize_todo_id(item.get("todo_id")) or ""
        text = str(item.get("text") or "").strip()
        identity = (todo_id, text, item.get("index"))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(item)
    return unique


def todo_summary_resume_blocked_items(value: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    source_items = (
        value.get("resume_blocked_items")
        if isinstance(value.get("resume_blocked_items"), list)
        else []
    )
    if not source_items:
        for key in ("items", "backlog_items", "first_open_items"):
            raw_items = value.get(key) if isinstance(value.get(key), list) else []
            source_items.extend(item for item in raw_items if isinstance(item, dict))
    items: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        if item.get("done") is True:
            continue
        if not normalize_todo_resume_when(item.get("resume_when")):
            continue
        if item.get("resume_ready") is not False:
            continue
        items.append(_compact_deferred_resume_item(item, text=text))
    return sorted(_dedupe_todo_items(items), key=todo_projection_sort_key)


def _monitor_target_todo_ids(value: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in (
        "monitor_open_items",
        "current_agent_claimed_monitor_items",
        "claimed_monitor_open_items",
        "items",
        "backlog_items",
        "first_open_items",
    ):
        source_items = value.get(key) if isinstance(value.get(key), list) else []
        for item in source_items:
            if not isinstance(item, dict):
                continue
            todo_id = normalize_todo_id(item.get("todo_id"))
            if not todo_id:
                continue
            if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR:
                ids.add(todo_id)
    return ids


def todo_summary_monitor_blocked_resume_items(
    value: dict[str, Any],
) -> list[dict[str, Any]]:
    monitor_ids = _monitor_target_todo_ids(value)
    candidates: list[dict[str, Any]] = []
    for item in todo_summary_resume_blocked_items(value):
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        condition = (
            item.get("resume_condition")
            if isinstance(item.get("resume_condition"), dict)
            else {}
        )
        target_todo_id = normalize_todo_id(
            condition.get("target_todo_id") or condition.get("target")
        )
        target_status = normalize_todo_status(condition.get("target_status"))
        target_task_class = normalize_todo_task_class(
            condition.get("target_task_class"),
            text="",
        )
        if target_status != TODO_STATUS_OPEN:
            continue
        if target_task_class != TODO_TASK_CLASS_MONITOR and target_todo_id not in monitor_ids:
            continue
        candidate = dict(item)
        if target_todo_id:
            candidate["blocking_monitor_todo_id"] = target_todo_id
        candidates.append(candidate)
    return sorted(_dedupe_todo_items(candidates), key=todo_projection_sort_key)


def _agent_claim_filtered_deferred_items(
    items: list[dict[str, Any]],
    *,
    agent_id: str | None,
    claim: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in items:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claim == "current" and claimed_by != agent_id:
            continue
        if claim == "unclaimed" and claimed_by:
            continue
        if claim == "other" and (not claimed_by or claimed_by == agent_id):
            continue
        selected.append(item)
    return selected


def build_todo_resume_blocked_visibility_lanes(
    value: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
    item_limit: int,
) -> dict[str, Any]:
    resume_blocked_items = todo_summary_resume_blocked_items(value)
    monitor_blocked_items = todo_summary_monitor_blocked_resume_items(value)
    if not resume_blocked_items and not monitor_blocked_items:
        return {}
    lanes: dict[str, Any] = {
        "resume_blocked_count": len(resume_blocked_items),
        "resume_blocked_items": resume_blocked_items[:item_limit],
    }
    if monitor_blocked_items:
        lanes.update(
            {
                "monitor_blocked_resume_count": len(monitor_blocked_items),
                "monitor_blocked_resume_candidates": monitor_blocked_items[
                    :item_limit
                ],
            }
        )
    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id and monitor_blocked_items:
        current_agent_candidates = _agent_claim_filtered_deferred_items(
            monitor_blocked_items,
            agent_id=agent_id,
            claim="current",
        )
        unclaimed_candidates = _agent_claim_filtered_deferred_items(
            monitor_blocked_items,
            agent_id=agent_id,
            claim="unclaimed",
        )
        other_agent_candidates = _agent_claim_filtered_deferred_items(
            monitor_blocked_items,
            agent_id=agent_id,
            claim="other",
        )
        lanes.update(
            {
                "current_agent_monitor_blocked_resume_candidates": (
                    current_agent_candidates[:item_limit]
                ),
                "unclaimed_monitor_blocked_resume_candidates": (
                    unclaimed_candidates[:item_limit]
                ),
                "other_agent_monitor_blocked_resume_candidates": (
                    other_agent_candidates[:item_limit]
                ),
                "current_agent_monitor_blocked_resume_count": len(
                    current_agent_candidates
                ),
                "unclaimed_monitor_blocked_resume_count": len(unclaimed_candidates),
                "other_agent_monitor_blocked_resume_count": len(other_agent_candidates),
                "monitor_blocked_resume_selection_policy": (
                    TODO_MONITOR_BLOCKED_RESUME_SELECTION_POLICY
                ),
            }
        )
    return lanes


def build_todo_deferred_visibility_lanes(
    value: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
    item_limit: int,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    deferred_items = todo_summary_deferred_items(value, "deferred_items")
    deferred_resume_candidates = [
        item
        for item in todo_summary_deferred_items(value, "deferred_resume_candidates")
        if item.get("resume_ready") is True
    ]
    if not deferred_items and not deferred_resume_candidates and not value.get("deferred_count"):
        return {}

    lanes: dict[str, Any] = {
        "deferred_count": value.get("deferred_count", len(deferred_items)),
        "deferred_visibility_limit": item_limit,
        "deferred_items": deferred_items[:item_limit],
        "deferred_resume_candidates": deferred_resume_candidates[:item_limit],
    }
    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id:
        current_agent_candidates = _agent_claim_filtered_deferred_items(
            deferred_resume_candidates,
            agent_id=agent_id,
            claim="current",
        )
        unclaimed_candidates = _agent_claim_filtered_deferred_items(
            deferred_resume_candidates,
            agent_id=agent_id,
            claim="unclaimed",
        )
        other_agent_candidates = _agent_claim_filtered_deferred_items(
            deferred_resume_candidates,
            agent_id=agent_id,
            claim="other",
        )
        lanes.update(
            {
                "current_agent_deferred_resume_candidates": (
                    current_agent_candidates[:item_limit]
                ),
                "unclaimed_deferred_resume_candidates": (
                    unclaimed_candidates[:item_limit]
                ),
                "other_agent_deferred_resume_candidates": (
                    other_agent_candidates[:item_limit]
                ),
                "current_agent_deferred_resume_count": len(current_agent_candidates),
                "unclaimed_deferred_resume_count": len(unclaimed_candidates),
                "other_agent_deferred_resume_count": len(other_agent_candidates),
                "deferred_resume_selection_policy": (
                    TODO_DEFERRED_RESUME_SELECTION_POLICY
                ),
            }
        )
    return lanes
